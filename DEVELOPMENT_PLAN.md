# UniFi MCP Server Development Plan

**📋 Version Correction Notice**: v0.2.0 was published prematurely on 2025-11-17. The current stable release is v0.1.4 (identical code). The true v0.2.0 with all planned features is targeted for Q1 2025.

**🆕 Recent Updates (2025-11-26)**:
- ✅ Implemented comprehensive multi-API support (local, cloud-v1, cloud-ea)
- ✅ Fixed list_vlans to return all networks including WAN, VPN, and corporate networks
- ✅ Updated UNIFI_API.md to v10.0.156 with comprehensive endpoint documentation
- ✅ Added automatic endpoint translation for local gateway API
- ✅ Implemented response normalization across all three API types

## 1. Executive Summary

This document outlines the strategic roadmap for the modernization of the UniFi MCP Server. The primary goal is to align the server's capabilities with the latest advancements in the UniFi ecosystem, ensuring its continued relevance and value to users.

The immediate priorities are the implementation of **Zone-Based Firewall (ZBF)** and **Traffic Flows API** support, which are critical for users of UniFi Network Application 9.0 and above. These features represent a fundamental shift in UniFi's networking paradigm, and their absence in the MCP Server is a significant gap.

The development plan is structured around a phased rollout, with clear version milestones and technical objectives. The timeline for major milestones is as follows:

- **Q1 2025:** Introduction of modern firewall and monitoring capabilities.
- **Q2 2025:** Implementation of policy automation and next-generation networking features.
- **H2 2025:** Expansion into a multi-application platform with enterprise-grade features.

This plan is ambitious yet achievable, and it is designed to provide a clear path forward for the project, its contributors, and its users.

## 2. Version Roadmap

### Version 0.2.0 (Q1 2025) - Modern Firewall & Monitoring

This release will focus on delivering the most critical features for modern UniFi deployments, addressing the highest priority gaps identified in the comprehensive API analysis.

- **Zone-Based Firewall API (Critical - P0):**
  - Full support for Zone-Based Firewall introduced in UniFi Network 9.0
  - Zone creation and management (Internal, External, Gateway, VPN zones)
  - Zone-to-zone traffic policies via zone matrix operations
  - Zone membership assignment for devices and networks
  - Guest Hotspot integration with ZBF
  - Quick application blocking using zone-based rules
  - Migration tools from traditional firewall rules to ZBF
  - **API Endpoints:** `/api/s/{site}/rest/firewallzone`, `/api/s/{site}/rest/firewallzonematrix`
  - **Estimated Tools:** 5-8 new MCP tools

- **Traffic Flows Monitoring (Critical - P0):**
  - Real-time traffic flow visualization with packet counts and connection details
  - Flow ID tracking for granular connection monitoring
  - Application-level traffic analysis beyond basic DPI categories
  - Quick block actions from traffic flows (block source/destination IP)
  - Enhanced client traffic aggregation with authentication failure tracking
  - Live bandwidth monitoring with streaming updates (10-15 second intervals)
  - Custom flow filtering and view operations
  - **API Endpoints:** `/api/s/{site}/stat/trafficflow`, `/api/s/{site}/rest/trafficflow`
  - **Estimated Tools:** 4-6 new MCP tools

- **Advanced QoS and Traffic Management (High - P1):**
  - **Status:** 🚀 READY TO IMPLEMENT - Detailed plan complete (2025-11-28)
  - QoS profile management with 0-7 priority levels and DSCP marking (0-63)
  - 6 reference traffic profiles: Voice-First, Video-Conferencing, Cloud-Gaming, Streaming-Media, Bulk-Backup, Guest-Best-Effort
  - 7 ProAV protocol templates: Dante, Q-SYS, SDVoE, AVB, RAVENNA/AES67, NDI, SMPTE 2110
  - Smart Queue Management (SQM) with fq_codel for WAN <300 Mbps
  - Traffic routing rules with match criteria and time-based scheduling
  - Bandwidth limits, guarantees, and DSCP preservation
  - **Best Practices Documented:** Hardware offload impact, trust boundaries, performance considerations
  - **API Endpoints:** `/api/s/{site}/rest/qosprofile`, `/api/s/{site}/rest/routing`, `/api/s/{site}/rest/wanconf`
  - **Estimated Tools:** 12-15 new MCP tools (5 QoS profile, 3 ProAV, 3 Smart Queue, 4 Traffic Route)
  - **Test Coverage Target:** 80%+ (40-50 comprehensive tests)
  - **Estimated Effort:** 27-35 hours (2-3 weeks)

- **Backup and Restore Operations (High - P1):**
  - System config backups (complete OS, application, device configurations)
  - Network-only backups (network settings and device configurations)
  - Automated cloud backup management (weekly + pre-update backups)
  - Backup listing, download, and deletion
  - Partial restoration capabilities
  - Cross-device migration support
  - Backup scheduling and retention policies
  - **API Endpoints:** `/api/cmd/backup`, `/api/backup/list-backups`, `/api/backup/delete-backup`, `/api/backup/restore`
  - **Estimated Tools:** 4-6 new MCP tools

- **Site Manager API Foundation (High - P1):**
  - OAuth/SSO authentication for Site Manager API at `unifi.ui.com`
  - Multi-site aggregated monitoring and management
  - Cross-site device status and health metrics
  - Internet health metrics integration
  - Vantage Point support for performance monitoring
  - Multi-tenant architecture for enterprise deployments
  - **Estimated Tools:** 3-4 new MCP tools

- **Enhanced RADIUS and Guest Portal (Medium - P2):**
  - Full CRUD operations for RADIUS profiles (currently GET only)
  - RADIUS account management (creation, modification, deletion)
  - Guest portal customization API
  - Voucher system with bandwidth and time limits
  - Hotspot package configuration
  - Payment gateway integration support (Stripe)
  - External portal server configuration
  - RADIUS-assigned VLAN support
  - Guest authorization code management
  - **API Endpoints:** `/api/s/{site}/rest/radiusprofile` (full CRUD), `/api/s/{site}/rest/account`, `/api/s/{site}/rest/hotspotpackage`, `/api/s/{site}/cmd/hotspot`
  - **Estimated Tools:** 4-6 new MCP tools

- **Topology Retrieval and Network Mapping (Medium - P2):**
  - Network topology graph data retrieval
  - Device interconnection details and port-level connection mapping
  - Client-to-device associations for visualization
  - Link label data (speeds, port numbers, connection types)
  - Automated network diagram data generation
  - **API Endpoints:** `/api/s/{site}/stat/topology`
  - **Estimated Tools:** 2-3 new MCP tools

**Total Estimated New Tools for v0.2.0:** ~25-35 new MCP tools
**Target Timeline:** Q1 2025 (3-4 months development)
**Development Effort:** ~15-20 weeks total across all features

### Version 0.3.0 (Q2 2025) - Policy Automation & SD-WAN

This release will build on the foundation of v0.2.0 by introducing advanced policy automation, SD-WAN management, and enhanced monitoring capabilities.

- **SD-WAN Management (Critical - P0):**
  - Hub-and-spoke topology configuration supporting up to 1,000 locations
  - Redundant failover hub setup for disaster recovery
  - License-free site-to-site VPN at scale
  - Mesh mode support for up to 20 interconnected sites
  - Zero Touch Provisioning (ZTP) for remote site deployment
  - Multi-site SD-WAN topology management and visualization
  - Automated failover configuration and testing
  - Site-to-site VPN tunnel automation
  - **Dependencies:** Site Manager API (from v0.2.0)
  - **Estimated Tools:** 6-8 new MCP tools

- **Alert and Notification Management (High - P1):**
  - Configurable alert triggers (device offline, login attempts, performance thresholds)
  - Email and push notification configuration
  - Location-based notifications with geofencing support
  - Webhook delivery for custom integrations and automation
  - Alert priority and recipient management
  - Per-admin notification preferences
  - SMTP and SSO email service configuration
  - Alert rule CRUD operations with template support
  - **API Endpoints:** Alert configuration endpoints, webhook registration
  - **Estimated Tools:** 4-6 new MCP tools

- **Object-Oriented Networking (High - P1):**
  - Device Groups for streamlined policy management
  - Network Objects for reusable network definitions
  - Policy Engine for automated policy application across devices
  - Template-based configuration deployment
  - Bulk operations on device groups
  - Tools to eliminate manual firewall rule creation
  - **Estimated Tools:** 4-5 new MCP tools

- **Enhanced DPI with Historical Trends (Medium - P2):**
  - Historical DPI trend analysis over time
  - Application usage patterns and comparative analytics
  - Time-series data for bandwidth consumption by application
  - Predictive usage modeling and forecasting
  - Export capabilities for DPI historical data
  - **Dependencies:** Traffic Flows API (from v0.2.0)
  - **Estimated Tools:** 2-3 new MCP tools

