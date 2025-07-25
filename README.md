# AgentLogger

A Flask-based web application that leverages AI to generate human-readable summaries of GitHub repository commit logs.

## Overview

AgentLogger fetches commit history from GitHub repositories and uses Claude AI (Anthropic) to create clear, non-technical summaries of the changes. This tool is designed to help stakeholders understand project progress without needing to parse technical git logs.

## Features

- **GitHub Integration**: Fetches repository lists and commit histories using the GitHub API
- **AI-Powered Summaries**: Uses Claude AI to generate easy-to-understand summaries of git commits
- **Web Interface**: Clean, responsive UI for selecting repositories and viewing summaries
- **Markdown Support**: Renders AI-generated summaries with proper formatting

## Structure

```
AgentLogger/
├── log.py                 # Flask backend with API endpoints
└── templates/
    └── logger.html        # Frontend interface
```

## Requirements

- Python with Flask
- Anthropic API key for Claude AI
- GitHub personal access token
- Environment variables:
  - `ANTHROPIC_API_KEY`
  - `GITHUB_TOKEN`

## API Endpoints

- `GET /` - Serves the main web interface
- `POST /get_repos` - Fetches list of repositories for a given GitHub username
- `POST /summarize_logs` - Generates AI summary of commit logs for a specific repository

## Usage

1. Enter a GitHub username
2. Click "Load Repos" to fetch available repositories
3. Select a repository from the dropdown
4. Click "Summarize Logs" to generate an AI-powered summary of recent commits

The application fetches the last 50 commits and presents them in a visually appealing, easy-to-understand format suitable for non-technical readers.