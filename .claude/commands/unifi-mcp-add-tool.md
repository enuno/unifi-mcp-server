---
description: Scaffold a new UniFi MCP tool with model, function, tests, and docs
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(pytest:*)
  - Bash(/Users/elvis/Library/Python/3.12/bin/pytest:*)
author: project
version: 1.0.0
---

Scaffold a complete new MCP tool for the UniFi MCP Server.

This command creates all necessary files and code for a new tool following the project's architecture and standards.

**Steps to execute:**

1. Ask the user for tool details:
   - Tool name (e.g., "get_port_profile")
   - Tool category (e.g., "networks", "devices", "clients", "firewall")
   - Brief description of what the tool does
   - UniFi API endpoint it will use
   - Whether it's a read-only or mutating operation

2. Create or update the Pydantic model in `src/models/`:
   - If the model file for the category doesn't exist, create it
   - Add request/response models based on UniFi API schema
   - Include proper type hints and field descriptions
   - Add validators if needed

3. Create the tool function in `src/tools/`:
   - If the tool file for the category doesn't exist, create it
   - Implement async tool function with proper error handling
   - Add confirmation/dry-run support for mutating operations
   - Include comprehensive docstring with:
     - Description
     - Parameters
     - Returns
     - Raises
     - Example usage

4. Register the tool in `src/main.py`:
   - Add import statement
   - Register tool with FastMCP

5. Create comprehensive unit tests in `tests/unit/`:
   - Test file following naming convention: `test_<category>_tools.py`
   - Include tests for:
     - Success case with mocked API response
     - Error handling (authentication, network, API errors)
     - Validation of parameters
     - Confirmation/dry-run mode (if applicable)
   - Aim for 80%+ coverage

6. Update API.md documentation:
   - Add tool to appropriate category section
   - Include description, parameters, returns, example

7. Run validation:
   - Format code: `black src/ tests/`
   - Check tests: `pytest tests/unit/test_<category>_tools.py -v`
   - Verify registration: `python -c "from src.main import mcp; print(mcp.list_tools())"`

**Report back with:**

- Summary of files created/modified
- Tool registration confirmation
- Test results
- Next steps for integration testing
- Reminder to update TESTING_PLAN.md if needed

**Example workflow:**

```
User: "I want to add a tool to get WLAN groups"
Assistant:
1. Creates src/models/wifi.py with WLANGroupResponse model
2. Creates src/tools/wifi.py with get_wlan_groups() function
3. Updates src/main.py to register the tool
4. Creates tests/unit/test_wifi_tools.py
5. Updates API.md with documentation
6. Runs tests and reports results
```

**Safety checks:**

- Never expose sensitive credentials in code
- Always use async/await for I/O operations
- Include proper type hints for all parameters
- Follow the principle of least privilege
- Validate all user inputs
