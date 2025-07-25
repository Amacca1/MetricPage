from flask import Blueprint, render_template, request, jsonify
import requests
from dotenv import load_dotenv
import os
import re
import ast
import json
import base64

load_dotenv()

docuwriter_bp = Blueprint('docuwriter', __name__, template_folder='templates')

GITHUB_API = "https://api.github.com"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL")
MODEL = os.getenv("MODEL")
VERSION = os.getenv("VERSION")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Optional: for private repos or higher rate limits

@docuwriter_bp.route('/')
def index():
    return render_template('writerpage.html')

@docuwriter_bp.route('/repos')
def list_repos():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'No username provided'}), 400
    
    headers = {}
    if GITHUB_TOKEN:
        headers['Authorization'] = f"token {GITHUB_TOKEN}"
    
    r = requests.get(f"{GITHUB_API}/users/{username}/repos", headers=headers)
    if r.status_code != 200:
        return jsonify({'error': 'GitHub error'}), 500
    repos = [repo['name'] for repo in r.json()]
    return jsonify({'repos': repos})

@docuwriter_bp.route('/branches')
def list_branches():
    username = request.args.get('username')
    repo = request.args.get('repo')
    if not username or not repo:
        return jsonify({'error': 'Missing params'}), 400
    
    headers = {}
    if GITHUB_TOKEN:
        headers['Authorization'] = f"token {GITHUB_TOKEN}"
    
    r = requests.get(f"{GITHUB_API}/repos/{username}/{repo}/branches", headers=headers)
    if r.status_code != 200:
        return jsonify({'error': 'GitHub error'}), 500
    branches = [b['name'] for b in r.json()]
    return jsonify({'branches': branches})

@docuwriter_bp.route('/filetree')
def filetree():
    username = request.args.get('username')
    repo = request.args.get('repo')
    branch = request.args.get('branch', 'main')
    if not username or not repo:
        return jsonify({'error': 'Missing params'}), 400
    
    headers = {}
    if GITHUB_TOKEN:
        headers['Authorization'] = f"token {GITHUB_TOKEN}"
    
    def get_repo_files(path=""):
        url = f"{GITHUB_API}/repos/{username}/{repo}/contents/{path}"
        params = {'ref': branch}
        r = requests.get(url, headers=headers, params=params)
        if r.status_code != 200:
            return []
        
        files = []
        for item in r.json():
            if item['type'] == 'file':
                if (item['name'].endswith('.py') or 
                    item['name'].endswith('.html') or 
                    item['name'] == "README.md"):
                    files.append(item['path'])
            elif item['type'] == 'dir' and item['name'] not in {'venv', '.venv', '__pycache__', 'tests', 'migrations'}:
                files.extend(get_repo_files(item['path']))
        return files
    
    tree = get_repo_files()
    return jsonify(tree)

@docuwriter_bp.route('/filecontent')
def filecontent():
    username = request.args.get('username')
    repo = request.args.get('repo')
    path = request.args.get('path')
    branch = request.args.get('branch', 'main')
    
    if not username or not repo or not path:
        return jsonify({'error': 'Missing params'}), 400
    
    headers = {}
    if GITHUB_TOKEN:
        headers['Authorization'] = f"token {GITHUB_TOKEN}"
    
    r = requests.get(f"{GITHUB_API}/repos/{username}/{repo}/contents/{path}", 
                    headers=headers, params={'ref': branch})
    if r.status_code != 200:
        return jsonify({'error': 'GitHub error'}), 500
    
    content = base64.b64decode(r.json()['content']).decode('utf-8')
    return jsonify({'content': content})

