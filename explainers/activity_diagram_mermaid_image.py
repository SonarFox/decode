# explainers/activity_diagram_mermaid_image.py
import os
import ollama
import sys      # For stderr
import re       # For cleanup
import subprocess # To call Mermaid CLI
import tempfile   # For temporary files
import shutil     # To check if mmdc is in PATH

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE_FOR_EXPLAINER = True
except ImportError:
    GEMINI_AVAILABLE_FOR_EXPLAINER = False

# This explainer does NOT require Graphviz, but DOES require Mermaid CLI (mmdc)
# REQUIRES_MMDC = True # Flag for main script if specific check is implemented

OUTPUT_FILENAME_BASE = "activity_diagram_mermaid_output" # Base name for the output image
OUTPUT_FORMAT = "png" # Desired image format (mmdc supports png, svg, pdf)

def is_mmdc_available():
    """Checks if the Mermaid CLI (mmdc) is available in the system PATH."""
    return shutil.which("mmdc") is not None

def escape_mermaid_label(label_text):
    """Basic escaping for Mermaid labels if they contain problematic characters."""
    # Mermaid labels can be problematic with quotes inside.
    # This is a simple approach; more complex labels might need more sophisticated handling.
    if not isinstance(label_text, str):
        label_text = str(label_text)
    return label_text.replace('"', '#quot;') # Replace quotes to avoid breaking syntax

