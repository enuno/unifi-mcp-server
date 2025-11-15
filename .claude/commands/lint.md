---
description: Run all linters and code quality checks
allowed-tools:
  - Bash(black:*)
  - Bash(isort:*)
  - Bash(ruff:*)
  - Bash(mypy:*)
  - Bash(/Users/elvis/Library/Python/3.12/bin/black:*)
  - Bash(/Users/elvis/Library/Python/3.12/bin/isort:*)
  - Bash(/Users/elvis/Library/Python/3.12/bin/ruff:*)
  - Bash(/Users/elvis/Library/Python/3.12/bin/mypy:*)
author: project
version: 1.0.0
---

Run comprehensive code quality checks on the project.

Execute the following checks:

1. Black formatting check: `black --check src/ tests/`
2. isort import sorting check: `isort --check-only src/ tests/`
3. Ruff linting: `ruff check src/ tests/`
4. MyPy type checking: `mypy src/`

Report back with:

- List of any formatting issues
- Import sorting problems
- Linting errors or warnings
- Type checking errors
- Suggested fixes for any issues found

If there are issues, ask if I should auto-fix them.
