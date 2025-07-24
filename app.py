from flask import Flask, render_template, request, jsonify
import requests
import os
import tempfile
import subprocess
from dotenv import load_dotenv
import ast

load_dotenv()
app = Flask(__name__)

GITHUB_API = "https://api.github.com"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL")
MODEL = os.getenv("MODEL")
VERSION = os.getenv("VERSION")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/repos')
def list_repos():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'No username provided'}), 400
    r = requests.get(f"{GITHUB_API}/users/{username}/repos")
    if r.status_code != 200:
        return jsonify({'error': 'GitHub error'}), 500
    repos = [repo['name'] for repo in r.json()]
    return jsonify({'repos': repos})

@app.route('/repo_files')
def repo_files():
    username = request.args.get('username')
    repo = request.args.get('repo')
    if not username or not repo:
        return jsonify({'error': 'Missing params'}), 400
    r = requests.get(f"{GITHUB_API}/repos/{username}/{repo}/contents")
    if r.status_code != 200:
        return jsonify({'error': 'GitHub error'}), 500
    py_files = [f['path'] for f in r.json() if f['name'].endswith('.py')]
    return jsonify({'files': py_files})

@app.route('/file_content')
def file_content():
    username = request.args.get('username')
    repo = request.args.get('repo')
    path = request.args.get('path')
    if not username or not repo or not path:
        return jsonify({'error': 'Missing params'}), 400
    r = requests.get(f"{GITHUB_API}/repos/{username}/{repo}/contents/{path}")
    if r.status_code != 200:
        return jsonify({'error': 'GitHub error'}), 500
    import base64
    content = base64.b64decode(r.json()['content']).decode('utf-8')
    return jsonify({'content': content})

def extract_functions(code):
    tree = ast.parse(code)
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]

def call_claude(function_code):
    # Call Claude API to generate tests for the function
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": VERSION,
        "anthropic-model": MODEL,
        "content-type": "application/json"
    }
    prompt = (
        "Write a logical, non-trivial pytest test function for the following Python function. "
        "Do not simply echo the function or use trivial asserts. include all necessary imports. "
        "The test should cover edge cases and be well-structured. "
        "Only return the test code, nothing else.\n\n"
        f"{function_code}"
    )
    data = {
        "model": MODEL,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post(url, headers=headers, json=data)
    if r.status_code != 200:
        return "# Claude API error"
    return r.json()['content'][0]['text']

@app.route('/generate_tests', methods=['POST'])
def generate_tests():
    import re
    data = request.json
    code = data.get('code')
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    functions = extract_functions(code)
    tests = []
    for func in functions:
        func_code = ast.unparse(func)
        test_code = call_claude(func_code)
        # Remove markdown/code block formatting and non-code text
        test_code = re.sub(r"^```python|^```|```$", "", test_code, flags=re.MULTILINE).strip()
        # Ensure import pytest is present
        if "import pytest" not in test_code:
            test_code = "import pytest\n" + test_code
        tests.append({'function': func.name, 'test_code': test_code})
    return jsonify({'tests': tests})

@app.route('/run_test', methods=['POST'])
def run_test():
    data = request.json
    code = data.get('code')
    test_code = data.get('test_code')
    if not code or not test_code:
        return jsonify({'error': 'Missing code or test_code'}), 400
    with tempfile.TemporaryDirectory() as tmpdir:
        code_path = os.path.join(tmpdir, "module.py")
        test_path = os.path.join(tmpdir, "test_module.py")
        with open(code_path, "w") as f:
            f.write(code)
        with open(test_path, "w") as f:
            f.write("import module\n" + test_code)
        try:
            result = subprocess.run(
                ["pytest", test_path, "-v", "--tb=short", "--disable-warnings"],
                cwd=tmpdir,
                capture_output=True,
                timeout=10
            )
            output = result.stdout.decode() + result.stderr.decode()
        except Exception as e:
            output = str(e)
    return jsonify({'output': output})

if __name__ == '__main__':
    app.run(debug=True)