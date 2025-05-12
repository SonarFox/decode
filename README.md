# AI-Powered Code Explainer

This Python script leverages Large Language Models (LLMs) like Ollama (local) and Google's Gemini to analyze source code files and provide explanations in various formats. It features a modular system allowing users to choose how the code's understanding is presented, including text-based summaries, component breakdowns, edge case analysis, and even graphical flowcharts.

## Features

* **Dual LLM Support:** Choose between using a local Ollama instance or Google's Gemini API.
* **Modular Explainer System:** Easily extendable with new explanation formats by adding Python modules to the `explainers/` directory.
* **Multiple Explanation Formats:**
    * **Simple Summary:** A concise overview of the code.
    * **Key Components:** Identifies main functions, classes, and their purposes.
    * **Metaphor/Analogy:** Explains the code using a real-world analogy.
    * **Edge Cases for Testing:** Suggests edge cases to consider for automated tests.
    * **Flowchart (Text-Based):** Describes the execution flow in text suitable for a flowchart.
    * **Flowchart (Graphical):** Generates a graphical flowchart image (e.g., PNG) using Graphviz based on LLM output.
* **Interactive Format Selection:** Prompts the user to choose their preferred explanation style.
* **Source Code Analysis:** Reads single files. (The `read_source_file` function can be extended to support directories.)

## Directory Structure

your_project_folder/
├── basic_code_explainer.py     # Main script (or your chosen name)
├── requirements.txt            # Python dependencies
├── explainers/                 # Directory for explainer modules
│   ├── init.py
│   ├── simple_summary.py
│   ├── key_components.py
│   ├── metaphor_analogy.py
│   ├── edge_cases.py
│   ├── flowchart_text.py
│   └── flowchart_graphical.py
└── flowchart_output.png        # Example output from graphical flowchart (generated in the run directory)


## Setup and Installation

### 1. Prerequisites

