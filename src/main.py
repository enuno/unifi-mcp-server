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

from .a2a import A2AState
from .a2a.audit import get_audit_logger
from .a2a.auth import AuthManager
from .a2a.route_policy import ConfirmationWorkflow, SafetyController
from .api import validate_controller_relative_endpoint
from .config import APIType, Settings, ToolProfile, TransportMode
from .mcp_auth import build_mcp_auth, require_authenticated_request
from .resources import ClientsResource, DevicesResource, NetworksResource, SitesResource
from .resources import protect as protect_resource
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
from .tools import events as events_tools
from .tools import firewall as firewall_tools
from .tools import firewall_groups as firewall_groups_tools
from .tools import firewall_policies as firewall_policies_tools
from .tools import firewall_zones as firewall_zones_tools
from .tools import integration_api as integration_api_tools
from .tools import network_config as network_config_tools
from .tools import networks as networks_tools
from .tools import port_forwarding as port_fwd_tools
from .tools import port_profiles as port_profile_tools
from .tools import protect_cameras as protect_cameras_tools
from .tools import protect_devices as protect_devices_tools
from .tools import protect_events as protect_events_tools
from .tools import protect_nvr as protect_nvr_tools
from .tools import protect_views as protect_views_tools
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
from .utils import audit_on_failure, coerce_bool, get_logger, log_audit, validate_confirmation

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

settings = Settings()
logger = get_logger(__name__, settings.log_level)

mcp = FastMCP("UniFi MCP Server", auth=build_mcp_auth(settings))

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
    integration_api_tools,
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
    events_tools,
    devices_tools,
    ref_tools,
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
    protect_devices_tools,
    protect_cameras_tools,
    protect_views_tools,
    protect_events_tools,
    protect_nvr_tools,
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

# ---------------------------------------------------------------------------
# Profile-based module filtering (UNIFI_PROFILE env var)
#
# Set UNIFI_PROFILE to load only a subset of tools, reducing LLM context size.
# Valid profiles: network, devices, security, system, minimal, protect, read-only
# Omit UNIFI_PROFILE (or set to "all") to load all tools for the API type.
# ---------------------------------------------------------------------------

_PROFILE_MODULES: dict[str, list[Any]] = {
    "network": [
        client_mgmt_tools,
        clients_tools,
        dhcp_tools,
        dns_tools,
        network_config_tools,
        networks_tools,
        vouchers_tools,
        wans_tools,
        wifi_tools,
    ],
    "devices": [
        device_control_tools,
        devices_tools,
        diagnostics_tools,
        port_profile_tools,
        switching_tools,
        topology_tools,
    ],
    "security": [
        acls_tools,
        content_filtering_tools,
        firewall_tools,
        firewall_groups_tools,
        firewall_policies_tools,
        firewall_zones_tools,
        port_fwd_tools,
        site_vpn_tools,
        vpn_tools,
    ],
    "system": [
        application_tools,
        events_tools,
        backups_tools,
        connector_tools,
        dpi_tools,
        dpi_new_tools,
        integration_api_tools,
        qos_tools,
        radius_tools,
        ref_tools,
        site_manager_tools,
        sites_tools,
        protect_devices_tools,
        protect_cameras_tools,
        protect_views_tools,
        protect_events_tools,
        protect_nvr_tools,
        traffic_flows_tools,
        tml_tools,
    ],
    "minimal": [
        sites_tools,
        clients_tools,
        devices_tools,
    ],
    "protect": [
        protect_devices_tools,
        protect_cameras_tools,
        protect_views_tools,
        protect_events_tools,
        protect_nvr_tools,
    ],
}

_active_profile = settings.profile.value
_READ_ONLY_PREFIXES = ("get_", "list_", "stat_", "search_")


def _read_only_include(module: Any) -> list[str] | None:
    """Return a registration allowlist for the read-only profile."""
    if settings.profile != ToolProfile.READ_ONLY:
        return None
    return [name for name in dir(module) if name.startswith(_READ_ONLY_PREFIXES)]


