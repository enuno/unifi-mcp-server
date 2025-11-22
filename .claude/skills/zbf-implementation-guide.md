---
name: zbf-implementation-guide
description: Use this skill when implementing Zone-Based Firewall (ZBF) features for UniFi Network 9.0+. Provides comprehensive guidance on ZBF architecture, data models, tool implementation, migration strategies, and best practices for the critical v0.2.0 P0 feature.
---

# Zone-Based Firewall Implementation Guide

## Purpose
Guide the complete implementation of Zone-Based Firewall (ZBF) support for UniFi Network 9.0+, the highest priority (P0) feature for v0.2.0. This skill provides architectural guidance, implementation patterns, and migration strategies for transitioning from traditional firewall rules to modern zone-based security.

## When to Use This Skill
- Implementing Phase 1 of v0.2.0 (Zone-Based Firewall)
- Creating new ZBF tools or data models
- Planning migration from traditional firewall rules
- Understanding ZBF architecture and concepts
- Testing ZBF endpoints with real UniFi controller
- Troubleshooting ZBF API integration issues

## Phase 1: Understanding ZBF Architecture

### ZBF Fundamentals

**What Changed in UniFi Network 9.0:**
- Traditional firewall rules → Zone-based traffic policies
- Device/network grouping into security zones
- Zone-to-zone traffic matrix for policy management
- Simplified management for complex networks

**Zone Types:**
1. **INTERNAL** - Trusted internal networks (LAN, corporate)
2. **EXTERNAL** - Untrusted external networks (WAN, Internet)
3. **GATEWAY** - Gateway/router zone
4. **VPN** - VPN tunnel zones

**Core Concepts:**
- **Zones**: Logical groupings of networks and devices
- **Zone Matrix**: Zone-to-zone traffic policies (ACCEPT, REJECT, DROP)
- **Zone Assignment**: Mapping networks/devices to zones
- **Application Blocking**: DPI-based blocking per zone
- **Guest Integration**: Guest hotspot with ZBF zones

### Current Implementation Status

**Completed (v0.1.4):**
- ✅ Basic zone management tools (create, list, update, assign)
- ✅ Zone matrix tools (get matrix, update policies, block apps)
- ✅ Pydantic data models (FirewallZone, ZonePolicy, etc.)
- ✅ Unit tests (84.13% coverage)

**Remaining Work (TODO.md Phase 1):**
- ❌ Verify endpoints with real UniFi Network 9.0+ controller
- ❌ Additional tools (delete_zone, unassign_network, get_statistics)
- ❌ Migration tool from traditional firewall rules
- ❌ Guest Hotspot integration
- ❌ Zone template system (Corporate, Guest, IoT)
- ❌ Documentation updates

## Phase 2: Data Models Deep Dive

### FirewallZone Model

**Location:** `src/models/firewall_zone.py`

```python
class FirewallZone(BaseModel):
    """Zone-Based Firewall zone configuration."""
    id: Optional[str] = Field(None, alias="_id")
    site_id: str
    name: str
    zone_type: Literal["INTERNAL", "EXTERNAL", "GATEWAY", "VPN"]
    description: Optional[str] = None
    enabled: bool = True
    networks: List[str] = Field(default_factory=list)  # Network IDs
    devices: List[str] = Field(default_factory=list)   # Device IDs
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

**Key Considerations:**
- Use `zone_type` for zone classification
- `networks` and `devices` lists for zone membership
- `enabled` flag for quickly disabling zones
- Store both creation and update timestamps

### ZonePolicy Model

**Location:** `src/models/zbf_matrix.py`

```python
class ZonePolicy(BaseModel):
    """Zone-to-zone traffic policy."""
    source_zone_id: str
    destination_zone_id: str
    action: Literal["ACCEPT", "REJECT", "DROP"]
    priority: int = 1000
    log: bool = False
    description: Optional[str] = None
```

**Policy Actions:**
- **ACCEPT**: Allow traffic
- **REJECT**: Block traffic with ICMP response
- **DROP**: Silently drop traffic

**Priority Rules:**
- Lower numbers = higher priority
- Default priority: 1000
- Range: 1-10000

### ZonePolicyMatrix Model

```python
class ZonePolicyMatrix(BaseModel):
    """Complete zone-to-zone policy matrix."""
    site_id: str
    policies: List[ZonePolicy]
    default_action: Literal["ACCEPT", "REJECT", "DROP"] = "DROP"
```

**Matrix Best Practices:**
- Default to DROP for security
- Explicit ACCEPT policies for allowed traffic
- Document policies with descriptions
- Log important policy matches

## Phase 3: API Endpoint Integration

### Verified Endpoints (Need Confirmation with Real Controller)

**Zone Management:**
```python
# List zones
GET /api/s/{site}/rest/firewallzone

