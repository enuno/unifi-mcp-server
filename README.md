# UniFi MCP Server

[![CI](https://github.com/elvis/unifi-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/elvis/unifi-mcp-server/actions/workflows/ci.yml)
[![Security](https://github.com/elvis/unifi-mcp-server/actions/workflows/security.yml/badge.svg)](https://github.com/elvis/unifi-mcp-server/actions/workflows/security.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A Model Context Protocol (MCP) server that exposes the UniFi Network Controller API, enabling AI agents and applications to interact with UniFi network infrastructure in a standardized way.

## Features

- **Device Management**: List, monitor, and control UniFi devices (APs, switches, gateways)
- **Network Configuration**: Manage networks, VLANs, and subnets
- **Client Management**: Query and manage connected clients
- **Firewall Rules**: Create and manage firewall rules
- **Multi-Site Support**: Work with multiple UniFi sites
- **Real-time Monitoring**: Access device and network statistics
- **Type-Safe**: Full type hints and Pydantic validation
- **Async Support**: Built with async/await for high performance
- **Comprehensive Testing**: Extensive test coverage with pytest
- **Security-First**: Multiple security scanners and best practices

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
git clone https://github.com/elvis/unifi-mcp-server.git
cd unifi-mcp-server

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

#### Using pip

```bash
# Clone the repository
git clone https://github.com/elvis/unifi-mcp-server.git
cd unifi-mcp-server

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

#### Using Docker

```bash
# Pull the image
docker pull ghcr.io/elvis/unifi-mcp-server:latest

# Run the container (Cloud API)
docker run -d \
  -e UNIFI_API_KEY=your-api-key \
  -e UNIFI_API_TYPE=cloud \
  -p 3000:3000 \
  ghcr.io/elvis/unifi-mcp-server:latest

# OR run with local gateway proxy
docker run -d \
  -e UNIFI_API_KEY=your-api-key \
  -e UNIFI_API_TYPE=local \
  -e UNIFI_HOST=192.168.1.1 \
  -p 3000:3000 \
  ghcr.io/elvis/unifi-mcp-server:latest
```

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

    # Get network information
    networks = await mcp.read_resource("sites://default/networks")
    print(f"Networks: {len(networks)}")

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
pytest

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Run only unit tests
pytest -m unit

# Run only integration tests (requires UniFi controller)
pytest -m integration
```

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
│   └── workflows/          # CI/CD pipelines
├── src/
│   ├── main.py            # MCP server entry point
│   ├── config/            # Configuration management
│   ├── api/               # UniFi API client
│   ├── tools/             # MCP tool definitions
│   ├── resources/         # MCP resource definitions
│   └── utils/             # Utility functions
├── tests/
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
├── docs/                  # Additional documentation
├── .env.example           # Environment variable template
├── pyproject.toml         # Project configuration
├── README.md              # This file
├── API.md                 # API documentation
├── CONTRIBUTING.md        # Contribution guidelines
├── SECURITY.md            # Security policy
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

### Version 0.1.0 (Current)

- [x] Basic device management
- [x] Network configuration
- [x] Client management
- [x] Firewall rule management
- [x] Site support

### Version 0.2.0 (Planned)

- [ ] WiFi network (SSID) management
- [ ] Port forwarding configuration
- [ ] DPI statistics
- [ ] Webhook support for events

### Version 1.0.0 (Future)

- [ ] Complete UniFi API coverage
- [ ] Advanced analytics
- [ ] Backup and restore
- [ ] VPN configuration
- [ ] Alert management

## Acknowledgments

This project is inspired by and builds upon:

- [sirkirby/unifi-network-mcp](https://github.com/sirkirby/unifi-network-mcp) - Reference implementation
- [MakeWithData UniFi MCP Guide](https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access) - Tutorial and guide
- [Anthropic MCP](https://github.com/anthropics/mcp) - Model Context Protocol specification
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/elvis/unifi-mcp-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/elvis/unifi-mcp-server/discussions)
- **Documentation**: See [API.md](API.md) and other docs in this repository

## Links

- **Repository**: https://github.com/elvis/unifi-mcp-server
- **Docker Hub**: https://ghcr.io/elvis/unifi-mcp-server
- **Documentation**: [API.md](API.md)
- **UniFi Official**: https://www.ui.com/

---

Made with ❤️ for the UniFi and AI communities
