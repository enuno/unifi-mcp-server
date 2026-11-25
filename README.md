<p align="center">
  <img src="assets/unifi-mcp-server-logo.png" alt="UniFi MCP Server logo" width="200" height="200">
</p>

<h1 align="center">UniFi MCP Server</h1>

<p align="center">
  <strong>AI-native control of UniFi networks through the Model Context Protocol</strong>
</p>

<p align="center">

  [![CI](https://github.com/enuno/unifi-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/enuno/unifi-mcp-server/actions/workflows/ci.yml)
  [![Security](https://github.com/enuno/unifi-mcp-server/actions/workflows/security.yml/badge.svg)](https://github.com/enuno/unifi-mcp-server/actions/workflows/security.yml)
  [![codecov](https://codecov.io/github/enuno/unifi-mcp-server/graph/badge.svg?token=ZD314B59CE)](https://codecov.io/github/enuno/unifi-mcp-server)
  [![PyPI](https://img.shields.io/pypi/v/unifi-mcp-server.svg)](https://pypi.org/project/unifi-mcp-server/)
  [![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
  [![Documentation](https://img.shields.io/badge/docs-UniFi%20MCP-0D9373)](https://unifi-mcp-docs.hashgrid.net/)
  [![Ask DeepWiki](https://img.shields.io/badge/Ask-DeepWiki-6E56CF)](https://deepwiki.com/enuno/unifi-mcp-server)

</p>

An MCP server that exposes UniFi Network, UniFi Protect and the UniFi cloud APIs (Site Manager, Mobility, InnerSpace, Carrier Fabric) as MCP tools, so AI agents can read and change UniFi infrastructure through one standard interface. It runs against one controller or, in fleet mode, many.

**Current release: 0.12.0.** See [CHANGELOG.md](CHANGELOG.md) for what changed.

  [![UniFi MCP Server MCP server – quality and maintenance score on Glama](https://glama.ai/mcp/servers/enuno/unifi-mcp-server/badges/card.svg)](https://glama.ai/mcp/servers/enuno/unifi-mcp-server)

## Contents

- [Features](#features)
- [API modes](#api-modes)
- [Quick start](#quick-start)
- [Agent skills](#agent-skills)
- [Tool profiles and safety controls](#tool-profiles-and-safety-controls)
- [Network transports and deployment](#network-transports-and-deployment)
- [Calling the server from code](#calling-the-server-from-code)
- [Native MCP prompts](#native-mcp-prompts)
- [Documentation](#documentation)
- [Development](#development)

## Features

365 tools in local mode, from 64 modules.

- **Network:** clients (search, block, reconnect), networks and VLANs, WiFi SSIDs, DHCP reservations, DNS, WAN, guest vouchers, QoS profiles and traffic routes, DPI statistics, traffic flows (including lookup by flow ID), client-connection events and bulk client editing, and Matter/Thread inventory on Network 11.
- **Devices:** inventory, adoption, restart, locate, upgrade, radio settings, port profiles and per-port overrides, switching and stacks, topology export (JSON, GraphML, DOT), diagnostics, WiFi channel planning.
- **Security:** legacy firewall rules and groups, zone-based firewall (zones, policies, zone matrix), ACL rules, traffic matching lists, port forwarding, VPN and site-to-site VPN, content filtering, RADIUS and the guest portal.
- **Protect:** cameras, NVRs, views, events, sensors, lights, chimes, sirens, relays, speakers, alarm hubs and the alarm manager.
- **Cloud:** Site Manager (hosts, sites, cross-site statistics), the connector proxy, Mobility workspaces and devices, InnerSpace floor plans and inventory, Carrier Fabric subscribers and service plans.
- **Operations:** sites, backups (create, schedule, download, restore), events, multi-site aggregation, device migration between sites, console NetFlow export configuration, and gateway packet capture.
- **Fleet mode** (optional, with Postgres and Redis): many controllers behind one server, a controller registry with encrypted credentials, server-issued tokens with roles, a shared read cache, several replicas and background workers, and `fleet_*` tools that read across controllers. See [MULTI_CONTROLLER.md](MULTI_CONTROLLER.md) and [docs/FLEET_SCALING_PLAN.md](docs/FLEET_SCALING_PLAN.md).
- **Native prompts:** eight parameterised UniFi operational workflows (health check, client connectivity, WiFi performance, device investigation, firewall review, change planning, Protect health, fleet summary) exposed through the standard `prompts/list` and `prompts/get` operations. See [docs/PROMPTS.md](docs/PROMPTS.md).
- **Safety:** every mutating tool needs `confirm=True` and supports `dry_run=True`, plus read-only and dry-run server modes, role-based access over risk tiers, and a hash-chained audit log (see [below](#tool-profiles-and-safety-controls)).
- **A2A discovery and delegation:** an agent card built from the live tool registry, served at `/a2a/agent-card` and `/.well-known/agent-card.json`, plus a capability manifest and a delegation endpoint that runs a registered tool under the server's own role, confirmation and audit controls. See [A2A.md](A2A.md).
- **Observability:** Prometheus `/metrics`, `/healthz`, SIEM export of audit records, optional Redis caching, webhooks with HMAC verification.

## API modes

Set `UNIFI_API_TYPE` to choose how the server reaches UniFi.

| Mode | What it reaches | Use it for |
|---|---|---|
| `local` (recommended) | Your UniFi console or gateway on the LAN (`UNIFI_LOCAL_HOST`) | Everything: device and client control, configuration, firewall, Protect |
| `cloud-ea` | UniFi's Early Access cloud API | Sites and aggregate statistics; no per-device control or configuration |
| `cloud-v1` | UniFi's stable v1 cloud API | Sites and aggregate statistics; no per-device control or configuration |

The cloud tools (Site Manager, Mobility, InnerSpace, Carrier Fabric) call `api.ui.com` and are registered in every mode. Set `UNIFI_SITE_MANAGER_ENABLED=true` to use Site Manager tools; actual exposure also depends on the selected profile. The existing Site Manager SD-WAN config list/detail/status reads use the official v1.0.0 `/v1/sd-wan-configs` paths after the 2026-11-08 reconciliation; this does not implement typed destination/performance steering policies, policy writes, or prove live account interoperability (see [API.md](API.md) and [the gap reconciliation](docs/COMPETITOR_GAP_RECONCILIATION.md)).

Site Manager health summaries use the documented `/v1/sites` statistics and
`/v1/isp-metrics/5m` records. These report available values without running a
speed test. The `statistics` fields can differ by UniFi Network version;
unavailable values appear as `null` or `unknown`. The inferred site status
describes device availability; reported internet issue entries appear separately
because they do not by themselves prove a current fault (see [API.md](API.md)).
That data mapping has been checked read-only against one Site Manager account;
the added edge cases use mocked responses, and version-wide live compatibility
has not been verified.

Zone-based firewall tools need UniFi Network 9.0 or later. Some documented UniFi endpoints do not exist on every firmware version; see [docs/UNIFI_API.md](docs/UNIFI_API.md).

The Matter and Thread reads need UniFi Network 11 or later. No published UniFi contract exposes a Matter or Thread path, so these tools are built against routes derived from the vendor's own Network 11.0.97 application package and verified only as far as a Network 10.6 controller allows: both routes answer 404 there, while a control route in the same API family answers 200 with the same API key, which establishes route absence rather than an auth refusal. **A successful Matter or Thread read has not been observed**, so the tools are implemented-needs-verification and report `supported: false` on a controller without the routes. A node's Matter pairing code is never returned. See [the discovery record](docs/research/matter-thread-network-11-discovery.md).

**UniFi Network 11 / UniFi OS 6:** compatible per released documentation, with four items pending live-controller verification — not yet a claim of full support. USG gateways and the classic, self-hosted Network Application Server are removed platform targets; `fleet_health` automatically flags any registered controller with a USG in its device inventory, but there is no API signal to auto-detect a classic Network Application Server, so label that controller instead (e.g. `deployment=classic-server`) and filter on it. Network 11 replaces the statistics engine and resets historical data, so the statistics tools (`get_historical_stats`, `get_speed_test_history`, `get_dpi_statistics`, `list_top_applications`, `get_client_dpi`) attach a `statistics_note` to every empty response — an empty history right after the upgrade is expected, not an outage. See [docs/NETWORK_11_COMPATIBILITY.md](docs/NETWORK_11_COMPATIBILITY.md) for the full compatibility matrix.

## Quick start

### 1. Get an API key

1. Sign in to [UniFi Site Manager](https://unifi.ui.com).
2. Go to **Settings → Control Plane → Integrations** and choose **Create API Key**.
3. Copy the key. It is shown only once.

### 2. Install

```bash
pip install unifi-mcp-server          # or: uv tool install unifi-mcp-server
# Fleet mode extras (Postgres, Redis):
pip install 'unifi-mcp-server[fleet]'
```

Or use the container image (amd64, arm64 and arm/v7; the `-fleet` variant for amd64 and arm64):

```bash
docker pull ghcr.io/enuno/unifi-mcp-server:latest
```

### 3. Add it to your MCP client

Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows), Cursor (`mcp.json`, from **View: Open MCP Settings**) and most other MCP clients take the same `mcpServers` block:

```json
{
  "mcpServers": {
    "unifi": {
      "command": "uvx",
      "args": ["unifi-mcp-server"],
      "env": {
        "UNIFI_API_KEY": "<your-api-key>",
        "UNIFI_API_TYPE": "local",
        "UNIFI_LOCAL_HOST": "192.168.2.1"
      }
    }
  }
}
```

If you installed with `pip`, use `"command": "unifi-mcp-server"` and drop `args`. To run the container instead:

```json
{
  "mcpServers": {
    "unifi": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "UNIFI_API_KEY=your-api-key-here",
        "-e", "UNIFI_API_TYPE=local",
        "-e", "UNIFI_LOCAL_HOST=192.168.2.1",
        "ghcr.io/enuno/unifi-mcp-server:latest"
      ]
    }
  }
}
```

Keep `-i` and do not add `-d`: the client talks to the server over the container's stdin and stdout.

### 4. Main settings

| Variable | Purpose | Default |
|---|---|---|
| `UNIFI_API_KEY` | UniFi API key (required) | — |
| `UNIFI_API_TYPE` | `local`, `cloud-ea` or `cloud-v1` | `cloud-ea` |
| `UNIFI_LOCAL_HOST` / `UNIFI_LOCAL_PORT` | Console address in `local` mode. The port depends on the deployment: `443` for a UniFi OS appliance, `11443` for UniFi OS Server 5.1.15+, `8443` for a legacy Network Application Server (whose support is unverified — see API.md, "Which console port to point at") | — / `443` |
| `UNIFI_LOCAL_VERIFY_SSL` | Verify the console's TLS certificate. `false` logs a warning at startup | `true` |
| `UNIFI_LOCAL_CA_FILE` | CA certificate (PEM) for a self-signed console, instead of turning verification off. Can be the console's own certificate | — |
| `UNIFI_LOCAL_TLS_SERVER_NAME` | Name the console's certificate is checked against, when it is not `UNIFI_LOCAL_HOST`: `unifi.local` for UniFi OS's own certificate | — |
| `UNIFI_DEFAULT_SITE` | Site used when a tool call names none | `default` |
| `UNIFI_SITE_MANAGER_ENABLED` | Enable the cloud tools (Site Manager, Mobility, InnerSpace, Carrier) | `false` |
| `UNIFI_PROFILE` | Register only one group of tools ([profiles](#tool-profiles-and-safety-controls)) | all |
| `UNIFI_READ_ONLY` / `UNIFI_DRY_RUN` | Read-only or preview-only server | `false` |
| `DEBUG` | Registers `debug_api_request` (raw GET/DELETE, destructive tier, removed by read-only). Leave unset in production | unset |
| `MCP_SERVER_TRANSPORT` | `stdio`, `streamable_http`, `http` or `sse` | `stdio` |
| `MCP_AUTH_TOKEN` | Bearer token, required on network transports; `viewer:<token>` (or `operator:`, `admin:`) limits a token's role | — |
| `REDIS_URL` | Optional response cache | — |
| `WEBHOOK_SECRET` | HMAC secret for incoming UniFi webhooks | — |
| `DATABASE_URL` | Turns on fleet mode (Postgres) | — |

[.env.example](.env.example) lists every setting with comments, including audit logging, SIEM export, metrics, Supermemory and agnost.ai.

## Agent skills

The `skills/` directory contains 16 installable agent skills. Each is a Markdown `SKILL.md` that an AI agent loads when relevant: operator skills guide safe use of a running server; developer skills give repository-specific implementation procedures. The summaries below describe when to use each skill and its main workflow. Follow the linked `SKILL.md` for complete tool references, prerequisites, examples, safety gates, and troubleshooting guidance.

**Using the server (operator skills)**

| Skill | When to use it and what it covers |
|---|---|
| [`unifi-network`](skills/unifi-network/SKILL.md) | Inspect and manage connected clients, networks/VLANs, WiFi/SSIDs, DHCP reservations, DNS filters, WAN connections, and guest vouchers. |
| [`unifi-devices`](skills/unifi-devices/SKILL.md) | Inventory, adopt, diagnose, restart, or upgrade UniFi hardware; configure radios, port profiles, switching, stacks, and topology. |
| [`unifi-security`](skills/unifi-security/SKILL.md) | Review or manage firewall rules/groups, zone-based firewall, ACLs, port forwarding, VPNs, and content filtering; observe local-mode and firmware requirements. |
| [`unifi-system`](skills/unifi-system/SKILL.md) | Administer sites and backups; investigate QoS/routes, traffic flows, DPI, RADIUS, guest portal, and traffic matching lists. |
| [`unifi-protect`](skills/unifi-protect/SKILL.md) | Work with cameras, NVRs, alarms, sensors, chimes, sirens, lights, viewers, events, and Protect configuration, with privacy and safety considerations. |
| [`unifi-fleet-operations`](skills/unifi-fleet-operations/SKILL.md) | Operate multiple controllers through one server: select the target controller, route calls, inspect fleet health, manage registry entries, and understand fan-out limits. |
| [`unifi-channel-planning`](skills/unifi-channel-planning/SKILL.md) | Turn AP and neighbor observations into a low-interference channel plan, including planning constraints, scoring, validation, and safe rollout. |
| [`unifi-discovery`](skills/unifi-discovery/SKILL.md) | Check what a server exposes, its health and profile, then choose the appropriate local, cloud, or fleet backend before using tools. |
| [`unifi-safe-changes`](skills/unifi-safe-changes/SKILL.md) | Gate state changes with `confirm`, `dry_run`, read-only mode, risk awareness, rollback planning, and audit checks. Use when a mutation is proposed or a call is refused. |
| [`unifi-mcp-setup`](skills/unifi-mcp-setup/SKILL.md) | Set up or configure the server: installation, environment variables, API-mode capability matrix, profiles, and example prompts. |

**Changing this codebase (developer skills)**

| Skill | When to use it and what it covers |
|---|---|
| [`unifi-mcp-tool-builder`](skills/unifi-mcp-tool-builder/SKILL.md) | Add an MCP tool end to end: research the API, design models and function behavior, register it, write tests, and update documentation. |
| [`unifi-network-config-tools`](skills/unifi-network-config-tools/SKILL.md) | Implement or test Network configuration tools, including endpoint URL spaces, site-ID translation, read-modify-write behavior, caching, and firmware-specific cases. |
| [`unifi-security-tools`](skills/unifi-security-tools/SKILL.md) | Implement or test security tools across firewall, ZBF, ACL, port forwarding, traffic matching, RADIUS, and related areas; covers endpoint/ID mapping and risk tiers. |
| [`unifi-protect-tools`](skills/unifi-protect-tools/SKILL.md) | Implement or test Protect modules, HTTP/WebSocket paths, v7 models, response shapes, and the confirmed/dry-run write pattern. |
| [`unifi-cloud-fleet-tools`](skills/unifi-cloud-fleet-tools/SKILL.md) | Implement or test Site Manager, connector, integration API, Mobility, InnerSpace, Carrier Fabric, and fleet routing/authentication. |
| [`unifi-docs-sync`](skills/unifi-docs-sync/SKILL.md) | Keep the live tool registry, A2A card, native prompt catalog, API reference, skills, and generated artifacts aligned; includes the drift-test workflow. |

### Install

Claude Code loads skills from `~/.claude/skills/<name>/SKILL.md` (every session) or `<project>/.claude/skills/<name>/SKILL.md` (one project). Copy the folders you want:

```bash
git clone https://github.com/enuno/unifi-mcp-server.git
cd unifi-mcp-server
mkdir -p ~/.claude/skills

# All operator skills
cp -r skills/unifi-network skills/unifi-devices skills/unifi-security \
      skills/unifi-system skills/unifi-protect skills/unifi-fleet-operations \
      skills/unifi-channel-planning skills/unifi-discovery \
      skills/unifi-safe-changes skills/unifi-mcp-setup ~/.claude/skills/

# Or one skill
cp -r skills/unifi-security ~/.claude/skills/

# The one-file overview of the whole server
cp -r skills/unifi-mcp-setup ~/.claude/skills/
```

Note: `npx skills` (and similar package-skill installers) only install a
`SKILL.md` at the repository root, not the folders under `skills/`. Install
individual skills with the `cp -r skills/<name>` commands above instead of
relying on a root-level skill file.

Other agents that read the same `SKILL.md` format take the same folders; copy them into that agent's skills directory (Codex, for example, reads `.agents/skills/`). To update, pull and copy again. Inside this repository the developer skills are already installed for Claude Code (`.claude/skills/`) and Codex (`.agents/skills/`).

### Use

You don't invoke a skill yourself. The agent reads each skill's description and loads the one that matches your request, then calls the MCP tools it describes, so the MCP server must also be configured in the same client. For example:

- "Which clients are on the guest VLAN right now?" loads `unifi-network`.
- "Audit the zone-based firewall for anything that allows WAN to LAN." loads `unifi-security`.
- "Which APs share a 5 GHz channel with a neighbor? Propose a channel plan." loads `unifi-channel-planning`.
- "Which controller should I target, and what tools does this server expose?" loads `unifi-discovery`.
- "Plan maintenance across APs managed by two controllers." loads `unifi-fleet-operations`.
- "Preview a VLAN change and explain how to roll it back." loads `unifi-safe-changes`.

If the agent doesn't pick a skill up, name it ("use the unifi-security skill"). Pair a skill with the matching `UNIFI_PROFILE` to keep the tool list small too. [docs/SKILLS.md](docs/SKILLS.md) has additional guidance on skill installation and profiles.

## Tool profiles and safety controls

**Profiles.** `UNIFI_PROFILE` registers only one group of modules, so the client sees fewer tool definitions:

| Profile | Tools | Covers |
|---|---|---|
| `network` | 48 | Clients, networks, WiFi, DHCP, DNS, WAN, vouchers, channel planning |
| `devices` | 53 | Devices, control, migration, ports, switching, topology, diagnostics |
| `security` | 47 | Firewall, ZBF, ACLs, port forwarding, VPN, content filtering |
| `system` | 182 | Sites, backups, events, DPI, QoS, RADIUS, traffic flows, Protect, cloud |
| `protect` | 75 | The Protect modules |
| `mobility` / `innerspace` / `carrier` | 12 / 10 / 15 | One cloud API each |
| `minimal` | 19 | Sites, clients, devices |

Counts include the four fleet tools every profile gets. An unknown profile logs a warning and loads everything.

**Safety controls.**

- Every mutating tool requires `confirm=True`, and `dry_run=True` returns the change it would make without making it.
- `UNIFI_READ_ONLY=true` leaves mutating tools out of the tool list entirely. `UNIFI_DRY_RUN=true` forces every mutating call into preview mode.
- `DEBUG=true` adds `debug_api_request`, a raw GET or DELETE to any controller endpoint. It is a destructive-tier tool, a DELETE needs `confirm=True`, and read-only mode removes it. Leave `DEBUG` unset in production.
- With tokens, each tool has a risk tier (`read`, `write`, `destructive`) and each role a set of tiers: `viewer` reads, `operator` writes, and `admin` can also run destructive tools, including deletes, restores, restarts, client blocking and firewall policy changes. See [API.md](API.md#access-control).
- Mutations are written to a hash-chained JSON-lines audit log (Postgres in fleet mode), with optional field encryption and SIEM export. See [SECURITY.md](SECURITY.md).
- Inputs are validated with Pydantic, and credentials are redacted from logs.

## Network transports and deployment

`stdio` is the default and needs no port. To serve MCP over the network, use Streamable HTTP:

```bash
export MCP_SERVER_TRANSPORT=streamable_http
export MCP_SERVER_PORT=3000
export MCP_AUTH_TOKEN=$(openssl rand -hex 32)   # required on every network transport
unifi-mcp-server
# Listening on 127.0.0.1:3000; clients send Authorization: Bearer $MCP_AUTH_TOKEN
```

Clients and MCP gateways then connect to `http://<host>:3000/mcp`. The server binds to `127.0.0.1` unless you set `MCP_SERVER_HOST`; put an authenticating TLS proxy in front before exposing it further. `http` also works. `sse` is deprecated: client proxies such as `mcp-remote` can race its initialize handshake ([#96](https://github.com/enuno/unifi-mcp-server/issues/96)).

Container, with the published port on loopback:

```yaml
services:
  unifi-mcp:
    image: ghcr.io/enuno/unifi-mcp-server:latest
    environment:
      UNIFI_API_KEY: your-api-key
      UNIFI_API_TYPE: local
      UNIFI_LOCAL_HOST: 192.168.2.1
      MCP_SERVER_TRANSPORT: streamable_http
      MCP_SERVER_PORT: 3000
      MCP_SERVER_HOST: 0.0.0.0          # inside the container only
      MCP_AUTH_TOKEN: ${MCP_AUTH_TOKEN}
    ports:
      - "127.0.0.1:3000:3000"
```

The repository's [docker-compose.yml](docker-compose.yml) adds Redis and the MCP Toolbox dashboard ([MCP_TOOLBOX.md](MCP_TOOLBOX.md)); copy `.env.docker.example` to `.env` and run `make compose-up`. That example starts read-only (`UNIFI_READ_ONLY=true`) with a `viewer` stdio caller (`UNIFI_STDIO_ROLE=viewer`); to allow changes, set `UNIFI_READ_ONLY=false` and raise `UNIFI_STDIO_ROLE` to `operator`, or `admin` for destructive changes.

- **Ansible:** [deploy/ansible/](deploy/ansible/overview.md) deploys the server alone, a single-host fleet (server, worker, Redis, Postgres), or replicas behind nginx on several hosts. To have an AI agent run the deployment, start from a prompt in [docs/deploy-prompts/](docs/deploy-prompts/overview.md).
- **Kubernetes:** [deploy/helm/unifi-mcp/](deploy/helm/unifi-mcp/overview.md) is a Helm chart for the server alone or in fleet mode with workers, taking every credential from an existing Secret.
- **Local dev deployment (either method):** `make helm-deploy-local` or `make ansible-dev-deploy` build the current working tree — including uncommitted changes — tag it `local-<short-sha>[-dirty]`, and deploy it for real, instead of pulling or building from a published release. See the "Deploying from a local checkout" / "Local dev deployment" sections in the two overview docs above.

## Calling the server from code

Any MCP client library works. With the [FastMCP](https://github.com/jlowin/fastmcp) client:

```python
import asyncio

from fastmcp import Client

config = {
    "mcpServers": {
        "unifi": {
            "command": "unifi-mcp-server",
            "env": {
                "UNIFI_API_KEY": "<your-api-key>",
                "UNIFI_API_TYPE": "local",
                "UNIFI_LOCAL_HOST": "192.168.2.1",
            },
        }
    }
}


async def main() -> None:
    async with Client(config) as client:
        sites = await client.call_tool("list_sites", {})
        print(sites.data)

        clients = await client.call_tool("list_active_clients", {"site_id": "default"})
        print(clients.data)

        # Mutations need confirm=True; dry_run=True previews the change.
        preview = await client.call_tool(
            "create_firewall_zone",
            {"site_id": "default", "name": "IoT", "confirm": True, "dry_run": True},
        )
        print(preview.data)


asyncio.run(main())
```

`bin/unifi-cli` runs a single tool from a shell (`unifi-cli list-clients --site default`); see [docs/SKILLS.md](docs/SKILLS.md#binunifi-cli--cli-wrapper).

## Native MCP prompts

Besides the tools, the server exposes eight parameterised UniFi operational
workflows through the standard MCP prompts interface. A client discovers them
with `prompts/list` and retrieves a rendered workflow brief with `prompts/get`.

```python
import asyncio

from fastmcp import Client

config = {
    "mcpServers": {
        "unifi": {
            "command": "unifi-mcp-server",
            "env": {
                "UNIFI_API_KEY": "<your-api-key>",
                "UNIFI_API_TYPE": "local",
                "UNIFI_LOCAL_HOST": "192.168.2.1",
            },
        }
    }
}


async def main() -> None:
    async with Client(config) as client:
        for prompt in await client.list_prompts():
            print(prompt.name, prompt.description)

        result = await client.get_prompt(
            "network_health_check",
            {"site_id": "default", "focus": "wan"},
        )
        for message in result.messages:
            print(message.content.text)


asyncio.run(main())
```

The prompts are `network_health_check`, `troubleshoot_client_connectivity`,
`troubleshoot_wifi_performance`, `investigate_device`,
`review_firewall_policy`, `plan_network_change`, `protect_health_check` and
`fleet_health_summary`. A workflow is advertised only when the tools it needs
are registered on this server, so the prompt list follows the API mode, the
profile and the read-only and dry-run settings.

Retrieving a prompt does **not** run the workflow and grants no approval. The
rendered text tells an agent which read tools to call and what to report; the
agent calls the tools itself, and the server's role checks, `confirm` gate and
audit trail still apply.

Use `make inspect` to open the MCP Inspector and browse the prompts, or the
MCPJungle CLI to check what the gateway forwards:

```bash
mcpjungle list prompts --server unifi
mcpjungle get prompt unifi__network_health_check --arg site_id=default
```

A tools-only client will not display the prompts; that is a client limitation.
There is no prompts-as-tools shim.

See [docs/PROMPTS.md](docs/PROMPTS.md) for the full catalog, the availability
matrix, the validation rules and the manual acceptance steps.

## Documentation

| Document | Contents |
|---|---|
| [API.md](API.md) | Every MCP tool and resource, with parameters and examples |
| [docs/PROMPTS.md](docs/PROMPTS.md) | The native MCP prompt catalog, with arguments and availability rules |
| [A2A.md](A2A.md) | The agent card, the capability manifest and the delegation endpoint |
| [docs/AUDIT_A2A_SKILLS.md](docs/AUDIT_A2A_SKILLS.md) | The A2A and skills audit: what was implemented, what was not, and why |
| [docs/SKILLS.md](docs/SKILLS.md) | Agent skills, profiles and the CLI wrapper |
| [docs/UNIFI_API.md](docs/UNIFI_API.md) | The UniFi endpoints behind the tools |
| [MULTI_CONTROLLER.md](MULTI_CONTROLLER.md) | Fleet mode: controllers, tokens and roles |
| [METRICS.md](METRICS.md), [WEBHOOK_SETUP.md](WEBHOOK_SETUP.md), [A2A.md](A2A.md) | Metrics, webhooks, the A2A agent endpoints |
| [NETWORK_PLAYBOOK.md](NETWORK_PLAYBOOK.md), [HARBOR_SETUP.md](HARBOR_SETUP.md) | Operating runbooks |
| [SECURITY.md](SECURITY.md) | Reporting vulnerabilities, audit logging and hardening |
| [SPEC.md](SPEC.md), [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md), [ROADMAP.md](ROADMAP.md) | Architecture target and roadmap |
| [docs/research/](docs/research/) | Endpoint discovery records and negative findings: what was probed, what was observed live, and what remains unverified |
| [CHANGELOG.md](CHANGELOG.md), [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md) | Release history and how releases are cut and published |

## Development

```bash
git clone https://github.com/enuno/unifi-mcp-server.git
cd unifi-mcp-server
make install    # uv sync from uv.lock with the dev extra (no activation needed)
make hooks      # pre-commit and commit-msg hooks
cp .env.example .env   # then set UNIFI_API_KEY and, for local mode, UNIFI_LOCAL_HOST

make test       # unit tests
make ci         # every blocking CI check: lint, typecheck, security, docs coverage, tests with the 80% gate
make inspect    # open the server in the MCP Inspector (needs Node.js)
make help       # list every target
```

Without `make`, the same commands run through `uv run --locked`, for example `uv run --locked pytest tests/unit/ -m "not integration"`. Integration tests (`-m integration`) need real UniFi hardware.

Layout: `src/main.py` builds the server, `src/tools/` holds the tool modules, `src/api/` the UniFi clients, `src/models/` the Pydantic models, `src/fleet/` the fleet stack, and `tests/unit/` the unit tests. [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) describe the conventions in detail, and [commands.md](commands.md) lists the development commands.

## Contributing

Contributions from people and AI coding agents are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

1. Fork the repository and create a branch.
2. Write tests first, keep new code at 80% coverage or better, and run `make ci`.
3. Use conventional commit messages (`feat: ...`, `fix: ...`) and open a pull request.

Issues with `[Bug]` in the title opened by a maintainer or collaborator get an automated first analysis; other reports are triaged by hand ([details](CONTRIBUTING.md#automated-workflows)).

## Security

Report vulnerabilities as described in [SECURITY.md](SECURITY.md). Never commit credentials.

## Acknowledgments

- [sirkirby/unifi-network-mcp](https://github.com/sirkirby/unifi-network-mcp), the reference implementation
- [MakeWithData's UniFi MCP guide](https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access)
- [Model Context Protocol](https://modelcontextprotocol.io) and [FastMCP](https://github.com/jlowin/fastmcp)

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Links

- Issues and discussions: [GitHub Issues](https://github.com/enuno/unifi-mcp-server/issues), [GitHub Discussions](https://github.com/enuno/unifi-mcp-server/discussions)
- Releases: <https://github.com/enuno/unifi-mcp-server/releases>
- PyPI: <https://pypi.org/project/unifi-mcp-server/>
- Container images: <https://ghcr.io/enuno/unifi-mcp-server>
- MCP Registry: search for `io.github.enuno/unifi-mcp-server` at <https://registry.modelcontextprotocol.io>

[![Star History Chart](https://api.star-history.com/svg?repos=enuno/unifi-mcp-server&type=date&legend=top-left)](https://www.star-history.com/#enuno/unifi-mcp-server&type=date&legend=top-left)
