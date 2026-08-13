---
name: unifi-mcp-tool-builder
description: Specialized guide for adding new MCP tools to the UniFi MCP Server following project standards, UniFi API patterns, and test-driven development practices. Use when implementing new UniFi Network Controller features as MCP tools.
license: Apache 2.0
version: 1.0.0
author: UniFi MCP Server Team
---

# UniFi MCP Tool Builder

## Overview

This skill guides you through adding new MCP tools to the existing UniFi MCP Server. Unlike building an MCP server from scratch, this focuses on **extending** the current 74-tool implementation with new UniFi Network Controller functionality while maintaining the project's quality standards.

**Project Context:**

- **Existing Tools**: 74 MCP tools across 9 feature categories
- **Test Coverage**: 990 tests, 78.18% overall coverage
- **Architecture**: FastMCP + Pydantic v2 + async/await patterns
- **API Support**: Local gateway (full), Cloud V1/EA (limited)
- **Quality Standards**: 80% minimum test coverage, TDD required

---

# Process

## Phase 1: Research and Planning

### 1.1 Understand the Tool Request

Before implementation, clarify:

- **What UniFi feature/endpoint** needs to be exposed?
- **Which API mode** supports it (local, cloud-v1, cloud-ea)?
- **What workflow** does this enable for AI agents?
- **How does this fit** into existing tool categories?

**Tool Categories in UniFi MCP Server:**

1. Device Management (list, control, upgrade)
2. Client Management (block, unblock, statistics)
3. Network Configuration (VLANs, subnets, DHCP)
4. Firewall & Security (rules, zones, ACLs)
5. WiFi/SSID Management (create, configure, statistics)
6. QoS & Traffic (profiles, flows, DPI)
7. Backup & Restore (automated backups, restore)
8. Site Management (multi-site, aggregation)
9. Topology & Monitoring (network maps, health)

### 1.2 Study UniFi API Documentation

**Load UniFi API reference:**

```bash
# Read the comprehensive UniFi API documentation
Read: docs/UNIFI_API.md
```

This document contains verified endpoints for UniFi Network v10.0.156+.

**Critical considerations:**

- **Endpoint availability**: Not all documented endpoints exist in all versions
- **API mode differences**: Local gateway vs Cloud APIs have different capabilities
- **Response formats**: Local API returns different structures than Cloud API
- **Authentication**: Local uses local credentials, Cloud uses API keys

### 1.3 Review Existing Patterns

**Study similar tools in the codebase:**

```bash
# Example: For a new device tool, read existing device tools
Read: src/tools/devices.py
Read: src/tools/device_control.py

# For network tools:
Read: src/tools/networks.py
Read: src/tools/network_config.py

# For testing patterns:
Read: tests/unit/test_devices.py
```

**Key patterns to identify:**

- How similar tools structure their inputs (Pydantic models)
- Response formatting (JSON with TypedDict or Pydantic response models)
- Error handling patterns
- Confirmation requirements for mutating operations
- Dry-run mode implementation
- Caching strategies (if applicable)

### 1.4 Verify API Endpoint Availability

**CRITICAL: Not all documented API endpoints actually exist!**

The UniFi MCP Server has discovered that many documented endpoints don't exist in real controllers. Before implementation:

1. **Check endpoint existence** in `docs/UNIFI_API.md` verification notes
2. **Test on real hardware** if possible (U7 Express, UDM Pro, etc.)
3. **Document findings** in code comments and API.md

**Known endpoint issues:**

- ZBF matrix endpoints don't exist (use Firewall Policies v2 instead)
- Some statistics endpoints are documented but not available
- Cloud APIs have very limited endpoint support vs local gateway

### 1.5 Create Implementation Plan

Document your plan covering:

**Tool Definition:**

- Tool name (follow naming convention: `{action}_{resource}`)
- Description (one-line summary for LLMs)
- Input parameters (with Pydantic model)
- Response format (TypedDict or Pydantic model)
- Error scenarios

**Data Models:**

- Pydantic models for request validation
- Response models (if complex data structure)
- Enums for allowed values

**Testing Strategy:**

- Unit test scenarios (minimum 10-15 tests)
- Mock API responses
- Edge cases (empty results, errors, pagination)
- Target coverage: 85%+ for new code

**Documentation:**

