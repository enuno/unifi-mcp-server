# Plugin description

## Short description

One line, for a listing header.

```
Operate UniFi Network, Protect and cloud APIs through the UniFi MCP Server.
```

## Full description

For a listing body or a marketplace entry.

```
Operate a UniFi network from an AI agent. The UniFi MCP Server exposes the
official UniFi Network, UniFi Protect and UniFi cloud APIs as MCP tools, so an
agent can read a network's state and change it through one standard interface.

The plugin ships the operator skills that describe which tools exist, which
API mode each one needs, and how to use them safely, and it starts the MCP
server over stdio with uvx.

It runs against one controller or, in fleet mode, many. The server defaults to
read-only with a small tool profile, so an installed plugin can observe a
network but not change it until the user opts in. Every mutating tool
additionally requires an explicit confirmation, and the 53 tools that can
interrupt service or lock an operator out are classified separately and are
off in read-only mode.

No credential is stored in the plugin. The server reads its UniFi API key from
the user's own environment, talks only to the controller the user configured,
and collects no telemetry unless the user explicitly enables it.
```

## Metadata

| Field | Value | Source |
|---|---|---|
| Name | `unifi-mcp-server` | `plugin.json` `name` |
| Display name | UniFi MCP Server | Derived |
| Version | 0.12.0 | `plugin.json` `version` |
| Author | enuno | `plugin.json` `author` |
| License | Apache-2.0 | `plugin.json` `license` and the `LICENSE` file |
| Homepage | https://github.com/enuno/unifi-mcp-server | `plugin.json` `homepage` |
| Repository | https://github.com/enuno/unifi-mcp-server | `plugin.json` `repository` |
| Icon | `.claude-plugin/icon.png`, 1024x1024 PNG | `plugin.json` `icon` |
| Keywords | unifi, network, protect, mcp, model-context-protocol, infrastructure, firewall, wifi, automation | `plugin.json` `keywords` |
| Documentation | https://unifi-mcp-docs.hashgrid.net/ | The README links to it |
| Support | https://github.com/enuno/unifi-mcp-server/issues | The README links to it |
| Privacy policy | `TODO(verify)` | Not published yet. See the note below |

### The privacy policy gap

The Anthropic directory reads `privacyPolicyUrl` and `termsOfServiceUrl` from `plugin.json`. This project publishes neither yet, because it runs no hosted service and collects no data. Two options for the submission:

1. Publish a short privacy policy that states the plugin runs entirely on the user's machine, sends data only to the user's own controller, and collects no telemetry unless the user enables it. Then set `privacyPolicyUrl` and `termsOfServiceURL`.
2. Leave both fields unset and answer the Data handling step accordingly.

`TODO(verify)`: whether the directory requires these URLs for a plugin bundle that collects no data. The documented rule is in the Directory Policy §3.A, which requires "a clear, accessible privacy policy link" for software that collects user data or connects to a remote service.

## Tools

The server registers 365 tools in local mode, from 64 modules.

| Tier | Count | What it covers |
|---|---|---|
| Read | 215 | Observe controller state |
| Write | 93 | Change controller state, with `confirm=True` |
| Destructive | 53 | Change controller state in a way that can interrupt service or lock an operator out |

A read-only session registers 219 tools and no mutating tool at all. That is
the 215 read-tier tools plus the four fleet tools, which carry no tier.
