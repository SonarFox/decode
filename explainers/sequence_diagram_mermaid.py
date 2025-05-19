# explainers/sequence_diagram_mermaid_image.py
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
# REQUIRES_GRAPHVIZ = False # Explicitly not needed
# We can add a new flag if the main script needs to check for mmdc specifically,
# or just let it try and fail with a helpful message.
# For now, the error handling within this module will guide the user.

OUTPUT_FILENAME = "sequence_diagram_mermaid_output" # Base name for the output image
OUTPUT_FORMAT = "png" # Desired image format (mmdc supports png, svg, pdf)

def is_mmdc_available():
    """Checks if the Mermaid CLI (mmdc) is available in the system PATH."""
    return shutil.which("mmdc") is not None

def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    """
    Asks the LLM to generate a Sequence Diagram in Mermaid syntax,
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
    print("Explainer [sequence_diagram_mermaid_image]: Requesting Mermaid syntax for Sequence Diagram from LLM...")

    prompt = f"""
Based on the following detailed code analysis AND the original source code, generate a **Sequence Diagram** in **Mermaid syntax**.

Your goal is to illustrate a typical or primary interaction flow between key components (e.g., classes, objects, modules, functions).
1.  Identify the main participants involved in a significant interaction.
2.  Describe the sequence of messages or function calls between these participants.
3.  Use activations and deactivations if appropriate to show focus of control.
4.  Consider loops, alt (alternatives), and opt (optional) blocks if they are central to the interaction.

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

--- Original Source Code Start ---
{original_code}
--- Original Source Code End ---

