# UniFi Network API Documentation (v10.2.105)

## Overview

This document provides comprehensive reference documentation for the UniFi Network API version 10.0.160. Each UniFi Application has its own API endpoints running locally on each site, offering detailed analytics and control related to that specific application. For a single endpoint with high-level insights across all your UniFi sites, refer to the [UniFi Site Manager API](https://developer.ui.com/).

## Table of Contents

- [Getting Started](#getting-started)
- [Example Prompts for MCP Interaction](#example-prompts-for-mcp-interaction)
- [Filtering](#filtering)
- [Error Handling](#error-handling)
- [Application Info](#application-info)
- [Sites](#sites)
- [UniFi Devices](#unifi-devices)
- [Clients](#clients)
- [Networks](#networks)
- [WiFi Broadcasts](#wifi-broadcasts)
- [Hotspot](#hotspot)
- [RADIUS & Guest Portal](#radius--guest-portal)
- [Firewall](#firewall)
- [Firewall Policies](#firewall-policies)
- [Access Control (ACL Rules)](#access-control-acl-rules)
- [Switching](#switching)
- [DNS Policies](#dns-policies)
- [Traffic Matching Lists](#traffic-matching-lists)
- [Quality of Service (QoS)](#quality-of-service-qos)
- [Backup and Restore](#backup-and-restore)
- [Site Manager API](#site-manager-api)
- [Supporting Resources](#supporting-resources)

---

## Getting Started

### Introduction

Each UniFi Application has its own API endpoints running locally on each site, offering detailed analytics and control related to that specific application. For a single endpoint with high-level insights across all your UniFi sites, refer to the [UniFi Site Manager API](https://developer.ui.com/).

### Authentication and Request Format

An API Key is a unique identifier used to authenticate API requests. To generate API Keys and view an example of the API Request Format, visit the Integrations section of your UniFi application.

**Authentication Header:**
```
X-API-KEY: {YOUR_API_KEY}
Content-Type: application/json
```

### Base URL

All API endpoints are relative to your UniFi controller:

**Integration API (Recommended):**
```
https://{CONTROLLER_IP}/proxy/network/integration/v1
```

**Local API:**
```
https://{CONTROLLER_IP}/proxy/network/api
```

---

## Example Prompts for MCP Interaction

When using an AI assistant with the UniFi MCP Server, you can use natural language prompts to accomplish complex network management tasks. Here are example prompts organized by category:

### Network Discovery & Monitoring

```
"Show me all offline devices on my network"
"List all clients connected to the Guest WiFi network"
"What devices are connected to the main switch in the living room?"
"Show me devices with firmware updates available"
"Which access points have the highest client load right now?"
"Find all devices with uptime less than 24 hours"
```

### QoS & Traffic Management

```
"Create a QoS profile for Zoom video conferencing with 5 Mbps guaranteed bandwidth"
"Set up a ProAV profile for our Dante audio system in the studio"
"Configure Smart Queue Management on WAN1 for my 100 Mbps connection"
"Create a traffic route to prioritize all UDP port 5060 traffic (SIP/VoIP)"
"Show me all QoS profiles and their current bandwidth allocations"
"Validate if my network can support SMPTE 2110 professional video"
```

### Firewall & Security

```
"Create a firewall rule to block all inbound traffic on port 445 (SMB)"
"Set up a firewall policy to allow VPN traffic from the remote office subnet"
"List all firewall rules that are currently blocking traffic"
"Create a zone-based policy to isolate the IoT network from the main LAN"
"Show me recent traffic flows from the Guest network to the internet"
"Block all traffic from China and Russia to my web server"
```

### WiFi & Guest Access

```
"Create a guest WiFi network with a daily voucher system"
"Generate 10 WiFi vouchers valid for 24 hours with 10 Mbps speed limit"
"List all active guest clients and their bandwidth usage"
"Create a separate SSID for IoT devices with device isolation enabled"
"Show me WiFi channel utilization across all access points"
"Set up a hotspot portal with social media authentication"
```

### Network Configuration

```
"Create a new VLAN 20 for the security cameras with 192.168.20.0/24 subnet"
"Set up a static route to reach the remote office subnet via the VPN gateway"
"Configure port forwarding for SSH (port 22) to my home server at 192.168.2.100"
"Create a DHCP reservation for the printer at 192.168.1.50"
"Show me all networks and their current IP address assignments"
"Set up inter-VLAN routing between the main LAN and the security camera network"
```

### RADIUS & Guest Portal

```
"Create a RADIUS profile for our corporate WiFi using the FreeRADIUS server"
"Set up WPA2-Enterprise authentication with VLAN assignment enabled"
"List all RADIUS user accounts for the guest network"
"Create a RADIUS account for the contractor with 7-day expiration"
"Configure the guest portal with a custom welcome message and company logo"
"Set the guest WiFi session timeout to 4 hours with 5 Mbps download limit"
"Create a hotspot package: 1 hour access for $5 with 1GB data quota"
"Show me all active hotspot packages and their pricing"
"Update the guest portal to require terms of service acceptance"
"Enable redirect to our company website after guest login"
```

### Site Management & Health

```
"Show me the overall health status of all my UniFi sites"
"What's the internet connectivity status for the remote office location?"
"List all sites and their WAN uplink speeds"
"Show me any sites experiencing issues or alerts"
"Compare network performance metrics across all sites"
```

### Backups & Recovery

```
"Create a full backup of my site configuration right now"
"Schedule automatic backups every night at 2 AM"
"List all available backups and their creation dates"
"Restore the site configuration from the backup created on January 15th"
"Validate the integrity of my most recent backup"
```

### Advanced Workflows

```
"Set up a home office network with:
- Main LAN on VLAN 10
- Guest WiFi on VLAN 20 (isolated)
- IoT devices on VLAN 30 (restricted internet only)
- Firewall rules to prevent cross-VLAN traffic
- QoS to prioritize video conferencing"

"Configure a ProAV network for live streaming:
- Dedicated VLAN for NDI devices
- QoS profile with 100 Mbps guaranteed bandwidth
- Multicast support enabled
- Traffic routes to prioritize NDI ports
- Monitoring for packet loss and jitter"

"Implement a secure remote access setup:
- L2TP VPN server with strong encryption
- Firewall rules to allow VPN traffic
- QoS to ensure VPN performance
- Traffic routes to route VPN clients through main gateway
- Monitoring for active VPN connections"
```

### Troubleshooting & Diagnostics

```
"Why is my WiFi so slow in the bedroom? Show me the access point status and client connections"
"Diagnose connectivity issues between the printer and my laptop"
"Show me all firewall rules that might be blocking port 443"
"Which device is consuming the most bandwidth right now?"
"List all clients with poor WiFi signal strength (RSSI below -70 dBm)"
"Find any device that's been disconnecting frequently"
```

### Batch Operations

```
"Reboot all access points in the main building"
"Upgrade firmware on all switches to the latest version"
"Create firewall rules to block the top 10 malicious IP addresses"
"Generate 100 guest vouchers for the conference next week"
"Apply the 'Video Conference' QoS profile to all Zoom traffic"
```

### Best Practices for Effective Prompts

1. **Be Specific**: Include exact values (IP addresses, port numbers, VLAN IDs)
2. **Use Context**: Reference existing configurations ("the Guest WiFi", "my main switch")
3. **Request Confirmation**: Ask the AI to explain changes before applying them
4. **Combine Operations**: Chain related tasks in a single conversational flow
5. **Ask for Validation**: Request health checks or impact analysis before major changes
6. **Leverage Dry-Run**: Ask the AI to show what would happen without actually making changes

**Example Multi-Step Conversation:**

```
User: "I need to set up QoS for my Zoom calls. What do you recommend?"

AI: "I recommend creating a QoS profile with priority level 5, DSCP marking 34 (AF41),
     and guaranteed bandwidth of 5 Mbps down / 2 Mbps up. This ensures high-quality
     video even during network congestion. Would you like me to create this?"

User: "Yes, but first show me what the configuration would look like in dry-run mode."

AI: [Shows dry-run output with exact configuration values]

User: "Perfect, go ahead and create it. Also, create a traffic route to apply this
      QoS profile to all UDP traffic on port 8801 (Zoom media)."

AI: [Creates QoS profile and traffic route, confirms success]

User: "Now validate that this is working correctly."

AI: [Shows active traffic flows with DSCP marking applied, confirms QoS is active]
```

---

## Filtering

Explains how to use the filter query parameter for advanced querying across list endpoints.

Some `GET` and `DELETE` endpoints support filtering using the `filter` query parameter. Each endpoint supporting filtering will have a detailed list of filterable properties, their types, and allowed functions.

### Filtering Syntax

Filtering follows a structured, URL-safe syntax with three types of expressions.

#### 1. Property Expressions

Apply functions to an individual property using the form `<property>.<function>(<arguments>)`, where argument values are separated by commas.

**Examples:**
- `id.eq(123)` - checks if `id` is equal to `123`
- `name.isNotNull()` - checks if `name` is not null
- `createdAt.in(2025-01-01, 2025-01-05)` - checks if `createdAt` is either `2025-01-01` or `2025-01-05`

#### 2. Compound Expressions

Combine two or more expressions with logical operators using the form `<logical-operator>(<expressions>)`, where expressions are separated by commas.

**Examples:**
- `and(name.isNull(), createdAt.gt(2025-01-01))` - checks if `name` is null **and** `createdAt` is greater than `2025-01-01`
- `or(name.isNull(), expired.isNull(), expiresAt.isNull())` - checks if **any** of `name`, `expired`, or `expiresAt` is null

#### 3. Negation Expressions

Negate any other expressions using the form `not(<expression>)`.

**Example:**
- `not(name.like('guest*'))` - matches all values except those that start with `guest`

### Filterable Property Types

| Type | Examples | Syntax |
|------|----------|--------|
| `STRING` | `'Hello, ''World''!'` | Must be wrapped in single quotes. To escape a single quote, use another single quote. |
| `INTEGER` | `123` | Must start with a digit. |
| `DECIMAL` | `123`, `123.321` | Must start with a digit. Can include a decimal point (.). |
| `TIMESTAMP` | `2025-01-29`, `2025-01-29T12:39:11Z` | Must follow ISO 8601 format (date or date-time). |
| `BOOLEAN` | `true`, `false` | Can be `true` or `false`. |
| `UUID` | `550e8400-e29b-41d4-a716-446655440000` | Must be a valid UUID format (8-4-4-4-12). |
| `SET(STRING\|INTEGER\|DECIMAL\|TIMESTAMP\|UUID)` | `[1, 2, 3, 4, 5]` | A set of (unique) values. |

### Filtering Functions

| Function | Arguments | Semantics | Supported Property Types |
|----------|-----------|-----------|--------------------------|
| `isNull` | 0 | is null | all types |
| `isNotNull` | 0 | is not null | all types |
| `eq` | 1 | equals | STRING, INTEGER, DECIMAL, TIMESTAMP, BOOLEAN, UUID |
| `ne` | 1 | not equals | STRING, INTEGER, DECIMAL, TIMESTAMP, BOOLEAN, UUID |
| `gt` | 1 | greater than | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `ge` | 1 | greater than or equals | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `lt` | 1 | less than | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `le` | 1 | less than or equals | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `like` | 1 | matches pattern | STRING |
| `in` | 1 or more | one of | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `notIn` | 1 or more | not one of | STRING, INTEGER, DECIMAL, TIMESTAMP, UUID |
| `isEmpty` | 0 | is empty | SET |
| `contains` | 1 | contains | SET |
| `containsAny` | 1 or more | contains any of | SET |
| `containsAll` | 1 or more | contains all of | SET |
| `containsExactly` | 1 or more | contains exactly | SET |

#### Pattern Matching (`like` Function)

- `.` matches any **single** character. Example: `type.like('type.')` matches `type1`, but not `type100`
- `*` matches **any number** of characters. Example: `name.like('guest*')` matches `guest1` and `guest100`
- `\` is used to escape `.` and `*`

---

## Error Handling

Describes the standard API error response structure.

### Error Message Schema

| Field | Type | Description |
|-------|------|-------------|
| `statusCode` | integer (int32) | HTTP status code |
| `statusName` | string | Status name (e.g., UNAUTHORIZED) |
| `code` | string | Error code (e.g., api.authentication.missing-credentials) |
| `message` | string | Human-readable error message |
| `timestamp` | string (date-time) | ISO 8601 timestamp |
| `requestPath` | string | The request path |
| `requestId` | string (uuid) | Request ID for tracking (useful for 500 errors) |

**Example Response:**
```json
{
  "statusCode": 400,
  "statusName": "UNAUTHORIZED",
  "code": "api.authentication.missing-credentials",
  "message": "Missing credentials",
  "timestamp": "2024-11-27T08:13:46.966Z",
  "requestPath": "/integration/v1/sites/123",
  "requestId": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

---

## Application Info

Returns general details about the UniFi Network application.

### Get Application Info

Retrieve general information about the UniFi Network application.

- **Method:** `GET`
- **Endpoint:** `/v1/info`
- **Response:** `200 OK`

**Example Response:**
```json
{
  "applicationVersion": "9.1.0"
}
```

---

## Sites

Endpoints for listing and managing UniFi sites. Site ID is required for most other API requests.

### List Local Sites

Retrieve a paginated list of local sites managed by this Network application.

- **Method:** `GET`
- **Endpoint:** `/v1/sites`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `offset` | number (int32) | 0 | Pagination offset (>= 0) |
| `limit` | number (int32) | 25 | Pagination limit (0-200) |
| `filter` | string | - | Filter expression |

**Response:** `200 OK`

```json
{
  "offset": 0,
  "limit": 25,
  "count": 2,
  "totalCount": 2,
  "data": [
    {
      "id": "default",
      "name": "Default",
      "description": "Default site"
    }
  ]
}
```

---

## UniFi Devices

Endpoints to list, inspect, and interact with UniFi devices.

### List Devices Pending Adoption

- **Method:** `GET`
- **Endpoint:** `/v1/pending-devices`

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### List Adopted Devices

Retrieve a paginated list of all adopted devices on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/devices`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### Adopt Device

Adopt a device to a site.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/devices`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `macAddress` | string | Yes | MAC address of the device to adopt |
| `ignoreDeviceLimit` | boolean | Yes | Whether to ignore device limit |

**Example Request:**
```json
{
  "macAddress": "00:1A:2B:3C:4D:5E",
  "ignoreDeviceLimit": true
}
```

**Response:** `200 OK`

Returns device details including IDs, MAC/IP, firmware, features, and interface lists.

### Get Adopted Device Details

Retrieve detailed information about a specific adopted device.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/devices/{deviceId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |
| `deviceId` | string (uuid) | Yes |

**Response:** `200 OK`

**Response Fields:**
- `id`, `macAddress`, `ipAddress`, `name`, `model`, `supported`, `state`
- `firmwareVersion`, `firmwareUpdatable`
- `adoptedAt`, `provisionedAt`
- `configurationId`, `uplink.deviceId`
- `features.switching`, `features.accessPoint`
- `interfaces.ports[...]`, `interfaces.radios[...]`

### Get Latest Adopted Device Statistics

Retrieve real-time statistics including uptime, CPU, memory utilization.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/devices/{deviceId}/statistics/latest`

**Response:** `200 OK`

```json
{
  "uptimeSec": 86400,
  "lastHeartbeatAt": "2025-11-26T12:00:00Z",
  "nextHeartbeatAt": "2025-11-26T12:05:00Z",
  "loadAverage1Min": 0.5,
  "loadAverage5Min": 0.4,
  "loadAverage15Min": 0.3,
  "cpuUtilizationPct": 15.5,
  "memoryUtilizationPct": 45.2,
  "uplink": {
    "txRateBps": 1000000,
    "rxRateBps": 500000
  }
}
```

### Execute Adopted Device Action

Perform an action on a specific adopted device.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/devices/{deviceId}/actions`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |
| `deviceId` | string (uuid) | Yes |

**Request Body:**

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `action` | string | Yes | `RESTART` |

**Response:** `200 OK`

### Execute Port Action

Perform an action on a specific device port.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/devices/{deviceId}/interfaces/ports/{portIdx}/actions`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `portIdx` | integer (int32) | Yes |
| `siteId` | string (uuid) | Yes |
| `deviceId` | string (uuid) | Yes |

**Request Body:**

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `action` | string | Yes | `POWER_CYCLE` |

**Response:** `200 OK`

### Remove (Unadopt) Device

Removes (unadopts) an adopted device from the site. If the device is online, it will be reset to factory defaults.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/devices/{deviceId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |
| `deviceId` | string (uuid) | Yes |

**Response:** `200 OK`

---

## Clients

Endpoints for viewing and managing connected clients (wired, wireless, VPN, and guest).

### List Connected Clients

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/clients`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### Get Connected Client Details

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/clients/{clientId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `clientId` | string (uuid) | Yes |
| `siteId` | string (uuid) | Yes |

**Response:** `200 OK`

**Response Fields:**
- `type` – one of `WIRED`, `WIRELESS`, `VPN`, `TELEPORT`
- `id`, `name`, `connectedAt`
- `ipAddress`, `macAddress`
- `access.type`
- `uplinkDeviceId`

### Execute Client Action

Perform an action on a specific connected client.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/clients/{clientId}/actions`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | string | Yes | `AUTHORIZE_GUEST_ACCESS` or `UNAUTHORIZE_GUEST_ACCESS` |
| `timeLimitMinutes` | integer (int64) | No | Guest authorization time limit (1-1000000 minutes) |
| `dataUsageLimitMBytes` | integer (int64) | No | Data usage limit (1-1048576 MB) |
| `rxRateLimitKbps` | integer (int64) | No | Download rate limit (2-100000 Kbps) |
| `txRateLimitKbps` | integer (int64) | No | Upload rate limit (2-100000 Kbps) |

**Response:** `200 OK`

---

## Networks

Endpoints for creating, updating, deleting, and inspecting network configurations including VLANs, DHCP, NAT, and IPv4/IPv6 settings.

> **API Limitations (verified 2026-04-13):**
> - The v1 Network API only exposes `management`, `name`, `enabled`, `vlanId`, and `dhcpGuarding`. DHCP range, subnet, purpose, and isolation settings are NOT available through the v1 API.
> - The legacy REST API (`/rest/networkconf`) exposes more fields (DHCP, subnet, purpose) but `purpose` is **immutable after creation**.
> - **Network-level client isolation** ("Isolate Network" in the UI) is not available through any documented API. Use `clientIsolationEnabled` on WiFi Broadcasts for SSID-level isolation instead.
> - The legacy REST API uses `"vlan"` (not `"vlan_id"`) for the VLAN number field.

### List Networks

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/networks`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### Create Network

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/networks`
- **Response:** `201 Created`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `management` | string | Yes | `UNMANAGED`, `GATEWAY`, or `SWITCH` |
| `name` | string | Yes | Network name |
| `enabled` | boolean | Yes | Enable/disable |
| `vlanId` | integer (int32) | Yes | VLAN ID (2-4000) |
| `dhcpGuarding` | object | No | DHCP Guarding settings |

### Get Network Details

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/networks/{networkId}`

**Response:** `200 OK`

**Response Fields:**
- `management` – `UNMANAGED`, `GATEWAY`, or `SWITCH`
- `id`, `name`, `enabled`
- `vlanId` (2–4000)
- `metadata.origin`
- `dhcpGuarding.trustedDhcpServerIpAddresses[...]`

### Update Network

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/networks/{networkId}`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `management` | string | Yes | `UNMANAGED`, `GATEWAY`, or `SWITCH` |
| `name` | string | Yes | Network name (non-empty) |
| `enabled` | boolean | Yes | Enable/disable |
| `vlanId` | integer | Yes | VLAN ID (2-4000) |
| `dhcpGuarding` | object | No | DHCP Guarding settings (null to disable) |

**Response:** `200 OK`

### Delete Network

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/networks/{networkId}`

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `cascade` | boolean | false |
| `force` | boolean | false |

**Response:** `200 OK`

### Get Network References

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/networks/{networkId}/references`

**Response:** `200 OK`

```json
{
  "referenceResources": [
    {
      ...
    }
  ]
}
```

---

## WiFi Broadcasts

Endpoints to create, update, or remove WiFi networks (SSIDs). Supports configuration of security, band steering, multicast filtering, and captive portals.

### List Wifi Broadcasts

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/wifi/broadcasts`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### Create Wifi Broadcast

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/wifi/broadcasts`
- **Response:** `201 Created`

**Request Body Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | `STANDARD` or `IOT_OPTIMIZED` |
| `name` | string | Yes | WiFi broadcast name |
| `enabled` | boolean | Yes | Enable/disable broadcast |
| `network` | object | No | WiFi network reference |
| `securityConfiguration` | object | Yes | WiFi security configuration detail |
| `broadcastingDeviceFilter` | object | No | Custom scope of devices that will broadcast. If null, all AP-capable devices broadcast. |
| `mdnsProxyConfiguration` | object | No | mDNS filtering configuration |
| `multicastFilteringPolicy` | object | No | Multicast filtering policy |
| `multicastToUnicastConversionEnabled` | boolean | Yes | Enable multicast to unicast conversion |
| `clientIsolationEnabled` | boolean | Yes | Enable client isolation |
| `hideName` | boolean | Yes | Hide SSID |
| `uapsdEnabled` | boolean | Yes | Enable Unscheduled Automatic Power Save Delivery (U-APSD) |
| `basicDataRateKbpsByFrequencyGHz` | object | No | Basic data rates by frequency (e.g., `{"5":6000,"2.4":2000}`) |
| `clientFilteringPolicy` | object | No | Client connection filtering policy (allow/restrict by MAC) |
| `blackoutScheduleConfiguration` | object | No | Blackout schedule configuration |
| `broadcastingFrequenciesGHz` | array | Yes | Unique items: `2.4`, `5`, `6` |
| `hotspotConfiguration` | object | No | WiFi hotspot configuration |
| `mloEnabled` | boolean | No | Enable MLO |
| `bandSteeringEnabled` | boolean | No | Enable band steering |
| `arpProxyEnabled` | boolean | Yes | Enable ARP proxy |
| `bssTransitionEnabled` | boolean | Yes | Enable BSS transition |
| `advertiseDeviceName` | boolean | Yes | Advertise device name in beacon frames |
| `dtimPeriodByFrequencyGHzOverride` | object | No | DTIM period configuration by frequency |

### Get Wifi Broadcast Details

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/wifi/broadcasts/{wifiBroadcastId}`

**Response:** `200 OK`

**Response Fields:**
- `type` – `STANDARD` or `IOT_OPTIMIZED`
- `id`, `name`, `enabled`
- `metadata.origin`
- `network.type`
- `securityConfiguration.type`, `securityConfiguration.radiusConfiguration`
- `broadcastingDeviceFilter.type`
- `mdnsProxyConfiguration.mode`
- `multicastFilteringPolicy.action`
- `multicastToUnicastConversionEnabled`
- `clientIsolationEnabled`
- `hideName`, `uapsdEnabled`
- `basicDataRateKbpsByFrequencyGHz`
- `clientFilteringPolicy.action`, `clientFilteringPolicy.macAddressFilter[...]`
- `blackoutScheduleConfiguration.days[...]`
- `broadcastingFrequenciesGHz`
- `hotspotConfiguration.type`
- `mloEnabled`, `bandSteeringEnabled`, `arpProxyEnabled`, `bssTransitionEnabled`, `advertiseDeviceName`
- `dtimPeriodByFrequencyGHzOverride`

### Update Wifi Broadcast

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/wifi/broadcasts/{wifiBroadcastId}`

**Request Body:** Same schema as Create Wifi Broadcast.

**Response:** `200 OK`

### Delete Wifi Broadcast

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/wifi/broadcasts/{wifiBroadcastId}`

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `force` | boolean | false |

**Response:** `200 OK`

---

## Hotspot

Endpoints for managing guest access via Hotspot vouchers.

### List Vouchers

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/hotspot/vouchers`

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 100 (max 1000) |
| `filter` | string | - |

**Response:** `200 OK`

### Generate Vouchers

Create one or more Hotspot vouchers.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/hotspot/vouchers`
- **Response:** `201 Created`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `count` | integer (int32) | No | Number of vouchers to generate (1-1000), Default: 1 |
| `name` | string | Yes | Voucher note, duplicated across all generated vouchers |
| `authorizedGuestLimit` | integer (int64) | No | Limit for how many different guests can use the same voucher (>= 1) |
| `timeLimitMinutes` | integer (int64) | Yes | How long (in minutes) the voucher provides access (1-1000000) |
| `dataUsageLimitMBytes` | integer (int64) | No | Data usage limit in megabytes (1-1048576) |
| `rxRateLimitKbps` | integer (int64) | No | Download rate limit in kilobits per second (2-100000) |
| `txRateLimitKbps` | integer (int64) | No | Upload rate limit in kilobits per second (2-100000) |

### Delete Vouchers

Remove Hotspot vouchers based on the specified filter criteria.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/hotspot/vouchers`

**Query Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `filter` | string | Yes |

**Response:** `200 OK`

```json
{
  "vouchersDeleted": 5
}
```

### Get Voucher Details

Retrieve details of a specific Hotspot voucher.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/hotspot/vouchers/{voucherId}`

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (uuid) | Voucher ID |
| `createdAt` | string (date-time) | Creation timestamp |
| `name` | string | Voucher note |
| `code` | integer | Voucher code |
| `authorizedGuestLimit` | integer | Max guests allowed |
| `authorizedGuestCount` | integer | Current guests using voucher |
| `activatedAt` | string (date-time) | Activation timestamp |
| `expiresAt` | string (date-time) | Expiration timestamp |
| `expired` | boolean | Expiration status |
| `timeLimitMinutes` | integer | Time limit in minutes |
| `dataUsageLimitMBytes` | integer | Data limit in MB |
| `rxRateLimitKbps` | integer | Download rate limit |
| `txRateLimitKbps` | integer | Upload rate limit |

### Delete Voucher

Remove a specific Hotspot voucher.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/hotspot/vouchers/{voucherId}`

**Response:** `200 OK`

---

## RADIUS & Guest Portal

Endpoints for managing RADIUS authentication profiles, guest portal configuration, and hotspot packages.

### RADIUS Profile Management

#### List RADIUS Profiles

List all RADIUS authentication profiles for a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/radius/profiles`
- **Response:** `200 OK`

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | RADIUS profile ID |
| `name` | string | Profile name |
| `auth_server` | string | Authentication server IP/hostname |
| `auth_port` | integer | Authentication port (default: 1812) |
| `acct_server` | string | Accounting server IP/hostname |
| `acct_port` | integer | Accounting port (default: 1813) |
| `vlan_enabled` | boolean | VLAN assignment enabled |
| `enabled` | boolean | Profile is active |

#### Get RADIUS Profile

Retrieve a specific RADIUS profile.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/radius/profiles/{profileId}`
- **Response:** `200 OK`

#### Create RADIUS Profile

Create a new RADIUS authentication profile for WPA2-Enterprise.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/radius/profiles`
- **Response:** `201 Created`
- **Requires Confirmation:** `confirm=true`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Profile name |
| `auth_server` | string | Yes | Authentication server IP/hostname |
| `auth_port` | integer | No | Authentication port (default: 1812) |
| `auth_secret` | string | Yes | Shared secret for authentication |
| `acct_server` | string | No | Accounting server IP/hostname |
| `acct_port` | integer | No | Accounting port (default: 1813) |
| `acct_secret` | string | No | Shared secret for accounting |
| `use_same_secret` | boolean | No | Use auth_secret for accounting (default: true) |
| `vlan_enabled` | boolean | No | Enable VLAN assignment (default: false) |
| `vlan_wlan_mode` | string | No | VLAN mode for WLAN |
| `interim_update_interval` | integer | No | Accounting update interval in seconds |

**Example Request:**

```json
{
  "name": "Corporate RADIUS",
  "auth_server": "radius.example.com",
  "auth_port": 1812,
  "auth_secret": "supersecret",
  "acct_port": 1813,
  "vlan_enabled": true
}
```

#### Update RADIUS Profile

Modify an existing RADIUS profile.

- **Method:** `PATCH`
- **Endpoint:** `/v1/sites/{siteId}/radius/profiles/{profileId}`
- **Response:** `200 OK`
- **Requires Confirmation:** `confirm=true`

#### Delete RADIUS Profile

Remove a RADIUS profile.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/radius/profiles/{profileId}`
- **Response:** `200 OK`
- **Requires Confirmation:** `confirm=true`

### RADIUS Account Management

#### List RADIUS Accounts

List all RADIUS user accounts (passwords redacted).

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/radius/accounts`
- **Response:** `200 OK`

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Account ID |
| `name` | string | Username |
| `password` | string | ***REDACTED*** |
| `enabled` | boolean | Account is active |
| `vlan_id` | integer | Assigned VLAN ID |
| `start_time` | integer | Activation timestamp (Unix) |
| `end_time` | integer | Expiration timestamp (Unix) |

#### Create RADIUS Account

Create a new RADIUS user account for guest access.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/radius/accounts`
- **Response:** `201 Created`
- **Requires Confirmation:** `confirm=true`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Username |
| `password` | string | Yes | Password |
| `enabled` | boolean | No | Account enabled (default: true) |
| `vlan_id` | integer | No | Assigned VLAN ID |
| `start_time` | integer | No | Activation timestamp (Unix) |
| `end_time` | integer | No | Expiration timestamp (Unix) |
| `tunnel_type` | integer | No | RADIUS tunnel type |
| `tunnel_medium_type` | integer | No | RADIUS tunnel medium type |

#### Delete RADIUS Account

Remove a RADIUS user account.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/radius/accounts/{accountId}`
- **Response:** `200 OK`
- **Requires Confirmation:** `confirm=true`

### Guest Portal Configuration

#### Get Guest Portal Config

Retrieve the current guest portal configuration.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/guest-portal/config`
- **Response:** `200 OK`

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Guest portal enabled |
| `portal_title` | string | Portal page title |
| `auth_method` | string | Authentication method (none/password/voucher/radius/external) |
| `session_timeout` | integer | Session timeout in minutes (0=unlimited) |
| `redirect_enabled` | boolean | Redirect after authentication |
| `redirect_url` | string | Redirect URL |
| `terms_of_service_enabled` | boolean | Require ToS acceptance |
| `download_limit_kbps` | integer | Download speed limit in kbps |
| `upload_limit_kbps` | integer | Upload speed limit in kbps |

#### Configure Guest Portal

Customize guest portal settings.

- **Method:** `PATCH`
- **Endpoint:** `/v1/sites/{siteId}/guest-portal/config`
- **Response:** `200 OK`
- **Requires Confirmation:** `confirm=true`

**Request Body (all fields optional):**

| Field | Type | Description |
|-------|------|-------------|
| `portal_title` | string | Portal page title |
| `auth_method` | string | Authentication method |
| `password` | string | Portal password (if auth_method=password) |
| `session_timeout` | integer | Session timeout in minutes |
| `redirect_enabled` | boolean | Enable redirect after auth |
| `redirect_url` | string | Redirect URL |
| `terms_of_service_enabled` | boolean | Require ToS acceptance |
| `terms_of_service_text` | string | Terms of service text |
| `download_limit_kbps` | integer | Download speed limit |
| `upload_limit_kbps` | integer | Upload speed limit |
| `background_image_url` | string | Background image URL |
| `logo_url` | string | Logo image URL |

### Hotspot Package Management

#### List Hotspot Packages

List all available hotspot packages with time and bandwidth limits.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/hotspot/packages`
- **Response:** `200 OK`

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Package ID |
| `name` | string | Package name |
| `duration_minutes` | integer | Duration in minutes |
| `download_limit_kbps` | integer | Download speed limit in kbps |
| `upload_limit_kbps` | integer | Upload speed limit in kbps |
| `download_quota_mb` | integer | Download quota in MB |
| `upload_quota_mb` | integer | Upload quota in MB |
| `price` | float | Package price |
| `currency` | string | Currency code |
| `enabled` | boolean | Package is available |

#### Create Hotspot Package

Create a new hotspot package with pricing.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/hotspot/packages`
- **Response:** `201 Created`
- **Requires Confirmation:** `confirm=true`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Package name |
| `duration_minutes` | integer | Yes | Duration in minutes |
| `download_limit_kbps` | integer | No | Download speed limit in kbps |
| `upload_limit_kbps` | integer | No | Upload speed limit in kbps |
| `download_quota_mb` | integer | No | Download quota in MB |
| `upload_quota_mb` | integer | No | Upload quota in MB |
| `price` | float | No | Package price |
| `currency` | string | No | Currency code (default: USD) |

**Example Request:**

```json
{
  "name": "1 Hour Premium",
  "duration_minutes": 60,
  "download_limit_kbps": 10000,
  "upload_limit_kbps": 5000,
  "download_quota_mb": 500,
  "price": 5.99,
  "currency": "USD"
}
```

#### Delete Hotspot Package

Remove a hotspot package.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/hotspot/packages/{packageId}`
- **Response:** `200 OK`
- **Requires Confirmation:** `confirm=true`

---

## Firewall

Endpoints for managing custom firewall zones within a site.

### List Firewall Zones

Retrieve a list of all firewall zones on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/firewall/zones`

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### Create Custom Firewall Zone

Create a new custom firewall zone on a site.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/firewall/zones`
- **Response:** `201 Created`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Name of firewall zone |
| `networkIds` | array | Yes | List of Network IDs (UUIDs) |

**Example Request:**
```json
{
  "name": "My custom zone",
  "networkIds": ["dfb21062-8ea0-4dca-b1d8-1eb3da00e58b"]
}
```

### Get Firewall Zone

Get a firewall zone on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/firewall/zones/{firewallZoneId}`

**Response Fields:**

| Field | Type |
|-------|------|
| `id` | string (uuid) |
| `name` | string |
| `networkIds` | array of strings (uuid) |
| `metadata.origin` | string |

### Update Firewall Zone

Update a firewall zone on a site.

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/firewall/zones/{firewallZoneId}`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Name of firewall zone |
| `networkIds` | array | Yes | List of Network IDs (>= 0 items) |

**Response:** `200 OK`

### Delete Custom Firewall Zone

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/firewall/zones/{firewallZoneId}`

**Response:** `200 OK`

---

## Firewall Policies

Endpoints for managing firewall policies within a site. Define or update network segmentation and security boundaries.

### List Firewall Policies

Retrieve a list of all firewall policies on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/firewall/policies`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### Create Firewall Policy

Create a new firewall policy on a site.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/firewall/policies`
- **Response:** `201 Created`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | boolean | Yes | Enable/disable policy |
| `name` | string | Yes | Policy name (non-empty) |
| `description` | string | No | Policy description |
| `action` | object | Yes | Defines action for matched traffic |
| `source` | object | Yes | Firewall policy source |
| `destination` | object | Yes | Firewall policy destination |
| `ipProtocolScope` | object | Yes | Defines rules for matching by IP version and protocol |
| `connectionStateFilter` | array | No | Match on firewall connection state. Values: `NEW`, `INVALID`, `ESTABLISHED`, `RELATED`. If null, matches all. |
| `ipsecFilter` | string | No | Match on traffic encrypted or not encrypted by IPsec. Values: `MATCH_ENCRYPTED`, `MATCH_NOT_ENCRYPTED`. If null, matches all. |
| `loggingEnabled` | boolean | Yes | Generate syslog entries when traffic is matched |
| `schedule` | object | No | Defines date and time when the entity is active. If null, the entity is always active. |

**Response:** Returns created policy with all fields including `id`, `index`, and `metadata`.

### Get Firewall Policy

Retrieve specific firewall policy.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/firewall/policies/{firewallPolicyId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `firewallPolicyId` | string (uuid) | Yes |
| `siteId` | string (uuid) | Yes |

**Response:** `200 OK`

**Response Fields:**
- `id`, `enabled`, `name`, `description`, `index`
- `action.type`
- `source.firewallZoneId`, `source.trafficFilter`
- `destination.firewallZoneId`, `destination.trafficFilter`
- `ipProtocolScope.ipVersion`
- `connectionStateFilter` (array: `NEW`, `INVALID`, `ESTABLISHED`, `RELATED`)
- `ipsecFilter` (`MATCH_ENCRYPTED`, `MATCH_NOT_ENCRYPTED`)
- `loggingEnabled`
- `schedule.mode`
- `metadata.origin`

### Update Firewall Policy

Update an existing firewall policy on a site.

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/firewall/policies/{firewallPolicyId}`

**Request Body:** Same schema as Create Firewall Policy.

**Response:** `200 OK`

### Patch Firewall Policy

Patch an existing firewall policy on a site.

- **Method:** `PATCH`
- **Endpoint:** `/v1/sites/{siteId}/firewall/policies/{firewallPolicyId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `firewallPolicyId` | string (uuid) | Yes |
| `siteId` | string (uuid) | Yes |

**Request Body:**

Partial policy object with only the fields to update.

**Example Request:**
```json
{
  "loggingEnabled": true
}
```

**Response:** `200 OK`

### Delete Firewall Policy

Delete an existing firewall policy on a site.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/firewall/policies/{firewallPolicyId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `firewallPolicyId` | string (uuid) | Yes |
| `siteId` | string (uuid) | Yes |

**Response:** `200 OK`

### Get User-Defined Firewall Policy Ordering

Retrieve user-defined firewall policy ordering for a specific source/destination zone pair.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/firewall/policies/ordering`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `sourceFirewallZoneId` | string (uuid) | Yes |
| `destinationFirewallZoneId` | string (uuid) | Yes |

**Response:** `200 OK`

```json
{
  "orderedFirewallPolicyIds": {
    "beforeSystemDefined": [...],
    "afterSystemDefined": [...]
  }
}
```

### Reorder User-Defined Firewall Policies

Reorder user-defined firewall policies for a specific source/destination zone pair.

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/firewall/policies/ordering`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `sourceFirewallZoneId` | string (uuid) | Yes |
| `destinationFirewallZoneId` | string (uuid) | Yes |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `orderedFirewallPolicyIds` | object | Yes | Ordered firewall policy IDs |

**Example Request:**
```json
{
  "orderedFirewallPolicyIds": {
    "beforeSystemDefined": [...],
    "afterSystemDefined": [...]
  }
}
```

**Response:** `200 OK`

---

## Access Control (ACL Rules)

Endpoints for creating, listing, and managing ACL rules that enforce traffic filtering across devices and networks.

### List ACL Rules

Retrieve a paginated list of all ACL rules on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/acl-rules`

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### Create ACL Rule

Create a new user defined ACL rule.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/acl-rules`
- **Response:** `201 Created`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | `IPV4` or `MAC` |
| `enabled` | boolean | Yes | Enable/disable rule |
| `name` | string | Yes | ACL rule name (non-empty) |
| `description` | string | No | ACL rule description |
| `action` | string | Yes | `ALLOW` or `BLOCK` |
| `enforcingDeviceFilter` | object | No | IDs of Switch-capable devices to enforce. When null, rule applies to all switches. |
| `index` | integer (int32) | Yes | Rule priority (>= 0, lower = higher priority). **Deprecated:** Use ACL rule reordering endpoint. |
| `sourceFilter` | object | No | Traffic source filter |
| `destinationFilter` | object | No | Traffic destination filter |
| `protocolFilter` | array | No | Protocols (`TCP`, `UDP`), null = all |

### Get ACL Rule

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/acl-rules/{aclRuleId}`

**Response Fields:**

| Field | Type |
|-------|------|
| `type` | string (`IPV4` or `MAC`) |
| `id` | string (uuid) |
| `enabled` | boolean |
| `name` | string |
| `description` | string |
| `action` | string (`ALLOW` or `BLOCK`) |
| `enforcingDeviceFilter` | object |
| `index` | integer |
| `sourceFilter` | object |
| `destinationFilter` | object |
| `metadata.origin` | string |
| `protocolFilter` | array (`TCP`, `UDP`) |

### Update ACL Rule

Update an existing user defined ACL rule.

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/acl-rules/{aclRuleId}`

**Request Body:** Same schema as Create ACL Rule.

**Response:** `200 OK`

### Delete ACL Rule

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/acl-rules/{aclRuleId}`

**Response:** `200 OK`

### Get User-Defined ACL Rule Ordering

Retrieve user-defined ACL rule ordering on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/acl-rules/ordering`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Response:** `200 OK`

```json
{
  "orderedAclRuleIds": ["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
}
```

### Reorder User-Defined ACL Rules

Reorder user-defined ACL rules on a site.

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/acl-rules/ordering`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `orderedAclRuleIds` | array | Yes | Array of ACL rule IDs (UUIDs) in desired order |

**Example Request:**
```json
{
  "orderedAclRuleIds": ["497f6eca-6276-4993-bfeb-53cbbbba6f08"]
}
```

**Response:** `200 OK`

---

## Switching

Endpoints for managing switching features like Switch Stacking and LAG (Link Aggregation Groups).

### List Switch Stacks

Retrieve a paginated list of all Switch Stacks on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/switching/switch-stacks`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | integer (int32) | 0 |
| `limit` | integer (int32) | 25 |
| `filter` | string | - |

**Response:** `200 OK` — paginated list

### Get Switch Stack

Retrieve Switch Stack details.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/switching/switch-stacks/{switchStackId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |
| `switchStackId` | string (uuid) | Yes |

**Response:** `200 OK`

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "name": "string",
  "members": [{}, {}],
  "lags": [{}],
  "metadata": {
    "origin": "string"
  }
}
```

### List MC-LAG Domains

Retrieve a paginated list of all MC-LAG Domains on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/switching/mc-lag-domains`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | integer (int32) | 0 |
| `limit` | integer (int32) | 25 |
| `filter` | string | - |

**Response:** `200 OK` — paginated list

### Get MC-LAG Domain

Retrieve MC-LAG Domain details.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/switching/mc-lag-domains/{mcLagDomainId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |
| `mcLagDomainId` | string (uuid) | Yes |

**Response:** `200 OK`

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "name": "string",
  "peers": [{}],
  "lags": [{}],
  "metadata": {
    "origin": "string"
  }
}
```

### List LAGs

Retrieve a paginated list of all LAGs (Link Aggregation Groups) on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/switching/lags`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | integer (int32) | 0 |
| `limit` | integer (int32) | 25 |
| `filter` | string | - |

**Response:** `200 OK` — paginated list

### Get LAG Details

Retrieve LAG details.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/switching/lags/{lagId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |
| `lagId` | string (uuid) | Yes |

**Response:** `200 OK`

```json
{
  "type": "SWITCH_STACK",
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "members": [{}],
  "switchStackId": "bd2c5532-16a4-4f97-91d1-09f6ed6a3b97"
}
```

---

## DNS Policies

Endpoints for managing DNS Policies within a site. Supports A, AAAA, CNAME, MX, TXT, SRV records, and domain forwarding.

### List DNS Policies

Retrieve a paginated list of all DNS policies on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/dns/policies`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### Create DNS Policy

Create a new DNS policy on a site.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/dns/policies`
- **Response:** `201 Created`

**Request Body (A_RECORD example):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Record type (see supported types below) |
| `enabled` | boolean | Yes | Enable/disable policy |
| `domain` | string | Yes | Domain name (1-127 chars) |
| `ipv4Address` | string | Yes* | IPv4 address (*for A_RECORD type) |
| `ttlSeconds` | integer | Yes | Time to live in seconds (0-604800) |

**Supported Types:** `A_RECORD`, `AAAA_RECORD`, `CNAME_RECORD`, `MX_RECORD`, `TXT_RECORD`, `SRV_RECORD`, `FORWARD_DOMAIN`

**Example Request (A_RECORD):**
```json
{
  "type": "A_RECORD",
  "enabled": true,
  "domain": "example.com",
  "ipv4Address": "192.168.2.10",
  "ttlSeconds": 14400
}
```

**Response:** Returns created DNS policy with `id`.

### Get DNS Policy

Retrieve specific DNS policy.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/dns/policies/{dnsPolicyId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `dnsPolicyId` | string (uuid) | Yes |
| `siteId` | string (uuid) | Yes |

**Response:** `200 OK`

**Example Response (A_RECORD):**
```json
{
  "type": "A_RECORD",
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "enabled": true,
  "domain": "example.com",
  "ipv4Address": "192.168.2.10",
  "ttlSeconds": 14400
}
```

### Update DNS Policy

Update an existing DNS policy on a site.

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/dns/policies/{dnsPolicyId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `dnsPolicyId` | string (uuid) | Yes |
| `siteId` | string (uuid) | Yes |

**Request Body:** Same schema as Create DNS Policy for the appropriate record type.

**Response:** `200 OK`

### Delete DNS Policy

Delete an existing DNS policy on a site.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/dns/policies/{dnsPolicyId}`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `dnsPolicyId` | string (uuid) | Yes |
| `siteId` | string (uuid) | Yes |

**Response:** `200 OK`

---

## Traffic Matching Lists

Endpoints for managing port and IP address lists used across firewall policy configurations.

### List Traffic Matching Lists ✅

Retrieve all traffic matching lists on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/traffic-matching-lists`
- **MCP Tool:** `list_traffic_matching_lists()`
- **Implementation:** Batch 1 (92.47% coverage)

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### Create Traffic Matching List ✅

Create a new traffic matching list on a site.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/traffic-matching-lists`
- **MCP Tool:** `create_traffic_matching_list()`
- **Implementation:** Batch 1 (92.47% coverage)
- **Response:** `201 Created`

**Request Body:**

| Field | Type | Required |
|-------|------|----------|
| `type` | string | Yes (`PORTS`, `IPV4_ADDRESSES`, `IPV6_ADDRESSES`) |
| `name` | string | Yes (non-empty) |
| `items` | array | Yes (non-empty) |

### Get Traffic Matching List ✅

Get an existing traffic matching list on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/traffic-matching-lists/{trafficMatchingListId}`
- **MCP Tool:** `get_traffic_matching_list()`
- **Implementation:** Batch 1 (92.47% coverage)

**Response Fields:**

| Field | Type |
|-------|------|
| `type` | string (`PORTS`, `IPV4_ADDRESSES`, `IPV6_ADDRESSES`) |
| `id` | string (uuid) |
| `name` | string |
| `items` | array |

**Example Response (PORTS type):**
```json
{
  "type": "PORTS",
  "id": "ffcdb32c-6278-4364-8947-df4f77118df8",
  "name": "Allowed port list",
  "items": [...]
}
```

### Update Traffic Matching List ✅

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/traffic-matching-lists/{trafficMatchingListId}`
- **MCP Tool:** `update_traffic_matching_list()`
- **Implementation:** Batch 1 (92.47% coverage)

**Request Body:**

| Field | Type | Required |
|-------|------|----------|
| `type` | string | Yes (`PORTS`, `IPV4_ADDRESSES`, `IPV6_ADDRESSES`) |
| `name` | string | Yes (non-empty) |
| `items` | array | Yes (non-empty) |

**Response:** `200 OK`

### Delete Traffic Matching List ✅

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/traffic-matching-lists/{trafficMatchingListId}`
- **MCP Tool:** `delete_traffic_matching_list()`
- **Implementation:** Batch 1 (92.47% coverage)

**Response:** `200 OK`

---

## Quality of Service (QoS)

Manage Quality of Service profiles, ProAV (Professional Audio/Video) protocols, Smart Queue Management (bufferbloat mitigation), and policy-based traffic routing rules.

### Overview

UniFi's QoS system provides comprehensive traffic prioritization and shaping capabilities:

- **QoS Profiles**: Define traffic priority levels (0-7) with DSCP marking (0-63) for bandwidth guarantees
- **ProAV Protocols**: Pre-configured templates for professional audio/video standards (Dante, Q-SYS, SDVoE, AVB, RAVENNA, NDI, SMPTE 2110)
- **Smart Queue Management (SQM)**: Bufferbloat mitigation using fq_codel or CAKE algorithms
- **Traffic Routes**: Policy-based routing rules with match criteria (IP, port, protocol, VLAN) and actions (allow, deny, mark, shape)

**Best Practices:**
- Use priority levels 5-7 for real-time traffic (voice, video conferencing)
- Apply DSCP marking EF (46) for voice, AF41 (34) for high-quality video
- Enable SQM on WAN interfaces <300 Mbps for best bufferbloat mitigation
- Use reference profiles (voice-first, video-conferencing, cloud-gaming) as starting points
- Test QoS rules during peak hours to validate bandwidth guarantees

### List QoS Profiles ✅

Retrieve all QoS profiles configured for traffic prioritization and bandwidth shaping.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/qos/profiles`
- **MCP Tool:** `list_qos_profiles()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `offset` | number | 0 | Number of items to skip |
| `limit` | number | 100 | Maximum items to return |

**Response:** `200 OK`

```json
{
  "data": [
    {
      "_id": "profile-001",
      "name": "Voice Priority",
      "priority_level": 6,
      "dscp_marking": 46,
      "bandwidth_guaranteed_down_kbps": 256,
      "bandwidth_guaranteed_up_kbps": 256,
      "bandwidth_limit_down_kbps": 1024,
      "bandwidth_limit_up_kbps": 512,
      "enabled": true
    }
  ],
  "total": 5,
  "offset": 0,
  "limit": 100
}
```

---

### Get QoS Profile ✅

Retrieve detailed information about a specific QoS profile.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/qos/profiles/{profileId}`
- **MCP Tool:** `get_qos_profile()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)

**Response:** `200 OK`

---

### Create QoS Profile ✅

Create a new QoS profile with comprehensive traffic shaping configuration.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/qos/profiles`
- **MCP Tool:** `create_qos_profile()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)
- **Requires:** `confirm=true`
- **Supports:** `dry_run=true`

**Request Body:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique profile name |
| `priority_level` | number | Yes | 0-7 (0=lowest, 7=highest) |
| `dscp_marking` | number | No | 0-63 (DSCP value) |
| `bandwidth_guaranteed_down_kbps` | number | No | ≥0 |
| `bandwidth_guaranteed_up_kbps` | number | No | ≥0 |
| `bandwidth_limit_down_kbps` | number | No | ≥0 |
| `bandwidth_limit_up_kbps` | number | No | ≥0 |
| `enabled` | boolean | No | Default: true |
| `schedule` | object | No | Time-based activation |

**Example Request:**

```json
{
  "name": "Video Conferencing Premium",
  "priority_level": 5,
  "dscp_marking": 34,
  "bandwidth_guaranteed_down_kbps": 5000,
  "bandwidth_guaranteed_up_kbps": 2000,
  "bandwidth_limit_down_kbps": 10000,
  "bandwidth_limit_up_kbps": 5000,
  "enabled": true,
  "schedule": {
    "days_of_week": [1, 2, 3, 4, 5],
    "start_time": "08:00",
    "end_time": "18:00"
  }
}
```

**Response:** `201 Created`

---

### Update QoS Profile ✅

Update an existing QoS profile's configuration.

- **Method:** `PATCH`
- **Endpoint:** `/v1/sites/{siteId}/qos/profiles/{profileId}`
- **MCP Tool:** `update_qos_profile()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)
- **Requires:** `confirm=true`
- **Supports:** `dry_run=true`

**Request Body:** All fields optional (only provided fields are updated)

**Response:** `200 OK`

---

### Delete QoS Profile ✅

Delete a QoS profile from the site.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/qos/profiles/{profileId}`
- **MCP Tool:** `delete_qos_profile()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)
- **Requires:** `confirm=true`

**Response:** `200 OK`

---

### List ProAV Templates ✅

List available Professional Audio/Video protocol templates and reference QoS profiles.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/qos/proav/templates`
- **MCP Tool:** `list_proav_templates()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)

**Response:** `200 OK`

```json
{
  "templates": [
    {
      "protocol": "dante",
      "name": "Dante",
      "description": "Audinate Dante professional audio over IP",
      "priority_level": 6,
      "dscp_marking": 46,
      "bandwidth_requirement_mbps": 100,
      "latency_requirement_ms": 5,
      "recommendations": [
        "Enable PTP (Precision Time Protocol) for clock synchronization",
        "Use dedicated VLAN for Dante traffic",
        "Multicast support required",
        "Minimum 1 Gbps network recommended"
      ]
    }
  ],
  "total": 13
}
```

**Available ProAV Protocols:**
- **dante**: Audinate Dante (100 Mbps, 5ms latency, DSCP 46)
- **q-sys**: Q-SYS by QSC (50 Mbps, 10ms latency, DSCP 34)
- **sdvoe**: SDVoE (10 Gbps, 100µs latency, DSCP 46)
- **avb**: Audio Video Bridging (100 Mbps, 2ms latency, DSCP 46)
- **ravenna**: RAVENNA (100 Mbps, 1ms latency, DSCP 46)
- **ndi**: NDI (Network Device Interface) (100 Mbps, 16ms latency, DSCP 34)
- **smpte-2110**: SMPTE 2110 (10 Gbps, 1ms latency, DSCP 46)

**Reference Profiles:**
- **voice-first**: Voice-optimized (128 Kbps guaranteed, DSCP 46)
- **video-conferencing**: Balanced video conferencing (5 Mbps guaranteed, DSCP 34)
- **cloud-gaming**: Low-latency gaming (10 Mbps guaranteed, DSCP 28)
- **streaming-media**: High-bandwidth streaming (25 Mbps guaranteed, DSCP 26)
- **bulk-backup**: Bulk data transfer (no guarantee, DSCP 8)
- **guest-best-effort**: Guest network (throttled to 10 Mbps, DSCP 0)

---

### Create ProAV Profile ✅

Create a QoS profile from a ProAV or reference template with optional customizations.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/qos/proav/profiles`
- **MCP Tool:** `create_proav_profile()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)
- **Requires:** `confirm=true`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `protocol` | string | Yes | ProAV protocol or reference profile name |
| `name` | string | No | Custom name (defaults to protocol name) |
| `priority_level` | number | No | Override template priority |
| `dscp_marking` | number | No | Override template DSCP |
| `bandwidth_multiplier` | number | No | Scale bandwidth (default: 1.0) |
| `enabled` | boolean | No | Enable immediately (default: true) |

**Example Request:**

```json
{
  "protocol": "dante",
  "name": "Dante Audio System - Studio A",
  "bandwidth_multiplier": 1.5,
  "enabled": true
}
```

**Response:** `201 Created`

---

### Validate ProAV Profile ✅

Validate that network infrastructure meets ProAV protocol requirements.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/qos/proav/validate`
- **MCP Tool:** `validate_proav_profile()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)

**Request Body:**

| Field | Type | Required |
|-------|------|----------|
| `protocol` | string | Yes |
| `bandwidth_mbps` | number | No |

**Response:** `200 OK`

```json
{
  "valid": true,
  "protocol": "dante",
  "requirements": {
    "bandwidth_mbps": 100,
    "latency_ms": 5,
    "jitter_tolerance_ms": 1
  },
  "current_capacity": {
    "bandwidth_mbps": 1000,
    "estimated_latency_ms": 2
  },
  "warnings": [],
  "recommendations": [
    "Enable PTP (Precision Time Protocol) for clock synchronization",
    "Use dedicated VLAN for Dante traffic"
  ]
}
```

---

### Get Smart Queue Config ✅

Retrieve Smart Queue Management (SQM) configuration for a WAN interface.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/qos/smart-queue/{wanId}`
- **MCP Tool:** `get_smart_queue_config()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)

**Response:** `200 OK`

```json
{
  "_id": "wan-001",
  "algorithm": "fq_codel",
  "download_kbps": 100000,
  "upload_kbps": 20000,
  "overhead_bytes": 44,
  "atm_mode": false,
  "enabled": true
}
```

---

### Configure Smart Queue ✅

Configure Smart Queue Management for bufferbloat mitigation on a WAN interface.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/qos/smart-queue/{wanId}`
- **MCP Tool:** `configure_smart_queue()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)
- **Requires:** `confirm=true`
- **Supports:** `dry_run=true`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `download_kbps` | number | Yes | Download bandwidth in Kbps |
| `upload_kbps` | number | Yes | Upload bandwidth in Kbps |
| `algorithm` | string | No | "fq_codel" or "cake" (default: fq_codel) |
| `overhead_bytes` | number | No | Protocol overhead (default: 44) |
| `atm_mode` | boolean | No | ATM cell overhead (default: false) |

**Example Request:**

```json
{
  "download_kbps": 95000,
  "upload_kbps": 19000,
  "algorithm": "cake",
  "overhead_bytes": 44,
  "atm_mode": false
}
```

**Performance Note:** SQM is most effective for connections <300 Mbps. Above 300 Mbps, CPU overhead may impact performance.

**Response:** `200 OK`

---

### Disable Smart Queue ✅

Disable Smart Queue Management on a WAN interface.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/qos/smart-queue/{wanId}`
- **MCP Tool:** `disable_smart_queue()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)
- **Requires:** `confirm=true`

**Response:** `200 OK`

---

### List Traffic Routes ✅

List all policy-based traffic routing rules.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/qos/routes`
- **MCP Tool:** `list_traffic_routes()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 100 |

**Response:** `200 OK`

```json
{
  "data": [
    {
      "_id": "route-001",
      "name": "VoIP Priority Route",
      "action": "mark",
      "priority": 100,
      "match_criteria": {
        "source_ip": "192.168.1.0/24",
        "destination_port": 5060,
        "protocol": "udp"
      },
      "dscp_marking": 46,
      "enabled": true
    }
  ],
  "total": 12,
  "offset": 0,
  "limit": 100
}
```

---

### Create Traffic Route ✅

Create a new policy-based traffic routing rule.

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/qos/routes`
- **MCP Tool:** `create_traffic_route()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)
- **Requires:** `confirm=true`

**Request Body:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique route name |
| `action` | string | Yes | "allow", "deny", "mark", "shape" |
| `priority` | number | No | 1-1000 (default: 100) |
| `source_ip` | string | No | CIDR notation |
| `destination_ip` | string | No | CIDR notation |
| `source_port` | number | No | 1-65535 |
| `destination_port` | number | No | 1-65535 |
| `protocol` | string | No | "tcp", "udp", "icmp" |
| `vlan_id` | number | No | 1-4094 |
| `dscp_marking` | number | No | 0-63 (for "mark" action) |
| `bandwidth_limit_kbps` | number | No | ≥0 (for "shape" action) |
| `enabled` | boolean | No | Default: true |

**Example Request:**

```json
{
  "name": "Zoom QoS Priority",
  "action": "mark",
  "priority": 200,
  "match_criteria": {
    "destination_port": 8801,
    "protocol": "udp"
  },
  "dscp_marking": 34,
  "enabled": true
}
```

**Response:** `201 Created`

---

### Update Traffic Route ✅

Update an existing traffic routing rule.

- **Method:** `PATCH`
- **Endpoint:** `/v1/sites/{siteId}/qos/routes/{routeId}`
- **MCP Tool:** `update_traffic_route()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)
- **Requires:** `confirm=true`

**Response:** `200 OK`

---

### Delete Traffic Route ✅

Delete a traffic routing rule.

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/qos/routes/{routeId}`
- **MCP Tool:** `delete_traffic_route()`
- **Implementation:** v0.2.0 Phase 3 (82% coverage)
- **Requires:** `confirm=true`

**Response:** `200 OK`

---

### DSCP Marking Reference

Common DSCP values for traffic classification (RFC 4594):

| DSCP | Binary | Decimal | Traffic Class | Use Case |
|------|--------|---------|---------------|----------|
| EF | 101110 | 46 | Expedited Forwarding | Voice, real-time interactive |
| AF41 | 100010 | 34 | Assured Forwarding 4-1 | High-quality video conferencing |
| AF31 | 011010 | 26 | Assured Forwarding 3-1 | Streaming media, broadcast video |
| AF21 | 010010 | 18 | Assured Forwarding 2-1 | Bulk data, email |
| CS1 | 001000 | 8 | Class Selector 1 | Background/scavenger traffic |
| DF | 000000 | 0 | Default/Best Effort | Standard internet traffic |

**Assured Forwarding Classes:**
- **AF4x** (32-34): High priority, low drop precedence
- **AF3x** (26-28): Medium priority
- **AF2x** (18-20): Normal priority
- **AF1x** (10-12): Low priority

**Class Selectors (Backward Compatible):**
- **CS7** (56): Network control
- **CS6** (48): Internetwork control
- **CS5** (40): Voice/video
- **CS4** (32): Real-time interactive
- **CS3** (24): Broadcast video
- **CS2** (16): High-throughput data
- **CS1** (8): Low-priority data

---

## Backup and Restore

Comprehensive backup and restore operations for disaster recovery, configuration migration, and system maintenance.

### Overview

UniFi's Backup and Restore system provides critical disaster recovery capabilities:

- **Backup Creation**: Create network or system backups on-demand or on schedule
- **Backup Management**: List, download, validate, and delete backup files
- **Restore Operations**: Restore from backups with automatic pre-restore safety backups
- **Automated Scheduling**: Configure daily, weekly, or monthly automated backups
- **Operation Monitoring**: Track backup and restore progress in real-time
- **Cloud Sync**: Optionally sync backups to UniFi Cloud (requires account)

**Backup Types:**
- **Network Backups** (<10 MB): Network settings, device configurations, WiFi networks, firewall rules (fastest, recommended for frequent backups)
- **System Backups** (10-100+ MB): Complete OS, application, and device configurations (comprehensive, recommended for major changes)

**Best Practices:**
- Always create a pre-restore backup before restoring (enabled by default)
- Schedule automated daily network backups for production environments
- Keep at least 7-30 days of backup retention
- Download critical backups to external storage before major changes
- Test backup validation before restore operations
- Monitor controller connectivity during restore (controller may restart)

### Trigger Backup ✅

Create a new backup of the specified type.

- **Method:** `POST`
- **Endpoint:** `/api/cmd/backup`
- **MCP Tool:** `trigger_backup()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)
- **Requires:** `confirm=true`
- **Supports:** `dry_run=true`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `backup_type` | string | Yes | "network" or "system" |
| `retention_days` | number | No | Days to retain (default: 30, -1 for indefinite) |

**Example Request:**

```json
{
  "backup_type": "network",
  "retention_days": 30
}
```

**Response:** `200 OK`

```json
{
  "backup_id": "backup_20260124_123456",
  "filename": "backup_2026-01-24_12-34-56.unf",
  "download_url": "/data/backup/backup_2026-01-24_12-34-56.unf",
  "backup_type": "network",
  "created_at": "2026-01-24T12:34:56Z",
  "retention_days": 30,
  "status": "completed"
}
```

**Note**: Network backups complete in <30 seconds, system backups may take 1-3 minutes.

---

### List Backups ✅

Retrieve metadata for all available backup files.

- **Method:** `GET`
- **Endpoint:** `/api/backup/list-backups`
- **MCP Tool:** `list_backups()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)

**Response:** `200 OK`

```json
[
  {
    "backup_id": "backup_20260124_123456",
    "filename": "backup_2026-01-24_12-34-56.unf",
    "backup_type": "NETWORK",
    "created_at": "2026-01-24T12:34:56Z",
    "size_bytes": 8456192,
    "version": "10.1.68",
    "is_valid": true,
    "cloud_synced": true
  }
]
```

---

### Get Backup Details ✅

Retrieve detailed information about a specific backup.

- **Method:** `GET`
- **Endpoint:** `/api/backup/details/{filename}`
- **MCP Tool:** `get_backup_details()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `backup_filename` | string | Backup filename (e.g., "backup_2026-01-24.unf") |

**Response:** `200 OK`

---

### Download Backup ✅

Download a backup file to local storage.

- **Method:** `GET`
- **Endpoint:** `/api/backup/download/{filename}`
- **MCP Tool:** `download_backup()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `backup_filename` | string | Yes | Backup filename to download |
| `output_path` | string | Yes | Local filesystem path to save |
| `verify_checksum` | boolean | No | Calculate SHA256 checksum (default: true) |

**Example Usage:**

```python
result = await download_backup(
    site_id="default",
    backup_filename="backup_2026-01-24.unf",
    output_path="/backups/unifi_backup.unf",
    settings=settings
)
print(f"Downloaded: {result['size_bytes']} bytes")
print(f"Checksum: {result['checksum']}")
```

---

### Delete Backup ✅

Permanently delete a backup file from controller storage.

- **Method:** `DELETE`
- **Endpoint:** `/api/backup/delete-backup`
- **MCP Tool:** `delete_backup()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)
- **Requires:** `confirm=true`
- **Supports:** `dry_run=true`

**Warning**: This operation cannot be undone. Ensure backup is downloaded or unnecessary before deletion.

---

### Restore Backup ✅

Restore the controller from a backup file (DESTRUCTIVE).

- **Method:** `POST`
- **Endpoint:** `/api/backup/restore`
- **MCP Tool:** `restore_backup()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)
- **Requires:** `confirm=true`
- **Supports:** `dry_run=true`

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `backup_filename` | string | Yes | Backup file to restore from |
| `create_pre_restore_backup` | boolean | No | Create safety backup first (default: true) |

**Safety Features:**
- Automatic pre-restore backup creation (recommended)
- Mandatory confirmation flag
- Rollback capability via pre-restore backup
- Audit logging

**Example Request:**

```json
{
  "backup_filename": "backup_2026-01-24.unf",
  "create_pre_restore_backup": true
}
```

**Response:** `200 OK`

```json
{
  "backup_filename": "backup_2026-01-24.unf",
  "status": "restore_initiated",
  "pre_restore_backup_id": "backup_20260124_140000_preRestore",
  "can_rollback": true,
  "restore_time": "2026-01-24T14:00:00Z",
  "warning": "Controller may restart. Devices may temporarily disconnect."
}
```

**Critical Warning**: Restore operations will:
1. Restore all configuration from the backup
2. Overwrite current settings
3. Cause controller restart (2-5 minutes)
4. Temporarily disconnect devices

---

### Validate Backup ✅

Validate a backup file before restore.

- **Method:** `POST`
- **Endpoint:** `/api/backup/validate`
- **MCP Tool:** `validate_backup()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)

**Response:** `200 OK`

```json
{
  "backup_id": "backup_20260124_123456",
  "backup_filename": "backup_2026-01-24.unf",
  "is_valid": true,
  "checksum_valid": true,
  "format_valid": true,
  "version_compatible": true,
  "backup_version": "10.1.68",
  "warnings": [],
  "errors": [],
  "size_bytes": 8456192,
  "validated_at": "2026-01-24T14:00:00Z"
}
```

---

### Get Backup Status ✅

Monitor the progress of an ongoing or completed backup operation.

- **Method:** `GET`
- **Endpoint:** `/api/backup/status/{operationId}`
- **MCP Tool:** `get_backup_status()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `operation_id` | string | Backup operation identifier (from trigger_backup) |

**Response:** `200 OK`

```json
{
  "operation_id": "op_backup_abc123",
  "status": "completed",
  "progress_percent": 100,
  "current_step": "Finalizing backup",
  "started_at": "2026-01-24T12:34:00Z",
  "completed_at": "2026-01-24T12:35:30Z",
  "backup_metadata": {
    "id": "backup-123",
    "filename": "backup_20260124.unf"
  },
  "error_message": null
}
```

**Status Values:** `pending`, `in_progress`, `completed`, `failed`

**Note**: Most backups complete quickly. This tool is primarily useful for large system backups.

---

### Get Restore Status ✅

Monitor the progress of an ongoing or completed restore operation.

- **Method:** `GET`
- **Endpoint:** `/api/restore/status/{operationId}`
- **MCP Tool:** `get_restore_status()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `operation_id` | string | Restore operation identifier (from restore_backup) |

**Response:** `200 OK`

```json
{
  "operation_id": "op_restore_xyz789",
  "backup_id": "backup_20260124_123456",
  "status": "in_progress",
  "progress_percent": 45,
  "current_step": "Restoring device configurations",
  "started_at": "2026-01-24T14:00:00Z",
  "completed_at": null,
  "pre_restore_backup_id": "backup_20260124_140000_preRestore",
  "can_rollback": true,
  "error_message": null,
  "rollback_reason": null
}
```

**Status Values:** `pending`, `in_progress`, `completed`, `failed`, `rolled_back`

**Note**: Expect connection errors during restore as controller restarts. Monitor controller connectivity to determine completion.

---

### Schedule Backups ✅

Configure automated backup schedule for recurring backups.

- **Method:** `POST`
- **Endpoint:** `/api/backup/schedule`
- **MCP Tool:** `schedule_backups()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)
- **Requires:** `confirm=true`
- **Supports:** `dry_run=true`

**Request Body:**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `backup_type` | string | Yes | "network" or "system" |
| `frequency` | string | Yes | "daily", "weekly", or "monthly" |
| `time_of_day` | string | Yes | HH:MM format (24-hour) |
| `enabled` | boolean | No | Default: true |
| `retention_days` | number | No | 1-365 (default: 30) |
| `max_backups` | number | No | 1-100 (default: 10) |
| `day_of_week` | number | No | 0-6 (0=Monday, required if weekly) |
| `day_of_month` | number | No | 1-31 (required if monthly) |
| `cloud_backup_enabled` | boolean | No | Sync to cloud (default: false) |

**Example Request (Daily):**

```json
{
  "backup_type": "network",
  "frequency": "daily",
  "time_of_day": "03:00",
  "retention_days": 30,
  "max_backups": 10,
  "enabled": true
}
```

**Example Request (Weekly):**

```json
{
  "backup_type": "system",
  "frequency": "weekly",
  "time_of_day": "02:00",
  "day_of_week": 6,
  "retention_days": 90,
  "max_backups": 12,
  "cloud_backup_enabled": true,
  "enabled": true
}
```

**Response:** `201 Created`

```json
{
  "schedule_id": "schedule_daily_network",
  "site_id": "default",
  "enabled": true,
  "backup_type": "network",
  "frequency": "daily",
  "time_of_day": "03:00",
  "retention_days": 30,
  "max_backups": 10,
  "cloud_backup_enabled": false,
  "configured_at": "2026-01-24T14:30:00Z",
  "next_run": "2026-01-25T03:00:00Z"
}
```

**Scheduling Recommendations:**
- **Daily network backups**: Production environments (3 AM recommended)
- **Weekly system backups**: Most use cases (Sunday 2 AM recommended)
- **Monthly backups**: Only for static environments

---

### Get Backup Schedule ✅

Retrieve the configured automated backup schedule for a site.

- **Method:** `GET`
- **Endpoint:** `/api/backup/schedule`
- **MCP Tool:** `get_backup_schedule()`
- **Implementation:** v0.2.0 Phase 4 (86% coverage)

**Response (Configured):** `200 OK`

```json
{
  "configured": true,
  "schedule_id": "schedule_daily_network",
  "enabled": true,
  "backup_type": "network",
  "frequency": "daily",
  "time_of_day": "03:00",
  "retention_days": 30,
  "max_backups": 10,
  "cloud_backup_enabled": true,
  "last_run": "2026-01-24T03:00:00Z",
  "last_backup_id": "backup-123",
  "next_run": "2026-01-25T03:00:00Z"
}
```

**Response (Not Configured):** `200 OK`

```json
{
  "configured": false,
  "message": "No automated backup schedule configured for this site",
  "recommendation": "Use schedule_backups to configure automated backups"
}
```

---

## Site Manager API

**Implementation:** v0.2.0 Phase 5 (~60% complete)
**Coverage:** 92.95% (33 tests passing)
**Status:** Multi-site aggregation complete, OAuth/SSO pending

The Site Manager API provides centralized management and monitoring capabilities across multiple UniFi sites. These tools enable comprehensive oversight of distributed network deployments through unified health metrics, performance comparisons, inventory management, and cross-site search functionality.

**⚠️ Configuration Required:**
```bash
export UNIFI_SITE_MANAGER_ENABLED=true
export UNIFI_API_KEY=<your-site-manager-api-key>
export UNIFI_API_TYPE=cloud-ea  # or cloud-v1
```

### Overview

The Site Manager API consists of 8 tools organized into three categories:

**Basic Aggregation:**
- List all sites with aggregated statistics
- Get internet health metrics
- Get site health summaries
- List Vantage Points

**Advanced Analytics:**
- Get site inventory (comprehensive resource breakdown)
- Compare site performance (rankings and metrics)
- Get cross-site statistics

**Search & Discovery:**
- Search across sites (devices, clients, networks)

---

### Example Prompts for Site Manager

```
"Show me all my sites and their current health status"
"Which site has the best uptime and performance?"
"Find all Ubiquiti access points across all my locations"
"Give me a complete inventory of devices at the downtown office"
"Compare performance metrics between all my branch offices"
"Search for the device with MAC address aa:bb:cc:dd:ee:ff across all sites"
"Show me sites with degraded internet connectivity"
"Which site has the most devices offline right now?"
```

---

### List All Sites Aggregated ✅

List all managed sites with aggregated statistics from the Site Manager API.

- **Method:** `GET`
- **Endpoint:** `/v1/sites`
- **MCP Tool:** `list_all_sites_aggregated()`
- **Implementation:** v0.2.0 Phase 5 (93% coverage)

**Request:** No parameters required.

**Response:** `200 OK`

```json
[
  {
    "site_id": "site-abc123",
    "name": "Main Office",
    "devices": 25,
    "clients": 150,
    "status": "healthy",
    "uptime_percentage": 99.9
  },
  {
    "site_id": "site-def456",
    "name": "Branch Office",
    "devices": 10,
    "clients": 50,
    "status": "degraded",
    "uptime_percentage": 95.0
  }
]
```

---

### Get Internet Health ✅

Get internet connectivity health metrics across sites or for a specific site.

- **Method:** `GET`
- **Endpoint:** `/v1/internet/health` or `/v1/sites/{siteId}/internet/health`
- **MCP Tool:** `get_internet_health(site_id=None)`
- **Implementation:** v0.2.0 Phase 5 (93% coverage)

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `site_id` | string | No | Site identifier (None for aggregate) |

**Response (Aggregate):** `200 OK`

```json
{
  "site_id": null,
  "latency_ms": 25.5,
  "packet_loss_percent": 0.1,
  "jitter_ms": 2.3,
  "bandwidth_up_mbps": 100.0,
  "bandwidth_down_mbps": 500.0,
  "status": "healthy",
  "last_tested": "2026-01-24T12:00:00Z"
}
```

**Response (Specific Site):** `200 OK`

```json
{
  "site_id": "site-abc123",
  "latency_ms": 15.0,
  "packet_loss_percent": 0.0,
  "jitter_ms": 1.0,
  "bandwidth_up_mbps": 50.0,
  "bandwidth_down_mbps": 200.0,
  "status": "healthy",
  "last_tested": "2026-01-24T12:00:00Z"
}
```

---

### Get Site Health Summary ✅

Get health summary for all sites or a specific site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/health` or `/v1/sites/{siteId}/health`
- **MCP Tool:** `get_site_health_summary(site_id=None)`
- **Implementation:** v0.2.0 Phase 5 (93% coverage)

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `site_id` | string | No | Site identifier (None for all sites) |

**Response (All Sites):** `200 OK`

```json
[
  {
    "site_id": "site-abc123",
    "site_name": "Main Office",
    "status": "healthy",
    "devices_online": 25,
    "devices_total": 25,
    "clients_active": 150,
    "uptime_percentage": 99.9,
    "last_updated": "2026-01-24T12:00:00Z"
  },
  {
    "site_id": "site-def456",
    "site_name": "Branch Office",
    "status": "degraded",
    "devices_online": 8,
    "devices_total": 10,
    "clients_active": 50,
    "uptime_percentage": 95.0,
    "last_updated": "2026-01-24T12:00:00Z"
  }
]
```

---

### Get Cross-Site Statistics ✅

Get aggregated statistics across all managed sites.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/statistics`
- **MCP Tool:** `get_cross_site_statistics()`
- **Implementation:** v0.2.0 Phase 5 (93% coverage)

**Request:** No parameters required.

**Response:** `200 OK`

```json
{
  "total_sites": 5,
  "sites_healthy": 3,
  "sites_degraded": 1,
  "sites_down": 1,
  "total_devices": 75,
  "devices_online": 68,
  "total_clients": 350,
  "total_bandwidth_up_mbps": 500.0,
  "total_bandwidth_down_mbps": 2500.0,
  "site_summaries": [
    {
      "site_id": "site-abc123",
      "site_name": "Main Office",
      "status": "healthy",
      "devices_online": 25,
      "devices_total": 25,
      "clients_active": 150,
      "uptime_percentage": 99.9,
      "last_updated": "2026-01-24T12:00:00Z"
    }
  ]
}
```

---

### List Vantage Points ✅

List all Vantage Points for network monitoring and testing.

- **Method:** `GET`
- **Endpoint:** `/v1/vantage-points`
- **MCP Tool:** `list_vantage_points()`
- **Implementation:** v0.2.0 Phase 5 (93% coverage)

**Request:** No parameters required.

**Response:** `200 OK`

```json
[
  {
    "vantage_point_id": "vp-123",
    "name": "New York Office",
    "location": "New York, NY",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "status": "active",
    "site_ids": ["site-abc123", "site-def456"]
  },
  {
    "vantage_point_id": "vp-456",
    "name": "London Office",
    "location": "London, UK",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "status": "active",
    "site_ids": ["site-ghi789"]
  }
]
```

---

### Get Site Inventory ✅ 🆕

Get comprehensive inventory for a site or all sites.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/inventory` or `/v1/sites/inventory`
- **MCP Tool:** `get_site_inventory(site_id=None)`
- **Implementation:** v0.2.0 Phase 5 (93% coverage)

Provides detailed resource breakdown including device counts by type, networks, SSIDs, VPN tunnels, and firewall rules.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `site_id` | string | No | Site identifier (None for all sites) |

**Response (Specific Site):** `200 OK`

```json
{
  "site_id": "site-abc123",
  "site_name": "Main Office",
  "device_count": 25,
  "device_types": {
    "uap": 15,
    "usw": 8,
    "ugw": 2
  },
  "client_count": 150,
  "network_count": 8,
  "ssid_count": 5,
  "uplink_count": 2,
  "vpn_tunnel_count": 4,
  "firewall_rule_count": 45,
  "last_updated": "2026-01-24T12:00:00Z"
}
```

**Response (All Sites):** `200 OK`

Returns an array of inventory objects for each site.

---

### Compare Site Performance ✅ 🆕

Compare performance metrics across all sites with rankings.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/performance/compare`
- **MCP Tool:** `compare_site_performance()`
- **Implementation:** v0.2.0 Phase 5 (93% coverage)

Analyzes uptime, latency, bandwidth, and health status to identify best and worst performing sites.

**Request:** No parameters required.

**Response:** `200 OK`

```json
{
  "total_sites": 3,
  "best_performing_site": {
    "site_id": "site-abc123",
    "site_name": "Main Office",
    "avg_latency_ms": 10.0,
    "avg_bandwidth_up_mbps": 100.0,
    "avg_bandwidth_down_mbps": 500.0,
    "uptime_percentage": 99.9,
    "device_online_percentage": 100.0,
    "client_count": 150,
    "health_status": "healthy"
  },
  "worst_performing_site": {
    "site_id": "site-ghi789",
    "site_name": "Remote Office",
    "avg_latency_ms": 150.0,
    "avg_bandwidth_up_mbps": 20.0,
    "avg_bandwidth_down_mbps": 100.0,
    "uptime_percentage": 80.0,
    "device_online_percentage": 50.0,
    "client_count": 20,
    "health_status": "degraded"
  },
  "average_uptime": 91.63,
  "average_latency_ms": 61.67,
  "site_metrics": [
    {
      "site_id": "site-abc123",
      "site_name": "Main Office",
      "avg_latency_ms": 10.0,
      "uptime_percentage": 99.9,
      "health_status": "healthy"
    },
    {
      "site_id": "site-def456",
      "site_name": "Branch Office",
      "avg_latency_ms": 25.0,
      "uptime_percentage": 95.0,
      "health_status": "healthy"
    },
    {
      "site_id": "site-ghi789",
      "site_name": "Remote Office",
      "avg_latency_ms": 150.0,
      "uptime_percentage": 80.0,
      "health_status": "degraded"
    }
  ]
}
```

**Use Cases:**
- Identify sites needing infrastructure upgrades
- Compare performance across geographic regions
- Track improvement over time
- SLA compliance monitoring

---

### Search Across Sites ✅ 🆕

Search for devices, clients, or networks across all managed sites.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/search`
- **MCP Tool:** `search_across_sites(query, search_type='all')`
- **Implementation:** v0.2.0 Phase 5 (93% coverage)

Useful for locating resources in multi-site deployments. Supports search by name, MAC address, or IP address.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Search query (name, MAC, IP) |
| `search_type` | string | No | "device", "client", "network", or "all" (default: "all") |

**Example Request:**

```json
{
  "query": "ap-living",
  "search_type": "device"
}
```

**Response:** `200 OK`

```json
{
  "total_results": 2,
  "search_query": "ap-living",
  "result_type": "device",
  "results": [
    {
      "type": "device",
      "site_id": "site-abc123",
      "site_name": "Main Office",
      "resource": {
        "name": "AP-Living-Room",
        "mac": "aa:bb:cc:dd:ee:01",
        "type": "uap",
        "model": "U6-Pro",
        "ip": "192.168.2.10",
        "status": "online"
      }
    },
    {
      "type": "device",
      "site_id": "site-def456",
      "site_name": "Branch Office",
      "resource": {
        "name": "AP-Living-Area",
        "mac": "aa:bb:cc:dd:ee:02",
        "type": "uap",
        "model": "U6-Lite",
        "ip": "192.168.2.10",
        "status": "online"
      }
    }
  ]
}
```

**Search Types:**
- `device` - Search devices by name or MAC address
- `client` - Search clients by name, MAC, or IP address
- `network` - Search networks by name
- `all` - Search all resource types

**Use Cases:**
- Locate specific device across multiple locations
- Find all instances of a client device
- Identify which site has a particular resource
- MAC address tracking for security investigations

---

## Supporting Resources

Contains read-only reference endpoints used to retrieve supporting data such as WAN interfaces, DPI categories, country codes, RADIUS profiles, and device tags.

### List WAN Interfaces

Returns available WAN interface definitions for a given site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/wans`

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |

**Response:** `200 OK`

### List Site-To-Site VPN Tunnels ✅

Retrieve a paginated list of all site-to-site VPN tunnels on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/vpn/site-to-site-tunnels`
- **MCP Tool:** `list_vpn_tunnels()`
- **Implementation:** Batch 2 (100% coverage)

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### List VPN Servers ✅

Retrieve a paginated list of all VPN servers on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/vpn/servers`
- **MCP Tool:** `list_vpn_servers()`
- **Implementation:** Batch 2 (100% coverage)

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### List Radius Profiles ✅

Returns available RADIUS authentication profiles.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/radius/profiles`
- **MCP Tool:** `list_radius_profiles()`
- **Implementation:** Batch 3 (100% coverage)

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### List Device Tags ✅

Returns all device tags defined within a site (used for WiFi Broadcast assignments).

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/device-tags`
- **MCP Tool:** `list_device_tags()`
- **Implementation:** Batch 3 (100% coverage)

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### List DPI Categories

Returns predefined Deep Packet Inspection (DPI) categories used for traffic identification and filtering.

- **Method:** `GET`
- **Endpoint:** `/v1/dpi/categories`

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### List DPI Applications

Lists DPI-recognized applications grouped under categories.

- **Method:** `GET`
- **Endpoint:** `/v1/dpi/applications`

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

### List Countries ✅

Returns ISO-standard country codes and names.

- **Method:** `GET`
- **Endpoint:** `/v1/countries`
- **MCP Tool:** `list_countries()` (enhanced with pagination)
- **Implementation:** Batch 3 (100% coverage)

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

---

## Common Response Format (Paginated Lists)

All list endpoints return a standard paginated response:

```json
{
  "offset": 0,
  "limit": 25,
  "count": 10,
  "totalCount": 1000,
  "data": [...]
}
```

| Field | Description |
|-------|-------------|
| `offset` | Current pagination offset |
| `limit` | Maximum items per page |
| `count` | Items in current response |
| `totalCount` | Total items available |
| `data` | Array of result objects |

---

## Notes

- All timestamps use ISO 8601 format
- All endpoints require valid API key authentication via `X-API-KEY` header
- Rate limiting applies per API key
- Mutating operations should implement confirmation flags in MCP server implementations
- The API is under active development; check changelog for updates

---

**Documentation Version:** v10.0.160
**Last Updated:** January 23, 2026
**Source:** UniFi Network API v10.0.160 (Merged Update)



## Site Manager API - New Endpoints

*Added: 2026-01-24*

### Version Control

Endpoints combined into Ansible Modules for customized workflows.

**Reference:** [Version Control](https://developer.ui.com/site-manager/v1.0.0/versioncontrol)

---

### List Hosts

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L "https://api.ui.com/v1/hosts?pageSize=10&nextToken=602232A870250000000006C514FF00000000073DD8DB000000006369FDA2%3A1467082514" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [List Hosts](https://developer.ui.com/site-manager/v1.0.0/listhosts)

---

### Get Host by ID

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/hosts/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get Host by ID](https://developer.ui.com/site-manager/v1.0.0/gethostbyid)

---

### List Sites

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L "https://api.ui.com/v1/sites?pageSize=10&nextToken=602232A870250000000006C514FF00000000073DD8DB000000006369FDA2%3A1467082514" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [List Sites](https://developer.ui.com/site-manager/v1.0.0/listsites)

---

### Get ISP Metrics

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/isp-metrics/{type}?beginTimestamp=2024-06-30T13%3A35%3A00Z&endTimestamp=2024-06-30T15%3A35%3A00Z&duration={duration}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get ISP Metrics](https://developer.ui.com/site-manager/v1.0.0/getispmetrics)

---




## Network API - New Endpoints

*Added: 2026-01-24*

### Connector - POST

- **Method:** `GET`
- **Endpoint:** `requests`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{id}/*path" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"action\": \"AUTHORIZE_GUEST_ACCESS\"}"
```

**Reference:** [Connector - POST](https://developer.ui.com/network/v10.1.68/connectorpost)

---

### Connector - GET

- **Method:** `GET`
- **Endpoint:** `requests`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{id}/*path" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Connector - GET](https://developer.ui.com/network/v10.1.68/connectorget)

---

### Connector - PUT

- **Method:** `GET`
- **Endpoint:** `requests`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X PUT "https://api.ui.com/v1/connector/consoles/{id}/*path" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"name\": \"Updated Firewall Zone\"}"
```

**Reference:** [Connector - PUT](https://developer.ui.com/network/v10.1.68/connectorput)

---

### Connector - DELETE

- **Method:** `GET`
- **Endpoint:** `requests`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X DELETE "https://api.ui.com/v1/connector/consoles/{id}/*path" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Connector - DELETE](https://developer.ui.com/network/v10.1.68/connectordelete)

---

### Connector - PATCH

- **Method:** `GET`
- **Endpoint:** `requests`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X PATCH "https://api.ui.com/v1/connector/consoles/{id}/*path" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"name\": \"Updated Viewer Name\"}"
```

**Reference:** [Connector - PATCH](https://developer.ui.com/network/v10.1.68/connectorpatch)

---




## Protect API - New Endpoints

*Added: 2026-01-24*

### Connector - POST

- **Method:** `GET`
- **Endpoint:** `requests`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{id}/*path" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"action\": \"AUTHORIZE_GUEST_ACCESS\"}"
```

**Reference:** [Connector - POST](https://developer.ui.com/protect/v6.2.83/connectorpost)

---

### Connector - GET

- **Method:** `GET`
- **Endpoint:** `requests`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{id}/*path" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Connector - GET](https://developer.ui.com/protect/v6.2.83/connectorget)

---

### Connector - PUT

- **Method:** `GET`
- **Endpoint:** `requests`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X PUT "https://api.ui.com/v1/connector/consoles/{id}/*path" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"name\": \"Updated Firewall Zone\"}"
```

**Reference:** [Connector - PUT](https://developer.ui.com/protect/v6.2.83/connectorput)

---

### Connector - DELETE

- **Method:** `GET`
- **Endpoint:** `requests`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X DELETE "https://api.ui.com/v1/connector/consoles/{id}/*path" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Connector - DELETE](https://developer.ui.com/protect/v6.2.83/connectordelete)

---

### Connector - PATCH

- **Method:** `GET`
- **Endpoint:** `requests`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X PATCH "https://api.ui.com/v1/connector/consoles/{id}/*path" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"name\": \"Updated Viewer Name\"}"
```

**Reference:** [Connector - PATCH](https://developer.ui.com/protect/v6.2.83/connectorpatch)

---

### Query ISP Metrics

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/isp-metrics/{type}/query" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"sites\": [    {      \"beginTimestamp\": \"2024-06-30T13:35:00Z\",      \"hostId\": \"900A6F00301100000000074A6BA90000000007A3387E0000000063EC9853:123456789\",      \"endTimestamp\": \"2024-06-30T15:35:00Z\",      \"siteId\": \"661900ae6aec8f548d49fd54\"    }  ]}"
```

**Reference:** [Query ISP Metrics](https://developer.ui.com/site-manager/v1.0.0/queryispmetrics)

---

### List SD-WAN Configs

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L "https://api.ui.com/v1/sd-wan-configs" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [List SD-WAN Configs](https://developer.ui.com/site-manager/v1.0.0/listsdwanconfigs)

---

### Get SD-WAN Config by ID

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/sd-wan-configs/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get SD-WAN Config by ID](https://developer.ui.com/site-manager/v1.0.0/getsdwanconfigbyid)

---

### Get SD-WAN Config Status

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/sd-wan-configs/{id}/status" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get SD-WAN Config Status](https://developer.ui.com/site-manager/v1.0.0/getsdwanconfigstatus)

---

### Adopt Devices

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/network/integration/v1/sites/{siteId}/devices" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"macAddress\": \"string\",  \"ignoreDeviceLimit\": true}"
```

**Reference:** [Adopt Devices](https://developer.ui.com/network/v10.1.68/adoptdevice)

---

### List DPI Application Categories

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/network/integration/v1/dpi/categories?offset={offset}&limit={limit}&filter={filter}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [List DPI Application Categories](https://developer.ui.com/network/v10.1.68/getdpiapplicationcategories)

---

### Quick Start

- **Method:** `GET`
- **Endpoint:** `register`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
pip install httpx urllib3
```

**Reference:** [Quick Start](https://developer.ui.com/network/v10.1.68/quick_start)

---

### Get application information

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/meta/info" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get application information](https://developer.ui.com/protect/v6.2.83/get-v1metainfo)

---

### Get viewer details

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/viewers/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get viewer details](https://developer.ui.com/protect/v6.2.83/get-v1viewersid)

---

### Patch viewer settings

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X PATCH "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/viewers/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"name\": \"string\",  \"liveview\": \"string\"}"
```

**Reference:** [Patch viewer settings](https://developer.ui.com/protect/v6.2.83/patch-v1viewersid)

---

### Get all viewers

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/viewers" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get all viewers](https://developer.ui.com/protect/v6.2.83/get-v1viewers)

---

### Get live view details

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/liveviews/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get live view details](https://developer.ui.com/protect/v6.2.83/get-v1liveviewsid)

---

### Patch live view configuration

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X PATCH "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/liveviews/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"id\": \"string\",  \"modelKey\": \"string\",  \"name\": \"string\",  \"isDefault\": true,  \"isGlobal\": true,  \"owner\": \"string\",  \"layout\": 0,  \"slots\": [    {      \"cameras\": [        \"string\"      ],      \"cycleMode\": \"motion\",      \"cycleInterval\": 0    }  ]}"
```

**Reference:** [Patch live view configuration](https://developer.ui.com/protect/v6.2.83/patch-v1liveviewsid)

---

### Get all live views

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/liveviews" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get all live views](https://developer.ui.com/protect/v6.2.83/get-v1liveviews)

---

### Create live view

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/liveviews" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"id\": \"string\",  \"modelKey\": \"string\",  \"name\": \"string\",  \"isDefault\": true,  \"isGlobal\": true,  \"owner\": \"string\",  \"layout\": 0,  \"slots\": [    {      \"cameras\": [        \"string\"      ],      \"cycleMode\": \"motion\",      \"cycleInterval\": 0    }  ]}"
```

**Reference:** [Create live view](https://developer.ui.com/protect/v6.2.83/post-v1liveviews)

---

### Get update messages about devices

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/subscribe/devices" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get update messages about devices](https://developer.ui.com/protect/v6.2.83/get-v1subscribedevices)

---

### Get Protect event messages

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/subscribe/events" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get Protect event messages](https://developer.ui.com/protect/v6.2.83/get-v1subscribeevents)

---

### Start a camera PTZ patrol

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X POST "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}/ptz/patrol/start/{slot}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Start a camera PTZ patrol](https://developer.ui.com/protect/v6.2.83/post-v1camerasidptzpatrolstartslot)

---

### Stop active camera PTZ patrol

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X POST "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}/ptz/patrol/stop" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Stop active camera PTZ patrol](https://developer.ui.com/protect/v6.2.83/post-v1camerasidptzpatrolstop)

---

### Move PTZ camera to preset

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X POST "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}/ptz/goto/{slot}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Move PTZ camera to preset](https://developer.ui.com/protect/v6.2.83/post-v1camerasidptzgotoslot)

---

### Send a webhook to the alarm manager

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X POST "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/alarm-manager/webhook/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Send a webhook to the alarm manager](https://developer.ui.com/protect/v6.2.83/post-v1alarm-managerwebhookid)

---

### Get light details

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/lights/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get light details](https://developer.ui.com/protect/v6.2.83/get-v1lightsid)

---

### Patch light settings

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X PATCH "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/lights/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"name\": \"string\",  \"isLightForceEnabled\": true,  \"lightModeSettings\": {    \"mode\": \"string\",    \"enableAt\": \"string\"  },  \"lightDeviceSettings\": {    \"isIndicatorEnabled\": true,    \"pirDuration\": 0,    \"pirSensitivity\": 0,    \"ledLevel\": 0  }}"
```

**Reference:** [Patch light settings](https://developer.ui.com/protect/v6.2.83/patch-v1lightsid)

---

### Get all lights

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/lights" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get all lights](https://developer.ui.com/protect/v6.2.83/get-v1lights)

---

### Get camera details

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get camera details](https://developer.ui.com/protect/v6.2.83/get-v1camerasid)

---

### Patch camera settings

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X PATCH "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"name\": \"string\",  \"osdSettings\": {    \"isNameEnabled\": true,    \"isDateEnabled\": true,    \"isLogoEnabled\": true,    \"isDebugEnabled\": true,    \"overlayLocation\": \"topLeft\"  },  \"ledSettings\": {    \"isEnabled\": true,    \"welcomeLed\": true,    \"floodLed\": true  },  \"lcdMessage\": {    \"type\": \"string\"  },  \"videoMode\": \"default\",  \"smartDetectSettings\": {    \"objectTypes\": [      \"person\"    ],    \"audioTypes\": [      \"alrmSmoke\"    ]  }}"
```

**Reference:** [Patch camera settings](https://developer.ui.com/protect/v6.2.83/patch-v1camerasid)

---

### Get all cameras

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get all cameras](https://developer.ui.com/protect/v6.2.83/get-v1cameras)

---

### Create RTSPS streams for camera

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}/rtsps-stream" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"qualities\": [    \"high\"  ]}"
```

**Reference:** [Create RTSPS streams for camera](https://developer.ui.com/protect/v6.2.83/post-v1camerasidrtsps-stream)

---

### Delete camera RTSPS stream

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X DELETE "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}/rtsps-stream?qualities={qualities}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Delete camera RTSPS stream](https://developer.ui.com/protect/v6.2.83/delete-v1camerasidrtsps-stream)

---

### Get RTSPS streams for camera

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}/rtsps-stream" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get RTSPS streams for camera](https://developer.ui.com/protect/v6.2.83/get-v1camerasidrtsps-stream)

---

### Get camera snapshot

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}/snapshot?highQuality={highQuality}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get camera snapshot](https://developer.ui.com/protect/v6.2.83/get-v1camerasidsnapshot)

---

### Permanently disable camera microphone

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X POST "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}/disable-mic-permanently" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Permanently disable camera microphone](https://developer.ui.com/protect/v6.2.83/post-v1camerasiddisable-mic-permanently)

---

### Create talkback session for camera

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X POST "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/cameras/{id}/talkback-session" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Create talkback session for camera](https://developer.ui.com/protect/v6.2.83/post-v1camerasidtalkback-session)

---

### Get sensor details

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/sensors/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get sensor details](https://developer.ui.com/protect/v6.2.83/get-v1sensorsid)

---

### Patch sensor settings

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X PATCH "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/sensors/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"name\": \"string\",  \"lightSettings\": {    \"isEnabled\": true,    \"margin\": 0  },  \"humiditySettings\": {    \"isEnabled\": true,    \"margin\": 0  },  \"temperatureSettings\": {    \"isEnabled\": true,    \"margin\": 0  },  \"motionSettings\": {    \"isEnabled\": true,    \"sensitivity\": 0  },  \"alarmSettings\": {    \"isEnabled\": true  }}"
```

**Reference:** [Patch sensor settings](https://developer.ui.com/protect/v6.2.83/patch-v1sensorsid)

---

### Get all sensors

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/sensors" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get all sensors](https://developer.ui.com/protect/v6.2.83/get-v1sensors)

---

### Get NVR details

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/nvrs" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get NVR details](https://developer.ui.com/protect/v6.2.83/get-v1nvrs)

---

### Upload device asset file

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X POST "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/files/{fileType}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Upload device asset file](https://developer.ui.com/protect/v6.2.83/post-v1filesfiletype)

---

### Get device asset files

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/files/{fileType}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get device asset files](https://developer.ui.com/protect/v6.2.83/get-v1filesfiletype)

---

### Get chime details

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/chimes/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get chime details](https://developer.ui.com/protect/v6.2.83/get-v1chimesid)

---

### Patch chime settings

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g -X PATCH "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/chimes/{id}" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>" \-H "Content-Type: application/json" \-d "{  \"name\": \"string\",  \"cameraIds\": [    \"string\"  ],  \"ringSettings\": [    {      \"cameraId\": \"string\",      \"repeatTimes\": 0,      \"ringtoneId\": \"string\",      \"volume\": 0    }  ]}"
```

**Reference:** [Patch chime settings](https://developer.ui.com/protect/v6.2.83/patch-v1chimesid)

---

### Get all chimes

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
curl -L -g "https://api.ui.com/v1/connector/consoles/{consoleId}/proxy/protect/integration/v1/chimes" \-H "Accept: application/json" \-H "X-API-Key: <X-API-Key>"
```

**Reference:** [Get all chimes](https://developer.ui.com/protect/v6.2.83/get-v1chimes)

---

### Quick Start

- **Method:** `GET`
- **Endpoint:** `register`

Endpoints combined into Ansible Modules for customized workflows.

**Example:**
```json
pip install httpx urllib3
```

**Reference:** [Quick Start](https://developer.ui.com/protect/v6.2.83/quick_start)

---
