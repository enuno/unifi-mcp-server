---
description: Run the full test suite with coverage reporting
---

Run the project's test suite with coverage reporting.

Execute the following commands:

1. Activate the virtual environment if not already active
2. Run pytest with coverage: `pytest --cov=src --cov-report=term-missing --cov-report=html`
3. Display the coverage summary
4. If any tests fail, analyze the failures and suggest fixes
5. Check if coverage meets the 80% minimum threshold

Report back with:
- Number of tests passed/failed
- Overall code coverage percentage
- Any areas with low coverage
- Suggestions for improvement if needed
