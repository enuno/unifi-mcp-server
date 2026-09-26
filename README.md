# <img src="https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/unifi-dark.png" alt="UniFi Dark Logo" width="40" /> UniFi MCP Server

[![CI](https://github.com/enuno/unifi-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/enuno/unifi-mcp-server/actions/workflows/ci.yml)
[![Security](https://github.com/enuno/unifi-mcp-server/actions/workflows/security.yml/badge.svg)](https://github.com/enuno/unifi-mcp-server/actions/workflows/security.yml)
[![codecov](https://codecov.io/github/enuno/unifi-mcp-server/graph/badge.svg?token=ZD314B59CE)](https://codecov.io/github/enuno/unifi-mcp-server)
[![PyPI](https://img.shields.io/pypi/v/unifi-mcp-server.svg)](https://pypi.org/project/unifi-mcp-server/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/enuno/unifi-mcp-server)

A Model Context Protocol (MCP) server that exposes the UniFi Network Controller API, enabling AI agents and applications to interact with UniFi network infrastructure in a standardized way. Connect Claude, Cursor, or any MCP client to your UniFi network and manage it via natural language.

## Quick Start

### Install

```bash
pip install unifi-mcp-server
# or
uvx unifi-mcp-server
```

### Configure (Claude Desktop)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "unifi": {
      "command": "unifi-mcp-server",
      "env": {
        "UNIFI_LOCAL_API_KEY": "your-local-api-key",
        "UNIFI_REMOTE_API_KEY": "your-remote-api-key",
        "UNIFI_API_TYPE": "local",
        "UNIFI_LOCAL_HOST": "192.168.2.1"
      }
    }
  }
}
```

**Key designations used by this project:**

- **LOCAL key** (`UNIFI_LOCAL_API_KEY`) — created on a local site in UniFi Network Integrations
- **REMOTE key** (`UNIFI_REMOTE_API_KEY`) — created at [unifi.ui.com](https://unifi.ui.com) API Keys

### Docker

```bash
# 1. Copy the example environment file and add your API keys
cp .env.docker.example .env

# 2. Start the server
docker compose up -d

# 3. Verify it's running
curl -s http://localhost:3000/mcp | head
```

The MCP endpoint is available at `http://localhost:3000/mcp` by default.

#### Claude Code

Claude Code supports HTTP MCP servers natively. Add a `.mcp.json` to the project root:

```json
{
  "mcpServers": {
    "unifi": {
      "type": "http",
      "url": "http://localhost:3000/mcp"
    }
  }
}
```

#### Claude Desktop

Claude Desktop only supports stdio transport, so you need [`mcp-remote`](https://github.com/geelen/mcp-remote) to bridge to the HTTP server. Requires Node.js.

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "unifi": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:3000/mcp"]
    }
  }
}
```

> **Tip:** To avoid `npx` fetching on every launch, install globally first:
>
> ```bash
> npm install -g mcp-remote
> ```
>
> Then use the full path as the command (e.g. `"command": "/usr/local/bin/mcp-remote"`).

## API Modes

| Mode | `UNIFI_API_TYPE` | Capability |
|------|-----------------|------------|
| **Local Gateway** (recommended) | `local` | Full access — device control, configuration, real-time data |
| Cloud V1 | `cloud-v1` | Site-level aggregate statistics only |
| Cloud EA | `cloud-ea` | Site-level aggregate statistics only |

For local mode, set `UNIFI_LOCAL_HOST=<gateway-ip>` and use `UNIFI_LOCAL_API_KEY`. For cloud modes, use `UNIFI_REMOTE_API_KEY` (recommended) or `UNIFI_LOCAL_API_KEY` if your account supports cloud access with the local key.

## Features

**86+ MCP tools** across 8 categories:

- **Core Network** — devices, clients, networks/VLANs, WiFi/SSIDs, port profiles, port forwarding, DPI statistics
- **Security & Firewall** — firewall rules, ACL management, traffic matching lists, Zone-Based Firewall (UniFi 9.0+)
- **RADIUS & Guest Portal** — 802.1X authentication, captive portals, voucher management
- **QoS** — traffic prioritization, bandwidth limits, ProAV templates, traffic routes
- **Backup & Operations** — scheduled backups, restore, checksum verification
- **Multi-Site Management** — site provisioning, site-to-site VPN, device migration, cross-site analytics
- **Network Topology** — full topology discovery, connection mapping, GraphML/DOT export
- **Safety** — all mutating operations require `confirm=True`; `dry_run=True` preview mode; full audit logging

## Documentation

| Topic | File |
|-------|------|
| MCP tool reference (all 86+ tools) | [docs/api/mcp-tools.md](docs/api/mcp-tools.md) |
| UniFi API reference | [docs/api/unifi-api-reference.md](docs/api/unifi-api-reference.md) |
| API audit (endpoint status) | [docs/api/api-audit.md](docs/api/api-audit.md) |
| Testing strategy | [docs/testing/test-plan.md](docs/testing/test-plan.md) |
| Release process | [docs/operations/release-process.md](docs/operations/release-process.md) |
| Disaster recovery | [docs/operations/disaster-recovery.md](docs/operations/disaster-recovery.md) |
| Zone-Based Firewall status | [docs/features/zbf-status.md](docs/features/zbf-status.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines, branch strategy, commit conventions, and testing requirements.

Issues with `[Bug]` in the title are automatically triaged by an AI bug handler — see [CONTRIBUTING.md](CONTRIBUTING.md#automated-workflows) for details.

## Security

See [SECURITY.md](SECURITY.md) for the vulnerability reporting process and security best practices. Never commit API keys or credentials.

## License

Apache 2.0 — see [LICENSE](LICENSE).
