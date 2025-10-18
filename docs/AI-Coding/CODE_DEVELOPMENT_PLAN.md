# Code Development Plan for UniFi MCP Server

This document provides a comprehensive, phase-by-phase development plan for AI coding assistants (Claude Code, Cursor, Windsurf, etc.) to implement the UniFi MCP Server. This plan is designed to be followed sequentially, with each phase building upon the previous one.

## Project Overview

The UniFi MCP Server is a Model Context Protocol (MCP) server that exposes the official UniFi Network Controller API, enabling AI agents and applications to interact with UniFi network infrastructure in a standardized way. The project leverages the UniFi Site Manager API (cloud-based) and supports local gateway proxy connections.

### Key Technologies

- **Python:** 3.10 or higher with full type hints
- **FastMCP:** MCP server framework
- **Pydantic:** Data validation and settings management
- **httpx:** Async HTTP client for API requests
- **pytest:** Testing framework
- **Docker:** Containerization

### Reference Resources

- [UniFi Site Manager API Documentation](https://developer.ui.com/site-manager-api/gettingstarted)
- [sirkirby/unifi-network-mcp](https://github.com/sirkirby/unifi-network-mcp) - Reference implementation
- [MakeWithData UniFi MCP Guide](https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)

## Development Phases

### Phase 1: Core Infrastructure Setup

**Objective:** Establish the foundational project structure, configuration management, and API client framework.

#### Tasks

1. **Configuration Management (`src/config/`)**
   - Create `config.py` with Pydantic settings model
   - Support environment variables and `.env` file loading
   - Implement configuration for both cloud and local API modes
   - Add validation for required fields (API key, API type, host, port)
   - Support multiple sites configuration

2. **API Client Foundation (`src/api/`)**
   - Create `client.py` with base UniFi API client class
   - Implement authentication using X-API-Key header
   - Add support for both cloud API (`api.ui.com`) and local gateway proxy
   - Implement rate limiting handler (100 req/min for EA, 10,000 req/min for v1)
   - Add retry logic with exponential backoff for 429 responses
   - Create async request wrapper with proper error handling

3. **Utility Functions (`src/utils/`)**
   - Create `logger.py` for structured logging
   - Create `exceptions.py` for custom exception classes
   - Create `validators.py` for common validation functions
   - Create `helpers.py` for shared utility functions

#### Expected Deliverables

- Fully functional configuration system that loads from environment and `.env` files
- Base API client that can authenticate and make requests to UniFi API
- Comprehensive error handling and logging infrastructure
- Unit tests for configuration and API client (minimum 80% coverage)

#### Validation Criteria

```python
# Configuration should load successfully
from src.config import Settings
settings = Settings()
assert settings.api_key is not None
assert settings.api_type in ["cloud", "local"]

# API client should authenticate
from src.api import UniFiClient
client = UniFiClient(settings)
await client.authenticate()
assert client.is_authenticated
```

---

### Phase 2: MCP Resources Implementation

**Objective:** Implement MCP resources for read-only data access following the resource URI scheme.

#### Tasks

1. **Sites Resource (`src/resources/sites.py`)**
   - Implement `@mcp.resource("sites://")` to list all sites
   - Support pagination (limit/offset pattern)
   - Return site metadata (ID, name, description, location)
   - Add caching with configurable TTL

2. **Devices Resource (`src/resources/devices.py`)**
   - Implement `@mcp.resource("sites://{site_id}/devices")` to list devices
   - Support filtering by device type (AP, switch, gateway)
   - Include device status, model, firmware version
   - Add health metrics (uptime, CPU, memory)

3. **Clients Resource (`src/resources/clients.py`)**
   - Implement `@mcp.resource("sites://{site_id}/clients")` to list connected clients
   - Include client details (MAC, IP, hostname, device type)
   - Add connection statistics (signal strength, bandwidth usage)
   - Support filtering by connection status (active/inactive)

4. **Networks Resource (`src/resources/networks.py`)**
   - Implement `@mcp.resource("sites://{site_id}/networks")` to list networks
   - Include VLAN configuration
   - Add subnet information
   - Support DHCP settings display

#### Expected Deliverables

- Four fully functional MCP resources with proper URI schemes
- Pagination support for all list operations
- Comprehensive data models using Pydantic
- Unit and integration tests for each resource
- Documentation in `API.md` with examples

#### Validation Criteria

```python
# Resources should be accessible via MCP
from mcp import MCP
mcp_client = MCP("unifi-mcp-server")

# List sites
sites = await mcp_client.read_resource("sites://")
assert len(sites) > 0

# List devices for a site
devices = await mcp_client.read_resource("sites://default/devices")
assert all("name" in device for device in devices)
```

---

### Phase 3: MCP Tools - Read Operations

**Objective:** Implement MCP tools for querying and retrieving detailed information.

#### Tasks

1. **Device Management Tools (`src/tools/devices.py`)**
   - `get_device_details`: Get detailed information for a specific device
   - `get_device_statistics`: Retrieve real-time statistics for a device
   - `list_devices_by_type`: Filter devices by type (AP, switch, gateway)
   - `search_devices`: Search devices by name, MAC, or IP

2. **Client Management Tools (`src/tools/clients.py`)**
   - `get_client_details`: Get detailed information for a specific client
   - `get_client_statistics`: Retrieve bandwidth and connection stats
   - `list_active_clients`: List currently connected clients
   - `search_clients`: Search clients by MAC, IP, or hostname

3. **Network Information Tools (`src/tools/networks.py`)**
   - `get_network_details`: Get detailed network configuration
   - `list_vlans`: List all VLANs in a site
   - `get_subnet_info`: Get subnet and DHCP information
   - `get_network_statistics`: Retrieve network usage statistics

4. **Site Management Tools (`src/tools/sites.py`)**
   - `get_site_details`: Get detailed site information
   - `list_sites`: List all accessible sites
   - `get_site_statistics`: Retrieve site-wide statistics

#### Expected Deliverables

- Minimum 12 read-only MCP tools
- Full type hints and Pydantic validation for all inputs/outputs
- Comprehensive error handling with meaningful error messages
- Unit tests with mocked API responses
- Integration tests with real UniFi controller (optional)
- Updated `API.md` documentation with tool descriptions and examples

#### Validation Criteria

```python
# Tools should be callable via MCP
devices = await mcp_client.call_tool("list_devices_by_type", {
    "site_id": "default",
    "device_type": "ap"
})
assert all(device["type"] == "ap" for device in devices)

# Error handling should work
try:
    await mcp_client.call_tool("get_device_details", {
        "device_id": "invalid-id"
    })
except Exception as e:
    assert "not found" in str(e).lower()
```

---

### Phase 4: MCP Tools - Write Operations (Mutating)

**Objective:** Implement MCP tools for modifying UniFi configuration with safety mechanisms.

#### Tasks

1. **Firewall Rules Tools (`src/tools/firewall.py`)**
   - `create_firewall_rule`: Create a new firewall rule (requires `confirm=true`)
   - `update_firewall_rule`: Modify an existing firewall rule (requires `confirm=true`)
   - `delete_firewall_rule`: Remove a firewall rule (requires `confirm=true`)
   - `list_firewall_rules`: List all firewall rules (read-only)

2. **Network Configuration Tools (`src/tools/network_config.py`)**
   - `create_network`: Create a new network/VLAN (requires `confirm=true`)
   - `update_network`: Modify network settings (requires `confirm=true`)
   - `delete_network`: Remove a network (requires `confirm=true`)

3. **Device Control Tools (`src/tools/device_control.py`)**
   - `restart_device`: Restart a UniFi device (requires `confirm=true`)
   - `locate_device`: Enable LED locate on a device (requires `confirm=true`)
   - `upgrade_device`: Trigger firmware upgrade (requires `confirm=true`)

4. **Client Management Tools (`src/tools/client_management.py`)**
   - `block_client`: Block a client from the network (requires `confirm=true`)
   - `unblock_client`: Unblock a previously blocked client (requires `confirm=true`)
   - `reconnect_client`: Force client reconnection (requires `confirm=true`)

#### Safety Mechanisms

All mutating tools must implement the following safety features:

- **Confirmation Required:** All tools must check for `confirm=true` parameter
- **Dry Run Mode:** Support `dry_run=true` to preview changes without applying
- **Validation:** Validate all inputs before making API calls
- **Audit Logging:** Log all mutating operations with timestamp and parameters
- **Rollback Support:** Where possible, provide rollback mechanisms

#### Expected Deliverables

- Minimum 12 mutating MCP tools with safety mechanisms
- Confirmation parameter enforcement on all mutating operations
- Comprehensive validation and error handling
- Audit logging for all mutating operations
- Unit tests with mocked API responses
- Integration tests with safety checks
- Updated `API.md` and `SECURITY.md` documentation

#### Validation Criteria

```python
# Mutating tools should require confirmation
try:
    await mcp_client.call_tool("create_firewall_rule", {
        "site_id": "default",
        "rule_name": "test-rule",
        "action": "accept"
    })
    assert False, "Should have raised error for missing confirm"
except Exception as e:
    assert "confirm" in str(e).lower()

# With confirmation, should succeed
result = await mcp_client.call_tool("create_firewall_rule", {
    "site_id": "default",
    "rule_name": "test-rule",
    "action": "accept",
    "confirm": True
})
assert result["success"] == True
```

---

### Phase 5: Advanced Features

**Objective:** Implement advanced functionality for enhanced capabilities.

#### Tasks

1. **WiFi Network (SSID) Management (`src/tools/wifi.py`)**
   - `list_wlans`: List all wireless networks
   - `create_wlan`: Create a new SSID (requires `confirm=true`)
   - `update_wlan`: Modify SSID settings (requires `confirm=true`)
   - `delete_wlan`: Remove an SSID (requires `confirm=true`)
   - `get_wlan_statistics`: Get WiFi usage statistics

2. **Port Forwarding (`src/tools/port_forwarding.py`)**
   - `list_port_forwards`: List all port forwarding rules
   - `create_port_forward`: Create port forwarding rule (requires `confirm=true`)
   - `delete_port_forward`: Remove port forwarding rule (requires `confirm=true`)

3. **DPI Statistics (`src/tools/dpi.py`)**
   - `get_dpi_statistics`: Get Deep Packet Inspection statistics
   - `list_top_applications`: List top applications by bandwidth
   - `get_client_dpi`: Get DPI stats for specific client

4. **Caching and Performance (`src/utils/cache.py`)**
   - Implement Redis-based caching for frequently accessed data
   - Add cache invalidation strategies
   - Support configurable TTL per resource type
   - Add cache warming for critical data

5. **Webhook Support (`src/webhooks/`)**
   - Create webhook receiver for UniFi events
   - Support event filtering and routing
   - Add webhook authentication
   - Implement event logging

#### Expected Deliverables

- WiFi management tools with full CRUD operations
- Port forwarding configuration tools
- DPI statistics and analytics tools
- Caching layer with Redis support
- Webhook event handling system
- Performance benchmarks and optimization
- Updated documentation

---

### Phase 6: Testing and Quality Assurance

**Objective:** Ensure comprehensive test coverage and code quality.

#### Tasks

1. **Unit Tests (`tests/unit/`)**
   - Achieve minimum 90% code coverage
   - Test all configuration scenarios
   - Test all API client methods with mocked responses
   - Test all tools and resources with mocked data
   - Test error handling and edge cases

2. **Integration Tests (`tests/integration/`)**
   - Test against real UniFi controller (in CI/CD with test environment)
   - Test end-to-end workflows
   - Test rate limiting and retry logic
   - Test authentication and authorization
   - Test multi-site scenarios

3. **Security Testing**
   - Run `bandit` security scanner
   - Run `safety` dependency vulnerability scanner
   - Test API key handling and storage
   - Test input validation and sanitization
   - Perform penetration testing on exposed endpoints

4. **Performance Testing**
   - Benchmark API response times
   - Test concurrent request handling
   - Test caching effectiveness
   - Profile memory usage
   - Load test with multiple sites and devices

5. **Code Quality**
   - Ensure all code passes `black` formatting
   - Ensure all code passes `ruff` linting
   - Ensure all code passes `mypy` type checking
   - Ensure all code passes pre-commit hooks
   - Review and refactor complex functions

#### Expected Deliverables

- Test coverage report showing ≥90% coverage
- Integration test suite with real UniFi controller
- Security scan reports with no critical issues
- Performance benchmark results
- Code quality metrics dashboard

---

### Phase 7: Documentation and Deployment

**Objective:** Complete all documentation and prepare for production deployment.

#### Tasks

1. **API Documentation (`API.md`)**
   - Document all MCP tools with examples
   - Document all MCP resources with URI schemes
   - Add request/response format specifications
   - Include error codes and troubleshooting guide
   - Add usage examples for common scenarios

2. **User Documentation (`docs/`)**
   - Create installation guide
   - Create configuration guide
   - Create troubleshooting guide
   - Create FAQ document
   - Add video tutorials (optional)

3. **Developer Documentation**
   - Update `CONTRIBUTING.md` with development workflow
   - Update `AGENTS.md` with AI assistant guidelines
   - Create architecture documentation
   - Add code style guide
   - Document testing procedures

4. **Docker and Deployment**
   - Create optimized `Dockerfile`
   - Create `docker-compose.yml` for local development
   - Set up GitHub Actions for CI/CD
   - Configure automated testing in CI
   - Set up automated Docker image publishing
   - Create deployment guides for various platforms

5. **Release Preparation**
   - Create `CHANGELOG.md` with version history
   - Tag version 0.1.0 release
   - Publish to PyPI (optional)
   - Publish Docker image to ghcr.io
   - Create release notes

#### Expected Deliverables

- Complete API documentation with examples
- User-friendly installation and configuration guides
- Developer documentation for contributors
- Production-ready Docker images
- Automated CI/CD pipeline
- Version 0.1.0 release

---

## Development Guidelines for AI Assistants

### Code Style and Standards

- **Type Hints:** Use full type hints for all functions and methods
- **Docstrings:** Use Google-style docstrings for all public functions
- **Naming:** Use descriptive names following PEP 8 conventions
- **Error Handling:** Use specific exception types, not bare `except`
- **Async/Await:** Use async functions for all I/O operations
- **Logging:** Use structured logging with appropriate log levels

### Testing Requirements

- Write tests **before** or **alongside** implementation (TDD encouraged)
- Each tool/resource must have corresponding unit tests
- Mock external API calls in unit tests
- Use fixtures for common test data
- Test both success and error scenarios

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

**Examples:**
- `feat(tools): add firewall rule creation tool`
- `fix(api): handle rate limiting correctly`
- `docs(api): add examples for device tools`
- `test(resources): add integration tests for sites resource`

### Pull Request Guidelines

- Create feature branches: `feature/<description>`
- Keep PRs focused on a single feature or fix
- Include tests with all code changes
- Update documentation as needed
- Ensure all CI checks pass
- Request review from human maintainer

### Security Considerations

- **Never** commit API keys or credentials
- Use environment variables for all secrets
- Validate all user inputs
- Sanitize all outputs
- Use HTTPS for all API communications
- Implement rate limiting on all tools
- Log security-relevant events

## Progress Tracking

Use the following checklist to track development progress:

### Phase 1: Core Infrastructure
- [ ] Configuration management implemented
- [ ] API client foundation complete
- [ ] Utility functions created
- [ ] Unit tests passing (≥80% coverage)

### Phase 2: MCP Resources
- [ ] Sites resource implemented
- [ ] Devices resource implemented
- [ ] Clients resource implemented
- [ ] Networks resource implemented
- [ ] Documentation updated

### Phase 3: Read Operations
- [ ] Device management tools complete
- [ ] Client management tools complete
- [ ] Network information tools complete
- [ ] Site management tools complete
- [ ] Tests passing (≥85% coverage)

### Phase 4: Write Operations
- [ ] Firewall rules tools complete
- [ ] Network configuration tools complete
- [ ] Device control tools complete
- [ ] Client management tools complete
- [ ] Safety mechanisms implemented
- [ ] Audit logging functional

### Phase 5: Advanced Features
- [ ] WiFi management complete
- [ ] Port forwarding complete
- [ ] DPI statistics complete
- [ ] Caching layer implemented
- [ ] Webhook support added

### Phase 6: Testing and QA
- [ ] Unit tests ≥90% coverage
- [ ] Integration tests complete
- [ ] Security scans passing
- [ ] Performance benchmarks complete
- [ ] Code quality checks passing

### Phase 7: Documentation and Deployment
- [ ] API documentation complete
- [ ] User documentation complete
- [ ] Developer documentation complete
- [ ] Docker images published
- [ ] CI/CD pipeline functional
- [ ] Version 0.1.0 released

## Getting Help

If you encounter issues or need clarification:

1. Review the reference documentation links at the top of this document
2. Check the `AGENTS.md` file for AI-specific guidelines
3. Review the `CONTRIBUTING.md` file for contribution guidelines
4. Examine the reference implementation at `sirkirby/unifi-network-mcp`
5. Consult the UniFi API documentation
6. Create an issue in the GitHub repository with detailed information

---

**Author:** Manus AI  
**Last Updated:** October 17, 2025  
**Version:** 1.0

