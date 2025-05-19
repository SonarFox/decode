# explainers/call_graph_image.py
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
OUTPUT_FILENAME_BASE = "call_graph_output"
OUTPUT_FORMAT = "png" # Or 'svg', 'pdf', etc.
# Add a flag to indicate if graphviz is required by this explainer
REQUIRES_GRAPHVIZ = True


def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    """
    Asks the LLM to generate a call graph description in DOT language format,
    then uses the graphviz library to render it as an image file.

    Args:
        base_explanation (str): The initial detailed explanation text.
        llm_client: The initialized LLM client instance (Ollama client or None for Gemini).
        model_name (str): The name of the LLM model to use.
        provider (str): The LLM provider ('ollama' or 'gemini').
        original_code (str): The original source code (essential for identifying calls).
        **kwargs: Accepts other potential arguments. Expected: 'api_key' if provider is 'gemini'.

    Returns:
        str: A success message with the output file path, or an error message.
    """
    print("Explainer [call_graph_image]: Requesting DOT language for Call Graph from LLM...")

    prompt = f"""
Based on the following detailed code analysis AND the original source code, generate a **Call Graph** description in the **DOT language** suitable for rendering with Graphviz.

Identify key functions, methods, or procedures and the calls made between them.
* Nodes should represent the functions/methods. Use meaningful and concise labels (e.g., function name, or Class.methodName).
* Directed edges (`Caller -> Callee;`) should indicate that the "Caller" function/method makes a call to the "Callee" function/method.
* Focus on the primary call relationships to keep the graph readable. Avoid overly granular or standard library calls unless they are central to the logic.
* If possible, indicate the entry point(s) or main function(s) by giving them a distinct style (e.g., `shape=doublecircle` or `fillcolor=lightgreen`).

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

--- Original Source Code Start ---
{original_code}
--- Original Source Code End ---

Provide *ONLY* the DOT language code block itself, starting directly with `digraph CallGraph {{` and ending with `}}`. Do not include any other explanatory text, markdown formatting like backticks, or the word 'dot' outside the code block.

**Example DOT Output for a Call Graph:**
```dot
digraph CallGraph {{
  rankdir=LR; // Left-to-Right or TB for Top-to-Bottom
  node [shape=box, style="rounded,filled", fillcolor=lightblue];

  // Nodes (Functions/Methods)
  "main" [label="main()", shape=doublecircle, fillcolor=palegreen];
  "processInput" [label="processInput(data)"];
  "validateData" [label="validateData(input)"];
  "calculateResult" [label="calculateResult(validData)"];
  "saveOutput" [label="saveOutput(result)"];
  "utility.format" [label="utility.format(text)"]; // Example for qualified name

  // Edges (Calls: A -> B means A calls B)
  "main" -> "processInput";
  "processInput" -> "validateData";
  "processInput" -> "calculateResult";
  "calculateResult" -> "utility.format";
  "main" -> "saveOutput";
}}
```

DOT Language Output:
"""

    dot_source_from_llm = ""
    try:
        # --- Step 1: Get DOT source from LLM ---
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                 return f"Error [call_graph_image]: Invalid or missing Ollama client."
            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.05} # Low temperature for structured output
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                dot_source_from_llm = response.message.content
            else:
                return f"Error [call_graph_image]: Unexpected Ollama response structure. Raw: {response}"

        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER:
                return "Error [call_graph_image]: Gemini library not available."
            api_key_for_gemini = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key_for_gemini:
                 return "Error [call_graph_image]: Gemini API key not available."

            genai.configure(api_key=api_key_for_gemini)
            gemini_model = genai.GenerativeModel(model_name)
            response = gemini_model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.05))

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
                 return f"Error [call_graph_image]: Could not extract DOT source from Gemini.{feedback_info}"
        else:
            return f"Error [call_graph_image]: Unknown provider '{provider}'."

        # --- Cleanup DOT source ---
        match = re.search(r"```(?:dot)?\s*(digraph\s+\w+\s*\{.*?\})\s*```", dot_source_from_llm, re.DOTALL | re.IGNORECASE)
        cleaned_source = ""
        if match:
            cleaned_source = match.group(1).strip()
        else:
            digraph_match = re.search(r"(digraph\s+\w+\s*\{.*)(?=\n?\s*\})", dot_source_from_llm, re.DOTALL | re.IGNORECASE) # Adjusted regex
            if digraph_match:
                 block_start_index = digraph_match.start(1)
                 first_brace_index = dot_source_from_llm.find('{', block_start_index)
                 if first_brace_index != -1:
                     open_braces = 0
                     for i, char in enumerate(dot_source_from_llm[first_brace_index:]):
                         if char == '{':
                             open_braces += 1
                         elif char == '}':
                             open_braces -= 1
                             if open_braces == 0:
                                 cleaned_source = dot_source_from_llm[block_start_index : first_brace_index + i + 1].strip()
                                 break
                     if not cleaned_source: # Fallback
                          cleaned_source = dot_source_from_llm.strip()
                 else: # No '{' found after 'digraph'
                      cleaned_source = dot_source_from_llm.strip()
            else:
                cleaned_source = dot_source_from_llm.strip()


        if not cleaned_source.lower().startswith('digraph'):
            print(f"Warning [call_graph_image]: LLM output after cleanup doesn't look like DOT language:\n---\n{cleaned_source}\n---", file=sys.stderr)
            print(f"Original LLM output was:\n---\n{dot_source_from_llm}\n---", file=sys.stderr)
            return f"Error [call_graph_image]: LLM did not return valid DOT language for Call Graph. Cleaned output started with: '{cleaned_source[:70]}...'"

        # --- Step 2: Render DOT source using Graphviz ---
        print(f"Explainer [call_graph_image]: Rendering DOT source to {OUTPUT_FILENAME_BASE}.{OUTPUT_FORMAT}...")
        try:
            graph = graphviz.Source(cleaned_source, filename=OUTPUT_FILENAME_BASE, format=OUTPUT_FORMAT, engine='dot')
            output_path = graph.render(cleanup=True, view=False)

            print(f"Explainer [call_graph_image]: Successfully rendered call graph.")
            return f"Success: Call graph image saved to: {output_path}"

        except graphviz.exceptions.ExecutableNotFound:
            print("Error [call_graph_image]: Graphviz executable not found.", file=sys.stderr)
            print("Please ensure Graphviz is installed correctly and its 'bin' directory is in your system's PATH.", file=sys.stderr)
            print("Installation guide: https://graphviz.org/download/", file=sys.stderr)
            return "Error: Graphviz executable not found. Please install Graphviz system-wide."
        except Exception as render_err:
            print(f"Error [call_graph_image]: Failed to render DOT source: {render_err}", file=sys.stderr)
            print(f"--- Cleaned DOT Source Attempted ---\n{cleaned_source}\n--------------------------", file=sys.stderr)
            return f"Error: Failed to render call graph image. Details: {render_err}"

    except Exception as e:
        return f"Error [call_graph_image]: Exception during LLM call ({provider}, model: {model_name}) for DOT source: {type(e).__name__}: {e}"

