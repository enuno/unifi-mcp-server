"""Main entry point for UniFi MCP Server."""

from fastmcp import FastMCP

from .config import Settings
from .resources import ClientsResource, DevicesResource, NetworksResource, SitesResource
from .tools import clients as clients_tools
from .tools import devices as devices_tools
from .tools import networks as networks_tools
from .tools import sites as sites_tools
from .utils import get_logger

# Initialize settings
settings = Settings()
logger = get_logger(__name__, settings.log_level)

# Initialize FastMCP server
mcp = FastMCP(
    "UniFi MCP Server",
    version="0.1.0",
    description="Model Context Protocol server for UniFi Network API",
)

# Initialize resource handlers
sites_resource = SitesResource(settings)
devices_resource = DevicesResource(settings)
clients_resource = ClientsResource(settings)
networks_resource = NetworksResource(settings)


# MCP Tools
@mcp.tool()
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify server is running.

    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "version": "0.1.0",
        "api_type": settings.api_type.value,
    }


# MCP Resources
@mcp.resource("sites://")
async def get_sites_resource() -> str:
    """Get all UniFi sites.

    Returns:
        JSON string of sites list
    """
    sites = await sites_resource.list_sites()
    return "\n".join([f"Site: {s.name} ({s.id})" for s in sites])


@mcp.resource("sites://{site_id}/devices")
async def get_devices_resource(site_id: str) -> str:
    """Get all devices for a site.

    Args:
        site_id: Site identifier

    Returns:
        JSON string of devices list
    """
    devices = await devices_resource.list_devices(site_id)
    return "\n".join(
        [f"Device: {d.name or d.model} ({d.mac}) - {d.ip}" for d in devices]
    )


@mcp.resource("sites://{site_id}/clients")
async def get_clients_resource(site_id: str) -> str:
    """Get all clients for a site.

    Args:
        site_id: Site identifier

    Returns:
        JSON string of clients list
    """
    clients = await clients_resource.list_clients(site_id, active_only=True)
    return "\n".join(
        [f"Client: {c.hostname or c.name or c.mac} ({c.ip})" for c in clients]
    )


@mcp.resource("sites://{site_id}/networks")
async def get_networks_resource(site_id: str) -> str:
    """Get all networks for a site.

    Args:
        site_id: Site identifier

    Returns:
        JSON string of networks list
    """
    networks = await networks_resource.list_networks(site_id)
    return "\n".join(
        [f"Network: {n.name} (VLAN {n.vlan_id or 'none'}) - {n.ip_subnet}" for n in networks]
    )


# Device Management Tools
@mcp.tool()
async def get_device_details(site_id: str, device_id: str) -> dict:
    """Get detailed information for a specific device."""
    return await devices_tools.get_device_details(site_id, device_id, settings)


@mcp.tool()
async def get_device_statistics(site_id: str, device_id: str) -> dict:
    """Retrieve real-time statistics for a device."""
    return await devices_tools.get_device_statistics(site_id, device_id, settings)


@mcp.tool()
async def list_devices_by_type(site_id: str, device_type: str) -> list[dict]:
    """Filter devices by type (uap, usw, ugw)."""
    return await devices_tools.list_devices_by_type(site_id, device_type, settings)


@mcp.tool()
async def search_devices(site_id: str, query: str) -> list[dict]:
    """Search devices by name, MAC, or IP address."""
    return await devices_tools.search_devices(site_id, query, settings)


# Client Management Tools
@mcp.tool()
async def get_client_details(site_id: str, client_mac: str) -> dict:
    """Get detailed information for a specific client."""
    return await clients_tools.get_client_details(site_id, client_mac, settings)


@mcp.tool()
async def get_client_statistics(site_id: str, client_mac: str) -> dict:
    """Retrieve bandwidth and connection statistics for a client."""
    return await clients_tools.get_client_statistics(site_id, client_mac, settings)


@mcp.tool()
async def list_active_clients(site_id: str) -> list[dict]:
    """List currently connected clients."""
    return await clients_tools.list_active_clients(site_id, settings)


@mcp.tool()
async def search_clients(site_id: str, query: str) -> list[dict]:
    """Search clients by MAC, IP, or hostname."""
    return await clients_tools.search_clients(site_id, query, settings)


# Network Information Tools
@mcp.tool()
async def get_network_details(site_id: str, network_id: str) -> dict:
    """Get detailed network configuration."""
    return await networks_tools.get_network_details(site_id, network_id, settings)


@mcp.tool()
async def list_vlans(site_id: str) -> list[dict]:
    """List all VLANs in a site."""
    return await networks_tools.list_vlans(site_id, settings)


@mcp.tool()
async def get_subnet_info(site_id: str, network_id: str) -> dict:
    """Get subnet and DHCP information for a network."""
    return await networks_tools.get_subnet_info(site_id, network_id, settings)


@mcp.tool()
async def get_network_statistics(site_id: str) -> dict:
    """Retrieve network usage statistics for a site."""
    return await networks_tools.get_network_statistics(site_id, settings)


# Site Management Tools
@mcp.tool()
async def get_site_details(site_id: str) -> dict:
    """Get detailed site information."""
    return await sites_tools.get_site_details(site_id, settings)


@mcp.tool()
async def list_all_sites() -> list[dict]:
    """List all accessible sites."""
    return await sites_tools.list_sites(settings)


@mcp.tool()
async def get_site_statistics(site_id: str) -> dict:
    """Retrieve site-wide statistics."""
    return await sites_tools.get_site_statistics(site_id, settings)


def main() -> None:
    """Main entry point for the MCP server."""
    logger.info("Starting UniFi MCP Server...")
    logger.info(f"API Type: {settings.api_type.value}")
    logger.info(f"Base URL: {settings.base_url}")
    logger.info("Server ready to handle requests")


if __name__ == "__main__":
    main()
