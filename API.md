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

### Device Management

#### `list_devices`

List all devices in a site.

**Parameters:**
- `site_id` (string, optional): Site identifier. Default: `"default"`

**Returns:**
Array of device objects containing device information.

**Example:**
```python
result = await mcp.call_tool("list_devices", {
    "site_id": "default"
})
```

**Response:**
```json
[
  {
    "mac": "aa:bb:cc:dd:ee:ff",
    "name": "Living Room AP",
    "model": "U6-Lite",
    "type": "uap",
    "ip": "192.168.1.100",
    "status": "connected",
    "uptime": 86400,
    "version": "6.5.55.14277"
  }
]
```

#### `get_device`

Get detailed information about a specific device.

**Parameters:**
- `mac_address` (string, required): Device MAC address
- `site_id` (string, optional): Site identifier. Default: `"default"`

**Returns:**
Object containing detailed device information.

**Example:**
```python
result = await mcp.call_tool("get_device", {
    "mac_address": "aa:bb:cc:dd:ee:ff",
    "site_id": "default"
})
```

#### `restart_device`

Restart a UniFi device.

**Parameters:**
- `mac_address` (string, required): Device MAC address
- `site_id` (string, optional): Site identifier. Default: `"default"`

**Returns:**
Success confirmation.

**Example:**
```python
result = await mcp.call_tool("restart_device", {
    "mac_address": "aa:bb:cc:dd:ee:ff"
})
```

### Network Management

#### `list_networks`

List all networks in a site.

**Parameters:**
- `site_id` (string, optional): Site identifier. Default: `"default"`

**Returns:**
Array of network configuration objects.

**Example:**
```python
result = await mcp.call_tool("list_networks", {
    "site_id": "default"
})
```

**Response:**
```json
[
  {
    "id": "5f8a...",
    "name": "Default",
    "purpose": "corporate",
    "vlan": 1,
    "subnet": "192.168.1.0/24",
    "dhcp_enabled": true
  }
]
```

#### `create_network`

Create a new network.

**Parameters:**
- `name` (string, required): Network name
- `vlan_id` (integer, required): VLAN ID (1-4094)
- `subnet` (string, required): Network subnet in CIDR notation
- `dhcp_enabled` (boolean, optional): Enable DHCP. Default: `true`
- `site_id` (string, optional): Site identifier. Default: `"default"`

**Returns:**
Created network object.

**Example:**
```python
result = await mcp.call_tool("create_network", {
    "name": "Guest WiFi",
    "vlan_id": 20,
    "subnet": "192.168.20.0/24",
    "dhcp_enabled": true
})
```

### Client Management

#### `list_clients`

List all active clients in a site.

**Parameters:**
- `site_id` (string, optional): Site identifier. Default: `"default"`

**Returns:**
Array of client objects.

**Example:**
```python
result = await mcp.call_tool("list_clients", {
    "site_id": "default"
})
```

**Response:**
```json
[
  {
    "mac": "11:22:33:44:55:66",
    "hostname": "iPhone",
    "ip": "192.168.1.50",
    "network": "Default",
    "ap_mac": "aa:bb:cc:dd:ee:ff",
    "signal": -45,
    "uptime": 3600
  }
]
```

#### `block_client`

Block a client from accessing the network.

**Parameters:**
- `mac_address` (string, required): Client MAC address
- `site_id` (string, optional): Site identifier. Default: `"default"`

**Returns:**
Success confirmation.

**Example:**
```python
result = await mcp.call_tool("block_client", {
    "mac_address": "11:22:33:44:55:66"
})
```

### Firewall Management

#### `list_firewall_rules`

List all firewall rules in a site.

**Parameters:**
- `site_id` (string, optional): Site identifier. Default: `"default"`

**Returns:**
Array of firewall rule objects.

**Example:**
```python
result = await mcp.call_tool("list_firewall_rules", {
    "site_id": "default"
})
```

#### `create_firewall_rule`

Create a new firewall rule.

**Parameters:**
- `name` (string, required): Rule name
- `action` (string, required): Action (`"accept"`, `"drop"`, `"reject"`)
- `source` (string, optional): Source network/IP
- `destination` (string, optional): Destination network/IP
- `protocol` (string, optional): Protocol (`"tcp"`, `"udp"`, `"icmp"`, `"all"`)
- `port` (integer, optional): Destination port
- `enabled` (boolean, optional): Enable rule. Default: `true`
- `site_id` (string, optional): Site identifier. Default: `"default"`

**Returns:**
Created firewall rule object.

**Example:**
```python
result = await mcp.call_tool("create_firewall_rule", {
    "name": "Block external SSH",
    "action": "drop",
    "protocol": "tcp",
    "port": 22,
    "enabled": true
})
```

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
