from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv
import os

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
    for root, dirs, files in os.walk(REPO_ROOT):
        rel_root = os.path.relpath(root, REPO_ROOT)
        for file in files:
            if file.startswith('.'):
                continue
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
    code = data.get("code")  # Optionally, just a snippet

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
        "messages": []
    }

    try:
        response = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        suggestion = resp_json["content"][0]["text"]
        resp_json = response.json()
        usage = resp_json.get("usage", {})
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
        return jsonify({"suggestion": suggestion})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)