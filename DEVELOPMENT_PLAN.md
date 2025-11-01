# UniFi MCP Server - Development Plan

## Document Overview

This document outlines the strategic development roadmap for the UniFi MCP Server project. It provides a high-level view of project phases, feature priorities, and long-term goals.

**Related Documents:**
- [CODE_DEVELOPMENT_PLAN.md](docs/AI-Coding/CODE_DEVELOPMENT_PLAN.md) - Detailed technical implementation plan for AI assistants
- [README.md](README.md) - Quick start and usage guide
- [API.md](API.md) - Complete API documentation
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines

---

## Project Vision

Create a production-ready Model Context Protocol (MCP) server that exposes comprehensive UniFi Network Controller functionality, enabling AI agents and applications to manage UniFi infrastructure safely, efficiently, and intuitively.

### Core Principles

1. **Safety First**: All mutating operations require explicit confirmation and support dry-run mode
2. **Developer Experience**: Intuitive APIs with comprehensive documentation and examples
3. **Performance**: Efficient caching and rate limiting for production workloads
4. **Reliability**: Extensive testing, error handling, and audit logging
5. **Standards Compliance**: Full adherence to MCP protocol specifications

---

## Current Status

**Version:** 0.1.0 (Alpha)
**Status:** Feature Complete for v0.1.0
**Current Branch:** `ea-unifi-10.0.140` - UniFi EA API 10.0.140 implementation

### Implementation Summary

- **40 MCP Tools** implemented (16 read-only + 24 mutating)
- **4 MCP Resources** with URI-based access
- **105 Unit Tests** with comprehensive coverage
- **CI/CD Pipelines** for testing, security scanning, and releases
- **Multi-Architecture Docker** images (amd64, arm64)
- **Security Scanning** with CodeQL, Trivy, Bandit, Safety
- **Enterprise-Grade Infrastructure** with pre-commit hooks and automation

---

## Development Phases

### Phase 1: Foundation ✅ COMPLETED

**Status:** ✅ Completed
**Duration:** Initial development (Q4 2024)

#### Objectives
- Establish project infrastructure
- Implement core API client
- Set up development tooling

#### Deliverables
- [x] Project structure and configuration (`pyproject.toml`, `.gitignore`)
- [x] FastMCP-based server implementation
- [x] UniFi API client with authentication
- [x] Configuration management (environment variables, YAML)
- [x] Basic error handling and logging
- [x] Docker containerization
- [x] Development environment setup

#### Technical Achievements
- Python 3.10+ support with type hints
- Async/await architecture
- Pydantic validation throughout
- HTTPx-based HTTP client
- Structured logging with masking

---

### Phase 2: Code Quality Infrastructure ✅ COMPLETED

**Status:** ✅ Completed
**Duration:** Q4 2024

#### Objectives
- Establish enterprise-grade code quality standards
- Automate quality checks and security scanning
- Enable AI-human collaborative development

#### Deliverables
- [x] Pre-commit hooks (11 automated checks)
- [x] Code formatters (Black, isort)
- [x] Linters (Ruff, MyPy)
- [x] Security scanners (Bandit, detect-secrets)
- [x] CI/CD pipelines (.github/workflows/)
- [x] Documentation standards (CONTRIBUTING.md, AGENTS.md, SECURITY.md)
- [x] Custom slash commands for development automation
- [x] Conventional commits enforcement

#### Technical Stack
- **Testing:** pytest, pytest-cov, pytest-asyncio
- **Formatting:** Black (100 char line length), isort
- **Linting:** Ruff, MyPy (strict mode)
- **Security:** Bandit, Safety, detect-secrets, CodeQL
- **CI/CD:** GitHub Actions (multi-Python versions)

---

### Phase 3: Read-Only Operations ✅ COMPLETED

**Status:** ✅ Completed
**Tools:** 16 read-only MCP tools

#### Objectives
- Implement safe, read-only query operations
- Provide comprehensive network visibility
- Establish MCP resource patterns

#### Deliverables

