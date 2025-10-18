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
**Vulnerability Type:** API Key Exposure

**Description:**
The application logs UniFi API keys in plain text when debug
logging is enabled, potentially exposing sensitive authentication information.

**Impact:**
An attacker with access to log files could retrieve the UniFi API key
and gain unauthorized access to the UniFi Cloud API and network infrastructure.

**Reproduction Steps:**
1. Enable debug logging in the configuration
2. Start the MCP server
3. Examine the log output - API key appears in plain text

**Affected Versions:** 0.1.0 - 0.1.3

**Suggested Fix:**
Implement API key masking in the logging module to redact sensitive
information before writing to logs. Show only first 8 characters or use
placeholder text like "API key: ********".
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

- **UniFi API keys** (primary authentication method)
- Passwords
- Private keys
- Certificates
- OAuth tokens
- Session tokens
- Encryption keys
- Database connection strings
- Any `.env` files containing secrets

**DO use environment variables or secure secret management:**

```python
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr

class Settings(BaseSettings):
    """Application settings loaded from environment."""

    unifi_api_key: SecretStr = Field(..., description="UniFi API Key from unifi.ui.com")
    unifi_api_type: str = Field(default="cloud", description="API type: cloud or local")
    unifi_host: str = Field(default="api.ui.com", description="API host")
    unifi_port: int = Field(default=443, description="API port")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Usage with automatic masking
settings = Settings()
# API key is automatically masked when printed
print(f"Using host: {settings.unifi_host}")  # Safe
print(f"API key: {settings.unifi_api_key}")  # Outputs: **********
```

### UniFi API Key Security

**Obtaining API Keys Securely:**

1. Log in to [UniFi Site Manager](https://unifi.ui.com)
2. Navigate to Settings → Control Plane → Integrations
3. Create API Key with a descriptive name
4. **Copy the key immediately** - it's only shown once
5. Store in a password manager or secure secret management system

**API Key Best Practices:**

```python
# ❌ NEVER hardcode API keys
api_key = "abc123def456..."

# ❌ NEVER log full API keys
logging.debug(f"Using API key: {api_key}")

# ✅ DO load from environment
api_key = os.getenv("UNIFI_API_KEY")

# ✅ DO mask in logs (show first 8 chars only)
logging.debug(f"Using API key: {api_key[:8]}..." if api_key else "not set")

# ✅ DO use SecretStr for automatic masking
from pydantic import SecretStr
api_key = SecretStr(os.getenv("UNIFI_API_KEY"))
```

**API Key Rotation:**

- Rotate API keys every 90 days or sooner
- Immediately rotate if a key is exposed or compromised
- Use separate keys for development, staging, and production
- Revoke old keys after rotation
- Document key rotation procedures in your runbooks

**Secure Storage Options:**

- Environment variables (`.env` file, never committed)
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault
- Google Cloud Secret Manager
- Password managers (1Password, LastPass, etc.)

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
- Always use HTTPS for API communications (required for UniFi Cloud API)
- Use API key authentication via `X-API-Key` header
- No session management needed (stateless authentication)
- Store API keys securely using environment variables or secret management

**API Key Headers:**
```python
import httpx
from pydantic import SecretStr

async def make_api_request(api_key: SecretStr, endpoint: str):
    """Make authenticated request to UniFi API."""
    headers = {
        "X-API-Key": api_key.get_secret_value(),  # Only expose when needed
        "Accept": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.ui.com/v1/{endpoint}",
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
```

**Rate Limiting:**
- Respect UniFi API rate limits (100 req/min EA, 10k req/min v1)
- Implement client-side rate limiting
- Add exponential backoff for 429 (rate limit) errors
- Cache frequently accessed data to reduce API calls

**Rate Limit Implementation Example:**
```python
import asyncio
from datetime import datetime, timedelta

class APIRateLimiter:
    """Enforce rate limits for UniFi API."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests = []

    async def acquire(self):
        """Wait if necessary to respect rate limits."""
        now = datetime.now()

        # Remove old requests
        self.requests = [req for req in self.requests if req > now - self.window]

        # Wait if at limit
        if len(self.requests) >= self.max_requests:
            sleep_time = (self.requests[0] + self.window - now).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.requests.append(now)
```

**Error Handling:**
- Never expose API keys in error messages
- Log errors securely without exposing secrets
- Provide user-friendly error messages

```python
import logging

# ❌ BAD - Exposes API key
logging.error(f"Failed to connect with API key: {api_key}")

# ❌ BAD - Shows partial key (still risky)
logging.error(f"Auth failed with key: {api_key[:16]}...")

# ✅ GOOD - No key exposure
logging.error(f"Authentication failed for host '{host}'. Check your UNIFI_API_KEY.")

# ✅ GOOD - Redacted for debugging
logging.debug(f"API key configured: {'yes' if api_key else 'no'}")
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

- **API Key Authentication:** Stateless authentication via official UniFi Cloud API
- **Environment-based Configuration:** API keys stored in environment variables, not in code
- **Secret Masking:** Pydantic SecretStr automatically masks sensitive values
- **Type Safety:** Pydantic models enforce data validation
- **Async Security:** Non-blocking I/O prevents certain timing attacks
- **HTTPS-Only:** Secure communication with UniFi Cloud API (TLS 1.2+)
- **Pre-commit Hooks:** Automated secret detection before commits using detect-secrets
- **Dependency Scanning:** Automated vulnerability scanning with Safety and Bandit
- **Container Security:** Docker images scanned with Trivy
- **Input Validation:** All user inputs validated with Pydantic models

### Planned Security Enhancements

- [ ] Audit logging for all API operations
- [ ] Role-based access control (RBAC) for MCP tools
- [ ] API key rotation automation
- [ ] Request signing for additional security
- [ ] IP allowlist/denylist support
- [ ] Webhook signature verification
- [ ] Enhanced monitoring and alerting for suspicious activity
- [ ] Security headers for HTTP responses
- [ ] Support for multiple API keys with different scopes

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