- Docstring with examples
- API.md section update
- README.md feature list update (if major feature)

---

## Phase 2: Implementation

### 2.1 Create Pydantic Models (if needed)

**Location**: `src/models/{feature}.py`

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class YourRequestModel(BaseModel):
    """Request model for your_tool operation.

    Attributes:
        site_id: UniFi site identifier
        resource_id: Resource to operate on
        options: Optional configuration parameters
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    site_id: str = Field(..., description="UniFi site ID (e.g., 'default')")
    resource_id: str = Field(..., min_length=1, description="Resource identifier")
    options: Optional[dict] = Field(None, description="Additional options")

class YourResponseModel(BaseModel):
    """Response from your_tool operation."""
    success: bool
    resource_id: str
    message: str
```

**Key requirements:**

- Use Pydantic v2 syntax (`model_config` instead of `Config`)
- `extra="forbid"` to reject unknown fields
- Comprehensive Field descriptions for LLM understanding
- Type hints for all fields
- Docstrings explaining purpose

### 2.2 Implement the MCP Tool

**Location**: `src/tools/{category}.py` (or new file if new category)

```python
from fastmcp import Context
from src.models.your_model import YourRequestModel, YourResponseModel
from src.api.client import UniFiClient
from src.utils.validators import validate_site_id

@mcp.tool()
async def your_tool_name(
    site_id: str,
    resource_id: str,
    options: dict | None = None,
    settings: Context = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Brief one-line description of what this tool does.

    Detailed explanation of the tool's purpose, when to use it,
    and what it accomplishes. Include examples of common use cases.

    Args:
        site_id: UniFi site identifier (e.g., 'default')
        resource_id: Resource to operate on
        options: Optional configuration dictionary
        settings: FastMCP context (auto-injected)
        confirm: Required for mutating operations (default: False)
        dry_run: Preview changes without applying (default: False)

    Returns:
        Dictionary containing:
        - success: Operation success status
        - resource_id: Modified resource identifier
        - message: Human-readable result message
        - details: (if dry_run) Preview of changes

    Raises:
        ValueError: If site_id is invalid or resource not found
        PermissionError: If confirm=True not provided for mutation

    Examples:
        >>> # Read-only operation
        >>> result = await your_tool_name(site_id="default", resource_id="abc123")

        >>> # Mutating operation (requires confirmation)
        >>> result = await your_tool_name(
        ...     site_id="default",
        ...     resource_id="abc123",
        ...     confirm=True
        ... )

        >>> # Preview changes first
        >>> preview = await your_tool_name(
        ...     site_id="default",
        ...     resource_id="abc123",
        ...     dry_run=True
        ... )
    """
    # Validate inputs
    validate_site_id(site_id)

    # Get client from context
    client: UniFiClient = settings.get("client")

    # MUTATING OPERATIONS: Require confirmation
    if not dry_run:
        if not confirm:
            raise PermissionError(
                "This operation modifies network configuration. "
                "Set confirm=True to proceed, or use dry_run=True to preview changes."
            )

    # Dry-run mode: Preview changes
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "preview": {
                "operation": "your_operation",
                "resource_id": resource_id,
                "changes": {"key": "value"},
            },
            "message": "Dry-run completed. Set confirm=True to apply changes."
        }

    # Execute operation
    try:
        response = await client.request(
            method="POST",
            endpoint=f"/api/s/{site_id}/rest/your_endpoint",
            json={"resource_id": resource_id, **(options or {})},
        )

        return {
            "success": True,
            "resource_id": resource_id,
            "message": f"Successfully processed resource {resource_id}",
            "data": response.get("data", {}),
        }

    except Exception as e:
        # Provide actionable error messages
        if "not found" in str(e).lower():
            raise ValueError(
                f"Resource '{resource_id}' not found in site '{site_id}'. "
                f"Use list_resources tool to see available resources."
            ) from e
        raise
```

**Implementation checklist:**

- [ ] FastMCP `@mcp.tool()` decorator
- [ ] Comprehensive docstring with examples
- [ ] Input validation (use existing validators in `src/utils/validators.py`)
- [ ] Confirm requirement for mutating operations
- [ ] Dry-run mode support for previewing changes
- [ ] Actionable error messages that guide LLM to correct usage
- [ ] Async/await for all I/O operations
- [ ] Proper exception handling with context

### 2.3 Register Tool in Main Server

**Location**: `src/main.py`

Add your tool to the imports and ensure it's registered:

```python
from src.tools.your_category import your_tool_name

