---
name: unifi-api-explorer
description: Use this skill for interactive UniFi API endpoint research and testing. Guides safe API exploration, helps design Pydantic models from responses, documents API behavior, and generates tool implementation templates. Essential for implementing new features from the roadmap.
---

# UniFi API Explorer Skill

## Purpose
Guide interactive exploration and testing of UniFi API endpoints to accelerate development of new MCP tools. This skill helps safely test API endpoints, understand response structures, design appropriate data models, and document API quirks before full implementation.

## When to Use This Skill
- Implementing new features from DEVELOPMENT_PLAN.md (QoS, SD-WAN, Backup, etc.)
- Researching UniFi API capabilities
- Testing endpoints before creating tools
- Designing Pydantic models from API responses
- Documenting API behavior and limitations
- Troubleshooting API integration issues
- Verifying endpoint availability on specific controller versions

## Phase 1: Safe API Exploration

### Step 1: Identify Target API

Ask the user what they want to explore:

**Common Exploration Scenarios:**
1. New feature implementation (e.g., "QoS profiles for Phase 3")
2. Endpoint verification (e.g., "Does /api/s/{site}/rest/qosprofile work?")
3. Response structure analysis (e.g., "What does traffic flow data look like?")
4. API capability discovery (e.g., "What backup endpoints are available?")

**Gather Context:**
- What feature are you implementing?
- Do you have API documentation? (UniFi docs, community resources)
- What controller version are you using?
- Cloud API or local gateway?

### Step 2: Load API Documentation

**Primary Reference Sources:**
1. **Official UniFi API Docs**: `docs/UNIFI_API.md` (if exists)
2. **Project API Docs**: `API.md`
3. **Development Plan**: `DEVELOPMENT_PLAN.md` (feature requirements)
4. **Community Resources**:
   - Art-of-WiFi UniFi API client (GitHub)
   - Ubiquiti Community Wiki
   - UniFi API Getting Started Guide

**Extract Relevant Information:**
- Endpoint paths and HTTP methods
- Required/optional parameters
- Expected response structure
- Authentication requirements
- Rate limits and constraints

### Step 3: Plan Safe Testing Strategy

**Testing Principles:**
1. **Start with READ operations** - GET requests only
2. **Test on non-production sites** - Use test/sandbox sites
3. **Use dry-run when available** - Preview changes first
4. **Backup before writes** - Ensure you can rollback
5. **Test incrementally** - One endpoint at a time
6. **Document everything** - Record findings immediately

**Safety Checklist:**
- [ ] Using test site or lab environment
- [ ] Starting with GET/read-only requests
- [ ] API key has appropriate permissions
- [ ] Backup of configuration available
- [ ] Ready to rollback if needed

## Phase 2: Interactive API Testing

### Testing Workflow

**Step 1: Environment Setup**

Verify environment variables:
```bash
# Check configuration
echo "API Type: $UNIFI_API_TYPE"
echo "Host: $UNIFI_HOST"
echo "Site: ${UNIFI_SITE:-default}"
```

For local testing:
```python
# Test script template
import asyncio
from src.api.client import UniFiClient

async def test_endpoint():
    client = UniFiClient.from_env()

    # Test GET request
    response = await client.request(
        "GET",
        "/api/s/default/rest/[endpoint]"
    )

    print("Response:", response)
    return response

if __name__ == "__main__":
    asyncio.run(test_endpoint())
```

**Step 2: Test Read-Only Endpoints**

Start with safe GET requests:

```python
# Example: Test QoS profiles endpoint
async def explore_qos_profiles():
    client = UniFiClient.from_env()

    # Test if endpoint exists
    try:
        response = await client.request(
            "GET",
            "/api/s/default/rest/qosprofile"
        )

        print(f"✅ Endpoint works!")
        print(f"Found {len(response.get('data', []))} QoS profiles")

        # Examine first profile
        if response.get('data'):
            first_profile = response['data'][0]
            print("\nExample profile structure:")
            print(json.dumps(first_profile, indent=2))

        return response['data']

    except Exception as e:
        print(f"❌ Endpoint failed: {e}")
        return None
```

**Step 3: Document Response Structure**

Analyze and document the response:

```python
# Document findings
{
    "endpoint": "/api/s/default/rest/qosprofile",
    "method": "GET",
    "status": "working",
    "controller_version": "9.0.156",
    "response_structure": {
        "data": [
            {
                "_id": "string",
                "name": "string",
                "priority": "integer (0-7)",
                "bandwidth_limit": "integer (kbps)",
                "dscp_marking": "integer (0-63)",
                "applications": ["string"],
                "enabled": "boolean"
            }
        ],
        "meta": {
            "rc": "string (ok/error)"
        }
    },
    "notes": [
        "Priority 0 = highest, 7 = lowest",
        "bandwidth_limit is optional",
        "applications is list of DPI app IDs"
    ],
    "quirks": [
        "Empty data array if no profiles configured",
        "Some fields may be null in response"
    ]
}
```

