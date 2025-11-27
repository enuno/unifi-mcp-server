# UniFi Network API Documentation (v10.0.160)

## Overview

This document provides comprehensive reference documentation for the UniFi Network API version 10.0.160. Each UniFi Application has its own API endpoints running locally on each site, offering detailed analytics and control related to that specific application. For a single endpoint with high-level insights across all your UniFi sites, refer to the [UniFi Site Manager API](https://developer.ui.com/).

## Table of Contents

- [Getting Started](#getting-started)
- [Filtering](#filtering)
- [Error Handling](#error-handling)
- [Application Info](#application-info)
- [Sites](#sites)
- [UniFi Devices](#unifi-devices)
- [Clients](#clients)
- [Networks](#networks)
- [WiFi Broadcasts](#wifi-broadcasts)
- [Hotspot](#hotspot)
- [Firewall](#firewall)
- [Access Control (ACL Rules)](#access-control-acl-rules)
- [Traffic Matching Lists](#traffic-matching-lists)
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

### Get Latest Adopted Device Statistics

Retrieve real-time statistics including uptime, CPU, memory utilization.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/devices/{deviceId}/statistics/latest`

**Response:** `200 OK`

```json
{
  "uptimeSec": 86400,
  "lastHeartbeatAt": "2025-11-26T12:00:00Z",
  "cpuUtilizationPct": 15.5,
  "memoryUtilizationPct": 45.2
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

Endpoints for creating, updating, deleting, and inspecting network configurations.

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

### Update Network

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/networks/{networkId}`

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

---

## WiFi Broadcasts

Endpoints to create, update, or remove WiFi networks (SSIDs).

### List Wifi Broadcasts

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/wifi/broadcasts`

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string (uuid) | Yes |

**Response:** `200 OK`

### Create Wifi Broadcast

- **Method:** `POST`
- **Endpoint:** `/v1/sites/{siteId}/wifi/broadcasts`
- **Response:** `201 Created`

**Request Body Fields:**

| Field | Type | Required |
|-------|------|----------|
| `type` | string | Yes (`STANDARD` or `IOT_OPTIMIZED`) |
| `name` | string | Yes |
| `enabled` | boolean | Yes |
| `securityConfiguration` | object | Yes |
| `multicastToUnicastConversionEnabled` | boolean | Yes |
| `clientIsolationEnabled` | boolean | Yes |
| `hideName` | boolean | Yes |
| `uapsdEnabled` | boolean | Yes |
| `broadcastingFrequenciesGHz` | array | Yes (`2.4`, `5`, `6`) |
| `arpProxyEnabled` | boolean | Yes |
| `bssTransitionEnabled` | boolean | Yes |

### Get Wifi Broadcast Details

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/wifi/broadcasts/{wifiBroadcastId}`

**Response:** `200 OK`

### Update Wifi Broadcast

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/wifi/broadcasts/{wifiBroadcastId}`

**Response:** `200 OK`

### Delete Wifi Broadcast

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/wifi/broadcasts/{wifiBroadcastId}`

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

## Firewall

Endpoints for managing custom firewall zones and policies within a site.

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

| Field | Type | Required |
|-------|------|----------|
| `name` | string | Yes |
| `networkIds` | array | Yes |

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
| `name` | string | Yes | ACL rule name |
| `description` | string | No | ACL rule description |
| `action` | string | Yes | `ALLOW` or `BLOCK` |
| `enforcingDeviceFilter` | object | No | Device filter (null = all switches) |
| `index` | integer (int32) | Yes | Rule priority (>= 0, lower = higher priority) |
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

**Response:** `200 OK`

### Delete ACL Rule

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/acl-rules/{aclRuleId}`

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
| `name` | string | Yes |
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

### Update Traffic Matching List ✅

- **Method:** `PUT`
- **Endpoint:** `/v1/sites/{siteId}/traffic-matching-lists/{trafficMatchingListId}`
- **MCP Tool:** `update_traffic_matching_list()`
- **Implementation:** Batch 1 (92.47% coverage)

**Response:** `200 OK`

### Delete Traffic Matching List ✅

- **Method:** `DELETE`
- **Endpoint:** `/v1/sites/{siteId}/traffic-matching-lists/{trafficMatchingListId}`
- **MCP Tool:** `delete_traffic_matching_list()`
- **Implementation:** Batch 1 (92.47% coverage)

**Response:** `200 OK`

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

**Response:** `200 OK`

### List VPN Servers ✅

Retrieve a paginated list of all VPN servers on a site.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/vpn/servers`
- **MCP Tool:** `list_vpn_servers()`
- **Implementation:** Batch 2 (100% coverage)

**Response:** `200 OK`

### List Radius Profiles ✅

Returns available RADIUS authentication profiles.

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/radius/profiles`
- **MCP Tool:** `list_radius_profiles()`
- **Implementation:** Batch 3 (100% coverage)

**Response:** `200 OK`

### List Device Tags ✅

Returns all device tags defined within a site (used for WiFi Broadcast assignments).

- **Method:** `GET`
- **Endpoint:** `/v1/sites/{siteId}/device-tags`
- **MCP Tool:** `list_device_tags()`
- **Implementation:** Batch 3 (100% coverage)

**Response:** `200 OK`

### List DPI Categories

Returns predefined Deep Packet Inspection (DPI) categories used for traffic identification and filtering.

- **Method:** `GET`
- **Endpoint:** `/v1/dpi/categories`

**Response:** `200 OK`

### List DPI Applications

Lists DPI-recognized applications grouped under categories.

- **Method:** `GET`
- **Endpoint:** `/v1/dpi/applications`

**Response:** `200 OK`

### List Countries ✅

Returns ISO-standard country codes and names.

- **Method:** `GET`
- **Endpoint:** `/v1/countries`
- **MCP Tool:** `list_countries()` (enhanced with pagination)
- **Implementation:** Batch 3 (100% coverage)

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
**Last Updated:** November 26, 2025
**Source:** UniFi Network API v10.0.160
