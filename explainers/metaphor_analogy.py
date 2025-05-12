# explainers/metaphor_analogy.py
import os
import ollama
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE_FOR_EXPLAINER = True
except ImportError:
    GEMINI_AVAILABLE_FOR_EXPLAINER = False

def explain(base_explanation, llm_client, model_name, provider, **kwargs):
    """
    Generates a metaphor or analogy to explain the code based on the
    base explanation, using a secondary call to the specified LLM provider.

    Args:
        base_explanation (str): The initial detailed explanation text.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        **kwargs: Accepts other potential arguments. Expected: 'api_key' if provider is 'gemini'.

    Returns:
        str: A metaphorical explanation of the code, or an error message.
    """
    print("Explainer [metaphor_analogy]: Requesting metaphorical explanation from LLM...")

    prompt = f"""
Based *only* on the following detailed code analysis:

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

Please generate a creative and insightful metaphor or real-world analogy to explain the overall structure and functionality of the code described in the analysis.
Describe the analogy and briefly map the key components or processes mentioned in the analysis to elements within your analogy.

Example: "Think of this code as a custom coffee shop. Requests are orders placed by customers. The main router function is the barista who directs the order. Specific functions are like different coffee machines (espresso, drip) that prepare the drink. The database is the cash register and order history log."

Metaphor/Analogy Explanation:
"""

    try:
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                 return f"Error [metaphor_analogy]: Invalid or missing Ollama client for secondary call."

            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                # Consider slightly higher temperature for creativity
                # options={'temperature': 0.7}
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                return response.message.content
            else:
                return f"Error [metaphor_analogy]: Unexpected Ollama response structure. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [metaphor_analogy]: Gemini library not available for secondary call."

            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                 return "Error [metaphor_analogy]: Gemini API key not available for secondary call."

            genai.configure(api_key=api_key_for_gemini)
            # Use a model known for creative tasks if possible, otherwise default is fine
            gemini_model = genai.GenerativeModel(model_name)
            # Potentially adjust safety settings if needed for more creative output
            response = gemini_model.generate_content(prompt) #, safety_settings=...)

            explanation_text = ""
            if response and hasattr(response, 'text'):
                explanation_text = response.text
            elif response and hasattr(response, 'parts') and response.parts:
                 explanation_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))

            if explanation_text and explanation_text.strip():
                return explanation_text
            else:
                 feedback_info = ""
                 try: # Get feedback details if available
                     if hasattr(response, 'prompt_feedback'): feedback_info += f" Prompt Feedback: {response.prompt_feedback}"
                     if hasattr(response, 'candidates') and response.candidates:
                          feedback_info += f" Finish Reason: {response.candidates[0].finish_reason}"
                          feedback_info += f" Safety Ratings: {response.candidates[0].safety_ratings}"
                 except Exception: pass
                 return f"Error [metaphor_analogy]: Could not extract metaphor from Gemini.{feedback_info} Raw Response Excerpt: {str(response)[:200]}..."
        else:
            return f"Error [metaphor_analogy]: Unknown provider '{provider}' for secondary call."

    except Exception as e:
        return f"Error [metaphor_analogy]: Exception during LLM call ({provider}, model: {model_name}) for metaphor: {type(e).__name__}: {e}"