**Device Management (4 tools)**
- [x] `list_devices` - List all UniFi devices in a site
- [x] `get_device_details` - Get detailed device information
- [x] `get_device_statistics` - Real-time device statistics
- [x] `list_devices_by_type` - Filter devices by type (AP, switch, gateway)
- [x] `search_devices` - Search devices by name, MAC, or IP

**Client Management (4 tools)**
- [x] `list_clients` - List all clients (active and inactive)
- [x] `get_client_details` - Get detailed client information
- [x] `get_client_statistics` - Bandwidth and connection statistics
- [x] `list_active_clients` - List currently connected clients only
- [x] `search_clients` - Search clients by MAC, IP, or hostname

**Network Information (4 tools)**
- [x] `list_networks` - List all networks/VLANs
- [x] `get_network_details` - Get network configuration
- [x] `list_vlans` - List VLAN configurations
- [x] `get_subnet_info` - Get subnet and DHCP information
- [x] `get_network_statistics` - Network usage statistics

**Site Management (4 tools)**
- [x] `list_all_sites` - List accessible sites
- [x] `get_site_details` - Get site information
- [x] `get_site_statistics` - Comprehensive site statistics
- [x] `health_check` - Server health verification

**MCP Resources (4 resource types)**
- [x] `sites://{site_id}/devices` - Device resource URIs
- [x] `sites://{site_id}/networks` - Network resource URIs
- [x] `sites://{site_id}/clients` - Client resource URIs
- [x] `sites://` - Sites listing resource

#### Technical Features
- Resource URI scheme implementation
- Pagination support (limit/offset)
- Filtering and search capabilities
- Statistics aggregation
- Error handling with detailed messages

---

### Phase 4: Mutating Operations with Safety ✅ COMPLETED

**Status:** ✅ Completed
**Tools:** 13 mutating MCP tools

#### Objectives
- Enable network configuration changes
- Implement comprehensive safety mechanisms
- Provide audit logging and compliance

#### Safety Mechanisms (Applied to ALL mutating tools)
- **Confirmation Required:** All operations require `confirm=True`
- **Dry-Run Mode:** Preview changes with `dry_run=True`
- **Audit Logging:** All operations logged to `audit.log`
- **Input Validation:** Pydantic-based parameter validation
- **Password Masking:** Automatic masking in logs

#### Deliverables

**Firewall Management (3 tools)**
- [x] `list_firewall_rules` - List all firewall rules
- [x] `create_firewall_rule` - Create firewall rule with traffic filtering
- [x] `update_firewall_rule` - Modify existing firewall rule
- [x] `delete_firewall_rule` - Remove firewall rule

**Network Configuration (3 tools)**
- [x] `create_network` - Create network/VLAN with DHCP
- [x] `update_network` - Update network settings
- [x] `delete_network` - Delete network (with cascade option)

**Device Control (3 tools)**
- [x] `restart_device` - Restart UniFi device
- [x] `locate_device` - Enable/disable LED locate mode
- [x] `upgrade_device` - Trigger firmware upgrade

**Client Management (4 tools)**
- [x] `block_client` - Block client from network
- [x] `unblock_client` - Unblock client
- [x] `reconnect_client` - Force client reconnection
- [x] `authorize_guest` - Authorize guest with time limits

#### Compliance Features
- Audit log format: timestamp, user, action, parameters, result
- Password/key masking in logs
- Request ID tracking
- Error details capture

---

### Phase 5: Advanced Features ✅ COMPLETED

**Status:** ✅ Completed
**Tools:** 11 advanced MCP tools + caching + webhooks

#### Objectives
- Extend WiFi and security management capabilities
- Implement performance optimizations
- Add real-time event processing

#### Deliverables

**WiFi/SSID Management (4 tools)**
- [x] `list_wlans` - List wireless networks
- [x] `create_wlan` - Create WiFi network with WPA2/WPA3
- [x] `update_wlan` - Update WLAN configuration
- [x] `delete_wlan` - Remove wireless network
- [x] `get_wlan_statistics` - WiFi usage statistics
- [x] Support for guest networks, VLAN isolation, hidden SSIDs

