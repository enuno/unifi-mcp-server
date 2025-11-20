**UniFi MCP Server - Google Gemini AI Configuration**

This document provides Google Gemini-specific instructions for developing, testing, and extending the UniFi MCP Server. For universal agent rules and conventions, refer to [AGENTS.md](AGENTS.md).

***

## Quick Start with Gemini CLI

### Prerequisites

```bash
# Install Gemini CLI
npm install -g @google/generative-ai-cli

# Set up API key (get from Google AI Studio)
export GEMINI_API_KEY="your-api-key"

# Or add to .env
echo "GEMINI_API_KEY=your-api-key" >> .gemini/.env
```


### Configuration

Create `.gemini/settings.json` in project root:

```json
{
  "model": {
    "name": "gemini-2.5-pro",
    "temperature": 0.3
  },
  "context": {
    "fileName": ["GEMINI.md", "AGENTS.md", "API.md", "README.md"]
  },
  "mcpServers": {
    "unifi": {
      "command": "uv",
      "args": ["--directory", ".", "run", "python", "src/main.py"],
      "env": {
        "UNIFI_API_KEY": "${UNIFI_API_KEY}",
        "UNIFI_API_TYPE": "cloud"
      }
    }
  }
}
```


***

## Project Context for Gemini

### Technology Stack

- **Language**: Python 3.10+
- **Framework**: FastMCP (Model Context Protocol server)
- **API Client**: Async UniFi Network API
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Caching**: Redis (optional, with async client)
- **Validation**: Pydantic v2 models
- **Code Quality**: black, isort, ruff, mypy, pre-commit


### Architecture Overview

```
src/
├── main.py              # MCP server entry point (55 tools)
├── api/                 # UniFi API client with rate limiting
├── models/              # Pydantic data models
│   └── zbf.py          # Zone-Based Firewall models
├── tools/               # MCP tool implementations (read + write)
├── resources/           # MCP resource definitions
├── cache.py             # Redis caching layer
├── webhooks/            # Event handlers
└── utils/               # Validators and helpers
```


***

## Gemini-Specific Development Guidelines

### 1. Code Generation Standards

**When generating Python code for this project:**

#### Type Safety

- Always use Python 3.10+ type hints
- Use `from __future__ import annotations` for forward references
- Leverage Pydantic v2 for data validation
- Use `typing` module: `Optional`, `List`, `Dict`, `Literal`, `TypedDict`

```python
from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field, validator

class FirewallRule(BaseModel):
    """Firewall rule configuration."""
    name: str = Field(..., description="Rule name")
    action: Literal["accept", "drop", "reject"]
    enabled: bool = True
    protocol: Optional[Literal["tcp", "udp", "icmp"]] = None
```


#### Async/Await Patterns

- All I/O operations MUST be async
- Use `asyncio.gather()` for parallel operations
- Implement proper error handling with try/except blocks
- Use `async with` for context managers

```python
async def get_devices(self, site_id: str) -> List[Dict]:
    """Fetch devices with error handling."""
    try:
        async with self.session.get(f"/sites/{site_id}/devices") as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch devices: {e}")
        raise
```


### 2. MCP Tool Development

#### Tool Structure Template

When creating new MCP tools, follow this pattern:

```python
@mcp.tool()
async def tool_name(
    site_id: str,
    param: str,
    confirm: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Brief description of what the tool does.
    
    Args:
        site_id: UniFi site identifier (e.g., 'default')
        param: Description of parameter
        confirm: Required safety flag for mutating operations
        dry_run: Preview changes without applying
        
    Returns:
        Dictionary containing operation results
        
    Raises:
        ValueError: If validation fails
        APIError: If UniFi API request fails
    """
    # 1. Input validation
    if not site_id:
        raise ValueError("site_id is required")
    
    # 2. Safety checks for mutating operations
    if not dry_run and not confirm:
        return {
            "error": "confirm=True required for this operation",
            "dry_run_available": True
        }
    
    # 3. Dry-run preview
    if dry_run:
        return {
            "dry_run": True,
            "would_perform": "description of action",
            "affected_resources": ["list", "of", "resources"]
        }
    
    # 4. Execute operation
    try:
        result = await unifi_api.perform_action(site_id, param)
        
        # 5. Audit logging
        logger.info(f"Tool executed: {tool_name}", extra={
            "site_id": site_id,
            "param": param,
            "result": result
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Tool failed: {e}")
        raise
```


#### Safety Mechanisms (CRITICAL)

**All mutating operations MUST implement:**

1. **`confirm` parameter**: Explicit opt-in for changes
2. **`dry_run` parameter**: Preview before execution
3. **Input validation**: Comprehensive parameter checks
4. **Audit logging**: Record all actions to `audit.log`
5. **Error handling**: Graceful failure with informative messages

