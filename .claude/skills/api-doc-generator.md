---
name: api-doc-generator
description: Use this skill to generate and update API.md documentation from code. Automatically extracts tool definitions, parameters, and examples from source code to keep documentation in sync with implementation. Ensures comprehensive and accurate API documentation.
---

# API Documentation Generator Skill

## Purpose
Automate the generation and maintenance of API.md documentation by extracting information from MCP tool definitions, docstrings, and type hints. Ensures API documentation remains accurate and comprehensive as the project grows from 77 to 160+ tools.

## When to Use This Skill
- After implementing new MCP tools
- After major feature releases (v0.2.0, v0.3.0)
- When API.md is out of sync with code
- Before creating release documentation
- After refactoring tool signatures
- Quarterly documentation review

## Phase 1: Scan Source Code

### Step 1: Discover All MCP Tools

Find all tools registered in the MCP server:

```bash
# Search for @mcp.tool() decorators
rg "@mcp\.tool\(\)" src/tools/ -A 5
```

**Tool Categories to Scan:**
```
src/tools/
├── clients.py          # Client management (4 tools)
├── devices.py          # Device management (4 tools)
├── networks.py         # Network query (4 tools)
├── sites.py            # Site query (4 tools)
├── firewall.py         # Firewall rules (3 tools)
├── firewall_zones.py   # ZBF zones (5 tools)
├── zbf_matrix.py       # ZBF policies (5 tools)
├── network_config.py   # Network CRUD (3 tools)
├── device_control.py   # Device operations (3 tools)
├── client_management.py # Client operations (3 tools)
├── wifi.py             # WiFi/SSID (4 tools)
├── port_forwarding.py  # Port forwarding (3 tools)
├── dpi.py              # DPI statistics (3 tools)
├── traffic_flows.py    # Traffic monitoring (15 tools)
└── ... (v0.2.0+ tools)
```

### Step 2: Extract Tool Metadata

For each tool, extract:

1. **Function name** - The tool name
2. **Docstring** - Description, Args, Returns, Raises
3. **Parameters** - Names, types, defaults
4. **Return type** - What the tool returns
5. **Examples** - Usage examples from docstring

**Example Extraction:**
```python
# src/tools/devices.py

@mcp.tool()
async def list_devices(
    site_id: str = "default",
    device_type: str = None
) -> List[dict]:
    """
    List all devices in a UniFi site.

    Retrieves information about all UniFi devices including access points,
    switches, and gateways. Optionally filter by device type.

    Args:
        site_id: UniFi site ID (default: "default")
        device_type: Filter by type (uap, usw, ugw) (optional)

    Returns:
        List[dict]: List of device objects with details

    Raises:
        RuntimeError: If API request fails

    Example:
        >>> devices = await list_devices("default")
        >>> aps = await list_devices("default", device_type="uap")
    """
```

**Extracted Metadata:**
```json
{
    "name": "list_devices",
    "category": "Device Management",
    "description": "List all devices in a UniFi site.",
    "long_description": "Retrieves information about all UniFi devices including access points, switches, and gateways. Optionally filter by device type.",
    "parameters": [
        {
            "name": "site_id",
            "type": "str",
            "default": "\"default\"",
            "required": false,
            "description": "UniFi site ID (default: \"default\")"
        },
        {
            "name": "device_type",
            "type": "str",
            "default": "None",
            "required": false,
            "description": "Filter by type (uap, usw, ugw) (optional)"
        }
    ],
    "returns": {
        "type": "List[dict]",
        "description": "List of device objects with details"
    },
    "raises": [
        {
            "exception": "RuntimeError",
            "condition": "If API request fails"
        }
    ],
    "examples": [
        "devices = await list_devices(\"default\")",
        "aps = await list_devices(\"default\", device_type=\"uap\")"
    ]
}
```

### Step 3: Group Tools by Category

Organize tools by functional category:

**Categories:**
1. **Site Management** (sites.py)
2. **Device Management** (devices.py, device_control.py)
3. **Client Management** (clients.py, client_management.py)
4. **Network Configuration** (networks.py, network_config.py)
5. **Firewall Management** (firewall.py, firewall_zones.py, zbf_matrix.py)
6. **WiFi/SSID Management** (wifi.py)
7. **Port Forwarding** (port_forwarding.py)
8. **DPI Statistics** (dpi.py)
9. **Traffic Flow Monitoring** (traffic_flows.py)
10. **QoS and Traffic Management** (qos.py) - v0.2.0
11. **Backup and Restore** (backup.py) - v0.2.0
12. **And more...**

## Phase 2: Generate Documentation

### Documentation Template

