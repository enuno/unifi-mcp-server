"""Main entry point for UniFi MCP Server."""

from fastmcp import FastMCP

from .config import Settings
from .resources import ClientsResource, DevicesResource, NetworksResource, SitesResource
from .tools import client_management as client_mgmt_tools
from .tools import clients as clients_tools
from .tools import device_control as device_control_tools
from .tools import devices as devices_tools
from .tools import firewall as firewall_tools
from .tools import network_config as network_config_tools
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


# Firewall Management Tools (Phase 4)
@mcp.tool()
async def list_firewall_rules(site_id: str) -> list[dict]:
    """List all firewall rules in a site."""
    return await firewall_tools.list_firewall_rules(site_id, settings)


@mcp.tool()
async def create_firewall_rule(
    site_id: str,
    name: str,
    action: str,
    source: str | None = None,
    destination: str | None = None,
    protocol: str | None = None,
    port: int | None = None,
    enabled: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Create a new firewall rule (requires confirm=True)."""
    return await firewall_tools.create_firewall_rule(
        site_id, name, action, settings, source, destination, protocol, port, enabled, confirm, dry_run
    )


@mcp.tool()
async def update_firewall_rule(
    site_id: str,
    rule_id: str,
    name: str | None = None,
    action: str | None = None,
    source: str | None = None,
    destination: str | None = None,
    protocol: str | None = None,
    port: int | None = None,
    enabled: bool | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Update an existing firewall rule (requires confirm=True)."""
    return await firewall_tools.update_firewall_rule(
        site_id, rule_id, settings, name, action, source, destination, protocol, port, enabled, confirm, dry_run
    )


@mcp.tool()
async def delete_firewall_rule(
    site_id: str, rule_id: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Delete a firewall rule (requires confirm=True)."""
    return await firewall_tools.delete_firewall_rule(site_id, rule_id, settings, confirm, dry_run)


# Network Configuration Tools (Phase 4)
@mcp.tool()
async def create_network(
    site_id: str,
    name: str,
    vlan_id: int,
    subnet: str,
    purpose: str = "corporate",
    dhcp_enabled: bool = True,
    dhcp_start: str | None = None,
    dhcp_stop: str | None = None,
    dhcp_dns_1: str | None = None,
    dhcp_dns_2: str | None = None,
    domain_name: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Create a new network/VLAN (requires confirm=True)."""
    return await network_config_tools.create_network(
        site_id, name, vlan_id, subnet, settings, purpose, dhcp_enabled,
        dhcp_start, dhcp_stop, dhcp_dns_1, dhcp_dns_2, domain_name, confirm, dry_run
    )


@mcp.tool()
async def update_network(
    site_id: str,
    network_id: str,
    name: str | None = None,
    vlan_id: int | None = None,
    subnet: str | None = None,
    purpose: str | None = None,
    dhcp_enabled: bool | None = None,
    dhcp_start: str | None = None,
    dhcp_stop: str | None = None,
    dhcp_dns_1: str | None = None,
    dhcp_dns_2: str | None = None,
    domain_name: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Update an existing network (requires confirm=True)."""
    return await network_config_tools.update_network(
        site_id, network_id, settings, name, vlan_id, subnet, purpose, dhcp_enabled,
        dhcp_start, dhcp_stop, dhcp_dns_1, dhcp_dns_2, domain_name, confirm, dry_run
    )


@mcp.tool()
async def delete_network(
    site_id: str, network_id: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Delete a network (requires confirm=True)."""
    return await network_config_tools.delete_network(site_id, network_id, settings, confirm, dry_run)


# Device Control Tools (Phase 4)
@mcp.tool()
async def restart_device(
    site_id: str, device_mac: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Restart a UniFi device (requires confirm=True)."""
    return await device_control_tools.restart_device(site_id, device_mac, settings, confirm, dry_run)


@mcp.tool()
async def locate_device(
    site_id: str, device_mac: str, enabled: bool = True, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Enable/disable LED locate mode on a device (requires confirm=True)."""
    return await device_control_tools.locate_device(site_id, device_mac, settings, enabled, confirm, dry_run)


@mcp.tool()
async def upgrade_device(
    site_id: str, device_mac: str, firmware_url: str | None = None, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Trigger firmware upgrade for a device (requires confirm=True)."""
    return await device_control_tools.upgrade_device(site_id, device_mac, settings, firmware_url, confirm, dry_run)


# Client Management Tools (Phase 4)
@mcp.tool()
async def block_client(
    site_id: str, client_mac: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Block a client from accessing the network (requires confirm=True)."""
    return await client_mgmt_tools.block_client(site_id, client_mac, settings, confirm, dry_run)


@mcp.tool()
async def unblock_client(
    site_id: str, client_mac: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Unblock a previously blocked client (requires confirm=True)."""
    return await client_mgmt_tools.unblock_client(site_id, client_mac, settings, confirm, dry_run)


@mcp.tool()
async def reconnect_client(
    site_id: str, client_mac: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Force a client to reconnect (requires confirm=True)."""
    return await client_mgmt_tools.reconnect_client(site_id, client_mac, settings, confirm, dry_run)


def main() -> None:
    """Main entry point for the MCP server."""
    logger.info("Starting UniFi MCP Server...")
    logger.info(f"API Type: {settings.api_type.value}")
    logger.info(f"Base URL: {settings.base_url}")
    logger.info("Server ready to handle requests")


if __name__ == "__main__":
    main()
