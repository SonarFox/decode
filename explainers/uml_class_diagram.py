# explainers/uml_class_diagram.py
import os
import ollama
import graphviz  # Requires graphviz Python library and system installation
import sys  # For stderr
import re  # Import regular expressions
import html  # For escaping HTML characters in labels

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE_FOR_EXPLAINER = True
except ImportError:
    GEMINI_AVAILABLE_FOR_EXPLAINER = False

OUTPUT_FILENAME_BASE = "uml_class_diagram_output"  # Default if not called from web app
OUTPUT_FORMAT = "png"
REQUIRES_GRAPHVIZ = True


def escape_html_for_dot(text):
    if not isinstance(text, str): text = str(text)
    return html.escape(text)


def parse_llm_class_structure(llm_output_text):
    """
    Parses a structured text output from LLM into a list of classes
    with their attributes and methods.
    """
    # print("--- LLM Structured Output to Parse ---", file=sys.stderr) # Keep for deep debugging if needed
    # print(llm_output_text, file=sys.stderr)
    # print("--- End of LLM Structured Output ---", file=sys.stderr)

    classes = {}
    relationships = []
    current_class_name = None
    parsing_section = None  # None, "ATTRIBUTES", "METHODS"

    cleaned_llm_output = llm_output_text.strip()
    lines_for_parsing = cleaned_llm_output.splitlines()
    start_index = 0
    for i, line in enumerate(lines_for_parsing):
        stripped_line_lower = line.strip().lower()
        if stripped_line_lower.startswith("class:") or \
                stripped_line_lower.startswith("**class:") or \
                stripped_line_lower.startswith("relationship:") or \
                stripped_line_lower.startswith("**relationship:"):
            start_index = i
            break
    llm_output_text_to_parse = "\n".join(lines_for_parsing[start_index:])

    if llm_output_text_to_parse.startswith("```") and llm_output_text_to_parse.endswith("```"):
        temp_lines = llm_output_text_to_parse.splitlines()
        if temp_lines and temp_lines[0].startswith("```"):
            temp_lines.pop(0)
        if temp_lines and temp_lines[-1] == "```":
            temp_lines.pop()
        llm_output_text_to_parse = "\n".join(temp_lines)

    for line in llm_output_text_to_parse.splitlines():
        line = line.strip()
        if not line:
            continue

        class_match = re.match(r"(?:\*\*)?CLASS:(?:\*\*)?\s*([a-zA-Z_][\w.]*)", line, re.IGNORECASE)
        attrs_match = re.match(r"(?:\*\*)?ATTRIBUTES:(?:\*\*)?", line, re.IGNORECASE)
        methods_match = re.match(r"(?:\*\*)?METHODS:(?:\*\*)?", line, re.IGNORECASE)
        rel_match = re.match(
            r"(?:\*\*)?RELATIONSHIP:(?:\*\*)?\s*([a-zA-Z_][\w.]*)\s*->\s*([a-zA-Z_][\w.]*)\s*\[type=(\w+)(?:,\s*label=\"(.*?)\")?\]",
            line, re.IGNORECASE)
        rel_none_match = re.match(r"(?:\*\*)?RELATIONSHIP:(?:\*\*)?\s*None", line, re.IGNORECASE)
        separator_match = re.match(r"---", line)

        if class_match:
            current_class_name = class_match.group(1)
            if current_class_name not in classes:
                classes[current_class_name] = {"attributes": [], "methods": []}
            parsing_section = None
            # print(f"Parser: Found CLASS: {current_class_name}", file=sys.stderr)
        elif attrs_match and current_class_name:
            parsing_section = "ATTRIBUTES"
            # print(f"Parser: Switched to ATTRIBUTES for {current_class_name}", file=sys.stderr)
        elif methods_match and current_class_name:
            parsing_section = "METHODS"
            # print(f"Parser: Switched to METHODS for {current_class_name}", file=sys.stderr)
        elif rel_none_match:
            # print(f"Parser: Found 'RELATIONSHIP: None', skipping.", file=sys.stderr)
            parsing_section = None
        elif rel_match:
            source, target, rel_type, label = rel_match.groups()
            relationships.append({"source": source, "target": target, "type": rel_type.lower(), "label": label or ""})
            # print(f"Parser: Found RELATIONSHIP: {source} -> {target}", file=sys.stderr)
            parsing_section = None
        elif separator_match:
            # print(f"Parser: Found separator ---, resetting current class context.", file=sys.stderr)
            current_class_name = None
            parsing_section = None
        elif current_class_name and parsing_section:
            member_line = line.strip()
            if member_line and not member_line.lower().startswith("(no ") and not member_line.lower().startswith(
                    "omitted"):
                if parsing_section == "ATTRIBUTES":
                    classes[current_class_name]["attributes"].append(member_line)
                    # print(f"Parser: Added attribute to {current_class_name}: {member_line}", file=sys.stderr)
                elif parsing_section == "METHODS":
                    classes[current_class_name]["methods"].append(member_line)
                    # print(f"Parser: Added method to {current_class_name}: {member_line}", file=sys.stderr)
            # else:
            # print(f"Parser: Skipping empty or placeholder member line for {current_class_name}: '{member_line}'", file=sys.stderr)

    # print("--- Parsed Classes Dictionary (before returning) ---", file=sys.stderr)
    # import json
    # print(json.dumps(classes, indent=2), file=sys.stderr)
    # print("--- End of Parsed Classes Dictionary ---", file=sys.stderr)

    return classes, relationships