@docuwriter_bp.route('/suggest_doc', methods=['POST'])
def suggest_doc():
    data = request.get_json()
    code = data.get("code") 

    if not code:
        return jsonify({'error': 'No code provided'}), 400

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
        usage = resp_json.get("usage", {})
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
        print(f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, Total tokens: {total_tokens}")
        return jsonify({"suggestion": suggestion})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@docuwriter_bp.route('/generate_readme', methods=['POST'])
def generate_readme():
    data = request.get_json()
    username = data.get('username')
    repo = data.get('repo')
    branch = data.get('branch', 'main')
    write_to_repo = data.get('write_to_repo', False)  # New option to write to repo
    readme_content = data.get('readme_content')  # Pre-generated content for write-only operations
    
    if not username or not repo:
        return jsonify({'error': 'Missing username or repo'}), 400

    headers = {}
    if GITHUB_TOKEN:
        headers['Authorization'] = f"token {GITHUB_TOKEN}"

    # If we're writing to repo and have pre-generated content, skip generation
    if write_to_repo and readme_content:
        if not GITHUB_TOKEN:
            return jsonify({"error": "GitHub token required to write to repository"}), 400
        
        write_result = write_readme_to_repo(username, repo, branch, readme_content, headers)
        
        # Also save a local copy in the workspace for VS Code visibility
        local_save_result = save_local_readme(username, repo, readme_content)
        
        if write_result.get('success'):
            return jsonify({
                "success": True, 
                "readme": readme_content,
                "written_to_repo": True,
                "commit_sha": write_result.get('commit_sha'),
                "local_saved": local_save_result.get('success', False),
                "local_path": local_save_result.get('path')
            })
        else:
            return jsonify({
                "success": True, 
                "readme": readme_content,
                "written_to_repo": False,
                "write_error": write_result.get('error'),
                "local_saved": local_save_result.get('success', False),
                "local_path": local_save_result.get('path')
            })

    # Generate README content
    def get_repo_files(path=""):
        url = f"{GITHUB_API}/repos/{username}/{repo}/contents/{path}"
        params = {'ref': branch}
        r = requests.get(url, headers=headers, params=params)
        if r.status_code != 200:
            return []
        
        files = []
        for item in r.json():
            if item['type'] == 'file':
                if (item['name'].endswith('.py') or 
                    item['name'].endswith('.html') or 
                    item['name'] == "README.md"):
                    files.append(item['path'])
            elif item['type'] == 'dir' and item['name'] not in {'venv', '.venv', '__pycache__', 'tests', 'migrations'}:
                files.extend(get_repo_files(item['path']))
        return files

    file_paths = get_repo_files()
    
    # Read contents of each file (limit total size for API)
    code_snippets = []
    total_chars = 0
    max_chars = 8000  # Limit to avoid API issues
    
    for path in file_paths:
        if total_chars > max_chars:
            break
            
        file_url = f"{GITHUB_API}/repos/{username}/{repo}/contents/{path}"
        params = {'ref': branch}
        r = requests.get(file_url, headers=headers, params=params)
        
        if r.status_code == 200:
            try:
                content = base64.b64decode(r.json()['content']).decode('utf-8')
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

    headers_api = {
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
        response = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers_api)
        response.raise_for_status()
        resp_json = response.json()
        generated_readme = resp_json["content"][0]["text"]
        
        # If write_to_repo is True, write the README to the repository
        if write_to_repo:
            if not GITHUB_TOKEN:
                return jsonify({"error": "GitHub token required to write to repository"}), 400
            
            write_result = write_readme_to_repo(username, repo, branch, generated_readme, headers)
            
            # Also save a local copy in the workspace for VS Code visibility
            local_save_result = save_local_readme(username, repo, generated_readme)
            
            if write_result.get('success'):
                return jsonify({
                    "success": True, 
                    "readme": generated_readme,
                    "written_to_repo": True,
                    "commit_sha": write_result.get('commit_sha'),
                    "local_saved": local_save_result.get('success', False),
                    "local_path": local_save_result.get('path')
                })
            else:
                return jsonify({
                    "success": True, 
                    "readme": generated_readme,
                    "written_to_repo": False,
                    "write_error": write_result.get('error'),
                    "local_saved": local_save_result.get('success', False),
                    "local_path": local_save_result.get('path')
                })
        
        return jsonify({"success": True, "readme": generated_readme, "written_to_repo": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Helper functions for documentation processing
def write_readme_to_repo(username, repo, branch, readme_content, headers):
    """
    Write README content to a GitHub repository
    """
    # First, check if README.md already exists
    readme_url = f"{GITHUB_API}/repos/{username}/{repo}/contents/README.md"
    params = {'ref': branch}
    
    existing_readme = requests.get(readme_url, headers=headers, params=params)
    
    # Prepare the content for GitHub API (must be base64 encoded)
    encoded_content = base64.b64encode(readme_content.encode('utf-8')).decode('utf-8')
    
    # Prepare the commit data
    commit_data = {
        "message": "Auto-generated README.md using Docuwriter",
        "content": encoded_content,
        "branch": branch
    }
    
    # If README already exists, we need to include the SHA for updating
    if existing_readme.status_code == 200:
        commit_data["sha"] = existing_readme.json()["sha"]
        commit_message = "Updated README.md using Docuwriter"
    else:
        commit_message = "Created README.md using Docuwriter"
    
    commit_data["message"] = commit_message
    
    # Make the API call to create/update the file
    try:
        response = requests.put(readme_url, json=commit_data, headers=headers)
        if response.status_code in [200, 201]:
            return {"success": True, "commit_sha": response.json().get("commit", {}).get("sha")}
        else:
            return {"success": False, "error": f"GitHub API error: {response.status_code} - {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def save_local_readme(username, repo, readme_content):
    """
    Save README content to a local file in the workspace for VS Code visibility
    """
    try:
        # Create a local directory structure: workspace/generated_readmes/username_repo/
        workspace_root = os.path.dirname(os.path.dirname(__file__))  # Go up to MetricPage root
        readme_dir = os.path.join(workspace_root, "generated_readmes", f"{username}_{repo}")
        
        # Create the directory if it doesn't exist
        os.makedirs(readme_dir, exist_ok=True)
        
        # Save the README file
        readme_path = os.path.join(readme_dir, "README.md")
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        return {"success": True, "path": readme_path}
    except Exception as e:
        return {"success": False, "error": str(e)}

def insert_docstrings(original_code, suggestions):
    """
    original_code: str, the code of the file
    suggestions: dict, mapping function/class names to docstring/comment
    Returns: str, code with inserted docstrings/comments
    """
    try:
        tree = ast.parse(original_code)
    except SyntaxError:
        return original_code
    
    lines = original_code.split('\n')
    offset = 0  # Track line insertions

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            name = node.name
            if name in suggestions:
                insert_line = node.lineno - 1 + offset  # Zero-indexed
                if insert_line < len(lines):
                    # Insert docstring after function/class definition line
                    docstring = f'    """{suggestions[name]}"""'
                    lines.insert(insert_line + 1, docstring)
                    offset += 1

    return '\n'.join(lines)