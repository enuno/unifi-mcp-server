---
name: integration-guide
description: Use this skill when integrating major new UniFi features that span multiple components (models, API client, tools, tests, documentation). Provides structured guidance for complex features like QoS, SD-WAN, Backup, and other roadmap items from DEVELOPMENT_PLAN.md.
---

# Integration Guide Skill

## Purpose
Provide comprehensive guidance for integrating major new UniFi features into the MCP server. This skill coordinates the multi-component implementation process, ensuring all aspects (models, API integration, tools, tests, documentation) are properly implemented and integrated.

## When to Use This Skill
- Implementing Phase 3+ features from DEVELOPMENT_PLAN.md
- Adding major new capabilities (QoS, SD-WAN, Backup, VPN)
- Integrating new UniFi applications (Access, Identity, Protect)
- Large-scale feature additions spanning multiple files
- Multi-sprint feature implementation
- Cross-cutting architectural changes

## Phase 1: Feature Analysis

### Step 1: Understand Feature Requirements

Load feature requirements from DEVELOPMENT_PLAN.md:

**Example: Advanced QoS and Traffic Management (Phase 3)**

```markdown
From DEVELOPMENT_PLAN.md:

**Feature**: Advanced QoS and Traffic Management
**Priority**: P1 (High)
**Target Version**: v0.2.0
**Estimated Effort**: 2-3 weeks
**Dependencies**: Traffic Flow analysis (Phase 2)

**Capabilities:**
- Application-based traffic prioritization
- Pre-configured ProAV profiles (Dante, Q-SYS, SDVoE)
- Category-based traffic shaping
- DSCP tagging and remarking operations
- Advanced bandwidth control with schedules
- Queue-based priority assignment (0-7 priority levels)
- Per-application bandwidth limits

**API Endpoints:**
- `/api/s/{site}/rest/qosprofile` - QoS profile management (CRUD)
- `/api/s/{site}/rest/trafficroute` - Traffic routing rules (CRUD)

**Estimated Tools**: 12-15 new MCP tools
```

### Step 2: Break Down Into Components

Identify all components needed:

**Component Checklist:**
1. **Data Models** (`src/models/`)
   - Pydantic models for API responses
   - Validation rules
   - Type-safe structures

2. **API Client Integration** (`src/api/client.py`)
   - New endpoint methods (if needed)
   - Request/response handling
   - Error handling patterns

3. **MCP Tools** (`src/tools/`)
   - Read-only tools (list, get)
   - Mutating tools (create, update, delete)
   - Specialized tools (apply templates, etc.)

4. **Unit Tests** (`tests/unit/`)
   - Model validation tests
   - Tool functionality tests
   - Mock API responses
   - Error handling tests

5. **Documentation** (`docs/`, `API.md`)
   - Tool documentation
   - Usage examples
   - Best practices guide

6. **Integration** (`src/main.py`)
   - Register tools with MCP server
   - Initialize caching if needed

### Step 3: Define Implementation Phases

Plan implementation in logical phases:

**Example: QoS Feature Implementation**

**Phase A: Data Models (2-3 days)**
- Design QoSProfile model
- Design TrafficRoute model
- Design ProAVProfile model
- Write model validation tests

**Phase B: API Client (3-4 days)**
- Test `/api/s/{site}/rest/qosprofile` endpoint
- Test `/api/s/{site}/rest/trafficroute` endpoint
- Document API behavior
- Handle edge cases

**Phase C: Core Tools (5-7 days)**
- Implement CRUD tools for QoS profiles
- Implement CRUD tools for traffic routes
- Add safety mechanisms (confirm, dry_run)
- Write comprehensive tests

**Phase D: Advanced Features (2-3 days)**
- ProAV profile templates
- DSCP tagging operations
- Bandwidth scheduling
- Application-specific tools

**Phase E: Documentation & Polish (1-2 days)**
- Update API.md
- Create QoS usage guide
- Add examples to README
- Final testing and cleanup

## Phase 2: Data Model Design

### Model Design Workflow

**Step 1: Analyze API Responses**

Use `unifi-api-explorer` skill to understand API:

```python
# Explore QoS profile endpoint
async def explore_qos():
    response = await client.request("GET", "/api/s/default/rest/qosprofile")
    print(json.dumps(response['data'][0], indent=2))
```

**Step 2: Design Pydantic Models**

Create type-safe models:

