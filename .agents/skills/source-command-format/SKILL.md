---
name: "source-command-format"
description: "Auto-format all Python code"
---

# source-command-format

Use this skill when the user asks to run the migrated source command `format`.

## Command Template

Automatically format all Python code in the project.

Execute the following commands:

1. Format code with Black: `black src/ tests/`
2. Sort imports with isort: `isort src/ tests/`
3. Fix auto-fixable linting issues: `ruff check src/ tests/ --fix`

Report back with:

- Files that were modified
- Summary of changes made
- Any remaining issues that require manual intervention
