# explainers/dependency_graph.py
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
OUTPUT_FILENAME = "dependency_graph_output"
OUTPUT_FORMAT = "png" # Or 'svg', 'pdf', etc.
# Add a flag to indicate if graphviz is required by this explainer
REQUIRES_GRAPHVIZ = True


def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    """
    Asks the LLM to generate a dependency graph description in DOT language format,
    then uses the graphviz library to render it as an image file.

    Args:
        base_explanation (str): The initial detailed explanation text.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        original_code (str): The original source code (can help LLM with dependencies).
        **kwargs: Accepts other potential arguments. Expected: 'api_key' if provider is 'gemini'.

    Returns:
        str: A success message with the output file path, or an error message.
    """
    print("Explainer [dependency_graph]: Requesting DOT language for dependency graph from LLM...")

    # Prompt asking for DOT language output for a dependency graph
    prompt = f"""
Based on the following detailed code analysis AND the original source code, generate a dependency graph description in the **DOT language** suitable for rendering with Graphviz.

Identify key components (e.g., modules, files, classes, major functions/methods) and the dependencies between them (e.g., imports, calls, usage).
* Nodes should represent the components. Use meaningful and concise labels.
* Directed edges (`A -> B`) should indicate that component A depends on component B (or A uses/calls B).
* Keep the graph focused on significant dependencies to maintain readability.

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

--- Original Source Code Start ---
{original_code}
--- Original Source Code End ---

Provide *only* the DOT language code block itself, starting directly with `digraph Dependencies {{` (or a similar graph name) and ending with `}}`. Do not include any other explanatory text, markdown formatting like backticks, or the word 'dot' outside the code block.

Example DOT Output for a Dependency Graph:
```dot
digraph Dependencies {{
  rankdir=LR; // Left-to-right or TB for Top-to-bottom
  node [shape=box, style="rounded,filled", fillcolor=lightblue];

  // Nodes (Components)
  "MainApp" [label="Main Application"];
  "ModuleA" [label="Data Processing Module"];
  "ModuleB" [label="Utility Functions"];
  "DatabaseConnector" [label="DB Connector"];
  "ExternalAPIClient" [label="API Client"];

  // Edges (Dependencies: A -> B means A depends on B)
  "MainApp" -> "ModuleA";
  "MainApp" -> "ModuleB";
  "ModuleA" -> "DatabaseConnector";
  "ModuleA" -> "ModuleB";
  "ModuleB" -> "ExternalAPIClient"; // Example: Utils call an external API
}}
```

DOT Language Output:
"""

    dot_source_from_llm = ""
    try:
        # --- Step 1: Get DOT source from LLM ---
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                 return f"Error [dependency_graph]: Invalid or missing Ollama client."
            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.1} # Low temperature for structured output
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                dot_source_from_llm = response.message.content
            else:
                return f"Error [dependency_graph]: Unexpected Ollama response structure. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [dependency_graph]: Gemini library not available."
            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                 return "Error [dependency_graph]: Gemini API key not available."

            genai.configure(api_key=api_key_for_gemini)
            gemini_model = genai.GenerativeModel(model_name)
            response = gemini_model.generate_content(prompt)

            explanation_text = ""
            if response and hasattr(response, 'text'):
                explanation_text = response.text
            elif response and hasattr(response, 'parts') and response.parts:
                 explanation_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))

            if explanation_text:
                dot_source_from_llm = explanation_text
            else:
                 feedback_info = ""
                 try:
                     if hasattr(response, 'prompt_feedback'): feedback_info += f" Prompt Feedback: {response.prompt_feedback}"
                     if hasattr(response, 'candidates') and response.candidates:
                          feedback_info += f" Finish Reason: {response.candidates[0].finish_reason}"
                 except Exception: pass
                 return f"Error [dependency_graph]: Could not extract DOT source from Gemini.{feedback_info}"
        else:
            return f"Error [dependency_graph]: Unknown provider '{provider}'."

        # --- Cleanup DOT source ---
        match = re.search(r"```(?:dot)?\s*(.*?)\s*```", dot_source_from_llm, re.DOTALL)
        cleaned_source = ""
        if match:
            cleaned_source = match.group(1).strip()
        else:
            digraph_match = re.search(r"(digraph\s+\w+\s*\{.*?\})", dot_source_from_llm, re.DOTALL | re.IGNORECASE)
            if digraph_match:
                cleaned_source = digraph_match.group(1).strip()
            else:
                temp_cleaned_source = dot_source_from_llm.strip()
                intro_phrases = [
                    "here is the dot language code block for the dependency graph:",
                    "dependency graph dot output:",
                ] # Add more specific intro phrases if observed
                for phrase in intro_phrases:
                    pattern = re.compile(r"^\s*" + re.escape(phrase) + r"\s*:?\s*", re.IGNORECASE | re.MULTILINE)
                    temp_cleaned_source = pattern.sub("", temp_cleaned_source, count=1).strip()
                cleaned_source = temp_cleaned_source

        if not cleaned_source.lower().startswith('digraph'): # case-insensitive check
            print(f"Warning [dependency_graph]: LLM output after cleanup doesn't look like DOT language:\n---\n{cleaned_source}\n---", file=sys.stderr)
            print(f"Original LLM output was:\n---\n{dot_source_from_llm}\n---", file=sys.stderr)
            return f"Error [dependency_graph]: LLM did not return valid DOT language for dependency graph. Cleaned output started with: '{cleaned_source[:70]}...'"

        # --- Step 2: Render DOT source using Graphviz ---
        print(f"Explainer [dependency_graph]: Rendering DOT source to {OUTPUT_FILENAME}.{OUTPUT_FORMAT}...")
        try:
            # Use 'dot' engine for hierarchical layouts, or 'fdp', 'neato' for spring model layouts
            graph = graphviz.Source(cleaned_source, filename=OUTPUT_FILENAME, format=OUTPUT_FORMAT, engine='dot')
            output_path = graph.render(cleanup=True, view=False)

            print(f"Explainer [dependency_graph]: Successfully rendered dependency graph.")
            return f"Success: Dependency graph saved to: {output_path}"

        except graphviz.exceptions.ExecutableNotFound:
            print("Error [dependency_graph]: Graphviz executable not found.", file=sys.stderr)
            print("Please ensure Graphviz is installed correctly and its 'bin' directory is in your system's PATH.", file=sys.stderr)
            print("Installation guide: https://graphviz.org/download/", file=sys.stderr)
            return "Error: Graphviz executable not found. Please install Graphviz system-wide."
        except Exception as render_err:
            print(f"Error [dependency_graph]: Failed to render DOT source: {render_err}", file=sys.stderr)
            print(f"--- Cleaned DOT Source Attempted ---\n{cleaned_source}\n--------------------------", file=sys.stderr)
            return f"Error: Failed to render dependency graph image. Details: {render_err}"

    except Exception as e:
        return f"Error [dependency_graph]: Exception during LLM call ({provider}, model: {model_name}) for DOT source: {type(e).__name__}: {e}"

