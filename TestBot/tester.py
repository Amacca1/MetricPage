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

def extract_dependencies(code):
    """Extract all dependencies that need to be imported from the module being tested"""
    dependencies = set()
    
    # Parse the code to find all names being used
    try:
        tree = ast.parse(code)
        
        # Walk through all nodes to find function calls and module-level references
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Handle function calls like get_github_headers()
                if isinstance(node.func, ast.Name):
                    # Only include functions that look like module-level functions
                    func_name = node.func.id
                    if func_name not in ['get', 'json', 'split', 'append', 'update', 'add', 'remove']:
                        dependencies.add(func_name)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                # Handle variable references - focus on UPPERCASE constants and specific patterns
                name = node.id
                if (name.isupper() and len(name) > 2) or name in ['request', 'jsonify', 'render_template']:
                    dependencies.add(name)
    
    except Exception:
        # If parsing fails, fall back to regex patterns for key dependencies
        import re
        
        # Find function calls that look like module functions
        func_calls = re.findall(r'(\w+)\s*\(', code)
        for func in func_calls:
            if func not in ['get', 'json', 'split', 'append', 'update', 'add', 'remove', 'len', 'str', 'int'] and not func.startswith('_'):
                dependencies.add(func)
        
        # Find uppercase constants
        constants = re.findall(r'\b([A-Z_][A-Z0-9_]{2,})\b', code)
        dependencies.update(constants)
        
        # Find specific Flask/module patterns
        flask_patterns = re.findall(r'\b(request|jsonify|render_template|Blueprint)\b', code)
        dependencies.update(flask_patterns)
    
    # Filter out common Python builtins, keywords, and local variables
    builtins_and_keywords = {
        'def', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'finally',
        'return', 'yield', 'import', 'from', 'as', 'class', 'pass', 'break',
        'continue', 'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is',
        'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'bool',
        'print', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted',
        'max', 'min', 'sum', 'abs', 'all', 'any', 'isinstance', 'hasattr',
        'getattr', 'setattr', 'type', 'super', 'property', 'staticmethod',
        'classmethod', 'open', 'file', 'Exception', 'ValueError', 'TypeError',
        'KeyError', 'IndexError', 'AttributeError', 'get', 'json', 'status_code',
        # Common local variable names to exclude
        'e', 'r', 'response', 'result', 'data', 'content', 'headers', 'params',
        'error_msg', 'error_detail', 'username', 'repo', 'repos', 'branches',
        'files', 'path', 'branch'
    }
    
    # Remove builtins, keywords, and common local variables
    dependencies = {dep for dep in dependencies if dep not in builtins_and_keywords}
    
    # Only keep likely module-level dependencies
    filtered_deps = set()
    for dep in dependencies:
        # Keep uppercase constants, specific Flask functions, and module-style function names
        if (dep.isupper() and len(dep) > 2) or \
           dep in ['request', 'jsonify', 'render_template'] or \
           (dep.startswith('get_') and len(dep) > 4) or \
           (dep.endswith('_bp') and len(dep) > 3) or \
           dep in ['Blueprint', 'requests']:
            filtered_deps.add(dep)
    
    return sorted(list(filtered_deps))

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
    
    # Detect if this is a Flask route function by checking for Flask imports or decorators
    is_flask_function = (
        'from flask import' in function_code or
        'import flask' in function_code or
        '@' in function_code and ('route' in function_code or 'bp.route' in function_code) or
        'render_template' in function_code or
        'request.' in function_code or
        'jsonify' in function_code
    )
    
    if is_flask_function:
        # Extract all dependencies from the function code
        dependencies = extract_dependencies(function_code)
        deps_import = ", ".join(dependencies) if dependencies else "function_name"
        
        full_prompt = (
            "Given the following Flask route function, write comprehensive pytest test functions for it. "
            "CRITICAL FLASK TESTING REQUIREMENTS: "
            "1. ALWAYS create a proper Flask application instance with ALL BLUEPRINTS registered "
            "2. Import all requirements to test the generated code: Ie All imported modules in the orignal code being tested"
            "3. Use the client fixture in all route tests: def test_route(client): "
            "4. Mock external dependencies (requests, API calls, etc.) using unittest.mock.patch "
            "5. For render_template calls, mock them to avoid template dependencies "
            "6. Test both success and error scenarios including 404, 500, etc. "
            f"7. Include proper import statement: 'from module import {deps_import}' "
            "8. Import ALL dependencies used in the function from the module "
            "9. Return ONLY the test code, no explanations "
            "10. Use only double quotes (\") for strings, never apostrophes (') "
            "11. Test route endpoints with proper URL paths including blueprint prefixes "
            "12. Mock any external functions or constants used (like get_github_headers, GITHUB_API, etc.) "
            "\n\n"
            "Example Flask route test pattern:\n"
            "```python\n"
            "import pytest\n"
            "from unittest.mock import patch, Mock\n"
            f"from module import {deps_import}\n"
            "\n"
            "@pytest.fixture\n"
            "def app():\n"
            "    # Flask app setup with blueprints as shown above\n"
            "    pass\n"
            "\n"
            "@pytest.fixture\n"
            "def client(app):\n"
            "    return app.test_client()\n"
            "\n"
            "def test_route_success(client):\n"
            "    with patch('module.external_dependency') as mock_dep:\n"
            "        mock_dep.return_value = 'test_data'\n"
            "        response = client.get('/prefix/route')\n"
            "        assert response.status_code == 200\n"
            "        assert response.get_json()['data'] == 'expected'\n"
            "```\n\n"
            f"Function to test:\n{function_code}"
        )
    else:
        # Extract dependencies for non-Flask functions too
        dependencies = extract_dependencies(function_code)
        deps_import = ", ".join(dependencies) if dependencies else "function_name"
        
        full_prompt = (
            "Given the following Python function, write comprehensive pytest test functions for it. "
            "Guidelines: "
            "1. Test different input scenarios (valid, invalid, edge cases) "
            "2. Test return values and side effects "
            "3. Mock external dependencies if any "
            "4. Include proper assertions "
            f"5. Add 'from module import {deps_import}' at the top "
            "6. Return only the test code, no explanations "
            "7. For render_template calls, mock them to avoid template dependencies"
            "8. Mock any external functions or constants used in the function"
            "\n\n"
            f"Function to test:\n{function_code}"
        )
    
    data = {
        "model": MODEL or "claude-3-5-sonnet-20241022",
        "max_tokens": 1536,
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
                # Extract dependencies for this specific function
                func_dependencies = extract_dependencies(func_code)
                # Always include the function name itself
                func_dependencies.append(func.name)
                
                # Let call_claude handle the prompt generation with Flask detection
                test_code, input_tokens, output_tokens = call_claude(func_code, None)
                
                # Remove markdown/code block formatting and non-code text
                test_code = re.sub(r"^```python|^```|```$", "", test_code, flags=re.MULTILINE).strip()
                
                # Ensure import pytest is present
                if "import pytest" not in test_code:
                    test_code = "import pytest\n" + test_code
                
                # Ensure unittest.mock imports are present if patch is used
                if "patch(" in test_code and "from unittest.mock import" not in test_code:
                    # Add mock import after pytest import
                    test_code = test_code.replace("import pytest", "import pytest\nfrom unittest.mock import patch, Mock")
                elif "patch(" in test_code and "patch" not in test_code:
                    # Add patch to existing mock import
                    test_code = re.sub(r'from unittest\.mock import ([^\\n]+)', r'from unittest.mock import \1, patch', test_code)
                
                # Fix import statements to use 'module' consistently
                # Replace various import patterns
                test_code = re.sub(r'from\s+(?:app|your_module|my_module|test_module|main|\w+_module|\w+\.py|calculator|tester|chatbot|docuwriter|logger)\s+import', 'from module import', test_code)
                test_code = re.sub(r'patch\(["\'](?:app|your_module|my_module|test_module|main|\w+_module|\w+\.py|calculator)\.', 'patch("module.', test_code)
                # Handle standalone module references in patches
                test_code = re.sub(r'patch\(["\'](?:app|your_module|my_module|test_module|main|calculator)(["\'])', r'patch("module\1', test_code)
                
                # Remove duplicate imports and clean up any remaining bad imports
                test_code = re.sub(r'from\s+\w+\.\w+\s+import\s+[^\n]+\n', '', test_code)
                test_code = re.sub(r'from\s+(?:calculator|tester|chatbot|docuwriter|logger)\s+import\s+[^\n]+\n', '', test_code)
                
                # Check if this is a Flask function and ensure fixtures are present
                is_flask_function = (
                    '@' in func_code and ('route' in func_code or 'bp.route' in func_code) or
                    'client' in test_code
                )
                
                if is_flask_function:
                    # Ensure Flask fixtures are present
                    if '@pytest.fixture' not in test_code or 'def app():' not in test_code:
                        # Add Flask fixtures at the beginning of test functions
                        fixture_code = '''
@pytest.fixture
def app():
    from flask import Flask
    from ChatBot.chatbot import chatbot_bp
    from AgentLogger.log import logger_bp
    from Docuwriter.docuwriter import docuwriter_bp
    from TestBot.tester import tester_bp
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
    app.register_blueprint(logger_bp, url_prefix='/logger')
    app.register_blueprint(docuwriter_bp, url_prefix='/writer')
    app.register_blueprint(tester_bp, url_prefix='/tester')
    return app

@pytest.fixture
def client(app):
    return app.test_client()

'''
                        # Insert fixtures after imports
                        lines = test_code.split('\n')
                        insert_pos = 0
                        for i, line in enumerate(lines):
                            if line.strip().startswith('import ') or line.strip().startswith('from '):
                                insert_pos = i + 1
                            elif line.strip() and not line.strip().startswith('#'):
                                break
                        lines.insert(insert_pos, fixture_code)
                        test_code = '\n'.join(lines)
                
                # Remove duplicate imports (e.g., from TestBot.tester import ...)
                test_code = re.sub(r'from\s+\w+\.\w+\s+import\s+[^\n]+\n', '', test_code)
                
                # Check if this is a Flask function and ensure fixtures are present
                is_flask_function = (
                    '@' in func_code and ('route' in func_code or 'bp.route' in func_code) or
                    'client' in test_code
                )
                
                if is_flask_function:
                    # Ensure Flask fixtures are present
                    if '@pytest.fixture' not in test_code or 'def app():' not in test_code:
                        # Add Flask fixtures at the beginning of test functions
                        fixture_code = '''
@pytest.fixture
def app():
    from flask import Flask
    from ChatBot.chatbot import chatbot_bp
    from AgentLogger.log import logger_bp
    from Docuwriter.docuwriter import docuwriter_bp
    from TestBot.tester import tester_bp
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
    app.register_blueprint(logger_bp, url_prefix='/logger')
    app.register_blueprint(docuwriter_bp, url_prefix='/writer')
    app.register_blueprint(tester_bp, url_prefix='/tester')
    return app

@pytest.fixture
def client(app):
    return app.test_client()

'''
                        # Insert fixtures after imports
                        lines = test_code.split('\n')
                        insert_pos = 0
                        for i, line in enumerate(lines):
                            if line.strip().startswith('import ') or line.strip().startswith('from '):
                                insert_pos = i + 1
                            elif line.strip() and not line.strip().startswith('#'):
                                break
                        lines.insert(insert_pos, fixture_code)
                        test_code = '\n'.join(lines)
                
                # Ensure all function dependencies are included in the import
                if func_dependencies:
                    # Check if there's already a 'from module import' line
                    import_match = re.search(r'from module import (.+)', test_code)
                    if import_match:
                        current_imports = set(item.strip() for item in import_match.group(1).split(','))
                        all_imports = current_imports.union(set(func_dependencies))
                        new_import_line = f"from module import {', '.join(sorted(all_imports))}"
                        test_code = re.sub(r'from module import .+', new_import_line, test_code)
                    else:
                        # Add the import line if it doesn't exist
                        import_line = f"from module import {', '.join(sorted(func_dependencies))}"
                        # Insert after other imports
                        lines = test_code.split('\n')
                        insert_pos = 0
                        for i, line in enumerate(lines):
                            if line.strip().startswith('import ') or line.strip().startswith('from '):
                                insert_pos = i + 1
                            else:
                                break
                        lines.insert(insert_pos, import_line)
                        test_code = '\n'.join(lines)
                    
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

def analyze_test_failure(test_output, test_code, original_code):
    """Analyze test failure output and provide suggestions for fixing"""
    failure_analysis = {
        'error_type': 'unknown',
        'error_message': '',
        'suggested_fixes': [],
        'needs_regeneration': False
    }
    
    # Common error patterns and their fixes
    if 'ImportError' in test_output or 'ModuleNotFoundError' in test_output:
        failure_analysis['error_type'] = 'import_error'
        failure_analysis['error_message'] = 'Missing imports or module dependencies'
        failure_analysis['suggested_fixes'] = [
            'Add missing imports from module',
            'Check dependency extraction',
            'Ensure all used functions are imported'
        ]
        failure_analysis['needs_regeneration'] = True
        
    elif 'NameError' in test_output:
        failure_analysis['error_type'] = 'name_error'
        failure_analysis['error_message'] = 'Undefined variable or function'
        failure_analysis['suggested_fixes'] = [
            'Import missing functions/variables',
            'Add proper mocking for undefined names',
            'Check function and variable names'
        ]
        failure_analysis['needs_regeneration'] = True
        
    elif 'AttributeError' in test_output:
        failure_analysis['error_type'] = 'attribute_error'
        failure_analysis['error_message'] = 'Missing attribute or method'
        failure_analysis['suggested_fixes'] = [
            'Mock missing attributes',
            'Check object structure',
            'Add proper fixture setup'
        ]
        failure_analysis['needs_regeneration'] = True
        
    elif 'SyntaxError' in test_output:
        failure_analysis['error_type'] = 'syntax_error'
        failure_analysis['error_message'] = 'Invalid Python syntax'
        failure_analysis['suggested_fixes'] = [
            'Fix syntax errors',
            'Check indentation',
            'Validate generated code structure'
        ]
        failure_analysis['needs_regeneration'] = True
        
    elif 'AssertionError' in test_output:
        failure_analysis['error_type'] = 'assertion_error'
        failure_analysis['error_message'] = 'Test assertion failed'
        failure_analysis['suggested_fixes'] = [
            'Update expected values',
            'Fix mock return values',
            'Adjust test logic'
        ]
        failure_analysis['needs_regeneration'] = False
        
    elif 'fixture' in test_output.lower() and ('not found' in test_output.lower() or 'error' in test_output.lower()):
        failure_analysis['error_type'] = 'fixture_error'
        failure_analysis['error_message'] = 'Missing or invalid pytest fixtures'
        failure_analysis['suggested_fixes'] = [
            'Add missing Flask fixtures',
            'Fix fixture dependencies',
            'Ensure proper fixture setup'
        ]
        failure_analysis['needs_regeneration'] = True
        
    elif 'ConnectionError' in test_output or 'requests' in test_output:
        failure_analysis['error_type'] = 'mock_error'
        failure_analysis['error_message'] = 'External dependencies not properly mocked'
        failure_analysis['suggested_fixes'] = [
            'Add proper mocking for requests',
            'Mock external API calls',
            'Isolate external dependencies'
        ]
        failure_analysis['needs_regeneration'] = True
    
    return failure_analysis

def generate_improved_test(function_code, original_test_code, failure_analysis, attempt_number):
    """Generate improved test code based on failure analysis"""
    
    if not ANTHROPIC_API_KEY:
        return "# Error: Anthropic API key not configured", 0, 0
    
    # Extract dependencies and function name
    dependencies = extract_dependencies(function_code)
    
    # Create enhanced prompt based on failure analysis
    improvement_prompt = f"""
You are a expert test engineer. The previous test attempt failed with the following analysis:

ERROR TYPE: {failure_analysis['error_type']}
ERROR MESSAGE: {failure_analysis['error_message']}
SUGGESTED FIXES: {', '.join(failure_analysis['suggested_fixes'])}

ATTEMPT NUMBER: {attempt_number}/3

CRITICAL REQUIREMENTS FOR THIS ITERATION:
1. MUST include ALL necessary imports from module: {', '.join(dependencies) if dependencies else 'function_name'}
2. MUST include proper Flask fixtures with ALL blueprints registered
3. MUST use comprehensive mocking for ALL external dependencies
4. MUST handle all edge cases and error scenarios
5. MUST use proper pytest syntax and structure
6. MUST mock requests, API calls, and external functions
7. MUST ensure all variables and functions are properly defined

PREVIOUS FAILING TEST CODE:
```python
{original_test_code}
```

FUNCTION TO TEST:
```python
{function_code}
```

Generate a CORRECTED and IMPROVED test that addresses the specific failure. Include:
- Complete Flask app setup with all blueprints
- All necessary imports from module
- Comprehensive mocking of external dependencies
- Proper error handling and edge case testing
- Valid pytest syntax and structure

Return ONLY the corrected Python test code, no explanations.
"""

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    data = {
        "model": MODEL or "claude-3-5-sonnet-20241022",
        "max_tokens": 2000,  # Increased for more comprehensive fixes
        "messages": [{"role": "user", "content": improvement_prompt}]
    }
    
    try:
        r = requests.post(url, headers=headers, json=data, timeout=45)
        if r.status_code != 200:
            error_msg = f"Claude API error: {r.status_code}"
            try:
                error_detail = r.json().get('error', {}).get('message', 'Unknown error')
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {r.text}"
            return f"# {error_msg}", 0, 0
            
        response = r.json()
        
        if 'content' in response and len(response['content']) > 0:
            response_text = response['content'][0]['text']
        else:
            return "# Error: No content in Claude response", 0, 0

        usage = response.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        return response_text, input_tokens, output_tokens
        
    except requests.exceptions.RequestException as e:
        return f"# Network error calling Claude API: {str(e)}", 0, 0
    except Exception as e:
        return f"# Error processing Claude response: {str(e)}", 0, 0

@tester_bp.route('/generate_iterative_tests', methods=['POST'])
def generate_iterative_tests():
    """Generate tests with iterative improvement based on test failures"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        code = data.get('code')
        max_iterations = data.get('max_iterations', 3)  # Default to 3 attempts
        
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
        
        results = []
        
        for func in functions:
            func_code = ast.unparse(func)
            func_result = {
                'function': func.name,
                'function_code': func_code,
                'attempts': [],
                'final_status': 'failed',
                'total_input_tokens': 0,
                'total_output_tokens': 0
            }
            
            current_test_code = None
            
            # Iterative improvement loop
            for attempt in range(1, max_iterations + 1):
                attempt_result = {
                    'attempt_number': attempt,
                    'test_code': '',
                    'test_output': '',
                    'success': False,
                    'failure_analysis': None,
                    'input_tokens': 0,
                    'output_tokens': 0
                }
                
                try:
                    if attempt == 1:
                        # First attempt: generate initial test
                        test_code, input_tokens, output_tokens = call_claude(func_code, None)
                        
                        # Apply standard post-processing
                        test_code = re.sub(r"^```python|^```|```$", "", test_code, flags=re.MULTILINE).strip()
                        
                        if "import pytest" not in test_code:
                            test_code = "import pytest\n" + test_code
                        
                        if "patch(" in test_code and "from unittest.mock import" not in test_code:
                            test_code = test_code.replace("import pytest", "import pytest\nfrom unittest.mock import patch, Mock")
                        
                        # Fix import statements to use 'module' consistently
                        test_code = re.sub(r'from\s+(?:app|your_module|my_module|test_module|main|\w+_module|\w+\.py|calculator|tester|chatbot|docuwriter|logger)\s+import', 'from module import', test_code)
                        test_code = re.sub(r'patch\(["\'](?:app|your_module|my_module|test_module|main|\w+_module|\w+\.py|calculator)\.', 'patch("module.', test_code)
                        test_code = re.sub(r'patch\(["\'](?:app|your_module|my_module|test_module|main|calculator)(["\'])', r'patch("module\1', test_code)
                        
                        # Remove duplicate imports and clean up any remaining bad imports
                        test_code = re.sub(r'from\s+\w+\.\w+\s+import\s+[^\n]+\n', '', test_code)
                        test_code = re.sub(r'from\s+(?:calculator|tester|chatbot|docuwriter|logger)\s+import\s+[^\n]+\n', '', test_code)
                        
                        # Ensure dependencies are imported
                        func_dependencies = extract_dependencies(func_code)
                        func_dependencies.append(func.name)
                        
                        # Check if there's already a 'from module import' line
                        import_match = re.search(r'from module import (.+)', test_code)
                        if import_match:
                            # Merge existing imports with function dependencies
                            current_imports = set(item.strip() for item in import_match.group(1).split(','))
                            all_imports = current_imports.union(set(func_dependencies))
                            new_import_line = f"from module import {', '.join(sorted(all_imports))}"
                            test_code = re.sub(r'from module import .+', new_import_line, test_code)
                        else:
                            # Add the import line if it doesn't exist
                            import_line = f"from module import {', '.join(sorted(func_dependencies))}"
                            lines = test_code.split('\n')
                            insert_pos = 0
                            for i, line in enumerate(lines):
                                if line.strip().startswith('import ') or line.strip().startswith('from '):
                                    insert_pos = i + 1
                                else:
                                    break
                            lines.insert(insert_pos, import_line)
                            test_code = '\n'.join(lines)
                        
                        # Ensure Flask fixtures for Flask functions
                        is_flask_function = '@' in func_code and ('route' in func_code or 'bp.route' in func_code)
                        if is_flask_function and '@pytest.fixture' not in test_code:
                            fixture_code = '''
@pytest.fixture
def app():
    from flask import Flask
    from ChatBot.chatbot import chatbot_bp
    from AgentLogger.log import logger_bp
    from Docuwriter.docuwriter import docuwriter_bp
    from TestBot.tester import tester_bp
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
    app.register_blueprint(logger_bp, url_prefix='/logger')
    app.register_blueprint(docuwriter_bp, url_prefix='/writer')
    app.register_blueprint(tester_bp, url_prefix='/tester')
    return app

@pytest.fixture
def client(app):
    return app.test_client()

'''
                            lines = test_code.split('\n')
                            insert_pos = 0
                            for i, line in enumerate(lines):
                                if line.strip().startswith('import ') or line.strip().startswith('from '):
                                    insert_pos = i + 1
                                elif line.strip() and not line.strip().startswith('#'):
                                    break
                            lines.insert(insert_pos, fixture_code)
                            test_code = '\n'.join(lines)
                    
                    else:
                        # Subsequent attempts: generate improved test based on previous failure
                        test_code, input_tokens, output_tokens = generate_improved_test(
                            func_code, current_test_code, 
                            func_result['attempts'][-1]['failure_analysis'], 
                            attempt
                        )
                        test_code = re.sub(r"^```python|^```|```$", "", test_code, flags=re.MULTILINE).strip()
                        
                        # Apply the same post-processing for improved tests
                        if "import pytest" not in test_code:
                            test_code = "import pytest\n" + test_code
                        
                        if "patch(" in test_code and "from unittest.mock import" not in test_code:
                            test_code = test_code.replace("import pytest", "import pytest\nfrom unittest.mock import patch, Mock")
                        elif "patch(" in test_code and "patch" not in test_code:
                            test_code = re.sub(r'from unittest\.mock import ([^\n]+)', r'from unittest.mock import \1, patch', test_code)
                        
                        # Fix import statements to use 'module' consistently
                        test_code = re.sub(r'from\s+(?:app|your_module|my_module|test_module|main|\w+_module|\w+\.py|calculator|tester|chatbot|docuwriter|logger)\s+import', 'from module import', test_code)
                        test_code = re.sub(r'patch\(["\'](?:app|your_module|my_module|test_module|main|\w+_module|\w+\.py|calculator)\.', 'patch("module.', test_code)
                        test_code = re.sub(r'patch\(["\'](?:app|your_module|my_module|test_module|main|calculator)(["\'])', r'patch("module\1', test_code)
                        
                        # Remove duplicate imports and clean up any remaining bad imports
                        test_code = re.sub(r'from\s+\w+\.\w+\s+import\s+[^\n]+\n', '', test_code)
                        test_code = re.sub(r'from\s+(?:calculator|tester|chatbot|docuwriter|logger)\s+import\s+[^\n]+\n', '', test_code)
                        
                        # Ensure all function dependencies are included in the import
                        func_dependencies = extract_dependencies(func_code)
                        func_dependencies.append(func.name)
                        
                        # Check if there's already a 'from module import' line
                        import_match = re.search(r'from module import (.+)', test_code)
                        if import_match:
                            # Merge existing imports with function dependencies
                            current_imports = set(item.strip() for item in import_match.group(1).split(','))
                            all_imports = current_imports.union(set(func_dependencies))
                            new_import_line = f"from module import {', '.join(sorted(all_imports))}"
                            test_code = re.sub(r'from module import .+', new_import_line, test_code)
                        else:
                            # Add the import line if it doesn't exist
                            import_line = f"from module import {', '.join(sorted(func_dependencies))}"
                            lines = test_code.split('\n')
                            insert_pos = 0
                            for i, line in enumerate(lines):
                                if line.strip().startswith('import ') or line.strip().startswith('from '):
                                    insert_pos = i + 1
                                else:
                                    break
                            lines.insert(insert_pos, import_line)
                            test_code = '\n'.join(lines)
                    
                    current_test_code = test_code
                    attempt_result['test_code'] = test_code
                    attempt_result['input_tokens'] = input_tokens
                    attempt_result['output_tokens'] = output_tokens
                    func_result['total_input_tokens'] += input_tokens
                    func_result['total_output_tokens'] += output_tokens
                    
                    # Run the test
                    import tempfile, os, subprocess
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
                                timeout=15
                            )
                            test_output = result.stdout.decode() + result.stderr.decode()
                            
                            # Check if tests passed
                            if result.returncode == 0 and 'passed' in test_output and 'FAILED' not in test_output:
                                attempt_result['success'] = True
                                attempt_result['test_output'] = test_output
                                func_result['final_status'] = 'success'
                                func_result['attempts'].append(attempt_result)
                                break
                            else:
                                # Test failed, analyze the failure
                                attempt_result['test_output'] = test_output
                                failure_analysis = analyze_test_failure(test_output, test_code, func_code)
                                attempt_result['failure_analysis'] = failure_analysis
                                
                        except subprocess.TimeoutExpired:
                            attempt_result['test_output'] = "Test execution timeout"
                            attempt_result['failure_analysis'] = {
                                'error_type': 'timeout',
                                'error_message': 'Test execution exceeded time limit',
                                'suggested_fixes': ['Optimize test performance', 'Reduce test complexity'],
                                'needs_regeneration': True
                            }
                        except Exception as e:
                            attempt_result['test_output'] = f"Test execution error: {str(e)}"
                            attempt_result['failure_analysis'] = {
                                'error_type': 'execution_error',
                                'error_message': str(e),
                                'suggested_fixes': ['Fix test execution environment'],
                                'needs_regeneration': True
                            }
                            
                except Exception as e:
                    attempt_result['test_output'] = f"Generation error: {str(e)}"
                    attempt_result['failure_analysis'] = {
                        'error_type': 'generation_error',
                        'error_message': str(e),
                        'suggested_fixes': ['Fix test generation'],
                        'needs_regeneration': False
                    }
                
                func_result['attempts'].append(attempt_result)
                
                # If the test succeeded, break out of the loop
                if attempt_result['success']:
                    break
            
            results.append(func_result)
        
        return jsonify({'results': results})
        
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500