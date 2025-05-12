import argparse
import os
import sys
import importlib # For dynamic module loading
import importlib.util
import ollama
import requests # Used only for checking Ollama server reachability
# Only import genai if needed
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    # Define a placeholder if not available, so checks don't fail
    class GenaiPlaceholder: pass
    genai = GenaiPlaceholder()


# --- Configuration ---
OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"
DEFAULT_EXPLAINER_DIR = "explainers" # Subdirectory for explainer modules

# --- Helper Functions ---

def check_ollama_server(host=OLLAMA_HOST):
    """Checks if the Ollama server is running and reachable."""
    # (Function remains the same as previous version)
    print(f"Checking for Ollama server at {host}...")
    try:
        response = requests.get(host, timeout=5)
        response.raise_for_status()
        print("Ollama server found and responding.")
        return True
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Ollama server at {host}.", file=sys.stderr)
        print("Please ensure Ollama is installed and running.", file=sys.stderr)
        return False
    except requests.exceptions.Timeout:
        print(f"Error: Connection to Ollama server at {host} timed out.", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error: An issue occurred while checking Ollama server: {e}", file=sys.stderr)
        return False

def read_source_file(file_path):
    """Reads the content of the specified source code file."""
    # (Function remains the same as previous version)
    print(f"Reading source code from: {file_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: File not found at '{file_path}'")
    if not os.path.isfile(file_path):
         raise ValueError(f"Error: Path '{file_path}' is not a file.")

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if not content.strip():
             print(f"Warning: File '{file_path}' is empty or contains only whitespace.", file=sys.stderr)
             return None
        print(f"Successfully read {len(content)} characters.")
        return content
    except Exception as e:
        raise IOError(f"Error reading file '{file_path}': {e}")

def select_explanation_format(available_explainers):
    """Prompts the user to select the desired explanation format from discovered explainers."""
    # (Function remains the same as previous version)
    print("\nSelect how you want the code to be explained:")
    explainer_map = {}
    default_choice_num = None
    default_explainer_name = 'simple_summary'
    sorted_explainer_names = sorted(available_explainers.keys())
    if default_explainer_name in sorted_explainer_names:
        sorted_explainer_names.remove(default_explainer_name)
        sorted_explainer_names.insert(0, default_explainer_name)

    for i, name in enumerate(sorted_explainer_names, 1):
        display_name = name.replace('_', ' ').title()
        default_text = ""
        if name == default_explainer_name:
            default_text = " (Default)"
            default_choice_num = i
        print(f"  {i}: {display_name}{default_text}")
        explainer_map[i] = name

    if not explainer_map:
        print("Error: No explanation formats found!", file=sys.stderr)
        sys.exit(1)

    while True:
        try:
            default_prompt = f" [default: {default_choice_num} ({default_explainer_name})]" if default_choice_num else ""
            choice_str = input(f"Enter your choice (1-{len(explainer_map)}){default_prompt}: ")

            if not choice_str and default_choice_num is not None:
                return explainer_map[default_choice_num]

            choice_num = int(choice_str)
            if choice_num in explainer_map:
                return explainer_map[choice_num]
            else:
                print(f"Invalid choice. Please enter a number between 1 and {len(explainer_map)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except EOFError:
             print("\nOperation cancelled by user.", file=sys.stderr)
             sys.exit(1)

def discover_explainers(explainer_dir):
    """Discovers available explainer modules in the specified directory."""
    # (Function remains the same as previous version)
    explainers = {}
    if not os.path.isdir(explainer_dir):
        print(f"Warning: Explainer directory '{explainer_dir}' not found.", file=sys.stderr)
        return explainers

    explainer_package_name = os.path.basename(explainer_dir)
    parent_dir = os.path.dirname(os.path.abspath(explainer_dir))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    print(f"Discovering explainers in '{explainer_dir}'...")
    try:
        for filename in os.listdir(explainer_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                full_module_path = os.path.join(explainer_dir, filename)
                import_path = f"{explainer_package_name}.{module_name}"

                try:
                    spec = importlib.util.spec_from_file_location(import_path, full_module_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        if hasattr(module, 'explain'):
                            explainers[module_name] = import_path
                            print(f"  - Found valid explainer: '{module_name}'")
                        else:
                            print(f"Warning: Module '{import_path}' missing 'explain' function. Skipping.", file=sys.stderr)
                    else:
                         print(f"Warning: Could not create spec for module '{import_path}'. Skipping.", file=sys.stderr)
                except Exception as e:
                     print(f"Warning: Error importing or validating explainer '{import_path}': {e}", file=sys.stderr)
    except Exception as e:
        print(f"Error accessing explainer directory '{explainer_dir}': {e}", file=sys.stderr)

    if not explainers:
        print(f"Warning: No valid explainers with an 'explain' function found in '{explainer_dir}'.", file=sys.stderr)

    return explainers

def run_explainer(explainer_name, import_path, base_explanation, **kwargs):
    """Loads and runs the specified explainer module's 'explain' function."""
    # (Function remains the same as previous version)
    try:
        print(f"\n--- Applying Explainer: {explainer_name} ---")
        explainer_module = importlib.import_module(import_path)

        if hasattr(explainer_module, 'explain'):
            formatted_result = explainer_module.explain(base_explanation=base_explanation, **kwargs)
            print(f"--- Explainer '{explainer_name}' Applied Successfully ---")
            if not isinstance(formatted_result, str):
                 print(f"Warning: Explainer '{explainer_name}' did not return a string.", file=sys.stderr)
                 return f"Error: Explainer '{explainer_name}' returned unexpected type."
            return formatted_result
        else:
            print(f"Error: Explainer module '{import_path}' is missing the 'explain' function.", file=sys.stderr)
            return f"Error: Could not run explainer '{explainer_name}'. Function not found."

    except ModuleNotFoundError:
         print(f"Error: Could not import explainer module '{import_path}'.", file=sys.stderr)
         return f"Error: Explainer '{explainer_name}' module not found."
    except Exception as e:
        print(f"Error running explainer '{explainer_name}': {type(e).__name__}: {e}", file=sys.stderr)
        return f"Error: An exception occurred while running explainer '{explainer_name}'."


# --- LLM Interaction Functions (Requesting Base Explanation) ---

def get_base_explanation_with_ollama(code_content, model_name, ollama_host):
    """Sends code to Ollama and asks for a general, detailed base explanation."""
    if not code_content:
        return "Error: No code content provided to explain."

    prompt = f"""
Please analyze the following source code in detail. Provide a comprehensive explanation covering:
1. The overall purpose and main functionality.
2. Key components (functions, classes, modules).
3. How the components interact or the general execution flow.
4. Any notable inputs or outputs.

--- Source Code Start ---
{code_content}
--- Source Code End ---

Detailed Explanation:
"""

    print(f"\n--- Requesting Base Explanation from Ollama (Model: {model_name}) ---")
    try:
        client = ollama.Client(host=ollama_host)
        response = client.chat(
            model=model_name,
            messages=[{'role': 'user', 'content': prompt}]
        )
        print("--- Base Explanation Received from Ollama ---")

        # *** FIXED SECTION FOR OLLAMA RESPONSE OBJECT ***
        # Check if the response object exists and has the expected attributes
        if response and hasattr(response, 'message') and \
           hasattr(response.message, 'content'):
            content = response.message.content
            if not content or not content.strip():
                 print("Warning: Ollama returned an empty base explanation.", file=sys.stderr)
                 print(f"Raw response object was: {response}", file=sys.stderr) # Print object representation
                 return "Error: Received empty explanation from Ollama."
            return content # Success! Return the content string
        else:
            # If structure is unexpected, print the raw response object and return an error
            print(f"Error: Unexpected response structure received from Ollama.", file=sys.stderr)
            print(f"Raw response object received: {response}", file=sys.stderr) # Print object representation
            return f"Error: Could not extract base explanation from Ollama response object. Raw response: {response}"
        # *** END OF FIXED SECTION ***

    except ollama.ResponseError as e:
        print(f"\nOllama API Error: {e.status_code}", file=sys.stderr)
        error_detail = getattr(e, 'error', 'No specific error detail provided')
        print(f"Details: {error_detail}", file=sys.stderr)
        if "model" in str(error_detail).lower() and "not found" in str(error_detail).lower():
             print(f"Hint: Ensure the model '{model_name}' is pulled locally ('ollama pull {model_name}')", file=sys.stderr)
        return f"Error: Ollama API returned an error ({e.status_code}). Details: {error_detail}"
    except requests.exceptions.ConnectionError as e:
         print(f"\nError: Connection to Ollama server failed during API call: {e}", file=sys.stderr)
         return "Error: Could not connect to Ollama server for analysis."
    except Exception as e:
        print(f"\nError during Ollama interaction: {type(e).__name__}: {e}", file=sys.stderr)
        return f"Error: An unexpected issue occurred while communicating with Ollama: {e}"

def get_base_explanation_with_gemini(code_content, model_name, api_key):
    """Sends code to Gemini API and asks for a general, detailed base explanation."""
    # (Function remains the same as previous version - check availability)
    if not GEMINI_AVAILABLE:
        return "Error: Gemini library ('google-generativeai') not installed. Cannot use Gemini provider."
    if not code_content:
        return "Error: No code content provided to explain."
    if not api_key:
        return f"Error: Gemini API key not found. Please set the {GEMINI_API_KEY_ENV_VAR} environment variable or use the --api-key argument."

    prompt = f"""
Please analyze the following source code in detail. Provide a comprehensive explanation covering:
1. The overall purpose and main functionality.
2. Key components (functions, classes, modules).
3. How the components interact or the general execution flow.
4. Any notable inputs or outputs.

--- Source Code Start ---
{code_content}
--- Source Code End ---

Detailed Explanation:
"""

    print(f"\n--- Requesting Base Explanation from Gemini (Model: {model_name}) ---")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        print("--- Base Explanation Received from Gemini ---")

        explanation_text = ""
        # Prioritize accessing response.text if available
        if response and hasattr(response, 'text'):
            explanation_text = response.text
        # Fallback for potential multi-part responses
        elif response and hasattr(response, 'parts') and response.parts:
             explanation_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))

        if explanation_text and explanation_text.strip():
             return explanation_text
        else:
             # Handle empty or blocked responses
             print(f"Warning: Gemini returned an empty or potentially blocked response.", file=sys.stderr)
             try: # Attempt to print safety feedback
                 print(f"Gemini prompt feedback: {response.prompt_feedback}", file=sys.stderr)
                 if hasattr(response, 'candidates') and response.candidates:
                      print(f"Gemini candidate finish reason: {response.candidates[0].finish_reason}", file=sys.stderr)
                      print(f"Gemini candidate safety ratings: {response.candidates[0].safety_ratings}", file=sys.stderr)
             except Exception as feedback_err:
                 print(f"(Could not retrieve detailed feedback: {feedback_err})", file=sys.stderr)
             return f"Error: Could not extract valid base explanation from Gemini response (check for safety blocks or empty content). Raw response excerpt: {str(response)[:200]}..." # Show limited raw response

    except Exception as e:
        print(f"\nError during Gemini interaction: {type(e).__name__}: {e}", file=sys.stderr)
        return f"Error: An unexpected issue occurred while communicating with Gemini: {e}"

# --- Main Execution ---
if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Explain a source code file using a selected LLM and explanation format."
    )
    parser.add_argument(
        "file_path",
        help="Path to the source code file to explain."
    )
    # Add provider choices dynamically based on availability
    provider_choices = ['ollama']
    if GEMINI_AVAILABLE:
        provider_choices.append('gemini')
    parser.add_argument(
        "--provider",
        type=str,
        choices=provider_choices,
        default='ollama',
        help=f"The LLM provider to use ({', '.join(provider_choices)}). Default: ollama"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=None,
        help=f"Name of the LLM model to use. Default for Ollama: '{DEFAULT_OLLAMA_MODEL}', Default for Gemini: '{DEFAULT_GEMINI_MODEL}'."
    )
    parser.add_argument(
        "--host",
        type=str,
        default=OLLAMA_HOST,
        help=f"URL of the Ollama server (used only if provider is 'ollama'). Default: {OLLAMA_HOST}"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help=f"API key for Gemini (used only if provider is 'gemini'). Can also be set via the {GEMINI_API_KEY_ENV_VAR} environment variable."
    )
    parser.add_argument(
        "--explainer-dir",
        type=str,
        default=DEFAULT_EXPLAINER_DIR,
        help=f"Directory containing explainer Python modules. Default: '{DEFAULT_EXPLAINER_DIR}'"
    )

    args = parser.parse_args()

    # Validate Gemini usage if selected but library not installed
    if args.provider == 'gemini' and not GEMINI_AVAILABLE:
         print("Error: Gemini provider selected, but 'google-generativeai' library is not installed.", file=sys.stderr)
         print("Please install it using: pip install google-generativeai", file=sys.stderr)
         sys.exit(1)

    # Determine model if not specified
    if args.model is None:
        args.model = DEFAULT_OLLAMA_MODEL if args.provider == 'ollama' else DEFAULT_GEMINI_MODEL

    gemini_api_key = args.api_key or os.getenv(GEMINI_API_KEY_ENV_VAR)

    # --- Workflow ---
    final_explanation = ""
    try:
        # Step 1: Discover available explanation formats
        script_dir = os.path.dirname(os.path.abspath(__file__))
        explainer_path = os.path.join(script_dir, args.explainer_dir)
        available_explainers = discover_explainers(explainer_path)

        if not available_explainers:
            print(f"Error: No valid explainers found in '{explainer_path}'. Exiting.", file=sys.stderr)
            sys.exit(1)

        # Step 2: Read the source code file
        source_code = read_source_file(args.file_path)
        if not source_code:
            print("\nExiting: No code content read from the file.", file=sys.stderr)
            sys.exit(1)

        # Step 3: Get the base explanation from the selected LLM provider
        base_explanation = ""
        llm_client = None # Placeholder for potential future use in explainers
        if args.provider == 'ollama':
            if not check_ollama_server(args.host):
                sys.exit(1)
            base_explanation = get_base_explanation_with_ollama(source_code, args.model, args.host)
            try: # Store client if needed later
                 llm_client = ollama.Client(host=args.host)
            except Exception as client_err:
                 print(f"Warning: Could not re-initialize Ollama client for explainer context: {client_err}", file=sys.stderr)
                 llm_client = None
        elif args.provider == 'gemini':
            base_explanation = get_base_explanation_with_gemini(source_code, args.model, gemini_api_key)
            # No separate client object needed for current gemini usage pattern

        # Check if base explanation failed
        if base_explanation.startswith("Error:"):
            print(f"\nFailed to get base explanation from {args.provider.upper()}.", file=sys.stderr)
            print(f"Reason: {base_explanation}", file=sys.stderr) # Print the detailed error
            sys.exit(1)

        # Step 4: Get user's choice for explanation format
        selected_explainer_name = select_explanation_format(available_explainers)
        print(f"Selected explainer: '{selected_explainer_name}'")

        # Step 5: Run the selected explainer
        explainer_import_path = available_explainers.get(selected_explainer_name)
        if explainer_import_path:
            explainer_kwargs = {
                "llm_client": llm_client,
                "model_name": args.model,
                "original_code": source_code,
                "provider": args.provider # Pass provider name too
            }
            final_explanation = run_explainer(
                selected_explainer_name,
                explainer_import_path,
                base_explanation,
                **explainer_kwargs
            )
        else:
            print(f"Internal Error: Selected explainer '{selected_explainer_name}' not found in discovered list.", file=sys.stderr)
            final_explanation = f"Error: Could not run selected explainer.\n\n--- Base Explanation ---\n{base_explanation}"


        # Step 6: Print the final explanation from the explainer
        print("\n--- Final Code Explanation ---")
        # Check if the explainer itself returned an error
        if final_explanation.startswith("Error:"):
             print(final_explanation, file=sys.stderr)
             # Optionally decide whether to exit with error if explainer fails
             # sys.exit(1)
        else:
             print(final_explanation)


    except (FileNotFoundError, ValueError, IOError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback # Uncomment for debugging
        traceback.print_exc() # Uncomment for debugging
        sys.exit(1)

    print("\nScript finished.")
