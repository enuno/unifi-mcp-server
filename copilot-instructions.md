# GitHub Copilot Instructions for UniFi MCP Server

## Project Overview

This is a Model Context Protocol (MCP) server that provides AI agents with access to UniFi Network Controller infrastructure. The project emphasizes **safety, security, and type safety** with comprehensive testing and validation.

**Tech Stack:**
- Python 3.10+ with async/await patterns
- FastMCP framework for MCP protocol implementation
- Pydantic v2 for validation and type safety
- Redis for optional caching
- Docker multi-architecture support (amd64, arm64, arm/v7, arm64/v8)

## Core Architecture Principles

### 1. Safety-First Design
All mutating operations MUST include:
- `confirm: bool = False` parameter (must be explicitly set to `True`)
- `dry_run: bool = False` parameter for preview mode
- Comprehensive input validation with detailed error messages
- Audit logging to `audit.log` for all operations

Example:
```python
async def delete_firewall_rule(
    site_id: str,
    rule_id: str,
    confirm: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    if not confirm and not dry_run:
        raise ValueError("Must set confirm=True or dry_run=True")

    if dry_run:
        return {"status": "preview", "action": "would_delete", "rule_id": rule_id}

    # Log to audit.log before execution
    logger.info(f"Deleting firewall rule {rule_id} in site {site_id}")
    # ... actual deletion
```

### 2. Type Safety & Validation
- Use Pydantic v2 models for ALL data structures
- Leverage `Annotated` types with validators
- Use `Field()` for documentation and constraints
- Implement custom validators for complex business logic

Example:
```python
from pydantic import BaseModel, Field, field_validator
from typing import Annotated

class NetworkConfig(BaseModel):
    """Network configuration with validation."""
    name: Annotated[str, Field(min_length=1, max_length=32)]
    vlan_id: Annotated[int, Field(ge=1, le=4094)]
    cidr: str
    dhcp_enabled: bool = True

    @field_validator('cidr')
    @classmethod
    def validate_cidr(cls, v: str) -> str:
        """Validate CIDR notation."""
        import ipaddress
        try:
            ipaddress.ip_network(v)
        except ValueError:
            raise ValueError(f"Invalid CIDR notation: {v}")
        return v
```

### 3. Async Patterns
- All API calls and I/O operations use `async/await`
- Use `asyncio.gather()` for concurrent operations
- Implement proper error handling with async context managers
- Rate limiting with `asyncio.Semaphore`

Example:
```python
async def fetch_multiple_sites(site_ids: list[str]) -> list[dict]:
    """Fetch multiple sites concurrently with rate limiting."""
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

    async def fetch_one(site_id: str) -> dict:
        async with semaphore:
            return await api.get_site(site_id)

    return await asyncio.gather(*[fetch_one(sid) for sid in site_ids])
```

### 4. MCP Tool Structure
Each tool should follow this pattern:

```python
@mcp.tool()
async def tool_name(
    site_id: str,
    # ... other parameters
    dry_run: bool = False,
    confirm: bool = False  # For mutating operations only
) -> ToolResponse:
    """
    Brief description.

    Args:
        site_id: UniFi site identifier (e.g., 'default')
        dry_run: Preview changes without applying them
        confirm: Required for mutating operations (must be True)

    Returns:
        Dictionary containing operation results

    Raises:
        ValueError: For invalid parameters or missing confirmation
        UniFiAPIError: For API-related errors
    """
    # 1. Input validation
    validate_site_id(site_id)

    # 2. Safety check for mutating operations
    if is_mutating_operation and not confirm and not dry_run:
        raise ValueError("Must set confirm=True or dry_run=True")

    # 3. Cache check (if applicable)
    if cached_data := await cache.get(cache_key):
        return cached_data

    # 4. Dry-run preview
    if dry_run:
        return {"status": "preview", "action": "would_perform", ...}

    # 5. Audit logging
    logger.info(f"Executing {tool_name} for site {site_id}")

    # 6. API call with error handling
    try:
        result = await api.call(...)
    except UniFiAPIError as e:
        logger.error(f"API error: {e}")
        raise

    # 7. Cache invalidation (if applicable)
    await cache.invalidate_related(cache_keys)

    # 8. Return typed response
    return ToolResponse.model_validate(result)
```

### 5. Testing Requirements
- **Minimum 80% code coverage** for new code
- Unit tests for all tools using pytest and pytest-asyncio
- Mock UniFi API responses with realistic data
- Test both success and failure scenarios
- Test safety mechanisms (confirm, dry_run)