# Create zone
POST /api/s/{site}/rest/firewallzone
{
    "name": "LAN",
    "zone_type": "INTERNAL",
    "description": "Corporate LAN",
    "enabled": true
}

# Update zone
PUT /api/s/{site}/rest/firewallzone/{zone_id}
{
    "name": "Updated Name",
    "description": "Updated description"
}

# Delete zone
DELETE /api/s/{site}/rest/firewallzone/{zone_id}
```

**Zone Matrix:**
```python
# Get zone matrix
GET /api/s/{site}/rest/firewallzonematrix

# Update zone policy
PUT /api/s/{site}/rest/firewallzonematrix
{
    "source_zone_id": "zone-123",
    "destination_zone_id": "zone-456",
    "action": "ACCEPT",
    "priority": 1000
}
```

**Zone Assignment:**
```python
# Assign network to zone
PUT /api/s/{site}/rest/networkconf/{network_id}
{
    "firewall_zone_id": "zone-123"
}
```

### Endpoint Verification Strategy

**Step 1: Read-Only Testing**
Start with safe GET requests:
```python
# List existing zones
zones = await client.request("GET", "/api/s/default/rest/firewallzone")
print(f"Found {len(zones['data'])} zones")

# Get zone matrix
matrix = await client.request("GET", "/api/s/default/rest/firewallzonematrix")
print(f"Matrix has {len(matrix['data'])} policies")
```

**Step 2: Create Test Zone**
Test zone creation in test site:
```python
# Create a test zone
test_zone = {
    "name": "TEST_ZONE",
    "zone_type": "INTERNAL",
    "description": "Test zone - safe to delete",
    "enabled": false  # Disabled for safety
}
result = await client.request(
    "POST",
    "/api/s/default/rest/firewallzone",
    json=test_zone
)
zone_id = result["data"]["_id"]
```

**Step 3: Test Update and Delete**
```python
# Update test zone
await client.request(
    "PUT",
    f"/api/s/default/rest/firewallzone/{zone_id}",
    json={"description": "Updated test zone"}
)

# Delete test zone
await client.request(
    "DELETE",
    f"/api/s/default/rest/firewallzone/{zone_id}"
)
```

**Step 4: Document API Behavior**
Record findings:
- Exact endpoint paths
- Required/optional fields
- Response structure
- Error codes and messages
- API quirks or limitations

## Phase 4: Tool Implementation

### Missing Tools to Implement

**1. delete_firewall_zone**
```python
@mcp.tool()
async def delete_firewall_zone(
    site_id: str = "default",
    zone_id: str,
    confirm: bool = False
) -> dict:
    """
    Delete a Zone-Based Firewall zone.

    IMPORTANT: Validates that zone is not in use before deletion.

    Args:
        site_id: UniFi site ID
        zone_id: Zone ID to delete
        confirm: Must be True to delete

    Returns:
        dict: Deletion confirmation

    Raises:
        ValueError: If confirm=False or zone in use
        RuntimeError: If API request fails
    """
    if not confirm:
        raise ValueError("confirm=True required for deletion")

    # Check if zone is in use
    zone = await get_firewall_zone(site_id, zone_id)
    if zone.get("networks") or zone.get("devices"):
        raise ValueError(
            f"Zone '{zone['name']}' is in use. "
            "Unassign all networks/devices first."
        )

    # Delete zone
    endpoint = f"/api/s/{site_id}/rest/firewallzone/{zone_id}"
    await unifi_client.request("DELETE", endpoint)

    return {"deleted": True, "zone_id": zone_id}
```

**2. unassign_network_from_zone**
```python
@mcp.tool()
async def unassign_network_from_zone(
    site_id: str = "default",
    network_id: str,
    confirm: bool = False
) -> dict:
    """Remove network from its assigned zone."""
    if not confirm:
        raise ValueError("confirm=True required")

    endpoint = f"/api/s/{site_id}/rest/networkconf/{network_id}"
    await unifi_client.request(
        "PUT",
        endpoint,
        json={"firewall_zone_id": None}
    )

    return {"unassigned": True, "network_id": network_id}
```

**3. get_zone_statistics**
```python
@mcp.tool()
async def get_zone_statistics(
    site_id: str = "default",
    zone_id: str
) -> dict:
    """Get traffic statistics for a firewall zone."""
    # This endpoint may not exist - needs verification
    endpoint = f"/api/s/{site_id}/stat/firewallzone/{zone_id}"

    try:
        result = await unifi_client.request("GET", endpoint)
        return result["data"]
    except Exception:
        # Fallback: aggregate stats from zone networks
        return await _calculate_zone_stats_from_networks(site_id, zone_id)
