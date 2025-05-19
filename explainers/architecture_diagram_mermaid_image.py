# explainers/architecture_diagram_mermaid_image.py
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

OUTPUT_FILENAME_BASE = "architecture_diagram_mermaid_output" # Base name for the output image
OUTPUT_FORMAT = "png" # Desired image format (mmdc supports png, svg, pdf)

def is_mmdc_available():
    """Checks if the Mermaid CLI (mmdc) is available in the system PATH."""
    return shutil.which("mmdc") is not None

def escape_mermaid_label(label_text):
    """Basic escaping for Mermaid labels if they contain problematic characters."""
    if not isinstance(label_text, str):
        label_text = str(label_text)
    # Replace quotes to avoid breaking syntax if label is not already quoted by LLM
    # More robust would be to ensure LLM always quotes labels with special chars.
    return label_text.replace('"', '#quot;')

def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    """
    Asks the LLM to generate an Architecture Diagram in Mermaid syntax (using generic graph),
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
    print("Explainer [architecture_diagram_mermaid_image]: Requesting Mermaid syntax for Architecture Diagram from LLM...")

    prompt = f"""
Based on the following detailed code analysis AND the original source code, generate an **Architecture Diagram** in **Mermaid syntax** using a generic graph (`graph TD` or `graph LR`).

Your goal is to illustrate the high-level architecture, showing key components and their relationships.
1.  Identify major architectural components (e.g., services, modules, layers, databases, external APIs, UI components).
2.  Represent these components as nodes. Use clear, concise labels. Quote labels if they contain spaces or special characters.
3.  Show the primary relationships or data flows between these components using directed arrows (`-->`). Label arrows if the relationship type is important (e.g., "uses", "sends data to", "calls").
4.  Optionally, use subgraphs to group related components (e.g., `subgraph "Backend Services"` ... `end`).
5.  Keep the diagram high-level and focused on the main architectural structure.

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

--- Original Source Code Start ---
{original_code}
--- Original Source Code End ---

