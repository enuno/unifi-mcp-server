# UniFi MCP Server — Skills Guide

This guide explains how to use the UniFi MCP Server's skill files with AI agents, and how to reduce LLM context overhead using tool profiles.

## Overview

When the UniFi MCP Server runs as a full MCP server, it loads all 215+ tool definitions into the LLM context for every conversation — even when you're not doing anything network-related. The skill system solves this in two complementary ways:

| Approach | How it works | Best for |
|---|---|---|
| **SKILL.md** | A lightweight capability manifest the AI reads on-demand | Always-on awareness without context cost |
| **skills/ files** | Granular domain skills loaded per-task | Targeted guidance for specific tasks |
| **UNIFI_PROFILE** | Server-side tool filtering | Reducing tool count in a persistent MCP session |

---

## SKILL.md — Top-Level Manifest

`SKILL.md` at the repo root is a Claude Code-compatible skill file with YAML frontmatter. It describes all UniFi capabilities, setup instructions, the API mode feature matrix, and example prompts.

### Installation

```bash
# Personal skill (applies to all your Claude Code sessions)
cp SKILL.md ~/.claude/skills/unifi.md

# Project-local skill (only active in this project's sessions)
cp SKILL.md .claude/skills/unifi.md
```

Once installed, Claude Code will see the `unifi` skill in its skill list. The frontmatter `triggers:` section specifies keywords that tell the agent when to load this skill:

```yaml
triggers:
  - UniFi
  - Ubiquiti
  - network clients
  - access point
  - firewall policy
  - ...
```

When a conversation matches a trigger, the agent reads the skill to understand what's available, then decides whether to invoke the MCP server for that task — rather than always keeping 215+ tool definitions in context.

### Frontmatter tuning

If your AI agent responds inconsistently to the skill, you can tune the `description:` field. The description is the primary signal agents use to decide when to load the skill:

```yaml
# More specific (agent loads skill only for explicit UniFi tasks)
description: Manage UniFi Network Controller devices, clients, VLANs, and firewall

# Broader (agent loads skill for any network management topic)
description: Network infrastructure management via UniFi — clients, devices, firewall,
  VLANs, WiFi, backups, traffic analysis, and more
```

---

## Domain Skill Files

The `skills/` directory contains four focused skill files, one per capability domain. Use these when you want tighter guidance for a specific type of task.

| File | Domain | Key tools |
|---|---|---|
| `skills/unifi-network.md` | Networking | Clients, VLANs, WiFi, DHCP, DNS, WAN, vouchers |
| `skills/unifi-devices.md` | Hardware | Inventory, adoption, control, ports, switching, topology |
| `skills/unifi-security.md` | Security | Firewall, ZBF, ACLs, port forwards, VPN, content filtering |
| `skills/unifi-system.md` | Operations | Sites, backups, traffic flows, DPI, RADIUS, QoS |

### Installing domain skills

```bash
# Install all four
cp skills/*.md ~/.claude/skills/

# Or install just the ones you use
cp skills/unifi-security.md ~/.claude/skills/
```

### When to use domain skills vs. SKILL.md

- **Use `SKILL.md`** when you want general UniFi awareness across all domains. Good default.
- **Use domain skills** when you're doing extended work in one area (e.g., a firewall audit session) and want the agent to have detailed tool references without loading unrelated tools.
- **Use both** — they complement each other. `SKILL.md` gives the overview; domain skills give depth.

---

## UNIFI_PROFILE — Server-Side Tool Filtering

When you're running the MCP server full-time (e.g., in Claude Desktop or Cursor), you can reduce the number of tool definitions injected into the LLM context by setting `UNIFI_PROFILE`.

### Available profiles

| Profile | Modules loaded | Tool count (approx.) |
|---|---|---|
| `network` | clients, client_management, networks, network_config, wifi, dhcp_reservations, dns_management, wans, vouchers | ~25 |
| `devices` | devices, device_control, port_profiles, switching, topology, diagnostics | ~20 |
| `security` | firewall, firewall_groups, firewall_zones, firewall_policies, acls, port_forwarding, vpn, site_vpn, content_filtering | ~25 |
| `system` | sites, site_manager, backups, qos, traffic_flows, traffic_matching_lists, dpi, dpi_tools, radius, application | ~40 |
| `minimal` | sites, clients, devices | ~10 |
| *(unset)* | All modules for the API type | 215+ |

### Planned application modes

The existing profile system is the natural place to add more granular, application-specific tool exposure modes that reduce context-window bloat in larger deployments.

| Planned mode | Intended tool surface |
|---|---|
| `network` | network, switching, WiFi, DHCP, DNS, traffic, client tools |
| `protect` | cameras, NVR, events, talkback, Protect workflows |
| `access` | doors, readers, credentials, visitors, access workflows |
| `talk` | UniFi Talk devices, calls, lines, telephony workflows |
| `drive` | UniFi Drive storage, files, sharing, drive workflows |
| `read-only` | `get_*`, `list_*`, `stat_*`, `search_*` only |