```python
# src/models/qos.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from datetime import datetime

class QoSProfile(BaseModel):
    """QoS profile for traffic prioritization."""

    id: Optional[str] = Field(None, alias="_id")
    site_id: str
    name: str = Field(..., min_length=1, max_length=32)
    priority: int = Field(..., ge=0, le=7, description="0=highest, 7=lowest")
    bandwidth_limit_down: Optional[int] = Field(None, ge=0)
    bandwidth_limit_up: Optional[int] = Field(None, ge=0)
    dscp_marking: Optional[int] = Field(None, ge=0, le=63)
    applications: List[str] = Field(default_factory=list)
    schedule: Optional[str] = None
    enabled: bool = True

    class Config:
        populate_by_name = True

class TrafficRoute(BaseModel):
    """Traffic routing rule for QoS application."""

    id: Optional[str] = Field(None, alias="_id")
    site_id: str
    name: str
    qos_profile_id: str
    match_criteria: dict  # Application, source, destination filters
    action: Literal["PRIORITIZE", "LIMIT", "BLOCK"]
    enabled: bool = True

class ProAVProfile(BaseModel):
    """Pre-configured ProAV QoS profile."""

    name: str
    type: Literal["DANTE", "Q_SYS", "SDVOE", "CUSTOM"]
    priority: int
    dscp_marking: int
    applications: List[str]
    description: str
```

**Step 3: Write Model Tests**

```python
# tests/unit/test_qos_models.py

import pytest
from src.models.qos import QoSProfile, TrafficRoute

class TestQoSProfile:
    def test_valid_profile(self):
        """Test creating valid QoS profile."""
        profile = QoSProfile(
            site_id="default",
            name="Video Conferencing",
            priority=2,
            bandwidth_limit_down=50000,
            dscp_marking=46,
            applications=["zoom", "teams"]
        )
        assert profile.priority == 2
        assert profile.enabled is True

    def test_invalid_priority(self):
        """Test priority validation."""
        with pytest.raises(ValueError):
            QoSProfile(
                site_id="default",
                name="Test",
                priority=10  # Invalid: must be 0-7
            )

    def test_name_length(self):
        """Test name length validation."""
        with pytest.raises(ValueError):
            QoSProfile(
                site_id="default",
                name="",  # Too short
                priority=4
            )
```

## Phase 3: API Integration

### API Integration Workflow

**Step 1: Test Endpoints Manually**

Use interactive testing:

```python
# scripts/test_qos_endpoints.py

async def test_qos_endpoints():
    """Manual endpoint testing script."""

    client = UniFiClient.from_env()

    # Test GET
    print("→ Testing GET /api/s/default/rest/qosprofile")
    profiles = await client.request("GET", "/api/s/default/rest/qosprofile")
    print(f"✅ Found {len(profiles['data'])} profiles")

    # Test POST
    print("→ Testing POST (create)")
    test_profile = {
        "name": "TEST_DELETE_ME",
        "priority": 4,
        "enabled": False
    }
    created = await client.request(
        "POST",
        "/api/s/default/rest/qosprofile",
        json=test_profile
    )
    profile_id = created['data']['_id']
    print(f"✅ Created profile: {profile_id}")

    # Test PUT
    print("→ Testing PUT (update)")
    await client.request(
        "PUT",
        f"/api/s/default/rest/qosprofile/{profile_id}",
        json={"description": "Updated"}
    )
    print("✅ Updated profile")

    # Test DELETE
    print("→ Testing DELETE")
    await client.request(
        "DELETE",
        f"/api/s/default/rest/qosprofile/{profile_id}"
    )
    print("✅ Deleted profile")

    print("\n✅ All QoS endpoints working!")
```

**Step 2: Document API Behavior**

Create API documentation:

```python
# docs/api/QOS_API.md

## QoS Profile API

### List Profiles
GET /api/s/{site}/rest/qosprofile

Response:
{
    "data": [
        {
            "_id": "qos-123",
            "name": "Video Conferencing",
            "priority": 2,
            ...
        }
    ]
}

### Create Profile
POST /api/s/{site}/rest/qosprofile

Request:
{
    "name": "Profile Name",
    "priority": 0-7,
    "bandwidth_limit_down": 50000,  # Optional
    ...
}

Validation:
- name: 1-32 characters
- priority: 0 (highest) to 7 (lowest)
- bandwidth limits: ≥0 kbps

Errors:
- 400: Invalid parameters
- 409: Name already exists
```

