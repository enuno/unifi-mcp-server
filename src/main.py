"""Main entry point for UniFi MCP Server."""

from fastmcp import FastMCP

from .config import Settings
from .resources import ClientsResource, DevicesResource, NetworksResource, SitesResource
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


def main() -> None:
    """Main entry point for the MCP server."""
    logger.info("Starting UniFi MCP Server...")
    logger.info(f"API Type: {settings.api_type.value}")
    logger.info(f"Base URL: {settings.base_url}")
    logger.info("Server ready to handle requests")


if __name__ == "__main__":
    main()