def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    """
    Asks the LLM to generate a UML Activity Diagram in Mermaid syntax,
    then attempts to render it to an image file using the Mermaid CLI (mmdc).

    Args:
        base_explanation (str): The initial detailed explanation text.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        original_code (str): The original source code.
        **kwargs: Accepts other potential arguments. Expected: 'api_key' if provider is 'gemini'.

    Returns:
        str: A success message with the image file path, the Mermaid syntax if rendering fails
             but syntax was generated, or an error message.
    """
    print("Explainer [activity_diagram_mermaid_image]: Requesting Mermaid syntax for Activity Diagram from LLM...")

    # Corrected f-string curly braces in Mermaid examples within the prompt
    prompt = f"""
Based on the following detailed code analysis AND the original source code, generate a **UML Activity Diagram** in **Mermaid syntax**.

Your goal is to illustrate the flow of activities, decisions, and potentially parallel processes for a significant operation or the main execution path.
Focus on clarity and use standard, common Mermaid activity diagram features.

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

--- Original Source Code Start ---
{original_code}
--- Original Source Code End ---

Provide *ONLY* the Mermaid activity diagram syntax code block itself, starting with `graph TD` or `graph LR`.
Do not include any other explanatory text or markdown fences like \`\`\`mermaid.

**Mermaid Activity Diagram Syntax Guidelines (MUST FOLLOW):**
* **Orientation:** Start with `graph TD` (Top-Down) or `graph LR` (Left-Right).
* **Start Node:** Use `A([Start])` or `idA([Start])` or `[*] --> B` (where B is the first activity ID).
* **End Node:** Use `Z([End])` or `idZ([End])` or `Y --> [*]` (where Y is the last activity ID).
* **Activities (Actions):**
    * Rectangular: `activityId["Description of activity"]` (Use quotes for descriptions with spaces or special characters).
    * Rounded: `activityId("Description of activity")`
* **Decisions (Diamond Shape):**
    * `decisionId{{"Is condition met?"}}`  {escape_mermaid_label("-- Corrected: Content of decision node is a quoted string for f-string compatibility")}
    * `decisionId -- Yes --> pathYesActivityId`
    * `decisionId -- No --> pathNoActivityId`
    * (Ensure conditions in labels are concise: `decisionId{{"Condition: x > 10"}}`)
* **Arrows:** Use `-->` for transitions.
* **Labels on Arrows:** `A -- "Label text" --> B` {escape_mermaid_label("-- Labels on arrows should be quoted if they contain spaces")}
* **Subgraphs (Optional, use sparingly for clarity):**
    `subgraph "Group Title"`
    `  Activity1`
    `  Activity2`
    `end`
* **Avoid overly complex or rarely used Mermaid features unless absolutely necessary.** Stick to the elements above for better compatibility and LLM generation accuracy.
* **Quoting:** If text for node descriptions or edge labels contains spaces, parentheses, or special characters, enclose it in double quotes (e.g., `A["This is an activity"]`).

**Example Mermaid Output (just the syntax, no fences):**
graph TD
    A([Start]) --> B{{"User Authentication?"}}; {escape_mermaid_label("-- Corrected: Decision node content quoted")}
    B -- Authenticated --> C[Process User Request];
    B -- Failed --> D[Display Authentication Error];
    C --> E[Generate Response Data];
    subgraph "Data Formatting"
        E --> F["Format Output for Display"];
    end
    F --> G([End]);
    D --> G;

Mermaid Syntax Output (ONLY the syntax):
"""

    mermaid_syntax_from_llm = ""
    try:
        # --- Step 1: Get Mermaid syntax from LLM ---
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                 return "Error [activity_diagram_mermaid_image]: Invalid or missing Ollama client."
            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.05, 'num_ctx': 8192} # Low temp, increased context
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                mermaid_syntax_from_llm = response.message.content
            else:
                return f"Error [activity_diagram_mermaid_image]: Unexpected Ollama response. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [activity_diagram_mermaid_image]: Gemini library not available."
            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                 return "Error [activity_diagram_mermaid_image]: Gemini API key not available."

            genai.configure(api_key=api_key_for_gemini)
            gemini_model = genai.GenerativeModel(model_name)
            response = gemini_model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.05)) # type: ignore

            explanation_text = ""
            if response and hasattr(response, 'text'):
                explanation_text = response.text
            elif response and hasattr(response, 'parts') and response.parts:
                 explanation_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))

            if explanation_text:
                mermaid_syntax_from_llm = explanation_text
            else:
                 feedback_info = ""
                 try:
                     if hasattr(response, 'prompt_feedback'): feedback_info += f" Prompt Feedback: {response.prompt_feedback}"
                     if hasattr(response, 'candidates') and response.candidates:
                          feedback_info += f" Finish Reason: {response.candidates[0].finish_reason}" # type: ignore
                 except Exception: pass
                 return f"Error [activity_diagram_mermaid_image]: Could not extract Mermaid syntax from Gemini.{feedback_info}"
        else:
            return f"Error [activity_diagram_mermaid_image]: Unknown provider '{provider}'."

        # --- Cleanup Mermaid syntax ---
        match = re.search(r"```(?:mermaid)?\s*((?:graph\s+(?:TD|LR)|activityDiagram)[\s\S]*?)\s*```", mermaid_syntax_from_llm, re.IGNORECASE)
        cleaned_syntax = ""
        if match:
            cleaned_syntax = match.group(1).strip()
        else:
            temp_syntax = mermaid_syntax_from_llm.strip()
            if temp_syntax.lower().startswith("graph td") or \
               temp_syntax.lower().startswith("graph lr") or \
               temp_syntax.lower().startswith("activitydiagram"):
                cleaned_syntax = temp_syntax
            else:
                lines = mermaid_syntax_from_llm.splitlines()
                for i, line in enumerate(lines):
                    stripped_line_lower = line.strip().lower()
                    if stripped_line_lower.startswith("graph td") or \
                       stripped_line_lower.startswith("graph lr") or \
                       stripped_line_lower.startswith("activitydiagram"):
                        cleaned_syntax = "\n".join(lines[i:]).strip()
                        break
                if not cleaned_syntax:
                    print(f"Warning [activity_diagram_mermaid_image]: LLM output doesn't appear to contain Mermaid activity diagram syntax:\n---\n{mermaid_syntax_from_llm}\n---", file=sys.stderr)
                    return f"Error [activity_diagram_mermaid_image]: LLM did not return valid Mermaid syntax. Output started with: '{mermaid_syntax_from_llm[:100]}...'"


        if not (cleaned_syntax.lower().startswith('graph td') or \
                cleaned_syntax.lower().startswith('graph lr') or \
                cleaned_syntax.lower().startswith('activitydiagram')):
            print(f"Warning [activity_diagram_mermaid_image]: LLM output after cleanup doesn't look like Mermaid activity diagram syntax:\n---\n{cleaned_syntax}\n---", file=sys.stderr)
            print(f"Original LLM output was:\n---\n{mermaid_syntax_from_llm}\n---", file=sys.stderr)
            return f"Error [activity_diagram_mermaid_image]: LLM did not return valid Mermaid syntax for Activity Diagram. Cleaned output started with: '{cleaned_syntax[:100]}...'"

        # --- Step 2: Render Mermaid syntax to an image file ---
        if not is_mmdc_available():
            error_msg = "Error [activity_diagram_mermaid_image]: Mermaid CLI (mmdc) not found in PATH. Cannot generate image.\n"
            error_msg += "Please install Node.js and then '@mermaid-js/mermaid-cli' (e.g., 'npm install -g @mermaid-js/mermaid-cli').\n"
            error_msg += "Returning Mermaid syntax instead:\n\n```mermaid\n" + cleaned_syntax + "\n```"
            print(error_msg, file=sys.stderr)
            return error_msg

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(cleaned_syntax)
                tmp_file_path = tmp_file.name

            output_file_path = f"{OUTPUT_FILENAME_BASE}.{OUTPUT_FORMAT}"
            cmd = [
                "mmdc",
                "-i", tmp_file_path,
                "-o", output_file_path,
                "-b", "white", # Set background color
            ]

            print(f"Explainer [activity_diagram_mermaid_image]: Rendering Mermaid diagram to {output_file_path} using command: {' '.join(cmd)}")
            process = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8')

            os.unlink(tmp_file_path) # Clean up temporary file

            if process.returncode == 0:
                abs_output_path = os.path.abspath(output_file_path)
                print(f"Explainer [activity_diagram_mermaid_image]: Successfully rendered activity diagram.")
                return f"Success: Mermaid activity diagram image saved to: {abs_output_path}"
            else:
                error_message = f"Error [activity_diagram_mermaid_image]: Failed to render Mermaid diagram with mmdc.\n"
                error_message += f"Return Code: {process.returncode}\n"
                if process.stdout: error_message += f"Stdout: {process.stdout.strip()}\n"
                if process.stderr: error_message += f"Stderr: {process.stderr.strip()}\n"
                error_message += "Please ensure Node.js and @mermaid-js/mermaid-cli are correctly installed and mmdc is in your PATH.\n"
                error_message += "Returning Mermaid syntax instead (this is the syntax that caused the error):\n\n```mermaid\n" + cleaned_syntax + "\n```" # Crucial for debugging
                print(error_message, file=sys.stderr)
                return error_message

        except Exception as e:
            error_message = f"Error [activity_diagram_mermaid_image]: An unexpected error occurred during Mermaid image rendering: {e}\n"
            error_message += "Returning Mermaid syntax instead:\n\n```mermaid\n" + cleaned_syntax + "\n```"
            print(error_message, file=sys.stderr)
            return error_message


    except Exception as e:
        return f"Error [activity_diagram_mermaid_image]: Exception during LLM call ({provider}, model: {model_name}) for Mermaid syntax: {type(e).__name__}: {e}"