**API.md Structure:**
```markdown
# UniFi MCP Server API Documentation

## Overview

This document provides comprehensive documentation for all MCP tools available in the UniFi MCP Server.

**Current Version**: v0.2.0
**Total Tools**: 77 (69 functional, 8 deprecated)
**Last Updated**: [AUTO-GENERATED DATE]

## Table of Contents

1. [Site Management](#site-management)
2. [Device Management](#device-management)
3. [Client Management](#client-management)
4. [Network Configuration](#network-configuration)
5. [Firewall Management](#firewall-management)
6. [WiFi/SSID Management](#wifissid-management)
7. [Port Forwarding](#port-forwarding)
8. [DPI Statistics](#dpi-statistics)
9. [Traffic Flow Monitoring](#traffic-flow-monitoring)
10. [And more...]

---

## Site Management

Tools for querying and managing UniFi sites.

### list_sites

List all UniFi sites in the controller.

**Parameters:**
- None

**Returns:**
- `List[dict]`: List of site objects

**Example:**
```python
sites = await mcp.call_tool("list_sites", {})
for site in sites:
    print(f"{site['name']}: {site['desc']}")
```

---

### get_site

Get detailed information about a specific site.

**Parameters:**
- `site_id` (string, optional): Site identifier (default: "default")

**Returns:**
- `dict`: Site details including health metrics

**Example:**
```python
site = await mcp.call_tool("get_site", {"site_id": "default"})
print(f"Site health: {site['health']}")
```

**Errors:**
- `RuntimeError`: If site not found or API request fails

---

[... Continue for all tools in each category ...]
```

### Tool Documentation Template

For each tool, generate:

```markdown
### [tool_name]

[Short description from docstring]

[Long description if available]

**Parameters:**
- `param_name` (type, [required|optional]): Description
  - Default: `value` (if applicable)
  - Constraints: [validation rules if applicable]
- [... more parameters ...]

**Returns:**
- `type`: Description of return value
- Structure: [if complex return type]

**Example:**
```python
result = await mcp.call_tool("[tool_name]", {
    "param1": "value1",
    "param2": "value2"
})
# Expected output: [description]
```

**Errors:**
- `ExceptionType`: When this occurs
- [... more exceptions ...]

**Notes:**
- [Important usage notes]
- [Safety considerations for mutating operations]
- [Performance considerations]

**Related Tools:**
- [link to related tools]

---
```

## Phase 3: Validation and Quality Checks

### Validation Checklist

For each tool, verify:

**Documentation Completeness:**
- [ ] Tool name and description present
- [ ] All parameters documented
- [ ] Return type documented
- [ ] At least one usage example
- [ ] Error conditions documented
- [ ] Related tools referenced (if applicable)

**Accuracy Checks:**
- [ ] Parameter types match code
- [ ] Default values match code
- [ ] Required/optional correctly labeled
- [ ] Return type matches function signature
- [ ] Examples are valid Python/TypeScript

**Consistency Checks:**
- [ ] Similar tools use similar documentation format
- [ ] Terminology is consistent
- [ ] Example format is consistent
- [ ] Error documentation follows pattern

### Missing Documentation Detection

Identify tools with incomplete documentation:

```python
# Pseudo-code for validation
for tool in tools:
    issues = []

    if not tool.description:
        issues.append("Missing description")

    if not tool.parameters_documented:
        issues.append("Parameters not documented")

    if not tool.examples:
        issues.append("No usage examples")

    if tool.is_mutating and not tool.safety_notes:
        issues.append("Missing safety notes for mutating operation")

    if issues:
        print(f"⚠️  {tool.name}: {', '.join(issues)}")
```

## Phase 4: Special Sections

### Deprecated Tools Section

Document deprecated tools with migration path:

```markdown
## Deprecated Tools

The following tools are deprecated and will be removed in future versions:

### create_zbf_rule (Deprecated)

**Status:** Deprecated in v0.1.4, will be removed in v0.3.0

**Reason:** Replaced by zone-based firewall tools

**Migration:**
Use Zone-Based Firewall tools instead:
- Create zones with `create_firewall_zone`
- Define zone policies with `update_zbf_policy`
- Assign networks to zones with `assign_network_to_zone`

**Example Migration:**
```python
# Old (deprecated):
await create_zbf_rule(source_network="LAN", dest_network="WAN", action="ACCEPT")

# New (recommended):
lan_zone = await create_firewall_zone(name="LAN", zone_type="INTERNAL")
wan_zone = await create_firewall_zone(name="WAN", zone_type="EXTERNAL")
await update_zbf_policy(source_zone_id=lan_zone["_id"],
                        destination_zone_id=wan_zone["_id"],
                        action="ACCEPT")
```

---
```

