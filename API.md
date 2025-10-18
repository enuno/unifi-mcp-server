# UniFi MCP Server API Documentation

This document provides comprehensive documentation for the Model Context Protocol (MCP) server that exposes UniFi Network Controller functionality. The server enables AI agents and other applications to interact with UniFi network infrastructure in a standardized way.

## Table of Contents

- [Overview](#overview)
- [Configuration](#configuration)
- [Authentication](#authentication)
- [MCP Tools](#mcp-tools)
- [MCP Resources](#mcp-resources)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)

## Overview

The UniFi MCP Server bridges the gap between AI applications and UniFi Network Controllers by exposing network management capabilities as MCP tools and resources. It handles authentication, request formatting, and error handling, providing a clean interface for network automation.

### Architecture

```
┌─────────────────┐
│  AI Application │
│  (Claude, etc.) │
└────────┬────────┘
         │ MCP Protocol
         │
┌────────▼────────┐
│   UniFi MCP     │
│     Server      │
└────────┬────────┘
         │ UniFi API
         │
┌────────▼────────┐
│  UniFi Network  │
│   Controller    │
└─────────────────┘
```

### Key Features

- **Device Management:** List, configure, and monitor UniFi devices
- **Network Configuration:** Manage networks, VLANs, and subnets
- **Client Information:** Query connected clients and their status
- **Firewall Rules:** Create and manage firewall rules
- **Site Management:** Work with multiple UniFi sites
- **Real-time Monitoring:** Access device and network statistics

## Configuration

### Environment Variables

Configure the MCP server using environment variables:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `UNIFI_API_KEY` | UniFi API Key from unifi.ui.com | Yes | - |
| `UNIFI_API_TYPE` | API type: `cloud` or `local` | No | `cloud` |
| `UNIFI_HOST` | API host (cloud: api.ui.com, local: gateway IP) | No | `api.ui.com` |
| `UNIFI_PORT` | API port | No | `443` |
| `UNIFI_VERIFY_SSL` | Verify SSL certificates | No | `true` |
| `UNIFI_SITE` | Default site ID | No | `default` |
| `UNIFI_RATE_LIMIT` | Max requests per minute | No | `100` |
| `UNIFI_TIMEOUT` | Request timeout (seconds) | No | `30` |
| `UNIFI_MAX_RETRIES` | Maximum retry attempts | No | `3` |
| `MCP_SERVER_PORT` | MCP server port | No | `3000` |
| `MCP_LOG_LEVEL` | Logging level | No | `INFO` |

### Configuration File

Alternatively, use a `config.yaml` file:

```yaml
unifi:
  api_key: your-api-key-here
  api_type: cloud  # or 'local'
  host: api.ui.com  # or gateway IP for local
  port: 443
  verify_ssl: true
  site: default
  rate_limit: 100
  timeout: 30
  max_retries: 3

mcp:
  server_port: 3000
  log_level: INFO
```

**Note:** Environment variables take precedence over configuration file settings.

## Authentication

### Obtaining Your API Key

The UniFi MCP Server uses the official UniFi Cloud API with API key authentication:

1. **Login** to [UniFi Site Manager](https://unifi.ui.com)
2. **Navigate** to Settings → Control Plane → Integrations
3. **Create** a new API Key by clicking "Create API Key"
4. **Save** the key immediately - it's only displayed once!
5. **Store** the key securely in environment variables or secret management

### Authentication Method

The server uses **stateless API key authentication** via the `X-API-Key` HTTP header:

```http
GET /v1/sites HTTP/1.1
Host: api.ui.com
X-API-Key: your-api-key-here
Accept: application/json
```

No session management or cookie handling is required. Each request is independently authenticated.

### API Access Modes

**Cloud API (Recommended)**
- Base URL: `https://api.ui.com/v1/`
- Access cloud-hosted UniFi instances
- Requires internet connectivity
- SSL verification recommended

**Local Gateway Proxy**
- Base URL: `https://{gateway-ip}:{port}/proxy/network/integration`
- Access local UniFi gateway directly
- Works without internet
- May require SSL verification disabled for self-signed certificates

### Current Limitations

- **Read-Only Access**: The Early Access API is currently read-only. Write operations will be available in future API versions and will require manual key updates.
- **Rate Limiting**: See [Rate Limiting](#rate-limiting) section below

### Security Considerations

- **Never hardcode API keys** in your code
- Store API keys in environment variables or secure secret management systems (AWS Secrets Manager, HashiCorp Vault, etc.)
- Use HTTPS when connecting to the UniFi API (especially for cloud)
- Implement proper access controls for MCP server access
- **Rotate keys regularly** - API keys can be regenerated from unifi.ui.com
- Monitor API key usage for suspicious activity
- Treat API keys like passwords - they provide full access to your UniFi environment

## MCP Tools

Tools are executable functions that perform actions on the UniFi Controller.

### Tool Categories

- **Phase 3 Tools:** Read-only operations for querying network information
- **Phase 4 Tools:** Mutating operations with safety mechanisms (confirm + dry-run)

### Health Check

#### `health_check`

Verify the MCP server is running and accessible.

**Parameters:** None

**Returns:**
Server health status information.

**Example:**
```python
result = await mcp.call_tool("health_check", {})
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "api_type": "cloud"
}
```

### Device Management Tools

#### `get_device_details`

Get detailed information for a specific device.

**Parameters:**
- `site_id` (string, required): Site identifier
- `device_id` (string, required): Device ID

**Returns:**
Object containing detailed device information.

**Example:**
```python
result = await mcp.call_tool("get_device_details", {
    "site_id": "default",
    "device_id": "507f1f77bcf86cd799439011"
})
```

**Response:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "Living Room AP",
  "model": "U6-LR",
  "type": "uap",
  "mac": "aa:bb:cc:dd:ee:ff",
  "ip": "192.168.1.100",
  "state": 1,
  "uptime": 86400,
  "version": "6.5.55.14277"
}
```

#### `get_device_statistics`

Retrieve real-time statistics for a device.

**Parameters:**
- `site_id` (string, required): Site identifier
- `device_id` (string, required): Device ID

**Returns:**
Object containing device statistics.

**Example:**
```python
result = await mcp.call_tool("get_device_statistics", {
    "site_id": "default",
    "device_id": "507f1f77bcf86cd799439011"
})
```

**Response:**
```json
{
  "device_id": "507f1f77bcf86cd799439011",
  "uptime": 86400,
  "cpu": 15,
  "mem": 42,
  "tx_bytes": 1024000000,
  "rx_bytes": 2048000000,
  "bytes": 3072000000,
  "state": 1,
  "uplink_depth": 0
}
```

#### `list_devices_by_type`

Filter devices by type (AP, switch, gateway).

**Parameters:**
- `site_id` (string, required): Site identifier
- `device_type` (string, required): Device type filter (uap, usw, ugw, udm, uxg, etc.)

**Returns:**
Array of device objects matching the type.

**Example:**
```python
result = await mcp.call_tool("list_devices_by_type", {
    "site_id": "default",
    "device_type": "uap"
})
```

#### `search_devices`

Search devices by name, MAC, or IP address.

**Parameters:**
- `site_id` (string, required): Site identifier
- `query` (string, required): Search query string

**Returns:**
Array of matching device objects.

**Example:**
```python
result = await mcp.call_tool("search_devices", {
    "site_id": "default",
    "query": "office"
})
```

### Client Management Tools

#### `get_client_details`

Get detailed information for a specific client.

**Parameters:**
- `site_id` (string, required): Site identifier
- `client_mac` (string, required): Client MAC address

**Returns:**
Object containing detailed client information.

**Example:**
```python
result = await mcp.call_tool("get_client_details", {
    "site_id": "default",
    "client_mac": "aa:bb:cc:dd:ee:01"
})
```

**Response:**
```json
{
  "mac": "aa:bb:cc:dd:ee:01",
  "hostname": "laptop-001",
  "ip": "192.168.1.100",
  "is_wired": false,
  "signal": -45,
  "tx_bytes": 1024000,
  "rx_bytes": 2048000
}
```

#### `get_client_statistics`

Retrieve bandwidth and connection statistics for a client.

**Parameters:**
- `site_id` (string, required): Site identifier
- `client_mac` (string, required): Client MAC address

**Returns:**
Object containing client statistics.

**Example:**
```python
result = await mcp.call_tool("get_client_statistics", {
    "site_id": "default",
    "client_mac": "aa:bb:cc:dd:ee:01"
})
```

**Response:**
```json
{
  "mac": "aa:bb:cc:dd:ee:01",
  "tx_bytes": 1024000,
  "rx_bytes": 2048000,
  "tx_packets": 15000,
  "rx_packets": 20000,
  "tx_rate": 150000,
  "rx_rate": 200000,
  "signal": -45,
  "rssi": 55,
  "noise": -90,
  "uptime": 3600,
  "is_wired": false
}
```

#### `list_active_clients`

List currently connected clients.

**Parameters:**
- `site_id` (string, required): Site identifier

**Returns:**
Array of active client objects.

**Example:**
```python
result = await mcp.call_tool("list_active_clients", {
    "site_id": "default"
})
```

#### `search_clients`

Search clients by MAC, IP, or hostname.

**Parameters:**
- `site_id` (string, required): Site identifier
- `query` (string, required): Search query string

**Returns:**
Array of matching client objects.

**Example:**
```python
result = await mcp.call_tool("search_clients", {
    "site_id": "default",
    "query": "laptop"
})
```

### Network Information Tools

#### `get_network_details`

Get detailed network configuration.

**Parameters:**
- `site_id` (string, required): Site identifier
- `network_id` (string, required): Network ID

**Returns:**
Object containing network configuration.

**Example:**
```python
result = await mcp.call_tool("get_network_details", {
    "site_id": "default",
    "network_id": "507f191e810c19729de860ea"
})
```

**Response:**
```json
{
  "id": "507f191e810c19729de860ea",
  "name": "LAN",
  "purpose": "corporate",
  "vlan_id": 1,
  "ip_subnet": "192.168.1.0/24",
  "dhcpd_enabled": true
}
```

#### `list_vlans`

List all VLANs in a site.

**Parameters:**
- `site_id` (string, required): Site identifier

**Returns:**
Array of VLAN/network objects.

**Example:**
```python
result = await mcp.call_tool("list_vlans", {
    "site_id": "default"
})
```

#### `get_subnet_info`

Get subnet and DHCP information for a network.

**Parameters:**
- `site_id` (string, required): Site identifier
- `network_id` (string, required): Network ID

**Returns:**
Object containing subnet and DHCP configuration.

**Example:**
```python
result = await mcp.call_tool("get_subnet_info", {
    "site_id": "default",
    "network_id": "507f191e810c19729de860ea"
})
```

**Response:**
```json
{
  "network_id": "507f191e810c19729de860ea",
  "name": "LAN",
  "ip_subnet": "192.168.1.0/24",
  "vlan_id": 1,
  "dhcpd_enabled": true,
  "dhcpd_start": "192.168.1.100",
  "dhcpd_stop": "192.168.1.254",
  "dhcpd_leasetime": 86400,
  "dhcpd_dns_1": "8.8.8.8",
  "dhcpd_dns_2": "8.8.4.4",
  "dhcpd_gateway": "192.168.1.1",
  "domain_name": "local"
}
```

#### `get_network_statistics`

Retrieve network usage statistics for a site.

**Parameters:**
- `site_id` (string, required): Site identifier

**Returns:**
Object containing network statistics across all networks.

**Example:**
```python
result = await mcp.call_tool("get_network_statistics", {
    "site_id": "default"
})
```

**Response:**
```json
{
  "site_id": "default",
  "networks": [
    {
      "network_id": "507f191e810c19729de860ea",
      "name": "LAN",
      "vlan_id": 1,
      "client_count": 15,
      "total_tx_bytes": 10240000,
      "total_rx_bytes": 20480000,
      "total_bytes": 30720000
    }
  ]
}
```

### Site Management Tools

#### `get_site_details`

Get detailed site information.

**Parameters:**
- `site_id` (string, required): Site identifier

**Returns:**
Object containing site details.

**Example:**
```python
result = await mcp.call_tool("get_site_details", {
    "site_id": "default"
})
```

**Response:**
```json
{
  "id": "default",
  "name": "Default Site",
  "desc": "Default site description"
}
```

#### `list_all_sites`

List all accessible sites.

**Parameters:** None

**Returns:**
Array of site objects.

**Example:**
```python
result = await mcp.call_tool("list_all_sites", {})
```

#### `get_site_statistics`

Retrieve site-wide statistics.

**Parameters:**
- `site_id` (string, required): Site identifier

**Returns:**
Object containing comprehensive site statistics.

**Example:**
```python
result = await mcp.call_tool("get_site_statistics", {
    "site_id": "default"
})
```

**Response:**
```json
{
  "site_id": "default",
  "devices": {
    "total": 25,
    "online": 24,
    "offline": 1,
    "access_points": 10,
    "switches": 8,
    "gateways": 7
  },
  "clients": {
    "total": 42,
    "wired": 15,
    "wireless": 27
  },
  "networks": {
    "total": 5
  },
  "bandwidth": {
    "total_tx_bytes": 102400000,
    "total_rx_bytes": 204800000,
    "total_bytes": 307200000
  }
}
```

## Phase 4: Mutating Tools

All Phase 4 tools modify UniFi configuration and require safety mechanisms.

### Safety Mechanisms

**All mutating tools implement these safety features:**

1. **Confirmation Required:** Must pass `confirm=True` to execute
2. **Dry Run Mode:** Pass `dry_run=True` to preview without changes
3. **Audit Logging:** All operations logged to `audit.log`
4. **Input Validation:** Parameters validated before execution

### Firewall Management

#### `list_firewall_rules`
List all firewall rules (read-only).

**Parameters:** `site_id`

#### `create_firewall_rule`
Create a new firewall rule.

**Parameters:** `site_id`, `name`, `action` (accept/drop/reject), `source`, `destination`, `protocol`, `port`, `enabled`, **`confirm`**, **`dry_run`**

**Example:**
```python
# Dry run first
result = await mcp.call_tool("create_firewall_rule", {
    "site_id": "default",
    "name": "Block SSH",
    "action": "drop",
    "protocol": "tcp",
    "port": 22,
    "dry_run": True
})

# Then execute
result = await mcp.call_tool("create_firewall_rule", {
    "site_id": "default",
    "name": "Block SSH",
    "action": "drop",
    "protocol": "tcp",
    "port": 22,
    "confirm": True
})
```

#### `update_firewall_rule` & `delete_firewall_rule`
Modify or remove firewall rules. Requires `confirm=True`.

### Network Configuration

#### `create_network`
Create a new network/VLAN.

**Parameters:** `site_id`, `name`, `vlan_id`, `subnet`, `purpose`, `dhcp_enabled`, DHCP settings, **`confirm`**, **`dry_run`**

#### `update_network` & `delete_network`
Modify or remove networks. Requires `confirm=True`.

### Device Control

#### `restart_device`
Restart a UniFi device.

**Parameters:** `site_id`, `device_mac`, **`confirm`**, **`dry_run`**

#### `locate_device`
Enable/disable LED locate mode.

**Parameters:** `site_id`, `device_mac`, `enabled`, **`confirm`**, **`dry_run`**

#### `upgrade_device`
Trigger firmware upgrade.

**Parameters:** `site_id`, `device_mac`, `firmware_url`, **`confirm`**, **`dry_run`**

### Client Management

#### `block_client` & `unblock_client`
Block or unblock a client from the network.

**Parameters:** `site_id`, `client_mac`, **`confirm`**, **`dry_run`**

#### `reconnect_client`
Force a client to reconnect.

**Parameters:** `site_id`, `client_mac`, **`confirm`**, **`dry_run`**

### Error Handling

All mutating tools raise:
- `ConfirmationRequiredError`: If `confirm` parameter not True
- `ValidationError`: If parameters invalid
- `ResourceNotFoundError`: If resource not found
- `APIError`: If UniFi API returns error

## MCP Resources

Resources provide read-only access to UniFi data through standardized URIs.

### Resource URI Scheme

Resources use a hierarchical URI scheme:

```
sites://<site_id>/<resource_type>/<identifier>
```

### Available Resources

#### `sites://{site_id}/devices`

List all devices in a site.

**Example:**
```python
devices = await mcp.read_resource("sites://default/devices")
```

#### `sites://{site_id}/devices/{mac_address}`

Get a specific device by MAC address.

**Example:**
```python
device = await mcp.read_resource("sites://default/devices/aa:bb:cc:dd:ee:ff")
```

#### `sites://{site_id}/networks`

List all networks in a site.

**Example:**
```python
networks = await mcp.read_resource("sites://default/networks")
```

#### `sites://{site_id}/clients`

List all active clients in a site.

**Example:**
```python
clients = await mcp.read_resource("sites://default/clients")
```

## Error Handling

### Error Response Format

Errors are returned in a standardized format:

```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Invalid username or password",
    "details": {
      "controller": "controller.local",
      "timestamp": "2025-10-17T12:00:00Z"
    }
  }
}
```

### Common Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `AUTHENTICATION_FAILED` | Invalid credentials | Check username/password |
| `CONNECTION_ERROR` | Cannot connect to controller | Verify host/port and network connectivity |
| `DEVICE_NOT_FOUND` | Device doesn't exist | Verify MAC address |
| `INVALID_PARAMETER` | Invalid parameter value | Check parameter format |
| `PERMISSION_DENIED` | Insufficient permissions | Check user role |
| `RATE_LIMIT_EXCEEDED` | Too many requests | Slow down requests |
| `TIMEOUT` | Request timed out | Increase timeout or check network |

## Rate Limiting

### Official API Rate Limits

The UniFi Cloud API enforces the following rate limits:

| API Version | Requests per Minute | Notes |
|-------------|--------------------:|-------|
| **Early Access (EA)** | 100 | Current version |
| **v1 Stable** | 10,000 | Future release |

### Rate Limit Response

When rate limits are exceeded, the API returns:

**HTTP Status:** `429 Too Many Requests`

**Headers:**
```http
Retry-After: 60
```

The `Retry-After` header indicates how many seconds to wait before retrying.

### MCP Server Rate Limit Handling

The MCP server implements intelligent rate limit handling:

- **Automatic retry** with exponential backoff
- **Request queuing** to prevent overwhelming the API
- **Configurable rate limit** via `UNIFI_RATE_LIMIT` environment variable
- **Graceful degradation** when limits are reached

### Best Practices

**For Application Developers:**
- Batch operations when possible to reduce API calls
- Cache frequently accessed data (devices, networks, etc.)
- Avoid polling; use event-driven approaches when available
- Implement client-side rate limiting to stay under limits
- Monitor the `X-RateLimit-*` headers (if provided by API)

**For High-Volume Applications:**
- Consider the v1 Stable API when available (10,000 req/min)
- Distribute load across multiple time windows
- Use pagination efficiently to minimize requests
- Cache static data locally

**Rate Limit Configuration Example:**
```env
# Set to match your API version
UNIFI_RATE_LIMIT=100  # EA: 100, v1 Stable: 10000
```

## Examples

### Complete Example: Network Setup

```python
import asyncio
from mcp import MCP

async def setup_guest_network():
    """Create a guest network with firewall isolation."""

    mcp = MCP("unifi-mcp-server")

    # Create guest network
    network = await mcp.call_tool("create_network", {
        "name": "Guest WiFi",
        "vlan_id": 20,
        "subnet": "192.168.20.0/24",
        "dhcp_enabled": true
    })

    # Create firewall rule to isolate guest network
    rule = await mcp.call_tool("create_firewall_rule", {
        "name": "Isolate Guest Network",
        "action": "drop",
        "source": "192.168.20.0/24",
        "destination": "192.168.1.0/24",
        "enabled": true
    })

    print(f"Created network: {network['name']}")
    print(f"Created firewall rule: {rule['name']}")

asyncio.run(setup_guest_network())
```

### Example: Monitor Devices

```python
async def monitor_devices():
    """List all devices and their status."""

    mcp = MCP("unifi-mcp-server")

    devices = await mcp.call_tool("list_devices", {
        "site_id": "default"
    })

    for device in devices:
        status = "🟢" if device["status"] == "connected" else "🔴"
        print(f"{status} {device['name']} ({device['model']}) - {device['ip']}")

asyncio.run(monitor_devices())
```

## API Changelog

### Version 0.1.0 (Initial Release)

- Basic device management (list, get, restart)
- Network management (list, create)
- Client management (list, block)
- Firewall rule management (list, create)
- Site-based resource URIs

## Future Enhancements

Planned features for future releases:

- [ ] Port forwarding management
- [ ] WiFi network (SSID) management
- [ ] DPI (Deep Packet Inspection) statistics
- [ ] Webhook support for events
- [ ] Backup and restore operations
- [ ] Bulk operations for devices
- [ ] Advanced firewall rule management
- [ ] VPN configuration
- [ ] Alert and notification management

## Support

For issues, questions, or contributions:

- **GitHub Issues:** https://github.com/elvis/unifi-mcp-server/issues
- **Documentation:** See `README.md` and `CONTRIBUTING.md`
- **Security Issues:** See `SECURITY.md`

---

**Last Updated:** 2025-10-17 | **API Version:** 0.1.0
