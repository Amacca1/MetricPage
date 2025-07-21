from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/chat/completions")
MODEL = os.getenv("ANTHROPIC_MODEL")
VERSION = os.getenv("ANTHROPIC_VERSION")

@app.route('/')
def index():
    return render_template('coderpage.html')


@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    messages = data.get("messages", [])

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,  # <-- lowercase x
        "anthropic-version": VERSION
    }

    payload = {
        "model": MODEL,
        "max_tokens": 16384,
        "system": "You are Claude, an AI assistant.",
        "messages": messages
    }

    try:
        response = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        content = response.json()["content"][0]["text"]
        return jsonify({"reply": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