- **Enhanced Monitoring Capabilities (Medium - P2):**
  - Advanced real-time monitoring of system and network metrics
  - CPU, memory, and performance metrics per device
  - Wi-Fi, wired, and VPN client monitoring with detailed statistics
  - Multi-site performance aggregation and comparison
  - Live traffic statistics with streaming updates
  - **Estimated Tools:** 3-4 new MCP tools

- **Speed Test Execution and Management (Medium - P2):**
  - Network speed test triggering from API
  - Speed test status monitoring
  - Historical speed test results and trending
  - Scheduled speed test execution
  - **API Endpoints:** `/api/s/{site}/cmd/devmgr/speedtest`, `/api/s/{site}/cmd/devmgr/speedtest-status`
  - **Estimated Tools:** 2-3 new MCP tools

- **Next-Generation Networking (Medium - P2):**
  - WiFi 7 MLO (Multi-Link Operation) configuration and management
  - BGP support for advanced routing
  - Advanced VLAN management
  - Network segmentation tools
  - **Estimated Tools:** 3-4 new MCP tools

- **Device Migration Tools (Low - P3):**
  - Device migration between controllers
  - Migration status monitoring and cancellation
  - Cross-controller device transfer workflows
  - **API Endpoints:** `/api/s/{site}/cmd/devmgr/migrate`, `/api/s/{site}/cmd/devmgr/cancel-migrate`
  - **Estimated Tools:** 2 new MCP tools

**Total Estimated New Tools for v0.3.0:** ~26-35 new MCP tools
**Target Timeline:** Q2 2025 (3-4 months development)
**Development Effort:** ~16-22 weeks total across all features

### Version 1.0.0 (H2 2025) - Multi-Application Platform

This release will mark the transition of the UniFi MCP Server into a comprehensive, multi-application platform with enterprise-grade capabilities, expanding beyond UniFi Network to support the entire UniFi ecosystem.

- **VPN Configuration Management (Critical - P0):**
  - WireGuard VPN server configuration and management
  - OpenVPN client/server management
  - VPN client peer management with QR code generation
  - Site-to-site VPN automation integrated with SD-WAN
  - Policy-based routing through VPN tunnels
  - Split tunneling configuration
  - VPN credential generation and revocation
  - VPN connection monitoring and troubleshooting
  - **Dependencies:** SD-WAN management (from v0.3.0)
  - **API Endpoints:** VPN server/client configuration endpoints
  - **Estimated Tools:** 5-7 new MCP tools

- **UniFi Identity Integration (High - P1):**
  - Identity Endpoint API for unified authentication
  - One-click WiFi and VPN access provisioning
  - LDAP/Active Directory integration endpoints
  - Directory provisioning and synchronization
  - Event hooks for identity events
  - Identity-based network access control
  - User lifecycle management
  - **Note:** Separate authentication context from Network API
  - **Estimated Tools:** 4-6 new MCP tools

- **UniFi Access Integration (High - P1):**
  - Smart door access management via mobile/wearable devices
  - Door unlock methods (NFC, Mobile, Face, PIN, QR, License Plate)
  - 2-step authentication configuration
  - Access schedules and policies
  - Visitor management workflows
  - Access event monitoring and logging
  - Door lock/unlock operations
  - **Note:** Separate application with distinct API endpoints
  - **Estimated Tools:** 5-7 new MCP tools

- **UniFi Protect Integration (Medium - P2):**
  - Camera snapshot retrieval
  - Motion detection events via webhooks
  - Alarm manager trigger configuration
  - Location-based notification settings for cameras
  - Video clip management
  - Camera configuration and status monitoring
  - **Note:** Separate application with distinct API endpoints
  - **Estimated Tools:** 4-5 new MCP tools

- **UniFi Talk Integration (Medium - P2):**
  - VoIP phone management
  - Call routing configuration
  - Voicemail management
  - Call history and analytics
  - **Estimated Tools:** 3-4 new MCP tools

- **Advanced Analytics Platform (High - P1):**
  - Comprehensive analytics platform for network intelligence
  - Cross-application insights (Network, Access, Protect)
  - Predictive analytics for network performance
  - Anomaly detection capabilities
  - Custom dashboard and reporting
  - Data export and integration with BI tools
  - **Dependencies:** Multiple data sources from v0.2.0 and v0.3.0
  - **Estimated Tools:** 4-6 new MCP tools

- **Enterprise-Grade Features (High - P1):**
  - Full feature parity with UniFi Site Manager
  - Advanced security features (SSL/TLS decryption, IDS/IPS integration)
  - Traffic sandboxing and threat analysis
  - Compliance reporting (PCI-DSS, HIPAA, GDPR)
  - Advanced user role and permission management
  - Audit logging and forensics
  - **Estimated Tools:** 5-7 new MCP tools

- **Spectrum Scan and RF Analysis (Medium - P2):**
  - RF spectrum scan results retrieval
  - Channel utilization analysis
  - Interference detection and reporting
  - Optimal channel recommendations
  - **API Endpoints:** `/api/s/{site}/stat/spectrumscan`
  - **Estimated Tools:** 2-3 new MCP tools

- **Additional Network Features (Low - P3):**
  - Dynamic DNS full CRUD operations (currently GET only)
  - Custom DDNS service configuration
  - Tagged MAC address management
  - Tag creation, assignment, and device grouping
  - Cloud/SSO connection status monitoring
  - **API Endpoints:** `/api/s/{site}/rest/dynamicdns` (PUT/POST), `/api/s/{site}/rest/tag`, `/api/s/{site}/stat/sdn`
  - **Estimated Tools:** 3-4 new MCP tools

**Total Estimated New Tools for v1.0.0:** ~35-50 new MCP tools
**Target Timeline:** H2 2025 (6-8 months development)
**Development Effort:** ~30-40 weeks total across all features
**Total Tools (v0.1.0 + all releases):** ~125-160 MCP tools

## 3. API Gap Analysis & Research Findings

This section provides a comprehensive analysis of UniFi API features and implementation gaps based on extensive research into the official UniFi API ecosystem, UniFi Network 9.0+ features, and community documentation.

### 3.1 Official UniFi API Ecosystem

**✅ IMPLEMENTATION UPDATE (2025-11-26)**: UniFi MCP Server now supports all three API types with automatic endpoint translation and response normalization.

UniFi provides three primary API types, all now supported:

1. **Local Gateway API** (Recommended) ✅ **FULLY IMPLEMENTED**
   - Complete feature support with detailed analytics and control
   - Direct access to UniFi gateway (e.g., 192.168.1.1)
   - All MCP tools functional (devices, clients, networks, firewall, WiFi, etc.)
   - Automatic endpoint translation from cloud format to local format
   - Site UUID → name mapping (uses 'default' instead of UUIDs)
   - Path mapping: `/ea/sites/{site}/devices` → `/proxy/network/api/s/{site}/stat/device`
   - SSL enforcement with configurable verification (`UNIFI_LOCAL_VERIFY_SSL`)
   - Configuration: `UNIFI_API_TYPE=local`

2. **Cloud V1 API** (Stable, Limited) ✅ **FULLY IMPLEMENTED**
   - Stable v1 API via `api.ui.com/v1/...`
   - High-level insights with aggregate statistics only
   - **Limitations**: No individual device/client access, no configuration changes
   - Rate limit: 10,000 requests/minute
   - Best for: Multi-site monitoring dashboards, internet health metrics
   - Configuration: `UNIFI_API_TYPE=cloud-v1`

3. **Cloud Early Access API** (Testing, Limited) ✅ **FULLY IMPLEMENTED**
   - Early Access API via `api.ui.com/ea/...`
   - Same limitations as Cloud V1 (aggregate statistics only)
   - Rate limit: 100 requests/minute
   - Best for: Testing new cloud API features
   - Configuration: `UNIFI_API_TYPE=cloud-ea`

**Response Normalization**: All three API types return consistent data structures:
- Cloud V1: Extracts `{data, httpStatusCode, traceId}` wrapper
- Local: Extracts `{data, count, totalCount}` wrapper
- Cloud EA: Pass-through (no wrapper)

### 3.2 Critical Implementation Gaps

The following features represent critical gaps in the current implementation that significantly impact functionality for UniFi Network 9.0+ users.

#### 3.2.1 Zone-Based Firewall (ZBF) Management

**Status:** ✅ Partially Implemented (Core zone management working, advanced features limited by API)

**✅ IMPLEMENTATION UPDATE (2025-11-18)**: Zone management tools implemented and verified on real hardware (U7 Express & UDM Pro, v10.0.156).

UniFi Network 9.0 introduced Zone-Based Firewall rules, fundamentally changing how traffic is managed by grouping devices and services into zones.

**Implemented Capabilities (7 tools working):**