# Tools are auto-registered via @mcp.tool() decorator
# No manual registration needed with FastMCP
```

### 2.4 Follow Code Quality Standards

**Run quality checks:**

```bash
# Format code
black src/tools/your_file.py
isort src/tools/your_file.py

# Lint
ruff check src/tools/your_file.py --fix

# Type check
mypy src/tools/your_file.py
```

---

## Phase 3: Test-Driven Development

### 3.1 Write Tests BEFORE Implementation

**Location**: `tests/unit/test_{category}.py`

**CRITICAL: UniFi MCP Server requires Test-Driven Development (TDD)**

1. Write failing tests first
2. Implement just enough to make tests pass
3. Refactor and improve
4. Achieve 85%+ coverage for new code

### 3.2 Test Structure

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.tools.your_category import your_tool_name

class TestYourToolName:
    """Test suite for your_tool_name."""

    @pytest.fixture
    def mock_context(self):
        """Mock FastMCP context with UniFi client."""
        context = MagicMock()
        client = AsyncMock()
        context.get.return_value = client
        return context, client

    @pytest.mark.asyncio
    async def test_successful_operation(self, mock_context):
        """Test successful tool execution."""
        context, client = mock_context
        client.request.return_value = {
            "data": {"_id": "abc123", "name": "test"}
        }

        result = await your_tool_name(
            site_id="default",
            resource_id="abc123",
            settings=context,
            confirm=True
        )

        assert result["success"] is True
        assert result["resource_id"] == "abc123"
        client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_requires_confirmation(self, mock_context):
        """Test that mutating operations require confirm=True."""
        context, client = mock_context

        with pytest.raises(PermissionError, match="Set confirm=True"):
            await your_tool_name(
                site_id="default",
                resource_id="abc123",
                settings=context,
                confirm=False
            )

    @pytest.mark.asyncio
    async def test_dry_run_mode(self, mock_context):
        """Test dry-run preview mode."""
        context, client = mock_context

        result = await your_tool_name(
            site_id="default",
            resource_id="abc123",
            settings=context,
            dry_run=True
        )

        assert result["dry_run"] is True
        assert "preview" in result
        client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_site_id(self, mock_context):
        """Test validation of site_id."""
        context, client = mock_context

        with pytest.raises(ValueError, match="Invalid site"):
            await your_tool_name(
                site_id="",
                resource_id="abc123",
                settings=context
            )

    @pytest.mark.asyncio
    async def test_resource_not_found(self, mock_context):
        """Test handling of not found errors."""
        context, client = mock_context
        client.request.side_effect = Exception("Resource not found")

        with pytest.raises(ValueError, match="not found"):
            await your_tool_name(
                site_id="default",
                resource_id="nonexistent",
                settings=context,
                confirm=True
            )

    @pytest.mark.asyncio
    async def test_with_optional_parameters(self, mock_context):
        """Test tool with optional parameters."""
        context, client = mock_context
        client.request.return_value = {"data": {"_id": "abc123"}}

        result = await your_tool_name(
            site_id="default",
            resource_id="abc123",
            options={"key": "value"},
            settings=context,
            confirm=True
        )

        assert result["success"] is True
        # Verify options were passed to API
        call_args = client.request.call_args
        assert call_args[1]["json"]["key"] == "value"
```

**Test coverage requirements:**

- Successful operation (happy path)
- Confirmation requirement (for mutating ops)
- Dry-run mode
- Input validation (invalid site_id, etc.)
- Error handling (not found, API errors)
- Optional parameters
- Edge cases (empty results, pagination)
- Response format validation

**Target**: 85%+ coverage for new code

### 3.3 Run Tests

```bash
# Run your specific test file
pytest tests/unit/test_your_category.py -v

# Run with coverage
pytest tests/unit/test_your_category.py --cov=src/tools/your_category --cov-report=term-missing

# Ensure coverage meets target (85%+)
pytest tests/unit/test_your_category.py --cov=src/tools/your_category --cov-report=html
open htmlcov/index.html  # Review coverage report
```

---

## Phase 4: Documentation

### 4.1 Update API.md

