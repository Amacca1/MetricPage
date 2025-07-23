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

def get_git_log_summary(username, repo_name, token):
    # Use GitHub API to get commit logs instead of local git
    url = f"https://api.github.com/repos/{username}/{repo_name}/commits?per_page=50"
    headers = {"Authorization": f"token {token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return f"Error retrieving commit logs: {resp.status_code} - {resp.text}"
    commits = resp.json()
    logs = []
    for commit in commits:
        sha = commit["sha"][:7]
        author = commit["commit"]["author"]["name"]
        date = commit["commit"]["author"]["date"][:10]
        message = commit["commit"]["message"].replace('\n', ' ')
        logs.append(f"{sha} {author} {date} {message}")
    logs_text = "\n".join(logs)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (
        "Summarize the following git commit logs for a non-technical reader. "
        "Use clear language, bullet points, and highlight the most important changes and their impact. "
        "Make the summary easy to comprehend and visually organized:\n\n"
        f"{logs_text}\n\nSummary:"
    )
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=1024,
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
    summary = get_git_log_summary(username, repo_name, GITHUB_TOKEN)
    return jsonify({"summary": summary})

if __name__ == "__main__":
    app.run(debug=True)