_TOOL_MODULES: list[Any] = []
if settings.api_type in (APIType.CLOUD_V1, APIType.CLOUD_EA):
    _base_modules = list(_CLOUD_TOOL_MODULES)
    if _active_profile not in ("all", "read-only"):
        _profile_set = set(_PROFILE_MODULES.get(_active_profile, []))
        _base_modules = [m for m in _base_modules if m in _profile_set]
        if not _base_modules:
            raise ValueError(
                f"UNIFI_PROFILE={_active_profile!r} has no tools compatible with "
                f"UNIFI_API_TYPE={settings.api_type.value!r}"
            )
    _TOOL_MODULES = _base_modules
    logger.info(
        f"Cloud API mode ({settings.api_type.value})"
        + (f", profile={_active_profile}" if _active_profile else "")
        + f" - registering {len(_TOOL_MODULES)} tool module(s)"
    )
    # get_site_statistics calls /ea/sites/{id}/devices, /sta, /rest/networkconf
    # which all 404 on the live Cloud API
    for _module in _TOOL_MODULES:
        if _module is sites_tools:
            register_module_tools(
                mcp,
                _module,
                settings,
                include=_read_only_include(_module),
                exclude=["get_site_statistics"],
            )
        else:
            register_module_tools(mcp, _module, settings, include=_read_only_include(_module))
else:
    _all_local = list(_CLOUD_TOOL_MODULES) + list(_LOCAL_TOOL_MODULES)
    if _active_profile not in ("all", "read-only"):
        _profile_set = set(_PROFILE_MODULES.get(_active_profile, []))
        _TOOL_MODULES = [m for m in _all_local if m in _profile_set]
        if not _TOOL_MODULES:
            raise ValueError(f"UNIFI_PROFILE={_active_profile!r} has no compatible tools")
    else:
        _TOOL_MODULES = _all_local
    logger.info(
        "Local API mode"
        + (f", profile={_active_profile}" if _active_profile else "")
        + f" - registering {len(_TOOL_MODULES)} tool module(s)"
    )
    for _module in _TOOL_MODULES:
        register_module_tools(mcp, _module, settings, include=_read_only_include(_module))

# ---------------------------------------------------------------------------
# Resource handlers
# ---------------------------------------------------------------------------

sites_resource = SitesResource(settings)
site_manager_res = site_manager_resource.SiteManagerResource(settings)

