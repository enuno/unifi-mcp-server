# UniFi MCP Server — Skills Guide

Agent skills are Markdown files with YAML frontmatter (`name`, `description`) that an AI agent reads on demand. They tell the agent which UniFi tools exist, which API mode each needs, and how to use them safely, without keeping every tool definition in context.

This repository ships two sets of skills in `skills/`, one folder per skill:

- **Operator skills** help an agent *use* a running UniFi MCP server.
- **Developer skills** help a coding agent *change* this codebase.

The root `SKILL.md` is a one-file overview of the whole server (setup, API modes, capability domains, example prompts).

A third skill, `mintlify-docs`, lives in `.mintlify/skills/` because Mintlify serves it from there. It helps an agent maintain, validate and publish this site's documentation.

---

## Operator skills (using the server)

| Skill | Covers |
|---|---|
| `skills/unifi-network/` | Clients, networks and VLANs, WiFi, DHCP reservations, DNS, WAN, vouchers |
| `skills/unifi-devices/` | Inventory, adoption, restarts and upgrades, radios, port profiles, switching, topology, diagnostics |
| `skills/unifi-security/` | Firewall rules and groups, zone-based firewall, ACL rules, port forwarding, VPN, content filtering |
| `skills/unifi-system/` | Sites, backups, QoS and traffic routes, traffic flows, DPI, RADIUS, guest portal, traffic matching lists |
| `skills/unifi-channel-planning/` | Building a low-interference WiFi channel plan from neighbor scans |

## Developer skills (changing the codebase)

| Skill | Covers |
|---|---|
| `skills/unifi-mcp-tool-builder/` | The workflow for adding any MCP tool: model, tool function, registration, tests, docs |
| `skills/unifi-network-config-tools/` | Network configuration tools: URL spaces, site ID translation, read-modify-write updates, caching |
| `skills/unifi-security-tools/` | Firewall, ZBF, ACL, traffic matching list, port forward and RADIUS tools, and their risk tiers |
| `skills/unifi-protect-tools/` | The `protect_*` modules: Protect client and paths, v7 models, the write pattern |
| `skills/unifi-cloud-fleet-tools/` | Site Manager, connector, integration API, Mobility, InnerSpace, Carrier, and the fleet stack |

The developer skills are also kept in `.claude/skills/` (Claude Code loads them automatically in this repository) and `.agents/skills/` (Codex and other agents). `skills/` is the source of truth: `tests/unit/test_agent_docs.py` fails if a copy differs, and checks that the developer skills cite only paths and names that exist.

The `mintlify-docs` skill follows the same pattern with a different source of truth: `.mintlify/skills/mintlify-docs/SKILL.md` is the original, and `.claude/skills/mintlify-docs/` and `.agents/skills/mintlify-docs/` hold copies of it. The same test keeps those copies in sync.

---

## Installing

Claude Code loads a skill from a folder that contains a `SKILL.md`: `~/.claude/skills/<name>/SKILL.md` for every session, or `.claude/skills/<name>/SKILL.md` for one project. Copy the folders you want.

```bash
git clone https://github.com/enuno/unifi-mcp-server.git
cd unifi-mcp-server

# All operator skills, for every Claude Code session
mkdir -p ~/.claude/skills
cp -r skills/unifi-network skills/unifi-devices skills/unifi-security \
      skills/unifi-system skills/unifi-channel-planning ~/.claude/skills/

# Or just one
cp -r skills/unifi-security ~/.claude/skills/

# The one-file overview, as a skill named "unifi"
mkdir -p ~/.claude/skills/unifi && cp SKILL.md ~/.claude/skills/unifi/SKILL.md

# Into another project instead of your home directory
cp -r skills/unifi-network /path/to/project/.claude/skills/
```

Other agents that read the same format (for example Codex, from `.agents/skills/`) take the same folders. Copy them into that agent's skills directory.

To update, pull the repository and copy the folders again.

## Using

You don't call a skill directly. The agent sees each skill's `description` and loads the skill when your request matches, then uses the UniFi MCP tools it describes. The MCP server must be configured in the same client (see the README's quick start), because the skills describe its tools but do not call the controller themselves.

Example prompts:

- "Which clients are on the guest VLAN right now?" (`unifi-network`)
- "Audit the zone-based firewall for rules that allow WAN to LAN." (`unifi-security`)
- "Which APs share a 5 GHz channel with a neighbor? Propose a channel plan." (`unifi-channel-planning`)
- "Back up the default site, then list the backups." (`unifi-system`)

If the agent does not pick a skill up, name it in the request ("use the unifi-security skill") or make its `description` broader.

### Safety

The skills follow the server's rules: every mutating tool needs `confirm=True`, `dry_run=True` previews a change, and `UNIFI_READ_ONLY=true` removes mutating tools from the server. With bearer tokens, the token's role decides what a call may do: `viewer` reads, `operator` makes ordinary changes, and `admin` is needed for destructive changes, including firewall policy changes.

---

## UNIFI_PROFILE — server-side tool filtering

A skill keeps tool guidance out of context until needed. `UNIFI_PROFILE` goes further and registers only some tool modules, so the client sees fewer tool definitions. Counts are tools the server lists in local mode, including the 4 fleet tools every profile gets.

| Profile | Modules | Tools |
|---|---|---|
| `network` | channel_planning, client_management, clients, dhcp_reservations, dns_management, network_config, networks, vouchers, wans, wifi | 48 |
| `devices` | device_control, device_migration, devices, diagnostics, mac_tags, port_profiles, switching, topology | 53 |
| `security` | acls, content_filtering, firewall, firewall_groups, firewall_policies, firewall_zones, port_forwarding, site_vpn, vpn | 47 |
| `system` | application, backups, connector, dpi, dpi_tools, events, integration_api, the Protect modules, qos, radius, reference_data, site_manager, sites, traffic_flows, traffic_matching_lists | 182 |
| `protect` | the 15 `protect_*` modules | 75 |
| `mobility` / `innerspace` / `carrier` | one module each (cloud APIs, every mode) | 12 / 10 / 15 |
| `minimal` | clients, devices, sites | 19 |
| *(unset or `all`)* | every module for the API type | 343 local, 71 cloud |

An unknown profile logs a warning and loads every module. To expose only non-mutating tools in any profile, set `UNIFI_READ_ONLY=true`.

Example, a security-focused server in Claude Desktop:

```json
{
  "mcpServers": {
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

Profiles apply at startup. Restart the server to change one. Pair a profile with the matching operator skill (for example `UNIFI_PROFILE=security` with `skills/unifi-security/`).

---

## bin/unifi-cli — CLI wrapper

`bin/unifi-cli` calls `unifi-mcp-server cli`, so you can run one tool from a shell or script without a persistent MCP server:

```bash
export PATH="$PATH:/path/to/unifi-mcp-server/bin"
export UNIFI_API_KEY=your-api-key UNIFI_API_TYPE=local UNIFI_LOCAL_HOST=192.168.2.1

unifi-cli list-clients --site default
unifi-cli list-firewall-policies --site default
```
