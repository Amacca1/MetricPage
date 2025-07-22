from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv
import os
import re

load_dotenv()

app = Flask(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL")
MODEL = os.getenv("MODEL")
VERSION = os.getenv("VERSION")

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/filetree')
def filetree():
    tree = []
    ignore_dirs = {'venv', '.venv', '__pycache__', 'tests', 'migrations'}
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        rel_root = os.path.relpath(root, REPO_ROOT)
        for file in files:
            if file.endswith('.py') or file.endswith('.html') or file == "README.md":
                tree.append(os.path.join(rel_root, file))
    return jsonify(tree)

@app.route('/filecontent')
def filecontent():
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    abs_path = os.path.abspath(os.path.join(REPO_ROOT, path))
    if not abs_path.startswith(REPO_ROOT):
        return jsonify({'error': 'Invalid path'}), 400
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/suggest_doc', methods=['POST'])
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
        "Reply ONLY with the suggested documentation lines (as docstrings or comments), "
        "not with explanations or code repeats.\n\n"
        f"Code:\n{code}\n"
    )

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": VERSION
    }

    payload = {
        "model": MODEL,
        "max_tokens": 512,
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
        return jsonify({"suggestion": suggestion})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/add_doc', methods=['POST'])
def add_doc():
    data = request.get_json()
    path = data.get("path")
    suggestion = data.get("suggestion")

    if not path or not suggestion:
        return jsonify({'error': 'No file path or suggestion provided'}), 400

    abs_path = os.path.abspath(os.path.join(REPO_ROOT, path))
    if not abs_path.startswith(REPO_ROOT):
        return jsonify({'error': 'Invalid path'}), 400

    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            original = f.read()

        # Highlight the documentation block
        highlighted = (
            "\n# === DOCUWRITER SUGGESTED DOCUMENTATION START ===\n"
            f"{suggestion}\n"
            "# === DOCUWRITER SUGGESTED DOCUMENTATION END ===\n"
        )

        # Find first function or class definition for Python files
        if abs_path.endswith('.py'):
            match = re.search(r'^(class |def )', original, re.MULTILINE)
            if match:
                idx = match.start()
                updated = original[:idx] + highlighted + original[idx:]
            else:
                updated = highlighted + original
        else:
            # For other files, just prepend
            updated = highlighted + original

        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(updated)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate_readme', methods=['POST'])
def generate_readme():
    # Gather all code files shown in the filetree
    tree = []
    ignore_dirs = {'venv', '.venv', '__pycache__', 'tests', 'migrations'}
    for root, dirs, files in os.walk(REPO_ROOT):
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
        # Write README.md
        readme_path = os.path.join(REPO_ROOT, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)
        # Add README.md to git
        os.system(f'git add "{readme_path}"')
        os.system('git commit -m "Add/update README.md generated by Docuwriter"')
        return jsonify({"success": True, "readme": readme_content})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)