**Port Forwarding (3 tools)**
- [x] `list_port_forwards` - List port forwarding rules
- [x] `create_port_forward` - Create forwarding rule
- [x] `delete_port_forward` - Remove forwarding rule
- [x] Protocol support: TCP, UDP, TCP+UDP

**DPI Analytics (3 tools)**
- [x] `get_dpi_statistics` - Site-wide DPI statistics
- [x] `list_top_applications` - Top bandwidth consumers
- [x] `get_client_dpi` - Per-client application usage
- [x] Time ranges: 1h, 6h, 12h, 24h, 7d, 30d

**Caching System (Optional)**
- [x] Redis-based caching implementation
- [x] Configurable TTL per resource type
- [x] Automatic cache invalidation on mutations
- [x] Cache keys: `unifi:{site_id}:{resource_type}:{id}`
- [x] TTL configuration: sites (5m), devices (1m), clients (30s), networks (5m)

**Webhook Support (Optional)**
- [x] Webhook receiver endpoint (`/webhooks/unifi`)
- [x] HMAC signature verification
- [x] Event handlers for device, client, and alert events
- [x] Automatic cache invalidation on events
- [x] Event types: device.online, device.offline, client.connected, client.disconnected, alert.raised

#### Performance Features
- Reduced API calls via caching
- Real-time updates via webhooks
- Efficient data structures
- Connection pooling

---

### Phase 6: UniFi API 10.0.140 Extensions ✅ COMPLETED

**Status:** ✅ Completed (Branch: `ea-unifi-10.0.140`)
**Tools:** 15+ new tools for EA API

#### Objectives
- Support latest UniFi Early Access API (v10.0.140)
- Implement advanced device and client management
- Add hotspot voucher system
- Extend firewall and ACL capabilities

#### New Categories

**Application Information (1 tool)**
- [x] `get_application_info` - Get UniFi application version and system info

**Enhanced Device Management (3 tools)**
- [x] `list_pending_devices` - List devices awaiting adoption
- [x] `adopt_device` - Adopt pending device onto site
- [x] `execute_port_action` - Port-level actions (PoE power cycle, enable/disable)

**Enhanced Client Actions (2 tools)**
- [x] `authorize_guest` - Authorize guest with bandwidth limits and duration
- [x] `limit_bandwidth` - Apply bandwidth restrictions to clients

**Hotspot Vouchers (5 tools)**
- [x] `list_vouchers` - List all hotspot vouchers
- [x] `get_voucher` - Get voucher details
- [x] `create_vouchers` - Generate vouchers with bandwidth/quota limits
- [x] `delete_voucher` - Delete specific voucher
- [x] `bulk_delete_vouchers` - Bulk delete with filter expressions

**Firewall Zones (3 tools)**
- [x] `list_firewall_zones` - List firewall zones
- [x] `create_firewall_zone` - Create custom zone
- [x] `update_firewall_zone` - Update zone configuration

**Access Control Lists (5 tools)**
- [x] `list_acl_rules` - List ACL rules
- [x] `get_acl_rule` - Get ACL rule details
- [x] `create_acl_rule` - Create ACL rule
- [x] `update_acl_rule` - Update ACL rule
- [x] `delete_acl_rule` - Delete ACL rule

**WAN Management (1 tool)**
- [x] `list_wan_connections` - List WAN interfaces with statistics

**DPI and Country Information (3 tools)**
- [x] `list_dpi_categories` - List DPI categories
- [x] `list_dpi_applications` - List DPI-identifiable applications
- [x] `list_countries` - List countries for configuration

#### New Data Models
- [x] `ACLRule` - Access Control List rule model
- [x] `Voucher` - Hotspot voucher model
- [x] `FirewallZone` - Firewall zone model
- [x] `WANConnection` - WAN connection model
- [x] `DPICategory` - DPI category model
- [x] `DPIApplication` - DPI application model
- [x] `Country` - Country information model

