import argparse
import os
import sys
# Use the ollama library for interaction
import ollama
# Used only for checking Ollama server reachability initially
import requests
# Import the time module
import time

# --- Configuration ---
# Define supported file extensions for analysis
SUPPORTED_EXTENSIONS = ('.py', '.java')
# Default Ollama server address (change if yours is running elsewhere)
OLLAMA_HOST = "http://localhost:11434"

# --- Helper Functions ---

def check_ollama_server(host=OLLAMA_HOST):
    """Checks if the Ollama server is running and reachable."""
    print(f"Checking for Ollama server at {host}...")
    try:
        # Use a timeout to avoid hanging indefinitely
        response = requests.get(host, timeout=5)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        print(f"Ollama server found and responding.")
        return True
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Ollama server at {host}.", file=sys.stderr)
        print("Please ensure Ollama is installed, running, and accessible.", file=sys.stderr)
        return False
    except requests.exceptions.Timeout:
        print(f"Error: Connection to Ollama server at {host} timed out.", file=sys.stderr)
        print("Please ensure Ollama is running and not blocked by a firewall.", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        # Catch other potential requests issues (e.g., invalid URL, SSL errors)
        print(f"Error: An issue occurred while checking Ollama server: {e}", file=sys.stderr)
        return False

def read_source_code(source_path):
    """Reads content from a single file or all supported files in a directory."""
    all_code = ""
    files_processed = []

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Error: Source path '{source_path}' not found.")

    if os.path.isfile(source_path):
        # Handle single file input
        if source_path.endswith(SUPPORTED_EXTENSIONS):
            try:
                # Read with UTF-8 encoding, common for source code
                with open(source_path, 'r', encoding='utf-8') as f:
                    all_code = f.read()
                files_processed.append(source_path)
                print(f"Read file: {source_path}")
            except Exception as e:
                # Warn if reading fails
                print(f"Warning: Could not read file {source_path}: {e}", file=sys.stderr)
        else:
            # Warn if the file extension isn't supported
            print(f"Warning: File '{source_path}' does not have a supported extension ({SUPPORTED_EXTENSIONS}). Skipping.", file=sys.stderr)

    elif os.path.isdir(source_path):
        # Handle directory input
        print(f"Reading supported files from directory: {source_path}")
        for root, _, files in os.walk(source_path):
            for filename in files:
                if filename.endswith(SUPPORTED_EXTENSIONS):
                    file_path = os.path.join(root, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            print(f"  - Reading: {file_path}")
                            # Add a separator/header for context when reading multiple files
                            relative_path = os.path.relpath(file_path, source_path)
                            all_code += f"\n\n--- Content from: {relative_path} ---\n\n"
                            all_code += f.read()
                        files_processed.append(file_path)
                    except Exception as e:
                        # Warn if reading a specific file fails, but continue with others
                        print(f"Warning: Could not read file {file_path}: {e}", file=sys.stderr)
        if not files_processed:
             # Warn if the directory contained no supported files
             print(f"Warning: No supported files ({SUPPORTED_EXTENSIONS}) found in directory '{source_path}'.", file=sys.stderr)

    else:
        # Handle cases where the path is neither a file nor a directory
        raise ValueError(f"Error: Source path '{source_path}' is neither a file nor a directory.")

    if not all_code.strip():
         # Check if any actual code content was read after processing
         print("Warning: No code content was successfully read.", file=sys.stderr)
         return None # Return None if no code was actually read

    return all_code

def get_format_instruction(format_choice):
    """Generates the instruction text for the LLM based on user choice."""
    # This function defines the specific request format for the LLM
    if format_choice == 1:
        return "Provide a concise, bulleted list describing the main components, purpose, and overall functionality of the code."
    elif format_choice == 2:
        return "Provide a paragraph narrative explaining what the code does, its primary purpose, and how its different parts interact."
    elif format_choice == 3:
        return "Describe the execution flow of the code step-by-step. Detail the logic, loops, conditions, and function/method calls in a way that could be used to construct a flowchart. You can use text like 'Start -> Read input -> Process data (Loop) -> If condition X -> Output A -> Else -> Output B -> End'."
    elif format_choice == 4:
        return "Identify the main classes, interfaces, methods, and their relationships (like inheritance, composition, or dependencies). Describe these components in a structured format suitable for generating a basic UML class diagram (e.g., list classes with their attributes and methods, and mention key interactions)."
    elif format_choice == 5:
        return "Describe the code's structure and behavior using a clear visual metaphor or analogy, explained in text. For example, you could describe it as a factory assembly line processing data, a decision tree navigating choices, etc."
    elif format_choice == 6:
        return "Analyze the functions or methods in the code. For each significant function/method, create a table (using markdown format if possible) listing its name, its primary purpose, its input parameters (with expected types if discernible), and what it returns or its main side effects."
    else:
        return "Describe the code's functionality." # Fallback (should not be reached with argparse)

def analyze_with_ollama(code_content, format_instruction, model_name):
    """Sends the code and format instruction to the local Ollama API."""
    if not code_content:
        # Handle case where read_source_code returned None
        return "No code content provided to analyze."

    # Construct the prompt. The 'code_content' variable (containing the file's code)
    # is dynamically inserted into this f-string.
    prompt = f"""
Analyze the following source code (it could be Python or Java).
Your goal is to understand the code and explain it according to the requested format.

Requested Analysis Format:
{format_instruction}

--- Source Code Start ---
{code_content}
--- Source Code End ---

Provide your analysis below:
"""

    print(f"\n--- Calling Ollama API (Model: {model_name}) ---")
    try:
        # Use ollama.chat for instruction-following tasks.
        # Ensure Ollama server is running.
        response = ollama.chat(
            model=model_name,
            messages=[
                {'role': 'user', 'content': prompt}
            ]
            # stream=False # Default is False, waits for full response
            # Add options here if needed, e.g., options={'temperature': 0.7}
        )
        print("--- Analysis Received ---")

        # --- FINAL CORRECTED RESPONSE PARSING ---
        # Check if the response object exists, has a 'message' attribute,
        # and if that message attribute has a 'content' attribute.
        if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
            # Access attributes directly using dot notation
            return response.message.content
        else:
            # Handle cases where the structure is truly unexpected or lacks content
            print(f"Warning: Unexpected response structure or missing content from Ollama: {response}", file=sys.stderr)
            return "Error: Could not extract content from Ollama response."
        # --- END OF FINAL CORRECTED RESPONSE PARSING ---

    except ollama.ResponseError as e:
        # Catch specific errors from the ollama library, like model not found
        print(f"\nOllama API Response Error: {e.status_code}", file=sys.stderr)
        print(f"Details: {e.error}", file=sys.stderr)
        # Make error check slightly more robust by converting potential error dict to string
        error_str = str(e.error).lower()
        if "model" in error_str and "not found" in error_str:
             print(f"Hint: Ensure the model '{model_name}' is pulled locally using 'ollama pull {model_name}'", file=sys.stderr)
        return f"Error: Ollama API returned an error ({e.status_code})."
    except requests.exceptions.ConnectionError as e:
        # This might be caught if the server stops between the check and the call
         print(f"\nError: Connection to Ollama server failed during API call: {e}", file=sys.stderr)
         print(f"Hint: Make sure the Ollama service/application is running at {OLLAMA_HOST}", file=sys.stderr)
         return "Error: Could not connect to Ollama server during analysis."
    except Exception as e:
        # Catch any other exceptions during the Ollama interaction
        print(f"\nError during Ollama API call: {e}", file=sys.stderr)
        # Consider adding more specific error handling based on ollama library behavior
        # import traceback
        # traceback.print_exc() # Uncomment for full traceback during debugging
        return f"Error: Could not get analysis from Ollama. Details: {e}"

# --- Main Execution Block ---
if __name__ == "__main__":
    # Check if Ollama server is running before trying to parse args and proceed
    if not check_ollama_server():
        sys.exit(1) # Exit if server isn't reachable

    # Set up argument parser for command-line interface
    parser = argparse.ArgumentParser(
        description="Analyze source code (Python/Java) using a local Ollama LLM.",
        formatter_class=argparse.RawTextHelpFormatter # Keep help formatting clean
    )
    parser.add_argument(
        "source_path",
        help="Path to the source code file or directory containing source files."
    )
    parser.add_argument(
        "-f", "--format",
        type=int,
        choices=range(1, 7), # Valid format options are 1 through 6
        default=1,           # Default to bulleted list if not specified
        help="Output format for the analysis:\n"
             "1: Bulleted description (default)\n"
             "2: Paragraph narrative\n"
             "3: Flowchart description (text-based)\n"
             "4: UML components description (text-based)\n"
             "5: Other visual metaphor description (text-based)\n"
             "6: Table of method inputs/outputs (markdown)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="llama3", # Default Ollama model
        help="Name of the Ollama model to use (e.g., 'llama3', 'mistral', 'codellama'). Default: llama3"
    )

    # Parse the arguments provided by the user
    args = parser.parse_args()

    try:
        # Use time module here (requires import time at the top)
        print(f"Script started ({time.strftime('%Y-%m-%d %H:%M:%S')})")
        print(f"Analyzing source: {args.source_path}")
        print(f"Requested format option: {args.format}")
        print(f"Using Ollama model: {args.model}")

        # Step 1: Read the source code from the specified path
        code = read_source_code(args.source_path)

        # Step 2: Proceed only if code was successfully read
        if code:
             # Step 3: Determine the specific instruction for the LLM based on format choice
            instruction = get_format_instruction(args.format)

            # Step 4: Call the LLM with the code and instruction
            # The prompt is constructed dynamically inside this function call
            analysis_result = analyze_with_ollama(code, instruction, args.model)

            # Step 5: Print the final analysis result to the console
            print("\n--- Code Analysis Result ---")
            print(analysis_result) # This should now print the actual content
        else:
            # If read_source_code returned None or empty string after stripping
            print("\nExiting: No valid code found to analyze.", file=sys.stderr)
            sys.exit(1) # Exit with a non-zero code to indicate an issue

    # Catch specific expected errors for cleaner exit messages
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except ValueError as e: # Catches issues like invalid path type
        print(e, file=sys.stderr)
        sys.exit(1)
    # Catch any other unexpected errors during execution
    except Exception as e:
        print(f"\nAn unexpected error occurred during script execution: {e}", file=sys.stderr)
        # For debugging, uncomment the next two lines to see the full traceback
        # import traceback
        # traceback.print_exc()
        sys.exit(1)

    # Use time module here (requires import time at the top)
    print(f"\nScript finished ({time.strftime('%Y-%m-%d %H:%M:%S')}).")
