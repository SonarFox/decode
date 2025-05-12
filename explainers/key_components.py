# explainers/key_components.py
import os # Added to use os.getenv
import ollama # For potential direct Ollama calls if llm_client is Ollama
# Import genai if you plan to allow Gemini for secondary calls as well
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE_FOR_EXPLAINER = True
except ImportError:
    GEMINI_AVAILABLE_FOR_EXPLAINER = False


# *** CORRECTED FUNCTION NAME: Renamed from 'explain_key_components' to 'explain' ***
def explain(base_explanation, llm_client, model_name, provider, **kwargs):
    """
    Identifies and lists key components from the base explanation
    by making another call to the specified LLM provider.

    Args:
        base_explanation (str): The initial detailed explanation text.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        **kwargs: Accepts other potential arguments. Expected: 'api_key' if provider is 'gemini'.

    Returns:
        str: A list or description of key components, or an error message.
    """
    print("Explainer [key_components]: Requesting key component identification from LLM...")

    prompt = f"""
Based *only* on the following detailed code analysis:

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

Please identify and list the key components (such as main functions, classes, modules, or significant structures) described in the analysis.
For each component, provide a very brief (one-sentence) description of its purpose as mentioned in the analysis.
Present this as a bulleted list.

Example:
* `process_data()`: This function is responsible for processing the input data.
* `UserClass`: This class represents a user in the system.

Key Components:
"""

    try:
        if provider == 'ollama':
            if not llm_client: # Should be ollama.Client instance
                return "Error [key_components]: Ollama client not provided for secondary call."
            # Ensure llm_client is actually an Ollama client instance before calling chat
            if not isinstance(llm_client, ollama.Client):
                 return f"Error [key_components]: Invalid Ollama client type provided: {type(llm_client)}"

            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            # Check response using attribute access
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                return response.message.content
            else:
                return f"Error [key_components]: Unexpected Ollama response structure for components. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [key_components]: Gemini library not available for secondary call."

            # Get API key from kwargs passed by main script
            api_key_for_gemini = kwargs.get('api_key')
            if not api_key_for_gemini:
                 # Fallback to environment variable if not passed in kwargs (less ideal)
                 api_key_for_gemini = os.getenv("GEMINI_API_KEY")
                 if not api_key_for_gemini:
                      return "Error [key_components]: Gemini API key not available for secondary call (checked kwargs and ENV)."

            # Configure Gemini API within this function scope
            genai.configure(api_key=api_key_for_gemini)

            gemini_model = genai.GenerativeModel(model_name)
            response = gemini_model.generate_content(prompt)

            explanation_text = ""
            # Check response using attribute access
            if response and hasattr(response, 'text'):
                explanation_text = response.text
            elif response and hasattr(response, 'parts') and response.parts:
                 explanation_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))

            if explanation_text and explanation_text.strip():
                return explanation_text
            else:
                 # Add more details if response is empty/blocked
                 feedback_info = ""
                 try:
                     if hasattr(response, 'prompt_feedback'):
                          feedback_info += f" Prompt Feedback: {response.prompt_feedback}"
                     if hasattr(response, 'candidates') and response.candidates:
                          feedback_info += f" Finish Reason: {response.candidates[0].finish_reason}"
                          feedback_info += f" Safety Ratings: {response.candidates[0].safety_ratings}"
                 except Exception: pass # Ignore errors getting feedback details
                 return f"Error [key_components]: Could not extract component list from Gemini (check for empty content or safety blocks).{feedback_info} Raw Response Excerpt: {str(response)[:200]}..."
        else:
            return f"Error [key_components]: Unknown provider '{provider}' for secondary call."

    except Exception as e:
        # Provide more context in the error message
        return f"Error [key_components]: Exception during LLM call ({provider}, model: {model_name}) for components: {type(e).__name__}: {e}"

