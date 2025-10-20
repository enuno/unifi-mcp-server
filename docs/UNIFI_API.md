# UniFi API Reference Guide

This document provides comprehensive information about the official UniFi Cloud API used by this MCP server.

## Table of Contents

- [Official Documentation](#official-documentation)
- [Getting Your API Key](#getting-your-api-key)
- [API Access Modes](#api-access-modes)
- [Available Endpoints](#available-endpoints)
- [Rate Limiting](#rate-limiting)
- [Migration Guide](#migration-guide)
- [Troubleshooting](#troubleshooting)
- [Additional Resources](#additional-resources)

## Official Documentation

### UniFi API Documentation

- **Getting Started Guide**: [https://developer.ui.com/site-manager-api/gettingstarted](https://developer.ui.com/site-manager-api/gettingstarted)
- **API Reference**: Available through the UniFi Developer Portal
- **MCP Implementation Guide**: [https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access](https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access)

### API Version Information

| Version | Status | Rate Limit | Features |
|---------|--------|------------|----------|
| Early Access (EA) | **Current** | 100 req/min | Read-only access |
| v1 Stable | Coming Soon | 10,000 req/min | Read + Write access |

## Getting Your API Key

### Step-by-Step Instructions

Follow these steps to obtain your UniFi API key:

#### 1. Sign In to UniFi Site Manager

Navigate to [https://unifi.ui.com](https://unifi.ui.com) and sign in with your UniFi account credentials.

#### 2. Access the API Section

From the left navigation menu:

1. Click on **Settings** (gear icon)
2. Select **Control Plane**
3. Click on **Integrations**

#### 3. Create an API Key

1. Click the **"Create API Key"** button
2. Optionally provide a description (e.g., "MCP Server - Production")
3. Click **Create**

#### 4. Save Your API Key

**CRITICAL**: The API key is displayed **only once** and cannot be retrieved later.

1. **Copy the entire key** immediately
2. Store it in a secure location:
   - Password manager (recommended)
   - Secure environment variable
   - Secret management system (AWS Secrets Manager, HashiCorp Vault, etc.)
3. **Never** commit the key to version control
4. **Never** share the key in plain text

#### 5. Configure Your Application

Add the API key to your `.env` file:

```env
UNIFI_API_KEY=your-api-key-here
```

### Managing API Keys

**Viewing Existing Keys**

- You can view a list of your API keys in the Integrations section
- Only the key name/description is shown, not the actual key value

**Revoking Keys**

- Click the trash icon next to a key to revoke it
- Revoked keys cannot be restored
- Applications using revoked keys will immediately lose access

**Best Practices**

- Create separate keys for different environments (dev, staging, production)
- Use descriptive names to identify where each key is used
- Rotate keys regularly (e.g., every 90 days)
- Revoke keys immediately if compromised

## API Access Modes

The UniFi MCP Server supports two API access modes:

### Cloud API (Recommended)

**Overview**

- Access UniFi services through Ubiquiti's cloud infrastructure
- Works with cloud-hosted UniFi instances
- Requires internet connectivity
- Official, supported API endpoint

**Configuration**

```env
UNIFI_API_TYPE=cloud
UNIFI_HOST=api.ui.com
UNIFI_PORT=443
UNIFI_VERIFY_SSL=true
```

**Base URL Structure**

```
https://api.ui.com/v1/{endpoint}
```

**Advantages**

- ✅ Official support from Ubiquiti
- ✅ Guaranteed uptime and reliability
- ✅ Automatic updates and improvements
- ✅ Higher rate limits (future v1 stable)
- ✅ Works from anywhere with internet
- ✅ SSL/TLS security by default

**Limitations**

- ❌ Requires internet connectivity
- ❌ Currently read-only (EA version)
- ❌ Rate limited (100 req/min in EA)

### Local Gateway Proxy

**Overview**

- Direct access to local UniFi gateway
- Works without internet connectivity
- Uses gateway as a proxy to the network controller
- Useful for air-gapped or isolated networks

**Configuration**

```env
UNIFI_API_TYPE=local
UNIFI_HOST=192.168.1.1  # Your gateway IP
UNIFI_PORT=443
UNIFI_VERIFY_SSL=false  # Often needed for self-signed certs
```

**Base URL Structure**

```
https://{gateway-ip}:{port}/proxy/network/integration/v1/{endpoint}
```

**Advantages**

- ✅ Works without internet
- ✅ Lower latency (local network)
- ✅ No cloud dependency
- ✅ Useful for isolated/secure environments

**Limitations**

- ❌ Requires local network access
- ❌ May have self-signed certificates
- ❌ No official support guarantee
- ❌ Must manage gateway availability

### Comparison Table

| Feature | Cloud API | Local Gateway Proxy |
|---------|-----------|---------------------|
| **Internet Required** | Yes | No |
| **Official Support** | Yes | Limited |
| **SSL Verification** | Recommended | Often disabled |
| **Rate Limits** | 100/min (EA), 10k/min (v1) | Varies by gateway |
| **Access Location** | Anywhere | Local network only |
| **Use Case** | Production, cloud deployments | Development, air-gapped networks |

## Available Endpoints

### Sites Management

#### List All Sites

```http
GET /v1/sites
```

**Pagination**: Returns up to 200 sites per request. Use `offset` and `limit` parameters for pagination.

**Example Response**:

```json
{
  "data": [
    {
      "id": "site-id-123",
      "name": "Default Site",
      "description": "Main site"
    }
  ]
}
```

### Devices Management

#### List Devices in a Site

```http
GET /v1/sites/{site_id}/devices
```

**Example Response**:

```json
{
  "data": [
    {
      "mac": "aa:bb:cc:dd:ee:ff",
      "name": "Living Room AP",
      "model": "U6-Lite",
      "type": "uap",
      "ip": "192.168.1.100",
      "status": "connected"
    }
  ]
}
```

### Hosts (Clients) Management

#### List All Hosts

```http
GET /v1/hosts
```

**Example Response**:

```json
{
  "data": [
    {
      "mac": "11:22:33:44:55:66",
      "hostname": "iPhone",
      "ip": "192.168.1.50",
      "network": "Default"
    }
  ]
}
```

### Authentication Header

All requests must include the API key in the `X-API-Key` header:

```http
X-API-Key: your-api-key-here
```

**Example with curl**:

```bash
curl -X GET 'https://api.ui.com/v1/sites' \
  -H 'X-API-Key: your-api-key-here' \
  -H 'Accept: application/json'
```

## Rate Limiting

### Current Limits (Early Access)

- **Requests per Minute**: 100
- **Burst Allowance**: Not documented
- **Reset Window**: 60 seconds

### Future Limits (v1 Stable)

- **Requests per Minute**: 10,000
- **Significantly higher capacity** for production workloads

### Rate Limit Headers

When you make a request, look for these headers (may vary by implementation):

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1634567890
```

### Handling Rate Limits

**429 Too Many Requests Response**:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

**Recommended Strategies**:

1. **Exponential Backoff**

   ```
   Wait time = min(base_delay * 2^retry_count, max_delay)
   ```

2. **Request Queuing**
   - Queue requests locally
   - Process at a controlled rate
   - Stay under the limit proactively

3. **Caching**
   - Cache frequently accessed data
   - Implement TTL-based cache invalidation
   - Use ETags for conditional requests (if supported)

4. **Batch Operations**
   - Combine multiple operations when possible
   - Reduce total number of API calls

### Rate Limit Best Practices

```python
# Example: Simple rate limiter
import time
from collections import deque

class RateLimiter:
    def __init__(self, max_requests=100, window=60):
        self.max_requests = max_requests
        self.window = window
        self.requests = deque()

    def allow_request(self):
        now = time.time()
        # Remove old requests outside the window
        while self.requests and self.requests[0] < now - self.window:
            self.requests.popleft()

        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False
```

## Migration Guide

### From Local Controller to Cloud API

If you're migrating from a local UniFi controller setup to the cloud API:

#### 1. Verify Cloud Access

Ensure your UniFi setup is accessible via unifi.ui.com:

- Log in to [https://unifi.ui.com](https://unifi.ui.com)
- Verify you can see your sites and devices

#### 2. Obtain API Key

Follow the [Getting Your API Key](#getting-your-api-key) instructions above.

#### 3. Update Environment Variables

**Before (Local Controller)**:

```env
UNIFI_HOST=controller.local
UNIFI_USERNAME=admin
UNIFI_PASSWORD=your-password
UNIFI_PORT=8443
UNIFI_VERIFY_SSL=false
```

**After (Cloud API)**:

```env
UNIFI_API_KEY=your-api-key-here
UNIFI_API_TYPE=cloud
UNIFI_HOST=api.ui.com
UNIFI_PORT=443
UNIFI_VERIFY_SSL=true
```

#### 4. Update Code (If Applicable)

**Authentication Changes**:

- Remove session/cookie management code
- Remove login/logout logic
- Add `X-API-Key` header to all requests
- Remove CSRF token handling

**Endpoint Changes**:

- Update base URL from controller to cloud API
- Update endpoint paths to match cloud API structure
- Implement pagination for large result sets

#### 5. Test Thoroughly

- Verify connectivity to cloud API
- Test all MCP tools and resources
- Confirm data matches expectations
- Monitor rate limiting behavior

#### 6. Update Documentation

- Update deployment documentation
- Update runbooks and procedures
- Notify team members of changes

### Migration Checklist

- [ ] Verify cloud access at unifi.ui.com
- [ ] Create API key
- [ ] Update `.env` file
- [ ] Remove old credential files
- [ ] Update code authentication logic
- [ ] Update endpoint URLs
- [ ] Implement rate limiting
- [ ] Test all functionality
- [ ] Update documentation
- [ ] Deploy to production
- [ ] Monitor for issues
- [ ] Revoke old credentials (if applicable)

## Troubleshooting

### Common Issues and Solutions

#### Issue: 401 Unauthorized

**Symptoms**:

```json
{
  "error": "Unauthorized",
  "message": "Invalid API key"
}
```

**Solutions**:

1. Verify API key is correct (no extra spaces or characters)
2. Check that `X-API-Key` header is set correctly
3. Ensure API key hasn't been revoked
4. Create a new API key if necessary

#### Issue: 429 Too Many Requests

**Symptoms**:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

**Solutions**:

1. Implement exponential backoff
2. Reduce request frequency
3. Cache frequently accessed data
4. Consider upgrading to v1 Stable when available (10k/min)

#### Issue: Connection Timeout

**Symptoms**:

- Requests hang or timeout
- No response from API

**Solutions**:

1. Check internet connectivity
2. Verify firewall allows outbound HTTPS (port 443)
3. Test with curl: `curl -v https://api.ui.com/v1/sites -H "X-API-Key: your-key"`
4. Check DNS resolution: `nslookup api.ui.com`
5. Try increasing timeout value in configuration

#### Issue: SSL Certificate Verification Failed

**Symptoms**:

```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solutions**:

**For Cloud API** (should not happen):

1. Update system CA certificates
2. Check system clock is correct
3. Verify DNS is resolving correctly

**For Local Gateway Proxy** (common):

1. Set `UNIFI_VERIFY_SSL=false` in `.env`
2. Or install gateway's self-signed certificate in system trust store

#### Issue: Empty Response / No Data

**Symptoms**:

- API returns 200 OK but no data
- Empty arrays in responses

**Solutions**:

1. Verify you have sites/devices configured in UniFi
2. Check site_id is correct
3. Ensure devices are adopted and online
4. Log in to unifi.ui.com to verify data exists

#### Issue: Read-Only API Limitations

**Symptoms**:

- Cannot create/update/delete resources
- 403 Forbidden on write operations

**Solutions**:

- This is expected behavior for EA version
- Read-only access is current limitation
- Wait for v1 Stable release for write operations
- Use UniFi web interface for configuration changes

### Debug Mode

Enable debug logging to troubleshoot issues:

```env
MCP_LOG_LEVEL=DEBUG
```

This will log:

- All HTTP requests and responses
- Authentication headers (keys are redacted)
- Rate limiting information
- Error details

## Additional Resources

### Official Links

- **UniFi Site Manager**: [https://unifi.ui.com](https://unifi.ui.com)
- **UniFi Developer Portal**: [https://developer.ui.com](https://developer.ui.com)
- **UniFi Community Forums**: [https://community.ui.com](https://community.ui.com)
- **Ubiquiti Support**: [https://help.ui.com](https://help.ui.com)

### API Tutorials and Guides

- **Building an MCP Server for UniFi**: [https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access](https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access)
- **UniFi API Getting Started**: [https://developer.ui.com/site-manager-api/gettingstarted](https://developer.ui.com/site-manager-api/gettingstarted)

### Related Projects

- **FastMCP**: [https://github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp) - MCP server framework
- **Anthropic MCP**: [https://github.com/anthropics/mcp](https://github.com/anthropics/mcp) - Model Context Protocol specification

### Security Resources

- **OWASP API Security**: [https://owasp.org/www-project-api-security/](https://owasp.org/www-project-api-security/)
- **API Key Management Best Practices**: Research industry standards for API key rotation and management

---

**Document Version**: 1.0
**Last Updated**: 2025-10-17
**API Version**: Early Access (EA)

For issues or questions about this documentation, please file an issue at the repository issue tracker.