**Step 4: Test Write Operations (Cautiously)**

After understanding read operations:

```python
async def test_create_qos_profile():
    """Test creating a QoS profile (in test site!)."""
    client = UniFiClient.from_env()

    # Minimal test profile
    test_profile = {
        "name": "TEST_PROFILE_DELETE_ME",
        "priority": 4,
        "enabled": False  # Disabled for safety
    }

    try:
        # Create profile
        response = await client.request(
            "POST",
            "/api/s/default/rest/qosprofile",
            json=test_profile
        )

        profile_id = response['data']['_id']
        print(f"✅ Created profile: {profile_id}")

        # Cleanup: Delete test profile
        await client.request(
            "DELETE",
            f"/api/s/default/rest/qosprofile/{profile_id}"
        )
        print(f"✅ Cleaned up test profile")

        return True

    except Exception as e:
        print(f"❌ Create failed: {e}")
        return False
```

## Phase 3: Data Model Design

### From API Response to Pydantic Model

**Step 1: Analyze Response Fields**

Examine a sample response:
```json
{
    "_id": "qos-profile-123",
    "name": "Video Conferencing",
    "priority": 2,
    "bandwidth_limit_down": 50000,
    "bandwidth_limit_up": 10000,
    "dscp_marking": 46,
    "applications": ["zoom", "teams", "webex"],
    "schedule": "always",
    "enabled": true,
    "created_at": 1699564800
}
```

**Step 2: Identify Field Types and Constraints**

Create type mapping:
```python
Field Mapping:
- _id: str (Optional on create, required in response)
- name: str (required, 1-32 chars)
- priority: int (0-7, required)
- bandwidth_limit_down: int (kbps, optional)
- bandwidth_limit_up: int (kbps, optional)
- dscp_marking: int (0-63, optional)
- applications: List[str] (optional, DPI app IDs)
- schedule: str (optional, cron or "always")
- enabled: bool (default: true)
- created_at: int (unix timestamp, read-only)
```

**Step 3: Design Pydantic Model**

Create model with validation:

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
    bandwidth_limit_down: Optional[int] = Field(
        None,
        ge=0,
        description="Download bandwidth limit in kbps"
    )
    bandwidth_limit_up: Optional[int] = Field(
        None,
        ge=0,
        description="Upload bandwidth limit in kbps"
    )
    dscp_marking: Optional[int] = Field(None, ge=0, le=63)
    applications: List[str] = Field(default_factory=list)
    schedule: Optional[str] = Field(
        None,
        description="Cron schedule or 'always'"
    )
    enabled: bool = True
    created_at: Optional[datetime] = None

    @validator('schedule')
    def validate_schedule(cls, v):
        """Validate schedule format."""
        if v and v != 'always':
            # Validate cron format
            parts = v.split()
            if len(parts) != 5:
                raise ValueError("Invalid cron format")
        return v

    @validator('applications')
    def validate_applications(cls, v):
        """Validate application IDs."""
        # Could validate against known DPI app IDs
        return v

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "name": "Video Conferencing",
                "priority": 2,
                "bandwidth_limit_down": 50000,
                "bandwidth_limit_up": 10000,
                "dscp_marking": 46,
                "applications": ["zoom", "teams"],
                "enabled": True
            }
        }
```

**Step 4: Test Model with Real Data**

Validate model works with API responses:

```python
# Test model parsing
async def test_qos_model():
    client = UniFiClient.from_env()
    response = await client.request("GET", "/api/s/default/rest/qosprofile")

    for profile_data in response['data']:
        # Parse with Pydantic
        profile = QoSProfile(**profile_data, site_id="default")

        # Verify validation works
        assert 0 <= profile.priority <= 7
        assert len(profile.name) > 0

        print(f"✅ Parsed: {profile.name}")
```

## Phase 4: Tool Implementation Template

### Generate Tool Skeleton

Based on API exploration, generate tool templates:

**Read Tool Template:**
```python
@mcp.tool()
async def list_qos_profiles(
    site_id: str = "default"
) -> List[dict]:
    """
    List all QoS profiles for traffic prioritization.

    Retrieves Quality of Service profiles configured for
    application-based traffic management.

    Args:
        site_id: UniFi site ID (default: "default")

    Returns:
        List[dict]: List of QoS profile configurations

    Example:
        >>> profiles = await list_qos_profiles("default")
        >>> for p in profiles:
        ...     print(f"{p['name']}: Priority {p['priority']}")
    """
    endpoint = f"/api/s/{site_id}/rest/qosprofile"

    try:
        result = await unifi_client.request("GET", endpoint)
        return result.get("data", [])
    except Exception as e:
        raise RuntimeError(f"Failed to list QoS profiles: {e}")
