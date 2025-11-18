---
description: Start MCP Inspector to interactively test UniFi MCP Server tools
allowed-tools:
  - Bash(npx:*)
  - Bash(python:*)
  - Bash(python3:*)
  - Bash(uv:*)
  - Read
  - Write
author: project
version: 1.0.0
---

Launch the MCP Inspector to interactively test and debug UniFi MCP Server tools and resources.

The MCP Inspector is a web-based UI for testing MCP servers, making API calls, and inspecting responses.

**Prerequisites check:**

1. Verify Node.js is installed:

   ```bash
   node --version
   ```

   - If not installed, provide installation instructions

2. Check if .env file exists:
   - If not, copy from .env.example
   - Remind user to add real UniFi credentials

3. Verify UniFi controller is accessible:
   - Check UNIFI_HOST environment variable
   - Provide connection test if needed

**Steps to execute:**

1. Prepare environment:
   - Check .env file has required variables:
     - UNIFI_HOST
     - UNIFI_USERNAME
     - UNIFI_PASSWORD
     - UNIFI_SITE (default: "default")
   - Warn if credentials are placeholder values
   - Offer to help configure if needed

2. Start MCP Inspector:

   ```bash
   npx @modelcontextprotocol/inspector uv run src/main.py
   ```

   - Run in background if user requests
   - Capture startup logs

3. Provide usage instructions:
   - Inspector URL (typically <http://localhost:5173>)
   - How to test tools:
     - Select a tool from the list
     - Fill in required parameters
     - Execute and view response
   - How to test resources:
     - Browse available resources
     - Subscribe to resource updates
     - View resource data

4. Monitor the inspector session:
   - Display connection status
   - Show any errors from the MCP server
   - Log tool invocations for debugging

5. Suggest tools to test first:
   - **get_sites** - List all UniFi sites (no parameters needed)
   - **get_devices** - List devices for a site
   - **get_clients** - List connected clients
   - **get_networks** - List configured networks

**Report back with:**

- MCP Inspector startup status
- URL to access the web UI
- Suggested workflow for testing:
  1. Start with read-only tools
  2. Test resource endpoints
  3. Try tools with parameters
  4. Test error handling (invalid params)
  5. Test confirmation/dry-run for mutating operations

- Quick reference for common tools:

  ```
  Read-only tools (safe to test):
  - get_sites
  - get_devices
  - get_clients
  - get_networks
  - get_wlans
  - list_firewall_rules
  - get_port_forwards

  Mutating tools (use dry_run=true):
  - create_firewall_rule
  - update_device
  - create_network
  - create_wlan
  - block_client
  ```

**Example output:**

```
MCP Inspector Starting...

Environment Check:
✓ Node.js installed (v20.10.0)
✓ .env file found
✓ UniFi credentials configured
✓ UniFi Host: https://192.168.1.1

Starting Inspector:
$ npx @modelcontextprotocol/inspector uv run src/main.py

Inspector running at: http://localhost:5173

Available Tools: 40
Available Resources: 4

Suggested Test Workflow:
1. Open http://localhost:5173 in your browser
2. Test get_sites to verify connectivity
3. Test get_devices with site_name from step 2
4. Explore other tools in categories:
   - Site Management (3 tools)
   - Device Operations (6 tools)
   - Client Management (5 tools)
   - Firewall & Security (8 tools)

Tips:
- Use dry_run=true for mutating operations
- Check the terminal for detailed server logs
- Press Ctrl+C to stop the inspector
```

**Troubleshooting:**

Common issues and solutions:

- Connection refused: Check if UniFi controller is accessible
- Authentication failed: Verify credentials in .env
- SSL errors: Set UNIFI_VERIFY_SSL=false for self-signed certs
- Port already in use: Inspector may already be running

**Safety checks:**

- Warn before testing mutating operations
- Suggest using dry_run mode first
- Never log credentials in output
- Remind about rate limiting for API calls
