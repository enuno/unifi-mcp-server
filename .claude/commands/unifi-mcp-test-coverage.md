---
description: Run tests and analyze coverage gaps by module to reach 80% target
allowed-tools:
  - Bash(pytest:*)
  - Bash(python:*)
  - Bash(python3:*)
  - Bash(/Users/elvis/Library/Python/3.12/bin/pytest:*)
  - Read
  - Grep
  - Glob
author: project
version: 1.0.0
---

Analyze test coverage for the UniFi MCP Server and identify areas needing improvement.

This command runs comprehensive coverage analysis and provides actionable recommendations to reach the 80% coverage target.

**Steps to execute:**

1. Run full test suite with detailed coverage:

   ```bash
   pytest --cov=src --cov-report=term-missing --cov-report=html --cov-report=json -v
   ```

2. Analyze coverage by module:
   - Parse coverage.json to extract per-file coverage percentages
   - Identify modules below 80% threshold
   - Prioritize based on TESTING_PLAN.md priorities

3. Generate coverage gap analysis:
   - List files with coverage < 80%
   - Show missing lines for each file
   - Calculate how many tests needed to reach 80%

4. Read TESTING_PLAN.md to understand priorities:
   - Phase 1 (Critical): API client, config, webhooks
   - Phase 2 (High): Tool modules by usage frequency
   - Phase 3 (Medium): Utility modules
   - Phase 4 (Low): Edge cases and error scenarios

5. Provide actionable recommendations:
   - Which module to focus on next
   - Specific functions/lines that need tests
   - Suggested test scenarios to add
   - Estimated effort (number of tests needed)

6. Compare with previous coverage:
   - Show coverage trend (if available)
   - Highlight improvements or regressions

**Report back with:**

- Current overall coverage percentage
- Coverage by category:
  - API client modules
  - Tool modules (by category)
  - Model modules
  - Utility modules
  - Webhook modules
- Top 5 files needing the most coverage
- Recommended next steps based on TESTING_PLAN.md
- Estimated tests needed to reach 80%

**Example output:**

```
Current Coverage: 34.10%
Target: 80%
Gap: 45.90%

Coverage by Category:
✓ Models: 86.62% (above target)
✗ API Client: 45.23% (needs +34.77%)
✗ Tools: 38.54% (needs +41.46%)
✗ Webhooks: 12.00% (needs +68.00%)

Top Priority Files (from TESTING_PLAN.md Phase 1):
1. src/api/client.py - 45.23% (55 missing lines)
   - Need tests for: rate limiting, error handling, retry logic
2. src/config/settings.py - 60.00% (20 missing lines)
   - Need tests for: environment variable loading, validation
3. src/webhooks/receiver.py - 12.00% (88 missing lines)
   - Need tests for: webhook validation, signature checking

Next Action: Focus on src/api/client.py
Estimated effort: 8-10 test cases
Expected coverage gain: +11.13%
```

**Integration with TESTING_PLAN.md:**

- Reference Phase priorities
- Track completion of milestones
- Suggest updates to the plan based on findings
