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
- [ ] All core and supporting endpoints mapped (Devices, VLANs, ACLs, WANs, Firewall, DPI)
- [ ] Read/write tools audit against new schema
- [ ] Filtering, pagination, error handling, and query parameter tests
- [ ] Documentation and inline usage examples updated
- [ ] New endpoints surfaced in MCP resource catalog for agent discovery

## Resources
- UniFi API documentation (https://developer.ui.com)
- In-app Swagger/OpenAPI docs: `https://{GATEWAY_HOST}:{GATEWAY_PORT}/docs`
- Updated `UNIFI_API.md` file

---
**Author:** Manus AI (Updated)
**Last Updated:** Oct 25, 2025
**Version:** 1.1