Example test structure:
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_create_network_success():
    """Test successful network creation."""
    mock_api = AsyncMock()
    mock_api.create_network.return_value = {"_id": "123", "name": "TestNet"}

    with patch('src.api.client.UniFiAPI', return_value=mock_api):
        result = await create_network(
            site_id="default",
            name="TestNet",
            vlan_id=100,
            cidr="10.0.100.0/24",
            confirm=True
        )

    assert result["name"] == "TestNet"
    mock_api.create_network.assert_called_once()

@pytest.mark.asyncio
async def test_create_network_requires_confirmation():
    """Test that mutating operations require confirmation."""
    with pytest.raises(ValueError, match="Must set confirm=True"):
        await create_network(
            site_id="default",
            name="TestNet",
            vlan_id=100,
            cidr="10.0.100.0/24"
            # confirm=False (default)
        )
```

## Code Organization

### File Structure
```
src/
├── main.py              # MCP server registration and startup
├── config/              # Configuration management
│   ├── settings.py      # Environment-based settings (Pydantic Settings)
│   └── constants.py     # Constants and enums
├── api/                 # UniFi API client
│   ├── client.py        # Async API client with rate limiting
│   ├── endpoints.py     # API endpoint definitions
│   └── exceptions.py    # Custom exceptions
├── tools/               # MCP tool implementations (one file per domain)
│   ├── devices.py       # Device management tools
│   ├── clients.py       # Client management tools
│   ├── networks.py      # Network configuration tools
│   ├── firewall.py      # Firewall rule tools
│   ├── wifi.py          # WiFi/SSID management tools
│   └── dpi.py           # DPI statistics tools
├── resources/           # MCP resource handlers
│   └── handlers.py      # Resource URI handlers
├── models/              # Pydantic models
│   ├── device.py        # Device models
│   ├── network.py       # Network models
│   └── responses.py     # Common response models
├── webhooks/            # Webhook receiver and handlers
│   ├── receiver.py      # FastAPI webhook endpoint
│   ├── handlers.py      # Event handlers
│   └── validators.py    # HMAC signature validation
├── cache.py             # Redis caching implementation
└── utils/               # Utility functions
    ├── validators.py    # Input validation helpers
    ├── formatters.py    # Response formatting
    └── logging.py       # Logging configuration
```

### Naming Conventions
- **Tools**: `verb_noun` (e.g., `list_devices`, `create_network`, `delete_firewall_rule`)
- **Models**: `PascalCase` (e.g., `DeviceInfo`, `NetworkConfig`)
- **Functions**: `snake_case` (e.g., `validate_cidr`, `format_bandwidth`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CACHE_TTL`, `MAX_VLAN_ID`)

## Security Best Practices

### 1. Input Validation
```python
# Always validate external input
def validate_vlan_id(vlan_id: int) -> None:
    if not 1 <= vlan_id <= 4094:
        raise ValueError(f"VLAN ID must be 1-4094, got {vlan_id}")

def validate_site_id(site_id: str) -> None:
    if not site_id or not site_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"Invalid site_id: {site_id}")
```

### 2. Sensitive Data Handling
```python
# Mask sensitive data in logs
def mask_sensitive_data(data: dict) -> dict:
    """Mask passwords, API keys, and other sensitive fields."""
    sensitive_keys = {"password", "api_key", "x_password", "secret"}

    return {
        k: "***REDACTED***" if k.lower() in sensitive_keys else v
        for k, v in data.items()
    }

# Use in logging
logger.info(f"API call: {mask_sensitive_data(params)}")
```

### 3. Error Handling
```python
# Never expose internal details in error messages
try:
    result = await api.call_endpoint()
except Exception as e:
    # Log full error internally
    logger.error(f"Internal error: {e}", exc_info=True)

    # Return sanitized error to user
    raise UniFiAPIError("Failed to complete operation. Check logs for details.")
```

## Redis Caching Patterns

### Cache Keys
Use hierarchical keys with TTL differentiation:
```python
# Format: resource_type:site_id:identifier
CACHE_KEYS = {
    "device": "devices:{site_id}:{device_id}",      # 5 min TTL
    "devices": "devices:{site_id}:all",             # 2 min TTL
    "network": "networks:{site_id}:{network_id}",   # 10 min TTL
    "clients": "clients:{site_id}:all",             # 1 min TTL
    "stats": "stats:{site_id}:{device_id}",         # 30 sec TTL
}
```

