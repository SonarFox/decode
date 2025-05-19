# AI-Powered Code Explainer

This Python script leverages Large Language Models (LLMs) like Ollama (local) and Google's Gemini to analyze source code files or entire directories and provide explanations in various formats. It features a modular system allowing users to choose how the code's understanding is presented, including text-based summaries, component breakdowns, edge case analysis, and various visual diagrams.

## Features

* **Dual LLM Support:** Choose between using a local Ollama instance or Google's Gemini API.
* **Directory & File Analysis:** Can process single source code files or recursively scan entire directories.
* **Modular Explainer System:** Easily extendable with new explanation formats by adding Python modules to the `explainers/` directory.
* **Multiple Explanation Formats:**
    * **Text-Based:**
        * Simple Summary
        * Key Components
        * Metaphor/Analogy
        * Edge Cases for Testing
        * Flowchart (Text)
    * **Visual (Graphviz - auto-generated images):**
        * Flowchart (Graphical)
        * Dependency Graph
        * Call Graph
        * UML Class Diagram (DOT/Graphviz based)
    * **Visual (Mermaid CLI - auto-generated images):**
        * Sequence Diagram (Mermaid)
        * UML Class Diagram (Mermaid)
        * Architecture Diagram (Mermaid)
* **Interactive Format Selection:** Prompts the user to choose their preferred explanation style.

## Directory Structure

your_project_folder/├── basic_code_explainer.py     # Main script (or your chosen name)├── requirements.txt            # Python dependencies├── explainers/                 # Directory for explainer modules│   ├── init.py│   ├── simple_summary.py│   ├── key_components.py│   ├── metaphor_analogy.py│   ├── edge_cases.py│   ├── flowchart_text.py│   ├── flowchart_graphical.py  # Uses Graphviz│   ├── dependency_graph.py     # Uses Graphviz│   ├── call_graph_image.py     # Uses Graphviz│   ├── uml_class_diagram.py    # Uses Graphviz (for DOT-based UML)│   ├── sequence_diagram_mermaid_image.py # Uses Mermaid CLI│   ├── uml_class_diagram_mermaid_image.py  # Uses Mermaid CLI│   └── architecture_diagram_mermaid_image.py # Uses Mermaid CLI└── output_images/              # Example: Directory where images might be saved (script saves to current dir by default)├── flowchart_output.png├── dependency_graph_output.png├── uml_class_diagram_mermaid_output.png└── ...
## Setup and Installation

### 1. Prerequisites

