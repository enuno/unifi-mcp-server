# AI Agent Guidelines for UniFi MCP Server

This document provides universal rules, workflows, and best practices for all AI coding agents contributing to the UniFi MCP Server project. These guidelines ensure consistency, quality, and security across all AI-assisted development.

## Table of Contents

- [Core Principles](#core-principles)
- [File Structure and Organization](#file-structure-and-organization)
- [Workflow Guidelines](#workflow-guidelines)
- [Do's and Don'ts](#dos-and-donts)
- [Testing Requirements](#testing-requirements)
- [Security Guardrails](#security-guardrails)
- [Code Quality Standards](#code-quality-standards)
- [Documentation Requirements](#documentation-requirements)
- [Approval and Merge Policies](#approval-and-merge-policies)

## Core Principles

All AI agents must adhere to these fundamental principles:

### 1. Safety First

- Never perform destructive operations without explicit confirmation
- Always validate inputs and handle errors gracefully
- Implement proper authentication and authorization checks
- Never commit or expose sensitive data

### 2. Clarity and Transparency

- Write clear, self-documenting code with appropriate comments
- Document all decisions and trade-offs
- Tag AI-generated contributions appropriately
- Explain complex logic in docstrings

### 3. Consistency

- Follow the project's established patterns and conventions
- Maintain consistent code style (enforced by linting tools)
- Use consistent naming conventions throughout the codebase
- Adhere to the project's architecture and design patterns

### 4. Quality Over Speed

- Prioritize correctness and maintainability over quick delivery
- Include comprehensive tests for all code changes
- Ensure code passes all quality checks before submission
- Perform self-review before requesting human review

## File Structure and Organization

### Project Layout

```
unifi-mcp-server/
├── .github/
│   └── workflows/          # CI/CD pipeline definitions
├── src/
│   ├── __init__.py
│   ├── main.py            # MCP server entry point
│   ├── config/            # Configuration management
│   │   ├── __init__.py
│   │   ├── settings.py    # Pydantic settings models
│   │   └── config.yaml    # Default configuration
│   ├── api/               # UniFi API client
│   │   ├── __init__.py
│   │   ├── client.py      # HTTP client wrapper
│   │   └── endpoints.py   # API endpoint definitions
│   ├── tools/             # MCP tool definitions
│   │   ├── __init__.py
│   │   ├── devices.py     # Device management tools
│   │   ├── networks.py    # Network configuration tools
│   │   └── firewall.py    # Firewall rule tools
│   ├── resources/         # MCP resource definitions
│   │   ├── __init__.py
│   │   └── schemas.py     # Resource URI schemas
│   └── utils/             # Utility functions
│       ├── __init__.py
│       └── validators.py  # Input validation helpers
├── tests/
│   ├── __init__.py
│   ├── conftest.py        # Pytest fixtures
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
├── docs/                  # Additional documentation
├── .env.example           # Environment variable template
├── .gitignore
├── .aiignore
├── pyproject.toml
├── README.md
└── ...
```

### File Naming Conventions

- **Python files:** Use `snake_case` (e.g., `device_manager.py`)
- **Classes:** Use `PascalCase` (e.g., `UniFiClient`)
- **Functions/variables:** Use `snake_case` (e.g., `get_devices()`)
- **Constants:** Use `UPPER_SNAKE_CASE` (e.g., `DEFAULT_TIMEOUT`)
- **Test files:** Prefix with `test_` (e.g., `test_device_manager.py`)

## Workflow Guidelines

### Before Starting Work

1. **Understand the Context:**
   - Read relevant documentation (`README.md`, `API.md`, `CONTRIBUTING.md`)
   - Review related issues and pull requests
   - Understand the feature request or bug report completely

2. **Plan Your Approach:**
   - Break down the task into smaller, manageable steps
   - Identify affected files and components
   - Consider potential edge cases and error conditions
   - Plan for comprehensive test coverage

3. **Check Existing Code:**
   - Review similar implementations in the codebase
   - Identify reusable functions and patterns
   - Ensure your approach is consistent with existing code

### During Development

1. **Write Code Incrementally:**
   - Implement one feature or fix at a time
   - Test each change before moving to the next
   - Commit logical units of work separately

2. **Follow TDD (Test-Driven Development):**
   - Write tests first when possible
   - Ensure tests fail before implementing the feature
   - Verify tests pass after implementation
   - Maintain minimum 80% code coverage

3. **Document as You Go:**
   - Add docstrings to all public functions and classes
   - Update relevant documentation files
   - Add inline comments for complex logic
   - Keep `API.md` updated for new MCP tools/resources

### After Implementation

1. **Self-Review:**
   - Review your own code critically
   - Ensure all tests pass: `pytest`
   - Run linting and formatting: `pre-commit run --all-files`
   - Check for security issues: `bandit -r src/`

2. **Create a Pull Request:**
   - Write a clear, descriptive PR title (conventional commits format)
   - Fill out the PR template completely
   - Link related issues
   - Tag the PR as AI-assisted
   - Request human review

3. **Respond to Feedback:**
   - Address all review comments
   - Make requested changes promptly
   - Explain decisions when necessary
   - Re-request review after making changes

## Do's and Don'ts

### Do's ✅

- **DO** validate all user inputs
- **DO** handle errors gracefully with try/except blocks
- **DO** use type hints for all function signatures
- **DO** write comprehensive docstrings
- **DO** add tests for all new code
- **DO** use async/await for I/O-bound operations
- **DO** centralize API interactions in dedicated modules
- **DO** use environment variables for configuration
- **DO** log important events and errors appropriately
- **DO** follow the principle of least privilege
- **DO** ask for clarification when requirements are unclear
- **DO** use Pydantic models for data validation
- **DO** keep functions small and focused (single responsibility)
- **DO** reuse existing code when possible

### Don'ts ❌

- **DON'T** commit credentials, API keys, or secrets
- **DON'T** merge code without human approval
- **DON'T** skip writing tests
- **DON'T** ignore linting errors or warnings
- **DON'T** expose sensitive information in logs or error messages
- **DON'T** make breaking changes without discussion
- **DON'T** copy-paste code - create reusable functions instead
- **DON'T** use bare except clauses - catch specific exceptions
- **DON'T** hardcode values that should be configurable
- **DON'T** submit incomplete or experimental code to main
- **DON'T** bypass security checks or pre-commit hooks
- **DON'T** write code without understanding its purpose
- **DON'T** use deprecated libraries or functions
- **DON'T** ignore type errors from MyPy

## Testing Requirements

### Test Coverage

All AI-generated code must include tests:

- **Minimum Coverage:** 80% overall
- **New Features:** 100% coverage of new code paths
- **Bug Fixes:** Regression tests for the fixed bug
- **Refactoring:** Maintain or improve existing coverage

### Test Types

1. **Unit Tests:**

   ```python
   import pytest
   from src.api.client import UniFiClient

   @pytest.mark.unit
   async def test_client_initialization():
       """Test that UniFi client initializes correctly."""
       client = UniFiClient(
           api_key="test-api-key",
           api_type="cloud",
           host="api.ui.com"
       )
       assert client.host == "api.ui.com"
       assert client.api_type == "cloud"
       assert client.api_key == "test-api-key"
   ```

2. **Integration Tests:**

   ```python
   import pytest

   @pytest.mark.integration
   async def test_get_devices_from_real_api():
       """Test fetching devices from real UniFi Cloud API."""
       # This test requires UNIFI_API_KEY environment variable
       client = UniFiClient.from_env()
       devices = await client.get_devices()
       assert isinstance(devices, list)
   ```

3. **Mock Tests:**

   ```python
   from unittest.mock import AsyncMock, patch

   @pytest.mark.unit
   async def test_get_devices_handles_error():
       """Test error handling when API fails."""
       with patch('src.api.client.httpx.AsyncClient.get') as mock_get:
           mock_get.side_effect = httpx.HTTPError("Connection failed")
           client = UniFiClient(
               api_key="test-key",
               host="api.ui.com",
               api_type="cloud"
           )
           with pytest.raises(APIError):
               await client.get_devices()
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Run only unit tests
pytest -m unit

# Run only integration tests (requires UniFi controller)
pytest -m integration

# Run specific test file
pytest tests/unit/test_client.py

# Run tests matching pattern
pytest -k "test_device"
```

## Security Guardrails

### Credential Management

**NEVER include API keys or credentials in code:**

```python
# ❌ BAD - Hardcoded API key
client = UniFiClient(
    api_key="abc123def456ghi789...",
    host="api.ui.com"
)

# ✅ GOOD - Load from environment
from src.config.settings import Settings

settings = Settings()  # Loads from environment
client = UniFiClient(
    api_key=settings.unifi_api_key,
    host=settings.unifi_host,
    api_type=settings.unifi_api_type
)
```

### Input Validation

Always validate and sanitize inputs:

```python
from pydantic import BaseModel, Field, validator

class NetworkConfig(BaseModel):
    name: str = Field(..., min_length=1, max_length=32)
    vlan_id: int = Field(..., ge=1, le=4094)
    subnet: str

    @validator('subnet')
    def validate_subnet(cls, v):
        import ipaddress
        try:
            ipaddress.ip_network(v)
        except ValueError:
            raise ValueError('Invalid subnet format')
        return v
```

### Error Handling

Don't expose sensitive information in errors:

```python
# ❌ BAD - Exposes API key in logs
logging.error(f"Auth failed with API key: {api_key}")

# ✅ GOOD - Safe error message
logging.error(f"Authentication failed for host '{host}' (API key: {api_key[:8]}...)")

# ✅ EVEN BETTER - No key exposure
logging.error(f"Authentication failed for host '{host}'. Check your UNIFI_API_KEY.")
```

### Secret Detection

Pre-commit hooks will prevent committing secrets:

```bash
# Initialize pre-commit
pre-commit install

# Manually check for secrets
detect-secrets scan
```

## UniFi API Guidelines

### Authentication with API Keys

This project uses the **official UniFi Cloud API** with API key authentication. All AI agents must follow these guidelines:

**Authentication Method:**

- Use `UNIFI_API_KEY` environment variable for authentication
- API key is passed via the `X-API-Key` HTTP header
- No session management or cookies required (stateless authentication)

**NEVER hardcode API keys:**

```python
# ❌ BAD - Hardcoded API key
headers = {
    "X-API-Key": "abc123def456..."
}

# ✅ GOOD - Load from environment
from src.config.settings import Settings

settings = Settings()
headers = {
    "X-API-Key": settings.unifi_api_key
}
```

### API Access Modes

Support both cloud and local gateway access modes:

**Cloud API (Default):**

```python
# Base URL: https://api.ui.com/v1/
settings.unifi_api_type = "cloud"
settings.unifi_host = "api.ui.com"
settings.unifi_port = 443
```

**Local Gateway Proxy:**

```python
# Base URL: https://{gateway-ip}/proxy/network/integration/v1/
settings.unifi_api_type = "local"
settings.unifi_host = "192.168.1.1"
settings.unifi_port = 443
```

### Read-Only Limitation

**IMPORTANT:** The Early Access API is currently **read-only**.

```python
# ✅ ALLOWED - Read operations
async def list_devices(site_id: str):
    """List all devices - read operation."""
    devices = await client.get(f"/v1/sites/{site_id}/devices")
    return devices

# ❌ NOT AVAILABLE - Write operations (will fail)
async def create_network(name: str, vlan_id: int):
    """Create network - not yet supported in EA API."""
    # This will return 403 Forbidden in current API version
    raise NotImplementedError(
        "Write operations are not available in the Early Access API. "
        "This feature will be available in v1 Stable release."
    )
```

**Handling write requests:**

- Document that write operations are not yet available
- Return clear error messages to users
- Consider implementing a "preview" mode that shows what would be created
- Monitor UniFi API release notes for v1 Stable availability

### Rate Limiting Considerations

Implement proper rate limiting to respect API limits:

**Current Limits:**

- Early Access: 100 requests/minute
- v1 Stable (future): 10,000 requests/minute

**Implementation Example:**

```python
import asyncio
from collections import deque
from datetime import datetime, timedelta

class UniFiRateLimiter:
    """Rate limiter for UniFi API requests."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests = deque()

    async def acquire(self):
        """Wait if necessary to respect rate limits."""
        now = datetime.now()

        # Remove old requests outside the window
        while self.requests and self.requests[0] < now - self.window:
            self.requests.popleft()

        # Wait if at limit
        if len(self.requests) >= self.max_requests:
            sleep_time = (self.requests[0] + self.window - now).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.requests.append(now)
```

**Best Practices:**

- Cache frequently accessed data (devices, sites, networks)
- Batch operations when possible
- Implement exponential backoff for 429 errors
- Use configurable rate limits via `UNIFI_RATE_LIMIT` environment variable
- Log rate limit warnings for monitoring

### API Error Handling

Handle UniFi API-specific errors gracefully:

```python
import httpx
from typing import Dict, Any

class UniFiAPIError(Exception):
    """Base exception for UniFi API errors."""
    pass

class UniFiAuthenticationError(UniFiAPIError):
    """Authentication failed - invalid API key."""
    pass

class UniFiRateLimitError(UniFiAPIError):
    """Rate limit exceeded."""
    pass

async def safe_api_request(
    client: httpx.AsyncClient,
    method: str,
    endpoint: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Make a safe API request with proper error handling.

    Args:
        client: HTTP client
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint
        **kwargs: Additional request parameters

    Returns:
        Response data as dictionary

    Raises:
        UniFiAuthenticationError: Invalid API key
        UniFiRateLimitError: Rate limit exceeded
        UniFiAPIError: Other API errors
    """
    try:
        response = await client.request(method, endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise UniFiAuthenticationError(
                "Invalid API key. Please check your UNIFI_API_KEY."
            )
        elif e.response.status_code == 429:
            retry_after = e.response.headers.get("Retry-After", 60)
            raise UniFiRateLimitError(
                f"Rate limit exceeded. Retry after {retry_after} seconds."
            )
        else:
            raise UniFiAPIError(f"API error: {e.response.status_code}")

    except httpx.RequestError as e:
        raise UniFiAPIError(f"Request failed: {str(e)}")
```

### Official API Documentation

Always reference the official UniFi API documentation:

**Primary Resources:**

- **Getting Started**: [https://developer.ui.com/site-manager-api/gettingstarted](https://developer.ui.com/site-manager-api/gettingstarted)
- **Project Reference**: `docs/UNIFI_API.md` (comprehensive guide)
- **API Tutorial**: [https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access](https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access)

**When implementing new features:**

1. Review official API documentation first
2. Check `docs/UNIFI_API.md` for project-specific guidance
3. Ensure endpoint paths match official specifications
4. Test against real UniFi Cloud API or gateway proxy
5. Document any API limitations or quirks discovered

### API Key Security Checklist

Before committing code, verify:

- [ ] No hardcoded API keys in source code
- [ ] API key loaded from environment variables
- [ ] No API keys in log messages (even debug logs)
- [ ] API keys redacted in error messages
- [ ] `.env` file in `.gitignore`
- [ ] `.env.example` has placeholder, not real key
- [ ] Pre-commit hooks detect-secrets passing
- [ ] Documentation mentions API key security

## Code Quality Standards

### Type Hints

All functions must have type hints:

```python
from typing import List, Dict, Optional
import httpx

async def get_devices(
    client: httpx.AsyncClient,
    site_id: str = "default"
) -> List[Dict[str, Any]]:
    """Fetch devices from UniFi controller."""
    response = await client.get(f"/api/s/{site_id}/stat/device")
    return response.json()["data"]
```

### Docstrings

Use Google-style docstrings:

```python
def calculate_network_capacity(
    bandwidth_mbps: int,
    devices: int,
    overhead_percent: float = 0.2
) -> float:
    """
    Calculate available bandwidth per device.

    Args:
        bandwidth_mbps: Total bandwidth in Mbps
        devices: Number of connected devices
        overhead_percent: Network overhead as decimal (default: 0.2 for 20%)

    Returns:
        Available bandwidth per device in Mbps

    Raises:
        ValueError: If bandwidth or devices is less than 1

    Example:
        >>> calculate_network_capacity(100, 10)
        8.0
    """
    if bandwidth_mbps < 1 or devices < 1:
        raise ValueError("Bandwidth and devices must be positive")

    available = bandwidth_mbps * (1 - overhead_percent)
    return available / devices
```

### Code Formatting

Code is automatically formatted by pre-commit hooks:

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
ruff check src/ tests/ --fix
```

## Documentation Requirements

### Code Documentation

- **All public functions:** Require docstrings
- **Complex logic:** Add inline comments
- **Type hints:** Required for all functions
- **Examples:** Include in docstrings when helpful

### Project Documentation

Update relevant documentation files:

- `README.md` - For user-facing changes
- `API.md` - For new MCP tools or resources
- `CONTRIBUTING.md` - For workflow changes
- `SECURITY.md` - For security-related changes

### API Documentation

When adding new MCP tools, document in `API.md`:

```markdown
### get_device

Retrieve information about a specific UniFi device.

**Parameters:**
- `mac_address` (string, required): Device MAC address
- `site_id` (string, optional): Site identifier (default: "default")

**Returns:**
Object containing device information

**Example:**
\`\`\`python
result = await mcp.call_tool("get_device", {
    "mac_address": "aa:bb:cc:dd:ee:ff",
    "site_id": "default"
})
\`\`\`
```

## Approval and Merge Policies

### Auto-Merge Restrictions

AI agents **MUST NOT**:

- Automatically merge pull requests
- Bypass code review requirements
- Push directly to the `main` branch
- Override branch protection rules
- Disable or skip CI/CD checks

### Required Approvals

All AI-generated code requires:

- At least one human reviewer approval
- All CI/CD checks passing
- No unresolved review comments
- Up-to-date with the `main` branch

### Human-in-the-Loop

Critical changes require additional human review:

- Security-related code
- Authentication/authorization logic
- Data deletion or modification
- API contract changes
- Database schema changes
- Configuration changes affecting production

### Tagging AI Contributions

Mark AI-assisted PRs in the description:

```markdown
## AI Assistance

This PR was created with assistance from Claude Code.

**Human Review Status:** ✅ Reviewed and approved by @username
**Test Coverage:** 95%
**Security Review:** Completed
```

## Special Considerations

### MCP-Specific Guidelines

When implementing MCP tools and resources:

```python
from fastmcp import FastMCP

mcp = FastMCP("UniFi Network")

@mcp.tool()
async def get_devices(site_id: str = "default") -> list:
    """
    Get all devices for a site.

    Args:
        site_id: Site identifier (default: "default")

    Returns:
        List of device objects
    """
    # Implementation
    pass

@mcp.resource("sites://{site_id}/devices")
async def list_site_devices(site_id: str) -> str:
    """List all devices in a site."""
    # Return JSON string of devices
    pass
```

### UniFi API Integration

Centralize API calls in dedicated modules:

```python
# src/api/client.py
class UniFiClient:
    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make authenticated request to UniFi API.

        Handles authentication, retries, and error handling.
        """
        # Centralized implementation
        pass
```

## Conclusion

By following these guidelines, AI agents can contribute effectively to the UniFi MCP Server project while maintaining high standards of quality, security, and maintainability.

**Remember:** When in doubt, ask for human guidance. It's better to request clarification than to make assumptions that could introduce bugs or security issues.

---

**Last Updated:** 2025-10-17

For additional guidance, see:

- `AI_CODING_ASSISTANT.md` - Project-specific AI guidelines
- `AI_GIT_PRACTICES.md` - AI-specific Git practices
- `CONTRIBUTING.md` - General contribution guidelines
- `SECURITY.md` - Security policies
