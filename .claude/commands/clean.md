---
description: Clean build artifacts and cache files
---

Clean all build artifacts, cache files, and temporary files from the project.

Execute the following cleanup commands:

1. Remove Python cache: `find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true`
2. Remove .pyc files: `find . -type f -name "*.pyc" -delete`
3. Remove pytest cache: `rm -rf .pytest_cache`
4. Remove coverage data: `rm -rf htmlcov .coverage coverage.xml`
5. Remove build artifacts: `rm -rf dist build *.egg-info`
6. Remove mypy cache: `rm -rf .mypy_cache`
7. Remove ruff cache: `rm -rf .ruff_cache`

Report back with:

- List of directories/files removed
- Disk space freed
- Confirmation that working directory is clean