### 3. Testing Requirements

#### Test Coverage Expectations

- **Unit tests**: 80% coverage target (currently 37%)
- **Test file location**: `tests/unit/test_<module>.py`
- **Fixtures**: Use pytest fixtures for common setup
- **Mocking**: Mock external API calls

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_create_firewall_rule():
    """Test firewall rule creation with validation."""
    # Arrange
    mock_api = AsyncMock()
    mock_api.create_rule.return_value = {"_id": "rule123", "name": "test"}
    
    # Act
    with patch("src.api.client.UniFiAPI", return_value=mock_api):
        result = await create_firewall_rule(
            site_id="default",
            name="test",
            action="accept",
            confirm=True
        )
    
    # Assert
    assert result["name"] == "test"
    mock_api.create_rule.assert_called_once()
```


#### Running Tests

```bash
# Run all tests with coverage
pytest tests/unit/ --cov=src --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_firewall_tools.py -v

# Run tests for specific feature
pytest -k "firewall" -v

# Run with debugging
pytest --pdb tests/unit/test_firewall_tools.py
```


### 4. API Integration Patterns

#### UniFi API Client Usage

```python
# Always use the configured API client
from src.api.client import UniFiAPI

async with UniFiAPI(config) as api:
    # List operations
    devices = await api.get(f"/sites/{site_id}/devices")
    
    # Create operations
    new_rule = await api.post(
        f"/sites/{site_id}/firewall/rules",
        json=rule_data
    )
    
    # Update operations
    updated = await api.put(
        f"/sites/{site_id}/firewall/rules/{rule_id}",
        json=updated_data
    )
    
    # Delete operations
    await api.delete(f"/sites/{site_id}/firewall/rules/{rule_id}")
```


#### Rate Limiting

The API client implements automatic rate limiting:

- Default: 10 requests per second
- Automatic backoff on 429 responses
- No manual rate limiting needed in tools


### 5. Pydantic Model Development

#### Model Best Practices

```python
from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List, Literal

class FirewallZone(BaseModel):
    """Zone-Based Firewall zone configuration."""
    
    # Required fields with descriptions
    name: str = Field(..., description="Zone name (e.g., 'LAN', 'IoT')")
    site_id: str = Field(..., description="UniFi site identifier")
    
    # Optional fields with defaults
    description: Optional[str] = Field(None, description="Zone description")
    enabled: bool = Field(True, description="Whether zone is active")
    
    # Constrained fields
    networks: List[str] = Field(
        default_factory=list,
        description="Network IDs in this zone",
        min_items=0,
        max_items=50
    )
    
    # Custom validation
    @validator("name")
    def validate_name(cls, v):
        """Validate zone name format."""
        if not v or len(v) < 3:
            raise ValueError("Zone name must be at least 3 characters")
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Zone name must be alphanumeric")
        return v
    
    @root_validator
    def check_consistency(cls, values):
        """Validate field consistency."""
        if values.get("enabled") and not values.get("networks"):
            raise ValueError("Enabled zones must have at least one network")
        return values
    
    class Config:
        """Pydantic configuration."""
        # Allow extra fields for forward compatibility
        extra = "allow"
        # Use enum values directly
        use_enum_values = True
        # Validate on assignment
        validate_assignment = True
```


### 6. Error Handling \& Logging

#### Logging Standards

```python
import logging
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Info: Normal operations
logger.info("Device restarted", extra={"device_id": device_id, "site_id": site_id})

# Warning: Recoverable issues
logger.warning("Rate limit approached", extra={"requests": count})

# Error: Operation failures
logger.error("API request failed", extra={"endpoint": url, "status": status}, exc_info=True)

# Debug: Detailed tracing (development only)
logger.debug("Request payload", extra={"data": sanitize(payload)})
```


#### Exception Handling

```python
from src.utils.exceptions import (
    UniFiAPIError,
    ValidationError,
    AuthenticationError,
    RateLimitError
)

try:
    result = await api.create_resource(data)
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    return {"error": "Invalid input", "details": str(e)}
except AuthenticationError as e:
    logger.error("Authentication failed")
    raise  # Re-raise auth errors
except RateLimitError as e:
    logger.warning("Rate limited, retrying...")
    await asyncio.sleep(e.retry_after)
    # Retry logic
except UniFiAPIError as e:
    logger.error(f"API error: {e}")
    return {"error": "API request failed", "message": str(e)}
```


***

## Gemini Workflow Examples

### Adding a New MCP Tool

```bash
# 1. Understand the UniFi API endpoint
gemini "Explain the UniFi API endpoint for creating VLANs. Include request format, parameters, and response structure."

