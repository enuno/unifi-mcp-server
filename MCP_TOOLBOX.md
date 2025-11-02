# MCP Toolbox - Analytics & Monitoring Dashboard

## Overview

MCP Toolbox is a web-based analytics and monitoring dashboard for Model Context Protocol servers, powered by [agnost.ai](https://agnost.ai). It provides real-time visualization of MCP server performance, usage patterns, and debugging capabilities.

**Dashboard URL**: `http://localhost:8080` (default)

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Dashboard Overview](#dashboard-overview)
- [Analytics & Metrics](#analytics--metrics)
- [Debugging](#debugging)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

---

## Features

### Real-time Monitoring

- **Live Tool Invocations**: Watch MCP tools being called in real-time
- **Performance Metrics**: Track execution times, success rates, and error rates
- **Resource Utilization**: Monitor memory, CPU, and network usage
- **Active Connections**: See which clients are connected to the server

### Analytics

- **Usage Patterns**: Identify most/least used tools and resources
- **Performance Trends**: Historical data with time-series graphs
- **Error Analysis**: Track error types, frequencies, and patterns
- **Client Statistics**: Per-client usage and performance metrics

### Debugging

- **Request/Response Inspection**: View full request and response payloads
- **Stack Traces**: Detailed error stack traces with context
- **Parameter Validation**: See parameter validation errors
- **Execution Timeline**: Step-by-step execution flow visualization

### Alerting (Optional)

- **Performance Alerts**: Get notified when response times exceed thresholds
- **Error Rate Alerts**: Alert on high error rates
- **Custom Alerts**: Define custom alerting rules

---

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- UniFi API key from [unifi.ui.com](https://unifi.ui.com)
- Agnost Organization ID from [app.agnost.ai](https://app.agnost.ai)

### Setup Steps

```bash
# 1. Clone the repository (if not already done)
git clone https://github.com/enuno/unifi-mcp-server.git
cd unifi-mcp-server

# 2. Copy environment template
cp .env.docker.example .env

# 3. Edit .env file with your credentials
nano .env  # or use your preferred editor
```

**Required environment variables:**
```env
# UniFi API Configuration
UNIFI_API_KEY=your-unifi-api-key-here

# Agnost Configuration (required for Toolbox)
AGNOST_ENABLED=true
AGNOST_ORG_ID=your-organization-id-here
```

```bash
# 4. Start all services
docker-compose up -d

# 5. Verify services are running
docker-compose ps

# 6. Access the Toolbox dashboard
open http://localhost:8080
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (includes Redis data)
docker-compose down -v
```

---

## Configuration

### Environment Variables

#### Basic Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGNOST_ENABLED` | Yes | `false` | Enable agnost tracking |
| `AGNOST_ORG_ID` | Yes* | - | Your agnost organization ID |
| `AGNOST_ENDPOINT` | No | `https://api.agnost.ai` | Agnost API endpoint |

*Required if AGNOST_ENABLED=true or using Toolbox

#### Toolbox Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TOOLBOX_PORT` | No | `8080` | Dashboard web interface port |
| `TOOLBOX_AUTH_ENABLED` | No | `false` | Enable authentication |
| `TOOLBOX_USERNAME` | No | `admin` | Admin username (if auth enabled) |
| `TOOLBOX_PASSWORD` | No | - | Admin password (if auth enabled) |

#### Privacy Controls

| Variable | Default | Description |
|----------|---------|-------------|
| `AGNOST_DISABLE_INPUT` | `false` | Set to `true` to disable input tracking |
| `AGNOST_DISABLE_OUTPUT` | `false` | Set to `true` to disable output tracking |

### Port Configuration

By default, the Toolbox dashboard runs on port 8080. To change this:

```env
# .env file
TOOLBOX_PORT=9090
```

Then access the dashboard at `http://localhost:9090`.

### Authentication

To enable dashboard authentication:

```env
# .env file
TOOLBOX_AUTH_ENABLED=true
TOOLBOX_USERNAME=admin
TOOLBOX_PASSWORD=your-secure-password-here
```

After enabling authentication, you'll be prompted for credentials when accessing the dashboard.

---

## Dashboard Overview

### Home Page

The home page provides an at-a-glance view of your MCP server:

- **Server Status**: Uptime, version, configuration
- **Tool Statistics**: Total tools, most used, success rate
- **Resource Statistics**: Resource types, access counts
- **Recent Activity**: Last 10 tool invocations with timing

### Tools Tab

View and analyze MCP tool usage:

- **Tool List**: All available tools with descriptions
- **Usage Statistics**: Call count, avg response time, error rate
- **Performance Graphs**: Response time distribution, success/failure trends
- **Tool Details**: Click any tool to see detailed analytics

### Resources Tab

Monitor MCP resource access:

- **Resource URIs**: All available resource endpoints
- **Access Patterns**: Most accessed resources, access frequency
- **Performance**: Response times, cache hit rates
- **Resource Details**: Click to see access history and performance

### Errors Tab

Track and debug errors:

- **Error List**: Recent errors with timestamps
- **Error Types**: Group by error type or tool
- **Stack Traces**: Full stack traces with code context
- **Error Trends**: Error frequency over time
- **Quick Filters**: Filter by tool, error type, or time range

### Analytics Tab

Deep dive into performance and usage:

- **Performance Metrics**:
  - Average response time by tool
  - P50, P95, P99 percentiles
  - Throughput (requests per second)
  - Error rates and types

- **Usage Metrics**:
  - Tool popularity (most/least used)
  - Peak usage times
  - Client distribution
  - Request patterns

- **Time-series Graphs**:
  - Response time trends
  - Request volume over time
  - Error rate trends
  - Resource utilization

---

## Analytics & Metrics

### Key Performance Indicators (KPIs)

#### Response Time Metrics

- **Average Response Time**: Mean execution time across all tools
- **Median (P50)**: 50th percentile response time
- **P95**: 95th percentile - 95% of requests faster than this
- **P99**: 99th percentile - 99% of requests faster than this

**Interpreting Response Times:**
- < 100ms: Excellent
- 100-500ms: Good
- 500ms-1s: Acceptable
- \> 1s: Needs optimization

#### Success Rate

- **Overall Success Rate**: Percentage of successful tool invocations
- **Per-Tool Success Rate**: Success rate for individual tools

**Healthy Ranges:**
- \> 99%: Excellent
- 95-99%: Good
- 90-95%: Needs attention
- < 90%: Critical

#### Throughput

- **Requests Per Second (RPS)**: Number of tool invocations per second
- **Requests Per Minute (RPM)**: Number of tool invocations per minute

### Tool-Specific Metrics

For each MCP tool, the dashboard tracks:

1. **Invocation Count**: Total number of times called
2. **Avg Response Time**: Average execution time
3. **Success Rate**: Percentage of successful calls
4. **Error Count**: Number of failed calls
5. **Last Used**: Timestamp of most recent invocation

### Resource Metrics

For each MCP resource:

1. **Access Count**: Number of times accessed
2. **Cache Hit Rate**: Percentage of cached responses
3. **Avg Response Size**: Average size of responses
4. **Response Time**: Average time to fetch resource

---

## Debugging

### Request/Response Inspection

Click any tool invocation in the dashboard to see:

**Request Details:**
- Tool name
- Input parameters (if tracking enabled)
- Timestamp
- Client information
- Headers (if available)

**Response Details:**
- Output data (if tracking enabled)
- Response time
- Success/failure status
- Error message (if failed)
- Stack trace (if error occurred)

### Error Analysis

The Errors tab provides powerful debugging capabilities:

1. **Error Grouping**: Errors grouped by type or tool
2. **Stack Traces**: Full Python stack traces with line numbers
3. **Context**: Request parameters that caused the error
4. **Frequency**: How often each error occurs
5. **Recent Occurrences**: Timeline of when errors happened

### Performance Profiling

Identify slow operations:

1. **Slowest Tools**: List of tools with highest avg response time
2. **Performance Timeline**: Visual timeline of execution
3. **Bottleneck Identification**: Pinpoint slow operations
4. **Comparison**: Compare performance across time ranges

### Live Monitoring

Watch your MCP server in real-time:

- **Live Feed**: Stream of tool invocations as they happen
- **Active Requests**: Currently executing tools
- **Connection Status**: Connected clients and their status
- **Resource Usage**: Live CPU, memory, and network stats

---

## Troubleshooting

### Toolbox Dashboard Not Accessible

**Problem**: Cannot access `http://localhost:8080`

**Solutions**:
1. Check if Toolbox container is running:
   ```bash
   docker-compose ps mcp-toolbox
   ```

2. Check Toolbox logs:
   ```bash
   docker-compose logs mcp-toolbox
   ```

3. Verify port is not in use:
   ```bash
   lsof -i :8080  # macOS/Linux
   netstat -ano | findstr :8080  # Windows
   ```

4. Try a different port:
   ```env
   TOOLBOX_PORT=9090
   ```

### No Data Showing in Dashboard

**Problem**: Dashboard loads but shows no data

**Solutions**:
1. Verify agnost tracking is enabled:
   ```env
   AGNOST_ENABLED=true
   AGNOST_ORG_ID=your-org-id-here
   ```

2. Check MCP server logs for tracking errors:
   ```bash
   docker-compose logs unifi-mcp | grep -i agnost
   ```

3. Verify MCP server is making tool calls:
   ```bash
   docker-compose logs unifi-mcp | grep -i "tool"
   ```

4. Check Organization ID is correct in agnost.ai dashboard

### Authentication Issues

**Problem**: Can't log in to dashboard

**Solutions**:
1. Verify credentials in `.env`:
   ```env
   TOOLBOX_AUTH_ENABLED=true
   TOOLBOX_USERNAME=admin
   TOOLBOX_PASSWORD=your-password
   ```

2. Restart Toolbox container:
   ```bash
   docker-compose restart mcp-toolbox
   ```

3. Disable authentication temporarily for testing:
   ```env
   TOOLBOX_AUTH_ENABLED=false
   ```

### High Memory Usage

**Problem**: Toolbox container using too much memory

**Solutions**:
1. Reduce data retention period (configure in agnost.ai dashboard)
2. Enable input/output tracking controls:
   ```env
   AGNOST_DISABLE_INPUT=true
   AGNOST_DISABLE_OUTPUT=true
   ```
3. Add memory limits to docker-compose.yml:
   ```yaml
   mcp-toolbox:
     mem_limit: 512m
   ```

---

## Security

### Best Practices

1. **Enable Authentication**
   ```env
   TOOLBOX_AUTH_ENABLED=true
   TOOLBOX_PASSWORD=strong-random-password
   ```

2. **Use Strong Passwords**
   - Minimum 16 characters
   - Mix of uppercase, lowercase, numbers, and symbols
   - Use a password manager

3. **Restrict Network Access**
   ```yaml
   # docker-compose.yml
   mcp-toolbox:
     ports:
       - "127.0.0.1:8080:8080"  # Only localhost
   ```

4. **Enable HTTPS** (for production)
   - Use a reverse proxy (nginx, Caddy, Traefik)
   - Configure SSL certificates
   - Redirect HTTP to HTTPS

5. **Control Data Tracking**
   ```env
   AGNOST_DISABLE_INPUT=true   # Don't track input params
   AGNOST_DISABLE_OUTPUT=true  # Don't track output data
   ```

### Data Privacy

**What Gets Tracked:**
- Tool names and execution times (always)
- Input parameters (if `AGNOST_DISABLE_INPUT=false`)
- Output results (if `AGNOST_DISABLE_OUTPUT=false`)
- Error messages and stack traces (always)

**What Doesn't Get Tracked:**
- UniFi API keys (always masked)
- Passwords (always masked)
- Authentication tokens (always masked)
- Personal data (unless explicitly in parameters)

**Data Retention:**
- Default: 30 days
- Configurable in agnost.ai dashboard
- Can be deleted manually at any time

### Network Security

**Recommended Firewall Rules:**
```bash
# Allow Toolbox only from local network
iptables -A INPUT -p tcp --dport 8080 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j DROP
```

**Production Deployment:**
- Use VPN for remote access
- Deploy behind a firewall
- Use reverse proxy with SSL
- Enable rate limiting
- Monitor access logs

---

## Advanced Configuration

### Custom Agnost Endpoint

For self-hosted agnost deployments:

```env
AGNOST_ENDPOINT=https://your-agnost-instance.com
```

### Docker Compose Overrides

Create `docker-compose.override.yml` for custom configuration:

```yaml
version: '3.8'

services:
  mcp-toolbox:
    environment:
      - CUSTOM_VAR=value
    volumes:
      - ./custom-config:/config
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
```

### Health Checks

Monitor service health:

```bash
# Check all services
docker-compose ps

# Check specific service health
docker inspect --format='{{.State.Health.Status}}' mcp-toolbox

# View health check logs
docker inspect --format='{{json .State.Health}}' mcp-toolbox | jq
```

---

## Support

### Resources

- **Agnost.ai Documentation**: https://docs.agnost.ai
- **MCP Toolbox GitHub**: https://github.com/googleapis/genai-toolbox
- **UniFi MCP Server**: https://github.com/enuno/unifi-mcp-server

### Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/enuno/unifi-mcp-server/issues)
- **GitHub Discussions**: [Ask questions and share ideas](https://github.com/enuno/unifi-mcp-server/discussions)
- **Agnost Support**: support@agnost.ai

---

## FAQ

**Q: Do I need agnost.ai to use the UniFi MCP server?**
A: No, agnost.ai and MCP Toolbox are completely optional. The UniFi MCP server works without them.

**Q: Is MCP Toolbox free?**
A: Check agnost.ai pricing at https://agnost.ai/pricing

**Q: Can I run Toolbox without Docker?**
A: Yes, but Docker is recommended. See agnost.ai documentation for alternative deployment methods.

**Q: How much data does Toolbox collect?**
A: You control data collection with `AGNOST_DISABLE_INPUT` and `AGNOST_DISABLE_OUTPUT` flags. With both disabled, only metadata is collected (tool names, timing, errors).

**Q: Can I use Toolbox with other MCP servers?**
A: Yes! MCP Toolbox works with any MCP server that implements agnost tracking.

**Q: How do I update Toolbox to the latest version?**
```bash
docker-compose pull mcp-toolbox
docker-compose up -d mcp-toolbox
```

---

**Last Updated**: 2025-11-01
**Version**: 1.0.0
**Maintainer**: Elvis (@enuno)