Provide *ONLY* the Mermaid sequence diagram syntax code block itself, starting with `sequenceDiagram`.
Do not include any other explanatory text or markdown fences like \`\`\`mermaid.

**Mermaid Sequence Diagram Syntax Guidelines:**
* Start with `sequenceDiagram`.
* Define participants: `participant Alice` or `actor Bob`.
* Messages:
    * Synchronous: `Alice->>John: Hello John, how are you?`
    * Asynchronous: `Alice->John: Message text` (Mermaid uses -> for async)
    * Reply: `John-->>Alice: Great!` (dashed line for reply)
* Activations: `activate John`, `deactivate John`
* Notes: `Note right of John: John is thinking.`
* Loops: `loop Every Minute` ... `end`
* Alternatives: `alt isSuccessful` ... `else isFailure` ... `end`
* Optional: `opt text` ... `end`

**Example Mermaid Output (just the syntax, no fences):**
sequenceDiagram
    participant User
    participant WebServer
    participant AppServer
    participant Database

    User->>WebServer: GET /data
    activate WebServer
    WebServer->>AppServer: process_request()
    activate AppServer
    AppServer->>Database: query("SELECT * FROM records")
    activate Database
    Database-->>AppServer: records
    deactivate Database
    AppServer-->>WebServer: formatted_data
    deactivate AppServer
    WebServer-->>User: HTML Page with data
    deactivate WebServer

Mermaid Syntax Output (ONLY the syntax):
"""

    mermaid_syntax_from_llm = ""
    try:
        # --- Step 1: Get Mermaid syntax from LLM ---
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                 return "Error [sequence_diagram_mermaid_image]: Invalid or missing Ollama client."
            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.1}
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                mermaid_syntax_from_llm = response.message.content
            else:
                return f"Error [sequence_diagram_mermaid_image]: Unexpected Ollama response. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [sequence_diagram_mermaid_image]: Gemini library not available."
            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                 return "Error [sequence_diagram_mermaid_image]: Gemini API key not available."

            genai.configure(api_key=api_key_for_gemini)
            gemini_model = genai.GenerativeModel(model_name)
            response = gemini_model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))

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
                          feedback_info += f" Finish Reason: {response.candidates[0].finish_reason}"
                 except Exception: pass
                 return f"Error [sequence_diagram_mermaid_image]: Could not extract Mermaid syntax from Gemini.{feedback_info}"
        else:
            return f"Error [sequence_diagram_mermaid_image]: Unknown provider '{provider}'."

        # --- Cleanup Mermaid syntax ---
        # Remove potential markdown fences and surrounding text
        match = re.search(r"```(?:mermaid)?\s*(sequenceDiagram[\s\S]*?)\s*```", mermaid_syntax_from_llm, re.IGNORECASE)
        cleaned_syntax = ""
        if match:
            cleaned_syntax = match.group(1).strip()
        else:
            # If no markdown fences, check if the response starts directly with sequenceDiagram
            # and try to remove preamble/postamble
            temp_syntax = mermaid_syntax_from_llm.strip()
            if temp_syntax.lower().startswith("sequencediagram"):
                cleaned_syntax = temp_syntax
            else: # Try to find the start of sequenceDiagram
                lines = mermaid_syntax_from_llm.splitlines()
                for i, line in enumerate(lines):
                    if line.strip().lower().startswith("sequencediagram"):
                        cleaned_syntax = "\n".join(lines[i:]).strip()
                        break
                if not cleaned_syntax:
                    print(f"Warning [sequence_diagram_mermaid_image]: LLM output doesn't appear to contain Mermaid sequence diagram syntax:\n---\n{mermaid_syntax_from_llm}\n---", file=sys.stderr)
                    return f"Error [sequence_diagram_mermaid_image]: LLM did not return valid Mermaid syntax. Output started with: '{mermaid_syntax_from_llm[:100]}...'"

        if not cleaned_syntax.lower().startswith('sequencediagram'):
            print(f"Warning [sequence_diagram_mermaid_image]: LLM output after cleanup doesn't look like Mermaid syntax:\n---\n{cleaned_syntax}\n---", file=sys.stderr)
            print(f"Original LLM output was:\n---\n{mermaid_syntax_from_llm}\n---", file=sys.stderr)
            return f"Error [sequence_diagram_mermaid_image]: LLM did not return valid Mermaid syntax for Sequence Diagram. Cleaned output started with: '{cleaned_syntax[:100]}...'"

        # --- Step 2: Render Mermaid syntax to an image file ---
        if not is_mmdc_available():
            error_msg = "Error [sequence_diagram_mermaid_image]: Mermaid CLI (mmdc) not found in PATH. Cannot generate image.\n"
            error_msg += "Please install Node.js and then '@mermaid-js/mermaid-cli' (e.g., 'npm install -g @mermaid-js/mermaid-cli').\n"
            error_msg += "Returning Mermaid syntax instead:\n\n```mermaid\n" + cleaned_syntax + "\n```"
            print(error_msg, file=sys.stderr)
            return error_msg

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(cleaned_syntax)
                tmp_file_path = tmp_file.name

            output_file_path = f"{OUTPUT_FILENAME}.{OUTPUT_FORMAT}"
            cmd = [
                "mmdc",
                "-i", tmp_file_path,
                "-o", output_file_path,
                "-b", "white", # Set background color for better contrast, e.g., white
                # "-t", "neutral" # Optional: specify a theme
            ]

            print(f"Explainer [sequence_diagram_mermaid_image]: Rendering Mermaid diagram to {output_file_path} using command: {' '.join(cmd)}")
            process = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8')

            os.unlink(tmp_file_path) # Clean up temporary file

            if process.returncode == 0:
                abs_output_path = os.path.abspath(output_file_path)
                print(f"Explainer [sequence_diagram_mermaid_image]: Successfully rendered sequence diagram.")
                return f"Success: Mermaid sequence diagram image saved to: {abs_output_path}"
            else:
                error_message = f"Error [sequence_diagram_mermaid_image]: Failed to render Mermaid diagram with mmdc.\n"
                error_message += f"Return Code: {process.returncode}\n"
                if process.stdout: error_message += f"Stdout: {process.stdout.strip()}\n"
                if process.stderr: error_message += f"Stderr: {process.stderr.strip()}\n"
                error_message += "Please ensure Node.js and @mermaid-js/mermaid-cli are correctly installed and mmdc is in your PATH.\n"
                error_message += "Returning Mermaid syntax instead:\n\n```mermaid\n" + cleaned_syntax + "\n```"
                print(error_message, file=sys.stderr)
                return error_message

        except Exception as e:
            error_message = f"Error [sequence_diagram_mermaid_image]: An unexpected error occurred during Mermaid image rendering: {e}\n"
            error_message += "Returning Mermaid syntax instead:\n\n```mermaid\n" + cleaned_syntax + "\n```"
            print(error_message, file=sys.stderr)
            return error_message


    except Exception as e:
        return f"Error [sequence_diagram_mermaid_image]: Exception during LLM call ({provider}, model: {model_name}) for Mermaid syntax: {type(e).__name__}: {e}"

