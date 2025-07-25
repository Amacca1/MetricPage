from flask import Flask, render_template
from ChatBot.chatbot import chatbot_bp
from AgentLogger.log import logger_bp
from Docuwriter.docuwriter import docuwriter_bp
from TestBot.tester import tester_bp

app = Flask(__name__)

# Register blueprints for each module
app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
app.register_blueprint(logger_bp, url_prefix='/logger')
app.register_blueprint(docuwriter_bp, url_prefix='/writer')
app.register_blueprint(tester_bp, url_prefix='/tester')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
