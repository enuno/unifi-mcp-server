# Test plan

How to test the plugin before submitting it, and what to record when you do.

The plugin is two things, and each is tested separately.

| Artifact | What it is | Where it comes from |
|---|---|---|
| Claude plugin | The MCP server plus the operator skills | `dist/claude/unifi-mcp-server/` |
| ChatGPT/Codex plugin | The operator skills only | `dist/chatgpt/unifi-mcp-server/` |

Both are built from the same `skills/` directory.

## 1. Build

```bash
python scripts/generate_skills_manifest.py
python scripts/build_plugin_packages.py
```

Expected: 10 operator skills in each package, and 6 developer skills left in the repository and not in either package.

## 2. Validate the manifests

```bash
python scripts/validate_plugins.py
claude plugin validate . --strict
claude plugin validate dist/claude/unifi-mcp-server --strict --profile directory
```

Expected: the version agrees across `pyproject.toml`, `server.json`, `plugin.json`, `marketplace.json` and `skills/manifest.json`; every skill a manifest names exists; no manifest carries a secret.

## 3. Confirm the skill set

```bash
claude plugin validate dist/claude/unifi-mcp-server | grep 'skills:'
```

Expected: exactly 10 skills, all named `unifi-mcp-server:<skill>`, and none of the 6 developer skills. The package must not contain `unifi-mcp-tool-builder`, `unifi-network-config-tools`, `unifi-security-tools`, `unifi-protect-tools`, `unifi-cloud-fleet-tools` or `unifi-docs-sync`.

## 4. Install into Claude Code

```bash
claude plugin marketplace add /path/to/unifi-mcp-server
claude plugin install unifi-mcp-server --marketplace unifi-mcp-server
```

Then, in a Claude Code session:

```
/plugin
```

Expected: the plugin lists its MCP server and its 10 skills.

## 5. Confirm the MCP server starts

Set the credential and start a session:

```bash
export UNIFI_API_KEY="<a UniFi API key for a test controller>"
```

Run `/mcp` in Claude Code. Expected:

- The server appears as `plugin:unifi-mcp-server:unifi`.
- It connects over stdio.
- The tool count matches the profile. With the default `UNIFI_PROFILE=minimal` and `UNIFI_READ_ONLY=true`, the server registers 17 tools.

If the server does not connect, the usual cause is `UNIFI_API_KEY` being unset. Claude Code warns with `Missing environment variable` and loads the server with the `${UNIFI_API_KEY}` text unexpanded.

## 6. Confirm the safe defaults

Run each of these and record what happened.

| Check | How | Expected |
|---|---|---|
| Read-only by default | Ask the agent to restart a device | The tool is not registered, so the agent says the tool does not exist |
| Minimal profile by default | Ask for a firewall policy | The firewall tools are not in the `minimal` profile, so the agent reports that they are unavailable |
| No credential in the package | `grep -r UNIFI_API_KEY dist/` | Only `${UNIFI_API_KEY}` placeholders |
| No telemetry | Check the server startup log | No agnost line, because `AGNOST_ENABLED` and `AGNOST_ORG_ID` are unset |

## 7. Run the three example prompts

Use the prompts in [example-prompts.md](example-prompts.md) against a test controller that has sample data. For each, record:

- The skill that loaded.
- The tools that were called.
- Whether the result was correct against the controller's own UI.
- Whether the agent asked for confirmation before any write.

The third prompt is the one to watch. The agent must not have changed anything before the user confirmed.

## 8. Test the opt-in path

```bash
export UNIFI_READ_ONLY=false
export UNIFI_PROFILE=security
```

Restart the session and confirm:

- The tool count rises to the profile's count.
- The write tools are registered.
- A write still needs `confirm=True`.

With `UNIFI_PROFILE=security` and read-only off, the server registers 47 tools.

## 9. Test the ChatGPT package

The ChatGPT package carries no MCP server, so it can only be tested by upload.

Before uploading, confirm the archive is skills-only:

```bash
unzip -l dist/chatgpt/unifi-mcp-server.zip
```

Expected: `plugin.json`, `.claude-plugin/plugin.json`, `skills/<name>/SKILL.md` for 10 skills, `LICENSE`, `README.md` and the icon. No `.mcp.json` and no `marketplace.json`.

The upload itself, and the review of the generated `.codex-plugin/plugin.json`, are the user's steps. See [../CHATGPT_CONNECTOR.md](../CHATGPT_CONNECTOR.md).

## 10. What to record

Keep the output of every command above, especially:

- The `claude plugin validate` results, with their exit codes.
- The installed-skill list from `/plugin`.
- The `/mcp` tool count.
- The three example prompts and their results.

These are the evidence a reviewer would ask for, and the directory's own review process runs an automated scan and a policy review on the submitted folder.

## Not covered

- **The MCP-enabled ChatGPT variant.** It needs a hosted endpoint that does not exist. See [../CHATGPT_CONNECTOR.md](../CHATGPT_CONNECTOR.md).
- **The Grok connector.** Same blocker. See [../GROK.md](../GROK.md).
- **Cloud API mode against a live Site Manager account.** The test plan above assumes a controller the tester owns. `TODO(verify)`: whether the directory's review needs a cloud-mode test account.