- ✅ Zone creation and management (`create_firewall_zone`, `update_firewall_zone`, `delete_firewall_zone`)
- ✅ Zone listing and details (`list_firewall_zones`, `get_zone_networks`)
- ✅ Zone membership assignment (`assign_network_to_zone`, `unassign_network_from_zone`)
- ✅ Zone types: Internal, External, Gateway, VPN zones supported

**API Limitations (8 tools deprecated - endpoints don't exist):**

- ❌ Zone-to-zone traffic policies (matrix operations) - **Must use UniFi Console UI**
- ❌ Application blocking per zone (DPI-based) - **Must use UniFi Console UI**
- ❌ Zone statistics and monitoring - **Must use UniFi Console UI**
- See ZBF_STATUS.md for complete endpoint verification report

**Current Implementation:**

- Zone management tools in `src/tools/firewall_zones.py` (7 working tools)
- Deprecated matrix tools in `src/tools/zbf_matrix.py` (8 non-functional tools, kept for reference)
- `FirewallZone` data model in `src/models/firewall_zone.py`
- Traditional firewall rules in `src/tools/firewall.py`
- Test coverage: 84.13% (22 tests)

**API Endpoints Required:**

- `/api/s/{site}/rest/firewallzone` - Zone management
- `/api/s/{site}/rest/firewallzonematrix` - Zone-to-zone policies
- Zone assignment operations for devices and networks

#### 3.2.2 Traffic Flow Analysis & Real-Time Monitoring

**Status:** ✅ **FULLY IMPLEMENTED** (2025-11-08)

**✅ IMPLEMENTATION UPDATE**: Complete traffic flow monitoring system with 15 tools, 86.62% test coverage.

UniFi Network 9.0 significantly enhanced traffic flow monitoring beyond basic Deep Packet Inspection.

**Implemented Capabilities (15 tools):**

- ✅ Real-time traffic flow visualization with packet counts (`get_traffic_flows`, `stream_traffic_flows`)
- ✅ Flow ID tracking and connection details (`get_traffic_flow_details`)
- ✅ Application-level traffic analysis (`get_flow_analytics`, `get_top_flows`)
- ✅ Quick block actions (`block_flow_source_ip`, `block_flow_destination_ip`, `block_flow_application`)
- ✅ Enhanced client traffic aggregation (`get_client_flow_aggregation`)
- ✅ Connection state tracking (`get_connection_states`) - active, closed, timed-out
- ✅ Live bandwidth monitoring with polling (15-second intervals, WebSocket-ready)
- ✅ Flow filtering and analytics (`filter_traffic_flows`, `get_flow_statistics`)
- ✅ Risk assessment and trending (`get_flow_risks`, `get_flow_trends`)
- ✅ Export capabilities (`export_traffic_flows`) - CSV and JSON formats

**Current Implementation:**

- Traffic flow tools in `src/tools/traffic_flows.py` (15 tools)
- Data models in `src/models/traffic_flow.py` (TrafficFlow, FlowStatistics, FlowRisk, FlowView)
- DPI statistics tools in `src/tools/dpi.py`
- Test coverage: 86.62% (16 tests)
- Integration with ZBF for application blocking

**API Endpoints Implemented:**

- ✅ `/api/s/{site}/stat/trafficflow` - Real-time flow data
- ✅ `/api/s/{site}/rest/trafficflow` - Flow management
- ✅ Flow filtering and custom view operations
- ⏳ WebSocket support for streaming updates (ready for future implementation)

#### 3.2.3 Advanced QoS and Traffic Management

**Status:** Not implemented

UniFi now provides sophisticated Quality of Service capabilities for traffic prioritization and shaping.

**Missing Capabilities:**

- Application-based traffic prioritization
- Pre-configured ProAV profiles (Dante, Q-SYS, SDVoE)
- Category-based traffic shaping
- DSCP tagging and remarking operations
- Advanced bandwidth control with schedules
- Queue-based priority assignment (0-7 priority levels)
- Per-application bandwidth limits

**Current Implementation:**

- Basic network configuration only
- No dedicated QoS tools

**API Endpoints Required:**

- `/api/s/{site}/rest/trafficroute` - Traffic routing rules
- `/api/s/{site}/rest/qosprofile` - QoS profile management
- ProAV profile configuration endpoints
- DSCP remarking operations

#### 3.2.4 SD-WAN Management

**Status:** Not implemented

UniFi Network 9.0 introduced SiteMagic SD-WAN with hub-and-spoke and mesh topologies.

**Missing Capabilities:**

- Hub-and-spoke topology configuration (up to 1,000 locations)
- Redundant failover hub setup for disaster recovery
- License-free site-to-site VPN at scale
- Mesh mode for up to 20 interconnected sites
- Zero Touch Provisioning (ZTP) for remote site deployment
- Multi-site SD-WAN topology management
- Automated failover configuration

**Current Implementation:**

- No SD-WAN management capabilities

**API Endpoints Required:**

- SD-WAN topology configuration endpoints
- Hub-and-spoke architecture management
- Site-to-site VPN automation
- Failover hub configuration
- ZTP provisioning workflows

#### 3.2.5 Backup and Restore Operations

**Status:** Roadmap v0.2.0, not implemented

UniFi distinguishes between system-level and network-only backups with cloud integration.

**Missing Capabilities:**

- System config backups (complete OS, application, device configs)
- Network-only backups (network settings and device configurations)
- Automated cloud backup management (weekly + pre-update)
- Partial restoration capabilities
- Cross-device migration support
- Backup scheduling and retention policies

**Current Implementation:**

- None (mentioned in roadmap but not implemented)

**API Endpoints Required:**

- `/api/cmd/backup` - Trigger backup creation
- `/api/backup/list-backups` - List available backups
- `/api/backup/delete-backup` - Delete specific backup
- `/api/backup/restore` - Restore from backup
- Cloud backup configuration

#### 3.2.6 Alert and Notification Management

**Status:** Not implemented

UniFi provides comprehensive alerting for network events and performance thresholds.

**Missing Capabilities:**

- Configurable alert triggers (device offline, login attempts, performance)
- Email and push notification configuration
- Location-based notifications (geofencing)
- Webhook delivery for custom integrations
- Alert priority and recipient management
- Per-admin notification preferences
- SMTP and SSO email service configuration

**Current Implementation:**

- No alert or notification management tools

**API Endpoints Required:**

- System log settings configuration
- Per-admin notification preference endpoints
- Email service configuration (SMTP/SSO)
- Webhook registration and management
- Alert rule CRUD operations

#### 3.2.7 VPN Configuration Management

**Status:** Roadmap v1.0.0, not implemented

UniFi supports WireGuard and OpenVPN with advanced features.

**Missing Capabilities:**

- WireGuard VPN server configuration
- OpenVPN client/server management
- VPN client peer management with QR code generation
- Site-to-site VPN automation
- Policy-based routing through VPN tunnels
- Split tunneling configuration
- VPN credential generation and revocation

**Current Implementation:**

- None (mentioned in v1.0.0 roadmap)

**API Endpoints Required:**

- VPN server configuration endpoints
- Client/peer credential generation
- VPN interface management for policy routes
- Site-to-site VPN tunnel configuration
- WireGuard peer management

#### 3.2.8 Topology Retrieval and Network Mapping

**Status:** Not implemented

UniFi provides detailed network topology visualization data.

**Missing Capabilities:**

- Network topology graph data retrieval
- Device interconnection details
- Port-level connection mapping
- Client-to-device associations with visual representation
- Link label data (speeds, port numbers, connection types)
- Automated network diagram generation

**Current Implementation:**

- No topology or mapping capabilities

**API Endpoints Required:**

- `/api/s/{site}/stat/topology` - Topology graph data
- Device connection details
- Port mapping information
- Client association data for visualization

#### 3.2.9 Enhanced Guest Portal & RADIUS Management

**Status:** Partially implemented (basic listing only)

UniFi provides advanced guest portal and RADIUS authentication features.

**Missing Capabilities:**

- RADIUS profile CRUD operations (only listing implemented)
- Guest portal customization API
- Voucher system with bandwidth/time limits
- Payment gateway integration (Stripe)
- External portal server configuration
- RADIUS-assigned VLAN support
- Facebook/social media authentication
- Guest authorization code management

**Current Implementation:**

- RADIUS profile listing in `src/unifi_mcp_server/tools/radius.py`
- RADIUS account listing only
- No voucher or guest portal tools

**API Endpoints Required:**

- `/api/s/{site}/rest/radiusprofile` - Full CRUD operations
- `/api/s/{site}/rest/account` - RADIUS account management
- `/api/s/{site}/rest/hotspotpackage` - Hotspot package configuration
- `/api/s/{site}/cmd/hotspot` - Voucher generation and management
- Guest portal customization endpoints

#### 3.2.10 UniFi Identity & Access Management

**Status:** Out of scope (separate application)

UniFi Identity and Access represent separate applications with their own APIs.

**Missing Capabilities:**

- Identity Endpoint API for unified authentication
- Smart door access via mobile/wearable devices
- One-click WiFi and VPN access
- LDAP/Active Directory integration endpoints
- Directory provisioning and synchronization
- Event hooks for identity events
- Door unlock methods (NFC, Mobile, Face, PIN, QR, License Plate)
- 2-step authentication configuration
- Access schedules and policies
- Visitor management

**Current Implementation:**

- None (unifi-mcp-server focuses on Network application only)

**Consideration:**

- These features are part of separate UniFi applications (Access, Identity)
- May be candidates for v1.0.0 Multi-Application Platform expansion
- Require separate authentication and API client considerations

### 3.3 Moderate Implementation Gaps

The following features represent moderate-priority gaps that enhance functionality but are not critical for core operations.

#### 3.3.1 Enhanced DPI with Historical Trends

**Current Status:** Basic DPI statistics implemented

**Missing:**

- Historical DPI trend analysis
- Application usage patterns over time
- Comparative analytics across time periods
- Predictive usage modeling

#### 3.3.2 Spectrum Scan Results

**Current Status:** Not implemented

**Missing:**

- `/api/s/{site}/stat/spectrumscan` - RF spectrum scan results
- Channel utilization analysis
- Interference detection and reporting

#### 3.3.3 Speed Test Execution

**Current Status:** Not implemented

**Missing:**

- `/api/s/{site}/cmd/devmgr/speedtest` - Trigger speed test
- `/api/s/{site}/cmd/devmgr/speedtest-status` - Check status
- Historical speed test results

#### 3.3.4 Device Migration Between Controllers

**Current Status:** Not implemented

**Missing:**

- `/api/s/{site}/cmd/devmgr/migrate` - Device migration
- `/api/s/{site}/cmd/devmgr/cancel-migrate` - Cancel migration
- Cross-controller device transfer

#### 3.3.5 Dynamic DNS Configuration

**Current Status:** Partially implemented (GET only)

**Missing:**

- `/api/s/{site}/rest/dynamicdns` - PUT/POST operations
- Full CRUD for DDNS providers
- Custom DDNS service configuration

#### 3.3.6 Tagged MAC Management

**Current Status:** Not implemented

**Missing:**

- `/api/s/{site}/rest/tag` - Tagged MAC addresses
- Tag creation, assignment, and management
- Device grouping via tags

### 3.4 Feature-to-Version Mapping

Based on the gap analysis, here is the recommended mapping of features to version milestones:

#### Version 0.2.0 Priority Features

- Zone-Based Firewall (ZBF) - **Critical**
- Traffic Flow Analysis - **Critical**
- Advanced QoS and Traffic Management - **High**
- Backup and Restore Operations - **High**
- Enhanced RADIUS and Guest Portal - **Medium**
- Topology Retrieval - **Medium**

#### Version 0.3.0 Priority Features

- SD-WAN Management - **Critical**
- Alert and Notification Management - **High**
- Enhanced DPI with Historical Trends - **Medium**
- Speed Test Execution - **Medium**
- Device Migration Tools - **Low**

#### Version 1.0.0 Priority Features

- VPN Configuration Management - **Critical**
- UniFi Identity Integration - **High**
- UniFi Access Integration - **High**
- UniFi Protect Integration - **Medium**
- Dynamic DNS Full CRUD - **Low**
- Tagged MAC Management - **Low**

### 3.5 API Endpoint Inventory

This section provides a comprehensive inventory of UniFi API endpoints categorized by implementation status.

#### Fully Implemented (v0.1.0)

- Device management (`/api/s/{site}/stat/device`, `/api/s/{site}/rest/device`)
- Client operations (`/api/s/{site}/stat/sta`, `/api/s/{site}/rest/user`)
- Basic firewall rules (`/api/s/{site}/rest/firewallrule`)
- WiFi configuration (`/api/s/{site}/rest/wlanconf`)
- Port forwarding (`/api/s/{site}/rest/portforward`)
- Basic DPI statistics (`/api/s/{site}/stat/dpi`)
- Site operations (`/api/s/{site}/stat/health`)

#### Partially Implemented

- RADIUS profiles (`/api/s/{site}/rest/radiusprofile`) - GET only
- Dynamic DNS (`/api/s/{site}/rest/dynamicdns`) - GET only
- RADIUS accounts (`/api/s/{site}/rest/account`) - Listing only

#### Not Implemented - High Priority

- `/api/s/{site}/rest/firewallzone` - Zone-based firewall zones
- `/api/s/{site}/rest/firewallzonematrix` - Zone-to-zone policies
- `/api/s/{site}/stat/trafficflow` - Real-time traffic flows
- `/api/s/{site}/rest/trafficroute` - Traffic routing/QoS rules
- `/api/cmd/backup` - Backup operations
- `/api/backup/list-backups` - Backup management
- SD-WAN configuration endpoints
- Alert configuration endpoints
- VPN server/client management endpoints

#### Not Implemented - Medium Priority

- `/api/s/{site}/stat/topology` - Network topology
- `/api/s/{site}/stat/spectrumscan` - Spectrum analysis
- `/api/s/{site}/cmd/devmgr/speedtest` - Speed tests
- `/api/s/{site}/rest/hotspotpackage` - Guest portal packages
- `/api/s/{site}/cmd/hotspot` - Voucher management
- `/api/s/{site}/rest/tag` - Tagged MACs
- Enhanced notification configuration

#### Not Implemented - Low Priority

- `/api/s/{site}/cmd/devmgr/migrate` - Device migration
- `/api/s/{site}/stat/sdn` - Cloud/SSO status
- `/api/s/{site}/stat/authorization` - Guest authorization

### 3.6 Research Sources

This gap analysis is based on extensive research from the following sources:

**Official Ubiquiti Documentation:**

- UniFi API Getting Started Guide (help.ui.com)
- UniFi Network Application documentation
- UniFi Access and Identity documentation
- Feature release notes for Network 9.0+

**Community Resources:**

- Art-of-WiFi UniFi API Client and Browser (GitHub)
- Ubiquiti Community Wiki API documentation
- Community forums and discussion threads

**Third-Party Analysis:**

- UniFi Network 9.0 feature analysis articles
- Integration guides and tutorials
- YouTube technical walkthroughs

**Total Sources Referenced:** 60+ articles, documentation pages, and community resources

## 4. Technical Architecture Updates

This section details the technical architecture changes required to support the new features identified in the gap analysis.

### 4.1 API Client Enhancements

The API client layer requires significant enhancements to support new endpoint categories and data patterns.

#### 4.1.1 Zone-Based Firewall Support

**New Endpoint Handlers:**

- `/api/s/{site}/rest/firewallzone` - Zone management (GET, POST, PUT, DELETE)
- `/api/s/{site}/rest/firewallzonematrix` - Zone-to-zone policy matrix (GET, POST, PUT)

**Data Models:**

```python
class FirewallZone:
    _id: str
    name: str
    type: Literal["INTERNAL", "EXTERNAL", "GATEWAY", "VPN"]
    members: List[str]  # Network IDs or device IDs
    description: Optional[str]
    enabled: bool
```

```python
class FirewallZoneMatrix:
    _id: str
    source_zone_id: str
    destination_zone_id: str
    action: Literal["ACCEPT", "REJECT", "DROP"]
    rule_priority: int
```

**Zone Membership Assignment:**

- Network-to-zone mapping
- Device-to-zone assignment
- Dynamic zone membership based on client type

#### 4.1.2 Traffic Flow Integration

**New Endpoint Handlers:**

- `/api/s/{site}/stat/trafficflow` - Real-time flow data (GET with advanced filters)
- `/api/s/{site}/rest/trafficflow` - Flow management operations

**Data Models:**

```python
class TrafficFlow:
    flow_id: str
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    protocol: str
    application: str
    bytes_sent: int
    bytes_received: int
    packets_sent: int
    packets_received: int
    start_time: datetime
    last_seen: datetime
    client_mac: Optional[str]
    risk_score: Optional[int]
```

**Real-Time Streaming:**

- WebSocket support for flow updates (10-15 second intervals)
- Polling fallback mechanism
- Flow filtering by application, client, time range

#### 4.1.3 QoS and Traffic Management

**New Endpoint Handlers:**

- `/api/s/{site}/rest/trafficroute` - Traffic routing rules (CRUD)
- `/api/s/{site}/rest/qosprofile` - QoS profile management (CRUD)

**Data Models:**

```python
class QoSProfile:
    _id: str
    name: str
    priority_level: int  # 0-7
    applications: List[str]
    dscp_marking: Optional[int]
    bandwidth_limit_down: Optional[int]  # kbps
    bandwidth_limit_up: Optional[int]    # kbps
    schedule: Optional[str]  # cron-like schedule
```

```python
class TrafficRoute:
    _id: str
    name: str
    match_criteria: Dict[str, Any]  # application, source, destination
    qos_profile_id: str
    action: Literal["PRIORITIZE", "LIMIT", "BLOCK"]
```

#### 4.1.4 Backup and Restore

**New Endpoint Handlers:**

- `/api/cmd/backup` - Trigger backup creation (POST)
- `/api/backup/list-backups` - List available backups (GET)
- `/api/backup/delete-backup` - Delete specific backup (DELETE)
- `/api/backup/restore` - Restore from backup (POST)

**Data Models:**

```python
class BackupMetadata:
    backup_id: str
    filename: str
    backup_type: Literal["SYSTEM", "NETWORK"]
    created_at: datetime
    size_bytes: int
    controller_version: str
    site_count: int
    device_count: int
    cloud_synced: bool
```

#### 4.1.5 Site Manager API

**Authentication:**

- OAuth/SSO support for `unifi.ui.com` endpoints
- Token management and refresh mechanisms
- Separate authentication context from local application APIs

**New Endpoint Handlers:**

- Site Manager API endpoints at `https://api.ui.com/ea/...`
- Multi-site aggregated monitoring
- Internet health metrics

**Data Models:**

```python
class SiteHealth:
    site_id: str
    site_name: str
    internet_health_score: int  # 0-100
    device_count: int
    client_count: int
    alerts_active: int
    last_updated: datetime
```

#### 4.1.6 Topology and Network Mapping

**New Endpoint Handlers:**

- `/api/s/{site}/stat/topology` - Network topology graph data (GET)

**Data Models:**

```python
class TopologyNode:
    node_id: str
    node_type: Literal["DEVICE", "CLIENT", "NETWORK"]
    name: str
    connections: List[TopologyConnection]
    position: Optional[Dict[str, float]]  # x, y coordinates
```

```python
class TopologyConnection:
    target_node_id: str
    port_number: Optional[int]
    connection_type: str  # "wired", "wireless", "uplink"
    speed_mbps: Optional[int]
    link_quality: Optional[int]
```

#### 4.1.7 Alert and Notification Management

**New Endpoint Handlers:**

- Alert configuration endpoints (to be researched - Network 9.0+)
- Webhook registration and management
- SMTP/email configuration

**Data Models:**

```python
class AlertRule:
    _id: str
    name: str
    trigger_type: str  # "DEVICE_OFFLINE", "HIGH_CPU", "LOGIN_FAILURE", etc.
    conditions: Dict[str, Any]
    notification_channels: List[str]  # channel IDs
    enabled: bool
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
```

```python
class NotificationChannel:
    _id: str
    type: Literal["EMAIL", "PUSH", "WEBHOOK"]
    config: Dict[str, Any]  # email addresses, webhook URL, etc.
    recipients: List[str]
```

#### 4.1.8 VPN Configuration

**New Endpoint Handlers:**

- VPN server configuration endpoints (WireGuard, OpenVPN)
- VPN peer management
- Policy-based routing configuration

**Data Models:**

```python
class VPNServer:
    _id: str
    type: Literal["WIREGUARD", "OPENVPN"]
    name: str
    listen_port: int
    network: str  # VPN subnet
    dns_servers: List[str]
    enabled: bool
```

```python
class VPNPeer:
    _id: str
    server_id: str
    name: str
    public_key: str  # WireGuard only
    allowed_ips: List[str]
    qr_code: Optional[str]  # base64 encoded QR for mobile setup
    created_at: datetime
    last_handshake: Optional[datetime]
```

### 4.2 Data Modeling & Caching

#### 4.2.1 New Data Models Summary

| Model | Purpose | Caching Strategy |
|-------|---------|------------------|
| FirewallZone | Zone definitions | Medium TTL (5 min), invalidate on update |
| FirewallZoneMatrix | Zone policies | Medium TTL (5 min), invalidate on update |
| TrafficFlow | Real-time flows | Short TTL (15 sec), streaming preferred |
| QoSProfile | QoS configurations | Long TTL (1 hour), invalidate on update |
| TrafficRoute | Traffic routing rules | Long TTL (1 hour), invalidate on update |
| BackupMetadata | Backup file info | Medium TTL (5 min), refresh on list |
| TopologyNode | Network topology | Medium TTL (10 min), manual refresh |
| AlertRule | Alert configurations | Long TTL (1 hour), invalidate on update |
| VPNServer | VPN server configs | Long TTL (1 hour), invalidate on update |
| VPNPeer | VPN peer/client info | Medium TTL (10 min), invalidate on update |

#### 4.2.2 Caching Strategies

**Real-Time Data (Traffic Flows, Live Stats):**

- Short TTL: 10-15 seconds
- WebSocket streaming preferred over polling
- Client-side caching with server push updates

**Configuration Data (ZBF, QoS, VPN):**

- Medium-Long TTL: 5-60 minutes
- Cache invalidation on write operations
- Optimistic updates with background refresh

**Static/Reference Data (Topology, Backups):**

- Long TTL: 10-60 minutes
- Manual refresh triggers available
- Lazy loading with background prefetch

### 4.3 Authentication & Multi-Tenancy

#### 4.3.1 Site Manager API Authentication

**OAuth/SSO Flow:**

1. User authenticates via `unifi.ui.com` SSO
2. Receive OAuth token and refresh token
3. Store tokens separately from local API credentials
4. Automatic token refresh mechanism
5. Fallback to manual re-authentication

**Multi-Tenant Architecture:**

- Per-site credential storage (encrypted)
- Site isolation in data layer
- Cross-site operations with explicit scope
- Role-based access control (RBAC) per site

#### 4.3.2 Multi-Application Authentication

**Separate Authentication Contexts:**

- UniFi Network API (local controller)
- Site Manager API (`unifi.ui.com`)
- UniFi Access API (separate controller)
- UniFi Identity API (separate controller)
- UniFi Protect API (separate controller)

Each application requires:

- Separate credential management
- Independent session handling
- Unified credential vault in MCP server

### 4.4 MCP Tools Organization

#### 4.4.1 New Tool Categories

**Zone-Based Firewall (`src/unifi_mcp_server/tools/firewall_zone/`):**

- `create_zone` - Create new firewall zone
- `list_zones` - List all zones
- `update_zone` - Modify zone configuration
- `delete_zone` - Remove zone
- `assign_to_zone` - Assign device/network to zone
- `get_zone_matrix` - Retrieve zone-to-zone policies
- `update_zone_matrix` - Modify zone-to-zone policy
- `migrate_rules_to_zbf` - Migration tool from traditional rules

**Traffic Flow Management (`src/unifi_mcp_server/tools/traffic_flow/`):**

- `get_flows` - Retrieve current traffic flows (with filters)
- `get_flow_details` - Get details for specific flow
- `block_flow` - Quick block source/destination IP
- `get_flow_stats` - Aggregated flow statistics
- `export_flows` - Export flow data for analysis

**QoS and Traffic Management (`src/unifi_mcp_server/tools/qos/`):**

- `create_qos_profile` - Create QoS profile
- `list_qos_profiles` - List all profiles
- `update_qos_profile` - Modify profile
- `create_traffic_route` - Create traffic routing rule
- `apply_proav_profile` - Apply ProAV template

**Backup and Restore (`src/unifi_mcp_server/tools/backup/`):**

- `trigger_backup` - Create new backup
- `list_backups` - List available backups
- `download_backup` - Download backup file
- `delete_backup` - Remove backup
- `restore_backup` - Restore from backup
- `get_backup_status` - Check backup operation status

**Network Topology (`src/unifi_mcp_server/tools/topology/`):**

- `get_topology` - Retrieve network topology graph
- `export_topology` - Export topology data (JSON, GraphML)

**Alert Management (`src/unifi_mcp_server/tools/alerts/`):**

- `create_alert_rule` - Create new alert
- `list_alert_rules` - List all rules
- `update_alert_rule` - Modify alert
- `create_notification_channel` - Add notification channel
- `test_notification` - Test notification delivery

**VPN Management (`src/unifi_mcp_server/tools/vpn/`):**

- `create_vpn_server` - Configure VPN server
- `list_vpn_servers` - List VPN servers
- `create_vpn_peer` - Add VPN client/peer
- `generate_peer_qr` - Generate QR code for mobile
- `list_vpn_peers` - List all peers
- `revoke_peer` - Revoke peer access

#### 4.4.2 Tool Count Estimates

| Version | New Tool Categories | Estimated New Tools | Cumulative Tools |
|---------|---------------------|---------------------|------------------|
| v0.1.0 | - | 40 | 40 |
| v0.2.0 | ZBF, Traffic Flow, QoS, Backup, Topology, RADIUS | 25-35 | 65-75 |
| v0.3.0 | SD-WAN, Alerts, Object-Oriented, Enhanced Monitoring | 26-35 | 91-110 |
| v1.0.0 | VPN, Multi-App (Identity, Access, Protect), Analytics | 35-50 | 126-160 |

### 4.5 Error Handling and Safety Mechanisms

#### 4.5.1 Extended Safety Features

**Zone-Based Firewall:**

- Dry-run mode for zone matrix changes
- Validation of zone membership conflicts
- Rollback mechanism for policy changes
- Warning on potentially disruptive rules

**Traffic Flow:**

- Rate limiting on flow queries
- Automatic pagination for large result sets
- Warning before blocking critical flows

**Backup and Restore:**

- Mandatory confirmation for restore operations
- Backup validation before restore
- Pre-restore backup creation
- Partial restore capabilities

**VPN Configuration:**

- Validation of VPN network conflicts
- Warning on split tunnel security implications
- Automatic backup before VPN config changes

## 5. Implementation Priorities

This section provides a detailed breakdown of implementation priorities based on criticality, user impact, technical dependencies, and development effort. Priorities are organized into phases aligned with version milestones.

### 5.1 Priority Levels

- **P0 (Critical):** Essential features affecting core functionality or blocking UniFi Network 9.0+ users
- **P1 (High):** Important features with high user demand or significant value add
- **P2 (Medium):** Valuable enhancements that improve functionality but not critical
- **P3 (Low):** Nice-to-have features with limited user impact

### 5.2 Version 0.2.0 Priorities (Q1 2025)

#### Phase 1: Zone-Based Firewall (P0 - Critical)

**Rationale:**

- Highest priority, as it affects all users of UniFi Network 9.0+ (current stable release)
- Fundamental shift in UniFi's firewall paradigm from traditional rules to zone-based architecture
- Traditional firewall rules being deprecated in favor of ZBF
- Users unable to fully utilize Network 9.0 features without this support

**Implementation Requirements:**

- Deep understanding of zone-based architecture and zone types (Internal, External, Gateway, VPN)
- New data models for `FirewallZone` and `FirewallZoneMatrix`
- Zone membership assignment algorithms for devices and networks
- Migration path and tools from traditional rules to ZBF
- Guest Hotspot integration with zone-based rules

**Estimated Effort:** 3-4 weeks
**Dependencies:** None (can start immediately)
**Risk Level:** Medium (new architectural paradigm)

**API Endpoints:**

- `/api/s/{site}/rest/firewallzone` (CRUD)
- `/api/s/{site}/rest/firewallzonematrix` (CRUD)

#### Phase 2: Traffic Flows Integration (P0 - Critical)

**Rationale:**

- Essential for modern security and compliance requirements
- UniFi Network 9.0 introduced significant enhancements beyond basic DPI
- Real-time monitoring critical for network operations and troubleshooting
- Enables quick-block actions from traffic analysis

**Implementation Requirements:**

- Real-time data processing and analytics capabilities
- WebSocket or polling mechanism for live updates (10-15 second intervals)
- Flow filtering and custom view operations
- Quick block action integration with firewall tools
- Enhanced client traffic aggregation logic

**Estimated Effort:** 2-3 weeks
**Dependencies:** None (can run parallel with Phase 1)
**Risk Level:** Medium (real-time data streaming)

**API Endpoints:**

- `/api/s/{site}/stat/trafficflow` (GET with advanced filters)
- `/api/s/{site}/rest/trafficflow` (management operations)

#### Phase 3: Advanced QoS and Traffic Management (P1 - High)

**Rationale:**

- Enhances network performance and user experience
- ProAV profiles critical for professional audio/video deployments
- Application-based prioritization increasingly important for business networks
- DSCP tagging required for WAN optimization

**Implementation Requirements:**

- QoS profile data models for traffic prioritization
- Traffic routing rule engine for application-based policies
- DSCP tagging and remarking operations
- Bandwidth scheduling with time-based policies
- ProAV profile templates (Dante, Q-SYS, SDVoE)

**Estimated Effort:** 2-3 weeks
**Dependencies:** Traffic Flow analysis (for monitoring QoS effectiveness)
**Risk Level:** Low-Medium

**API Endpoints:**

- `/api/s/{site}/rest/trafficroute` (CRUD)
- `/api/s/{site}/rest/qosprofile` (CRUD)

#### Phase 4: Backup and Restore Operations (P1 - High)

**Rationale:**

- Critical for disaster recovery and migration scenarios
- Currently on roadmap but not implemented
- High user demand for automated backup management
- Essential for production deployments

**Implementation Requirements:**

- Backup trigger and scheduling mechanisms
- Backup list management with metadata
- Retention policies and cloud backup integration
- Restore operations with validation and rollback
- Support for both system and network-only backups

**Estimated Effort:** 1-2 weeks
**Dependencies:** None
**Risk Level:** Low (well-documented API)

**API Endpoints:**

- `/api/cmd/backup` (POST)
- `/api/backup/list-backups` (GET)
- `/api/backup/delete-backup` (DELETE)
- `/api/backup/restore` (POST)

#### Phase 5: Site Manager API Foundation (P1 - High)

**Rationale:**

- Required for enterprise deployments with multiple sites
- Multi-site management increasingly common
- Official Ubiquiti API requires integration for cloud features
- Foundation for future cross-site operations

**Implementation Requirements:**

- OAuth/SSO authentication for `unifi.ui.com` endpoints
- Multi-tenant architecture for site isolation
- Cross-site aggregated monitoring capabilities
- Internet health metrics integration
- Vantage Point support for performance tracking

**Estimated Effort:** 2-3 weeks
**Dependencies:** Authentication system enhancements
**Risk Level:** Medium (new authentication paradigm)

#### Phase 6: Enhanced RADIUS and Guest Portal (P2 - Medium)

**Rationale:**

- Currently partially implemented (listing only)
- Guest portal features important for hospitality and public WiFi use cases
- RADIUS enhancements needed for enterprise authentication
- Voucher system requested by multiple users

**Implementation Requirements:**

- Full CRUD operations for RADIUS profiles
- Voucher generation and management with bandwidth/time limits
- Guest portal customization API
- Payment gateway integration (Stripe) - optional
- RADIUS-assigned VLAN support

**Estimated Effort:** 1-2 weeks
**Dependencies:** None
**Risk Level:** Low

**API Endpoints:**

- `/api/s/{site}/rest/radiusprofile` (PUT/POST/DELETE)
- `/api/s/{site}/rest/account` (full CRUD)
- `/api/s/{site}/rest/hotspotpackage` (CRUD)
- `/api/s/{site}/cmd/hotspot` (voucher operations)

#### Phase 7: Topology Retrieval and Network Mapping (P2 - Medium)

**Rationale:**

- Valuable for network visualization and troubleshooting
- Enhances understanding of network structure and device interconnections
- Moderate user demand for topology export

**Implementation Requirements:**

- Topology graph data parsing and structuring
- Device interconnection mapping logic
- Port-level connection details
- Client association visualization data
- Link metadata (speeds, port numbers, connection types)

**Estimated Effort:** 1 week
**Dependencies:** None
**Risk Level:** Low

**API Endpoints:**

- `/api/s/{site}/stat/topology` (GET)

### 5.3 Version 0.3.0 Priorities (Q2 2025)

#### Phase 8: SD-WAN Management (P0 - Critical)

**Rationale:**

- UniFi Network 9.0 introduced major SD-WAN enhancements (SiteMagic)
- Hub-and-spoke topology critical for enterprise deployments
- Supports up to 1,000 locations (massive scale)
- License-free site-to-site VPN valuable for cost-conscious deployments

**Implementation Requirements:**

- SD-WAN topology configuration and visualization
- Hub-and-spoke architecture management (primary + failover hubs)
- Mesh mode support for up to 20 interconnected sites
- Zero Touch Provisioning (ZTP) integration for remote deployment
- Automated failover configuration and testing
- Site-to-site VPN tunnel automation

**Estimated Effort:** 3-4 weeks
**Dependencies:** Site Manager API (from v0.2.0)
**Risk Level:** High (complex multi-site coordination)

#### Phase 9: Alert and Notification Management (P1 - High)

**Rationale:**

- Critical for proactive network monitoring and incident response
- Webhook integration important for automation and ITSM integration
- High user demand for custom alerting beyond default notifications
- Email configuration needed for self-hosted deployments

**Implementation Requirements:**

- Alert rule configuration with customizable triggers
- Notification channel management (email, push, webhooks)
- Alert priority and recipient management
- SMTP/SSO email configuration
- Location-based notifications with geofencing
- Alert templates and bulk operations

**Estimated Effort:** 2 weeks
**Dependencies:** None
**Risk Level:** Low-Medium

#### Phase 10: Object-Oriented Networking (P1 - High)

**Rationale:**

- Significant efficiency gains for network administrators
- Eliminates repetitive manual configuration
- Policy-based automation critical for large deployments
- Template-based deployment reduces human error

**Implementation Requirements:**

- Device Group data models and operations
- Network Object definitions (reusable IP ranges, ports, etc.)
- Policy Engine for automated policy application
- Template-based configuration deployment
- Bulk operations on device groups

**Estimated Effort:** 2-3 weeks
**Dependencies:** ZBF (for policy application)
**Risk Level:** Medium

### 5.4 Version 1.0.0 Priorities (H2 2025)

#### Phase 11: VPN Configuration Management (P0 - Critical)

**Rationale:**

- WireGuard support increasingly important for modern deployments
- Site-to-site VPN critical for enterprise multi-site networks
- Policy-based routing enhances security and compliance
- QR code generation simplifies mobile client setup

**Implementation Requirements:**

- WireGuard server/client configuration and management
- OpenVPN server/client management (backward compatibility)
- VPN peer management with QR code generation
- Policy-based routing through VPN tunnels
- Split tunneling configuration
- VPN credential generation and revocation

**Estimated Effort:** 3-4 weeks
**Dependencies:** SD-WAN management (for site-to-site integration)
**Risk Level:** Medium

#### Phase 12: Multi-Application Integration (P1 - High)

**Rationale:**

- Expands MCP server beyond Network application
- UniFi ecosystem value in integrated management
- Identity, Access, and Protect represent high-value targets
- Cross-application analytics unlock new insights

**Implementation Requirements:**

- Separate authentication contexts for each application
- UniFi Identity API integration (LDAP/AD, event hooks)
- UniFi Access API integration (door access, visitor management)
- UniFi Protect API integration (cameras, motion events)
- Cross-application data correlation

**Estimated Effort:** 8-10 weeks (across all applications)
**Dependencies:** Multiple application-specific research efforts
**Risk Level:** High (multiple new APIs)

### 5.5 Priority Summary Table

| Phase | Feature | Priority | Version | Effort | Dependencies | Risk |
|-------|---------|----------|---------|--------|--------------|------|
| 1 | Zone-Based Firewall | P0 | 0.2.0 | 3-4w | None | Medium |
| 2 | Traffic Flows | P0 | 0.2.0 | 2-3w | None | Medium |
| 3 | Advanced QoS | P1 | 0.2.0 | 2-3w | Traffic Flows | Low-Med |
| 4 | Backup/Restore | P1 | 0.2.0 | 1-2w | None | Low |
| 5 | Site Manager API | P1 | 0.2.0 | 2-3w | Auth | Medium |
| 6 | Enhanced RADIUS | P2 | 0.2.0 | 1-2w | None | Low |
| 7 | Topology | P2 | 0.2.0 | 1w | None | Low |
| 8 | SD-WAN | P0 | 0.3.0 | 3-4w | Site Manager | High |
| 9 | Alerts | P1 | 0.3.0 | 2w | None | Low-Med |
| 10 | Object-Oriented Networking | P1 | 0.3.0 | 2-3w | ZBF | Medium |
| 11 | VPN Management | P0 | 1.0.0 | 3-4w | SD-WAN | Medium |
| 12 | Multi-App Integration | P1 | 1.0.0 | 8-10w | Research | High |

### 5.6 Parallel Development Opportunities

The following phases can be developed in parallel to accelerate delivery:

**v0.2.0 Parallel Tracks:**

- Track A: Phase 1 (ZBF) + Phase 4 (Backup)
- Track B: Phase 2 (Traffic Flows) + Phase 5 (Site Manager API)
- Track C: Phase 3 (QoS) - depends on Track B
- Track D: Phase 6 (RADIUS) + Phase 7 (Topology) - independent

**v0.3.0 Parallel Tracks:**

- Track A: Phase 8 (SD-WAN) - requires Site Manager from v0.2.0
- Track B: Phase 9 (Alerts) + Phase 10 (Object-Oriented) - can run parallel

**v1.0.0 Parallel Tracks:**

- Track A: Phase 11 (VPN) - requires SD-WAN from v0.3.0
- Track B: Multi-app integration (Identity, Access, Protect) - can run parallel

## 6. Breaking Changes & Migration

- **Firewall Rule Management:**
  - The introduction of ZBF will likely introduce breaking changes to existing firewall rule management.
  - A clear migration path will be provided for users of the traditional firewall system.
- **Backward Compatibility:**
  - Efforts will be made to maintain backward compatibility where possible.
  - Deprecation notices will be issued for any features that are being replaced.

## 7. Testing & Quality Assurance

- **Unit Tests:**
  - The existing test suite will be expanded to cover the new API surface area.
  - New unit tests will be written for all ZBF and Traffic Flows functionality.
- **Integration Tests:**
  - Integration tests will be conducted with UniFi Network 9.0+ to ensure compatibility.
  - Multi-site testing scenarios will be developed to validate the Site Manager API.
- **Performance Tests:**
  - Performance testing will be conducted to ensure the efficient processing of Traffic Flows data.
  - Caching and data processing pipelines will be optimized for performance.

## 8. Documentation Updates

This section outlines the documentation requirements for each version milestone, ensuring comprehensive coverage of new features with examples, tutorials, and integration guides.

### 8.1 API Documentation (API.md)

The `API.md` file will be significantly expanded to cover all new features and endpoints.

#### 8.1.1 Version 0.2.0 Documentation

**Zone-Based Firewall Section:**

- Complete endpoint reference for `/api/s/{site}/rest/firewallzone` and `/api/s/{site}/rest/firewallzonematrix`
- Zone type descriptions (Internal, External, Gateway, VPN)
- Zone membership assignment patterns
- Zone-to-zone policy matrix operations
- Migration guide from traditional firewall rules to ZBF

**Traffic Flows Section:**

- Real-time flow monitoring endpoint documentation
- Flow filtering parameters and examples
- Quick-block action workflows
- Flow statistics and aggregation examples
- WebSocket streaming implementation guide

**QoS and Traffic Management Section:**

- QoS profile configuration reference
- Traffic routing rule syntax
- ProAV profile templates (Dante, Q-SYS, SDVoE)
- DSCP marking and remarking examples
- Bandwidth scheduling configuration

**Backup and Restore Section:**

- Backup creation and scheduling
- Backup list management
- Restore operation workflows
- Cloud backup integration
- Backup validation and verification

**Site Manager API Section:**

- OAuth/SSO authentication flow
- Multi-site monitoring endpoints
- Internet health metrics reference
- Vantage Point integration
- Cross-site operations

**Enhanced RADIUS and Guest Portal Section:**

- Full CRUD operations for RADIUS profiles
- Voucher generation and management
- Guest portal customization API
- Payment gateway integration (Stripe)
- RADIUS-assigned VLAN configuration

**Network Topology Section:**

- Topology graph data structure
- Device interconnection mapping
- Port-level connection details
- Topology export formats (JSON, GraphML)

#### 8.1.2 Version 0.3.0 Documentation

**SD-WAN Management Section:**

- Hub-and-spoke topology configuration
- Mesh mode setup (up to 20 sites)
- Zero Touch Provisioning (ZTP) workflows
- Failover hub configuration
- Site-to-site VPN automation

**Alert and Notification Section:**

- Alert rule configuration reference
- Notification channel types (email, push, webhooks)
- Alert trigger types and conditions
- SMTP/SSO email configuration
- Webhook integration examples

**Object-Oriented Networking Section:**

- Device Group operations
- Network Object definitions
- Policy Engine workflows
- Template-based deployment
- Bulk configuration operations

#### 8.1.3 Version 1.0.0 Documentation

**VPN Configuration Section:**

- WireGuard server/client setup
- OpenVPN server/client management
- VPN peer management with QR codes
- Policy-based routing through VPN
- Split tunneling configuration

**Multi-Application Integration Sections:**

- UniFi Identity API reference
- UniFi Access API reference
- UniFi Protect API reference
- UniFi Talk API reference
- Cross-application workflows

### 8.2 Usage Guides and Tutorials

#### 8.2.1 Version 0.2.0 Tutorials

**Zone-Based Firewall Workflows:**

1. "Getting Started with Zone-Based Firewall" - Basic zone setup
2. "Migrating from Traditional Firewall Rules to ZBF" - Step-by-step migration
3. "Advanced Zone Matrix Policies" - Complex multi-zone scenarios
4. "Guest Network Isolation with ZBF" - Guest hotspot integration

**Traffic Flow Monitoring Guides:**

1. "Real-Time Traffic Flow Analysis" - Monitoring active connections
2. "Identifying and Blocking Suspicious Traffic" - Security workflows
3. "Application-Level Traffic Analysis" - DPI integration
4. "Traffic Flow Reporting and Analytics" - Data export and analysis

**QoS Configuration Tutorials:**

1. "Setting Up QoS for VoIP Traffic" - Voice prioritization
2. "ProAV Profile Configuration for Professional Audio/Video" - Dante, Q-SYS setup
3. "Application-Based Traffic Shaping" - Custom QoS policies
4. "DSCP Marking for WAN Optimization" - Enterprise QoS

**Backup and Restore Workflows:**

1. "Automated Backup Configuration" - Scheduling and retention
2. "Cross-Controller Migration" - Moving to new hardware
3. "Disaster Recovery Planning" - Backup strategies
4. "Partial Restore Operations" - Selective configuration restore

#### 8.2.2 Version 0.3.0 Tutorials

**SD-WAN Configuration Guides:**

1. "Setting Up Hub-and-Spoke SD-WAN" - Enterprise deployment
2. "Mesh Mode for Small Multi-Site Networks" - Up to 20 sites
3. "Zero Touch Provisioning for Remote Sites" - ZTP workflows
4. "Failover Hub Configuration" - High availability

**Alert and Notification Tutorials:**

1. "Configuring Device Offline Alerts" - Proactive monitoring
2. "Webhook Integration with ITSM Systems" - ServiceNow, Jira
3. "Custom Email Alert Templates" - SMTP configuration
4. "Geofencing and Location-Based Alerts" - Advanced notifications

#### 8.2.3 Version 1.0.0 Tutorials

**VPN Configuration Guides:**

1. "WireGuard VPN Server Setup" - Modern VPN deployment
2. "Mobile Client Configuration with QR Codes" - Easy onboarding
3. "Site-to-Site VPN with SD-WAN Integration" - Enterprise connectivity
4. "Policy-Based Routing through VPN" - Traffic steering

**Multi-Application Integration Guides:**

1. "Integrating UniFi Access with Network" - Door access + WiFi
2. "UniFi Identity for Unified Authentication" - LDAP/AD integration
3. "Camera Integration with Network Events" - Protect + Network
4. "Cross-Application Analytics" - Unified insights

### 8.3 MCP Tool Reference Documentation

Each MCP tool will have comprehensive documentation including:

**Standard Documentation Template:**

1. **Tool Name and Description** - What the tool does
2. **Parameters** - Required and optional parameters with types
3. **Return Values** - Expected response structure
4. **Examples** - Basic and advanced usage examples
5. **Safety Considerations** - Warnings and confirmations
6. **Related Tools** - Cross-references to related functionality
7. **API Endpoints Used** - Underlying UniFi API calls

**Example Tool Documentation (create_firewall_zone):**

```markdown
### create_firewall_zone

Creates a new Zone-Based Firewall zone.

**Parameters:**
- `name` (string, required): Zone name
- `type` (string, required): Zone type - INTERNAL, EXTERNAL, GATEWAY, or VPN
- `description` (string, optional): Zone description
- `enabled` (boolean, optional, default: true): Enable zone immediately

**Returns:**
- `zone_id` (string): Created zone ID
- `zone` (object): Complete zone configuration

**Examples:**
Basic internal zone:
```json
{
  "name": "Corporate_LAN",
  "type": "INTERNAL",
  "description": "Corporate internal network"
}
```

**Safety Considerations:**

- Creating zones without proper matrix policies may block traffic unexpectedly
- Review zone matrix after creating new zones

**Related Tools:**

- list_zones
- update_zone
- update_zone_matrix

**API Endpoints:**

- POST `/api/s/{site}/rest/firewallzone`

```

### 8.4 Integration Documentation

#### 8.4.1 MCP Client Integration

**Claude Desktop Integration:**
- Configuration file setup (`claude_desktop_config.json`)
- Environment variable configuration
- Authentication credential management
- Multi-site setup

**Cline Integration:**
- Extension configuration
- Workspace-specific settings
- Credential storage

**Other MCP Clients:**
- Generic MCP client integration guide
- Server capabilities advertisement
- Tool discovery mechanism

#### 8.4.2 External System Integration

**Version 0.3.0 Integrations:**
- Webhook integration patterns (alert notifications)
- ITSM system integration (ServiceNow, Jira, PagerDuty)
- Monitoring system integration (Prometheus, Grafana)
- SIEM integration (Splunk, ELK Stack)

**Version 1.0.0 Integrations:**
- LDAP/Active Directory integration (UniFi Identity)
- Access control system integration (UniFi Access)
- Video management integration (UniFi Protect)
- VoIP system integration (UniFi Talk)

### 8.5 Research Sources and References

This development plan is based on extensive research from the following authoritative sources:

#### 8.5.1 Official Ubiquiti Documentation

**Primary Sources:**
1. **UniFi API Getting Started Guide** - https://help.ui.com/hc/en-us/articles/30076656117655
   - Official API overview
   - Site Manager API documentation
   - Local Application API structure

2. **UniFi Network Application Documentation** - https://help.ui.com
   - Feature documentation for Network 9.0+
   - Configuration guides
   - Best practices

3. **UniFi Access and Identity Documentation** - https://help.ui.com
   - UniFi Access API capabilities
   - Identity Endpoint API
   - LDAP/AD integration guides

4. **UniFi Protect Documentation** - https://help.ui.com
   - Camera API reference
   - Webhook event triggers
   - Alarm manager configuration

**Release Notes:**
5. **UniFi Network 9.0 Release Notes** - Official feature announcements
   - Zone-Based Firewall introduction
   - Traffic Flow enhancements
   - SiteMagic SD-WAN features

#### 8.5.2 Community Resources

**API Documentation Projects:**
6. **Art-of-WiFi/UniFi-API-client** (GitHub)
   - Community-maintained API client
   - Extensive endpoint documentation
   - Code examples and patterns

7. **Art-of-WiFi/UniFi-API-browser** (GitHub)
   - Interactive API explorer
   - Endpoint discovery tool
   - Response data structures

8. **Ubiquiti Community Wiki** - https://ubntwiki.com/products/software/unifi-controller/api
   - Community-documented endpoints
   - Unofficial API reference
   - Historical endpoint information

**Community Forums:**
9. **Ubiquiti Community Forums** - https://community.ui.com
   - User discussions and solutions
   - API integration questions
   - Feature requests and feedback

#### 8.5.3 Third-Party Analysis and Guides

**Feature Analysis Articles:**
10. **"UniFi Network 9.0: An Overview"** - iFeelTech
    - Comprehensive feature breakdown
    - Traffic Flow analysis
    - ZBF implementation details

11. **"UniFi Network 9.0: A Detailed Look"** - Seraphim Gate
    - SiteMagic SD-WAN coverage
    - New features deep dive
    - Enterprise deployment considerations

12. **"Ubiquiti Rolls out UniFi Network 9"** - DongKnows
    - Zone-Based Firewall analysis
    - QoS enhancements
    - Practical implementation examples

**Integration Guides:**
13. **"UniFi QoS and Traffic Shaping"** - LazyAdmin
    - QoS configuration tutorials
    - DSCP tagging guides
    - Bandwidth management

14. **"How to Set Up Alerts for UniFi Controller"** - UniHosted
    - Alert configuration guides
    - Notification setup
    - Best practices

15. **"UniFi Hotspot Portal Setup"** - TechExpress
    - Guest portal configuration
    - RADIUS integration
    - Voucher system setup

**Video Tutorials:**
16. **YouTube Technical Walkthroughs**
    - "What Really Changed With UniFi Firewalls in 2025"
    - "New UniFi Software Features & Innovations From Ubiquiti in 2025"
    - "UniFi QoS - How to Optimize Your Network"

#### 8.5.4 Integration-Specific Resources

17. **Home Assistant UniFi Integration** - Community forum discussions
18. **UniFi API Integration Patterns** - MyPlace Connect documentation
19. **LogicMonitor UniFi Monitoring** - Monitoring system integration
20. **Ansible UniFi Modules** - Automation integration patterns

**Total Sources Referenced:** 60+ articles, documentation pages, and community resources

### 8.6 Documentation Maintenance

**Version Control:**
- Documentation versioned alongside code releases
- Changelog documentation for each version
- Deprecation notices for removed features

**Community Contributions:**
- Documentation contribution guidelines
- Example submission process
- Community-contributed tutorials section

**Feedback Loop:**
- Documentation feedback mechanism (GitHub issues)
- Regular documentation reviews based on user questions
- FAQ section updated from common support requests

## 9. Community & Adoption

- **Beta Testing:**
  - A beta testing program will be launched for the new ZBF features.
  - Community feedback will be collected to identify and address any issues.
- **Migration Assistance:**
  - Migration assistance will be provided to help users transition to the new ZBF system.
  - A dedicated support channel will be established for migration-related questions.
- **Feedback Mechanisms:**
  - Community feedback will be collected through GitHub issues, surveys, and community forums.
  - This feedback will be used to inform the future development of the project.
