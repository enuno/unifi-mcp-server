---
description: Auto-generate and update API.md documentation from tool docstrings
allowed-tools:
  - Read
  - Edit
  - Grep
  - Glob
  - Bash(python:*)
  - Bash(python3:*)
author: project
version: 1.0.0
---

Automatically generate and update API.md documentation from tool docstrings and code.

This command scans all MCP tools and resources, extracts documentation from code, and updates API.md to ensure it stays in sync with the implementation.

**Steps to execute:**

1. Discover all MCP tools:
   - Scan `src/tools/` directory for all tool modules
   - Import each module and extract tool functions
   - Parse docstrings to get:
     - Description
     - Parameters with types and descriptions
     - Return values
     - Raises (errors)
     - Example usage

2. Discover all MCP resources:
   - Scan `src/resources/` directory for resource handlers
   - Extract resource URI templates
   - Document available operations (list, read, subscribe)

3. Categorize tools by functionality:
   - Site Management
   - Device Operations
   - Client Management
   - Network Configuration
   - WiFi/WLAN Management
   - Firewall & Security
   - Port Forwarding
   - DPI (Deep Packet Inspection)
   - Zone-Based Firewall
   - Traffic Flows
   - Vouchers
   - Webhooks

4. Read current API.md to preserve:
   - Overview and introduction sections
   - Authentication details
   - Rate limiting information
   - Error handling guide
   - Custom examples or notes

5. Generate updated documentation:
   - Table of contents with all categories
   - Tool documentation for each category:
     ```markdown
     ### tool_name

     **Description:** Brief description

     **Parameters:**
     - `param1` (type): Description
     - `param2` (type, optional): Description

     **Returns:** Return value description

     **Example:**
     ```json
     {
       "tool": "tool_name",
       "arguments": {
         "param1": "value1"
       }
     }
     ```
     ```

6. Update API.md:
   - Preserve manual sections (overview, auth, errors)
   - Replace tool documentation sections
   - Add new tools that aren't documented
   - Remove documentation for deleted tools
   - Update version number and last updated date

7. Validate documentation:
   - Check for missing descriptions
   - Verify all parameters are documented
   - Ensure examples are valid JSON
   - Check for broken internal links

**Report back with:**

- Number of tools documented
- Number of resources documented
- Tools added to documentation
- Tools removed from documentation
- Tools with incomplete documentation
- Summary of changes made
- Validation results

**Example output:**

```
Documentation Update Complete!

Tools Documented: 40
Resources Documented: 4

Changes:
✓ Added documentation for 2 new tools:
  - create_traffic_flow_rule
  - update_zbf_matrix
✓ Updated 5 tool descriptions
✓ Removed 1 deprecated tool: old_firewall_rule
⚠ Warning: 3 tools missing example usage:
  - get_device_stats
  - list_dpi_restrictions
  - create_port_forward

Categories:
- Site Management: 3 tools
- Device Operations: 6 tools
- Client Management: 5 tools
- Network Configuration: 4 tools
- WiFi/WLAN: 4 tools
- Firewall & Security: 8 tools
- Zone-Based Firewall: 5 tools
- Traffic Flows: 3 tools
- Other: 2 tools

API.md updated successfully!
Last updated: 2025-01-15
```

**Safety checks:**

- Never expose credentials in examples
- Use placeholder values for sensitive data
- Preserve existing manual documentation
- Create backup before major changes