### Cache Invalidation
```python
async def invalidate_network_cache(site_id: str, network_id: str = None) -> None:
    """Invalidate network-related cache entries."""
    patterns = [
        f"networks:{site_id}:all",
        f"sites:{site_id}:networks",
    ]

    if network_id:
        patterns.append(f"networks:{site_id}:{network_id}")

    await cache.delete_many(patterns)
```

## Documentation Standards

### Docstrings
Use Google-style docstrings with type information:
```python
async def create_firewall_rule(
    site_id: str,
    name: str,
    action: str,
    protocol: str,
    src_address: str,
    dst_address: str,
    dst_port: Optional[str] = None,
    enabled: bool = True,
    confirm: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Create a new firewall rule in the UniFi controller.

    This tool creates Layer 3/4 firewall rules with support for:
    - Source/destination IP filtering (CIDR notation)
    - Protocol filtering (TCP, UDP, ICMP, or all)
    - Port-based filtering
    - Accept/Drop/Reject actions

    Args:
        site_id: UniFi site identifier (e.g., 'default')
        name: Human-readable rule name (max 64 chars)
        action: Rule action - 'accept', 'drop', or 'reject'
        protocol: Network protocol - 'tcp', 'udp', 'icmp', or 'all'
        src_address: Source IP/CIDR (e.g., '192.168.1.0/24' or 'any')
        dst_address: Destination IP/CIDR (e.g., '10.0.0.1' or 'any')
        dst_port: Destination port or range (e.g., '80' or '8080-8090')
        enabled: Whether the rule is active (default: True)
        confirm: Must be True to create the rule (safety check)
        dry_run: Preview the rule without creating it

    Returns:
        Dictionary containing:
            - _id: Unique rule identifier
            - name: Rule name
            - action: Configured action
            - enabled: Rule status
            - ruleset: Associated ruleset name

    Raises:
        ValueError: If parameters are invalid or confirm=True not set
        UniFiAPIError: If the UniFi API request fails

    Example:
        >>> result = await create_firewall_rule(
        ...     site_id="default",
        ...     name="Block External SSH",
        ...     action="drop",
        ...     protocol="tcp",
        ...     src_address="any",
        ...     dst_address="192.168.1.0/24",
        ...     dst_port="22",
        ...     confirm=True
        ... )
        >>> print(result["_id"])
        '507f1f77bcf86cd799439011'
    """
```

### README Updates
When adding new features:
1. Update feature list in README.md
2. Add examples to API.md
3. Update DEVELOPMENT_PLAN.md roadmap
4. Document breaking changes in CHANGELOG.md

## Git Commit Practices

Follow Conventional Commits:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, no code change
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```bash
feat(tools): add WiFi/SSID management tools

- Implement create_wlan with WPA2/WPA3 support
- Add VLAN isolation for guest networks
- Include comprehensive input validation

Closes #42

---

fix(cache): prevent race condition in cache invalidation

The previous implementation could miss invalidations during
concurrent updates. Now uses Redis WATCH for atomic operations.

Fixes #58

---

test(dpi): add unit tests for DPI statistics tools

- Test top applications ranking
- Test bandwidth calculation
- Test time range filtering
- Achieve 87% coverage for dpi.py

Part of #65
```

## AI Coding Assistant Guidelines

### When to Suggest Refactoring
- Code duplication across 3+ locations → extract to utility function
- Function length > 50 lines → consider breaking into smaller functions
- Cyclomatic complexity > 10 → simplify logic or add early returns
- Missing type hints → add comprehensive type annotations
- Hard-coded values → extract to constants or configuration

### When NOT to Refactor
- Working code with 80%+ test coverage (unless fixing a bug)
- Code that follows existing patterns (maintain consistency)
- Performance-critical sections (profile before optimizing)

### Code Review Checklist
Before suggesting a PR, verify:
- [ ] All new functions have type hints and docstrings
- [ ] Unit tests added for new functionality (80%+ coverage)
- [ ] Safety mechanisms (confirm, dry_run) for mutating operations
- [ ] Audit logging for operations
- [ ] Input validation with clear error messages
- [ ] Cache invalidation logic (if applicable)
- [ ] README/API.md updated with examples
- [ ] pre-commit hooks pass
- [ ] No hardcoded credentials or sensitive data

## Common Patterns