#### API Endpoints Implemented
All endpoints from UniFi API v10.0.140:
- [x] `/integration/v1/application/info`
- [x] `/integration/v1/sites/{siteId}/devices/pending`
- [x] `/integration/v1/sites/{siteId}/devices/{deviceId}/adopt`
- [x] `/integration/v1/sites/{siteId}/devices/{deviceId}/ports/{portIdx}/action`
- [x] `/integration/v1/sites/{siteId}/clients/{clientId}/action` (enhanced)
- [x] `/integration/v1/sites/{siteId}/vouchers`
- [x] `/integration/v1/sites/{siteId}/firewall/zones`
- [x] `/integration/v1/sites/{siteId}/acls`
- [x] `/integration/v1/sites/{siteId}/wans`
- [x] `/integration/v1/dpi/categories`
- [x] `/integration/v1/dpi/applications`
- [x] `/integration/v1/countries`

---

## Version 0.2.0 Roadmap (Q1 2025)

**Status:** 🔄 Planning
**Target Release:** Q1 2025

### Goals
- Achieve 90%+ test coverage on all Phase 5 & 6 code
- Performance optimization and benchmarking
- Enhanced documentation and examples
- Bug fixes and stability improvements

### Planned Features

#### Testing & Quality (High Priority)
- [ ] Unit tests for WiFi management tools (Phase 5)
- [ ] Unit tests for port forwarding tools (Phase 5)
- [ ] Unit tests for DPI statistics tools (Phase 5)
- [ ] Unit tests for Phase 6 EA API tools
- [ ] Integration tests for Redis caching
- [ ] Integration tests for webhook processing
- [ ] Performance benchmarks for all endpoints
- [ ] Load testing with concurrent operations
- [ ] Increase coverage target to 90%

#### Performance (Medium Priority)
- [ ] Query optimization for large datasets
- [ ] Batch operation support
- [ ] Response compression
- [ ] Connection pooling optimization
- [ ] Cache warming strategies
- [ ] Rate limit optimization

#### Documentation (Medium Priority)
- [ ] Complete API.md with Phase 6 endpoints
- [ ] Add more code examples
- [ ] Video tutorials for common use cases
- [ ] Architecture diagrams
- [ ] Troubleshooting guide
- [ ] Performance tuning guide

#### Analytics & Monitoring (Low Priority)
- [ ] Enhanced DPI analytics with historical trends
- [ ] Bandwidth usage forecasting
- [ ] Alerting thresholds and notifications
- [ ] Custom dashboard support
- [ ] Export statistics to InfluxDB/Prometheus

#### Minor Enhancements
- [ ] Better error messages with suggested fixes
- [ ] Validation improvements
- [ ] CLI tool for testing and debugging
- [ ] Interactive configuration wizard

#### Performance Monitoring (High Priority)
- [x] Integrate agnost.ai for MCP performance tracking
- [x] Track tool execution times and success rates
- [x] Monitor resource access patterns
- [x] Error rate monitoring and alerting
- [x] Performance bottleneck identification
- [x] MCP Toolbox Docker integration for analytics dashboard
- [ ] Configure advanced alerting rules in Toolbox
- [ ] Set up performance benchmarking reports

### Breaking Changes
None planned for v0.2.0 (backward compatible)

---

## Version 1.0.0 Roadmap (Q2-Q3 2025)

**Status:** 🔮 Future Planning
**Target Release:** Q2-Q3 2025

### Goals
- Production-ready stable release
- Complete UniFi API coverage
- Advanced automation capabilities
- Enterprise features

### Major Features

#### Complete API Coverage
- [ ] Traffic shaping and QoS management
- [ ] VPN configuration (site-to-site, remote access)
- [ ] Alert and notification management
- [ ] IPS/IDS configuration
- [ ] Advanced routing configuration
- [ ] RADIUS server integration
- [ ] Multi-WAN failover configuration

#### Backup & Recovery
- [ ] Configuration backup operations
- [ ] Automated backup scheduling
- [ ] Restore operations with validation
- [ ] Configuration version control
- [ ] Disaster recovery procedures

#### Bulk Operations
- [ ] Mass device configuration
- [ ] Batch firmware upgrades
- [ ] Bulk client operations
- [ ] Site-wide configuration changes
- [ ] Rollback mechanisms

#### Advanced Analytics
- [ ] Historical trend analysis
- [ ] Capacity planning tools
- [ ] Network health scoring
- [ ] Anomaly detection
- [ ] Predictive maintenance

