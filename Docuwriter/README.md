# DocuWriter

A Flask-based web application that leverages AI to automatically generate documentation for Python codebases. DocuWriter uses the Anthropic API to analyze code and suggest comprehensive documentation, including docstrings, inline comments, and README files.

## Features

- **File Tree Explorer**: Browse Python files and HTML templates in your repository
- **Code Viewer**: View source code directly in the web interface
- **AI-Powered Documentation Suggestions**: Generate contextual docstrings and comments for any code file
- **Automatic Documentation Insertion**: Add suggested documentation directly to source files with clear markers
- **README Generator**: Automatically create comprehensive README.md files based on your entire codebase
- **Git Integration**: Automatically commit generated README files to your repository

## Key Endpoints

- `/` - Main web interface
- `/filetree` - Returns JSON list of Python and HTML files in the repository
- `/filecontent` - Retrieves content of a specific file
- `/suggest_doc` - Generates documentation suggestions for a given code file
- `/add_doc` - Inserts suggested documentation into source files
- `/generate_readme` - Creates a README.md file analyzing the entire codebase

## Configuration

The application requires the following environment variables (set in `.env`):

- `ANTHROPIC_API_KEY` - Your Anthropic API key
- `ANTHROPIC_API_URL` - Anthropic API endpoint URL
- `MODEL` - The AI model to use (e.g., claude-3)
- `VERSION` - API version string

## Usage

1. Set up your environment variables in a `.env` file
2. Run the Flask application: `python app.py`
3. Navigate to `http://localhost:5000` in your browser
4. Browse files, generate documentation suggestions, and create README files with a single click

## Security Features

- Path traversal protection ensures files can only be accessed within the repository root
- Configurable ignore directories (venv, __pycache__, tests, migrations)
- Safe file writing with clear documentation markers

## Documentation Markers

When documentation is added to files, it's wrapped in clear markers:
```
# === DOCUWRITER SUGGESTED DOCUMENTATION START ===
[Generated documentation]
# === DOCUWRITER SUGGESTED DOCUMENTATION END ===
```

This makes it easy to identify and manage AI-generated documentation in your codebase.