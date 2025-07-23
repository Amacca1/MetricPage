from flask import Flask, request, jsonify, render_template
import anthropic
from dotenv import load_dotenv
import os
import subprocess
import requests

app = Flask(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Set your GitHub token as env var
REPO_BASE = "cloned_repos"  # Directory to store cloned repos

def get_github_repos(username):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    url = f"https://api.github.com/users/{username}/repos"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return []
    return [repo["name"] for repo in resp.json()]

def clone_repo(username, repo_name):
    repo_path = os.path.join(REPO_BASE, repo_name)
    if not os.path.exists(REPO_BASE):
        os.makedirs(REPO_BASE)
    if not os.path.isdir(repo_path):
        repo_url = f"https://github.com/{username}/{repo_name}.git"
        subprocess.run(["git", "clone", repo_url, repo_path])
    return repo_path

def get_git_log_summary(repo_path):
    try:
        logs = subprocess.check_output(
            ["git", "-C", repo_path, "log", "--pretty=format:%h %an %ad %s", "--date=short", "--no-merges"],
            universal_newlines=True
        )
    except Exception as e:
        return f"Error retrieving git logs: {e}"

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (
        "Summarize the following git commit logs in a human-readable way, focusing on key changes and their impact:\n\n"
        f"{logs}\n\nSummary:"
    )
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=300,
        temperature=0.5,
        system="You are an expert AI agent summarizing git logs for a human reader.",
        messages=[{"role": "user", "content": prompt}]
    )
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None) if usage else None
    output_tokens = getattr(usage, "output_tokens", None) if usage else None
    total_tokens = (input_tokens or 0) + (output_tokens or 0)
    print(f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, Total tokens: {total_tokens}")
    return str(response.content)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_repos', methods=['POST'])
def get_repos():
    data = request.get_json()
    username = data.get("username")
    repos = get_github_repos(username)
    return jsonify({"repos": repos})

@app.route('/summarize_logs', methods=['POST'])
def summarize_logs():
    data = request.get_json()
    username = data.get("username")
    repo_name = data.get("repo_name")
    if not username or not repo_name:
        return jsonify({"error": "Missing username or repo name"}), 400
    repo_path = clone_repo(username, repo_name)
    summary = get_git_log_summary(repo_path)
    return jsonify({"summary": summary})

if __name__ == "__main__":
    app.run(debug=True)