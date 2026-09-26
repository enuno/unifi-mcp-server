"""Main entry point for UniFi MCP Server."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from . import __version__
from .api import pool
from .config import Settings
from .resources import ClientsResource, DevicesResource, NetworksResource, SitesResource
from .resources import site_manager as site_manager_resource
from .tools import traffic_flows as traffic_flows_tools
from .tools.acls import provider as acls_provider
from .tools.application import provider as application_provider
from .tools.backups import provider as backups_provider
from .tools.client_management import provider as client_management_provider
from .tools.clients import provider as clients_provider
from .tools.device_control import provider as device_control_provider
from .tools.devices import provider as devices_provider
from .tools.dns_policies import provider as dns_policies_provider
from .tools.dpi import provider as dpi_provider
from .tools.dpi_tools import provider as dpi_tools_provider
from .tools.events import provider as events_provider
from .tools.firewall import provider as firewall_provider
from .tools.firewall_policies import provider as firewall_policies_provider
from .tools.firewall_policy_backup import provider as firewall_policy_backup_provider
from .tools.firewall_policy_details import provider as firewall_policy_details_provider
from .tools.firewall_zones import provider as firewall_zones_provider
from .tools.groups import provider as groups_provider
from .tools.health import provider as health_provider
from .tools.network_config import provider as network_config_provider
from .tools.networks import provider as networks_provider
from .tools.port_forwarding import provider as port_forwarding_provider
from .tools.port_profiles import provider as port_profiles_provider
from .tools.qos import provider as qos_provider
from .tools.radius import provider as radius_provider
from .tools.reference_data import provider as reference_data_provider
from .tools.reports import provider as reports_provider
from .tools.rf_analysis import provider as rf_analysis_provider
from .tools.routing import provider as routing_provider
from .tools.settings import provider as settings_provider
from .tools.site_admin import provider as site_admin_provider
from .tools.site_manager import provider as site_manager_provider
from .tools.site_vpn import provider as site_vpn_provider
from .tools.sites import provider as sites_provider
from .tools.system import provider as system_provider
from .tools.topology import provider as topology_provider
from .tools.traffic_flows import provider as traffic_flows_provider
from .tools.traffic_matching_lists import provider as traffic_matching_lists_provider
from .tools.traffic_rules import provider as traffic_rules_provider
from .tools.vouchers import provider as vouchers_provider
from .tools.vpn import provider as vpn_provider
from .tools.wans import provider as wans_provider
from .tools.wifi import provider as wifi_provider
from .utils import get_logger

# Initialize settings
settings = Settings()
logger = get_logger(__name__, settings.log_level)


@asynccontextmanager
async def app_lifespan(_server: FastMCP) -> AsyncIterator[None]:
    await pool.initialize(settings)
    try:
        yield
    finally:
        await pool.shutdown()


SERVER_INSTRUCTIONS = (
    "UniFi Network Controller tools.\n"
    "- Start with list_all_sites to obtain a site_id; most tools require it.\n"
    "- All mutating tools require confirm=True. Call with confirm=False first "
    "to get a dry-run preview of the change without applying it.\n"
    "- Integration API endpoints require UUID ids (as returned by list_* tools). "
    "MongoDB ObjectId values from the legacy API are rejected.\n"
    "- Device actions through the Integration API support only RESTART. "
    "locate_device and upgrade_device use the legacy cmd/devmgr API instead.\n"
    "- Client actions (block, unblock, reconnect, forget) take MAC addresses "
    "directly; no id translation is needed.\n"
    "- Legacy and Integration responses use different field names "
    "(mac/macAddress, ip/ipAddress, _id/id); do not assume one shape.\n"
    "- list_firewall_policies and list_active_clients return the full "
    "unpaginated list and can be very large. Prefer search_clients, "
    "get_client_details and get_firewall_policy when you need one item."
)

# Initialize FastMCP server
mcp = FastMCP(
    "UniFi MCP Server",
    instructions=SERVER_INSTRUCTIONS,
    lifespan=app_lifespan,
    providers=[
        devices_provider,
        device_control_provider,
        clients_provider,
        client_management_provider,
        acls_provider,
        network_config_provider,
        networks_provider,
        firewall_provider,
        firewall_policies_provider,
        firewall_policy_details_provider,
        firewall_policy_backup_provider,
        firewall_zones_provider,
        groups_provider,
        wans_provider,
        dpi_provider,
        dpi_tools_provider,
        port_forwarding_provider,
        port_profiles_provider,
        qos_provider,
        dns_policies_provider,
        events_provider,
        health_provider,
        reports_provider,
        backups_provider,
        radius_provider,
        reference_data_provider,
        rf_analysis_provider,
        routing_provider,
        site_admin_provider,
        site_manager_provider,
        site_vpn_provider,
        settings_provider,
        sites_provider,
        system_provider,
        topology_provider,
        traffic_rules_provider,
        traffic_flows_provider,
        traffic_matching_lists_provider,
        application_provider,
        vouchers_provider,
        wifi_provider,
        vpn_provider,
    ],
)

# Configure agnost tracking if enabled
if os.getenv("AGNOST_ENABLED", "false").lower() in ("true", "1", "yes"):
    agnost_org_id = os.getenv("AGNOST_ORG_ID")
    if agnost_org_id:
        try:
            from agnost import config as agnost_config
            from agnost import track

            # Configure tracking with input/output control
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

# Initialize resource handlers
sites_resource = SitesResource(settings)
devices_resource = DevicesResource(settings)
clients_resource = ClientsResource(settings)
networks_resource = NetworksResource(settings)
site_manager_res = site_manager_resource.SiteManagerResource(settings)


# MCP Tools
@mcp.tool()
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify server is running.

    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "version": __version__,
        "api_type": settings.api_type.value,
    }


# Register debug tool only if DEBUG is enabled
if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
    logger.warning(
        "DEBUG mode is active — debug_api_request tool is enabled. "
        "Do not run in production with DEBUG=true."
    )

    @mcp.tool()
    async def debug_api_request(endpoint: str) -> object:
        """Debug tool to query arbitrary UniFi API endpoints (GET only).

        Only available when DEBUG=true. All requests are audit-logged.

        Args:
            endpoint: API endpoint path (e.g., /proxy/network/api/s/default/rest/networkconf)

        Returns:
            Raw JSON response from the API
        """
        from .api import UniFiClient

        logger.warning("DEBUG audit: debug_api_request called with endpoint=%r", endpoint)

        lowered_endpoint = endpoint.lower()
        if "http://" in lowered_endpoint or "https://" in lowered_endpoint:
            return {
                "error": "Invalid endpoint: URL schemes are not allowed. Use a relative API path.",
            }

        if not endpoint.startswith("/"):
            return {
                "error": "Invalid endpoint: must be a relative API path starting with '/'.",
            }

        async with UniFiClient(settings) as client:
            await client.authenticate()
            return await client.get(endpoint)


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


# Zone-Based Firewall Matrix Tools
# ⚠️ REMOVED: All zone policy matrix and application blocking tools have been removed
# because the UniFi API endpoints do not exist (verified on API v10.0.156).
# See tests/verification/PHASE2_FINDINGS.md for details.
#
# Removed tools:
# - get_zbf_matrix (endpoint /firewall/policies/zone-matrix does not exist)
# - get_zone_policies (endpoint /firewall/policies/zones/{id} does not exist)
# - update_zbf_policy (endpoint /firewall/policies/zone-matrix/{src}/{dst} does not exist)
# - block_application_by_zone (endpoint /firewall/zones/{id}/app-block does not exist)
# - list_blocked_applications (endpoint /firewall/zones/{id}/app-block does not exist)
# - get_zone_matrix_policy (endpoint /firewall/policies/zone-matrix/{src}/{dst} does not exist)
# - delete_zbf_policy (endpoint /firewall/policies/zone-matrix/{src}/{dst} does not exist)
#
# Alternative: Configure zone policies manually in UniFi Console UI


# ⚠️ REMOVED: get_zone_statistics - endpoint does not exist
# Zone statistics endpoint (/firewall/zones/{id}/statistics) does not exist in UniFi API v10.0.156.
# Monitor traffic via /sites/{siteId}/clients endpoint instead.

# ⚠️ REMOVED: get_zone_matrix_policy - endpoint does not exist
# Zone matrix policy endpoint does not exist in UniFi API v10.0.156.

# ⚠️ REMOVED: delete_zbf_policy - endpoint does not exist
# Zone policy delete endpoint does not exist in UniFi API v10.0.156.


# Additional MCP Resources
# ⚠️ REMOVED: sites://{site_id}/firewall/matrix resource
# ZBF matrix endpoint does not exist in UniFi API v10.0.156


@mcp.resource("sites://{site_id}/traffic/flows")
async def get_traffic_flows_resource(site_id: str) -> str:
    """Get traffic flows for a site.

    Args:
        site_id: Site identifier

    Returns:
        JSON string of traffic flows
    """
    flows = await traffic_flows_tools.get_traffic_flows(site_id)
    import json

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
