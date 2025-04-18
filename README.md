# Code Analyzer (using Ollama)

This Python script analyzes Python or Java source code files or directories using a locally running Ollama Large Language Model (LLM). It reads the source code, sends it to the specified Ollama model, and requests an analysis in one of several output formats.  The output formats so far include:

1.  **Bulleted Description (Default):**
2.  **Paragraph Narrative:**
3.  **Flowchart Description (Text-Based):**
4.  **UML Components Description (Text-Based):**
5.  **Other Visual Metaphor Description (Text-Based):**
6.  **Table of Method Inputs/Outputs:**

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

## Output Formats (`-f` option)

Choose the desired output format using the `-f` flag followed by the number. The script asks the LLM to structure its analysis as follows:

1.  **Bulleted Description (Default):**
    * Provides a concise summary using bullet points.
    * Focuses on the main components, primary purpose, and overall functionality of the code.

2.  **Paragraph Narrative:**
    * Explains what the code does in a descriptive paragraph format.
    * Covers the code's purpose and how different parts interact to achieve the goal.

3.  **Flowchart Description (Text-Based):**
    * Describes the step-by-step execution flow of the code.
    * Details logic, loops, conditions, and function/method calls sequentially.
    * **Note:** This option generates a *textual description* intended to be useful for *manually creating* a flowchart (e.g., using tools like Mermaid, PlantUML, or diagramming software). It does not generate an image directly.

4.  **UML Components Description (Text-Based):**
    * Identifies key object-oriented elements like classes, interfaces, and methods.
    * Describes their main attributes, methods, and relationships (inheritance, composition).
    * **Note:** This option provides a *structured text description* suitable as a basis for *manually creating* a basic UML class diagram. It does not generate an image directly.

5.  **Other Visual Metaphor Description (Text-Based):**
    * Explains the code's structure or behavior using an analogy or metaphor (e.g., comparing it to a factory assembly line, a decision tree, etc.).
    * The description is purely textual.

6.  **Table of Method Inputs/Outputs:**
    * Analyzes significant functions or methods within the code.
    * Presents the findings in a table (usually Markdown format).
    * Lists method/function name, its purpose, input parameters (and expected types if the LLM can infer them), and its return value or main side effects.
