/**
 * UniFi MCP Server - npm metadata package
 *
 * This package provides Model Context Protocol (MCP) registry metadata.
 * The actual MCP server is Python-based.
 *
 * Installation:
 *   pip install unifi-mcp-server
 *
 * Docker:
 *   docker pull ghcr.io/enuno/unifi-mcp-server:0.12.0
 *
 * Documentation:
 *   https://github.com/enuno/unifi-mcp-server
 */

module.exports = {
  name: 'unifi-mcp-server',
  version: '0.12.0',
  description: 'An MCP server that leverages official UniFi API',
  type: 'python',
  install: {
    pip: 'pip install unifi-mcp-server==0.12.0',
    docker: 'docker pull ghcr.io/enuno/unifi-mcp-server:0.12.0'
  },
  repository: 'https://github.com/enuno/unifi-mcp-server',
  documentation: 'https://github.com/enuno/unifi-mcp-server/blob/main/API.md'
};
