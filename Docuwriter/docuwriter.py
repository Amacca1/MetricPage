from flask import Blueprint, render_template, request, jsonify
import requests
from dotenv import load_dotenv
import os
import re
import ast
import json

load_dotenv()

docuwriter_bp = Blueprint('docuwriter', __name__, template_folder='templates')

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL")
MODEL = os.getenv("MODEL")
VERSION = os.getenv("VERSION")

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

@docuwriter_bp.route('/')
def index():
    return render_template('writerpage.html')

@docuwriter_bp.route('/filetree')
def filetree():
    repo_root = request.args.get('root') or REPO_ROOT
    tree = []
    ignore_dirs = {'venv', '.venv', '__pycache__', 'tests', 'migrations'}
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        rel_root = os.path.relpath(root, repo_root)
        for file in files:
            if file.endswith('.py') or file.endswith('.html') or file == "README.md":
                tree.append(os.path.join(rel_root, file))
    return jsonify(tree)

@docuwriter_bp.route('/filecontent')
def filecontent():
    repo_root = request.args.get('root') or REPO_ROOT
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    abs_path = os.path.abspath(os.path.join(repo_root, path))
    if not abs_path.startswith(repo_root):
        return jsonify({'error': 'Invalid path'}), 400
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@docuwriter_bp.route('/suggest_doc', methods=['POST'])
def suggest_doc():
    data = request.get_json()
    path = data.get("path")
    code = data.get("code") 

    if not path and not code:
        return jsonify({'error': 'No file path or code provided'}), 400

    if code is None:
        abs_path = os.path.abspath(os.path.join(REPO_ROOT, path))
        if not abs_path.startswith(REPO_ROOT):
            return jsonify({'error': 'Invalid path'}), 400
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    system_prompt = (
        "You are an expert code documentation assistant. "
        "Given the following code, suggest additional docstrings or inline comments "
        "that would improve its clarity and maintainability. "
        "Reply with the suggested documentation lines (as docstrings or comments) within the code, "
        "not with explanations.\n\n"
        f"Code:\n{code}\n"
    )

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": VERSION
    }

    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": code}
        ]
    }

    try:
        response = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        resp_json = response.json()
        suggestion = resp_json["content"][0]["text"]
        resp_json = response.json()
        usage = resp_json.get("usage", {})
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
        print(f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, Total tokens: {total_tokens}")
        return jsonify({"suggestion": suggestion})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@docuwriter_bp.route('/add_doc', methods=['POST'])
def add_doc():
    data = request.get_json()
    path = data.get("path")
    suggestion = data.get("suggestion")

    if not path or not suggestion:
        return jsonify({'error': 'No file path or suggestion provided'}), 400

    abs_path = os.path.abspath(os.path.join(REPO_ROOT, path))
    if not abs_path.startswith(REPO_ROOT):
        return jsonify({'error': 'Invalid path'}), 400

    # Remove suggested start/end markers if present
    suggestion = re.sub(r'# === DOCUWRITER SUGGESTED DOCUMENTATION START ===\n?', '', suggestion)
    suggestion = re.sub(r'# === DOCUWRITER SUGGESTED DOCUMENTATION END ===\n?', '', suggestion)

    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            original = f.read()

        # If Python file and suggestion is a mapping, use advanced placement
        if abs_path.endswith('.py'):
            try:
                # Expecting suggestion as JSON string mapping names to docstrings
                suggestions = json.loads(suggestion)
                updated = insert_docstrings(original, suggestions)
            except Exception:
                updated = suggestion + "\n" + original
        else:
            updated = suggestion + "\n" + original

        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(updated)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@docuwriter_bp.route('/generate_readme', methods=['POST'])
def generate_readme():
    repo_root = request.args.get('root') or REPO_ROOT

    # Gather all code files shown in the filetree
    tree = []
    ignore_dirs = {'venv', '.venv', '__pycache__', 'tests', 'migrations'}
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        rel_root = os.path.relpath(root, REPO_ROOT)
        for file in files:
            if file.endswith('.py') or file.endswith('.html'):
                tree.append(os.path.join(rel_root, file))

    # Read contents of each file (limit total size for API)
    code_snippets = []
    total_chars = 0
    max_chars = 8000  # Limit to avoid API issues
    for path in tree:
        abs_path = os.path.abspath(os.path.join(REPO_ROOT, path))
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
            snippet = f"File: {path}\n{content}\n"
            if total_chars + len(snippet) > max_chars:
                break
            code_snippets.append(snippet)
            total_chars += len(snippet)
        except Exception:
            continue

    # Compose prompt for the API
    prompt = (
        "You are an expert software documentation assistant. "
        "Given the following codebase, write a concise and informative README.md overview. "
        "Summarize the main functionality, structure, and purpose of the code. "
        "Reply ONLY with the README.md content in Markdown format.\n\n"
        + "\n".join(code_snippets)
    )

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": VERSION
    }

    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "system": prompt,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        resp_json = response.json()
        readme_content = resp_json["content"][0]["text"]
        # Write README.md to the selected repo directory
        readme_path = os.path.join(repo_root, "README.md")
        print(f"Writing README to {readme_path}")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)
        return jsonify({"success": True, "readme": readme_content})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@docuwriter_bp.route('/preview_doc', methods=['POST'])
def preview_doc():
    import re
    data = request.get_json()
    path = data.get("path")
    suggestion = data.get("suggestion")

    if not path or not suggestion:
        return jsonify({'error': 'No file path or suggestion provided'}), 400

    repo_root = request.args.get('root') or REPO_ROOT
    abs_path = os.path.abspath(os.path.join(repo_root, path))
    if not abs_path.startswith(repo_root):
        return jsonify({'error': 'Invalid path'}), 400

    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            original = f.read()

        # Highlight block with HTML for preview
        highlighted = (
            "\n<span style='background-color: #ffe066; color: #23272e; display: block; padding: 8px; border-radius: 4px;'>"
            "<b>// DOCUWRITER SUGGESTED DOCUMENTATION START //</b><br>"
            f"{suggestion.replace('\n', '<br>')}"
            "<br><b>// DOCUWRITER SUGGESTED DOCUMENTATION END //</b></span>\n"
        )

        # Insert above first function/class for Python, else prepend
        if abs_path.endswith('.py'):
            match = re.search(r'^(class |def )', original, re.MULTILINE)
            if match:
                idx = match.start()
                preview = original[:idx] + highlighted + original[idx:]
            else:
                preview = highlighted + original
        else:
            preview = highlighted + original

        return jsonify({'preview': preview})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def insert_docstrings(original_code, suggestions):
    """
    original_code: str, the code of the file
    suggestions: dict, mapping function/class names to docstring/comment
    Returns: str, code with inserted docstrings/comments
    """
    try:
        tree = ast.parse(original_code)
        lines = original_code.splitlines()
        # Offset for inserted lines
        offset = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                name = node.name
                if name in suggestions:
                    # Insert after the definition line
                    def_line = node.lineno - 1 + offset
                    docstring = suggestions[name]
                    # Insert as a docstring (for Python)
                    lines.insert(def_line + 1, f'    """{docstring}"""')
                    offset += 1
        return "\n".join(lines)
    except Exception as e:
        # Fallback: just prepend all suggestions
        all_docs = "\n".join([f"# {v}" for v in suggestions.values()])
        return f"{all_docs}\n{original_code}"

def extract_function_code(code, name):
    import ast
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = node.lineno - 1
            end = node.end_lineno if hasattr(node, 'end_lineno') else start + 1
            return '\n'.join(code.splitlines()[start:end])
    return ""