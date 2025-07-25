from flask import Blueprint, render_template, request, jsonify
import requests
import os
import tempfile
import subprocess
from dotenv import load_dotenv
import ast
import re

load_dotenv()
tester_bp = Blueprint('tester', __name__, template_folder='templates')

GITHUB_API = "https://api.github.com"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL")
MODEL = os.getenv("MODEL")
VERSION = os.getenv("VERSION")

@tester_bp.route('/')
def index():
    return render_template('index.html')

@tester_bp.route('/repos')
def list_repos():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'No username provided'}), 400
    r = requests.get(f"{GITHUB_API}/users/{username}/repos")
    if r.status_code != 200:
        return jsonify({'error': 'GitHub error'}), 500
    repos = [repo['name'] for repo in r.json()]
    return jsonify({'repos': repos})

@tester_bp.route('/branches')
def list_branches():
    username = request.args.get('username')
    repo = request.args.get('repo')
    if not username or not repo:
        return jsonify({'error': 'Missing params'}), 400
    r = requests.get(f"{GITHUB_API}/repos/{username}/{repo}/branches")
    if r.status_code != 200:
        return jsonify({'error': 'GitHub error'}), 500
    branches = [b['name'] for b in r.json()]
    return jsonify({'branches': branches})

@tester_bp.route('/repo_files')
def repo_files():
    username = request.args.get('username')
    repo = request.args.get('repo')
    branch = request.args.get('branch', 'main')
    if not username or not repo:
        return jsonify({'error': 'Missing params'}), 400
    r = requests.get(f"{GITHUB_API}/repos/{username}/{repo}/contents", params={'ref': branch})
    if r.status_code != 200:
        return jsonify({'error': 'GitHub error'}), 500
    py_files = [f['path'] for f in r.json() if f['name'].endswith('.py')]
    return jsonify({'files': py_files})

@tester_bp.route('/file_content')
def file_content():
    username = request.args.get('username')
    repo = request.args.get('repo')
    path = request.args.get('path')
    branch = request.args.get('branch', 'main')
    if not username or not repo or not path:
        return jsonify({'error': 'Missing params'}), 400
    r = requests.get(f"{GITHUB_API}/repos/{username}/{repo}/contents/{path}", params={'ref': branch})
    if r.status_code != 200:
        return jsonify({'error': 'GitHub error'}), 500
    import base64
    content = base64.b64decode(r.json()['content']).decode('utf-8')
    return jsonify({'content': content})

def extract_functions(code):
    tree = ast.parse(code)
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]

def call_claude(function_code,prompt):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": VERSION,
        "anthropic-model": MODEL,
        "content-type": "application/json"
    }
    prompt = (
        "Given the following Python function, write a logical, non-trivial pytest test function for it. "
        "Do not simply echo the function or use trivial asserts. "
        "Include all necessary imports. "
        "IMPORTANT: At the top of your test code, add 'from module import {func_name}'. "
        "Only call the function by its correct name. "
        "Only return the test code, nothing else.\n\n"
        f"{function_code}"
    )
    data = {
        "model": MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post(url, headers=headers, json=data)
    if r.status_code != 200:
        return "# Claude API error", 0, 0
    response = r.json()
    response_text = response['content'][0]['text']

    # Use exact token counts from API response
    usage = response.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    return response_text, input_tokens, output_tokens

@tester_bp.route('/generate_tests', methods=['POST'])
def generate_tests():
    data = request.json
    code = data.get('code')
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    functions = extract_functions(code)
    tests = []
    for func in functions:
        func_code = ast.unparse(func)
        prompt = (
            "Given the following Python function, write a logical, non-trivial pytest test function for it. "
            "Do not simply echo the function or use trivial asserts. "
            "Include all necessary imports. "
            f"IMPORTANT: At the top of your test code, add 'from module import {func.name}'. "
            "Only call the function by its correct name. "
            "Only return the test code, nothing else.\n\n"
            f"{func_code}"
        )
        test_code, input_tokens, output_tokens = call_claude(func_code, prompt)
        # Remove markdown/code block formatting and non-code text
        test_code = re.sub(r"^```python|^```|```$", "", test_code, flags=re.MULTILINE).strip()
        # Ensure import pytest is present
        if "import pytest" not in test_code:
            test_code = "import pytest\n" + test_code
        tests.append({
            'function': func.name,
            'function_code': func_code,
            'test_code': test_code,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens
        })
    return jsonify({'tests': tests})

@tester_bp.route('/run_test', methods=['POST'])
def run_test():
    data = request.json
    code = data.get('code')
    test_code = data.get('test_code')
    if not code or not test_code:
        return jsonify({'error': 'Missing code or test_code'}), 400

    # Validate test_code syntax before running
    try:
        compile(test_code, "<test_code>", "exec")
    except SyntaxError as e:
        return jsonify({'output': f"SyntaxError in generated test code: {e}"}), 200

    import tempfile, os, subprocess
    with tempfile.TemporaryDirectory() as tmpdir:
        code_path = os.path.join(tmpdir, "module.py")
        test_path = os.path.join(tmpdir, "test_module.py")
        with open(code_path, "w") as f:
            f.write(code)
        with open(test_path, "w") as f:
            f.write("import module\n" + test_code)

        # --- MOCK FILE CREATION LOGIC ---
        # Look for open("filename", ...) or open('filename', ...)
        file_matches = re.findall(r'open\(["\']([^"\']+)["\']', test_code)
        for filename in set(file_matches):
            # Only create files with safe names (no directories)
            if os.path.sep not in filename and filename not in ("module.py", "test_module.py"):
                file_path = os.path.join(tmpdir, filename)
                with open(file_path, "w") as mockf:
                    mockf.write("dummy content\n")
        # --- END MOCK FILE CREATION ---

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