Provide *ONLY* the Mermaid graph syntax code block itself, starting with `graph TD` or `graph LR`.
Do not include any other explanatory text or markdown fences like \`\`\`mermaid.

**Mermaid Graph Syntax Guidelines:**
* **Orientation:** Start with `graph TD` (Top-Down) or `graph LR` (Left-Right).
* **Nodes:**
    * `nodeId["Node Label with Spaces"]` (rectangle, default)
    * `nodeId("Rounded Node Label")`
    * `nodeId{{"Diamond Label (for decisions/gateways)"}}` (Note: double curly for f-string if this was Python)
    * `nodeId[/Parallelogram Label/]`
* **Edges (Arrows):**
    * `A --> B` (A points to B)
    * `A -- "label text" --> B` (A points to B with a label)
    * `A --- B` (Undirected link)
* **Subgraphs:**
    `subgraph "Group Title"`
    `  node1`
    `  node2 --> node3`
    `end`
* **Quoting:** Node labels or edge labels with spaces or special characters MUST be enclosed in double quotes.

**Example Mermaid Output (just the syntax, no fences):**
graph TD
    A["User Interface (Web App)"] --> B["API Gateway"];
    B --> C1["Auth Service"];
    B --> C2["Order Service"];
    B --> C3["Product Service"];
    C2 -- "writes to" --> D["Order Database (PostgreSQL)"];
    C3 -- "reads from" --> E["Product Catalog DB (MongoDB)"];
    C2 -- "sends event" --> F["Notification Service"];
    F --> G["Email Service (External)"];

    subgraph "Core Services"
        C1
        C2
        C3
    end

Mermaid Syntax Output (ONLY the syntax):
"""

    mermaid_syntax_from_llm = ""
    try:
        # --- Step 1: Get Mermaid syntax from LLM ---
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                 return "Error [architecture_diagram_mermaid_image]: Invalid or missing Ollama client."
            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.1} # Low temperature for structured output
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                mermaid_syntax_from_llm = response.message.content
            else:
                return f"Error [architecture_diagram_mermaid_image]: Unexpected Ollama response. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [architecture_diagram_mermaid_image]: Gemini library not available."
            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                 return "Error [architecture_diagram_mermaid_image]: Gemini API key not available."

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
                 return f"Error [architecture_diagram_mermaid_image]: Could not extract Mermaid syntax from Gemini.{feedback_info}"
        else:
            return f"Error [architecture_diagram_mermaid_image]: Unknown provider '{provider}'."

        # --- Cleanup Mermaid syntax ---
        match = re.search(r"```(?:mermaid)?\s*(graph\s+(?:TD|LR)[\s\S]*?)\s*```", mermaid_syntax_from_llm, re.IGNORECASE)
        cleaned_syntax = ""
        if match:
            cleaned_syntax = match.group(1).strip()
        else:
            temp_syntax = mermaid_syntax_from_llm.strip()
            if temp_syntax.lower().startswith("graph td") or \
               temp_syntax.lower().startswith("graph lr"):
                cleaned_syntax = temp_syntax
            else:
                lines = mermaid_syntax_from_llm.splitlines()
                for i, line in enumerate(lines):
                    stripped_line_lower = line.strip().lower()
                    if stripped_line_lower.startswith("graph td") or \
                       stripped_line_lower.startswith("graph lr"):
                        cleaned_syntax = "\n".join(lines[i:]).strip()
                        break
                if not cleaned_syntax:
                    print(f"Warning [architecture_diagram_mermaid_image]: LLM output doesn't appear to contain Mermaid graph syntax:\n---\n{mermaid_syntax_from_llm}\n---", file=sys.stderr)
                    return f"Error [architecture_diagram_mermaid_image]: LLM did not return valid Mermaid syntax. Output started with: '{mermaid_syntax_from_llm[:100]}...'"


        if not (cleaned_syntax.lower().startswith('graph td') or \
                cleaned_syntax.lower().startswith('graph lr')):
            print(f"Warning [architecture_diagram_mermaid_image]: LLM output after cleanup doesn't look like Mermaid graph syntax:\n---\n{cleaned_syntax}\n---", file=sys.stderr)
            print(f"Original LLM output was:\n---\n{mermaid_syntax_from_llm}\n---", file=sys.stderr)
            return f"Error [architecture_diagram_mermaid_image]: LLM did not return valid Mermaid syntax for Architecture Diagram. Cleaned output started with: '{cleaned_syntax[:100]}...'"

        # --- Step 2: Render Mermaid syntax to an image file ---
        if not is_mmdc_available():
            error_msg = "Error [architecture_diagram_mermaid_image]: Mermaid CLI (mmdc) not found in PATH. Cannot generate image.\n"
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

            print(f"Explainer [architecture_diagram_mermaid_image]: Rendering Mermaid diagram to {output_file_path} using command: {' '.join(cmd)}")
            process = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8')

            os.unlink(tmp_file_path) # Clean up temporary file

            if process.returncode == 0:
                abs_output_path = os.path.abspath(output_file_path)
                print(f"Explainer [architecture_diagram_mermaid_image]: Successfully rendered architecture diagram.")
                return f"Success: Mermaid architecture diagram image saved to: {abs_output_path}"
            else:
                error_message = f"Error [architecture_diagram_mermaid_image]: Failed to render Mermaid diagram with mmdc.\n"
                error_message += f"Return Code: {process.returncode}\n"
                if process.stdout: error_message += f"Stdout: {process.stdout.strip()}\n"
                if process.stderr: error_message += f"Stderr: {process.stderr.strip()}\n"
                error_message += "Please ensure Node.js and @mermaid-js/mermaid-cli are correctly installed and mmdc is in your PATH.\n"
                error_message += "Returning Mermaid syntax instead (this is the syntax that caused the error):\n\n```mermaid\n" + cleaned_syntax + "\n```"
                print(error_message, file=sys.stderr)
                return error_message

        except Exception as e:
            error_message = f"Error [architecture_diagram_mermaid_image]: An unexpected error occurred during Mermaid image rendering: {e}\n"
            error_message += "Returning Mermaid syntax instead:\n\n```mermaid\n" + cleaned_syntax + "\n```"
            print(error_message, file=sys.stderr)
            return error_message


    except Exception as e:
        return f"Error [architecture_diagram_mermaid_image]: Exception during LLM call ({provider}, model: {model_name}) for Mermaid syntax: {type(e).__name__}: {e}"