#### Enterprise Features
- [ ] Multi-tenancy support
- [ ] Role-based access control (RBAC)
- [ ] Compliance reporting (SOC 2, HIPAA)
- [ ] Custom audit log formats
- [ ] SSO integration
- [ ] API key management UI

#### Integration & Extensibility
- [ ] Plugin system for custom tools
- [ ] Custom MCP resource types
- [ ] Webhook forwarding
- [ ] External monitoring system integration
- [ ] ChatOps integrations (Slack, Teams, Discord)

### API Stability
- Semantic versioning adherence
- Deprecation policy (6 months notice)
- Migration guides for breaking changes
- Backward compatibility layers

---

## Performance Monitoring & Analytics (NEW)

**Status:** 🔄 In Progress
**Target Completion:** Q1 2025

### Agnost.ai Integration

We're implementing comprehensive MCP performance tracking using [agnost.ai](https://docs.agnost.ai/) to monitor server performance, usage patterns, and identify optimization opportunities.

#### Features
- **Real-time Performance Metrics**: Track tool execution times, success rates, and error patterns
- **User Analytics**: Monitor which tools are most used and by whom
- **Resource Access Patterns**: Understand how MCP resources are accessed
- **Error Tracking**: Automatic error capture and alerting
- **Custom Event Tracking**: Track specific business events (device adoptions, configuration changes)
- **Dashboard**: Visual analytics dashboard for performance insights

#### Implementation Status
- [x] Add agnost dependency to project
- [x] Configure environment variables for agnost organization ID
- [x] Integrate agnost tracking with FastMCP server
- [x] Add tracking to all MCP tools (automatic via FastMCP wrapper)
- [x] Add tracking to MCP resources (automatic via FastMCP wrapper)
- [x] Configure input/output tracking controls
- [ ] Set up dashboard and alerts in agnost.ai

#### Configuration

**Environment Variables:**
```env
# Agnost.ai Configuration (Optional - for performance tracking)
AGNOST_ENABLED=true
AGNOST_ORG_ID=your-organization-id
AGNOST_ENDPOINT=https://api.agnost.ai
AGNOST_DISABLE_INPUT=false   # Set to true to disable input tracking
AGNOST_DISABLE_OUTPUT=false  # Set to true to disable output tracking
```

**Tracking Controls:**
- `disable_input`: When true, tool input parameters are not tracked
- `disable_output`: When true, tool output/results are not tracked
- Both settings provide granular control over what data is sent to agnost.ai

#### Metrics Tracked
- Tool invocation count and timing
- Tool success/failure rates
- Resource access patterns
- Error types and frequencies
- Request/response sizes
- User behavior patterns
- Site-specific operations

#### Privacy & Security
- Control what data is tracked via `disable_input` and `disable_output` flags
- Sensitive data (API keys, passwords) automatically masked in logs
- Can be completely disabled via `AGNOST_ENABLED=false`
- All data encrypted in transit (HTTPS)
- Complies with data retention policies
- Opt-in only (disabled by default)

### MCP Toolbox Integration

**Status:** ✅ Implemented
**Docker Image:** `ghcr.io/agnost-io/toolbox:latest`

#### Overview

MCP Toolbox is a web-based analytics and monitoring dashboard for Model Context Protocol servers, powered by agnost.ai. It provides real-time visualization of:
- Tool execution performance
- Resource access patterns
- Error tracking and debugging
- Usage analytics
- Performance trends

#### Docker Compose Setup

The project now includes a complete Docker Compose configuration with three services:

1. **unifi-mcp**: The UniFi MCP server
2. **mcp-toolbox**: Analytics dashboard (port 8080)
3. **redis**: Caching layer (optional but recommended)

#### Features

**Real-time Dashboard:**
- Live monitoring of tool invocations
- Performance metrics visualization
- Error rate tracking
- Resource utilization graphs

**Analytics:**
- Historical performance data
- Usage patterns and trends
- Tool popularity metrics
- Response time distributions

**Debugging:**
- Request/response inspection
- Error stack traces
- Parameter validation logs
- Performance bottleneck identification

