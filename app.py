# basic_code_explainer.py (app.py)
import argparse
import os
import sys
import importlib
import importlib.util
import ollama
import requests
import re
import html
import shutil
import subprocess
import tempfile
import uuid

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory

# --- Configuration ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = "llama3"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"
DEFAULT_EXPLAINER_DIR_NAME = "explainers"
DEFAULT_REQUIREMENTS_FILENAME = "functional-requirements.txt"

SUPPORTED_EXTENSIONS = (
    '.py', '.java', '.js', '.ts', '.go', '.rb', '.php', '.cpp', '.c', '.h', '.hpp',
    '.cs', '.rs', '.swift', '.kt', '.scala', '.pl', '.pm', '.sh', '.bash',
    '.html', '.htm', '.css', '.scss', '.less', '.sql', '.md', '.txt',
    '.json', '.yaml', '.yml', '.xml', '.ini', '.toml', '.dockerfile', 'dockerfile', '.tf'
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPLAINER_DIR_PATH = os.path.join(BASE_DIR, DEFAULT_EXPLAINER_DIR_NAME)
STATIC_GENERATED_IMAGES_DIR_NAME = "generated_images"
STATIC_GENERATED_IMAGES_PATH = os.path.join(BASE_DIR, 'static', STATIC_GENERATED_IMAGES_DIR_NAME)

os.makedirs(STATIC_GENERATED_IMAGES_PATH, exist_ok=True)

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


    class GenaiPlaceholder:
        pass


    genai = GenaiPlaceholder()  # type: ignore

try:
    import graphviz

    GRAPHVIZ_PYTHON_LIB_AVAILABLE = True
except ImportError:
    GRAPHVIZ_PYTHON_LIB_AVAILABLE = False

GRAPHVIZ_SYSTEM_AVAILABLE = shutil.which("dot") is not None
MMDC_SYSTEM_AVAILABLE = shutil.which("mmdc") is not None


# --- Helper Functions (Keep as in previous complete app.py version) ---
def check_ollama_server(host=OLLAMA_HOST):
    print(f"Checking for Ollama server at {host}...")
    try:
        response = requests.get(host, timeout=3)
        response.raise_for_status()
        print("Ollama server found and responding.")
        return True
    except Exception as e:
        print(f"Ollama server check failed: {e}", file=sys.stderr)
        return False


def read_source_path(source_path_input):
    all_code = ""
    files_processed = []
    base_path = os.path.abspath(source_path_input)
    print(f"Reading source code from: {base_path}")
    if not os.path.exists(base_path):
        flash(f"Error: Source path not found at '{base_path}'", "danger")
        return None, []
    if os.path.isfile(base_path):
        filename_lower = base_path.lower()
        if any(filename_lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            try:
                with open(base_path, 'r', encoding='utf-8', errors='ignore') as f:
                    all_code = f.read()
                files_processed.append(base_path)
                print(f"Read file: {base_path}")
            except Exception as e:
                flash(f"Warning: Could not read file {base_path}: {e}", "warning")
        else:
            flash(f"Warning: File '{base_path}' does not have a supported extension. Skipping.", "warning")
    elif os.path.isdir(base_path):
        print(f"Reading supported files from directory: {base_path}")
        for root, dirs, files in os.walk(base_path, topdown=True):
            dirs[:] = [d for d in dirs if
                       not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'target', 'build', 'dist',
                                                           '.git', '.svn', '.hg']]
            files = [f for f in files if not f.startswith('.')]
            files.sort()
            for filename in files:
                filename_lower = filename.lower()
                if filename in SUPPORTED_EXTENSIONS or any(
                        filename_lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, base_path)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            print(f"  - Reading: {relative_path}")
                            content = f.read()
                            separator = f"\n\n{'=' * 20} Content from: {relative_path} {'=' * 20}\n\n"
                            all_code += separator + content
                        files_processed.append(file_path)
                    except Exception as e:
                        flash(f"Warning: Could not read file {file_path}: {e}", "warning")
        if not files_processed:
            flash(f"Warning: No supported files found in directory '{base_path}'.", "warning")
    else:
        flash(f"Error: Source path '{base_path}' is not a file or directory.", "danger")
        return None, []
    if not all_code.strip():
        flash("Warning: No code content was successfully read.", "warning")
        return None, []
    return all_code, files_processed


def read_text_file(file_path_input, file_description="file"):
    if not file_path_input:
        return None, None
    abs_path = os.path.abspath(file_path_input)
    print(f"Attempting to read {file_description} from: {abs_path}")
    if not os.path.exists(abs_path):
        flash(
            f"Info: {file_description.capitalize()} '{os.path.basename(abs_path)}' not found at specified path or in current directory.",
            "info")
        return None, abs_path
    if not os.path.isfile(abs_path):
        flash(f"Warning: {file_description.capitalize()} path '{abs_path}' is not a file.", "warning")
        return None, abs_path
    try:
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if not content.strip():
            flash(f"Info: {file_description.capitalize()} '{abs_path}' is empty.", "info")
            return "", abs_path
        print(f"Successfully read {file_description}: {abs_path}")
        return content, abs_path
    except Exception as e:
        flash(f"Error reading {file_description} '{abs_path}': {e}", "danger")
        return None, abs_path


def discover_explainers(explainer_dir_path):
    explainers = {}
    if not os.path.isdir(explainer_dir_path):
        print(f"Warning: Explainer directory '{explainer_dir_path}' not found.", file=sys.stderr)
        return explainers
    explainer_package_name = os.path.basename(explainer_dir_path)
    module_search_path = os.path.dirname(explainer_dir_path)
    if module_search_path not in sys.path:
        sys.path.insert(0, module_search_path)
    print(f"Discovering explainers in '{explainer_dir_path}' (package: {explainer_package_name})...")
    try:
        for filename in os.listdir(explainer_dir_path):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name_simple = filename[:-3]
                import_path = f"{explainer_package_name}.{module_name_simple}"
                full_module_path = os.path.join(explainer_dir_path, filename)
                try:
                    spec = importlib.util.spec_from_file_location(import_path, full_module_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[import_path] = module
                        spec.loader.exec_module(module)  # type: ignore
                        if hasattr(module, 'explain'):
                            requires_graphviz = getattr(module, 'REQUIRES_GRAPHVIZ', False)
                            requires_mmdc = getattr(module, 'REQUIRES_MMDC', False)  # Check for mmdc requirement
                            can_load = True
                            reason = ""
                            if requires_graphviz and (
                                    not GRAPHVIZ_PYTHON_LIB_AVAILABLE or not GRAPHVIZ_SYSTEM_AVAILABLE):
                                can_load = False
                                reason = "Requires Graphviz (Python library and system install), which is not fully available."
                            if requires_mmdc and not MMDC_SYSTEM_AVAILABLE:
                                can_load = False
                                reason = "Requires Mermaid CLI (mmdc), which is not available or not in PATH."
                            if can_load:
                                explainers[module_name_simple] = import_path
                                print(f"  - Found valid explainer: '{module_name_simple}'")
                            else:
                                print(f"  - Skipping explainer '{module_name_simple}': {reason}")
                        else:
                            print(f"Warning: Module '{import_path}' missing 'explain' function. Skipping.",
                                  file=sys.stderr)
                except Exception as e:
                    print(f"Warning: Error importing or validating explainer '{import_path}': {e}", file=sys.stderr)
    except Exception as e:
        print(f"Error accessing explainer directory '{explainer_dir_path}': {e}", file=sys.stderr)
    return explainers


# *** MODIFIED run_explainer function ***
def run_explainer(explainer_name, import_path, base_explanation, **kwargs):
    try:
        print(f"\n--- Applying Explainer: {explainer_name} ---")
        explainer_module = importlib.import_module(import_path)
        if hasattr(explainer_module, 'explain'):

            target_output_file_base_for_explainer = None
            # Determine if the explainer is expected to generate an image
            # Use flags from the explainer module itself
            is_image_explainer = False
            if getattr(explainer_module, 'REQUIRES_GRAPHVIZ', False):
                is_image_explainer = True
            elif getattr(explainer_module, 'REQUIRES_MMDC', False):
                is_image_explainer = True
            # Fallback to name checking if flags are not set (less reliable)
            # elif "graphical" in explainer_name or "image" in explainer_name or "diagram" in explainer_name:
            #     is_image_explainer = True

            if is_image_explainer:
                unique_id = uuid.uuid4().hex[:8]
                explainer_module_output_base = getattr(explainer_module, 'OUTPUT_FILENAME_BASE', explainer_name)

                target_output_file_base_for_explainer = os.path.join(
                    STATIC_GENERATED_IMAGES_PATH,
                    f"{explainer_module_output_base}_{unique_id}"
                )
                # Pass this to the explainer module via kwargs
                kwargs["target_output_file_base"] = target_output_file_base_for_explainer
                print(
                    f"DEBUG [app.py]: Setting target_output_file_base for '{explainer_name}': {target_output_file_base_for_explainer}",
                    file=sys.stderr)

            formatted_result = explainer_module.explain(base_explanation=base_explanation, **kwargs)

            if isinstance(formatted_result, str) and (formatted_result.startswith("Success:") and (
                    '.png' in formatted_result or '.svg' in formatted_result)):
                abs_image_path_from_explainer = formatted_result.split("Success: ")[1].split(" saved to: ")[1].strip()

                # Ensure the path is indeed within our static generated images directory
                # This also helps construct the correct web path if the explainer used the target_output_file_base
                if os.path.abspath(abs_image_path_from_explainer).startswith(
                        os.path.abspath(STATIC_GENERATED_IMAGES_PATH)):
                    rel_image_path = os.path.relpath(abs_image_path_from_explainer, STATIC_GENERATED_IMAGES_PATH)
                    web_image_path = url_for('static', filename=f'{STATIC_GENERATED_IMAGES_DIR_NAME}/{rel_image_path}')
                    print(
                        f"DEBUG [app.py]: Image explainer success. abs_path: {abs_image_path_from_explainer}, rel_path: {rel_image_path}, web_path: {web_image_path}",
                        file=sys.stderr)
                    return {"type": "image", "path": web_image_path, "message": formatted_result}
                else:
                    flash(
                        f"Error: Image explainer saved file '{abs_image_path_from_explainer}' outside designated static area '{STATIC_GENERATED_IMAGES_PATH}'. Please check explainer's output path logic.",
                        "danger")
                    return {"type": "text", "content": f"Error processing image path. {formatted_result}"}

            print(f"--- Explainer '{explainer_name}' Applied Successfully (Text Output) ---")
            if not isinstance(formatted_result, str) and not isinstance(formatted_result, dict):
                flash(f"Warning: Explainer '{explainer_name}' did not return a string or dict.", "warning")
                return {"type": "text", "content": f"Error: Explainer '{explainer_name}' returned unexpected type."}

            if isinstance(formatted_result, str):
                return {"type": "text", "content": formatted_result}
            return formatted_result  # Should be a dict if already processed

        else:
            flash(f"Error: Explainer module '{import_path}' is missing 'explain' function.", "danger")
            return {"type": "text",
                    "content": f"Error: Could not run explainer '{explainer_name}'. Function not found."}
    except Exception as e:
        flash(f"Error running explainer '{explainer_name}': {e}", "danger")
        import traceback
        traceback.print_exc()
        return {"type": "text", "content": f"Error: An exception occurred while running explainer '{explainer_name}'."}


# get_base_explanation_llm, Flask routes, and if __name__ == "__main__": block
# (Keep these functions as they were in the version that auto-detects requirements file)
def get_base_explanation_llm(provider, code_content, model_name, ollama_host_url, gemini_key):
    if provider == 'ollama':
        if not check_ollama_server(ollama_host_url):
            flash("Ollama server not reachable. Please ensure it's running.", "danger")
            return "Error: Ollama server not reachable."
        prompt = f"Please analyze the following source code (which may consist of multiple concatenated files) in detail. Provide a comprehensive explanation covering:\n1. The overall purpose and main functionality of the combined code.\n2. Key components (functions, classes, modules) across the different files if applicable, and their individual roles.\n3. How the components interact or the general execution flow of the entire codebase.\n4. Any notable inputs the code expects or outputs it produces.\n\n--- Source Code Start ---\n{code_content}\n--- Source Code End ---\n\nDetailed Explanation:"
        try:
            client = ollama.Client(host=ollama_host_url)
            response = client.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}])
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                content = response.message.content
                return content if content and content.strip() else "Error: Ollama returned an empty explanation."
            return f"Error: Could not extract explanation from Ollama. Raw: {response}"
        except Exception as e:
            return f"Error during Ollama call: {e}"
    elif provider == 'gemini':
        if not GEMINI_AVAILABLE: return "Error: Gemini library not installed."
        if not gemini_key: return f"Error: Gemini API key not provided."
        prompt = f"Please analyze the following source code (which may consist of multiple concatenated files) in detail. Provide a comprehensive explanation covering:\n1. The overall purpose and main functionality of the combined code.\n2. Key components (functions, classes, modules) across the different files if applicable, and their individual roles.\n3. How the components interact or the general execution flow of the entire codebase.\n4. Any notable inputs the code expects or outputs it produces.\n\n--- Source Code Start ---\n{code_content}\n--- Source Code End ---\n\nDetailed Explanation:"
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = ""
            if response and hasattr(response, 'text'):
                text = response.text
            elif response and hasattr(response, 'parts') and response.parts:
                text = "".join(p.text for p in response.parts if hasattr(p, 'text'))
            return text if text and text.strip() else "Error: Gemini returned an empty explanation."
        except Exception as e:
            return f"Error during Gemini call: {e}"
    return "Error: Unknown LLM provider."


