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
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL")
MODEL = os.getenv("MODEL")
VERSION = os.getenv("VERSION")

def get_github_headers():
    """Get headers for GitHub API requests with authentication"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "MetricPage-TestBot/1.0"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    else:
        print("Warning: GITHUB_TOKEN not found in environment variables")
    return headers

def validate_github_params(username, repo=None):
    """Validate GitHub username and repository name format"""
    import re
    
    # Basic username validation (GitHub allows alphanumeric, hyphens, but not starting/ending with hyphen)
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$', username):
        return False, f"Invalid username format: {username}"
    
    if repo:
        # Basic repo validation (similar to username but allows dots)
        if not re.match(r'^[a-zA-Z0-9._-]+$', repo):
            return False, f"Invalid repository name format: {repo}"
    
    return True, "Valid"

@tester_bp.route('/')
def index():
    return render_template('testpage.html')

@tester_bp.route('/repos')
def list_repos():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'No username provided'}), 400
    
    headers = get_github_headers()
    try:
        r = requests.get(f"{GITHUB_API}/users/{username}/repos", headers=headers)
        if r.status_code == 404:
            return jsonify({'error': f'User "{username}" not found'}), 404
        elif r.status_code == 403:
            return jsonify({'error': 'GitHub API rate limit exceeded or insufficient permissions'}), 403
        elif r.status_code != 200:
            error_msg = f'GitHub API error: {r.status_code}'
            try:
                error_detail = r.json().get('message', 'Unknown error')
                error_msg += f' - {error_detail}'
            except:
                pass
            return jsonify({'error': error_msg}), 500
        
        repos = [repo['name'] for repo in r.json()]
        return jsonify({'repos': repos})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Network error: {str(e)}'}), 500

@tester_bp.route('/branches')
def list_branches():
    username = request.args.get('username')
    repo = request.args.get('repo')
    if not username or not repo:
        return jsonify({'error': 'Missing username or repo parameter'}), 400
    
    headers = get_github_headers()
    try:
        r = requests.get(f"{GITHUB_API}/repos/{username}/{repo}/branches", headers=headers)
        if r.status_code == 404:
            return jsonify({'error': f'Repository "{username}/{repo}" not found'}), 404
        elif r.status_code == 403:
            return jsonify({'error': 'GitHub API rate limit exceeded or insufficient permissions'}), 403
        elif r.status_code != 200:
            error_msg = f'GitHub API error: {r.status_code}'
            try:
                error_detail = r.json().get('message', 'Unknown error')
                error_msg += f' - {error_detail}'
            except:
                pass
            return jsonify({'error': error_msg}), 500
        
        branches = [b['name'] for b in r.json()]
        return jsonify({'branches': branches})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Network error: {str(e)}'}), 500

@tester_bp.route('/repo_files')
def repo_files():
    username = request.args.get('username')
    repo = request.args.get('repo')
    branch = request.args.get('branch', 'main')
    if not username or not repo:
        return jsonify({'error': 'Missing username or repo parameter'}), 400
    
    headers = get_github_headers()
    try:
        r = requests.get(f"{GITHUB_API}/repos/{username}/{repo}/contents", 
                        headers=headers, params={'ref': branch})
        if r.status_code == 404:
            return jsonify({'error': f'Repository "{username}/{repo}" or branch "{branch}" not found'}), 404
        elif r.status_code == 403:
            return jsonify({'error': 'GitHub API rate limit exceeded or insufficient permissions'}), 403
        elif r.status_code != 200:
            error_msg = f'GitHub API error: {r.status_code}'
            try:
                error_detail = r.json().get('message', 'Unknown error')
                error_msg += f' - {error_detail}'
            except:
                pass
            return jsonify({'error': error_msg}), 500
        
        py_files = [f['path'] for f in r.json() if f['name'].endswith('.py')]
        return jsonify({'files': py_files})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Network error: {str(e)}'}), 500

@tester_bp.route('/file_content')
def file_content():
    username = request.args.get('username')
    repo = request.args.get('repo')
    path = request.args.get('path')
    branch = request.args.get('branch', 'main')
    if not username or not repo or not path:
        return jsonify({'error': 'Missing username, repo, or path parameter'}), 400
    
    headers = get_github_headers()
    try:
        r = requests.get(f"{GITHUB_API}/repos/{username}/{repo}/contents/{path}", 
                        headers=headers, params={'ref': branch})
        if r.status_code == 404:
            return jsonify({'error': f'File "{path}" not found in repository "{username}/{repo}" on branch "{branch}"'}), 404
        elif r.status_code == 403:
            return jsonify({'error': 'GitHub API rate limit exceeded or insufficient permissions'}), 403
        elif r.status_code != 200:
            error_msg = f'GitHub API error: {r.status_code}'
            try:
                error_detail = r.json().get('message', 'Unknown error')
                error_msg += f' - {error_detail}'
            except:
                pass
            return jsonify({'error': error_msg}), 500
        
        import base64
        content = base64.b64decode(r.json()['content']).decode('utf-8')
        return jsonify({'content': content})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Network error: {str(e)}'}), 500

def extract_functions(code):
    tree = ast.parse(code)
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]

def call_claude(function_code, prompt):
    """Call Claude API to generate test code"""
    if not ANTHROPIC_API_KEY:
        return "# Error: Anthropic API key not configured", 0, 0
    
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    full_prompt = (
        "Given the following Python function, write a logical, non-trivial pytest test function for it. "
        "Do not simply echo the function or use trivial asserts. "
        "Include all necessary imports. "
        "IMPORTANT: At the top of your test code, add 'from module import {func_name}'. "
        "Only call the function by its correct name. "
        "Only return the test code, nothing else.\n\n"
        f"{function_code}"
    )
    
    data = {
        "model": MODEL or "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": full_prompt}]
    }
    
    try:
        r = requests.post(url, headers=headers, json=data, timeout=30)
        if r.status_code != 200:
            error_msg = f"Claude API error: {r.status_code}"
            try:
                error_detail = r.json().get('error', {}).get('message', 'Unknown error')
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {r.text}"
            return f"# {error_msg}", 0, 0
            
        response = r.json()
        
        # Extract content from response
        if 'content' in response and len(response['content']) > 0:
            response_text = response['content'][0]['text']
        else:
            return "# Error: No content in Claude response", 0, 0

        # Use exact token counts from API response
        usage = response.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        return response_text, input_tokens, output_tokens
        
    except requests.exceptions.RequestException as e:
        return f"# Network error calling Claude API: {str(e)}", 0, 0
    except Exception as e:
        return f"# Error processing Claude response: {str(e)}", 0, 0

@tester_bp.route('/generate_tests', methods=['POST'])
def generate_tests():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        code = data.get('code')
        if not code:
            return jsonify({'error': 'No code provided'}), 400
            
        # Parse the code to extract functions
        try:
            functions = extract_functions(code)
        except SyntaxError as e:
            return jsonify({'error': f'Syntax error in provided code: {str(e)}'}), 400
        except Exception as e:
            return jsonify({'error': f'Error parsing code: {str(e)}'}), 400
            
        if not functions:
            return jsonify({'error': 'No functions found in the provided code'}), 400
            
        tests = []
        for func in functions:
            try:
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
            except Exception as e:
                # Continue with other functions if one fails
                tests.append({
                    'function': func.name,
                    'function_code': ast.unparse(func) if hasattr(ast, 'unparse') else str(func),
                    'test_code': f"# Error generating test for {func.name}: {str(e)}",
                    'input_tokens': 0,
                    'output_tokens': 0
                })
                
        return jsonify({'tests': tests})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

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