---
description: Run security scans and vulnerability checks
---

Run comprehensive security scans on the project.

Execute the following security checks:

1. Bandit security linter: `bandit -r src/ -ll`
2. Safety dependency vulnerability check: `safety check`
3. Check for secrets in code: `detect-secrets scan --baseline .secrets.baseline`
4. Review .env.example to ensure no credentials are exposed

Report back with:

- Any security vulnerabilities found
- Severity levels (LOW, MEDIUM, HIGH, CRITICAL)
- Recommended remediation steps
- Dependencies that need updating
- Overall security posture assessment
