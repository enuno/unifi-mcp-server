---
name: tool-design-reviewer
description: Use this skill before implementing a new MCP tool to ensure it follows best practices, maintains consistency with existing tools, and is designed for testability and maintainability. Provides pre-implementation design review and recommendations.
---

# Tool Design Reviewer Skill

## Purpose
Review and improve MCP tool designs before implementation to ensure quality, consistency, and adherence to best practices across the UniFi MCP Server's 77+ tools. Prevent design issues that would require costly refactoring later.

## When to Use This Skill
- Before implementing a new MCP tool
- Planning tools for v0.2.0 features (ZBF, QoS, Backup, etc.)
- Refactoring existing tools
- Unsure about tool naming, parameters, or structure
- Want to ensure consistency with existing 69 functional tools
- Need guidance on error handling or safety mechanisms

## Phase 1: Understanding the Requirement

### Step 1: Gather Tool Requirements
Ask the user clarifying questions about the tool they want to create:

**Essential Questions:**
1. What UniFi API endpoint(s) will this tool call?
2. What is the primary purpose/use case for this tool?
3. What parameters should the tool accept?
4. What should the tool return?
5. Is this a read-only or mutating operation?
6. Should this tool support dry-run mode?
7. Does this tool need confirmation for safety?
8. Will this tool be cached (if read-only)?

**Example User Input:**
> "I want to create a tool to delete a firewall zone in the Zone-Based Firewall system."

**Follow-up Questions:**
- What parameters are needed? (site_id, zone_id)
- What safety mechanisms? (confirm=True required)
- What validation is needed? (zone exists, not in use)
- What errors might occur? (zone not found, zone in use, API error)
- What should be returned? (success message, deleted zone details)

### Step 2: Load Context
Review relevant documentation for context:
- `API.md` - Existing tool patterns and conventions
- `README.md` - Tool categorization and organization
- `mcp-builder` skill - MCP best practices
- `AGENTS.md` - Safety and security requirements
- Existing tools in `src/tools/` - Similar tool patterns

## Phase 2: Tool Design Review

### Design Checklist

#### 1. Tool Naming
**Best Practices:**
- Use verb + noun pattern: `create_`, `get_`, `list_`, `update_`, `delete_`
- Be specific and descriptive: `get_firewall_zone` not `get_zone`
- Match existing naming patterns in the codebase
- Use snake_case (Python convention)

**Examples:**
- ✅ Good: `create_firewall_zone`, `list_qos_profiles`, `get_traffic_flows`
- ❌ Bad: `zone`, `makeZone`, `new_fw_zone`

**Review Questions:**
- [ ] Does the name clearly describe what the tool does?
- [ ] Does it follow the verb + noun pattern?
- [ ] Is it consistent with existing tool names?
- [ ] Is it specific enough to avoid confusion?

#### 2. Tool Description
**Best Practices:**
- Clear, concise, one-sentence summary
- Mention the UniFi feature/component
- Include key capabilities or constraints
- Use active voice

**Example Good Descriptions:**
```python
"""
Delete a Zone-Based Firewall zone.

Removes a firewall zone from the UniFi Network configuration.
Requires confirmation and validates that the zone is not currently
in use by any network or device assignments.
"""
```

**Review Questions:**
- [ ] Is the description clear and concise (1-3 sentences)?
- [ ] Does it explain what the tool does?
- [ ] Does it mention important constraints or requirements?
- [ ] Is it written in active voice?

#### 3. Parameters Design

**Required Parameters:**
```python
async def tool_name(
    site_id: str = "default",  # Always include site_id
    # ... other required params
) -> dict:
```

**Best Practices for Parameters:**
1. **Always include `site_id`** - Default to "default"
2. **Use type hints** - All parameters must have types
3. **Provide defaults where sensible** - Use `None` for optional params
4. **Use descriptive names** - `network_id` not `net_id`
5. **Follow existing patterns** - Check similar tools

