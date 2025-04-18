# Code Analyzer (using Ollama)

This Python script analyzes Python or Java source code files or directories using a locally running Ollama Large Language Model (LLM). It reads the source code, sends it to the specified Ollama model, and requests an analysis in one of several output formats.

## Prerequisites

Before running this script, ensure you have the following installed and configured:

1.  **Python 3:** The script is written for Python 3. Download from [python.org](https://www.python.org/) if needed.
2.  **Ollama:** You need Ollama installed and **running** on your system. Download from [ollama.com](https://ollama.com/). The script connects to the default Ollama API endpoint (`http://localhost:11434`).
3.  **An Ollama Model:** You need at least one LLM pulled locally via Ollama. Models suitable for code analysis (like `llama3`, `codellama`, `mistral`) are recommended. You can pull models using the command line (see Setup).
4.  **Required Python Libraries:** The script depends on the `ollama` and `requests` libraries.

## Setup Instructions

1.  **Install Ollama:**
    * Download and install Ollama from [ollama.com](https://ollama.com/).
    * Follow their instructions for your operating system.
    * **Important:** Ensure the Ollama application/service is running before executing the Python script.

2.  **Pull an Ollama Model:**
    * Open your terminal or command prompt.
    * Pull a model you want to use for analysis. For example, to get Llama 3:
        ```bash
        ollama pull llama3
        ```
    * You can replace `llama3` with other models like `codellama`, `mistral`, etc. The script defaults to `llama3` if no model is specified via the command line.

3.  **Install Python Libraries:**
    * Open your terminal or command prompt.
    * Install the required libraries using pip:
        ```bash
        pip install ollama requests
        # Or, if you use pip3 explicitly:
        # pip3 install ollama requests
        ```

4.  **Save the Script:**
    * Save the Python code analyzer script provided in the conversation into a file. Let's assume you named it `main.py`. Place it in a convenient directory.

## Running the Script

Execute the script from your terminal, providing the path to the source code file or directory you want to analyze.

**Basic Command Structure:**

```bash
python main.py <path_to_code_file_or_directory> [options]
# Or, if you use python3 explicitly:
# python3 main.py <path_to_code_file_or_directory> [options]
