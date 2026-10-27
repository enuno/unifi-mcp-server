---
name: unifi-mcp-tool-builder
description: Specialized guide for adding new MCP tools to the UniFi MCP Server following project standards, UniFi API patterns, and test-driven development practices. Use when implementing new UniFi Network Controller features as MCP tools.
license: Apache 2.0
version: 1.0.0
author: UniFi MCP Server Team
---

# UniFi MCP Tool Builder

## Overview

This skill guides you through adding new MCP tools to the existing UniFi MCP Server. Unlike building an MCP server from scratch, this focuses on **extending** the current implementation with new UniFi Network Controller functionality while maintaining the project's quality standards.

**Project Context:**

- **Existing Tools**: 343 MCP tools in local mode. The live count is what the registry reports; this figure is checked by `tests/unit/test_skill_tool_references.py`, so the test fails if it drifts.
- **Test Coverage**: the unit suite is the gate. Run `pytest tests/unit/ -q --cov=src --cov-fail-under=80` from the repository root; the coverage gate is 80%. The exact test count changes with every change, so read it from that run rather than from this file.
- **Architecture**: FastMCP + Pydantic v2 + async/await patterns
- **API Support**: Local gateway (full), Cloud V1/EA (limited)
- **Quality Standards**: 80% minimum test coverage, TDD required

---

## Process

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
Read: tests/unit/tools/test_devices_tools.py
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

**Location**: `src/tools/{category}.py` (or a new module for a new feature area)

Tools are plain async functions. Every public `async def` in a module that `src/main.py` lists becomes a tool; there is no `@mcp.tool()` decorator. Each tool declares `@read_tool` or `@write_tool` (`src/utils/tool_kind.py`); registration fails without one, and `UNIFI_READ_ONLY` registers only read tools. The registry passes `settings` and hides it from the tool's public signature. Name helpers with a leading `_` so they are not registered.

A read tool:

```python
from typing import Any

from ..api.client import UniFiClient
from ..config import Settings
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_site_id
from ..utils.tool_kind import read_tool


@read_tool
async def list_your_resources(site_id: str, settings: Settings) -> list[dict[str, Any]]:
    """List your resources on a site.

    Args:
        site_id: Site identifier (name or UUID)
        settings: Application settings

    Returns:
        List of resource records
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)
    async with UniFiClient(settings) as client:
        if not client.is_authenticated:
            await client.authenticate()
        response = await client.get(f"/ea/sites/{site_id}/rest/your_resource")
    data = response if isinstance(response, list) else response.get("data", [])
    logger.info(sanitize_log_message(f"Listed {len(data)} resources for site {site_id}"))
    return [YourModel(**item).model_dump() for item in data]
```

A write tool:

```python
from ..utils.tool_kind import write_tool
from ..utils.validators import coerce_bool, validate_confirmation


@write_tool
async def update_your_resource(
    site_id: str,
    resource_id: str,
    settings: Settings,
    name: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update a resource.

    Args:
        site_id: Site identifier (name or UUID)
        resource_id: Resource identifier
        settings: Application settings
        name: New name (unchanged when omitted)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated record, or the planned change on a dry run
    """
    validate_confirmation(confirm, "update your resource", dry_run)
    site_id = validate_site_id(site_id)
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if not payload:
        raise ValidationError("No updates provided")

    if coerce_bool(dry_run):
        return {"dry_run": True, "operation": "update_your_resource", "payload": payload}

    async with UniFiClient(settings) as client:
        if not client.is_authenticated:
            await client.authenticate()
        response = await client.put(
            f"/ea/sites/{site_id}/rest/your_resource/{resource_id}", json_data=payload
        )
    return response
```

Build paths with the `Settings` helpers (`get_integration_path`, `get_protect_integration_path`, `get_v2_api_path`) or the `/ea/sites/{site_id}/...` form that `UniFiClient` translates. Never hardcode `/proxy/network/...`. The tool-set skills (`unifi-protect-tools`, `unifi-network-config-tools`, `unifi-security-tools`, `unifi-cloud-fleet-tools`) list the paths and gotchas per area.