* **Python:** Version 3.8 or higher recommended.
* **Git:** For cloning the repository (if applicable).
* **Ollama:** If using the Ollama provider. [Install Ollama](https://ollama.com/).
* **Graphviz (System Install):** **Required** for Graphviz-based visual explainers (Flowchart Graphical, Dependency Graph, Call Graph, UML Class Diagram via DOT).
* **Node.js and npm:** **Required** for Mermaid-based visual explainers (Sequence Diagram, UML Class Diagram via Mermaid, Architecture Diagram).

### 2. Clone the Repository (Optional)

If you have this project in a Git repository:
```bash
git clone <your-repository-url>
cd your_project_folder
3. Create a Virtual Environment (Recommended)It's highly recommended to use a virtual environment to manage project dependencies.# Navigate to your project folder
cd your_project_folder

# Create a virtual environment named 'venv'
python -m venv venv

# Activate the virtual environment:
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
You should see (venv) at the beginning of your terminal prompt.4. Install Python DependenciesWith your virtual environment activated, install the required Python packages:pip install -r requirements.txt
If you don't have a requirements.txt yet, create one in your project's root directory with the following content:# requirements.txt
ollama>=0.1.8
requests>=2.20.0
google-generativeai>=0.5.0
graphviz>=0.20.0
# No specific Python library needed for Mermaid CLI, it's a subprocess call
Then run pip install -r requirements.txt.5. Ollama Setup (If using Ollama)Ensure the Ollama application is running or the server is started (e.g., by running ollama serve in a separate terminal).Pull the LLM models you intend to use. The script defaults to llama3.ollama pull llama3
ollama pull mistral
ollama pull codellama
6. Gemini API Key Setup (If using Gemini)Obtain a Gemini API key from Google AI Studio.Provide the API key via:Environment Variable (Recommended): Set GEMINI_API_KEY="YOUR_API_KEY_HERE".Command-line Argument: Use the --api-key flag.7. Install Graphviz System Software (For Graphviz-based diagrams)The Python graphviz library is an interface. You must install Graphviz on your system for explainers like "Flowchart Graphical", "Dependency Graph", "Call Graph", and "UML Class Diagram (DOT)" to work.Official Download Page: https://graphviz.org/download/macOS (Homebrew): brew install graphvizDebian/Ubuntu Linux: sudo apt update && sudo apt install graphvizWindows: Download the installer. Important: Add the Graphviz bin directory (e.g., C:\Program Files\Graphviz\bin) to your system's PATH.Verify Graphviz Installation: Open a new terminal and type dot -V. It should print the version.8. Install Node.js, npm, and Mermaid CLI (For Mermaid-based diagrams)For explainers like "Sequence Diagram Mermaid Image", "UML Class Diagram Mermaid Image", and "Architecture Diagram Mermaid Image", you need the Mermaid Command Line Interface (mmdc).Install Node.js and npm: If not already installed, download from nodejs.org. npm is included with Node.js.Install Mermaid CLI (mmdc): Open your terminal or command prompt and run:npm install -g @mermaid-js/mermaid-cli
This installs mmdc globally.Verify Mermaid CLI Installation: Open a new terminal and type:mmdc --version
This should print the mmdc version. If the command is not found, ensure Node.js's global bin directory is in your system's PATH.Running the ScriptThe main script (e.g., basic_code_explainer.py) is run from the command line from within your project directory (with the virtual environment activated).Basic Syntax:python your_main_script_name.py <path_to_source_code_file_or_directory> [options]
Examples:Explain a Python file using Ollama (default):python basic_code_explainer.py path/to/your/code.py
Explain an entire directory using Gemini:python basic_code_explainer.py path/to/your_project_dir/ --provider gemini --api-key YOUR_GEMINI_KEY
Specify a model:python basic_code_explainer.py my_script.java --model codellama
Interactive Format Selection:The script will prompt you to choose an explanation format from the discovered explainers:Select how you want the code to be explained:
  1: Simple Summary (Default)
  2: Activity Diagram Mermaid Image
  3: Architecture Diagram Mermaid Image
  4: Call Graph Image
  5: Dependency Graph
  6: Edge Cases
  7: Flowchart Graphical
  8: Flowchart Text
  9: Key Components
 10: Metaphor Analogy
 11: Sequence Diagram Mermaid Image
 12: Uml Class Diagram
 13: Uml Class Diagram Mermaid Image
Enter your choice (1-13) [default: 1 (Simple Summary)]:
Enter the number for your desired format.Image Output:Visual explainers that generate images (Graphviz or Mermaid CLI based) will save the image file (e.g., flowchart_output.png, sequence_diagram_mermaid_output.png) in the same directory where you ran the script. The script will print the path to the generated file.Adding New ExplainersCreate a new Python file in the explainers/ directory (e.g., my_new_visualizer.py).Define an explain function: def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):Use kwargs to access api_key for Gemini or processed_files if needed.If your explainer uses Graphviz, add REQUIRES_GRAPHVIZ = True at the top of the module.If it uses Mermaid CLI, ensure your explain function calls mmdc via subprocess and handles errors (see existing Mermaid image explainers for examples).The main script will auto-discover it. The menu name is derived from the filename.Troubleshootinggraphviz.exceptions.ExecutableNotFound: Graphviz system software is not installed or not in PATH. See Step 7.mmdc: command not found or errors from mmdc: Mermaid CLI is not installed correctly or not in PATH. See Step 8.Ollama errors: Ensure Ollama server is running and models are pulled.Gemini errors: Check API key and internet connection.LLM output issues (e.g., invalid DOT/Mermaid syntax): LLMs may not always perfectly follow complex syntax prompts.Try