```

## Phase 5: Migration Strategy

### Traditional Firewall → ZBF Migration

**Migration Tool Design:**
```python
@mcp.tool()
async def migrate_firewall_rules_to_zbf(
    site_id: str = "default",
    dry_run: bool = True,
    confirm: bool = False
) -> dict:
    """
    Migrate traditional firewall rules to Zone-Based Firewall.

    Strategy:
    1. Analyze existing firewall rules
    2. Group networks by common rules → zones
    3. Create zones for each network group
    4. Create zone-to-zone policies
    5. Assign networks to zones
    6. (Optional) Disable old rules

    Args:
        site_id: UniFi site ID
        dry_run: Preview migration without making changes
        confirm: Must be True to perform migration

    Returns:
        dict: Migration plan and results
    """
```

**Migration Steps:**

1. **Analyze Current Rules**
```python
# Get all firewall rules
rules = await list_firewall_rules(site_id)

# Categorize by source/destination
lan_to_wan = [r for r in rules if r["src_type"] == "LAN" and r["dst_type"] == "WAN"]
lan_to_guest = [r for r in rules if r["src_type"] == "LAN" and r["dst_type"] == "GUEST"]
# etc.
```

2. **Identify Zone Candidates**
```python
# Common zone patterns
zones = {
    "CORPORATE_LAN": {"type": "INTERNAL", "networks": [...]},
    "GUEST": {"type": "INTERNAL", "networks": [...]},
    "IOT": {"type": "INTERNAL", "networks": [...]},
    "WAN": {"type": "EXTERNAL", "networks": [...]}
}
```

3. **Create Zones**
```python
for zone_name, zone_config in zones.items():
    zone = await create_firewall_zone(
        site_id=site_id,
        name=zone_name,
        zone_type=zone_config["type"],
        confirm=confirm
    )
    zone_ids[zone_name] = zone["_id"]
```

4. **Create Zone Policies**
```python
# LAN can access WAN
await update_zbf_policy(
    site_id=site_id,
    source_zone_id=zone_ids["CORPORATE_LAN"],
    destination_zone_id=zone_ids["WAN"],
    action="ACCEPT",
    confirm=confirm
)

# LAN can access IoT (but not reverse)
await update_zbf_policy(
    site_id=site_id,
    source_zone_id=zone_ids["CORPORATE_LAN"],
    destination_zone_id=zone_ids["IOT"],
    action="ACCEPT",
    confirm=confirm
)
```

5. **Assign Networks to Zones**
```python
for zone_name, zone_config in zones.items():
    for network_id in zone_config["networks"]:
        await assign_network_to_zone(
            site_id=site_id,
            network_id=network_id,
            zone_id=zone_ids[zone_name],
            confirm=confirm
        )
```

### Migration Best Practices

**Safety Measures:**
- ✅ Always start with `dry_run=True`
- ✅ Test in non-production site first
- ✅ Backup configuration before migration
- ✅ Keep traditional rules until ZBF validated
- ✅ Migrate in phases (one zone at a time)
- ✅ Document migration mapping

**Validation Checklist:**
- [ ] All networks assigned to appropriate zones
- [ ] Zone-to-zone policies match intended traffic flow
- [ ] No unexpected traffic blocks
- [ ] Guest network isolation maintained
- [ ] IoT segmentation preserved
- [ ] VPN access working correctly

## Phase 6: Zone Templates

### Pre-configured Zone Templates

**Template 1: Corporate Network**
```python
CORPORATE_TEMPLATE = {
    "zones": [
        {
            "name": "CORPORATE_LAN",
            "type": "INTERNAL",
            "description": "Trusted corporate networks"
        },
        {
            "name": "GUEST",
            "type": "INTERNAL",
            "description": "Guest WiFi networks"
        },
        {
            "name": "IOT",
            "type": "INTERNAL",
            "description": "IoT devices"
        },
        {
            "name": "WAN",
            "type": "EXTERNAL",
            "description": "Internet connection"
        }
    ],
    "policies": [
        # Corporate can access everything
        {"source": "CORPORATE_LAN", "dest": "WAN", "action": "ACCEPT"},
        {"source": "CORPORATE_LAN", "dest": "IOT", "action": "ACCEPT"},
        {"source": "CORPORATE_LAN", "dest": "GUEST", "action": "ACCEPT"},

        # Guest can only access WAN
        {"source": "GUEST", "dest": "WAN", "action": "ACCEPT"},
        {"source": "GUEST", "dest": "CORPORATE_LAN", "action": "REJECT"},
        {"source": "GUEST", "dest": "IOT", "action": "REJECT"},

        # IoT can access WAN but not internal
        {"source": "IOT", "dest": "WAN", "action": "ACCEPT"},
        {"source": "IOT", "dest": "CORPORATE_LAN", "action": "REJECT"},
        {"source": "IOT", "dest": "GUEST", "action": "REJECT"}
    ]
}
```

**Template 2: Home Network**
```python
HOME_TEMPLATE = {
    "zones": [
        {"name": "TRUSTED", "type": "INTERNAL"},
        {"name": "IOT", "type": "INTERNAL"},
        {"name": "GUEST", "type": "INTERNAL"},
        {"name": "WAN", "type": "EXTERNAL"}
    ],
    "policies": [
        # Trusted can access everything
        {"source": "TRUSTED", "dest": "*", "action": "ACCEPT"},
        # IoT and Guest can only access WAN
        {"source": "IOT", "dest": "WAN", "action": "ACCEPT"},
        {"source": "GUEST", "dest": "WAN", "action": "ACCEPT"}
    ]
}
```

### Apply Template Tool
```python
@mcp.tool()
async def apply_zbf_template(
    site_id: str = "default",
    template_name: str,
    confirm: bool = False
) -> dict:
    """Apply a pre-configured ZBF template."""
    templates = {
        "corporate": CORPORATE_TEMPLATE,
        "home": HOME_TEMPLATE,
        # Add more templates
    }

    template = templates.get(template_name)
    if not template:
        raise ValueError(f"Unknown template: {template_name}")

    # Create zones and policies from template
    # ...
