---
name: unifi-discovery
description: >
  Find what a UniFi MCP Server can do and pick the right backend before
  acting. Use when starting a session, when a tool is missing or returns
  nothing, when choosing between local, cloud and fleet mode, or when
  deciding which tools are safe to call.
---

# UniFi Discovery and Backend Selection

Start here when you do not yet know what this server exposes, or when a tool
you expected is not there. Every other skill in this set assumes you have
made these two decisions: **which backend** answers, and **which tools are
actually registered**.

## Step 1: Find out what is registered

The server's own capability listing is the source of truth. Three ways to
read it, in order of preference.

### The A2A agent card (HTTP deployments)

```bash
curl -s -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
  http://127.0.0.1:3000/a2a/agent-card
```

The card lists every registered tool under `skills`, and summarises the
deployment under `metadata`:

| Field | What it tells you |
|---|---|
| `metadata.toolCount` | How many tools this deployment registered |
| `metadata.readToolCount` / `writeToolCount` / `destructiveToolCount` | The split by risk tier |
| `metadata.domains` | Which capability domains are present (`network`, `protect`, `cloud`, …) |
| `metadata.apiType` | The running API mode: `local`, `cloud-v1` or `cloud-ea` |
| `metadata.readOnly` | Whether mutating tools were filtered out |
| `metadata.dryRun` | Whether every write is forced into a preview |
| `metadata.fleet` | Whether the fleet registry is configured |
| `metadata.apiModes` | The modes this deployment can serve |

The same card is served at `/.well-known/agent-card.json`, and the discovery
manifest at `POST /a2a/discover` adds the per-domain tool inventory:

```bash
curl -s -X POST -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
  -H "Content-Type: application/json" -d '{}' \
  http://127.0.0.1:3000/a2a/discover
```

### The MCP protocol directly

```bash
# List the tools the server exposes
npx @modelcontextprotocol/inspector unifi-mcp-server
```

### The repository card

`agent-card.json` at the repository root is the reference card for a default
local deployment. It is useful for a quick sense of the full tool surface,
but it is a *reference*: what your deployment exposes may be narrower. Trust
the served card, not the file.

## Step 2: Pick the backend

The mode decides which tools exist. Asking for a tool the mode does not
provide is the most common failure.

| Mode | Set it with | What it reaches | Use it for |
|---|---|---|---|
| `local` | `UNIFI_API_TYPE=local` | Your console or gateway on the LAN | Everything: devices, clients, configuration, firewall, Protect |
| `cloud-v1` | `UNIFI_API_TYPE=cloud-v1` | UniFi's stable v1 cloud API | Sites and aggregate statistics only |
| `cloud-ea` | `UNIFI_API_TYPE=cloud-ea` | UniFi's Early Access cloud API | Sites and aggregate statistics only |
| fleet | `DATABASE_URL` set, plus `UNIFI_API_TYPE` | Several controllers behind one server | Many controllers, one endpoint |

**The cloud modes have no per-device control.** No client, device, firewall
or Protect tool is registered in `cloud-v1` or `cloud-ea`. If a task needs
to change a device, it needs `local` mode.

The cloud modes do register the Site Manager, connector, Mobility,
InnerSpace and Carrier Fabric tools, and those need
`UNIFI_SITE_MANAGER_ENABLED=true` to run.

## Step 3: Check the exposure profile

Three settings narrow what the server registers. Read them off the card
before assuming a tool is available.

| Setting | Effect | Your behaviour |
|---|---|---|
| `UNIFI_PROFILE` | Registers only the tool modules in that profile | A missing tool may be a profile, not a bug |
| `UNIFI_READ_ONLY=true` | Registers no mutating tool | Only read tools work; a write tool is absent, not refused |
| `UNIFI_DRY_RUN=true` | Forces `dry_run=True` on every write | Every change comes back as a preview; nothing changes |

The profiles are `minimal`, `protect`, `network`, `security`, `devices` and
`system`. `minimal` is the smallest useful set.

## Step 4: Confirm the server is healthy

```bash
# Liveness: no token needed, no details returned
curl -s http://127.0.0.1:3000/healthz
```

```bash
# The server's own health check, through the tool surface
# (name it as a tool call: health_check)
```

`health_check` reports whether the server can reach its controller. Use it
before a long read or a change, so a failure is attributed correctly.

## Step 5: Check what you are allowed to do

The bearer token's role decides what you may run. The roles, in ascending
order of privilege:

| Role | May run |
|---|---|
| `viewer` | Read tools only |
| `operator` | Read and write tools |
| `admin` | Read, write and destructive tools |
| `fleet-admin` | Everything, including the fleet registry and token tools |

`MCP_AUTH_TOKEN` entries may be written `<role>:<token>`; a bare token is a
break-glass `fleet-admin`. The client sends only the token part.

A tool that needs a higher role than yours is **refused with a permission
error**, not silently skipped. The audit record names the tier that was
needed.

## Common failures

| Symptom | Cause | What to do |
|---|---|---|
| Tool not found | Wrong mode, or the profile does not include it | Read the card's `metadata.domains` and `apiType` |
| Tool not found, cloud mode | Cloud modes have no per-device tools | Use `local` mode, or a Site Manager tool |
| Tool not found, Site Manager | `UNIFI_SITE_MANAGER_ENABLED` is off | Set it to `true` and restart |
| Write tool missing | `UNIFI_READ_ONLY=true` | Read-only is a server mode; ask for it to be turned off |
| Write returns a preview | `UNIFI_DRY_RUN=true` | The preview is the dry run; nothing changed |
| Permission denied | The token's role is too low | Check the role; `admin` covers destructive tools |
| Every call fails to reach the controller | The console is unreachable from this host | Check `UNIFI_LOCAL_HOST`, and the `health_check` result |

## Safety

- A tool's presence does not mean you should call it. Read the skill for
  the domain before making a change.
- Never put a credential in a tool argument unless the tool's own schema
  asks for it, and never in a prompt, a log line or a report.
- The card and the discovery manifest are public metadata. They carry tool
  names and schemas, not controller addresses or credentials.
