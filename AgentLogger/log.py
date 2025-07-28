from flask import Blueprint, render_template, request, jsonify
import anthropic
from dotenv import load_dotenv
import os
import subprocess
import requests

logger_bp = Blueprint('logger', __name__, template_folder='templates')

load_dotenv()

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
    url = f"https://api.github.com/repos/{username}/{repo_name}/commits?per_page=50"
    headers = {"Authorization": f"token {token}"}
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return f"Error retrieving commit logs: {resp.status_code} - {resp.text}"
        commits = resp.json()
        
        if not commits:
            return "No commits found in this repository."
            
        logs = []
        for commit in commits:
            sha = commit["sha"][:7]
            author = commit["commit"]["author"]["name"]
            date = commit["commit"]["author"]["date"][:10]
            message = commit["commit"]["message"].replace('\n', ' ')
            logs.append(f"{sha} {author} {date} {message}")
        logs_text = "\n".join(logs)

        if not ANTHROPIC_API_KEY:
            return "Error: Anthropic API key not configured"
            
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = (
            "Summarize the following git commit logs for a non-technical reader. "
            "Use clear language, bullet points, and highlight the most important changes and their impact. "
            "Make the summary easy to comprehend and visually organized:\n\n"
            f"{logs_text}\n\nSummary:"
        )
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            temperature=0.5,
            system="You are an expert AI agent summarizing git logs for a human reader.",
            messages=[{"role": "user", "content": prompt}]
        )
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None) if usage else None
        output_tokens = getattr(usage, "output_tokens", None) if usage else None
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
        print(f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, Total: {total_tokens}")
        summary_text = response.content if isinstance(response.content, str) else response.content[0].text if hasattr(response.content[0], "text") else str(response.content[0])
        return summary_text
    except requests.exceptions.RequestException as e:
        return f"Network error: {str(e)}"
    except Exception as e:
        return f"Error generating summary: {str(e)}"

@logger_bp.route('/')
def index():
    return render_template('logger.html')

@logger_bp.route('/get_repos', methods=['POST'])
def get_repos():
    data = request.get_json()
    username = data.get("username")
    repos = get_github_repos(username)
    return jsonify({"repos": repos})

@logger_bp.route('/summarize_logs', methods=['POST'])
def summarize_logs():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        username = data.get("username")
        repo_name = data.get("repo_name")
        if not username or not repo_name:
            return jsonify({"error": "Missing username or repo name"}), 400
        
        summary = get_git_log_summary(username, repo_name, GITHUB_TOKEN)
        return jsonify({"summary": summary})
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500