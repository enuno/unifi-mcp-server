"""Main entry point for UniFi MCP Server."""

from __future__ import annotations

import importlib.metadata
import json
import os
from typing import Any

try:
    _SERVER_VERSION = importlib.metadata.version("unifi-mcp-server")
except importlib.metadata.PackageNotFoundError:
    _SERVER_VERSION = "unknown"

from fastmcp import FastMCP

from .config import APIType, Settings, TransportMode
from .resources import ClientsResource, DevicesResource, NetworksResource, SitesResource
from .resources import site_manager as site_manager_resource
from .tool_registry import register_module_tools
from .tools import acls as acls_tools
from .tools import application as application_tools
from .tools import backups as backups_tools
from .tools import client_management as client_mgmt_tools
from .tools import clients as clients_tools
from .tools import connector as connector_tools
from .tools import content_filtering as content_filtering_tools
from .tools import device_control as device_control_tools
from .tools import devices as devices_tools
from .tools import dhcp_reservations as dhcp_tools
from .tools import diagnostics as diagnostics_tools
from .tools import dns_management as dns_tools
from .tools import dpi as dpi_tools
from .tools import dpi_tools as dpi_new_tools
from .tools import firewall as firewall_tools
from .tools import firewall_groups as firewall_groups_tools
from .tools import firewall_policies as firewall_policies_tools
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
from .tools import switching as switching_tools
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
# Conditional tool modules based on API type
# ---------------------------------------------------------------------------

_CLOUD_TOOL_MODULES = [
    sites_tools,
    site_manager_tools,
    connector_tools,
]

_LOCAL_TOOL_MODULES = [
    acls_tools,
    application_tools,
    backups_tools,
    client_mgmt_tools,
    clients_tools,
    content_filtering_tools,
    device_control_tools,
    diagnostics_tools,
    dhcp_tools,
    dns_tools,
    devices_tools,
    dpi_tools,
    dpi_new_tools,
    firewall_tools,
    firewall_groups_tools,
    firewall_policies_tools,
    firewall_zones_tools,
    network_config_tools,
    networks_tools,
    port_fwd_tools,
    port_profile_tools,
    qos_tools,
    radius_tools,
    ref_tools,
    site_vpn_tools,
    switching_tools,
    topology_tools,
    traffic_flows_tools,
    tml_tools,
    vouchers_tools,
    vpn_tools,
    wans_tools,
    wifi_tools,
]

_TOOL_MODULES: list[Any] = []
if settings.api_type in (APIType.CLOUD_V1, APIType.CLOUD_EA):
    _TOOL_MODULES = list(_CLOUD_TOOL_MODULES)
    logger.info(
        f"Cloud API mode ({settings.api_type.value}) - registering {_TOOL_MODULES} tool modules"
    )
    # get_site_statistics calls /ea/sites/{id}/devices, /sta, /rest/networkconf
    # which all 404 on the live Cloud API
    for _module in _TOOL_MODULES:
        if _module is sites_tools:
            register_module_tools(mcp, _module, settings, exclude=["get_site_statistics"])
        else:
            register_module_tools(mcp, _module, settings)
else:
    _TOOL_MODULES = list(_CLOUD_TOOL_MODULES) + list(_LOCAL_TOOL_MODULES)
    logger.info(f"Local API mode - registering {_TOOL_MODULES} tool modules")
    for _module in _TOOL_MODULES:
        register_module_tools(mcp, _module, settings)

# ---------------------------------------------------------------------------
# Resource handlers
# ---------------------------------------------------------------------------

sites_resource = SitesResource(settings)
site_manager_res = site_manager_resource.SiteManagerResource(settings)

if settings.api_type == APIType.LOCAL:
    devices_resource = DevicesResource(settings)
    clients_resource = ClientsResource(settings)
    networks_resource = NetworksResource(settings)

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
        "version": _SERVER_VERSION,
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


if settings.api_type == APIType.LOCAL:

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

    if settings.server_transport == TransportMode.STDIO:
        logger.info("Transport: stdio (default)")
        logger.info("Server ready to handle requests")
        mcp.run()
    else:
        logger.info(f"Transport: {settings.server_transport.value}")
        logger.info(f"Server listening on {settings.server_host}:{settings.server_port}")
        mcp.run(
            transport=settings.server_transport.value,
            host=settings.server_host,
            port=settings.server_port,
        )


if __name__ == "__main__":
    main()
