# <img src="https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/unifi-dark.png" alt="UniFi Dark Logo" width="40" /> UniFi MCP Server

[![CI](https://github.com/enuno/unifi-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/enuno/unifi-mcp-server/actions/workflows/ci.yml)
[![Security](https://github.com/enuno/unifi-mcp-server/actions/workflows/security.yml/badge.svg)](https://github.com/enuno/unifi-mcp-server/actions/workflows/security.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A Model Context Protocol (MCP) server that exposes the UniFi Network Controller API, enabling AI agents and applications to interact with UniFi network infrastructure in a standardized way.

## Features

### Core Capabilities

- **Device Management**: List, monitor, restart, locate, and upgrade UniFi devices (APs, switches, gateways)
- **Network Configuration**: Create, update, and delete networks, VLANs, and subnets with DHCP configuration
- **Client Management**: Query, block, unblock, and reconnect clients
- **Firewall Rules**: Create, update, and delete firewall rules with traffic filtering
- **WiFi/SSID Management**: Create and manage wireless networks with WPA2/WPA3, guest networks, and VLAN isolation
- **Port Forwarding**: Configure port forwarding rules for external access
- **DPI Statistics**: Deep Packet Inspection analytics for bandwidth usage by application and category
- **Multi-Site Support**: Work with multiple UniFi sites seamlessly
- **Real-time Monitoring**: Access device, network, client, and WiFi statistics

### Advanced Features

- **Redis Caching**: Optional Redis-based caching for improved performance (configurable TTL per resource type)
- **Webhook Support**: Real-time event processing with HMAC signature verification
- **Automatic Cache Invalidation**: Smart cache invalidation when configuration changes
- **Event Handlers**: Built-in handlers for device, client, and alert events
- **Performance Tracking**: Optional agnost.ai integration for monitoring MCP tool performance and usage analytics

### Safety & Security

- **Confirmation Required**: All mutating operations require explicit `confirm=True` flag
- **Dry-Run Mode**: Preview changes before applying them with `dry_run=True`
- **Audit Logging**: All operations logged to `audit.log` for compliance
- **Input Validation**: Comprehensive parameter validation with detailed error messages
- **Password Masking**: Sensitive data automatically masked in logs
- **Type-Safe**: Full type hints and Pydantic validation throughout
- **Security Scanners**: CodeQL, Trivy, Bandit, Safety, and detect-secrets integration

### Technical Excellence

- **Async Support**: Built with async/await for high performance and concurrency
- **MCP Protocol**: Standard Model Context Protocol for AI agent integration
- **Comprehensive Testing**: 179 unit tests with 34% coverage (target: 80%)
- **CI/CD Pipelines**: Automated testing, security scanning, and Docker builds
- **Multi-Architecture**: Docker images for amd64 and arm64

## Quick Start

### Prerequisites

- Python 3.10 or higher
- A UniFi account at [unifi.ui.com](https://unifi.ui.com)
- UniFi API key (obtain from Settings → Control Plane → Integrations)
- Access to UniFi Cloud API or local gateway

### Installation

#### Using uv (Recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/enuno/unifi-mcp-server.git
cd unifi-mcp-server

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

#### Using pip

```bash
# Clone the repository
git clone https://github.com/enuno/unifi-mcp-server.git
cd unifi-mcp-server

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

#### Using Docker Compose (Recommended for Production)

The recommended way to run the UniFi MCP Server with full monitoring capabilities:

```bash
# 1. Copy and configure environment variables
cp .env.docker.example .env
# Edit .env with your UNIFI_API_KEY and AGNOST_ORG_ID

# 2. Start all services (MCP Server + Redis + MCP Toolbox)
docker-compose up -d

# 3. Check service status
docker-compose ps

# 4. View logs
docker-compose logs -f unifi-mcp

# 5. Access MCP Toolbox dashboard
open http://localhost:8080

# 6. Stop all services
docker-compose down
```

**Included Services:**

- **UniFi MCP Server**: Main MCP server with 40 tools
- **MCP Toolbox**: Web-based analytics dashboard (port 8080)
- **Redis**: High-performance caching layer

See [MCP_TOOLBOX.md](MCP_TOOLBOX.md) for detailed Toolbox documentation.

#### Using Docker (Standalone)

For standalone Docker usage (not with MCP clients):

```bash
# Pull the image
docker pull ghcr.io/enuno/unifi-mcp-server:latest

# Run the container in background (Cloud API)
# Note: -i flag keeps stdin open for STDIO transport
docker run -i -d \
  --name unifi-mcp \
  -e UNIFI_API_KEY=your-api-key \
  -e UNIFI_API_TYPE=cloud \
  ghcr.io/enuno/unifi-mcp-server:latest

# OR run with local gateway proxy
docker run -i -d \
  --name unifi-mcp \
  -e UNIFI_API_KEY=your-api-key \
  -e UNIFI_API_TYPE=local \
  -e UNIFI_HOST=192.168.1.1 \
  ghcr.io/enuno/unifi-mcp-server:latest

# Check container status
docker ps --filter name=unifi-mcp

# View logs
docker logs unifi-mcp

# Stop and remove
docker rm -f unifi-mcp
```

**Note**: For MCP client integration (Claude Desktop, etc.), see the [Usage](#usage) section below for the correct configuration without `-d` flag.

### Configuration

#### Obtaining Your API Key

1. Log in to [UniFi Site Manager](https://unifi.ui.com)
2. Navigate to **Settings → Control Plane → Integrations**
3. Click **Create API Key**
4. **Save the key immediately** - it's only shown once!
5. Store it securely in your `.env` file

#### Configuration File

Create a `.env` file in the project root:

```env
# Required: Your UniFi API Key
UNIFI_API_KEY=your-api-key-here

# API Type: cloud or local
UNIFI_API_TYPE=cloud

# For cloud API (default)
UNIFI_HOST=api.ui.com
UNIFI_PORT=443
UNIFI_VERIFY_SSL=true

# For local gateway proxy, use:
# UNIFI_API_TYPE=local
# UNIFI_HOST=192.168.1.1
# UNIFI_VERIFY_SSL=false

# Optional settings
UNIFI_SITE=default

# Redis caching (optional - improves performance)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
# REDIS_PASSWORD=your-password  # If Redis requires authentication

# Webhook support (optional - for real-time events)
WEBHOOK_SECRET=your-webhook-secret-here

# Performance tracking with agnost.ai (optional - for analytics)
# Get your Organization ID from https://app.agnost.ai
# AGNOST_ENABLED=true
# AGNOST_ORG_ID=your-organization-id-here
# AGNOST_ENDPOINT=https://api.agnost.ai
# AGNOST_DISABLE_INPUT=false  # Set to true to disable input tracking
# AGNOST_DISABLE_OUTPUT=false # Set to true to disable output tracking
```

See `.env.example` for all available options.

### Running the Server

```bash
# Development mode with MCP Inspector
uv run mcp dev src/main.py

# Production mode
uv run python src/main.py
```

The MCP Inspector will be available at `http://localhost:5173` for interactive testing.

## Usage

### With Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

#### Option 1: Using uv (Recommended)

```json
{
  "mcpServers": {
    "unifi": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/unifi-mcp-server",
        "run",
        "mcp",
        "run",
        "src/main.py"
      ],
      "env": {
        "UNIFI_API_KEY": "your-api-key-here",
        "UNIFI_API_TYPE": "cloud"
      }
    }
  }
}
```

#### Option 2: Using Docker

```json
{
  "mcpServers": {
    "unifi": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "UNIFI_API_KEY=your-api-key-here",
        "-e",
        "UNIFI_API_TYPE=cloud",
        "ghcr.io/enuno/unifi-mcp-server:latest"
      ]
    }
  }
}
```

**Important**: Do NOT use `-d` (detached mode) in MCP client configurations. The MCP client needs to maintain a persistent stdin/stdout connection to the container.

### Programmatic Usage

```python
from mcp import MCP
import asyncio

async def main():
    mcp = MCP("unifi-mcp-server")

    # List all devices
    devices = await mcp.call_tool("list_devices", {
        "site_id": "default"
    })

    for device in devices:
        print(f"{device['name']}: {device['status']}")

    # Get network information via resource
    networks = await mcp.read_resource("sites://default/networks")
    print(f"Networks: {len(networks)}")

    # Create a guest WiFi network with VLAN isolation
    wifi = await mcp.call_tool("create_wlan", {
        "site_id": "default",
        "name": "Guest WiFi",
        "security": "wpapsk",
        "password": "GuestPass123!",
        "is_guest": True,
        "vlan_id": 100,
        "confirm": True  # Required for safety
    })
    print(f"Created WiFi: {wifi['name']}")

    # Get DPI statistics for top bandwidth users
    top_apps = await mcp.call_tool("list_top_applications", {
        "site_id": "default",
        "limit": 5,
        "time_range": "24h"
    })

    for app in top_apps:
        gb = app['total_bytes'] / 1024**3
        print(f"{app['application']}: {gb:.2f} GB")

asyncio.run(main())
```

## API Documentation

See [API.md](API.md) for complete API documentation, including:

- Available MCP tools
- Resource URI schemes
- Request/response formats
- Error handling
- Examples

## Development

### Setup Development Environment

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg
```

### Running Tests

```bash
# Run all tests
pytest tests/unit/

# Run with coverage report
pytest tests/unit/ --cov=src --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_zbf_tools.py -v

# Run tests for new v0.2.0 features
pytest tests/unit/test_new_models.py tests/unit/test_zbf_tools.py tests/unit/test_traffic_flow_tools.py

# Run only unit tests (fast)
pytest -m unit

# Run only integration tests (requires UniFi controller)
pytest -m integration
```

**Current Test Coverage**:

- **Overall**: 34.10% (179 tests passing)
- **New v0.2.0 Models**: 100% (36 tests)
- **ZBF Tools**: 82.68% (22 tests)
- **Traffic Flow Tools**: 86.62% (16 tests)
- **Existing Tools**: 15-95% (varying coverage)

See [TESTING_PLAN.md](TESTING_PLAN.md) for the comprehensive testing roadmap.

### Code Quality

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
ruff check src/ tests/ --fix

# Type check
mypy src/

# Run all pre-commit checks
pre-commit run --all-files
```

### Testing with MCP Inspector

```bash
# Start development server with inspector
uv run mcp dev src/main.py

# Open http://localhost:5173 in your browser
```

## Project Structure

```
unifi-mcp-server/
├── .github/
│   └── workflows/          # CI/CD pipelines (CI, security, release)
├── .claude/
│   └── commands/          # Custom slash commands for development
├── src/
│   ├── main.py            # MCP server entry point (40 tools registered)
│   ├── cache.py           # Redis caching implementation
│   ├── config/            # Configuration management
│   ├── api/               # UniFi API client with rate limiting
│   ├── tools/             # MCP tool definitions
│   │   ├── clients.py     # Client query tools
│   │   ├── devices.py     # Device query tools
│   │   ├── networks.py    # Network query tools
│   │   ├── sites.py       # Site query tools
│   │   ├── firewall.py    # Firewall management (Phase 4)
│   │   ├── network_config.py  # Network configuration (Phase 4)
│   │   ├── device_control.py  # Device control (Phase 4)
│   │   ├── client_management.py  # Client management (Phase 4)
│   │   ├── wifi.py        # WiFi/SSID management (Phase 5)
│   │   ├── port_forwarding.py  # Port forwarding (Phase 5)
│   │   └── dpi.py         # DPI statistics (Phase 5)
│   ├── resources/         # MCP resource definitions
│   ├── webhooks/          # Webhook receiver and handlers (Phase 5)
│   └── utils/             # Utility functions and validators
├── tests/
│   ├── unit/              # Unit tests (179 tests, 34% coverage)
│   ├── integration/       # Integration tests (planned)
│   └── performance/       # Performance benchmarks (planned)
├── docs/                  # Additional documentation
│   └── AI-Coding/         # AI coding guidelines
├── .env.example           # Environment variable template
├── pyproject.toml         # Project configuration
├── README.md              # This file
├── API.md                 # Complete API documentation
├── TESTING_PLAN.md        # Testing strategy and roadmap
├── DEVELOPMENT_PLAN.md    # Development roadmap
├── CONTRIBUTING.md        # Contribution guidelines
├── SECURITY.md            # Security policy and best practices
├── AGENTS.md              # AI agent guidelines
└── LICENSE                # Apache 2.0 License
```

## Contributing

We welcome contributions from both human developers and AI coding assistants! Please see:

- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [AGENTS.md](AGENTS.md) - AI agent-specific guidelines
- [AI_CODING_ASSISTANT.md](AI_CODING_ASSISTANT.md) - AI coding standards
- [AI_GIT_PRACTICES.md](AI_GIT_PRACTICES.md) - AI Git practices

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Run tests and linting: `pytest && pre-commit run --all-files`
5. Commit with conventional commits: `feat: add new feature`
6. Push and create a pull request

## Security

Security is a top priority. Please see [SECURITY.md](SECURITY.md) for:

- Reporting vulnerabilities
- Security best practices
- Supported versions

**Never commit credentials or sensitive data!**

## Roadmap

### Version 0.1.0 (Current - Complete ✅)

**Phase 3: Read-Only Operations (16 tools)**

- [x] Device management (list, details, statistics, search by type)
- [x] Client management (list, details, statistics, search)
- [x] Network information (details, VLANs, subnets, statistics)
- [x] Site management (list, details, statistics)
- [x] MCP resources (sites, devices, clients, networks)

**Phase 4: Mutating Operations with Safety (13 tools)**

- [x] Firewall rule management (create, update, delete)
- [x] Network configuration (create, update, delete networks/VLANs)
- [x] Device control (restart, locate, upgrade)
- [x] Client management (block, unblock, reconnect)
- [x] Safety mechanisms (confirmation, dry-run, audit logging)

**Phase 5: Advanced Features (11 tools)**

- [x] WiFi/SSID management (create, update, delete, statistics)
- [x] Port forwarding configuration (create, delete, list)
- [x] DPI statistics (site-wide, top apps, per-client)
- [x] Redis caching with automatic invalidation
- [x] Webhook support for real-time events

**Total: 40 MCP tools + 4 MCP resources**

### Version 0.2.0 (Planned)

- [ ] Unit tests for Phase 5 tools (target: 80% coverage)
- [ ] Integration tests for caching and webhooks
- [ ] Performance benchmarks and optimization
- [x] Performance tracking with agnost.ai integration
- [x] MCP Toolbox Docker integration for analytics dashboard
- [ ] Additional DPI analytics (historical trends)
- [ ] Backup and restore operations

### Version 1.0.0 (Future)

- [ ] Complete UniFi API coverage (remaining endpoints)
- [ ] Advanced analytics dashboard
- [ ] VPN configuration management
- [ ] Alert and notification management
- [ ] Bulk operations for devices
- [ ] Traffic shaping and QoS management

## Acknowledgments

This project is inspired by and builds upon:

- [sirkirby/unifi-network-mcp](https://github.com/sirkirby/unifi-network-mcp) - Reference implementation
- [MakeWithData UniFi MCP Guide](https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access) - Tutorial and guide
- [Anthropic MCP](https://github.com/anthropics/mcp) - Model Context Protocol specification
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/enuno/unifi-mcp-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/enuno/unifi-mcp-server/discussions)
- **Documentation**: See [API.md](API.md) and other docs in this repository

## Links

- **Repository**: <https://github.com/enuno/unifi-mcp-server>
- **Docker Hub**: <https://ghcr.io/enuno/unifi-mcp-server>
- **Documentation**: [API.md](API.md)
- **UniFi Official**: <https://www.ui.com/>

---

Made with ❤️ for the UniFi and AI communities
