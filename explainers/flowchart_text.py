# explainers/flowchart_text.py
import os
import ollama
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE_FOR_EXPLAINER = True
except ImportError:
    GEMINI_AVAILABLE_FOR_EXPLAINER = False

def explain(base_explanation, llm_client, model_name, provider, **kwargs):
    """
    Asks the LLM to generate a text-based description of the code's
    execution flow, suitable for creating a flowchart.

    Args:
        base_explanation (str): The initial detailed explanation text.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        **kwargs: Accepts other potential arguments. Expected: 'api_key' if provider is 'gemini'.

    Returns:
        str: A text-based flowchart description, or an error message.
    """
    print("Explainer [flowchart_text]: Requesting text-based flowchart description from LLM...")

    # Prompt asking for flowchart-like text, referencing the base explanation
    prompt = f"""
Based *only* on the following detailed code analysis, focusing on the 'Execution Flow' and 'Component Interaction' sections if available:

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

Describe the typical execution flow of the code step-by-step using simple text notation suitable for building a flowchart. Use terms like:
* `Start` / `End`
* `Process: [Action]` (e.g., `Process: Read configuration file`)
* `Input: [Data]` (e.g., `Input: User credentials`)
* `Output: [Result]` (e.g., `Output: Display results`)
* `Decision: [Condition]?` (e.g., `Decision: Is user valid?`)
* `Loop: [Condition/Items]` / `End Loop`
* `Call: [Function/Method]`
* `Parallel: [Tasks]` / `End Parallel` (if applicable)
* `Sub-process: [Name]` (for complex sections)

Connect steps logically using `->` (arrow). Keep descriptions brief and focused on the flow derived from the analysis.

Example:
Start -> Input: File path -> Process: Read file content -> Loop: Each line -> Decision: Is line valid? -> (Yes) Process: Extract data -> (No) Process: Log error -> End Loop -> Output: Summary report -> End

Provide *only* the text-based flowchart description. Do not include explanations about the format itself. If the flow isn't clear from the analysis, state that.
"""

    try:
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                 return f"Error [flowchart_text]: Invalid or missing Ollama client for secondary call."

            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.1} # Low temperature for structured output
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                # Basic check for flowchart structure
                content = response.message.content.strip()
                if '->' in content or 'Start' in content or 'End' in content:
                     return content
                else:
                     print("Warning [flowchart_text]: Ollama response may not be in expected flowchart format.", file=sys.stderr)
                     return content # Return anyway
            else:
                return f"Error [flowchart_text]: Unexpected Ollama response structure. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [flowchart_text]: Gemini library not available for secondary call."

            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                 return "Error [flowchart_text]: Gemini API key not available for secondary call."

            genai.configure(api_key=api_key_for_gemini)
            gemini_model = genai.GenerativeModel(model_name)
            # Configure for low temperature if desired via generation_config
            response = gemini_model.generate_content(prompt) # Add safety_settings if needed

            explanation_text = ""
            if response and hasattr(response, 'text'):
                explanation_text = response.text
            elif response and hasattr(response, 'parts') and response.parts:
                 explanation_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))

            if explanation_text and explanation_text.strip():
                 # Basic check for flowchart structure
                 content = explanation_text.strip()
                 if '->' in content or 'Start' in content or 'End' in content:
                      return content
                 else:
                      print("Warning [flowchart_text]: Gemini response may not be in expected flowchart format.", file=sys.stderr)
                      return content # Return anyway
            else:
                 feedback_info = ""
                 try: # Get feedback details if available
                     if hasattr(response, 'prompt_feedback'): feedback_info += f" Prompt Feedback: {response.prompt_feedback}"
                     if hasattr(response, 'candidates') and response.candidates:
                          feedback_info += f" Finish Reason: {response.candidates[0].finish_reason}"
                          feedback_info += f" Safety Ratings: {response.candidates[0].safety_ratings}"
                 except Exception: pass
                 return f"Error [flowchart_text]: Could not extract flowchart text from Gemini.{feedback_info} Raw Response Excerpt: {str(response)[:200]}..."
        else:
            return f"Error [flowchart_text]: Unknown provider '{provider}' for secondary call."

    except Exception as e:
        return f"Error [flowchart_text]: Exception during LLM call ({provider}, model: {model_name}) for flowchart: {type(e).__name__}: {e}"