#### Quick Start

```bash
# 1. Copy environment template
cp .env.docker.example .env

# 2. Edit .env with your credentials
#    - Set UNIFI_API_KEY
#    - Set AGNOST_ORG_ID (from https://app.agnost.ai)

# 3. Start all services
docker-compose up -d

# 4. Access Toolbox dashboard
open http://localhost:8080
```

#### Configuration Options

- `TOOLBOX_PORT`: Dashboard port (default: 8080)
- `TOOLBOX_AUTH_ENABLED`: Enable/disable authentication (default: false)
- `TOOLBOX_USERNAME`: Admin username (if auth enabled)
- `TOOLBOX_PASSWORD`: Admin password (if auth enabled)

---

## Technical Debt & Maintenance

### Current Technical Debt
1. **Test Coverage Gaps**
   - Phase 5 tools: WiFi, port forwarding, DPI (current: ~60%)
   - Phase 6 EA API tools (current: minimal)
   - Webhook event handlers
   - Cache invalidation logic

2. **Documentation Gaps**
   - Phase 6 tools missing from API.md
   - Limited deployment examples
   - Missing troubleshooting guide
   - Insufficient code comments in complex areas

3. **Performance Considerations**
   - No query optimization for large sites (>1000 devices)
   - Cache TTL values not tuned for production
   - No connection pooling benchmarks

### Maintenance Strategy

#### Regular Updates
- **Weekly:** Dependency updates and security patches
- **Monthly:** Performance reviews and optimization
- **Quarterly:** Major feature releases

#### Security
- Automated security scanning (CodeQL, Trivy, Bandit, Safety)
- Weekly vulnerability checks
- Immediate patching for critical issues
- Security disclosure policy in SECURITY.md

#### Dependencies
- Pin major versions in `pyproject.toml`
- Test updates in CI before merging
- Monitor deprecations and EOL dates

---

## Success Metrics

### Code Quality Metrics
- **Test Coverage:** ≥80% (current), target ≥90% (v0.2.0)
- **Type Coverage:** 100% (MyPy strict mode)
- **Linting:** Zero issues (Ruff, Black, isort)
- **Security:** Zero high/critical vulnerabilities

### Performance Metrics
- **API Response Time:** <500ms (p95)
- **Cache Hit Rate:** >70%
- **Rate Limit Efficiency:** <80% of API limits
- **Uptime:** 99.9%

### Adoption Metrics
- GitHub stars and forks
- Docker image pulls
- Community contributions
- Issue resolution time (<48h for critical)

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### How to Contribute to This Plan
1. Open an issue to discuss feature proposals
2. Create a PR with plan updates
3. Participate in quarterly planning sessions
4. Vote on feature priorities via GitHub Discussions

---

## Resources

### Official Documentation
- [UniFi API Documentation](https://developer.ui.com)
- [Model Context Protocol Spec](https://github.com/anthropics/mcp)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)

### Project Documentation
- [README.md](README.md) - Project overview and quick start
- [API.md](API.md) - Complete API reference
- [CODE_DEVELOPMENT_PLAN.md](docs/AI-Coding/CODE_DEVELOPMENT_PLAN.md) - Technical implementation details
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guide
- [SECURITY.md](SECURITY.md) - Security policy
- [AGENTS.md](AGENTS.md) - AI agent guidelines

### Community
- [GitHub Issues](https://github.com/enuno/unifi-mcp-server/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/enuno/unifi-mcp-server/discussions) - Questions and ideas
- [GitHub Projects](https://github.com/enuno/unifi-mcp-server/projects) - Development board

---

## Changelog

### v0.1.0 (Current)
- ✅ Initial release with 40 MCP tools
- ✅ Complete Phase 3-6 implementation
- ✅ UniFi EA API 10.0.140 support
- ✅ CI/CD pipelines and security scanning
- ✅ Docker multi-architecture support

---

**Last Updated:** 2025-11-01
**Version:** 0.1.0
**Status:** Active Development
**Maintainer:** Elvis (@enuno)

---

*This development plan is a living document. Updates are made as the project evolves.*