* **Python:** Version 3.8 or higher recommended.
* **Git:** For cloning the repository (if applicable).
* **Ollama:** If using the Ollama provider. [Install Ollama](https://ollama.com/).
* **Graphviz (System Install):** **Required** for the "Flowchart (Graphical)" explainer. This is separate from the Python `graphviz` library.

### 2. Clone the Repository (Optional)

If you have this project in a Git repository:
```bash
git clone <your-repository-url>
cd your_project_folder
3. Create a Virtual Environment (Recommended)
It's highly recommended to use a virtual environment to manage project dependencies.

Bash

# Navigate to your project folder
cd your_project_folder

# Create a virtual environment named 'venv'
python -m venv venv

# Activate the virtual environment:
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
You should see (venv) at the beginning of your terminal prompt.

4. Install Python Dependencies
With your virtual environment activated, install the required Python packages:

Bash

pip install -r requirements.txt
If you don't have a requirements.txt yet, create one in your project's root directory with the following content:

Plaintext

# requirements.txt
ollama>=0.1.8
requests>=2.20.0
google-generativeai>=0.5.0
graphviz>=0.20.0
Then run pip install -r requirements.txt.

5. Ollama Setup (If using Ollama)
Ensure the Ollama application is running or the server is started (e.g., by running ollama serve in a separate terminal).
Pull the LLM models you intend to use. The script defaults to llama3.
Bash

ollama pull llama3
ollama pull mistral # Example for another model
ollama pull codellama # Example for a code-specific model
6. Gemini API Key Setup (If using Gemini)
Obtain a Gemini API key from Google AI Studio.
You can provide the API key in one of two ways:
Environment Variable (Recommended): Set the GEMINI_API_KEY environment variable to your API key value.
Bash

# On Linux/macOS (add to your .bashrc or .zshrc for persistence)
export GEMINI_API_KEY="YOUR_API_KEY_HERE"

# On Windows (PowerShell - for current session)
$env:GEMINI_API_KEY="YOUR_API_KEY_HERE"
# (To set it permanently on Windows, search for "environment variables")

# On Windows (Command Prompt - for current session)
set GEMINI_API_KEY=YOUR_API_KEY_HERE
Command-line Argument: Use the --api-key flag when running the script (less secure if sharing command history).
7. Install Graphviz System Software (Crucial for Graphical Flowcharts)
The Python graphviz library is an interface to the Graphviz layout programs. You must install Graphviz on your operating system for the graphical flowchart feature to work.

Official Download Page: https://graphviz.org/download/
macOS (using Homebrew):
Bash

brew install graphviz
Debian/Ubuntu Linux:
Bash

sudo apt update
sudo apt install graphviz
Windows: Download the .msi installer from the official site. Important: During installation or afterwards, ensure the Graphviz bin directory (e.g., C:\Program Files\Graphviz\bin) is added to your system's PATH environment variable. You might need to restart your terminal or system for the PATH changes to take effect.
Verify Graphviz Installation:
After installing, open a new terminal or command prompt and type:

Bash

dot -V
This command should print the installed Graphviz version (e.g., dot - graphviz version X.Y.Z ...). If the command is not found, the Python script will not be able to render graphical flowcharts and will likely raise an ExecutableNotFound error.

Running the Script
The main script (e.g., basic_code_explainer.py or the name you've given it) is run from the command line from within your project directory (and with the virtual environment activated).

Basic Syntax:

Bash

python your_main_script_name.py <path_to_source_code_file> [options]
Examples:

Explain a Python file using Ollama (default provider) and default model (llama3):

Bash

python your_main_script_name.py path/to/your/code.py
Explain a Java file using Ollama with a specific model:

Bash

python your_main_script_name.py path/to/your/code.java --provider ollama --model codellama
Explain a JavaScript file using Gemini (API key set as environment variable):

Bash

python your_main_script_name.py path/to/your/script.js --provider gemini
Explain a C++ file using Gemini, providing API key as argument and specifying a model:

Bash

python your_main_script_name.py path/to/your/main.cpp --provider gemini --model gemini-1.5-pro-latest --api-key YOUR_ACTUAL_API_KEY
Interactive Format Selection:

After the script reads the source code and gets a base explanation from the LLM, it will prompt you to choose the explanation format:

Select how you want the code to be explained:
  1: Simple Summary (Default)
  2: Edge Cases
  3: Flowchart Graphical
  4: Flowchart Text
  5: Key Components
  6: Metaphor Analogy
Enter your choice (1-6) [default: 1 (Simple Summary)]:
Enter the number corresponding to your desired format.

Graphical Flowchart Output:

If you select the "Flowchart Graphical" option and it's successful, an image file (e.g., flowchart_output.png) will be saved in the same directory where you ran the script. The script will print the path to this file.

Adding New Explainers
The system is designed to be extensible. To add a new way of explaining code:

Create a new Python file in the explainers/ directory (e.g., my_new_explainer.py).
Inside this file, define a function named explain. This function must accept base_explanation as its first argument. It will also receive llm_client, model_name, provider, original_code, and any other arguments passed via **kwargs (like api_key) from the main script.
Python

# explainers/my_new_explainer.py
# Import necessary libraries (ollama, google.generativeai, etc.) if making further LLM calls

def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    # Your logic here to transform or augment the base_explanation
    # Example: api_key = kwargs.get('api_key') # if using Gemini for a secondary call
    # ...
    formatted_explanation = f"This is a new explanation based on: {base_explanation[:50]}..."
    return formatted_explanation
The main script will automatically discover this new explainer module during startup (if it's in the explainers directory and contains an explain function).
The menu option presented to the user will be derived from the Python filename (e.g., my_new_explainer.py will appear as "My New Explainer" in the list).
Troubleshooting
graphviz.exceptions.ExecutableNotFound: This means the Graphviz system software is not installed correctly or its bin directory is not in your system's PATH. Refer to Step 7 of the installation.
Ollama errors (e.g., connection refused): Ensure your Ollama server/application is running.
Gemini errors (e.g., authentication): Double-check your Gemini API key and ensure it's correctly set as an environment variable or passed as an argument.
LLM output issues (e.g., "did not return valid DOT language"): The LLM might not always perfectly follow the prompt. The script includes some cleanup, but complex or unexpected LLM responses might still cause issues. Trying a different model or refining the prompt within the specific explainer module might help.