@app.route('/', methods=['GET', 'POST'])
def index():
    available_explainers_dict = discover_explainers(EXPLAINER_DIR_PATH)
    sorted_explainer_names = sorted(list(available_explainers_dict.keys()))
    if 'simple_summary' in sorted_explainer_names:
        sorted_explainer_names.remove('simple_summary')
        sorted_explainer_names.insert(0, 'simple_summary')
    explainer_choices = [(name, name.replace('_', ' ').title()) for name in sorted_explainer_names]

    form_data_to_pass = request.form.to_dict(flat=False)  # Get all form data, including multi-selects if any
    # Simplify for single value fields that are commonly used
    simple_form_data = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in form_data_to_pass.items()}

    if request.method == 'POST':
        source_path_input = request.form.get('source_path', '').strip()

        requirements_text_content = None
        requirements_file_actual_path = None
        requirements_file_obj = request.files.get('requirements_file')

        if requirements_file_obj and requirements_file_obj.filename:
            try:
                requirements_text_content = requirements_file_obj.read().decode('utf-8', errors='ignore')
                requirements_file_actual_path = requirements_file_obj.filename
                if not requirements_text_content.strip():
                    flash(f"Uploaded requirements file '{requirements_file_obj.filename}' is empty.", "info")
                    requirements_text_content = ""
                else:
                    flash(f"Successfully processed uploaded requirements file: {requirements_file_obj.filename}",
                          "success")
            except Exception as e:
                flash(f"Error reading uploaded requirements file: {e}", "danger")
                requirements_text_content = None

        llm_provider = request.form.get('llm_provider', 'ollama')
        ollama_model_name = request.form.get('ollama_model', DEFAULT_OLLAMA_MODEL)
        gemini_model_name = request.form.get('gemini_model', DEFAULT_GEMINI_MODEL)
        gemini_api_key_input = request.form.get('gemini_api_key', '')
        selected_explainer_module_name = request.form.get('explainer')

        if not source_path_input:
            flash("Source code path is required.", "danger")
            return render_template('index.html', explainers=explainer_choices, result=None, base_explanation=None,
                                   form_data=simple_form_data, GEMINI_API_KEY_ENV_VAR=GEMINI_API_KEY_ENV_VAR)

        model_name = ollama_model_name if llm_provider == 'ollama' else gemini_model_name
        gemini_api_key_resolved = gemini_api_key_input or os.getenv(GEMINI_API_KEY_ENV_VAR)

        if llm_provider == 'gemini' and not gemini_api_key_resolved:
            flash("Gemini API key is required for Gemini provider.", "danger")
            return render_template('index.html', explainers=explainer_choices, result=None, base_explanation=None,
                                   form_data=simple_form_data, GEMINI_API_KEY_ENV_VAR=GEMINI_API_KEY_ENV_VAR)

        if not selected_explainer_module_name or selected_explainer_module_name not in available_explainers_dict:
            flash("Invalid explainer selected.", "danger")
            return render_template('index.html', explainers=explainer_choices, result=None, base_explanation=None,
                                   form_data=simple_form_data, GEMINI_API_KEY_ENV_VAR=GEMINI_API_KEY_ENV_VAR)

        source_code, processed_files = read_source_path(source_path_input)
        if not source_code:
            return render_template('index.html', explainers=explainer_choices, result=None, base_explanation=None,
                                   form_data=simple_form_data, GEMINI_API_KEY_ENV_VAR=GEMINI_API_KEY_ENV_VAR)

        flash("Requesting base explanation from LLM...", "info")
        base_explanation = get_base_explanation_llm(
            llm_provider, source_code, model_name, OLLAMA_HOST, gemini_api_key_resolved
        )
        if base_explanation.startswith("Error:"):
            flash(base_explanation, "danger")
            return render_template('index.html', explainers=explainer_choices, result=None, base_explanation=None,
                                   form_data=simple_form_data, GEMINI_API_KEY_ENV_VAR=GEMINI_API_KEY_ENV_VAR)

        explainer_import_path = available_explainers_dict.get(selected_explainer_module_name)
        final_result_data = None
        if explainer_import_path:
            explainer_kwargs = {
                "llm_client": ollama.Client(host=OLLAMA_HOST) if llm_provider == 'ollama' else None,
                "model_name": model_name,
                "original_code": source_code,
                "provider": llm_provider,
                "processed_files": processed_files,
                "requirements_text": requirements_text_content,
                "requirements_file_path": requirements_file_actual_path
            }
            if llm_provider == 'gemini':
                explainer_kwargs["api_key"] = gemini_api_key_resolved

            flash(f"Applying explainer: {selected_explainer_module_name}...", "info")
            final_result_data = run_explainer(
                selected_explainer_module_name,
                explainer_import_path,
                base_explanation,
                **explainer_kwargs
            )
        else:
            flash(f"Internal Error: Explainer '{selected_explainer_module_name}' not found.", "danger")
            final_result_data = {"type": "text", "content": "Error: Selected explainer could not be run."}

        return render_template('index.html',
                               explainers=explainer_choices,
                               result=final_result_data,
                               base_explanation=base_explanation,
                               form_data=simple_form_data,  # Pass simplified form data for repopulation
                               GEMINI_API_KEY_ENV_VAR=GEMINI_API_KEY_ENV_VAR)

    return render_template('index.html', explainers=explainer_choices, result=None, base_explanation=None,
                           form_data=simple_form_data, GEMINI_API_KEY_ENV_VAR=GEMINI_API_KEY_ENV_VAR)


if __name__ == '__main__':
    print(f"Gemini Available: {GEMINI_AVAILABLE}")
    print(f"Graphviz Python Lib Available: {GRAPHVIZ_PYTHON_LIB_AVAILABLE}")
    print(f"Graphviz System Available: {GRAPHVIZ_SYSTEM_AVAILABLE}")
    print(f"Mermaid CLI (mmdc) System Available: {MMDC_SYSTEM_AVAILABLE}")
    print(f"Explainers will be loaded from: {EXPLAINER_DIR_PATH}")
    app.run(debug=True, host='0.0.0.0', port=5001)