**Safety Parameters (for mutating operations):**
```python
async def delete_something(
    site_id: str = "default",
    resource_id: str,
    confirm: bool = False,  # REQUIRED for destructive operations
    dry_run: bool = False,  # OPTIONAL for preview
) -> dict:
```

**Review Questions:**
- [ ] Does it include `site_id` parameter?
- [ ] Are all parameters type-hinted?
- [ ] Do mutating operations require `confirm=True`?
- [ ] Are optional parameters properly defaulted?
- [ ] Are parameter names descriptive and consistent?
- [ ] Does it follow patterns from similar existing tools?

#### 4. Return Value Design

**Best Practices:**
```python
# Read-only tools - return data directly
async def get_firewall_zone(site_id: str, zone_id: str) -> dict:
    """Return zone details."""
    return zone_data

# Mutating tools - return operation result with details
async def create_firewall_zone(
    site_id: str,
    name: str,
    zone_type: str,
    confirm: bool = False
) -> dict:
    """Return created zone with ID."""
    return {
        "_id": "zone-123",
        "name": "LAN",
        "type": "INTERNAL",
        "created": True
    }

# List tools - return list of items
async def list_firewall_zones(site_id: str) -> list:
    """Return list of zones."""
    return zones_list
```

**Review Questions:**
- [ ] Is the return type specified (dict, list, bool)?
- [ ] Does it return useful information to the caller?
- [ ] For mutating operations, does it confirm what was changed?
- [ ] Is the return structure consistent with similar tools?

#### 5. Error Handling

**Required Error Checks:**
```python
async def tool_name(site_id: str, confirm: bool = False):
    # 1. Validate inputs
    if not site_id:
        raise ValueError("site_id cannot be empty")

    # 2. Check safety mechanisms
    if not confirm:
        raise ValueError(
            "This is a destructive operation. "
            "Set confirm=True to proceed."
        )

    # 3. Handle API errors
    try:
        result = await client.request("DELETE", endpoint)
    except Exception as e:
        raise RuntimeError(f"Failed to delete resource: {e}")

    # 4. Validate response
    if not result.get("data"):
        raise ValueError("Invalid response from UniFi API")

    return result["data"]
```

**Review Questions:**
- [ ] Does it validate all input parameters?
- [ ] Does it check `confirm=True` for destructive operations?
- [ ] Does it handle API errors gracefully?
- [ ] Does it provide meaningful error messages?
- [ ] Does it validate API responses?

#### 6. Async/Await Patterns

**Best Practices:**
```python
# ✅ Good - Proper async function
@mcp.tool()
async def get_data(site_id: str) -> dict:
    """Async tool that awaits API calls."""
    result = await unifi_client.request("GET", endpoint)
    return result["data"]

# ❌ Bad - Missing async or await
@mcp.tool()
def get_data(site_id: str) -> dict:  # Should be async
    result = unifi_client.request("GET", endpoint)  # Should be await
    return result["data"]
```

**Review Questions:**
- [ ] Is the function declared as `async def`?
- [ ] Does it `await` all async calls (client.request, cache operations)?
- [ ] Does it properly handle async context managers if needed?

#### 7. Caching Strategy (Read-Only Tools)

**Caching Best Practices:**
```python
@mcp.tool()
async def list_firewall_zones(site_id: str) -> list:
    """List zones - cache for 5 minutes."""
    cache_key = f"zones:{site_id}"

    # Try cache first
    if cached := await cache.get(cache_key):
        return cached

    # Fetch from API
    result = await client.request("GET", f"/api/s/{site_id}/rest/firewallzone")

    # Cache result
    await cache.set(cache_key, result["data"], ttl=300)  # 5 min

    return result["data"]
```