# 2. Generate the tool implementation
gemini "Create an MCP tool called 'create_vlan' that creates a VLAN in UniFi. Follow the patterns in src/tools/network_config.py. Include confirm and dry_run parameters."

# 3. Generate Pydantic models
gemini "Create Pydantic models for VLAN configuration with validation. Include fields for VLAN ID (1-4094), name, subnet, DHCP settings."

# 4. Generate unit tests
gemini "Generate pytest unit tests for the create_vlan tool. Mock the UniFi API client. Test successful creation, validation errors, and dry-run mode."

# 5. Update documentation
gemini "Update API.md to document the new create_vlan tool. Include examples and parameter descriptions."
```


### Debugging Existing Code

```bash
# Analyze error logs
gemini "Analyze this error traceback and suggest fixes: [paste traceback]"

# Optimize performance
gemini "Review src/tools/dpi.py for performance issues. The list_top_applications tool is slow with large datasets. Suggest optimizations."

# Refactor for clarity
gemini "Refactor src/tools/firewall_zones.py to improve readability. Reduce complexity in the assign_network_to_zone function."
```


### Code Review Assistance

```bash
# Before committing
gemini "Review my changes in src/tools/wifi.py. Check for: type safety, error handling, async patterns, test coverage, documentation."

# Security audit
gemini "Security audit this code for potential vulnerabilities: [paste code]. Focus on input validation, authentication, and data sanitization."
```


***

## Common Tasks \& Commands

### Development Workflow

```bash
# Start with context loading
gemini /init  # Generate initial GEMINI.md context

# Daily development
gemini "Review open issues on GitHub and suggest which to tackle first"
gemini "Explain the Zone-Based Firewall implementation in src/models/zbf.py"
gemini "Help me implement the missing endpoint for zone policy matrix"

# Before PR
gemini "Run pre-commit checks and fix any issues"
gemini "Generate release notes for changes in the current branch"
```


### Testing \& Quality

```bash
# Generate test cases
gemini "Generate test cases for edge cases in src/tools/client_management.py"

# Improve coverage
gemini "Which modules have coverage below 50%? Suggest unit tests to improve coverage."

# Static analysis
gemini "Run mypy on src/ and fix type errors"
```


### Documentation

```bash
# Generate docstrings
gemini "Add comprehensive docstrings to all functions in src/tools/port_forwarding.py following Google style"

# Update API docs
gemini "Update API.md with the latest tool signatures from src/main.py"

# Create examples
gemini "Create 5 practical examples of using the DPI statistics tools"
```


***

## Known Limitations \& Workarounds

### Zone-Based Firewall API Issues

**Problem**: 8 ZBF tools cannot function due to missing UniFi API endpoints (verified on v10.0.156):

- Zone policy matrix endpoints (get, update, delete)
- Application blocking per zone
- Zone statistics

**Workaround**:

```python
# Use console-based configuration for these features
# Document limitations clearly in tool docstrings

@mcp.tool()
async def update_zbf_policy_matrix(site_id: str, source_zone_id: str, dest_zone_id: str, action: str) -> Dict:
    """
    ⚠️ API LIMITATION: This endpoint does not exist in UniFi API v10.0.156.
    
    Configure zone policies via UniFi Console:
    Settings → Security → Zone-Based Firewall → Policy Matrix
    
    Args:
        site_id: UniFi site identifier
        source_zone_id: Source zone ID
        dest_zone_id: Destination zone ID
        action: Policy action ('accept', 'drop', 'reject')
        
    Returns:
        Error message explaining API limitation
    """
    return {
        "error": "API endpoint not available",
        "api_version": "v10.0.156",
        "workaround": "Configure via UniFi Console UI",
        "documentation": "See ZBF_STATUS.md for details"
    }
```


### Redis Caching

**Best Practice**: Always check cache configuration:

```python
# Tools should handle cache absence gracefully
cache = get_cache()  # May return None
if cache:
    cached_data = await cache.get(key)
    if cached_data:
        return cached_data

# Fetch from API
data = await api.get_data()

# Cache if available
if cache:
    await cache.set(key, data, ttl=300)
