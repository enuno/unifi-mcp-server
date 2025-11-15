---
description: Set up the development environment
allowed-tools:
  - Bash(uv:*)
  - Bash(pre-commit:*)
  - Bash(pytest:*)
  - Bash(cp:*)
  - Read
  - Write
author: project
version: 1.0.0
---

Set up a complete development environment for the UniFi MCP Server project.

Execute the following setup steps:

1. Check if uv is installed; if not, provide installation instructions
2. Create a virtual environment: `uv venv`
3. Activate the virtual environment
4. Install dependencies: `uv pip install -e ".[dev]"`
5. Install pre-commit hooks: `pre-commit install && pre-commit install --hook-type commit-msg`
6. Check if .env file exists; if not, copy from .env.example
7. Run initial tests to verify setup: `pytest --co -q`

Report back with:

- Setup completion status
- Any errors encountered
- Next steps for configuration
- Reminder to update .env with actual credentials