### Resource URIs Section

Document MCP resources:

```markdown
## MCP Resources

UniFi MCP Server provides the following MCP resources for structured data access:

### sites://[site_id]

Access site information as a resource.

**URI Pattern:** `sites://[site_id]`

**Example:**
```python
site_data = await mcp.read_resource("sites://default")
```

**Returns:** JSON-formatted site details

---

### sites://[site_id]/devices

List all devices in a site.

**URI Pattern:** `sites://[site_id]/devices`

**Example:**
```python
devices = await mcp.read_resource("sites://default/devices")
```

**Returns:** JSON array of device objects

---
```

## Phase 5: Cross-References and Navigation

### Add Internal Links

Create navigation links between related tools:

```markdown
### create_firewall_zone

[... tool documentation ...]

**Related Tools:**
- [`list_firewall_zones`](#list_firewall_zones) - List all zones
- [`update_firewall_zone`](#update_firewall_zone) - Modify zone
- [`delete_firewall_zone`](#delete_firewall_zone) - Delete zone
- [`assign_network_to_zone`](#assign_network_to_zone) - Assign networks
- [`update_zbf_policy`](#update_zbf_policy) - Configure zone policies

**See Also:**
- [Zone-Based Firewall Guide](ZBF_GUIDE.md)
- [Firewall Migration Guide](MIGRATION.md)
```

### Add Quick Reference

Create quick reference table:

```markdown
## Quick Reference

### All Tools by Category

| Category | Tool Count | Key Tools |
|----------|------------|-----------|
| Site Management | 4 | list_sites, get_site, get_site_health |
| Device Management | 7 | list_devices, get_device, restart_device |
| Client Management | 7 | list_clients, block_client, unblock_client |
| Firewall (ZBF) | 15 | create_firewall_zone, update_zbf_policy |
| Traffic Monitoring | 15 | get_traffic_flows, stream_traffic_flows |
| [... more categories ...] | | |

**Total**: 77 tools (69 functional, 8 deprecated)

### Tools by Operation Type

| Type | Count | Examples |
|------|-------|----------|
| Query (Read-only) | 45 | list_*, get_*, search_* |
| Create | 12 | create_* |
| Update | 8 | update_* |
| Delete | 4 | delete_* |
| Control | 8 | restart_*, block_*, locate_* |
```

## Phase 6: Automation Script

### Auto-Generation Script

Create a script to automate documentation generation:

```python
# scripts/generate_api_docs.py

import ast
import inspect
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

def extract_tools_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """Extract MCP tool metadata from Python file."""
    with open(file_path) as f:
        tree = ast.parse(f.read())

    tools = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check for @mcp.tool() decorator
            if has_mcp_decorator(node):
                tool_info = extract_tool_info(node)
                tools.append(tool_info)

    return tools

def generate_markdown(tools: List[Dict[str, Any]]) -> str:
    """Generate markdown documentation from tool metadata."""
    md = f"# UniFi MCP Server API Documentation\n\n"
    md += f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}\n\n"

    # Group by category
    by_category = group_by_category(tools)

    # Generate table of contents
    md += generate_toc(by_category)

    # Generate tool sections
    for category, category_tools in by_category.items():
        md += f"\n## {category}\n\n"
        for tool in category_tools:
            md += generate_tool_section(tool)

    return md

def main():
    # Scan all tool files
    tools_dir = Path("src/tools")
    all_tools = []

    for tool_file in tools_dir.glob("*.py"):
        tools = extract_tools_from_file(tool_file)
        all_tools.extend(tools)

    # Generate markdown
    markdown = generate_markdown(all_tools)

    # Write to API.md
    with open("API.md", "w") as f:
        f.write(markdown)

    print(f"✅ Generated documentation for {len(all_tools)} tools")

if __name__ == "__main__":
    main()
```

## Integration with Other Skills

- **After implementation**: Use `tool-design-reviewer` to ensure tool is documented
- **During development**: Use this skill to keep API.md updated
- **Before release**: Use `release-planner` which calls this skill
- **Quality check**: Use `/docs` slash command to review documentation

## Reference Files

Load for context:
- `src/tools/*.py` - All tool implementations
- `API.md` - Current API documentation
- `README.md` - Project overview (check consistency)
- `CHANGELOG.md` - Version history

## Success Metrics

Documentation generation successful when:
- [ ] All 77+ tools documented
- [ ] All parameters have descriptions
- [ ] All tools have examples
- [ ] Deprecated tools clearly marked
- [ ] Cross-references complete
- [ ] Quick reference tables accurate
- [ ] No broken internal links
- [ ] Consistent formatting throughout
- [ ] README.md and API.md in sync
