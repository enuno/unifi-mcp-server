# UniFi Network API Reference (v10.0.156)

## Overview

This document provides a comprehensive reference for the UniFi Network API version 10.0.156, covering all available endpoints, authentication requirements, filtering capabilities, and error handling patterns. The API enables programmatic access to UniFi network infrastructure for automation, monitoring, and management.

Each UniFi Application has its own API endpoints running locally on each site, offering detailed analytics and control related to that specific application. For a single endpoint with high-level insights across all your UniFi sites, refer to the [UniFi Site Manager API](https://developer.ui.com/).

## Base URL

```
https://{GATEWAY_HOST}:{GATEWAY_PORT}/integration/v1
```

For local gateway API access:
```
https://{GATEWAY_HOST}:{GATEWAY_PORT}/proxy/network/api
```

## Authentication

All API requests require Bearer token authentication using an API token generated from the UniFi console:

```
Authorization: Bearer {API_TOKEN}
Content-Type: application/json
```

**Generate API Token:**

1. Navigate to `https://unifi.ui.com` (for cloud API) or your local UniFi application
2. Go to **Settings → Control Plane → Integrations**
3. Click **Create API Key**
4. Store the token securely - it will only be displayed once

## Common Query Parameters

Most list endpoints support the following query parameters:

- `offset` (integer): Starting position for pagination (default: 0, minimum: 0)
- `limit` (integer): Maximum number of results to return (default: 25, range: 0-200)
- `filter` (string): Filter expression using structured query syntax

---

## Filtering

Explains how to use the filter query parameter for advanced querying across list endpoints, including supported property types, syntax, and operators.

Some `GET` and `DELETE` endpoints support filtering using the `filter` query parameter. Each endpoint supporting filtering will have a detailed list of filterable properties, their types, and allowed functions.

### Filtering Syntax

Filtering follows a structured, URL-safe syntax with three types of expressions.

#### 1. Property Expressions

Apply functions to an individual property using the form `.<function>(<args>)`, where argument values are separated by commas.

Examples:
- `id.eq(123)` checks if `id` is equal to `123`
- `name.isNotNull()` checks if `name` is not null
- `createdAt.in(2025-01-01, 2025-01-05)` checks if `createdAt` is either `2025-01-01` or `2025-01-05`

#### 2. Compound Expressions

Combine two or more expressions with logical operators using the form `<operator>(<expressions>)`, where expressions are separated by commas.

Examples:
- `and(name.isNull(), createdAt.gt(2025-01-01))` checks if `name` is null **and** `createdAt` is greater than `2025-01-01`
- `or(name.isNull(), expired.isNull(), expiresAt.isNull())` checks if **any** of `name`, `expired`, or `expiresAt` is null

#### 3. Negation Expressions

Negate any other expressions using the form `not(<expression>)`.

Example:
- `not(name.like('guest*'))` matches all values except those that start with `guest`

### Filterable Property Types

| Type | Examples | Syntax |
|------|----------|--------|
| `STRING` | `'Hello, ''World''!'` | Must be wrapped in single quotes. To escape a single quote, use another single quote. |
| `INTEGER` | `123` | Must start with a digit. |
| `DECIMAL` | `123`, `123.321` | Must start with a digit. Can include a decimal point (.). |
| `TIMESTAMP` | `2025-01-29`, `2025-01-29T12:39:11Z` | Must follow ISO 8601 format (date or date-time). |
| `BOOLEAN` | `true`, `false` | Can be `true` or `false`. |
| `UUID` | `550e8400-e29b-41d4-a716-44665544000` | Must be a valid UUID format (8-4-4-4-12). |
| `SET(...)` | `[1, 2, 3, 4, 5]` | A set of (unique) values. |

### Filtering Functions

| Function | Arguments | Semantics | Supported Property Types |
|----------|-----------|-----------|-------------------------|
| `isNull` | 0 | is null | all types |
| `isNotNull` | 0 | is not null | all types |
| `eq` | 1 | equals | `STRING`, `INTEGER`, `DECIMAL`, `TIMESTAMP`, `BOOLEAN`, `UUID` |
| `ne` | 1 | not equals | `STRING`, `INTEGER`, `DECIMAL`, `TIMESTAMP`, `BOOLEAN`, `UUID` |
| `gt` | 1 | greater than | `STRING`, `INTEGER`, `DECIMAL`, `TIMESTAMP`, `UUID` |
| `ge` | 1 | greater than or equals | `STRING`, `INTEGER`, `DECIMAL`, `TIMESTAMP`, `UUID` |
| `lt` | 1 | less than | `STRING`, `INTEGER`, `DECIMAL`, `TIMESTAMP`, `UUID` |
| `le` | 1 | less than or equals | `STRING`, `INTEGER`, `DECIMAL`, `TIMESTAMP`, `UUID` |
| `like` | 1 | matches pattern | `STRING` |
| `in` | 1 or more | one of | `STRING`, `INTEGER`, `DECIMAL`, `TIMESTAMP`, `UUID` |
| `notIn` | 1 or more | not one of | `STRING`, `INTEGER`, `DECIMAL`, `TIMESTAMP`, `UUID` |
| `isEmpty` | 0 | is empty | `SET` |
| `contains` | 1 | contains | `SET` |
| `containsAny` | 1 or more | contains any of | `SET` |
| `containsAll` | 1 or more | contains all of | `SET` |
| `containsExactly` | 1 or more | contains exactly | `SET` |

#### Pattern Matching (`like` Function)

- `.` matches any **single** character. Example: `type.like('type.')` matches `type1`, but not `type100`
- `*` matches **any number** of characters. Example: `name.like('guest*')` matches `guest1` and `guest100`
- `\` is used to escape `.` and `*`

---

## Error Handling

Describes the standard API error response structure, including error codes, status names, and troubleshooting guidance.

### Error Message Schema

| Field | Type | Description |
|-------|------|-------------|
| `statusCode` | integer | HTTP status code |
| `statusName` | string | Status name |
| `code` | string | Error code |
| `message` | string | Error message |
| `timestamp` | string | ISO 8601 timestamp |
| `requestPath` | string | Request path |
| `requestId` | string | Request ID (useful for tracking Internal Server Errors) |

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

## API Endpoints by Category

### 1. Application Info

#### Get Application Info

**`GET /v1/info`**

Retrieve general information about the UniFi Network application.

**Response:** `200 OK`

```json
{
  "applicationVersion": "9.1.0"
}
```

---

### 2. Sites

#### List Local Sites

**`GET /v1/sites`**

Retrieve a paginated list of local sites managed by this Network application. Site ID is required for other UniFi Network API calls.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `offset` | number | 0 | >= 0 |
| `limit` | number | 25 | [0..200] |
| `filter` | string | - | Filter expression |

**Response:** `200 OK`

```json
{
  "offset": 0,
  "limit": 25,
  "count": 10,
  "totalCount": 1000,
  "data": [...]
}
```

---

### 3. UniFi Devices

Endpoints to list, inspect, and interact with UniFi devices, including adopted and pending devices. Provides device stats, port control, and actions.

#### List Devices Pending Adoption

**`GET /v1/pending-devices`**

Retrieve a paginated list of devices pending adoption.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `offset` | number | 0 | >= 0 |
| `limit` | number | 25 | [0..200] |

**Response:** `200 OK`

#### List Adopted Devices

**`GET /v1/sites/{siteId}/devices`**

Retrieve a paginated list of all adopted devices on a site.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

#### Get Adopted Device Details

**`GET /v1/sites/{siteId}/devices/{deviceId}`**

Retrieve detailed information about a specific adopted device.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string | Yes |
| `deviceId` | string | Yes |

**Response:** `200 OK`

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "macAddress": "94:2a:6f:26:c6:ca",
  "ipAddress": "192.168.1.55",
  "name": "IW HD",
  "model": "UHDIW",
  "supported": true,
  "state": "ONLINE",
  "firmwareVersion": "6.6.55",
  "firmwareUpdatable": true,
  "adoptedAt": "2019-08-24T14:15:22Z",
  "provisionedAt": "2019-08-24T14:15:22Z",
  "configurationId": "7596498d2f367dc2",
  "uplink": {
    "deviceId": "4de4adb9-21ee-47e3-aeb4-8cf8ed6c109a"
  },
  "features": {
    "switching": null,
    "accessPoint": null
  },
  "interfaces": {
    "ports": [...],
    "radios": [...]
  }
}
```

#### Get Latest Adopted Device Statistics

**`GET /v1/sites/{siteId}/devices/{deviceId}/statistics/latest`**

Retrieve the latest real-time statistics of a specific adopted device.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string | Yes |
| `deviceId` | string | Yes |

**Response:** `200 OK`

```json
{
  "uptimeSec": 0,
  "lastHeartbeatAt": "2019-08-24T14:15:22Z",
  "nextHeartbeatAt": "2019-08-24T14:15:22Z",
  "loadAverage1Min": 0.1,
  "loadAverage5Min": 0.1,
  "loadAverage15Min": 0.1,
  "cpuUtilizationPct": 0.1,
  "memoryUtilizationPct": 0.1,
  "uplink": {
    "txRateBps": 0,
    "rxRateBps": 0
  },
  "interfaces": {
    "radios": [...]
  }
}
```

#### Execute Adopted Device Action

**`POST /v1/sites/{siteId}/devices/{deviceId}/actions`**

Perform an action on a specific adopted device.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string | Yes |
| `deviceId` | string | Yes |

**Request Body:**

```json
{
  "action": "RESTART"
}
```

**Response:** `200 OK`

**Common Actions:**

- `RESTART`: Reboot the device
- `UPGRADE`: Initiate firmware upgrade
- `LOCATE`: Enable LED identification
- `PROVISION`: Force device provisioning

#### Execute Port Action

**`POST /v1/sites/{siteId}/devices/{deviceId}/interfaces/ports/{portIdx}/actions`**

Perform an action on a specific device port.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `portIdx` | integer | Yes |
| `siteId` | string | Yes |
| `deviceId` | string | Yes |

**Request Body:**

```json
{
  "action": "POWER_CYCLE"
}
```

**Response:** `200 OK`

**Common Port Actions:**

- `POWER_CYCLE`: PoE power cycle
- `ENABLE`: Enable port
- `DISABLE`: Disable port

---

### 4. Clients

Endpoints for viewing and managing connected clients (wired, wireless, VPN, and guest). Supports actions such as authorizing or unauthorizing guest access.

#### List Connected Clients

**`GET /v1/sites/{siteId}/clients`**

Retrieve a paginated list of all connected clients on a site.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 |
| `filter` | string | - |

**Response:** `200 OK`

#### Get Connected Client Details

**`GET /v1/sites/{siteId}/clients/{clientId}`**

Retrieve detailed information about a specific connected client.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `clientId` | string | Yes |
| `siteId` | string | Yes |

**Response:** `200 OK`

#### Execute Client Action

**`POST /v1/sites/{siteId}/clients/{clientId}/actions`**

Perform an action on a specific connected client.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `clientId` | string | Yes |
| `siteId` | string | Yes |

**Request Body:**

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | `AUTHORIZE_GUEST_ACCESS` or `UNAUTHORIZE_GUEST_ACCESS` |
| `timeLimitMinutes` | integer | [1..1000] - How long (in minutes) the guest will be authorized |
| `dataUsageLimitMBytes` | integer | [1..1048576] - Data usage limit in megabytes |
| `rxRateLimitKbps` | integer | [2..1000] - Download rate limit in kbps |
| `txRateLimitKbps` | integer | [2..1000] - Upload rate limit in kbps |

**Response:** `200 OK`

---

### 5. Hotspot

Endpoints for managing guest access via Hotspot vouchers — create, list, or revoke vouchers and track their usage and expiration.

#### List Vouchers

**`GET /v1/sites/{siteId}/hotspot/vouchers`**

Retrieve a paginated list of Hotspot vouchers.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 100 (max 1000) |
| `filter` | string | - |

**Response:** `200 OK`

#### Generate Vouchers

**`POST /v1/sites/{siteId}/hotspot/vouchers`**

Create one or more Hotspot vouchers.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string | Yes |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `count` | integer | No | [1..1000], Default: 1. Number of vouchers to generate |
| `name` | string | Yes | Voucher note, duplicated across all generated vouchers |
| `authorizedGuestLimit` | integer | No | >= 1. Limit for how many different guests can use the same voucher |
| `timeLimitMinutes` | integer | Yes | [1..1000]. How long (in minutes) the voucher provides network access |
| `dataUsageLimitMBytes` | integer | No | [1..1048576]. Data usage limit in megabytes |
| `rxRateLimitKbps` | integer | No | [2..1000]. Download rate limit in kbps |
| `txRateLimitKbps` | integer | No | [2..1000]. Upload rate limit in kbps |

**Response:** `201 Created`

#### Delete Vouchers

**`DELETE /v1/sites/{siteId}/hotspot/vouchers`**

Remove Hotspot vouchers based on the specified filter criteria.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string | Yes |

**Query Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `filter` | string | Yes |

**Response:** `200 OK`

```json
{
  "vouchersDeleted": 0
}
```

#### Get Voucher Details

**`GET /v1/sites/{siteId}/hotspot/vouchers/{voucherId}`**

Retrieve details of a specific Hotspot voucher.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `voucherId` | string | Yes |
| `siteId` | string | Yes |

**Response:** `200 OK`

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "createdAt": "2019-08-24T14:15:22Z",
  "name": "hotel-guest",
  "code": 4861409510,
  "authorizedGuestLimit": 1,
  "authorizedGuestCount": 0,
  "activatedAt": "2019-08-24T14:15:22Z",
  "expiresAt": "2019-08-24T14:15:22Z",
  "expired": true,
  "timeLimitMinutes": 1440,
  "dataUsageLimitMBytes": 1024,
  "rxRateLimitKbps": 1000,
  "txRateLimitKbps": 1000
}
```

#### Delete Voucher

**`DELETE /v1/sites/{siteId}/hotspot/vouchers/{voucherId}`**

Remove a specific Hotspot voucher.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `voucherId` | string | Yes |
| `siteId` | string | Yes |

**Response:** `200 OK`

```json
{
  "vouchersDeleted": 0
}
```

---

### 6. Firewall

Endpoints for managing custom firewall zones and policies within a site. Define or update network segmentation and security boundaries.

#### List Firewall Zones

**`GET /v1/sites/{siteId}/firewall/zones`**

Retrieve a list of all firewall zones on a site.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string | Yes |

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `offset` | number | 0 |
| `limit` | number | 25 (max 200) |
| `filter` | string | - |

**Response:** `200 OK`

#### Create Custom Firewall Zone

**`POST /v1/sites/{siteId}/firewall/zones`**

Create a new custom firewall zone on a site.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `siteId` | string | Yes |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Name of a firewall zone |
| `networkIds` | array | Yes | >= 0 items. List of Network IDs |

**Request Sample:**
```json
{
  "name": "Hotspot|My custom zone",
  "networkIds": ["dfb21062-8ea0-4dca-b1d8-1eb3da00e58b"]
}
```

**Response:** `201 Created`

#### Get Firewall Zone

**`GET /v1/sites/{siteId}/firewall/zones/{firewallZoneId}`**

Get a firewall zone on a site.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `firewallZoneId` | string | Yes |
| `siteId` | string | Yes |

**Response:** `200 OK`

```json
{
  "id": "ffcdb32c-6278-4364-8947-df4f77118df8",
  "name": "Hotspot|My custom zone",
  "networkIds": ["dfb21062-8ea0-4dca-b1d8-1eb3da00e58b"],
  "metadata": {
    "origin": "string"
  }
}
```

#### Update Firewall Zone

**`PUT /v1/sites/{siteId}/firewall/zones/{firewallZoneId}`**

Update a firewall zone on a site.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `firewallZoneId` | string | Yes |
| `siteId` | string | Yes |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Name of a firewall zone |
| `networkIds` | array | Yes | >= 0 items. List of Network IDs |

**Response:** `200 OK`

#### Delete Custom Firewall Zone

**`DELETE /v1/sites/{siteId}/firewall/zones/{firewallZoneId}`**

Delete a custom firewall zone from a site.

**Path Parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `firewallZoneId` | string | Yes |
| `siteId` | string | Yes |

**Response:** `200 OK`

---

### 7. Deep Packet Inspection (DPI)

#### List DPI Categories

**`GET /dpi/categories`**

Retrieve all available DPI application categories.

**Response:**

- Array of category objects with category ID, name, and description

#### List DPI Applications

**`GET /dpi/applications`**

List all DPI-identifiable applications.

**Query Parameters:**

- `offset`, `limit`, `filter`

**Response:**

- Array of application objects with app ID, name, category, and traffic classification rules

---

### 8. Country Information

#### Get Country List

**`GET /countries`**

Retrieve a list of all known countries for configuration and localization.

**Response:**

- Array of country objects with ISO codes, names, and regulatory information

---

### 9. Networks (VLANs)

#### List Networks

**`GET /sites/{siteId}/networks`**

List all configured networks (VLANs) on the site.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Query Parameters:**

- `offset`, `limit`, `filter`

**Response:**

- Array of network objects with VLAN ID, IP ranges, DHCP settings, and firewall zone assignments

#### Get Network Details

**`GET /sites/{siteId}/networks/{networkId}`**

Retrieve details for a specific network.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `networkId` (string, required): Network identifier

#### Create Network

**`POST /sites/{siteId}/networks`**

Create a new network (VLAN) on the site.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Request Body:**

```json
{
  "name": "Guest Network",
  "vlan": 10,
  "subnet": "192.168.10.0/24",
  "dhcpEnabled": true,
  "dhcpRange": {
    "start": "192.168.10.10",
    "end": "192.168.10.250"
  }
}
```

#### Update Network

**`PUT /sites/{siteId}/networks/{networkId}`**

Update an existing network configuration.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `networkId` (string, required): Network identifier

**Request Body:**

- Network configuration object (partial updates supported)

#### Delete Network

**`DELETE /sites/{siteId}/networks/{networkId}`**

Remove a network from the site.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `networkId` (string, required): Network identifier

**Query Parameters:**

- `cascade` (boolean): If true, also remove dependent configurations

---

### 10. Access Control Lists (ACLs)

#### List ACL Rules

**`GET /sites/{siteId}/acls`**

List all ACL rules configured for the site.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Query Parameters:**

- `offset`, `limit`, `filter`

**Response:**

- Array of ACL rule objects with source, destination, action, and priority

#### Get ACL Rule Details

**`GET /sites/{siteId}/acls/{aclRuleId}`**

Retrieve details for a specific ACL rule.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `aclRuleId` (string, required): ACL rule identifier

#### Create ACL Rule

**`POST /sites/{siteId}/acls`**

Create a new Access Control List rule.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Request Body:**

```json
{
  "name": "Block Social Media",
  "enabled": true,
  "action": "deny",
  "sourceType": "network",
  "sourceId": "guest-network-id",
  "destinationType": "dpi-category",
  "destinationId": "social-media-category-id",
  "priority": 100
}
```

#### Update ACL Rule

**`PUT /sites/{siteId}/acls/{aclRuleId}`**

Update an existing ACL rule.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `aclRuleId` (string, required): ACL rule identifier

**Request Body:**

- ACL rule configuration object (partial updates supported)

#### Delete ACL Rule

**`DELETE /sites/{siteId}/acls/{aclRuleId}`**

Remove an ACL rule from the site.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `aclRuleId` (string, required): ACL rule identifier

---

### 11. WAN Connections

#### List WAN Connections

**`GET /sites/{siteId}/wans`**

List all WAN interfaces and connections configured on the site.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Response:**

- Array of WAN connection objects with interface details, connection status, IP addresses, and statistics

---

## Filtering & Error Handling

### Filter Syntax

The `filter` query parameter supports structured filtering using a type-safe syntax:

```
filter=status eq 'online'
filter=vlan gt 10 and vlan lt 100
filter=name contains 'guest'
```

**Supported Operators:**

- `eq`: Equal
- `ne`: Not equal
- `gt`: Greater than
- `lt`: Less than
- `gte`: Greater than or equal
- `lte`: Less than or equal
- `contains`: String contains
- `startswith`: String starts with
- `and`: Logical AND
- `or`: Logical OR

### Error Response Structure

All API errors return a standardized JSON response:

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

**Common Error Codes:**

| Status Code | Status Name | Description |
|-------------|-------------|-------------|
| 400 | BAD_REQUEST | Invalid request parameters or body |
| 401 | UNAUTHORIZED | Missing or invalid authentication |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT_FOUND | Resource does not exist |
| 409 | CONFLICT | Resource conflict (e.g., duplicate VLAN ID) |
| 422 | UNPROCESSABLE_ENTITY | Validation failure |
| 429 | TOO_MANY_REQUESTS | Rate limit exceeded |
| 500 | INTERNAL_SERVER_ERROR | Server error |
| 503 | SERVICE_UNAVAILABLE | Service temporarily unavailable |

---

## API Enhancements

### Improved Filtering Options

- Flexible, type-safe filtering through structured query parameter syntax
- Support for complex Boolean expressions
- Field-specific filtering capabilities

### Improved Error Reporting

- Standardized error response schema across all endpoints
- Unique request IDs for troubleshooting
- Detailed error codes and messages
- ISO 8601 timestamps

### Pagination Support

- Consistent pagination using `offset` and `limit` parameters
- Total count metadata in list responses
- Efficient handling of large result sets

---

## Additional Resources

For complete schema definitions, request/response examples, and interactive testing:

- Access the in-app Swagger/OpenAPI documentation at `https://{GATEWAY_HOST}:{GATEWAY_PORT}/docs`
- Review official UniFi developer documentation at `https://developer.ui.com`

---

## Notes

- All timestamps use ISO 8601 format
- All endpoints require valid API token authentication
- Rate limiting applies per API token
- Mutating operations should implement confirmation flags in MCP server implementations
- The API is under active development; check changelog for updates