## Phase 4: Tool Implementation

### Tool Implementation Workflow

**Step 1: Create Tool File**

```python
# src/tools/qos.py

from fastmcp import FastMCP
from src.api.client import UniFiClient
from src.models.qos import QoSProfile, TrafficRoute
from typing import List, Optional

mcp = FastMCP("QoS Tools")

@mcp.tool()
async def list_qos_profiles(
    site_id: str = "default"
) -> List[dict]:
    """
    List all QoS profiles for traffic prioritization.

    Args:
        site_id: UniFi site ID (default: "default")

    Returns:
        List[dict]: List of QoS profile configurations

    Example:
        >>> profiles = await list_qos_profiles("default")
        >>> for p in profiles:
        ...     print(f"{p['name']}: Priority {p['priority']}")
    """
    client = UniFiClient.from_env()
    endpoint = f"/api/s/{site_id}/rest/qosprofile"

    result = await client.request("GET", endpoint)
    return result.get("data", [])

@mcp.tool()
async def create_qos_profile(
    site_id: str = "default",
    name: str,
    priority: int,
    bandwidth_limit_down: int = None,
    bandwidth_limit_up: int = None,
    dscp_marking: int = None,
    applications: List[str] = None,
    enabled: bool = True,
    confirm: bool = False
) -> dict:
    """
    Create a new QoS profile for traffic prioritization.

    Args:
        site_id: UniFi site ID
        name: Profile name (1-32 chars)
        priority: Priority level (0=highest, 7=lowest)
        bandwidth_limit_down: Download limit in kbps (optional)
        bandwidth_limit_up: Upload limit in kbps (optional)
        dscp_marking: DSCP value 0-63 (optional)
        applications: List of DPI application IDs (optional)
        enabled: Enable profile immediately (default: True)
        confirm: Must be True to create

    Returns:
        dict: Created QoS profile with _id

    Raises:
        ValueError: If confirm=False or invalid parameters
        RuntimeError: If API request fails
    """
    if not confirm:
        raise ValueError("confirm=True required to create QoS profile")

    # Validate with Pydantic model
    profile = QoSProfile(
        site_id=site_id,
        name=name,
        priority=priority,
        bandwidth_limit_down=bandwidth_limit_down,
        bandwidth_limit_up=bandwidth_limit_up,
        dscp_marking=dscp_marking,
        applications=applications or [],
        enabled=enabled
    )

    # Build request payload
    payload = profile.dict(exclude={'id', 'site_id'}, exclude_none=True)

    # Create profile
    client = UniFiClient.from_env()
    endpoint = f"/api/s/{site_id}/rest/qosprofile"

    result = await client.request("POST", endpoint, json=payload)
    return result["data"]

# ... more tools (update, delete, get, etc.)
```

**Step 2: Write Tool Tests**

Use `test-strategy` skill to create comprehensive tests:

```python
# tests/unit/test_qos_tools.py

import pytest
from unittest.mock import AsyncMock
from src.tools.qos import list_qos_profiles, create_qos_profile

@pytest.mark.asyncio
async def test_list_qos_profiles(mock_unifi_client):
    """Test listing QoS profiles."""
    mock_unifi_client.request.return_value = {
        "data": [
            {"_id": "qos-1", "name": "Profile 1", "priority": 2},
            {"_id": "qos-2", "name": "Profile 2", "priority": 4}
        ]
    }

    profiles = await list_qos_profiles("default")

    assert len(profiles) == 2
    assert profiles[0]["name"] == "Profile 1"

@pytest.mark.asyncio
async def test_create_qos_profile_requires_confirm(mock_unifi_client):
    """Test that create requires confirmation."""
    with pytest.raises(ValueError, match="confirm=True required"):
        await create_qos_profile(
            site_id="default",
            name="Test",
            priority=4,
            confirm=False
        )

@pytest.mark.asyncio
async def test_create_qos_profile_validates_priority(mock_unifi_client):
    """Test priority validation."""
    with pytest.raises(ValueError):
        await create_qos_profile(
            site_id="default",
            name="Test",
            priority=10,  # Invalid
            confirm=True
        )
```

**Step 3: Register Tools with MCP Server**

```python
# src/main.py

from src.tools.qos import (
    list_qos_profiles,
    get_qos_profile,
    create_qos_profile,
    update_qos_profile,
    delete_qos_profile,
    # ... more tools
)

# Register all QoS tools
# (FastMCP auto-registers with @mcp.tool() decorator)
```