def generate_dot_from_structure(class_data, relationships_data):
    dot_lines = [
        'digraph UMLClassDiagram {',
        '  rankdir=TB;',
        '  graph [concentrate=true];',
        '  node [shape=none, margin=0, fontname="Helvetica"];',
        '  edge [fontname="Helvetica", fontsize=10];',
        ''
    ]
    if not class_data:
        dot_lines.append('  label="No class information parsed from LLM output.";')
        dot_lines.append('  fontsize=16;')
        dot_lines.append('}')
        return "\n".join(dot_lines)

    for class_name, members in class_data.items():
        node_id = f"{escape_html_for_dot(class_name)}_Node"

        attributes_html_list = []
        if members.get("attributes"):
            for attr in members["attributes"]:
                attributes_html_list.append(f"{escape_html_for_dot(attr)}")
        attributes_html_content = "<BR ALIGN=\"LEFT\"/>".join(
            attributes_html_list) if attributes_html_list else "<I>No attributes</I>"

        methods_html_list = []
        if members.get("methods"):
            for meth in members["methods"]:
                methods_html_list.append(f"{escape_html_for_dot(meth)}")
        methods_html_content = "<BR ALIGN=\"LEFT\"/>".join(
            methods_html_list) if methods_html_list else "<I>No methods</I>"

        label = f'''<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">
          <TR><TD BGCOLOR="lightblue" ALIGN="CENTER"><B>{escape_html_for_dot(class_name)}</B></TD></TR>
          <TR><TD ALIGN="LEFT" VALIGN="TOP">{attributes_html_content}</TD></TR>
          <TR><TD ALIGN="LEFT" VALIGN="TOP">{methods_html_content}</TD></TR>
        </TABLE>>'''
        dot_lines.append(f'  {node_id} [label={label}];')

    dot_lines.append('')
    for rel in relationships_data:
        if rel['source'] in class_data and rel['target'] in class_data:
            source_node = f"{escape_html_for_dot(rel['source'])}_Node"
            target_node = f"{escape_html_for_dot(rel['target'])}_Node"
            attrs = []
            if rel['type'] == "inheritance":
                attrs.append("arrowhead=empty, style=solid")
            elif rel['type'] == "aggregation":
                attrs.append('arrowhead=odiamond, style=solid, label="has a"')
            elif rel['type'] == "composition":
                attrs.append('arrowhead=diamond, style=solid, label="owns a"')
            elif rel['type'] == "association" or rel['type'] == "dependency":
                attrs.append('arrowhead=open, style=dashed')
                if rel['label']: attrs.append(f'label="{escape_html_for_dot(rel["label"])}"')
            if attrs: dot_lines.append(f"  {source_node} -> {target_node} [{', '.join(attrs)}];")
        else:
            print(
                f"Warning [uml_class_diagram]: Skipping relationship: {rel['source']} or {rel['target']} not in parsed classes.",
                file=sys.stderr)
    dot_lines.append('}')
    return "\n".join(dot_lines)