### Configuration examples

#### Claude Desktop — security-focused session

```json
{
  "mcpServers": {
    "unifi": {
      "command": "uvx",
      "args": ["unifi-mcp-server"],
      "env": {
        "UNIFI_API_KEY": "your-api-key",
        "UNIFI_API_TYPE": "local",
        "UNIFI_LOCAL_HOST": "192.168.2.1",
        "UNIFI_PROFILE": "security"
      }
    }
  }
}
```

#### Multiple scoped servers (different profiles for different purposes)

```json
{
  "mcpServers": {
    "unifi-network": {
      "command": "uvx",
      "args": ["unifi-mcp-server"],
      "env": {
        "UNIFI_API_KEY": "your-api-key",
        "UNIFI_API_TYPE": "local",
        "UNIFI_LOCAL_HOST": "192.168.2.1",
        "UNIFI_PROFILE": "network"
      }
    },
    "unifi-security": {
      "command": "uvx",
      "args": ["unifi-mcp-server"],
      "env": {
        "UNIFI_API_KEY": "your-api-key",
        "UNIFI_API_TYPE": "local",
        "UNIFI_LOCAL_HOST": "192.168.2.1",
        "UNIFI_PROFILE": "security"
      }
    }
  }
}
```

#### Environment variable (shell)

```bash
export UNIFI_API_KEY=your-api-key
export UNIFI_API_TYPE=local
export UNIFI_LOCAL_HOST=192.168.2.1
export UNIFI_PROFILE=devices

unifi-mcp-server
# Logs: "Local API mode, profile=devices - registering 6 tool module(s)"
```

### When profiles take effect

Profiles filter at server startup — only the specified tool modules are registered with FastMCP. This means the tool definitions sent to the LLM are fewer, not just hidden. If you need tools from a different profile, restart the server with `UNIFI_PROFILE` changed (or omit it for all tools).

---

## bin/unifi-cli — CLI Wrapper

`bin/unifi-cli` is an executable shell script that delegates to the `unifi-mcp-server cli` subcommand. It's useful for:

- Running single tool calls from a terminal without starting a persistent MCP server
- Scripting UniFi operations from shell scripts or Makefiles
- Giving AI agents a CLI surface they can invoke as a subprocess

### Setup

```bash
# Make available on your PATH
cp bin/unifi-cli /usr/local/bin/unifi-cli
chmod +x /usr/local/bin/unifi-cli

# Or add the repo's bin/ to PATH
export PATH="$PATH:/path/to/unifi-mcp-server/bin"
```

### Usage

```bash
export UNIFI_API_KEY=your-api-key
export UNIFI_API_TYPE=local
export UNIFI_LOCAL_HOST=192.168.2.1

unifi-cli list-clients --site default
unifi-cli get-device-details --site default --device-id <id>
unifi-cli list-firewall-policies --site default
```

### In AI agent skill instructions

If you're writing a custom skill that instructs an agent to use the CLI:

```markdown
When the user asks about their UniFi network, use the `unifi-cli` tool
to run commands. Example:
- List clients: `unifi-cli list-clients --site default`
- Block a client: `unifi-cli block-client --site default --mac aa:bb:cc:dd:ee:ff --confirm`
```

---

## Comparison: Full MCP vs. Skill + Profile

| | Full MCP (no profile) | SKILL.md only | Profile MCP | Skill + Profile |
|---|---|---|---|---|
| Tool definitions in LLM context | All 215+ | None | Subset | Subset |
| Works without MCP server running | No | Yes (read-only awareness) | No | No |
| Best for | Power users, automation | Casual awareness | Focused sessions | Focused sessions with AI guide |
| Setup complexity | Low | Minimal | Low | Low |

**Recommended setup for most users:**

1. Install `SKILL.md` as a personal Claude Code skill for always-on awareness.
2. Configure the MCP server in your AI client with `UNIFI_PROFILE=network` or the domain you use most.
3. Spin up a second scoped MCP entry (e.g., `UNIFI_PROFILE=security`) when you need it.

---

## Troubleshooting

**Agent doesn't use the skill**

The skill's `description:` field needs to match how you phrase your requests. Try broadening it:

```yaml
description: >
  Manage UniFi network infrastructure — use for anything involving Ubiquiti
  devices, WiFi, VLANs, firewall, clients, or network monitoring.
```

**Profile loads wrong tools**

Check the server log on startup — it logs the active profile and module count:

```
INFO: Local API mode, profile=security - registering 9 tool module(s)
```

If a tool you need isn't available, either switch profiles or unset `UNIFI_PROFILE` to load all tools.

**Unknown profile name**

An unrecognized or API-incompatible profile stops startup. Valid values:
`network`, `devices`, `security`, `system`, `minimal`, `protect`, `read-only`,
and `all` (or unset). This fail-closed behavior prevents a typo from exposing
the complete tool surface.