**Location**: `API.md`

Add your tool to the appropriate section with complete documentation:

```markdown
### your_tool_name

**Description**: Brief one-line description

**Purpose**: Detailed explanation of when and why to use this tool

**Parameters**:
- `site_id` (string, required): UniFi site identifier (e.g., "default")
- `resource_id` (string, required): Resource identifier to operate on
- `options` (object, optional): Additional configuration options
- `confirm` (boolean, optional): Required for mutating operations (default: false)
- `dry_run` (boolean, optional): Preview changes without applying (default: false)

**Returns**:
```json
{
  "success": true,
  "resource_id": "abc123",
  "message": "Successfully processed resource",
  "data": { /* resource details */ }
}
```

**Dry-run response**:

```json
{
  "success": true,
  "dry_run": true,
  "preview": {
    "operation": "your_operation",
    "resource_id": "abc123",
    "changes": { /* preview of changes */ }
  },
  "message": "Dry-run completed. Set confirm=True to apply changes."
}
```

**Examples**:

```python
# Example 1: Preview changes (dry-run)
result = await mcp.call_tool("your_tool_name", {
    "site_id": "default",
    "resource_id": "abc123",
    "dry_run": True
})

# Example 2: Execute operation
result = await mcp.call_tool("your_tool_name", {
    "site_id": "default",
    "resource_id": "abc123",
    "confirm": True
})
```

**Error Handling**:

- `ValueError`: Invalid site_id or resource not found
- `PermissionError`: Mutating operation requires confirm=True
- `APIError`: UniFi API returned error (check message for details)

**API Endpoint**: `POST /api/s/{site}/rest/your_endpoint`

**Supported API Modes**:

- ✅ Local Gateway API (full support)
- ⚠️ Cloud V1 API (limited support)
- ❌ Cloud EA API (not supported)

```

### 4.2 Update README.md (if major feature)

If adding a new feature category, update README.md:

```markdown
### Your New Feature Category

- **Feature Name**: Description of what it enables
- **Tools**: List of new tools
- **Use Cases**: Common scenarios where this is valuable
```

### 4.3 Update CHANGELOG.md

Add entry under "Unreleased" section:

```markdown
## [Unreleased]

### Added
- New tool `your_tool_name` for managing XYZ (#123)
- Support for ABC feature in UniFi Network 10.0+
```

---

## Phase 5: Quality Verification

### 5.1 Run Full Test Suite

```bash
# Run all tests
pytest tests/unit/

# Verify no regressions
pytest tests/unit/ --cov=src --cov-report=term-missing

# Check overall coverage (should remain ≥78%)
pytest tests/unit/ --cov=src --cov-report=html
```

### 5.2 Code Quality Checks

```bash
# Format (auto-fix)
black src/ tests/
isort src/ tests/

# Lint (auto-fix where possible)
ruff check src/ tests/ --fix

# Type check
mypy src/

# Security scan
bandit -r src/

# Pre-commit hooks
pre-commit run --all-files
```

### 5.3 Manual Testing with MCP Inspector

```bash
# Start MCP Inspector
uv run mcp dev src/main.py

# Open http://localhost:5173
# Test your new tool with real inputs
# Verify responses match expectations
```

### 5.4 Test on Real Hardware (if possible)

If you have access to a UniFi controller:

1. Configure local gateway API credentials
2. Test tool with real data
3. Verify API endpoint exists and returns expected format
4. Document any discrepancies in API.md

---

## Quality Checklist

Before submitting:

### Code Quality

- [ ] Tool follows naming convention (`{action}_{resource}`)
- [ ] Comprehensive docstring with examples
- [ ] Input validation using Pydantic models
- [ ] Confirmation required for mutating operations
- [ ] Dry-run mode implemented
- [ ] Actionable error messages
- [ ] Async/await used consistently
- [ ] Type hints throughout
- [ ] No hardcoded values (use constants)
- [ ] Follows existing code patterns

### Testing

- [ ] TDD: Tests written before implementation
- [ ] 85%+ coverage for new code
- [ ] Tests cover happy path
- [ ] Tests cover error scenarios
- [ ] Tests cover edge cases
- [ ] Mock API responses properly
- [ ] No integration tests without real hardware
- [ ] All tests passing

### Documentation

