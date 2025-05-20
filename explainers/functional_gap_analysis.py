# explainers/functional_gap_analysis.py
import os
import ollama
import sys  # For stderr
import re  # For cleanup

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE_FOR_EXPLAINER = True
except ImportError:
    GEMINI_AVAILABLE_FOR_EXPLAINER = False


# This explainer does not require Graphviz or Mermaid CLI.

def prompt_for_requirements_file():
    """
    Prompts the user for the path to the requirements file and reads its content.
    Returns a tuple (content, file_path) or (None, None) if cancelled or error.
    """
    while True:
        try:
            print("\nThis explainer requires a functional requirements text file.")
            file_path_input = input(
                "Enter the path to the requirements file (or type 'cancel' to skip this explainer): ").strip()

            if file_path_input.lower() == 'cancel':
                print("Functional gap analysis cancelled by user.")
                return None, None

            if not file_path_input:
                print("No path entered. Please provide a valid file path or type 'cancel'.")
                continue

            abs_path = os.path.abspath(file_path_input)

            if not os.path.exists(abs_path):
                print(f"Error: File not found at '{abs_path}'. Please check the path and try again.")
                continue
            if not os.path.isfile(abs_path):
                print(f"Error: Path '{abs_path}' is not a file. Please provide a path to a valid file.")
                continue

            try:
                with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if not content.strip():
                    print(f"Warning: Requirements file '{abs_path}' is empty. Analysis might not be useful.")
                    # Allow proceeding with an empty file, but the LLM prompt will indicate it.
                    return "", abs_path
                print(f"Successfully read requirements file: {abs_path}")
                return content, abs_path
            except Exception as e:
                print(f"Error reading requirements file '{abs_path}': {e}")
                # Allow user to try again or cancel

        except EOFError:  # Handle Ctrl+D
            print("\nInput cancelled by user.")
            return None, None
        except KeyboardInterrupt:  # Handle Ctrl+C
            print("\nOperation interrupted by user.")
            return None, None


