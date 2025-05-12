# explainers/flowchart_graphical.py
import os
import ollama
import graphviz # Requires graphviz Python library and system installation
import sys      # For stderr
import re       # Import regular expressions for more flexible cleanup

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE_FOR_EXPLAINER = True
except ImportError:
    GEMINI_AVAILABLE_FOR_EXPLAINER = False

# Define the output filename (can be made configurable later)
OUTPUT_FILENAME = "flowchart_output"
OUTPUT_FORMAT = "png" # Or 'svg', 'pdf', etc.

def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    """
    Asks the LLM to generate a flowchart description in DOT language format,
    then uses the graphviz library to render it as an image file.

    Args:
        base_explanation (str): The initial detailed explanation text.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        original_code (str): The original source code (can help LLM with flow).
        **kwargs: Accepts other potential arguments. Expected: 'api_key' if provider is 'gemini'.

    Returns:
        str: A success message with the output file path, or an error message.
    """
    print("Explainer [flowchart_graphical]: Requesting DOT language for flowchart from LLM...")

    # Prompt asking for DOT language output based on the analysis and code
    prompt = f"""
Based on the following detailed code analysis AND the original source code, generate a flowchart description in the **DOT language** suitable for rendering with Graphviz.

Represent the typical execution flow identified in the analysis. Use standard DOT syntax:
* Use `digraph G {{ ... }}`.
* Define nodes with labels (e.g., `node_id [label="Process Action"];`). Use meaningful node IDs (e.g., `start`, `read_input`, `check_valid`, `process_data`, `end`).
* Define edges using `->` (e.g., `start -> read_input;`).
* Use diamond shapes for decisions (`node_id [label="Is Valid?", shape=diamond];`).
* Label edges from decision nodes (e.g., `check_valid -> process_data [label="Yes"]; check_valid -> log_error [label="No"];`).
* Keep labels concise.

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

--- Original Source Code Start ---
{original_code}
--- Original Source Code End ---

Provide *only* the DOT language code block. Do not include explanations, backticks, or the word 'dot'. Start directly with `digraph G {{`.

Example DOT Output:
```dot
digraph G {{
  rankdir=TB; // Top-to-bottom flow
  node [shape=box, style=rounded]; // Default node shape

  start [label="Start", shape=ellipse];
  read_input [label="Read Input File"];
  check_valid [label="Is Data Valid?", shape=diamond];
  process_data [label="Process Valid Data"];
  log_error [label="Log Invalid Data Error"];
  end_process [label="End Process", shape=ellipse];

  start -> read_input;
  read_input -> check_valid;
  check_valid -> process_data [label="Yes"];
  check_valid -> log_error [label="No"];
  process_data -> end_process;
  log_error -> end_process;
}}
```

DOT Language Output:
"""

    dot_source = ""
    try:
        # --- Step 1: Get DOT source from LLM ---
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                 return f"Error [flowchart_graphical]: Invalid or missing Ollama client."
            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.1} # Low temperature for structured output
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                dot_source = response.message.content # Get raw content first
            else:
                return f"Error [flowchart_graphical]: Unexpected Ollama response structure. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [flowchart_graphical]: Gemini library not available."
            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                 return "Error [flowchart_graphical]: Gemini API key not available."

            genai.configure(api_key=api_key_for_gemini)
            gemini_model = genai.GenerativeModel(model_name)
            response = gemini_model.generate_content(prompt) # Add safety_settings if needed

            explanation_text = ""
            if response and hasattr(response, 'text'):
                explanation_text = response.text
            elif response and hasattr(response, 'parts') and response.parts:
                 explanation_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))

            if explanation_text: # Check if we got any text
                dot_source = explanation_text # Get raw content first
            else: # Handle empty/blocked response
                 feedback_info = ""
                 try:
                     if hasattr(response, 'prompt_feedback'): feedback_info += f" Prompt Feedback: {response.prompt_feedback}"
                     if hasattr(response, 'candidates') and response.candidates:
                          feedback_info += f" Finish Reason: {response.candidates[0].finish_reason}"
                 except Exception: pass
                 return f"Error [flowchart_graphical]: Could not extract DOT source from Gemini.{feedback_info}"
        else:
            return f"Error [flowchart_graphical]: Unknown provider '{provider}'."

        # *** MODIFIED CLEANUP SECTION ***
        # Strip leading/trailing whitespace first
        cleaned_source = dot_source.strip()

        # Remove potential markdown fences (```dot or ```)
        if cleaned_source.startswith("```dot"):
            cleaned_source = cleaned_source.removeprefix("```dot").strip()
        elif cleaned_source.startswith("```"):
             cleaned_source = cleaned_source.removeprefix("```").strip()
        if cleaned_source.endswith("```"):
            cleaned_source = cleaned_source.removesuffix("```").strip()

        # Remove known introductory phrases (case-insensitive check)
        intro_phrases = [
            "here is the dot language code block:",
            "dot language output:",
            "dot output:",
        ]
        # Use regex for more robust matching of intro lines possibly followed by newlines
        for phrase in intro_phrases:
             # Match phrase at the beginning, ignore case, allow optional colon and whitespace/newlines after
             pattern = re.compile(r"^\s*" + re.escape(phrase) + r"\s*:?\s*", re.IGNORECASE | re.MULTILINE)
             cleaned_source = pattern.sub("", cleaned_source, count=1) # Replace only the first occurrence


        # Final strip after potential removals
        cleaned_source = cleaned_source.strip()
        # *** END OF MODIFIED CLEANUP SECTION ***


        # Basic validation: Check if the cleaned source looks like DOT
        if not cleaned_source.startswith('digraph'):
            print(f"Warning [flowchart_graphical]: LLM output after cleanup doesn't look like DOT language:\n---\n{cleaned_source}\n---", file=sys.stderr)
            print(f"Original LLM output was:\n---\n{dot_source}\n---", file=sys.stderr) # Show original for comparison
            return f"Error [flowchart_graphical]: LLM did not return valid DOT language after cleanup. Cleaned output started with: '{cleaned_source[:50]}...'"

        # --- Step 2: Render DOT source using Graphviz ---
        print(f"Explainer [flowchart_graphical]: Rendering DOT source to {OUTPUT_FILENAME}.{OUTPUT_FORMAT}...")
        try:
            # Use the cleaned source
            graph = graphviz.Source(cleaned_source, filename=OUTPUT_FILENAME, format=OUTPUT_FORMAT, engine='dot')
            output_path = graph.render(cleanup=True, view=False)

            print(f"Explainer [flowchart_graphical]: Successfully rendered flowchart.")
            return f"Success: Graphical flowchart saved to: {output_path}"

        except graphviz.exceptions.ExecutableNotFound:
            print("Error [flowchart_graphical]: Graphviz executable not found.", file=sys.stderr)
            print("Please ensure Graphviz is installed correctly and its 'bin' directory is in your system's PATH.", file=sys.stderr)
            print("Installation guide: https://graphviz.org/download/", file=sys.stderr)
            return "Error: Graphviz executable not found. Please install Graphviz system-wide."
        except Exception as render_err:
            print(f"Error [flowchart_graphical]: Failed to render DOT source: {render_err}", file=sys.stderr)
            # Print the cleaned source that caused the error
            print(f"--- Cleaned DOT Source Attempted ---\n{cleaned_source}\n--------------------------", file=sys.stderr)
            return f"Error: Failed to render flowchart image. Details: {render_err}"

    except Exception as e:
        return f"Error [flowchart_graphical]: Exception during LLM call ({provider}, model: {model_name}) for DOT source: {type(e).__name__}: {e}"