```

## Phase 7: Testing and Validation

### Integration Test Plan

**Test with Real Controller:**
1. Create test zone
2. Assign test network to zone
3. Create zone-to-zone policy
4. Verify traffic behavior
5. Update zone configuration
6. Delete test zone

**Test Cases:**
```python
# test_zbf_integration.py

@pytest.mark.integration
async def test_zbf_end_to_end():
    """Complete ZBF workflow test."""
    # 1. Create zone
    zone = await create_firewall_zone(
        site_id="default",
        name="TEST_ZONE",
        zone_type="INTERNAL",
        confirm=True
    )

    # 2. Assign network
    await assign_network_to_zone(
        site_id="default",
        network_id="test-network-123",
        zone_id=zone["_id"],
        confirm=True
    )

    # 3. Create policy
    await update_zbf_policy(
        site_id="default",
        source_zone_id=zone["_id"],
        destination_zone_id="wan-zone-id",
        action="ACCEPT",
        confirm=True
    )

    # 4. Verify and cleanup
    zones = await list_firewall_zones("default")
    assert any(z["_id"] == zone["_id"] for z in zones)

    await delete_firewall_zone("default", zone["_id"], confirm=True)
```

## Phase 8: Documentation

### Update API.md

Add complete ZBF section to API.md:
- All zone management tools
- Zone matrix tools
- Migration tools
- Usage examples
- Best practices

### Update README.md

Update feature list:
- Zone-Based Firewall (Complete ✅)
- 15 ZBF tools available
- Migration support from traditional rules

### Create ZBF Guide

New file: `docs/ZBF_GUIDE.md`
- ZBF concepts and architecture
- Zone types and use cases
- Migration strategies
- Common patterns
- Troubleshooting

## Integration with Other Skills

- **Before implementation**: Use `tool-design-reviewer` for new ZBF tools
- **During implementation**: Use `unifi-api-explorer` to test endpoints
- **Testing**: Use `test-strategy` for comprehensive test coverage
- **Documentation**: Use `api-doc-generator` to update API.md

## Reference Files

Load these for context:
- `DEVELOPMENT_PLAN.md` - Phase 1 requirements (P0 - Critical)
- `TODO.md` - Phase 1 remaining tasks (~60% complete)
- `src/models/firewall_zone.py` - Zone data models
- `src/tools/firewall_zones.py` - Zone management tools
- `src/tools/zbf_matrix.py` - Zone matrix tools
- `tests/unit/test_zbf_tools.py` - ZBF test examples (84.13% coverage)
- `ZBF_STATUS.md` - ZBF implementation status (if exists)

## Success Metrics

Phase 1 complete when:
- [ ] All ZBF endpoints verified with real controller
- [ ] All 15 ZBF tools implemented and tested
- [ ] Migration tool working for common scenarios
- [ ] Documentation complete and accurate
- [ ] Test coverage > 80% for ZBF modules
- [ ] Integration tests passing
- [ ] Ready for v0.2.0 release