**Implementation checklist:**

- [ ] Public `async def` with `settings: Settings`, declared `@read_tool` or `@write_tool`; helpers start with `_`
- [ ] Google-style docstring that lists every argument (MCP clients show it)
- [ ] Input validation with `src/utils/validators.py`
- [ ] Write tools: `confirm` and `dry_run`, `validate_confirmation()` first, dry run returned before any request
- [ ] Optional update arguments default to `None`
- [ ] No audit code in the tool (the registry wrapper audits every write)
- [ ] Errors from `src/utils/exceptions.py` (`ValidationError` for bad input); no broad `except` that hides the cause

### 2.3 Register the Module

**Location**: `src/main.py`

- A new function in an existing module needs no registration.
- A new module: import it, add it to `_LOCAL_TOOL_MODULES` or `_CLOUD_TOOL_MODULES`, and add it to the `UNIFI_PROFILE` sets that should include it.
- Regenerate the risk-tier snapshot: `UPDATE_TOOL_TIERS=1 pytest tests/unit/fleet/test_tiers.py`. Destructive tools need a `delete_`, `remove_` or `bulk_delete_` prefix or an entry in `DESTRUCTIVE_TOOLS` (`src/tool_registry.py`). A write tool with a risky word in its name needs an entry in `DESTRUCTIVE_TOOLS` or `RISKY_NAME_EXEMPTIONS`.

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

**Location**: `tests/unit/tools/test_{module}_tools.py`

```python
from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.your_category import update_your_resource
from src.utils.exceptions import ValidationError


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    return Settings()


def _client(client_class, **responses):
    client = AsyncMock()
    client.is_authenticated = True
    for method, value in responses.items():
        setattr(client, method, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)  # a truthy value would swallow errors
    client_class.return_value = client
    return client


async def test_update_sends_only_changed_fields(settings):
    with patch("src.tools.your_category.UniFiClient") as client_class:
        client = _client(client_class, put={"data": [{"_id": "abc", "name": "new"}]})

        await update_your_resource("default", "abc", settings, name="new", confirm=True)

    assert client.put.await_args.kwargs["json_data"] == {"name": "new"}


async def test_update_refuses_without_confirm(settings):
    with patch("src.tools.your_category.UniFiClient") as client_class:
        with pytest.raises(ValidationError, match="confirm"):
            await update_your_resource("default", "abc", settings, name="new")
    client_class.assert_not_called()


async def test_update_dry_run_makes_no_request(settings):
    with patch("src.tools.your_category.UniFiClient") as client_class:
        result = await update_your_resource("default", "abc", settings, name="new", dry_run=True)
    assert result["dry_run"] is True
    client_class.assert_not_called()
```

`asyncio_mode = auto` is set, so tests need no asyncio marker. `--strict-markers` rejects any marker except `integration`.

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

- `ValidationError`: Invalid input, or confirm=True missing on a write
- `ResourceNotFoundError`: The resource does not exist (HTTP 404)
- `APIError`: UniFi API returned another error (check the message)

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

# Check overall coverage (the CI gate is 80%)
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

## Phase 6: Skills and A2A sync

A new or changed tool must also update the artifacts that describe the surface to agents and to A2A orchestrators.

### 6.1 Creating or updating a skill

Skills live in `skills/<name>/SKILL.md`. Developer skills (the ones an agent loads while coding) are also copied to `.claude/skills/<name>/` and `.agents/skills/<name>/`. The `mintlify-docs` skill is the exception: its source of truth is `.mintlify/skills/mintlify-docs/SKILL.md`.

To add a new skill:

1. Create `skills/<name>/SKILL.md` with YAML frontmatter containing at least `name` and `description`.
2. If it is a developer skill, copy it to `.claude/skills/<name>/SKILL.md` and `.agents/skills/<name>/SKILL.md`.
3. If it names tools or arguments, use the explicit argument-list form so the skill-reference guards can check it.
4. Run the guards:

   ```bash
   pytest tests/unit/test_skill_tool_references.py \
          tests/unit/test_skill_parameter_references.py \
          tests/unit/test_agent_docs.py -q
   ```