```


***

## Integration with Other AI Agents

### Cross-Agent Collaboration

This project supports multiple AI coding assistants. Coordination patterns:

1. **Gemini**: High-level architecture, API design, batch operations
2. **Claude**: Complex refactoring, documentation generation, code review
3. **Copilot**: Rapid boilerplate, autocomplete, inline suggestions
4. **Cursor**: Multi-file edits, codebase-wide changes

### Shared Context Files

All agents read from:

- `AGENTS.md` - Universal rules
- `API.md` - API documentation
- `SECURITY.md` - Security policies
- `CONTRIBUTING.md` - Contribution guidelines

Agent-specific files:

- `GEMINI.md` (this file)
- `CLAUDE.md`
- `.cursorrules`
- `copilot-instructions.md`

***

## Performance Optimization

### Batch Operations

```python
# Use asyncio.gather for parallel requests
async def batch_restart_devices(device_ids: List[str], site_id: str):
    """Restart multiple devices in parallel."""
    tasks = [restart_device(device_id, site_id) for device_id in device_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]
    
    return {"successes": len(successes), "failures": len(failures)}
```


### Caching Strategies

```python
# Cache expensive operations
@cached(ttl=600)  # 10 minutes
async def get_network_topology(site_id: str) -> Dict:
    """Get network topology with caching."""
    devices = await api.get_devices(site_id)
    clients = await api.get_clients(site_id)
    networks = await api.get_networks(site_id)
    
    # Build topology
    return build_topology(devices, clients, networks)
```


***

## Security Considerations

### API Key Management

```python
# ✅ CORRECT: Load from environment
UNIFI_API_KEY = os.getenv("UNIFI_API_KEY")

# ❌ WRONG: Hardcode API key
UNIFI_API_KEY = "xyz123abc"  # NEVER DO THIS
```


### Input Sanitization

```python
# Sanitize user inputs
def sanitize_firewall_rule_name(name: str) -> str:
    """Remove unsafe characters from rule name."""
    # Allow alphanumeric, hyphens, underscores, spaces
    return re.sub(r'[^a-zA-Z0-9\-_ ]', '', name)
```


### Audit Logging

All mutating operations are logged to `audit.log`:

```python
# Audit log format
{
    "timestamp": "2025-11-19T21:30:00Z",
    "tool": "create_firewall_rule",
    "user": "system",
    "site_id": "default",
    "action": "create",
    "resource_type": "firewall_rule",
    "resource_id": "rule_id",
    "parameters": {"name": "block-malware", "action": "drop"},
    "result": "success"
}
```


***

## Troubleshooting

### Common Issues

#### MCP Server Won't Start

```bash
# Check Python version
python --version  # Must be 3.10+

# Check dependencies
uv pip list | grep fastmcp

# Test configuration
python -c "from src.config import load_config; print(load_config())"
```


#### UniFi API Connection Fails

```bash
# Verify API key
echo $UNIFI_API_KEY

# Test API connectivity
curl -H "X-API-Key: $UNIFI_API_KEY" https://api.ui.com/ea/hosts
```


#### Tests Failing

```bash
# Clear pytest cache
rm -rf .pytest_cache

# Run with verbose output
pytest -vv tests/unit/test_failing_module.py

# Check for async issues
pytest -k "async" --tb=short
```


***

## Contributing Back

### Before Submitting PR

1. **Run full test suite**: `pytest tests/unit/ --cov=src`
2. **Run pre-commit**: `pre-commit run --all-files`
3. **Update documentation**: Ensure API.md reflects changes
4. **Add tests**: Maintain >80% coverage
5. **Follow conventions**: Review CONTRIBUTING.md

### Commit Message Format

```
feat(tools): add VLAN creation tool

- Implement create_vlan MCP tool
- Add VLANConfig Pydantic model with validation
- Include unit tests (95% coverage)
- Update API.md documentation

Closes #123
```


***

## Additional Resources

### Documentation

- **Main README**: [README.md](README.md)
- **API Reference**: [API.md](API.md)
- **Security Policy**: [SECURITY.md](SECURITY.md)
- **Development Plan**: [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)
- **Testing Strategy**: [TESTING_PLAN.md](TESTING_PLAN.md)
- **ZBF Status**: [ZBF_STATUS.md](ZBF_STATUS.md)


### External Links

- **UniFi API Documentation**: https://developer.ui.com/
- **FastMCP Framework**: https://github.com/jlowin/fastmcp
- **MCP Specification**: https://modelcontextprotocol.io/
- **Gemini CLI Docs**: https://geminicli.com/


### Community

- **GitHub Issues**: https://github.com/enuno/unifi-mcp-server/issues
- **GitHub Discussions**: https://github.com/enuno/unifi-mcp-server/discussions
- **UniFi Community**: https://community.ui.com/

***

## Version History

- **v1.0.0** (2025-11-19): Initial Gemini configuration for UniFi MCP Server
- Updated with project-specific context, tool patterns, and Gemini CLI integration

***

**Last Updated**: November 19, 2025
**Maintained By**: UniFi MCP Server Team
**Review Cycle**: Monthly or upon significant Gemini CLI updates

