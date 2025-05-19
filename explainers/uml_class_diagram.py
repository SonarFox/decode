# explainers/uml_class_diagram_mermaid_image.py
# (Formerly uml_class_diagram_mermaid.py - now generates an image)
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
# REQUIRES_MMDC = True # We can add a flag if the main script needs to check

OUTPUT_FILENAME_BASE = "uml_class_diagram_mermaid_output" # Base name for the output image
OUTPUT_FORMAT = "png" # Desired image format (mmdc supports png, svg, pdf)

def is_mmdc_available():
    """Checks if the Mermaid CLI (mmdc) is available in the system PATH."""
    return shutil.which("mmdc") is not None

def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    """
    Asks the LLM to generate a UML Class Diagram in Mermaid syntax,
    then attempts to render it to an image file using the Mermaid CLI (mmdc).

    Args:
        base_explanation (str): The initial detailed explanation text.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        original_code (str): The original source code (essential for class structure).
        **kwargs: Accepts other potential arguments. Expected: 'api_key' if provider is 'gemini'.

    Returns:
        str: A success message with the image file path, the Mermaid syntax if rendering fails
             but syntax was generated, or an error message.
    """
    print("Explainer [uml_class_diagram_mermaid_image]: Requesting Mermaid syntax for UML Class Diagram from LLM...")

    # Corrected prompt: Removed "visibility" keyword from member definitions.
    # Emphasized using only +, -, # for visibility.
    prompt = f"""
Based on the following detailed code analysis AND the original source code, generate a UML Class Diagram description using **Mermaid class diagram syntax**.

Identify key classes, their attributes (fields/variables with types), and methods (functions with parameters and return types). Also, identify relationships like inheritance, aggregation, composition, and association.

**Mermaid Class Diagram Syntax Guidelines:**
* Start with `classDiagram`.
* Define classes like:
  ```mermaid
  class ClassName {{
    +attributeName: attributeType  // Use + for public, - for private, # for protected
    -anotherAttribute: anotherType
    #protectedAttribute: type

    +methodName(paramType paramName, ...): returnType // Use + for public, - for private, # for protected
    -anotherMethod(param: type): void
    #protectedMethod()
  }}
  ```
  (If type has generics like List<String>, use `List~String~` or `List_String_` if `List<String>` causes issues in your Mermaid renderer, otherwise `List<String>` is often fine. For parameters, list type then name, e.g., `int id`.)
* Relationships:
    * Inheritance (ClassA inherits from ClassB): `ClassB <|-- ClassA`
    * Composition (ClassA owns ClassB): `ClassA *-- ClassB : owns`
    * Aggregation (ClassA has ClassB): `ClassA o-- ClassB : has a`
    * Association (ClassA uses ClassB): `ClassA --> ClassB : uses`
    * Dependency (ClassA depends on ClassB): `ClassA ..> ClassB : depends on`
* Keep the diagram focused on the most important classes and relationships.

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

--- Original Source Code Start ---
{original_code}
--- Original Source Code End ---

Provide *ONLY* the Mermaid class diagram syntax code block itself, starting with `classDiagram`.
Do not include any other explanatory text or markdown fences like \`\`\`mermaid.

**Example Mermaid Output (just the syntax, no fences):**
classDiagram
  class Animal {{
    +String name
    +int age
    +getName(): String
    +setAge(int age): void
  }}
  class Dog {{
    +String breed
    +bark(): void
  }}
  class Cat {{
    +String color
    +meow(): void
  }}

  Animal <|-- Dog
  Animal <|-- Cat
  Dog --> Cat : chases

Mermaid Syntax Output (ONLY the syntax):
"""

    mermaid_syntax_from_llm = ""
    try:
        # --- Step 1: Get Mermaid syntax from LLM ---
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                 return "Error [uml_class_diagram_mermaid_image]: Invalid or missing Ollama client."
            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.0} # Very low temperature for structured output
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                mermaid_syntax_from_llm = response.message.content
            else:
                return f"Error [uml_class_diagram_mermaid_image]: Unexpected Ollama response. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [uml_class_diagram_mermaid_image]: Gemini library not available."
            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                 return "Error [uml_class_diagram_mermaid_image]: Gemini API key not available."

            genai.configure(api_key=api_key_for_gemini)
            gemini_model = genai.GenerativeModel(model_name)
            response = gemini_model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.0)) # type: ignore

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
                 return f"Error [uml_class_diagram_mermaid_image]: Could not extract Mermaid syntax from Gemini.{feedback_info}"
        else:
            return f"Error [uml_class_diagram_mermaid_image]: Unknown provider '{provider}'."

        # --- Cleanup Mermaid syntax ---
        match = re.search(r"```(?:mermaid)?\s*(classDiagram[\s\S]*?)\s*```", mermaid_syntax_from_llm, re.IGNORECASE)
        cleaned_syntax = ""
        if match:
            cleaned_syntax = match.group(1).strip()
        else:
            temp_syntax = mermaid_syntax_from_llm.strip()
            if temp_syntax.lower().startswith("classdiagram"):
                cleaned_syntax = temp_syntax
            else:
                lines = mermaid_syntax_from_llm.splitlines()
                for i, line in enumerate(lines):
                    if line.strip().lower().startswith("classdiagram"):
                        cleaned_syntax = "\n".join(lines[i:]).strip()
                        break
                if not cleaned_syntax:
                    print(f"Warning [uml_class_diagram_mermaid_image]: LLM output doesn't appear to contain Mermaid class diagram syntax:\n---\n{mermaid_syntax_from_llm}\n---", file=sys.stderr)
                    return f"Error [uml_class_diagram_mermaid_image]: LLM did not return valid Mermaid syntax. Output started with: '{mermaid_syntax_from_llm[:100]}...'"


        if not cleaned_syntax.lower().startswith('classdiagram'):
            print(f"Warning [uml_class_diagram_mermaid_image]: LLM output after cleanup doesn't look like Mermaid syntax:\n---\n{cleaned_syntax}\n---", file=sys.stderr)
            print(f"Original LLM output was:\n---\n{mermaid_syntax_from_llm}\n---", file=sys.stderr)
            return f"Error [uml_class_diagram_mermaid_image]: LLM did not return valid Mermaid syntax for Class Diagram. Cleaned output started with: '{cleaned_syntax[:100]}...'"

        # --- Step 2: Render Mermaid syntax to an image file ---
        if not is_mmdc_available():
            error_msg = "Error [uml_class_diagram_mermaid_image]: Mermaid CLI (mmdc) not found in PATH. Cannot generate image.\n"
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
                "-b", "white", # Set background color for better contrast
            ]

            print(f"Explainer [uml_class_diagram_mermaid_image]: Rendering Mermaid diagram to {output_file_path} using command: {' '.join(cmd)}")
            process = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8')

            os.unlink(tmp_file_path) # Clean up temporary file

            if process.returncode == 0:
                abs_output_path = os.path.abspath(output_file_path)
                print(f"Explainer [uml_class_diagram_mermaid_image]: Successfully rendered UML Class Diagram.")
                return f"Success: Mermaid UML Class Diagram image saved to: {abs_output_path}"
            else:
                error_message = f"Error [uml_class_diagram_mermaid_image]: Failed to render Mermaid diagram with mmdc.\n"
                error_message += f"Return Code: {process.returncode}\n"
                if process.stdout: error_message += f"Stdout: {process.stdout.strip()}\n"
                if process.stderr: error_message += f"Stderr: {process.stderr.strip()}\n"
                error_message += "Please ensure Node.js and @mermaid-js/mermaid-cli are correctly installed and mmdc is in your PATH.\n"
                error_message += "Returning Mermaid syntax instead:\n\n```mermaid\n" + cleaned_syntax + "\n```"
                print(error_message, file=sys.stderr)
                return error_message

        except Exception as e:
            error_message = f"Error [uml_class_diagram_mermaid_image]: An unexpected error occurred during Mermaid image rendering: {e}\n"
            error_message += "Returning Mermaid syntax instead:\n\n```mermaid\n" + cleaned_syntax + "\n```"
            print(error_message, file=sys.stderr)
            return error_message


    except Exception as e:
        return f"Error [uml_class_diagram_mermaid_image]: Exception during LLM call ({provider}, model: {model_name}) for Mermaid syntax: {type(e).__name__}: {e}"