```

**Create Tool Template:**
```python
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

    # Validate parameters
    if not 0 <= priority <= 7:
        raise ValueError("priority must be 0-7")
    if not 1 <= len(name) <= 32:
        raise ValueError("name must be 1-32 characters")

    # Build request payload
    payload = {
        "name": name,
        "priority": priority,
        "enabled": enabled
    }

    # Add optional fields
    if bandwidth_limit_down is not None:
        payload["bandwidth_limit_down"] = bandwidth_limit_down
    if bandwidth_limit_up is not None:
        payload["bandwidth_limit_up"] = bandwidth_limit_up
    if dscp_marking is not None:
        payload["dscp_marking"] = dscp_marking
    if applications:
        payload["applications"] = applications

    # Create profile
    endpoint = f"/api/s/{site_id}/rest/qosprofile"

    try:
        result = await unifi_client.request("POST", endpoint, json=payload)
        return result["data"]
    except Exception as e:
        raise RuntimeError(f"Failed to create QoS profile: {e}")
```

## Phase 5: API Documentation

### Document Findings

Create comprehensive API documentation:

**Template:**
```markdown
# [Feature Name] API Documentation

## Endpoints

### List [Resources]
- **Path**: `/api/s/{site}/rest/[endpoint]`
- **Method**: GET
- **Auth**: Required (API Key or Session)
- **Rate Limit**: Standard (100/min for Early Access)

**Parameters**: None

**Response**:
```json
{
    "data": [
        {
            "_id": "resource-123",
            "name": "Example",
            ...
        }
    ],
    "meta": {
        "rc": "ok"
    }
}
```

**Status Codes**:
- 200: Success
- 401: Authentication failed
- 404: Site not found
- 500: Server error

**Notes**:
- Empty array if no resources configured
- Sorted by creation date (newest first)

### Create [Resource]
- **Path**: `/api/s/{site}/rest/[endpoint]`
- **Method**: POST
- **Auth**: Required
- **Rate Limit**: Standard

**Request Body**:
```json
{
    "name": "string (required)",
    "field": "value (optional)",
    ...
}
```

**Response**: Created resource with `_id`

**Validation**:
- `name`: 1-32 characters, alphanumeric
- `field`: Valid values only

**Quirks**:
- Field X may be ignored in certain cases
- Field Y defaults to Z if not specified

## Tested Versions
- UniFi Network 9.0.156 ✅
- UniFi Network 8.x.x ❌ (endpoint not available)

## API Behavior Notes
- [Note about caching, timing, etc.]
- [Note about permissions required]
- [Note about dependencies]
```

## Phase 6: Common API Patterns

### Pattern: List/Detail Resources

```python
# List all
GET /api/s/{site}/rest/[resource]

# Get one
GET /api/s/{site}/rest/[resource]/{id}
```

### Pattern: CRUD Operations

```python
# Create
POST /api/s/{site}/rest/[resource]

# Read
GET /api/s/{site}/rest/[resource]/{id}

# Update
PUT /api/s/{site}/rest/[resource]/{id}

# Delete
DELETE /api/s/{site}/rest/[resource]/{id}
```

### Pattern: Command Endpoints

```python
# Trigger operation
POST /api/s/{site}/cmd/[command]
{
    "cmd": "[operation]",
    "mac": "device-mac",  # If device-specific
    ...
}
```

### Pattern: Statistics

```python
# Get stats
GET /api/s/{site}/stat/[resource]

# Query with filters
GET /api/s/{site}/stat/[resource]?start=X&end=Y
```

## Integration with Other Skills

- **Before exploration**: Use `tool-design-reviewer` to plan tool design
- **During exploration**: Use this skill to test and document API
- **After exploration**: Use `test-strategy` to create comprehensive tests
- **Documentation**: Use `api-doc-generator` to update API.md

## Reference Files

Load for context:
- `DEVELOPMENT_PLAN.md` - Feature requirements and API endpoints
- `API.md` - Existing API documentation patterns
- `src/api/client.py` - UniFi API client implementation
- `docs/UNIFI_API.md` - UniFi API reference (if exists)
- `.env.example` - Environment configuration

## Success Metrics

API exploration successful when:
- [ ] Endpoint availability verified
- [ ] Response structure documented
- [ ] Pydantic model created and tested
- [ ] Tool template generated
- [ ] API quirks and limitations documented
- [ ] Ready to implement full tool with tests