To update an existing skill, edit `skills/<name>/SKILL.md` and re-copy the developer-skill copies. Do not edit the copies directly; `test_agent_docs.py` fails when they differ from the source.

### 6.2 Updating the A2A configuration

The A2A agent card and capability manifest are derived from the live tool registry, but several hand-written sources shape what they advertise:

- `src/a2a/capabilities.py` — capability names, module-to-domain map (`_MODULE_DOMAINS`), and the advertised API modes.
- `src/a2a/agent_card.py` — the card shape and safety-requirement logic.
- `agent-card.json` — the committed reference artifact.

When you add a tool in a new domain or change a tool's tier:

1. Update `_MODULE_DOMAINS` in `src/a2a/capabilities.py` if the module is not already mapped.
2. Regenerate the reference card:

   ```bash
   python scripts/generate_agent_card.py
   ```

3. Verify the card and the generator agree:

   ```bash
   pytest tests/unit/a2a/test_agent_card.py \
          tests/unit/a2a/test_agent_card_capabilities.py -q
   ```

Never hand-edit `agent-card.json`; the generator overwrites it and `test_agent_card.py` will fail if it does not match the source.

### 6.3 Updating the native prompt catalog

If a prompt workflow reads the new or changed tool:

1. Update `src/prompts/catalog.py` — the workflow's `evidence` and `requirements` tool lists.
2. Update `docs/PROMPTS.md` with the workflow's purpose and parameters.
3. Verify with:

   ```bash
   pytest tests/unit/prompts/test_prompt_catalog.py -q
   ```

A renamed tool can make a workflow disappear from `prompts/list` because the workflow is advertised only when every required tool is registered.

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
- [ ] Relevant skill updated in `skills/<name>/SKILL.md` and developer-skill copies synced
- [ ] `agent-card.json` regenerated if the tool surface changed
- [ ] Native prompt catalog updated if a workflow reads the tool

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
- [ ] Coverage ≥80% overall (CI gate), ≥85% for new code
- [ ] Pre-commit hooks pass
- [ ] MCP Inspector manual testing successful

---

## Common Patterns in UniFi MCP Server

Copy a real tool rather than a sketch:

| Pattern | Copy from |
|---------|-----------|
| Read tool, legacy API | `list_wlans` in `src/tools/wifi.py` |
| Read tool, integration API | `list_acl_rules` in `src/tools/acls.py` |
| Write tool with a partial update | `update_protect_relay` in `src/tools/protect_relays.py` |
| Read-modify-write update | `update_port_profile` in `src/tools/port_profiles.py` |
| Paginated list | `list_protect_relays` in `src/tools/protect_relays.py` (uses `validate_limit_offset()`) |
| Data across many controllers | `fleet_fanout` in `src/fleet/fleet_tools.py` (reads only) |

---

## References

### Project Documentation

- `README.md` - Project overview and quick start
- `API.md` - Complete MCP tool reference
- `AGENTS.md` - AI agent development guidelines
- `DEVELOPMENT_PLAN.md` - Roadmap and feature planning
- `docs/archive/TESTING_PLAN.md` - Testing strategy (archived)
- `CONTRIBUTING.md` - Contribution guidelines

### UniFi API Documentation

- `docs/UNIFI_API.md` - Verified endpoint documentation for v10.0.156+
- [UniFi Network Developer Documentation](https://developer.ui.com/)

### Code Examples

- `src/tools/devices.py` - Device management examples
- `src/tools/firewall.py` - Firewall rule management patterns
- `src/tools/firewall_policies.py` - Zone-Based Firewall policies
- `src/tools/qos.py` - QoS profile management examples
- `tests/unit/tools/test_protect_relays.py` - Write-gate and dry-run test examples

---

**Last Updated**: 2026-10-13
**Maintained By**: UniFi MCP Server Team
