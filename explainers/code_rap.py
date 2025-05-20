# explainers/code_rap.py
import os
import ollama
import sys  # For stderr
import re  # For cleanup

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE_FOR_EXPLAINER = True
except ImportError:
    GEMINI_AVAILABLE_FOR_EXPLAINER = False


# This explainer does NOT require Graphviz or Mermaid CLI.
# REQUIRES_GRAPHVIZ = False
# REQUIRES_MMDC = False

def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    """
    Asks the LLM to generate a rap explaining the code's purpose and functionality.

    Args:
        base_explanation (str): The initial detailed explanation text.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        original_code (str): The original source code.
        **kwargs: Accepts other potential arguments. Expected: 'api_key' if provider is 'gemini'.

    Returns:
        str: A string containing the rap lyrics, or an error message.
    """
    print("Explainer [code_rap]: Requesting a code rap from LLM...")

    prompt = f"""
Based on the following detailed code analysis AND the original source code, generate a **rap song** that explains what the code does, its main purpose, and key functionalities.

The rap should be:
- Informative yet entertaining.
- Have a good rhythm and flow (though actual audio isn't generated).
- Mention some key components or actions the code performs.
- Be suitable for a developer audience.

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

--- Original Source Code Start ---
{original_code}
--- Original Source Code End ---

Produce ONLY the rap lyrics. Do not include any other explanatory text, titles like "Rap Lyrics:", or markdown formatting.

Rap Lyrics:
"""

    rap_lyrics_from_llm = ""
    try:
        # --- Step 1: Get rap lyrics from LLM ---
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                return "Error [code_rap]: Invalid or missing Ollama client."
            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.7}  # Higher temperature for creativity
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                rap_lyrics_from_llm = response.message.content
            else:
                return f"Error [code_rap]: Unexpected Ollama response structure. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [code_rap]: Gemini library not available."
            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                return "Error [code_rap]: Gemini API key not available."

            genai.configure(api_key=api_key_for_gemini)
            gemini_model = genai.GenerativeModel(model_name)
            # Higher temperature for creative output
            response = gemini_model.generate_content(prompt,
                                                     generation_config=genai.types.GenerationConfig(temperature=0.7))

            explanation_text = ""
            if response and hasattr(response, 'text'):
                explanation_text = response.text
            elif response and hasattr(response, 'parts') and response.parts:
                explanation_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))

            if explanation_text:
                rap_lyrics_from_llm = explanation_text
            else:
                feedback_info = ""
                try:
                    if hasattr(response,
                               'prompt_feedback'): feedback_info += f" Prompt Feedback: {response.prompt_feedback}"
                    if hasattr(response, 'candidates') and response.candidates:
                        feedback_info += f" Finish Reason: {response.candidates[0].finish_reason}"
                except Exception:
                    pass
                return f"Error [code_rap]: Could not extract rap lyrics from Gemini.{feedback_info}"
        else:
            return f"Error [code_rap]: Unknown provider '{provider}'."

        # --- Cleanup rap lyrics ---
        # Remove potential markdown fences if LLM adds them despite instructions
        cleaned_lyrics = rap_lyrics_from_llm.strip()
        if cleaned_lyrics.startswith("```") and cleaned_lyrics.endswith("```"):
            cleaned_lyrics = re.sub(r"^```[a-zA-Z]*\n", "", cleaned_lyrics)
            cleaned_lyrics = re.sub(r"\n```$", "", cleaned_lyrics)
            cleaned_lyrics = cleaned_lyrics.strip()

        # Remove common preamble if LLM ignores "ONLY lyrics" instruction
        common_preambles = [
            "Rap Lyrics:", "Here's a rap about the code:", "Code Rap:",
            "Alright, check the mic, one two, this is how the code do:"
        ]
        for preamble in common_preambles:
            if cleaned_lyrics.lower().startswith(preamble.lower()):
                cleaned_lyrics = cleaned_lyrics[len(preamble):].lstrip(": \n")
                break  # Remove only the first matching preamble

        if not cleaned_lyrics:
            print(f"Warning [code_rap]: LLM returned empty lyrics after cleanup:\n---\n{rap_lyrics_from_llm}\n---",
                  file=sys.stderr)
            return f"Error [code_rap]: LLM did not return any rap lyrics."

        return f"Code Explainer Rap:\n\n{cleaned_lyrics}"

    except Exception as e:
        return f"Error [code_rap]: Exception during LLM call ({provider}, model: {model_name}) for rap: {type(e).__name__}: {e}"