**Review Questions:**
- [ ] Should this tool be cached? (read-only data that doesn't change often)
- [ ] What TTL is appropriate? (5min, 10min, 1hour)
- [ ] Does it invalidate cache on related mutations?

#### 8. MCP Tool Decorator and Schema

**Best Practices:**
```python
@mcp.tool()
async def create_firewall_zone(
    site_id: str = "default",
    name: str,
    zone_type: str,
    description: str = None,
    confirm: bool = False
) -> dict:
    """
    Create a new Zone-Based Firewall zone.

    Creates a firewall zone in the UniFi Network configuration for
    zone-based traffic policies.

    Args:
        site_id: UniFi site ID (default: "default")
        name: Zone name (e.g., "LAN", "Guest", "IoT")
        zone_type: Zone type ("INTERNAL", "EXTERNAL", "GATEWAY", "VPN")
        description: Optional zone description
        confirm: Must be True to create the zone

    Returns:
        dict: Created zone details with _id

    Raises:
        ValueError: If confirm=False or invalid inputs
        RuntimeError: If API request fails
    """
```

**Review Questions:**
- [ ] Does it use `@mcp.tool()` decorator?
- [ ] Does the docstring follow Google style?
- [ ] Are all parameters documented in Args section?
- [ ] Is the return value documented?
- [ ] Are exceptions documented in Raises section?

## Phase 3: Consistency Review

### Compare with Similar Existing Tools

**Find Similar Tools:**
1. Check `src/tools/firewall.py` for firewall-related tools
2. Check `src/tools/zbf_matrix.py` for ZBF tools
3. Check tools with similar operations (create, delete, list)

**Consistency Checklist:**
- [ ] Parameter names match similar tools (e.g., `zone_id` vs `id`)
- [ ] Return structure matches similar tools
- [ ] Error handling follows same patterns
- [ ] Caching strategy consistent with similar tools
- [ ] Safety mechanisms align with similar tools

**Example Comparison:**
```python
# Existing tool pattern
async def delete_firewall_rule(
    site_id: str,
    rule_id: str,
    confirm: bool = False
) -> dict:

# New tool should follow same pattern
async def delete_firewall_zone(
    site_id: str,
    zone_id: str,  # Consistent with rule_id pattern
    confirm: bool = False
) -> dict:
```

## Phase 4: Test-Driven Design

### Design for Testability

**Questions to ensure testability:**
1. Can the UniFi API client be easily mocked?
2. Are dependencies injected (not hardcoded)?
3. Can success and error paths be tested independently?
4. Are edge cases identifiable from the design?

**Example Testable Design:**
```python
# ✅ Good - Client dependency can be mocked
async def tool_name(site_id: str, client: UniFiClient = None):
    client = client or get_default_client()
    return await client.request("GET", endpoint)

# Test becomes simple:
async def test_tool_name():
    mock_client = AsyncMock()
    mock_client.request.return_value = {"data": [...]}
    result = await tool_name("default", client=mock_client)
    assert result is not None
```

### Identify Test Scenarios

Help the user plan tests before implementation:

**Test Categories:**
1. **Happy path** - Normal successful execution
2. **Invalid inputs** - Empty strings, None, wrong types
3. **API errors** - Connection failures, 404, 500 errors
4. **Business logic** - Validation rules, safety checks
5. **Edge cases** - Boundary conditions, empty lists

**Example Test Plan:**
```
Tests for delete_firewall_zone:
1. Happy path: Successfully delete zone
2. Requires confirmation: Raises error if confirm=False
3. Zone not found: Handles 404 gracefully
4. Zone in use: Validates zone not assigned to networks
5. API error: Handles connection failures
6. Invalid zone_id: Validates input format
```

## Phase 5: Documentation Planning

### What Documentation is Needed?

**Before Implementation:**
- [ ] Tool purpose and use case
- [ ] Parameter descriptions
- [ ] Return value structure
- [ ] Error conditions
- [ ] Example usage

**After Implementation:**
- [ ] Update `API.md` with tool documentation
- [ ] Add examples to README if this is a major new feature
- [ ] Update DEVELOPMENT_PLAN.md progress if part of roadmap

**API.md Template:**
```markdown
### create_firewall_zone

Create a new Zone-Based Firewall zone.

**Parameters:**
- `site_id` (string, optional): Site identifier (default: "default")
- `name` (string, required): Zone name
- `zone_type` (string, required): Zone type (INTERNAL, EXTERNAL, GATEWAY, VPN)
- `description` (string, optional): Zone description
- `confirm` (bool, required): Must be True to create zone

**Returns:**
- `_id` (string): Created zone ID
- `name` (string): Zone name
- `type` (string): Zone type
- `created` (bool): Creation confirmation

**Example:**
\`\`\`python
result = await mcp.call_tool("create_firewall_zone", {
    "site_id": "default",
    "name": "IoT",
    "zone_type": "INTERNAL",
    "description": "IoT devices zone",
    "confirm": True
})
# Returns: {"_id": "zone-123", "name": "IoT", "type": "INTERNAL", "created": True}
\`\`\`

**Errors:**
- `ValueError`: If confirm=False or invalid inputs
- `RuntimeError`: If API request fails
```

## Phase 6: Implementation Recommendations

After reviewing the design, provide recommendations:

### Approval Checklist

**Design is ready for implementation if:**
- [ ] Tool name follows conventions
- [ ] Parameters are well-defined with types
- [ ] Return value is clear and useful
- [ ] Error handling is comprehensive
- [ ] Safety mechanisms in place (confirm, dry_run)
- [ ] Consistent with existing tools
- [ ] Designed for testability
- [ ] Documentation planned

**Recommendations:**
1. **Implement the tool** in `src/tools/[module].py`
2. **Write tests first** (TDD) using `test-strategy` skill
3. **Add to MCP server** in `src/main.py`
4. **Update documentation** using `api-doc-generator` skill
5. **Run quality checks** with `/lint`, `/format`, `/test`

### Implementation Template

Provide this template to the user:

```python
# src/tools/firewall_zones.py

@mcp.tool()
async def [tool_name](
    site_id: str = "default",
    # ... parameters
    confirm: bool = False  # If mutating operation
) -> dict:  # Or list, bool as appropriate
    """
    [One-line description].

    [Detailed description of what this tool does and any important
    constraints or requirements.]

    Args:
        site_id: UniFi site ID (default: "default")
        [param]: [description]
        confirm: Must be True to perform operation (for mutating ops)

    Returns:
        dict: [Description of return value structure]

    Raises:
        ValueError: [When this is raised]
        RuntimeError: [When this is raised]

    Example:
        >>> result = await [tool_name](
        ...     site_id="default",
        ...     [param]="value",
        ...     confirm=True
        ... )
        >>> print(result)
        {[expected output]}
    """
    # 1. Validate inputs
    if not site_id:
        raise ValueError("site_id cannot be empty")

    # 2. Check safety (if mutating operation)
    if not confirm:
        raise ValueError(
            "This is a destructive operation. Set confirm=True to proceed."
        )

    # 3. Build API request
    endpoint = f"/api/s/{site_id}/rest/[resource]"

    # 4. Make API call with error handling
    try:
        result = await unifi_client.request("METHOD", endpoint, json={...})
    except Exception as e:
        raise RuntimeError(f"Failed to [operation]: {e}")

    # 5. Validate and return response
    data = result.get("data")
    if not data:
        raise ValueError("Invalid response from UniFi API")

    return data
```

## Integration with Other Skills

- **Before design**: Review DEVELOPMENT_PLAN.md for feature requirements
- **After design approval**: Use `test-strategy` to plan tests
- **During implementation**: Use `unifi-api-explorer` to test API endpoints
- **After implementation**: Use `api-doc-generator` to update documentation
- **Before commit**: Use `/lint`, `/format`, `/test` slash commands

## Reference Files

Load these when needed:
- `API.md` - Existing tool documentation patterns
- `README.md` - Tool organization and categorization
- `src/tools/*.py` - Existing tool implementations
- `AGENTS.md` - Safety and security requirements
- `mcp-builder` skill - MCP best practices
- `DEVELOPMENT_PLAN.md` - Feature requirements and roadmap

## Success Metrics

A well-designed tool will:
- Pass design review checklist (100%)
- Be consistent with existing tools
- Be easy to test (achieve 80%+ coverage)
- Be maintainable and clear to other developers
- Follow all MCP best practices
- Require minimal refactoring after implementation
