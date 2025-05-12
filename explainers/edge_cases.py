# explainers/edge_cases.py
# (Formerly potential_bugs.py - focusing now on edge cases for testing)
import os
import ollama
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE_FOR_EXPLAINER = True
except ImportError:
    GEMINI_AVAILABLE_FOR_EXPLAINER = False

def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    """
    Asks the LLM to identify edge cases based on the base explanation and
    original code, focusing on scenarios useful for automated testing.

    Args:
        base_explanation (str): The initial detailed explanation text.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        original_code (str): The original source code provided by the user.
        **kwargs: Accepts other potential arguments. Expected: 'api_key' if provider is 'gemini'.

    Returns:
        str: A list or description of potential edge cases for testing, or an error message.
    """
    # Updated print statement
    print("Explainer [edge_cases]: Requesting edge case analysis for testing from LLM...")

    # Updated prompt focusing on edge cases for automated tests
    prompt = f"""
Based on the following detailed code analysis AND the original source code provided below, please identify potential **edge cases** that would be important to cover when writing automated tests (unit tests, integration tests, etc.).

Focus specifically on scenarios that might not be immediately obvious or represent boundary conditions, such as:
* Empty inputs (e.g., empty strings, zero values, empty lists/arrays)
* Null or undefined inputs
* Very large or maximum allowed inputs
* Inputs with special characters or unusual formatting
* Zero iterations in loops
* Off-by-one errors in indexing or conditions
* Specific sequences of operations that might lead to unexpected states
* Resource exhaustion scenarios (if applicable/discernible)
* Concurrency issues leading to race conditions or deadlocks (if applicable)
* Failure conditions (e.g., network errors, file not found) and how the code should react

For each edge case identified, briefly explain *why* it's relevant for testing. If no significant edge cases are apparent from the provided information, state that clearly.

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

--- Original Source Code Start ---
{original_code}
--- Original Source Code End ---

Edge Cases for Automated Testing:
"""

    try:
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                 # Updated error message prefix
                 return f"Error [edge_cases]: Invalid or missing Ollama client for secondary call."

            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}]
                # Keep temperature low for analytical response
                # options={'temperature': 0.2}
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                return response.message.content
            else:
                 # Updated error message prefix
                return f"Error [edge_cases]: Unexpected Ollama response structure. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                 # Updated error message prefix
                return "Error [edge_cases]: Gemini library not available for secondary call."

            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                  # Updated error message prefix
                 return "Error [edge_cases]: Gemini API key not available for secondary call."

            genai.configure(api_key=api_key_for_gemini)
            gemini_model = genai.GenerativeModel(model_name)
            response = gemini_model.generate_content(prompt) # Add safety_settings if needed

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
                  # Updated error message prefix
                 return f"Error [edge_cases]: Could not extract edge cases from Gemini.{feedback_info} Raw Response Excerpt: {str(response)[:200]}..."
        else:
             # Updated error message prefix
            return f"Error [edge_cases]: Unknown provider '{provider}' for secondary call."

    except Exception as e:
         # Updated error message prefix
        return f"Error [edge_cases]: Exception during LLM call ({provider}, model: {model_name}) for edge cases: {type(e).__name__}: {e}"