def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    """
    Compares the source code against a provided requirements document and
    generates a gap analysis report.

    Args:
        base_explanation (str): The initial detailed explanation text of the code.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        original_code (str): The original source code.
        **kwargs: Accepts other potential arguments.
                  Expected: 'requirements_text' (str/None): Content of the requirements file.
                            'requirements_file_path' (str/None): Path to the requirements file for context.

    Returns:
        str: A string containing the functional gap analysis report, or an error message.
    """
    print("Explainer [functional_gap_analysis]: Requesting functional gap analysis from LLM...")

    # Prompt user for the requirements file path and read it
    requirements_text, requirements_file_path = prompt_for_requirements_file()

    if requirements_text is None:  # User cancelled or critical error during prompt
        return "Error [functional_gap_analysis]: Requirements file input was cancelled or failed."

    # Use the actual file path if available, otherwise indicate it wasn't properly read.
    requirements_file_path_for_prompt = requirements_file_path if requirements_file_path else "N/A (file not provided or unreadable)"

    if requirements_text == "":  # File was empty
        # Proceed, but the LLM will be informed the requirements file was empty.
        # The prompt will still include the file path for context.
        print("Info [functional_gap_analysis]: Proceeding with empty requirements text.")

    prompt = f"""
You are an expert software quality assurance analyst. Your task is to perform a functional gap analysis.
Compare the provided source code and its general explanation against the functional requirements listed below.

**Objective:**
Identify discrepancies between the functional requirements and the provided code. Specifically, report on:
1.  **Missing Requirements:** Requirements listed that do not appear to be implemented or addressed in the code.
2.  **Incorrect or Incomplete Implementations:** Requirements that seem to be addressed by the code, but where the implementation appears to be flawed, incomplete, or deviates from the requirement. For these, try to cite specific parts of the original source code (e.g., function names, class names, or even short snippets if possible and relevant) that relate to the issue.

**Output Format:**
Produce a structured report. Use Markdown for clarity.
For each identified gap, clearly state the requirement in question.

--- Functional Requirements (from file: {requirements_file_path_for_prompt}) ---
{requirements_text}
--- End of Functional Requirements ---

--- General Code Explanation (from base LLM analysis) ---
{base_explanation}
--- End of General Code Explanation ---

--- Original Source Code ---
{original_code}
--- End of Original Source Code ---

**Gap Analysis Report:**

**1. Missing Requirements:**
   (List each missing requirement and briefly explain why it appears to be missing based on the code and its explanation. If none, state "No missing requirements identified.")

**2. Incorrect or Incomplete Implementations:**
   (For each, state the requirement, describe the discrepancy, and cite the relevant code section(s) as specifically as possible. If none, state "No incorrect or incomplete implementations identified based on the provided information.")

Please be thorough and analytical.
"""

    analysis_report_from_llm = ""
    try:
        # --- Step 1: Get gap analysis report from LLM ---
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                return "Error [functional_gap_analysis]: Invalid or missing Ollama client."
            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.2, 'num_ctx': 8192}  # Lower temperature for analytical task
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                analysis_report_from_llm = response.message.content
            else:
                return f"Error [functional_gap_analysis]: Unexpected Ollama response. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [functional_gap_analysis]: Gemini library not available."
            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                return "Error [functional_gap_analysis]: Gemini API key not available."

            genai.configure(api_key=api_key_for_gemini)
            gemini_model = genai.GenerativeModel(model_name)
            response = gemini_model.generate_content(prompt,
                                                     generation_config=genai.types.GenerationConfig(temperature=0.2))

            explanation_text = ""
            if response and hasattr(response, 'text'):
                explanation_text = response.text
            elif response and hasattr(response, 'parts') and response.parts:
                explanation_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))

            if explanation_text:
                analysis_report_from_llm = explanation_text
            else:
                feedback_info = ""
                try:
                    if hasattr(response,
                               'prompt_feedback'): feedback_info += f" Prompt Feedback: {response.prompt_feedback}"
                    if hasattr(response, 'candidates') and response.candidates:
                        feedback_info += f" Finish Reason: {response.candidates[0].finish_reason}"
                except Exception:
                    pass
                return f"Error [functional_gap_analysis]: Could not extract report from Gemini.{feedback_info}"
        else:
            return f"Error [functional_gap_analysis]: Unknown provider '{provider}'."

        # --- Cleanup Report ---
        cleaned_report = analysis_report_from_llm.strip()
        # Remove potential markdown fences if LLM adds them around the whole report
        if cleaned_report.startswith("```markdown"):
            cleaned_report = cleaned_report.removeprefix("```markdown").strip()
        if cleaned_report.startswith("```"):
            cleaned_report = cleaned_report.removeprefix("```").strip()
        if cleaned_report.endswith("```"):
            cleaned_report = cleaned_report.removesuffix("```").strip()

        # Remove common preamble if LLM ignores "ONLY report" instruction
        common_preambles = [
            "Gap Analysis Report:", "Here is the gap analysis report:"
        ]
        for preamble in common_preambles:
            if cleaned_report.lower().startswith(preamble.lower()):
                cleaned_report = cleaned_report[len(preamble):].lstrip(": \n")
                break

        if not cleaned_report:
            print(
                f"Warning [functional_gap_analysis]: LLM returned an empty report after cleanup:\n---\n{analysis_report_from_llm}\n---",
                file=sys.stderr)
            return f"Error [functional_gap_analysis]: LLM did not return any report content."

        return f"Functional Gap Analysis Report (Code vs. Requirements from '{requirements_file_path_for_prompt}'):\n\n{cleaned_report}"

    except Exception as e:
        return f"Error [functional_gap_analysis]: Exception during LLM call ({provider}, model: {model_name}) for gap analysis: {type(e).__name__}: {e}"

