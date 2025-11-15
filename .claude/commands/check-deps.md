---
description: Check for outdated or vulnerable dependencies
allowed-tools:
  - Bash(uv:*)
  - Bash(safety:*)
  - Bash(pip:*)
  - Bash(pip3:*)
  - Read
author: project
version: 1.0.0
---

Check project dependencies for updates and vulnerabilities.

Execute the following checks:

1. List outdated packages: `uv pip list --outdated`
2. Check for security vulnerabilities: `safety check`
3. Review pyproject.toml dependencies
4. Check for deprecated package warnings

Report back with:

- List of outdated packages with current and latest versions
- Security vulnerabilities found (if any)
- Recommendations for which packages to update
- Potential breaking changes to watch for
- Commands to update specific packages

Ask if I want to update any packages before proceeding.
