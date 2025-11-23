---
name: MCP Bug Report
about: Report a bug found during MCP server live environment testing
title: '[Bug] '
labels: 'bug, needs-triage, mcp-testing'
assignees: ''
---

## Bug Description

<!-- Provide a clear and concise description of the bug -->

The MCP tool `[tool_name]` failed when tested against the **[environment]** environment.

## Error Message

```
[Paste the exact error message here]
```

## Environment Details

- **Environment Type**: [ ] Cloud API (api.ui.com) | [ ] U7 Express Local | [ ] UDM Pro Local | [ ] Other
- **Host/IP**:
- **SSL Verification**: [ ] Enabled | [ ] Disabled
- **MCP Server Version**:
- **Python Version**:
- **UniFi Controller Version**:

## Steps to Reproduce

1. Configure environment:
   ```bash
   export UNIFI_API_TYPE="..."
   export UNIFI_HOST="..." # or UNIFI_LOCAL_HOST
   export UNIFI_LOCAL_VERIFY_SSL="..."
   # Add other relevant environment variables
   ```

2. Start MCP server:
   ```bash
   uv run src/main.py
   ```

3. Test the tool:
   - Via MCP Inspector: `npx @modelcontextprotocol/inspector uv run src/main.py`
   - Via command: `/unifi-mcp-live-test`
   - Other method: [describe]

4. Observe the error

## Expected Behavior

<!-- What should happen when the tool is invoked correctly -->

The tool should execute successfully and return valid data without errors.

## Actual Behavior

<!-- What actually happened -->

The tool failed with the error message shown above.

## Additional Context

<!-- Add any other context about the problem here -->

- **Test Session ID**:
- **Related Log Files**:
- **Network Conditions**:
- **Authentication Method**: [ ] Username/Password | [ ] API Key | [ ] SSO
- **Rate Limiting Observed**: [ ] Yes | [ ] No
- **Reproducibility**: [ ] Always | [ ] Sometimes | [ ] Once

## Tool-Specific Information

<!-- For the specific MCP tool that failed -->

- **Tool Name**: `[tool_name]`
- **Tool Category**: [ ] Site Management | [ ] Device Operations | [ ] Client Management | [ ] Network Config | [ ] Firewall | [ ] Traffic Analytics | [ ] Other
- **Tool Parameters Used**:
  ```json
  {
    "site_name": "default",
    "param2": "value2"
  }
  ```
- **Dry Run Mode**: [ ] Yes | [ ] No | [ ] N/A

## Related Files

<!-- List any files that may be related to this bug -->

- `src/tools/[tool_name].py`
- `src/models/[model_name].py`
- `tests/unit/test_[tool_name].py`
- Configuration file: `.env`

## Possible Root Cause

<!-- If you have insights into what might be causing the issue -->

- [ ] Authentication/Authorization issue
- [ ] API endpoint not available in this environment
- [ ] SSL certificate validation problem
- [ ] Rate limiting or timeout
- [ ] Invalid parameter validation
- [ ] Response format parsing error
- [ ] Other: [describe]

## Impact Assessment

**Severity**: [ ] Critical (blocks all operations) | [ ] High (major functionality broken) | [ ] Medium (workaround available) | [ ] Low (minor inconvenience)

**Affected Users**: [ ] All users | [ ] Cloud API users only | [ ] Local gateway users only | [ ] Specific configuration only

**Workaround Available**: [ ] Yes | [ ] No

<!-- If yes, describe the workaround -->

## Testing Notes

<!-- Additional information from automated testing -->

- **Automated Test Run**: [ ] Yes | [ ] No
- **Test Command**: `/unifi-mcp-live-test`
- **Test Results File**:
- **Error Report**:

---

<!--
This issue template is used by the /unifi-mcp-live-test command to automatically
create bug reports with comprehensive information about MCP server failures
during live environment testing.
-->

**Checklist for Manual Bug Reports**:
- [ ] Error message included
- [ ] Environment details provided
- [ ] Steps to reproduce documented
- [ ] Expected vs actual behavior described
- [ ] Logs or test results attached (if available)
- [ ] Labels applied: `bug`, `needs-triage`, `mcp-testing`
