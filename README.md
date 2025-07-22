# DocuWriter

A Flask-based web application that leverages the Anthropic AI API to automatically generate documentation for code files and entire projects.

## Overview

DocuWriter is an intelligent documentation assistant that helps developers improve their codebase documentation. It provides an interactive web interface for browsing project files and automatically generating:
- Inline comments and docstrings for individual files
- Comprehensive README.md files for entire projects

## Key Features

- **File Tree Explorer**: Browse Python and HTML files in your project with an intuitive web interface
- **AI-Powered Documentation Suggestions**: Generate contextual documentation suggestions for any code file using Anthropic's Claude model
- **Automatic Documentation Insertion**: Add suggested documentation directly into source files with proper formatting and markers
- **README Generation**: Automatically create project README files by analyzing the entire codebase
- **Git Integration**: Automatically commits generated README files to your repository

## Technical Architecture

The application is built with:
- **Flask**: Web framework for the backend API
- **Anthropic API**: AI model for generating documentation
- **Environment Variables**: Secure configuration management via `.env` file

### API Endpoints

- `GET /`: Serves the main web interface
- `GET /filetree`: Returns JSON list of project files
- `GET /filecontent`: Retrieves content of a specific file
- `POST /suggest_doc`: Generates documentation suggestions for a given file
- `POST /add_doc`: Inserts documentation into source files
- `POST /generate_readme`: Creates a comprehensive README.md for the project

## Configuration

The application requires the following environment variables:
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `ANTHROPIC_API_URL`: API endpoint URL
- `MODEL`: The AI model to use (e.g., Claude)
- `VERSION`: API version

## Usage

1. Set up your environment variables in a `.env` file
2. Run the Flask application: `python app.py`
3. Open the web interface at `http://localhost:5000`
4. Browse files and click to generate documentation suggestions
5. Apply suggestions or generate a project README with one click

## Security Features

- Path traversal protection for file access
- Configurable ignore directories (venv, __pycache__, etc.)
- Secure API key management through environment variables