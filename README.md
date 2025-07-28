# MetricPage

A comprehensive web-based dashboard application that integrates multiple AI-powered development tools into a unified platform. MetricPage leverages the Claude AI API (Anthropic) to provide intelligent assistance for various software development tasks including code analysis, documentation generation, test creation, and repository management.

## Project Overview

MetricPage is a Flask-based web application that serves as a centralized dashboard for developers and teams. It combines several AI-enhanced capabilities into a single, cohesive interface, allowing users to streamline their development workflow without switching between multiple tools. The application provides an intuitive web interface where users can access different functionalities through a unified dashboard.

## Features

MetricPage integrates the following capabilities into a single dashboard:

- **AI-Powered Code Assistant**: Interactive chatbot interface for code-related queries and assistance
- **Repository Analytics**: Analyze GitHub repositories and generate human-readable summaries of commit histories
- **Automated Documentation Generation**: Create comprehensive documentation for Python codebases including docstrings, inline comments, and README files
- **Test Generation**: Automatically generate test cases for code repositories using AI analysis
- **GitHub Integration**: Direct integration with GitHub for repository browsing and analysis
- **File Explorer**: Built-in file tree explorer for navigating project structures
- **Code Viewer**: In-browser code viewing with syntax highlighting

## Architecture

MetricPage follows a modular Flask architecture with the following structure:

```
MetricPage/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   └── index.html        # Main dashboard interface
├── static/               # CSS and JavaScript files
├── ChatBot/              # Code assistant module
├── AgentLogger/          # Repository analytics module
├── Docuwriter/           # Documentation generation module
└── TestBot/              # Test generation module
```

Each module is implemented as a Flask Blueprint, allowing for clean separation of concerns while maintaining a unified application structure. The main application (`app.py`) registers these blueprints with specific URL prefixes:

- `/chatbot` - AI code assistant interface
- `/logger` - Repository commit analysis
- `/writer` - Documentation generation
- `/tester` - Test case generation

## Installation & Setup

1. **Clone the repository**
   ```bash
   git clone [repository-url]
   cd MetricPage
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory with the following:
   ```
   ANTHROPIC_API_KEY=your_anthropic_api_key
   GITHUB_TOKEN=your_github_personal_access_token
   ANTHROPIC_API_URL=https://api.anthropic.com/v1/messages
   MODEL=claude-3-opus-20240229
   VERSION=2023-06-01
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

   The application will start on `http://localhost:5000`

## Usage

1. **Access the Dashboard**
   Navigate to `http://localhost:5000` in your web browser to access the main MetricPage dashboard.

2. **Select a Tool**
   From the main dashboard, choose the functionality you need:
   - Click on the appropriate card or navigation link
   - Each tool opens in its dedicated interface within the application

3. **Using the Features**
   - **Code Assistant**: Enter your coding questions or requests in the chat interface
   - **Repository Analytics**: Input a GitHub username to fetch repositories, then select one to analyze commit history
   - **Documentation Generation**: Browse your codebase and select files to generate documentation
   - **Test Generation**: Select repository files and generate comprehensive test suites

4. **View Results**
   All AI-generated content is displayed within the application interface, with options to copy, download, or further refine the results.

## API Endpoints

MetricPage exposes the following internal API endpoints:

### Main Application
- `GET /` - Main dashboard interface

### Code Assistant Module
- `GET /chatbot/` - Chat interface
- `POST /chatbot/chat` - Send message to AI assistant

### Repository Analytics Module
- `GET /logger/` -