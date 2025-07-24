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
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": VERSION
    }

    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "system": "You are Claude, an AI assistant.",
        "messages": messages
    }

    try:
        response = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        resp_json = response.json()
        content = response.json()["content"][0]["text"]
        usage = resp_json.get("usage", {})
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
        print(f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, Total: {total_tokens}")
        return jsonify({"reply": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
