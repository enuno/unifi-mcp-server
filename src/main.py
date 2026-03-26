"""Main entry point for UniFi MCP Server."""

import json
import os

from fastmcp import FastMCP

from .config import Settings
from .resources import ClientsResource, DevicesResource, NetworksResource, SitesResource
from .resources import site_manager as site_manager_resource
from .tool_registry import register_module_tools
from .tools import acls as acls_tools
from .tools import application as application_tools
from .tools import backups as backups_tools
from .tools import client_management as client_mgmt_tools
from .tools import clients as clients_tools
from .tools import device_control as device_control_tools
from .tools import devices as devices_tools
from .tools import dpi as dpi_tools
from .tools import dpi_tools as dpi_new_tools
from .tools import firewall as firewall_tools
from .tools import firewall_zones as firewall_zones_tools
from .tools import network_config as network_config_tools
from .tools import networks as networks_tools
from .tools import port_forwarding as port_fwd_tools
from .tools import port_profiles as port_profile_tools
from .tools import qos as qos_tools
from .tools import radius as radius_tools
from .tools import reference_data as ref_tools
from .tools import site_manager as site_manager_tools
from .tools import site_vpn as site_vpn_tools
from .tools import sites as sites_tools
from .tools import topology as topology_tools
from .tools import traffic_flows as traffic_flows_tools
from .tools import traffic_matching_lists as tml_tools
from .tools import vouchers as vouchers_tools
from .tools import vpn as vpn_tools
from .tools import wans as wans_tools
from .tools import wifi as wifi_tools
from .utils import get_logger

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

settings = Settings()
logger = get_logger(__name__, settings.log_level)

mcp = FastMCP("UniFi MCP Server")

# ---------------------------------------------------------------------------
# Optional: agnost tracking
# ---------------------------------------------------------------------------

if os.getenv("AGNOST_ENABLED", "false").lower() in ("true", "1", "yes"):
    agnost_org_id = os.getenv("AGNOST_ORG_ID")
    if agnost_org_id:
        try:
            from agnost import config as agnost_config  # type: ignore[import-untyped]
            from agnost import track  # type: ignore[import-untyped]

            disable_input = os.getenv("AGNOST_DISABLE_INPUT", "false").lower() in (
                "true",
                "1",
                "yes",
            )
            disable_output = os.getenv("AGNOST_DISABLE_OUTPUT", "false").lower() in (
                "true",
                "1",
                "yes",
            )

            track(
                mcp,
                agnost_org_id,
                agnost_config(
                    endpoint=os.getenv("AGNOST_ENDPOINT", "https://api.agnost.ai"),
                    disable_input=disable_input,
                    disable_output=disable_output,
                ),
            )
            logger.info(
                f"Agnost.ai performance tracking enabled (input: {not disable_input}, output: {not disable_output})"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize agnost tracking: {e}")
    else:
        logger.warning("AGNOST_ENABLED is true but AGNOST_ORG_ID is not set")

# ---------------------------------------------------------------------------
# Resource handlers
# ---------------------------------------------------------------------------

sites_resource = SitesResource(settings)
devices_resource = DevicesResource(settings)
clients_resource = ClientsResource(settings)
networks_resource = NetworksResource(settings)
site_manager_res = site_manager_resource.SiteManagerResource(settings)

# ---------------------------------------------------------------------------
# Auto-register all tool modules
# ---------------------------------------------------------------------------

_TOOL_MODULES = [
    acls_tools,
    application_tools,
    backups_tools,
    client_mgmt_tools,
    clients_tools,
    device_control_tools,
    devices_tools,
    dpi_tools,
    dpi_new_tools,
    firewall_tools,
    firewall_zones_tools,
    network_config_tools,
    networks_tools,
    port_fwd_tools,
    port_profile_tools,
    qos_tools,
    radius_tools,
    ref_tools,
    site_manager_tools,
    site_vpn_tools,
    sites_tools,
    topology_tools,
    traffic_flows_tools,
    tml_tools,
    vouchers_tools,
    vpn_tools,
    wans_tools,
    wifi_tools,
]

for _module in _TOOL_MODULES:
    register_module_tools(mcp, _module, settings)

# ---------------------------------------------------------------------------
# Built-in tools (not in a module, or require special handling)
# ---------------------------------------------------------------------------


@mcp.tool()
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify server is running.

    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "version": "0.2.4",
        "api_type": settings.api_type.value,
    }


# Conditional debug tool
if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):

    @mcp.tool()
    async def debug_api_request(endpoint: str, method: str = "GET") -> dict:
        """Debug tool to query arbitrary UniFi API endpoints.

        Args:
            endpoint: API endpoint path (e.g., /proxy/network/api/s/default/rest/networkconf)
            method: HTTP method (GET, POST, PUT, DELETE)

        Returns:
            Raw JSON response from the API
        """
        from .api import UniFiClient

        async with UniFiClient(settings) as client:
            await client.authenticate()
            if method.upper() == "GET":
                return await client.get(endpoint)
            elif method.upper() == "DELETE":
                return await client.delete(endpoint)
            else:
                return {"error": f"Method {method} requires json_data parameter (not implemented)"}


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------


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
    return "\n".join([f"Device: {d.name or d.model} ({d.mac}) - {d.ip}" for d in devices])


@mcp.resource("sites://{site_id}/clients")
async def get_clients_resource(site_id: str) -> str:
    """Get all clients for a site.

    Args:
        site_id: Site identifier

    Returns:
        JSON string of clients list
    """
    clients = await clients_resource.list_clients(site_id, active_only=True)
    return "\n".join([f"Client: {c.hostname or c.name or c.mac} ({c.ip})" for c in clients])


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


@mcp.resource("sites://{site_id}/traffic/flows")
async def get_traffic_flows_resource(site_id: str) -> str:
    """Get traffic flows for a site.

    Args:
        site_id: Site identifier

    Returns:
        JSON string of traffic flows
    """
    flows = await traffic_flows_tools.get_traffic_flows(site_id, settings)
    return json.dumps(flows, indent=2)


@mcp.resource("site-manager://sites")
async def get_site_manager_sites_resource() -> str:
    """Get all sites from Site Manager API.

    Returns:
        JSON string of sites list
    """
    return await site_manager_res.get_all_sites()


@mcp.resource("site-manager://health")
async def get_site_manager_health_resource() -> str:
    """Get cross-site health metrics.

    Returns:
        JSON string of health metrics
    """
    return await site_manager_res.get_health_metrics()


@mcp.resource("site-manager://internet-health")
async def get_site_manager_internet_health_resource() -> str:
    """Get internet connectivity status.

    Returns:
        JSON string of internet health
    """
    return await site_manager_res.get_internet_health_status()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the MCP server."""
    logger.info("Starting UniFi MCP Server...")
    logger.info(f"API Type: {settings.api_type.value}")
    logger.info(f"Base URL: {settings.base_url}")
    logger.info("Server ready to handle requests")

    # Start the FastMCP server
    mcp.run()


if __name__ == "__main__":
    main()