def explain(base_explanation, llm_client, model_name, provider, original_code, **kwargs):
    print("Explainer [uml_class_diagram]: Requesting structured class information from LLM...")

    # *** DEBUG: Print received kwargs to check for target_output_file_base ***
    print(f"DEBUG [uml_class_diagram]: Received kwargs: {kwargs.keys()}", file=sys.stderr)
    if 'target_output_file_base' in kwargs:
        print(f"DEBUG [uml_class_diagram]: target_output_file_base from kwargs: {kwargs['target_output_file_base']}",
              file=sys.stderr)
    else:
        print(f"DEBUG [uml_class_diagram]: 'target_output_file_base' NOT FOUND in kwargs. Using default.",
              file=sys.stderr)
    # *** END DEBUG ***

    # Prompt for structured text (same as before)
    prompt = f"""
Based on the following detailed code analysis AND the original source code, extract information about classes, their attributes, methods, and relationships.

**Output Format (Strictly follow this text-based format):**
For each class, provide its details in a block like this:

CLASS: ClassName
ATTRIBUTES:
[+-#] attributeName1: typeName
[+-#] attributeName2: typeName
... (If no attributes, you can omit the ATTRIBUTES: line and its content for that class, or write "ATTRIBUTES:" followed by "(No attributes for this class)")
METHODS:
[+-#] methodName1(param1: type, param2: type): returnType
[+-#] methodName2(): void
... (If no methods, you can omit the METHODS: line and its content for that class, or write "METHODS:" followed by "(No methods for this class)")
--- (Use three hyphens as a separator before the next class block OR before relationships section)

After all classes, list relationships (if any):
RELATIONSHIP: SourceClassName -> TargetClassName [type=inheritance]
RELATIONSHIP: SourceClassName -> TargetClassName [type=aggregation, label="has a"]
RELATIONSHIP: SourceClassName -> TargetClassName [type=composition, label="owns a"]
RELATIONSHIP: SourceClassName -> TargetClassName [type=association, label="uses method of"]
RELATIONSHIP: SourceClassName -> TargetClassName [type=dependency, label="depends on type"]
(If no relationships, you can write "RELATIONSHIP: None" or omit the RELATIONSHIP section entirely)


**Details for Attributes and Methods:**
* Start each line with visibility: `+` (public), `-` (private), `#` (protected). Default to `+` if unclear.
* Attributes: `visibility attributeName: typeName`
* Methods: `visibility methodName(parameterName1: parameterType1, ...): returnType`. Use `void` if no return type.
* For generic types like `List<String>`, represent them as `List<String>` in your output. My parser will handle HTML escaping later.

**Example Output:**
CLASS: User
ATTRIBUTES:
- userId: int
+ username: String
METHODS:
+ getProfile(): Profile
+ setUsername(newName: String): void
---
CLASS: Profile
ATTRIBUTES:
+ email: String
- lastLogin: Date
METHODS:
+ updateEmail(newEmail: String): boolean
---
CLASS: OrderService
ATTRIBUTES:
(No attributes for this class)
METHODS:
+ placeOrder(order: Order): boolean
---
RELATIONSHIP: User -> Profile [type=association, label="has profile"]
RELATIONSHIP: None 

--- Detailed Analysis Start ---
{base_explanation}
--- Detailed Analysis End ---

--- Original Source Code Start ---
{original_code}
--- Original Source Code End ---

Structured Class Information Output:
"""
    llm_structured_output = ""
    try:
        if provider == 'ollama':
            if not llm_client or not isinstance(llm_client, ollama.Client):
                return "Error [uml_class_diagram]: Invalid or missing Ollama client."
            response = llm_client.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.0, 'num_ctx': 8192}
            )
            if response and hasattr(response, 'message') and hasattr(response.message, 'content'):
                llm_structured_output = response.message.content
            else:
                return f"Error [uml_class_diagram]: Unexpected Ollama response. Raw: {response}"
        elif provider == 'gemini':
            if not GEMINI_AVAILABLE_FOR_EXPLAINER: return "Error [uml_class_diagram]: Gemini library not available."
            api_key = kwargs.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key: return "Error [uml_class_diagram]: Gemini API key not available."
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.0))
            if response and hasattr(response, 'text') and response.text:
                llm_structured_output = response.text
            elif response and hasattr(response, 'parts') and response.parts:
                llm_structured_output = "".join(p.text for p in response.parts if hasattr(p, 'text'))
            else:
                return f"Error [uml_class_diagram]: Could not extract structured data from Gemini. {str(response)[:200]}"
        else:
            return f"Error [uml_class_diagram]: Unknown provider '{provider}'."

        if not llm_structured_output.strip():
            return "Error [uml_class_diagram]: LLM returned empty structured information."

        parsed_classes, parsed_relationships = parse_llm_class_structure(llm_structured_output)
        if not parsed_classes:
            print(
                f"Warning [uml_class_diagram]: Could not parse ANY class structures from LLM output. The LLM output likely did not follow the expected format (CLASS:, ATTRIBUTES:, METHODS:, ---).",
                file=sys.stderr)
            return "Error [uml_class_diagram]: Failed to parse class structure from LLM output. Check console for LLM's raw structured text."

        dot_source = generate_dot_from_structure(parsed_classes, parsed_relationships)

        # *** Use the target_output_file_base from kwargs if provided by app.py ***
        # This filename is the base path, graphviz.render() will append the .png (or other format)
        target_file_base_for_render = kwargs.get('target_output_file_base', OUTPUT_FILENAME_BASE)
        print(f"DEBUG [uml_class_diagram]: Using target_file_base_for_render: {target_file_base_for_render}",
              file=sys.stderr)

        print(f"Explainer [uml_class_diagram]: Rendering DOT source to image...")
        try:
            output_dir = os.path.dirname(target_file_base_for_render)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                print(f"Created output directory for explainer: {output_dir}", file=sys.stderr)

            # The `filename` parameter to Source is the base for output files.
            # `render` will create `target_file_base_for_render` (dot source) and `target_file_base_for_render.png`
            graph = graphviz.Source(dot_source, filename=target_file_base_for_render, format=OUTPUT_FORMAT,
                                    engine='dot')
            output_path_from_render = graph.render(cleanup=True, view=False)
            # output_path_from_render will be target_file_base_for_render + "." + OUTPUT_FORMAT

            print(
                f"Explainer [uml_class_diagram]: Successfully rendered UML Class Diagram to {output_path_from_render}")
            return f"Success: UML Class Diagram saved to: {output_path_from_render}"  # Return absolute path

        except graphviz.exceptions.ExecutableNotFound:
            return "Error: Graphviz executable not found. Please install Graphviz system-wide."
        except Exception as render_err:
            print(f"Error [uml_class_diagram]: Failed to render DOT source: {render_err}", file=sys.stderr)
            print(f"--- Generated DOT Source Attempted ---\n{dot_source}\n--------------------------", file=sys.stderr)
            return f"Error: Failed to render UML Class Diagram image. Details: {render_err}"

    except Exception as e:
        return f"Error [uml_class_diagram]: Exception during processing: {type(e).__name__}: {e}"

