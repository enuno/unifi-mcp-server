# UniFi Network API Reference

## Overview

This document provides a comprehensive reference for the UniFi Network API, covering all available endpoints, authentication requirements, filtering capabilities, and error handling patterns. The API enables programmatic access to UniFi network infrastructure for automation, monitoring, and management.

## Base URL

```
https://{GATEWAY_HOST}:{GATEWAY_PORT}/integration/v1
```

## Authentication

All API requests require Bearer token authentication using an API token generated from the UniFi console:

```
Authorization: Bearer {API_TOKEN}
Content-Type: application/json
```

**Generate API Token:**

1. Navigate to `https://unifi.ui.com`
2. Go to **Settings → Control Plane → Integrations**
3. Click **Create API Key**
4. Store the token securely

## Common Query Parameters

Most list endpoints support the following query parameters:

- `offset` (integer): Starting position for pagination (default: 0)
- `limit` (integer): Maximum number of results to return (default: 200)
- `filter` (string): Filter expression using structured query syntax

---

## API Endpoints by Category

### 1. About Application

#### Get Application Information

**`GET /application/info`**

Retrieve general information about the UniFi Network application instance.

**Response:**

- Application version
- System capabilities
- Deployment metadata

---

### 2. Sites

#### List Sites

**`GET /sites`**

Retrieve a paginated list of local sites configured in the UniFi controller.

**Query Parameters:**

- `offset`, `limit`, `filter`

**Response:**

- Array of site objects containing site ID, name, description, and configuration

---

### 3. UniFi Devices

#### List Pending Devices

**`GET /sites/{siteId}/devices/pending`**

Retrieve devices awaiting adoption on the specified site.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Response:**

- Paginated list of unadopted devices with MAC address, model, firmware version

#### List Adopted Devices

**`GET /sites/{siteId}/devices/adopted`**

List all devices currently adopted on the site.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Query Parameters:**

- `offset`, `limit`, `filter`

**Response:**

- Array of adopted device objects with full configuration and status

#### Get Device Details

**`GET /sites/{siteId}/devices/adopted/{deviceId}`**

Retrieve detailed information for a specific adopted device.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `deviceId` (string, required): Device identifier

**Response:**

- Complete device configuration, status, statistics, and metadata

#### Adopt Device

**`POST /sites/{siteId}/devices/{deviceId}/adopt`**

Adopt a pending device onto the specified site.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `deviceId` (string, required): Device identifier to adopt

**Request Body:**

```json
{
  "name": "Optional device name"
}
```

**Response:**

- 200 OK on successful adoption
- Device object with updated adoption status

#### Execute Device Action

**`POST /sites/{siteId}/devices/adopted/{deviceId}/action`**

Perform administrative actions on an adopted device (e.g., restart, upgrade, locate).

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `deviceId` (string, required): Device identifier

**Request Body:**

```json
{
  "action": "restart",
  "params": {}
}
```

**Common Actions:**

- `restart`: Reboot the device
- `upgrade`: Initiate firmware upgrade
- `locate`: Enable LED identification
- `provision`: Force device provisioning

#### Execute Port Action

**`POST /sites/{siteId}/devices/{deviceId}/ports/{portIdx}/action`**

Perform actions on a specific port of a device (e.g., power cycle PoE port).

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `deviceId` (string, required): Device identifier
- `portIdx` (integer, required): Port index number

**Request Body:**

```json
{
  "action": "power-cycle",
  "params": {}
}
```

**Common Port Actions:**

- `power-cycle`: PoE power cycle
- `enable`: Enable port
- `disable`: Disable port

---

### 4. Clients

#### List Clients

**`GET /sites/{siteId}/clients`**

List all connected clients on the specified site.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Query Parameters:**

- `offset`, `limit`, `filter`

**Response:**

- Array of client objects with connection details, MAC address, IP, hostname, usage statistics

#### Get Client Details

**`GET /sites/{siteId}/clients/{clientId}`**

Retrieve detailed information for a specific connected client.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `clientId` (string, required): Client identifier (typically MAC address)

**Response:**

- Complete client information including network assignment, connection quality, bandwidth usage

#### Execute Client Action

**`POST /sites/{siteId}/clients/{clientId}/action`**

Execute administrative actions on a client (authorize guest, limit bandwidth, block, reconnect).

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `clientId` (string, required): Client identifier

**Request Body:**

```json
{
  "action": "authorize-guest",
  "params": {
    "duration": 3600
  }
}
```

**Common Client Actions:**

- `authorize-guest`: Grant guest network access
- `block`: Block client access
- `unblock`: Unblock client
- `reconnect`: Force client reconnection
- `limit-bandwidth`: Apply bandwidth restrictions

---

### 5. Hotspot Vouchers

#### List Vouchers

**`GET /sites/{siteId}/vouchers`**

Retrieve all hotspot vouchers for the site.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Query Parameters:**

- `offset`, `limit`, `filter`

**Response:**

- Array of voucher objects with code, usage status, expiration

#### Create Vouchers

**`POST /sites/{siteId}/vouchers`**

Generate new hotspot vouchers for guest access.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Request Body:**

```json
{
  "count": 10,
  "duration": 86400,
  "uploadLimit": 1024,
  "downloadLimit": 10240
}
```

**Response:**

- Array of generated voucher codes

#### Bulk Delete Vouchers

**`DELETE /sites/{siteId}/vouchers`**

Remove multiple vouchers using a filter expression.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Query Parameters:**

- `filter`: Filter expression to select vouchers for deletion

#### Get Voucher Details

**`GET /sites/{siteId}/vouchers/{voucherId}`**

Retrieve details for a specific voucher.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `voucherId` (string, required): Voucher identifier

#### Delete Voucher

**`DELETE /sites/{siteId}/vouchers/{voucherId}`**

Remove a specific voucher.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `voucherId` (string, required): Voucher identifier

---

### 6. Firewall

#### List Firewall Zones

**`GET /sites/{siteId}/firewall/zones`**

List all firewall zones configured on the site.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Response:**

- Array of firewall zone objects with network assignments and policies

#### Create Firewall Zone

**`POST /sites/{siteId}/firewall/zones`**

Create a new custom firewall zone.

**Path Parameters:**

- `siteId` (string, required): Site identifier

**Request Body:**

```json
{
  "name": "DMZ",
  "description": "Demilitarized Zone",
  "networks": ["network-id-1"]
}
```

#### Update Firewall Zone

**`PUT /sites/{siteId}/firewall/zones/{firewallZoneId}`**

Update an existing custom firewall zone.

**Path Parameters:**

- `siteId` (string, required): Site identifier
- `firewallZoneId` (string, required): Firewall zone identifier

**Request Body:**

```json
{
  "name": "Updated DMZ",
  "networks": ["network-id-1", "network-id-2"]
}
```

> **Note:** Enhanced firewall policy management APIs are coming soon.

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