### Error Response Format
```python
class ErrorResponse(BaseModel):
    """Standardized error response."""
    error: str
    error_type: str
    details: Optional[Dict[str, Any]] = None

    @classmethod
    def validation_error(cls, field: str, message: str) -> "ErrorResponse":
        return cls(
            error=f"Validation failed for {field}",
            error_type="ValidationError",
            details={"field": field, "message": message}
        )
```

### Resource URI Handlers
```python
# Format: sites://{site_id}/{resource_type}/{identifier}
@mcp.resource("sites://{site_id}/devices/{device_id}")
async def get_device_resource(uri: str) -> Resource:
    """Handle device resource requests."""
    match = re.match(r"sites://([^/]+)/devices/([^/]+)", uri)
    if not match:
        raise ValueError(f"Invalid URI format: {uri}")

    site_id, device_id = match.groups()
    device = await api.get_device(site_id, device_id)

    return Resource(
        uri=uri,
        name=device["name"],
        mimeType="application/json",
        text=json.dumps(device, indent=2)
    )
```

### Rate Limiting
```python
from asyncio import Semaphore

class RateLimiter:
    """Rate limiter using token bucket algorithm."""

    def __init__(self, max_calls: int, period: float):
        self.semaphore = Semaphore(max_calls)
        self.period = period

    async def acquire(self):
        async with self.semaphore:
            await asyncio.sleep(self.period / self.semaphore._value)
```

## Performance Considerations

### Batch Operations
```python
async def batch_restart_devices(
    site_id: str,
    device_ids: list[str],
    confirm: bool = False
) -> list[Dict[str, Any]]:
    """Restart multiple devices concurrently with rate limiting."""
    if not confirm:
        raise ValueError("Must set confirm=True")

    # Limit to 5 concurrent restarts
    semaphore = asyncio.Semaphore(5)

    async def restart_one(device_id: str) -> Dict[str, Any]:
        async with semaphore:
            return await restart_device(site_id, device_id, confirm=True)

    return await asyncio.gather(
        *[restart_one(did) for did in device_ids],
        return_exceptions=True  # Don't fail entire batch on single error
    )
```

### Database Query Optimization
```python
# Prefer: Single query with filtering
devices = await api.get_devices(site_id, device_type="uap")

# Avoid: Multiple queries in loop
for device_id in device_ids:
    device = await api.get_device(site_id, device_id)  # N+1 problem
```

## Development Workflow

1. **Create Feature Branch**
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Implement with Tests**
   - Write tests first (TDD approach)
   - Implement feature with type safety
   - Run tests: `pytest tests/unit/ --cov=src`

3. **Verify Code Quality**
   ```bash
   # Run all pre-commit checks
   pre-commit run --all-files

   # Type check
   mypy src/

   # Security scan
   bandit -r src/
   ```

4. **Update Documentation**
   - Add docstrings
   - Update README.md examples
   - Update API.md reference

5. **Commit and Push**
   ```bash
   git add .
   git commit -m "feat(scope): description"
   git push origin feat/your-feature-name
   ```

6. **Create Pull Request**
   - Use PR template
   - Link related issues
   - Ensure CI passes

## Troubleshooting

### Common Issues

**Import Errors:**
```python
# Wrong: Circular import
from src.tools.devices import list_devices
from src.api.client import UniFiAPI

# Right: Use TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.client import UniFiAPI
```

**Async Context Issues:**
```python
# Wrong: Blocking call in async function
result = requests.get(url)  # Blocks event loop

# Right: Use async HTTP client
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        result = await response.json()
```

**Cache Key Collisions:**
```python
# Wrong: Generic key
cache_key = f"device:{device_id}"  # Collides across sites

# Right: Include site context
cache_key = f"devices:{site_id}:{device_id}"
```

## Resources

- **MCP Specification**: https://spec.modelcontextprotocol.io/
- **FastMCP Documentation**: https://github.com/jlowin/fastmcp
- **Pydantic V2 Docs**: https://docs.pydantic.dev/latest/
- **UniFi API Reference**: https://ubntwiki.com/products/software/unifi-controller/api
- **Project Documentation**: See API.md, TESTING_PLAN.md, DEVELOPMENT_PLAN.md

## Questions?

For complex architectural decisions or unclear requirements:
1. Check existing patterns in the codebase
2. Review DEVELOPMENT_PLAN.md for roadmap context
3. Consult AGENTS.md for AI assistant guidelines
4. Open a GitHub Discussion for community input

**Remember**: Safety first, type safety always, test everything!
