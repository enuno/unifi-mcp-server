# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

**Note:** As this project is in early development (pre-1.0), we recommend always using the latest version.

## Reporting a Vulnerability

We take the security of the UniFi MCP Server seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### Please DO NOT

- Open a public GitHub issue for security vulnerabilities
- Disclose the vulnerability publicly before it has been addressed
- Exploit the vulnerability beyond the minimum necessary to demonstrate the issue

### Please DO

**Report security vulnerabilities via GitHub Security Advisories:**

1. Go to the repository's Security tab
2. Click "Report a vulnerability"
3. Fill out the vulnerability report form with as much detail as possible

**Alternatively, you can email the maintainers directly at:**

- security@homelab.local (replace with actual contact)

### What to Include in Your Report

Please include the following information in your report:

- **Description:** A clear description of the vulnerability
- **Impact:** What an attacker could achieve by exploiting this vulnerability
- **Reproduction Steps:** Step-by-step instructions to reproduce the vulnerability
- **Affected Versions:** Which versions of the project are affected
- **Suggested Fix:** If you have suggestions for how to fix the vulnerability, please include them
- **Your Contact Information:** So we can follow up with questions if needed

### Example Report

```
**Vulnerability Type:** Credential Exposure

**Description:**
The application logs UniFi controller credentials in plain text when debug
logging is enabled, potentially exposing sensitive authentication information.

**Impact:**
An attacker with access to log files could retrieve UniFi controller credentials
and gain unauthorized access to the network infrastructure.

**Reproduction Steps:**
1. Enable debug logging in the configuration
2. Start the MCP server
3. Examine the log output - credentials appear in plain text

**Affected Versions:** 0.1.0 - 0.1.3

**Suggested Fix:**
Implement credential masking in the logging module to redact sensitive
information before writing to logs.
```

## Response Timeline

We aim to respond to security vulnerability reports according to the following timeline:

- **Initial Response:** Within 48 hours of receiving the report
- **Vulnerability Assessment:** Within 7 days, we will provide an assessment of the vulnerability
- **Fix Development:** Critical vulnerabilities will be addressed within 30 days
- **Public Disclosure:** After a fix is released and users have had time to update (typically 7-14 days)

## Security Best Practices for Contributors

### Credential Management

**NEVER commit credentials or secrets to the repository:**

- API keys
- Passwords
- Private keys
- Certificates
- OAuth tokens
- Session tokens
- Encryption keys

**DO use environment variables or secure secret management:**

```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    unifi_username: str
    unifi_password: str
    unifi_host: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### Input Validation

Always validate and sanitize user inputs:

```python
from pydantic import BaseModel, validator, Field

class DeviceConfig(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    mac_address: str

    @validator('mac_address')
    def validate_mac(cls, v):
        # Validate MAC address format
        import re
        if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', v):
            raise ValueError('Invalid MAC address format')
        return v.lower()
```

### API Security

**Authentication:**
- Always use HTTPS for API communications
- Implement proper session management
- Use secure token storage

**Rate Limiting:**
- Implement rate limiting to prevent abuse
- Add exponential backoff for failed authentication attempts

**Error Handling:**
- Never expose sensitive information in error messages
- Log errors securely without exposing credentials

```python
import logging

# BAD - Exposes credentials
logging.error(f"Failed to connect to {host} with user {username} and password {password}")

# GOOD - Masks sensitive data
logging.error(f"Failed to connect to {host} with user {username}")
```

### Dependency Security

**Regular Updates:**
- Keep all dependencies up to date
- Review security advisories for dependencies
- Use automated dependency scanning tools

**Vulnerability Scanning:**

Our CI/CD pipeline includes automated security scanning:

```bash
# Check for known vulnerabilities in dependencies
safety check

# Security linting with Bandit
bandit -r src/

# Docker image scanning
trivy image unifi-mcp-server:latest
```

**Manual Security Checks:**

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run security checks
safety check
bandit -r src/ -f json -o bandit-report.json

# Check for outdated packages with vulnerabilities
pip list --outdated
```

### AI-Specific Security Considerations

When using AI coding assistants:

1. **Review All AI-Generated Code:** Never merge AI-generated code without human review
2. **Validate Security-Critical Code:** Extra scrutiny for authentication, authorization, and data handling
3. **Test Generated Code:** Ensure comprehensive test coverage for AI contributions
4. **Audit AI Permissions:** Limit AI assistant access to only necessary resources
5. **Monitor AI Changes:** Track and review all AI-contributed changes in version control

See `AI_GIT_PRACTICES.md` and `AGENTS.md` for additional AI security guidelines.

### Docker Security

**Image Security:**
- Use official base images from trusted sources
- Keep base images updated
- Run containers as non-root users
- Scan images for vulnerabilities

**Example Secure Dockerfile:**

```dockerfile
FROM python:3.10-slim

# Create non-root user
RUN useradd -m -u 1000 mcpuser

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=mcpuser:mcpuser . .

# Switch to non-root user
USER mcpuser

# Run application
CMD ["python", "src/main.py"]
```

## Security Features

### Current Security Features

- **Environment-based Configuration:** Secrets stored in environment variables, not in code
- **Type Safety:** Pydantic models enforce data validation
- **Async Security:** Non-blocking I/O prevents certain timing attacks
- **HTTPS Support:** Secure communication with UniFi controllers
- **Pre-commit Hooks:** Automated secret detection before commits

### Planned Security Enhancements

- [ ] OAuth 2.0 support for authentication
- [ ] Audit logging for all operations
- [ ] Role-based access control (RBAC) for MCP tools
- [ ] Rate limiting for API endpoints
- [ ] Encrypted credential storage
- [ ] Security headers for HTTP responses

## Security Audit History

| Date       | Type          | Findings | Status   |
|------------|---------------|----------|----------|
| 2025-10-17 | Initial Setup | N/A      | Baseline |

## Compliance and Standards

This project strives to follow:

- **OWASP Top 10:** Web application security best practices
- **CWE Top 25:** Common weakness enumeration
- **NIST Guidelines:** Cybersecurity framework recommendations
- **Secure Coding Standards:** For Python development

## Security Contacts

For security-related questions or concerns:

- **Security Team:** security@homelab.local
- **Project Maintainer:** elvis@homelab.local
- **GitHub Security:** Use GitHub Security Advisories

## Acknowledgments

We appreciate the security research community and recognize contributors who responsibly disclose vulnerabilities:

<!-- Add acknowledged security researchers here -->

## Additional Resources

- [OWASP Python Security](https://owasp.org/www-project-python-security/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security)

---

**Last Updated:** 2025-10-17

Thank you for helping keep UniFi MCP Server and its users safe!
