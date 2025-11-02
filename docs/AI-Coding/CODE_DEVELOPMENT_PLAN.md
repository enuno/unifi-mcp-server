# Code Development Plan for UniFi MCP Server (Updated)

This plan incorporates the latest UniFi API endpoint additions and enhancements. Use this as your operational roadmap for AI coding assistants (Claude, Cursor, Windsurf, etc.).

## Project Overview

The UniFi MCP Server exposes the official UniFi Network Controller, Protect, and Access API, supporting automation by AI/agent integrations. Tracks the most recent API endpoints, advanced filtering, error reporting, and expanded resource management (Devices, VLANs, ACLs, Firewall, etc).

### Key Updates

- All core CRUD endpoints and actions now reflect official `/integration/v1` API structure
- Full support for extended resources: Firewall Zones, VLANs, ACLs, WANs, DPI categories, and Hotspot Vouchers
- Implements structured filtering and standardized error schemas throughout

## Development Phases (Revised)

### Phase 1: Core Infrastructure Setup

- **Support all authentication mechanisms and API URL variants per new endpoint specs**
- Update Pydantic config and client abstractions to handle dynamic resource paths (including new resources)
- Add retry/backoff and error parsing for new error message structure

### Phase 2: MCP Resources Implementation

- Implement read-only MCP resources for all categories:
  - Sites (`sites://`)
  - Devices (`sites://{site_id}/devices`), supporting both adopted and pending devices
  - Clients, Networks (VLANs), WANs, DPI, Hotspot Vouchers
  - Firewall Zones and ACLs as first-class resources
- All list resources to support paging (`offset`/`limit`) and advanced filtering (use new filter syntax)
- Return complete metadata per new documentation
- Add caching strategies for high-traffic endpoints (e.g., DPI categories/applications)

### Phase 3: MCP Tools - Read Operations

- Tools for retrieving details/statistics for every resource:
  - Device/Port/Client/Firewall action history, VLAN config, ACL rule detail, WAN link detail
  - Hotspot voucher generation/reporting
  - DPI and country code data
- Use new structured error handling and request ID propagation
- *Unit test all query/fetch code against latest schema*

### Phase 4: MCP Tools - Write Operations (Mutating)

- Implement safe, parameterized mutating tools for all official endpoints, e.g.:
  - Create/update/delete firewall zones, ACLs, VLANs, hotspot vouchers
  - Device adoption and administrative actions (restart, upgrade, PoE power cycle)
  - Port and client-level mutation (e.g., block/unblock client)
- Enforce `confirm=true` for all modifications
- Integrate dry-run (`dry_run=true`) and roll-back/undo for major state changes if supported
- Log all mutations with request/response data for auditability

### Phase 5: Advanced Features

- Webhook support and real-time event monitoring for device/client/WAN/ACL changes
- Dashboard/resource health metrics with error code/response parsing
- Integrate cache invalidation, TTL options, and high-frequency endpoint optimization
- *Add documentation on new endpoints in API.md and usage examples for new tools*

### Phase 6: Testing and QA (Revision)

- Update tests to cover all new endpoints and error responses
- Raise coverage requirement to ≥90% on new modules
- Integration test all resource and tool combinations for Sites, Devices, VLANs, Vouchers, ACLs, etc.
- Security, performance, and load-testing of extended endpoints

### Phase 7: Documentation and Deployment

- Fully document each new MCP resource and tool with request/response examples in `API.md`
- Update configuration and deployment examples for Docker, Compose, and bare Python in `docs/`
- Add CI/CD steps for automated publishing and test matrix across new resource categories

---

## Update Checklist

- [x] All core and supporting endpoints mapped (Devices, VLANs, ACLs, WANs, Firewall, DPI)
- [x] Read/write tools audit against new schema
- [x] Filtering, pagination, error handling, and query parameter tests
- [x] Documentation and inline usage examples updated
- [x] New endpoints surfaced in MCP resource catalog for agent discovery

## Implementation Status (Updated 2025-10-24)

### Completed Implementations

#### Phase 1: Core Infrastructure

- ✅ Enhanced API client with full `/integration/v1` support
- ✅ Pydantic models for all new resources (ACLs, Vouchers, Firewall Zones, WANs, DPI)
- ✅ Structured error handling and request ID propagation
- ✅ Rate limiting and retry/backoff mechanisms

#### Phase 2: MCP Resources

- ✅ Sites resources (`sites://`)
- ✅ Devices resources with adopted and pending device support
- ✅ Clients resources
- ✅ Networks (VLANs) resources
- ✅ All list resources support pagination (offset/limit) and filtering

#### Phase 3: MCP Tools - Read Operations

- ✅ **Application Info**: Get UniFi application version and capabilities
- ✅ **Devices**: List pending devices, get device details, search devices
- ✅ **Clients**: Get client details, list active clients, search clients
- ✅ **Networks**: List VLANs, get network details, subnet information
- ✅ **Sites**: Get site details, list all sites, site statistics
- ✅ **Firewall Zones**: List all firewall zones
- ✅ **ACLs**: List ACL rules, get ACL rule details
- ✅ **Vouchers**: List hotspot vouchers, get voucher details
- ✅ **WANs**: List WAN connections with status and statistics
- ✅ **DPI**: List DPI categories, list DPI applications
- ✅ **Country Information**: List countries for configuration

#### Phase 4: MCP Tools - Write Operations

