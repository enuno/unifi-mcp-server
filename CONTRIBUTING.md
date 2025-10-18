# Contributing to UniFi MCP Server

Thank you for your interest in contributing to the UniFi MCP Server project! This document provides guidelines and instructions for contributing to this project, whether you're a human developer or an AI coding assistant.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Commit Message Conventions](#commit-message-conventions)
- [Pull Request Process](#pull-request-process)
- [AI-Assisted Contributions](#ai-assisted-contributions)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to a code of conduct that promotes a welcoming and inclusive environment. All contributors are expected to:

- Be respectful and considerate in all interactions
- Accept constructive criticism gracefully
- Focus on what is best for the project and community
- Show empathy towards other community members

## Getting Started

### Prerequisites

- Python 3.10 or higher
- `uv` for Python package and virtual environment management
- Git for version control
- Docker (optional, for containerized deployment)
- A UniFi Network Controller for testing (can be a local instance or cloud-hosted)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:

```bash
git clone https://github.com/YOUR_USERNAME/unifi-mcp-server.git
cd unifi-mcp-server
```

3. Add the upstream repository as a remote:

```bash
git remote add upstream https://github.com/elvis/unifi-mcp-server.git
```

## Development Setup

### 1. Install uv

If you haven't already installed `uv`, follow the instructions at [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv).

### 2. Create Virtual Environment and Install Dependencies

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the project with development dependencies
uv pip install -e ".[dev]"
```

### 3. Set Up Pre-commit Hooks

Pre-commit hooks ensure code quality and consistency before commits:

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

### 4. Configure Environment

Create a `.env` file for local development:

```bash
cp .env.example .env
```

#### Obtain Your UniFi API Key

Before configuring the environment, you need to obtain an API key:

1. Log in to [UniFi Site Manager](https://unifi.ui.com)
2. Navigate to **Settings → Control Plane → Integrations**
3. Click **Create API Key**
4. **Copy and save the key immediately** - it's only shown once!

#### Configure Your Environment

Edit the `.env` file with your UniFi API key:

```env
# Required: Your UniFi API Key
UNIFI_API_KEY=your-api-key-here

# For cloud API (recommended)
UNIFI_API_TYPE=cloud
UNIFI_HOST=api.ui.com
UNIFI_PORT=443
UNIFI_VERIFY_SSL=true

# OR for local gateway proxy
# UNIFI_API_TYPE=local
# UNIFI_HOST=192.168.1.1
# UNIFI_VERIFY_SSL=false
```

**CRITICAL SECURITY NOTES:**

- **NEVER commit the `.env` file** to version control (it's in `.gitignore`)
- **API keys provide full access** to your UniFi environment - treat them like passwords
- **Store keys securely** using environment variables or secret management systems
- **Rotate keys regularly** for security best practices
- **Monitor key usage** for suspicious activity
- The API is currently **read-only** in Early Access, but will support write operations in future versions

## Development Workflow

### Branch Strategy

- `main` - The main branch contains stable, production-ready code
- `feature/*` - Feature branches for new functionality
- `fix/*` - Bug fix branches
- `docs/*` - Documentation-only changes
- `refactor/*` - Code refactoring that doesn't change functionality

### Creating a Feature Branch

```bash
# Update your local main branch
git checkout main
git pull upstream main

# Create a new feature branch
git checkout -b feature/your-feature-name
```

### Making Changes

1. Make your changes in your feature branch
2. Write or update tests as necessary
3. Update documentation if you're changing functionality
4. Ensure all tests pass: `pytest`
5. Ensure code passes linting: `pre-commit run --all-files`

## Code Style Guidelines

This project follows strict code style guidelines enforced by automated tools:

### Python Style

- **Formatting:** Code is formatted with [Black](https://black.readthedocs.io/) (line length: 100)
- **Import Sorting:** Imports are sorted with [isort](https://pycqa.github.io/isort/) (compatible with Black)
- **Linting:** Code is linted with [Ruff](https://docs.astral.sh/ruff/)
- **Type Checking:** Type hints are required and checked with [MyPy](http://mypy-lang.org/)

### Key Conventions

- Use type hints for all function signatures
- Prefer `async` functions for I/O-bound operations
- Keep functions focused and single-purpose
- Use descriptive variable and function names
- Add docstrings to all public functions, classes, and modules
- Maximum line length: 100 characters (enforced by Black)

### Example Code Style

```python
from typing import Dict, List, Optional
import httpx
from pydantic import BaseModel


class Device(BaseModel):
    """Represents a UniFi network device."""

    mac: str
    name: str
    model: str
    ip: Optional[str] = None


async def get_devices(
    client: httpx.AsyncClient, site_id: str = "default"
) -> List[Device]:
    """
    Retrieve all devices for a specific site.

    Args:
        client: Authenticated HTTP client
        site_id: Site identifier (default: "default")

    Returns:
        List of Device objects

    Raises:
        httpx.HTTPError: If the API request fails
    """
    response = await client.get(f"/api/s/{site_id}/stat/device")
    response.raise_for_status()
    data = response.json()
    return [Device(**device) for device in data["data"]]
```

## Commit Message Conventions

This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification:

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that don't affect code meaning (formatting, etc.)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Changes to build process or auxiliary tools
- `ci`: Changes to CI/CD configuration

### Examples

```
feat(api): add support for firewall rule management

Implement MCP tools for creating, updating, and deleting
UniFi firewall rules through the official API.

Closes #123
```

```
fix(auth): handle session timeout gracefully

Previously, the server would crash when the UniFi session
expired. Now it automatically re-authenticates.
```

## Pull Request Process

### Before Submitting

1. Ensure all tests pass: `pytest`
2. Ensure code passes all pre-commit checks: `pre-commit run --all-files`
3. Update the `README.md` or other documentation with details of changes
4. Update the `API.md` if you've added new MCP tools or resources
5. Rebase your branch on the latest `main` if needed

### Submitting a Pull Request

1. Push your branch to your fork:

```bash
git push origin feature/your-feature-name
```

2. Open a pull request on GitHub
3. Fill out the pull request template completely
4. Link any related issues (e.g., "Closes #123")
5. Request review from maintainers

### Pull Request Title

Use conventional commit format for PR titles:

```
feat(scope): brief description of changes
```

### Pull Request Description Template

```markdown
## Description

Brief description of what this PR does.

## Type of Change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing

Describe the tests you ran and how to reproduce them.

## Checklist

- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published
```

### Review Process

- At least one maintainer must approve the PR
- All CI/CD checks must pass
- No unresolved review comments
- Branch must be up-to-date with `main`

## AI-Assisted Contributions

### Transparency Requirements

When AI coding assistants contribute to this project:

1. **Tag Contributions:** Add a note in the PR description indicating AI assistance:

```markdown
## AI Assistance

This PR was created with assistance from [AI Tool Name].
```

2. **Human Review:** All AI-generated code must be reviewed by a human developer
3. **Testing:** AI-generated code must include comprehensive tests
4. **Documentation:** AI-generated code must be well-documented

### AI-Specific Guidelines

- AI assistants should follow the guidelines in `AGENTS.md`
- Never commit sensitive data (credentials, API keys, etc.)
- Always use environment variables for configuration
- Follow the principle of least privilege for permissions
- Include clear explanations for complex logic

See `AI_GIT_PRACTICES.md` and `CONTRIBUTION_BEST_PRACTICES.md` for additional AI-specific guidance.

## Testing Requirements

### Unit Tests

All new code must include unit tests:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_api.py

# Run tests matching a pattern
pytest -k "test_authentication"
```

### Test Coverage

- Minimum code coverage: 80%
- New features must include tests that cover all code paths
- Bug fixes should include regression tests

### Integration Tests

Integration tests that interact with a real UniFi controller should be marked:

```python
import pytest

@pytest.mark.integration
def test_real_controller_connection():
    # Test code here
    pass
```

Run integration tests separately:

```bash
pytest -m integration
```

### MCP Inspector Testing

Use the MCP Inspector to manually test tools and resources:

```bash
uv run mcp dev src/main.py
```

Then open `http://localhost:5173` in your browser.

## Documentation

### Code Documentation

- All public functions, classes, and modules must have docstrings
- Use Google-style docstrings:

```python
def function(arg1: str, arg2: int) -> bool:
    """
    Brief description of function.

    Longer description if needed.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When something is wrong
    """
    pass
```

### Project Documentation

- Update `README.md` for user-facing changes
- Update `API.md` for new MCP tools or resources
- Update `CHANGELOG.md` (if exists) with notable changes
- Add examples for new features

## Questions?

If you have questions about contributing:

1. Check existing documentation in the repository
2. Search for similar issues or pull requests
3. Open a new issue with the `question` label
4. Reach out to maintainers

Thank you for contributing to UniFi MCP Server!