- [ ] API.md updated with complete tool documentation
- [ ] Examples provided in docstring and API.md
- [ ] Error handling documented
- [ ] API endpoint documented
- [ ] API mode support clearly indicated
- [ ] CHANGELOG.md updated
- [ ] README.md updated (if major feature)

### Integration

- [ ] Tool registered in src/main.py
- [ ] Imports organized correctly
- [ ] No circular dependencies
- [ ] Compatible with existing tools

### Quality Gates

- [ ] `black` formatting passes
- [ ] `isort` import sorting passes
- [ ] `ruff` linting passes
- [ ] `mypy` type checking passes
- [ ] `bandit` security scan passes
- [ ] `pytest` all tests pass
- [ ] Coverage ≥78% overall, ≥85% for new code
- [ ] Pre-commit hooks pass
- [ ] MCP Inspector manual testing successful

---

## Common Patterns in UniFi MCP Server

### Pattern 1: List/Query Tools (Read-Only)

```python
@mcp.tool()
async def list_resources(
    site_id: str,
    filters: dict | None = None,
    settings: Context = None,
) -> list[dict]:
    """List resources in the UniFi controller.

    This is a read-only operation requiring no confirmation.
    """
    client = settings.get("client")
    response = await client.request(
        method="GET",
        endpoint=f"/api/s/{site_id}/rest/resource",
        params=filters or {}
    )
    return response.get("data", [])
```

### Pattern 2: Mutating Tools with Confirmation

```python
@mcp.tool()
async def update_resource(
    site_id: str,
    resource_id: str,
    updates: dict,
    settings: Context = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Update a resource (requires confirmation).

    Mutating operations always require confirm=True.
    """
    if not dry_run and not confirm:
        raise PermissionError("Set confirm=True to proceed")

    if dry_run:
        return {"dry_run": True, "preview": updates}

    client = settings.get("client")
    response = await client.request(
        method="PUT",
        endpoint=f"/api/s/{site_id}/rest/resource/{resource_id}",
        json=updates
    )
    return response
```

### Pattern 3: Tools with Pagination

```python
@mcp.tool()
async def list_large_dataset(
    site_id: str,
    limit: int = 100,
    offset: int = 0,
    settings: Context = None,
) -> dict:
    """List resources with pagination support."""
    client = settings.get("client")
    response = await client.request(
        method="GET",
        endpoint=f"/api/s/{site_id}/rest/resource",
        params={"limit": limit, "offset": offset}
    )

    return {
        "data": response.get("data", []),
        "total": response.get("meta", {}).get("total", 0),
        "limit": limit,
        "offset": offset
    }
```

### Pattern 4: Multi-Site Aggregation

```python
@mcp.tool()
async def aggregate_across_sites(
    settings: Context = None,
) -> dict:
    """Aggregate data across all sites."""
    client = settings.get("client")

    # Get all sites
    sites_response = await client.request(
        method="GET",
        endpoint="/api/self/sites"
    )
    sites = sites_response.get("data", [])

    # Aggregate data
    results = []
    for site in sites:
        site_id = site["name"]
        site_data = await client.request(
            method="GET",
            endpoint=f"/api/s/{site_id}/rest/resource"
        )
        results.append({
            "site_id": site_id,
            "data": site_data.get("data", [])
        })

    return {"sites": results}
```

---

## References

### Project Documentation

- `README.md` - Project overview and quick start
- `API.md` - Complete MCP tool reference
- `AGENTS.md` - AI agent development guidelines
- `DEVELOPMENT_PLAN.md` - Roadmap and feature planning
- `TESTING_PLAN.md` - Testing strategy and coverage goals
- `CONTRIBUTING.md` - Contribution guidelines

### UniFi API Documentation

- `docs/UNIFI_API.md` - Verified endpoint documentation for v10.0.156+
- [UniFi Network Developer Documentation](https://developer.ui.com/)

### Code Examples

- `src/tools/devices.py` - Device management examples
- `src/tools/firewall.py` - Firewall rule management patterns
- `src/tools/zbf_tools.py` - Zone-Based Firewall implementation
- `src/tools/qos.py` - QoS profile management examples
- `tests/unit/test_topology.py` - High-coverage test examples (95%+)

---

**Last Updated**: 2026-01-25
**Maintained By**: UniFi MCP Server Team