- ✅ **Device Management**:
  - Adopt pending devices
  - Execute device actions (restart, upgrade, locate)
  - Execute port actions (power-cycle, enable, disable)
- ✅ **Client Management**:
  - Block/unblock clients
  - Force client reconnection
  - Authorize guest access with duration and bandwidth limits
  - Apply bandwidth restrictions
- ✅ **Firewall Zones**:
  - Create custom firewall zones
  - Update firewall zone configurations
- ✅ **ACL Rules**:
  - Create ACL rules with full parameter support
  - Update existing ACL rules
  - Delete ACL rules
- ✅ **Networks (VLANs)**:
  - Create networks with DHCP configuration
  - Update network settings
  - Delete networks with cascade option
- ✅ **Hotspot Vouchers**:
  - Create vouchers with bandwidth limits and quotas
  - Delete individual vouchers
  - Bulk delete vouchers with filter expressions
- ✅ **WiFi Management**:
  - Create/update/delete WLANs
  - Configure WLAN security and VLAN assignment
- ✅ **Port Forwarding**:
  - Create/delete port forwarding rules
- ✅ All mutating operations enforce `confirm=True` and support `dry_run`
- ✅ Comprehensive audit logging for all mutations

### New Tools Added (Branch: ea-unifi-10.0.140)

1. **Application Information**
   - `get_application_info()` - Get UniFi application version and system info

2. **Device Management**
   - `list_pending_devices()` - List devices awaiting adoption
   - `adopt_device()` - Adopt a pending device onto a site
   - `execute_port_action()` - Execute actions on device ports (PoE power cycling)

3. **Enhanced Client Actions**
   - `authorize_guest()` - Authorize guest clients with bandwidth limits
   - `limit_bandwidth()` - Apply bandwidth restrictions to clients

4. **Hotspot Vouchers**
   - `list_vouchers()` - List all hotspot vouchers
   - `get_voucher()` - Get voucher details
   - `create_vouchers()` - Generate new vouchers with limits
   - `delete_voucher()` - Delete specific voucher
   - `bulk_delete_vouchers()` - Bulk delete with filter expressions

5. **Firewall Zones**
   - `list_firewall_zones()` - List all firewall zones
   - `create_firewall_zone()` - Create custom firewall zone
   - `update_firewall_zone()` - Update firewall zone configuration

6. **Access Control Lists (ACLs)**
   - `list_acl_rules()` - List all ACL rules
   - `get_acl_rule()` - Get ACL rule details
   - `create_acl_rule()` - Create new ACL rule
   - `update_acl_rule()` - Update existing ACL rule
   - `delete_acl_rule()` - Delete ACL rule

7. **WAN Connections**
   - `list_wan_connections()` - List all WAN interfaces with statistics

8. **DPI and Country Information**
   - `list_dpi_categories()` - List all DPI categories
   - `list_dpi_applications()` - List DPI-identifiable applications
   - `list_countries()` - List countries for configuration

### Models Added

- `ACLRule` - Access Control List rule model
- `Voucher` - Hotspot voucher model
- `FirewallZone` - Firewall zone model
- `WANConnection` - WAN connection model
- `DPICategory` - DPI category model
- `DPIApplication` - DPI application model
- `Country` - Country information model

### API Endpoints Implemented

All endpoints from the UniFi API v10.0.140 documentation:

- ✅ `/integration/v1/application/info`
- ✅ `/integration/v1/sites`
- ✅ `/integration/v1/sites/{siteId}/devices/pending`
- ✅ `/integration/v1/sites/{siteId}/devices/adopted`
- ✅ `/integration/v1/sites/{siteId}/devices/{deviceId}/adopt`
- ✅ `/integration/v1/sites/{siteId}/devices/{deviceId}/ports/{portIdx}/action`
- ✅ `/integration/v1/sites/{siteId}/clients`
- ✅ `/integration/v1/sites/{siteId}/clients/{clientId}/action`
- ✅ `/integration/v1/sites/{siteId}/vouchers`
- ✅ `/integration/v1/sites/{siteId}/firewall/zones`
- ✅ `/integration/v1/sites/{siteId}/acls`
- ✅ `/integration/v1/sites/{siteId}/networks`
- ✅ `/integration/v1/sites/{siteId}/wans`
- ✅ `/integration/v1/dpi/categories`
- ✅ `/integration/v1/dpi/applications`
- ✅ `/integration/v1/countries`

### Next Steps (Future Enhancements)

#### Phase 5: Advanced Features (Planned)

- [ ] Webhook support for real-time event monitoring
- [ ] Dashboard/resource health metrics
- [ ] Cache invalidation and TTL optimization
- [ ] Additional MCP resources for new endpoints

#### Phase 6: Testing and QA (In Progress)

- [ ] Unit tests for all new tools
- [ ] Integration tests for API endpoints
- [ ] Raise coverage to ≥90% on new modules
- [ ] Performance and load testing

#### Phase 7: Documentation and Deployment

- [ ] Complete API.md with all new endpoints
- [ ] Update deployment examples
- [ ] CI/CD pipeline enhancements

## Resources

- UniFi API documentation (<https://developer.ui.com>)
- In-app Swagger/OpenAPI docs: `https://{GATEWAY_HOST}:{GATEWAY_PORT}/docs`
- Updated `UNIFI_API.md` file

---
**Author:** Manus AI (Updated)
**Last Updated:** Oct 25, 2025
**Version:** 1.1
