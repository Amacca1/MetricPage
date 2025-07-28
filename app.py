from flask import Flask, render_template
from ChatBot.chatbot import chatbot_bp
from AgentLogger.log import logger_bp
from Docuwriter.docuwriter import docuwriter_bp
from TestBot.tester import tester_bp

app = Flask(__name__)

# Add cache control headers to prevent browser caching during development
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Register blueprints for each module
app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
app.register_blueprint(logger_bp, url_prefix='/logger')
app.register_blueprint(docuwriter_bp, url_prefix='/writer')
app.register_blueprint(tester_bp, url_prefix='/tester')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