## Phase 5: Advanced Features

### Template Systems

For features with templates (ProAV, zone templates, etc.):

```python
# src/templates/qos_templates.py

PROAV_TEMPLATES = {
    "DANTE": {
        "name": "Dante Audio",
        "priority": 1,
        "dscp_marking": 46,
        "applications": ["dante"],
        "description": "Optimized for Dante digital audio networking"
    },
    "Q_SYS": {
        "name": "Q-SYS Audio/Video",
        "priority": 1,
        "dscp_marking": 34,
        "applications": ["qsys"],
        "description": "Optimized for Q-SYS AV control systems"
    }
}

@mcp.tool()
async def apply_proav_template(
    site_id: str = "default",
    template_name: str,
    confirm: bool = False
) -> dict:
    """Apply a pre-configured ProAV QoS template."""
    if template_name not in PROAV_TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}")

    template = PROAV_TEMPLATES[template_name]

    return await create_qos_profile(
        site_id=site_id,
        **template,
        confirm=confirm
    )
```

## Phase 6: Documentation

### Documentation Workflow

**Step 1: Update API.md**

Use `api-doc-generator` skill to generate documentation.

**Step 2: Create Feature Guide**

```markdown
# docs/QOS_GUIDE.md

# QoS and Traffic Management Guide

## Overview

Quality of Service (QoS) allows you to prioritize network traffic...

## Quick Start

### Create a QoS Profile

\`\`\`python
profile = await mcp.call_tool("create_qos_profile", {
    "site_id": "default",
    "name": "Video Conferencing",
    "priority": 2,
    "bandwidth_limit_down": 50000,
    "applications": ["zoom", "teams", "webex"],
    "confirm": True
})
\`\`\`

### Apply ProAV Template

\`\`\`python
await mcp.call_tool("apply_proav_template", {
    "site_id": "default",
    "template_name": "DANTE",
    "confirm": True
})
\`\`\`

## Best Practices

1. **Priority Levels**: Reserve 0-2 for critical traffic
2. **DSCP Marking**: Follow RFC 4594 recommendations
3. **Bandwidth Limits**: Set realistic limits based on WAN capacity
...
```

**Step 3: Update README.md**

Add feature to README.md features list and roadmap.

## Phase 7: Integration Testing

### Integration Test Strategy

Create end-to-end tests:

```python
# tests/integration/test_qos_integration.py

@pytest.mark.integration
async def test_qos_workflow():
    """Test complete QoS workflow."""

    # Create profile
    profile = await create_qos_profile(
        site_id="default",
        name="TEST_QOS_INTEGRATION",
        priority=4,
        enabled=False,  # Disabled for safety
        confirm=True
    )

    profile_id = profile["_id"]

    try:
        # List profiles
        profiles = await list_qos_profiles("default")
        assert any(p["_id"] == profile_id for p in profiles)

        # Update profile
        updated = await update_qos_profile(
            site_id="default",
            profile_id=profile_id,
            description="Updated description",
            confirm=True
        )
        assert updated["description"] == "Updated description"

        # Get profile
        fetched = await get_qos_profile("default", profile_id)
        assert fetched["_id"] == profile_id

    finally:
        # Cleanup
        await delete_qos_profile("default", profile_id, confirm=True)
```

## Integration with Other Skills

- **Planning**: Start with this skill to plan integration
- **API Exploration**: Use `unifi-api-explorer` during Phase 3
- **Tool Design**: Use `tool-design-reviewer` before implementing tools
- **Testing**: Use `test-strategy` for comprehensive test coverage
- **Documentation**: Use `api-doc-generator` for API.md updates
- **Release**: Use `release-planner` when feature is complete

## Reference Files

Load for context:
- `DEVELOPMENT_PLAN.md` - Feature requirements and roadmap
- `TODO.md` - Implementation progress tracking
- `API.md` - Existing tool patterns
- `src/models/*.py` - Existing model patterns
- `src/tools/*.py` - Existing tool implementations
- `tests/unit/*.py` - Existing test patterns

## Success Metrics

Feature integration successful when:
- [ ] All components implemented (models, API, tools, tests)
- [ ] Test coverage ≥80% for new code
- [ ] All quality checks pass
- [ ] Documentation complete
- [ ] Integration tests passing
- [ ] No regressions in existing features
- [ ] Feature ready for release