if settings.api_type == APIType.LOCAL:
    devices_resource = DevicesResource(settings)
    clients_resource = ClientsResource(settings)
    networks_resource = NetworksResource(settings)
    protect_res = protect_resource.ProtectResource(settings)

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
if os.getenv("DEBUG", "").lower() in ("true", "1", "yes") and (
    settings.profile != ToolProfile.READ_ONLY
):

    @mcp.tool()
    async def debug_api_request(
        endpoint: str,
        method: str = "GET",
        confirm: bool | str = False,
        dry_run: bool | str = False,
    ) -> dict:
        """Debug tool to query arbitrary UniFi API endpoints.

        Args:
            endpoint: API endpoint path (e.g., /proxy/network/api/s/default/rest/networkconf)
            method: HTTP method (GET, POST, PUT, DELETE)
            confirm: Required for DELETE requests
            dry_run: Preview a DELETE without sending it

        Returns:
            Raw JSON response from the API
        """
        from .api import UniFiClient

        endpoint = validate_controller_relative_endpoint(endpoint)
        normalized_method = method.upper()
        if normalized_method == "DELETE":
            validate_confirmation(confirm, "debug API DELETE", dry_run)
            if coerce_bool(dry_run):
                log_audit(
                    operation="debug_api_request_delete",
                    parameters={"endpoint": endpoint},
                    result="dry_run",
                    dry_run=True,
                )
                return {"dry_run": True, "would_delete": endpoint}

        if normalized_method == "GET":
            async with UniFiClient(settings) as client:
                await client.authenticate()
                return await client.get(endpoint)

        if normalized_method == "DELETE":
            parameters = {"endpoint": endpoint}
            with audit_on_failure("debug_api_request_delete", parameters):
                async with UniFiClient(settings) as client:
                    await client.authenticate()
                    result = await client.delete(endpoint)
                log_audit(
                    operation="debug_api_request_delete",
                    parameters=parameters,
                    result="success",
                )
                return result

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

    @mcp.resource("protect://nvrs")
    async def get_protect_nvrs_resource() -> str:
        """Get all UniFi Protect NVRs.

        Returns:
            JSON string of NVRs list
        """
        nvrs = await protect_res.list_nvrs()
        return "\n".join([f"NVR: {n.name} ({n.id}) - {n.model}" for n in nvrs])

    @mcp.resource("protect://nvrs/{nvr_id}")
    async def get_protect_nvr_resource(nvr_id: str) -> str:
        """Get a single UniFi Protect NVR.

        Args:
            nvr_id: NVR identifier

        Returns:
            JSON string of NVR details
        """
        nvr = await protect_res.get_nvr(nvr_id)
        if nvr is None:
            return f"NVR {nvr_id} not found"
        return f"NVR: {nvr.name} ({nvr.id}) - {nvr.model}"

    @mcp.resource("protect://cameras")
    async def get_protect_cameras_resource() -> str:
        """Get all UniFi Protect cameras.

        Returns:
            JSON string of cameras list
        """
        cameras = await protect_res.list_cameras()
        return "\n".join([f"Camera: {c.name} ({c.id}) - {c.model}" for c in cameras])

    @mcp.resource("protect://cameras/{camera_id}")
    async def get_protect_camera_resource(camera_id: str) -> str:
        """Get a single UniFi Protect camera.

        Args:
            camera_id: Camera identifier

        Returns:
            JSON string of camera details
        """
        camera = await protect_res.get_camera(camera_id)
        if camera is None:
            return f"Camera {camera_id} not found"
        return f"Camera: {camera.name} ({camera.id}) - {camera.model}"


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
    if _active_profile != "all":
        logger.info(f"Profile: {_active_profile} ({len(_TOOL_MODULES)} module(s) active)")

    # ---------------------------------------------------------------------------
    # A2A protocol HTTP router (mounted when not in stdio mode)
    # ---------------------------------------------------------------------------
    a2a_state = A2AState(
        settings=settings,
        audit_logger=get_audit_logger(),
        auth_manager=AuthManager(),
        safety_controller=SafetyController(),
        confirmation_workflow=ConfirmationWorkflow(),
    )
    if settings.server_transport == TransportMode.STDIO:
        logger.info("Transport: stdio (default)")
        logger.info("Server ready to handle requests")
        mcp.run()
    else:
        logger.info(f"Transport: {settings.server_transport.value}")
        logger.info(f"Server listening on {settings.server_host}:{settings.server_port}")
        logger.info(
            "A2A endpoints: /a2a/agent-card, /a2a/discover, /a2a/delegate, /a2a/confirm, /a2a/audit"
        )
        # Register custom A2A routes before FastMCP creates its Starlette app.
        from starlette.requests import Request
        from starlette.responses import JSONResponse

        from .a2a.http_handlers import (
            confirm_handler,
            delegate_handler,
            discover_handler,
            get_agent_card_handler,
            get_audit_handler,
        )

        @mcp.custom_route("/a2a/agent-card", methods=["GET"])
        async def _a2a_agent_card(request: Request) -> JSONResponse:
            require_authenticated_request(request)
            return JSONResponse(get_agent_card_handler())

        @mcp.custom_route("/a2a/discover", methods=["POST"])
        async def _a2a_discover(request: Request) -> JSONResponse:
            require_authenticated_request(request)
            body = await request.body()
            payload = await request.json() if body else {}
            return JSONResponse(await discover_handler(payload, state=a2a_state))

        @mcp.custom_route("/a2a/delegate", methods=["POST"])
        async def _a2a_delegate(request: Request) -> JSONResponse:
            require_authenticated_request(request)
            payload = await request.json()
            return JSONResponse(await delegate_handler(payload, state=a2a_state))

        @mcp.custom_route("/a2a/confirm", methods=["POST"])
        async def _a2a_confirm(request: Request) -> JSONResponse:
            require_authenticated_request(request)
            payload = await request.json()
            return JSONResponse(await confirm_handler(payload, state=a2a_state))

        @mcp.custom_route("/a2a/audit", methods=["GET"])
        async def _a2a_audit(request: Request) -> JSONResponse:
            require_authenticated_request(request)
            payload = dict(request.query_params)
            return JSONResponse(await get_audit_handler(payload, state=a2a_state))

        logger.info("Authenticated A2A routes registered")

        mcp.run(
            transport=settings.server_transport.value,
            host=settings.server_host,
            port=settings.server_port,
        )


if __name__ == "__main__":
    main()
