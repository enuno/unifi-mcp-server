"""Main entry point for UniFi MCP Server."""

import os

from agnost import config as agnost_config
from agnost import track
from fastmcp import FastMCP

from .config import Settings
from .resources import ClientsResource, DevicesResource, NetworksResource, SitesResource
from .resources import site_manager as site_manager_resource
from .tools import acls as acls_tools
from .tools import application as application_tools
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
from .tools import site_manager as site_manager_tools
from .tools import sites as sites_tools
from .tools import traffic_flows as traffic_flows_tools
from .tools import vouchers as vouchers_tools
from .tools import wans as wans_tools
from .tools import wifi as wifi_tools
from .tools import zbf_matrix as zbf_matrix_tools
from .utils import get_logger

# Initialize settings
settings = Settings()
logger = get_logger(__name__, settings.log_level)

# Initialize FastMCP server
mcp = FastMCP("UniFi MCP Server")

# Configure agnost tracking if enabled
if os.getenv("AGNOST_ENABLED", "false").lower() in ("true", "1", "yes"):
    agnost_org_id = os.getenv("AGNOST_ORG_ID")
    if agnost_org_id:
        try:
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
        "version": "0.2.0",
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
        site_id,
        name,
        action,
        settings,
        source,
        destination,
        protocol,
        port,
        enabled,
        confirm,
        dry_run,
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
        site_id,
        rule_id,
        settings,
        name,
        action,
        source,
        destination,
        protocol,
        port,
        enabled,
        confirm,
        dry_run,
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
        site_id,
        name,
        vlan_id,
        subnet,
        settings,
        purpose,
        dhcp_enabled,
        dhcp_start,
        dhcp_stop,
        dhcp_dns_1,
        dhcp_dns_2,
        domain_name,
        confirm,
        dry_run,
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
        site_id,
        network_id,
        settings,
        name,
        vlan_id,
        subnet,
        purpose,
        dhcp_enabled,
        dhcp_start,
        dhcp_stop,
        dhcp_dns_1,
        dhcp_dns_2,
        domain_name,
        confirm,
        dry_run,
    )


@mcp.tool()
async def delete_network(
    site_id: str, network_id: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Delete a network (requires confirm=True)."""
    return await network_config_tools.delete_network(
        site_id, network_id, settings, confirm, dry_run
    )


# Device Control Tools (Phase 4)
@mcp.tool()
async def restart_device(
    site_id: str, device_mac: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Restart a UniFi device (requires confirm=True)."""
    return await device_control_tools.restart_device(
        site_id, device_mac, settings, confirm, dry_run
    )


@mcp.tool()
async def locate_device(
    site_id: str,
    device_mac: str,
    enabled: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Enable/disable LED locate mode on a device (requires confirm=True)."""
    return await device_control_tools.locate_device(
        site_id, device_mac, settings, enabled, confirm, dry_run
    )


@mcp.tool()
async def upgrade_device(
    site_id: str,
    device_mac: str,
    firmware_url: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Trigger firmware upgrade for a device (requires confirm=True)."""
    return await device_control_tools.upgrade_device(
        site_id, device_mac, settings, firmware_url, confirm, dry_run
    )


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


# WiFi Network (SSID) Management Tools (Phase 5)
@mcp.tool()
async def list_wlans(
    site_id: str, limit: int | None = None, offset: int | None = None
) -> list[dict]:
    """List all wireless networks (SSIDs) in a site."""
    return await wifi_tools.list_wlans(site_id, settings, limit, offset)


@mcp.tool()
async def create_wlan(
    site_id: str,
    name: str,
    security: str,
    password: str | None = None,
    enabled: bool = True,
    is_guest: bool = False,
    wpa_mode: str = "wpa2",
    wpa_enc: str = "ccmp",
    vlan_id: int | None = None,
    hide_ssid: bool = False,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Create a new wireless network/SSID (requires confirm=True)."""
    return await wifi_tools.create_wlan(
        site_id,
        name,
        security,
        settings,
        password,
        enabled,
        is_guest,
        wpa_mode,
        wpa_enc,
        vlan_id,
        hide_ssid,
        confirm,
        dry_run,
    )


@mcp.tool()
async def update_wlan(
    site_id: str,
    wlan_id: str,
    name: str | None = None,
    security: str | None = None,
    password: str | None = None,
    enabled: bool | None = None,
    is_guest: bool | None = None,
    wpa_mode: str | None = None,
    wpa_enc: str | None = None,
    vlan_id: int | None = None,
    hide_ssid: bool | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Update an existing wireless network (requires confirm=True)."""
    return await wifi_tools.update_wlan(
        site_id,
        wlan_id,
        settings,
        name,
        security,
        password,
        enabled,
        is_guest,
        wpa_mode,
        wpa_enc,
        vlan_id,
        hide_ssid,
        confirm,
        dry_run,
    )


@mcp.tool()
async def delete_wlan(
    site_id: str, wlan_id: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Delete a wireless network (requires confirm=True)."""
    return await wifi_tools.delete_wlan(site_id, wlan_id, settings, confirm, dry_run)


@mcp.tool()
async def get_wlan_statistics(site_id: str, wlan_id: str | None = None) -> dict:
    """Get WiFi usage statistics for a site or specific WLAN."""
    return await wifi_tools.get_wlan_statistics(site_id, settings, wlan_id)


# Port Forwarding Management Tools (Phase 5)
@mcp.tool()
async def list_port_forwards(
    site_id: str, limit: int | None = None, offset: int | None = None
) -> list[dict]:
    """List all port forwarding rules in a site."""
    return await port_fwd_tools.list_port_forwards(site_id, settings, limit, offset)


@mcp.tool()
async def create_port_forward(
    site_id: str,
    name: str,
    dst_port: int,
    fwd_ip: str,
    fwd_port: int,
    protocol: str = "tcp_udp",
    src: str = "any",
    enabled: bool = True,
    log: bool = False,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Create a port forwarding rule (requires confirm=True)."""
    return await port_fwd_tools.create_port_forward(
        site_id,
        name,
        dst_port,
        fwd_ip,
        fwd_port,
        settings,
        protocol,
        src,
        enabled,
        log,
        confirm,
        dry_run,
    )


@mcp.tool()
async def delete_port_forward(
    site_id: str, rule_id: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Delete a port forwarding rule (requires confirm=True)."""
    return await port_fwd_tools.delete_port_forward(site_id, rule_id, settings, confirm, dry_run)


# DPI Statistics Tools (Phase 5)
@mcp.tool()
async def get_dpi_statistics(site_id: str, time_range: str = "24h") -> dict:
    """Get Deep Packet Inspection statistics for a site."""
    return await dpi_tools.get_dpi_statistics(site_id, settings, time_range)


@mcp.tool()
async def list_top_applications(
    site_id: str, limit: int = 10, time_range: str = "24h"
) -> list[dict]:
    """List top applications by bandwidth usage."""
    return await dpi_tools.list_top_applications(site_id, settings, limit, time_range)


@mcp.tool()
async def get_client_dpi(
    site_id: str,
    client_mac: str,
    time_range: str = "24h",
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    """Get DPI statistics for a specific client."""
    return await dpi_tools.get_client_dpi(site_id, client_mac, settings, time_range, limit, offset)


# Application Information Tool
@mcp.tool()
async def get_application_info() -> dict:
    """Get UniFi Network application information."""
    return await application_tools.get_application_info(settings)


# Pending Devices and Adoption Tools
@mcp.tool()
async def list_pending_devices(
    site_id: str, limit: int | None = None, offset: int | None = None
) -> list[dict]:
    """List devices awaiting adoption on the specified site."""
    return await devices_tools.list_pending_devices(site_id, settings, limit, offset)


@mcp.tool()
async def adopt_device(
    site_id: str,
    device_id: str,
    name: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Adopt a pending device onto the specified site (requires confirm=True)."""
    return await devices_tools.adopt_device(site_id, device_id, settings, name, confirm, dry_run)


@mcp.tool()
async def execute_port_action(
    site_id: str,
    device_id: str,
    port_idx: int,
    action: str,
    params: dict | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Execute an action on a specific port (power-cycle, enable, disable) (requires confirm=True)."""
    return await devices_tools.execute_port_action(
        site_id, device_id, port_idx, action, settings, params, confirm, dry_run
    )


# Enhanced Client Actions
@mcp.tool()
async def authorize_guest(
    site_id: str,
    client_mac: str,
    duration: int,
    upload_limit_kbps: int | None = None,
    download_limit_kbps: int | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Authorize a guest client for network access (requires confirm=True)."""
    return await client_mgmt_tools.authorize_guest(
        site_id,
        client_mac,
        duration,
        settings,
        upload_limit_kbps,
        download_limit_kbps,
        confirm,
        dry_run,
    )


@mcp.tool()
async def limit_bandwidth(
    site_id: str,
    client_mac: str,
    upload_limit_kbps: int | None = None,
    download_limit_kbps: int | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Apply bandwidth restrictions to a client (requires confirm=True)."""
    return await client_mgmt_tools.limit_bandwidth(
        site_id, client_mac, settings, upload_limit_kbps, download_limit_kbps, confirm, dry_run
    )


# Hotspot Voucher Tools
@mcp.tool()
async def list_vouchers(
    site_id: str,
    limit: int | None = None,
    offset: int | None = None,
    filter_expr: str | None = None,
) -> list[dict]:
    """List all hotspot vouchers for a site."""
    return await vouchers_tools.list_vouchers(site_id, settings, limit, offset, filter_expr)


@mcp.tool()
async def get_voucher(site_id: str, voucher_id: str) -> dict:
    """Get details for a specific voucher."""
    return await vouchers_tools.get_voucher(site_id, voucher_id, settings)


@mcp.tool()
async def create_vouchers(
    site_id: str,
    count: int,
    duration: int,
    upload_limit_kbps: int | None = None,
    download_limit_kbps: int | None = None,
    upload_quota_mb: int | None = None,
    download_quota_mb: int | None = None,
    note: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Create new hotspot vouchers (requires confirm=True)."""
    return await vouchers_tools.create_vouchers(
        site_id,
        count,
        duration,
        settings,
        upload_limit_kbps,
        download_limit_kbps,
        upload_quota_mb,
        download_quota_mb,
        note,
        confirm,
        dry_run,
    )


@mcp.tool()
async def delete_voucher(
    site_id: str, voucher_id: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Delete a specific voucher (requires confirm=True)."""
    return await vouchers_tools.delete_voucher(site_id, voucher_id, settings, confirm, dry_run)


@mcp.tool()
async def bulk_delete_vouchers(
    site_id: str, filter_expr: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Bulk delete vouchers using a filter expression (requires confirm=True)."""
    return await vouchers_tools.bulk_delete_vouchers(
        site_id, filter_expr, settings, confirm, dry_run
    )


# Firewall Zone Tools
@mcp.tool()
async def list_firewall_zones(site_id: str) -> list[dict]:
    """List all firewall zones for a site."""
    return await firewall_zones_tools.list_firewall_zones(site_id, settings)


@mcp.tool()
async def create_firewall_zone(
    site_id: str,
    name: str,
    description: str | None = None,
    network_ids: list[str] | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Create a new firewall zone (requires confirm=True)."""
    return await firewall_zones_tools.create_firewall_zone(
        site_id, name, settings, description, network_ids, confirm, dry_run
    )


@mcp.tool()
async def update_firewall_zone(
    site_id: str,
    firewall_zone_id: str,
    name: str | None = None,
    description: str | None = None,
    network_ids: list[str] | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Update an existing firewall zone (requires confirm=True)."""
    return await firewall_zones_tools.update_firewall_zone(
        site_id, firewall_zone_id, settings, name, description, network_ids, confirm, dry_run
    )


# ACL Tools
@mcp.tool()
async def list_acl_rules(
    site_id: str,
    limit: int | None = None,
    offset: int | None = None,
    filter_expr: str | None = None,
) -> list[dict]:
    """List all ACL rules for a site."""
    return await acls_tools.list_acl_rules(site_id, settings, limit, offset, filter_expr)


@mcp.tool()
async def get_acl_rule(site_id: str, acl_rule_id: str) -> dict:
    """Get details for a specific ACL rule."""
    return await acls_tools.get_acl_rule(site_id, acl_rule_id, settings)


@mcp.tool()
async def create_acl_rule(
    site_id: str,
    name: str,
    action: str,
    enabled: bool = True,
    source_type: str | None = None,
    source_id: str | None = None,
    source_network: str | None = None,
    destination_type: str | None = None,
    destination_id: str | None = None,
    destination_network: str | None = None,
    protocol: str | None = None,
    src_port: int | None = None,
    dst_port: int | None = None,
    priority: int = 100,
    description: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Create a new ACL rule (requires confirm=True)."""
    return await acls_tools.create_acl_rule(
        site_id,
        name,
        action,
        settings,
        enabled,
        source_type,
        source_id,
        source_network,
        destination_type,
        destination_id,
        destination_network,
        protocol,
        src_port,
        dst_port,
        priority,
        description,
        confirm,
        dry_run,
    )


@mcp.tool()
async def update_acl_rule(
    site_id: str,
    acl_rule_id: str,
    name: str | None = None,
    action: str | None = None,
    enabled: bool | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    source_network: str | None = None,
    destination_type: str | None = None,
    destination_id: str | None = None,
    destination_network: str | None = None,
    protocol: str | None = None,
    src_port: int | None = None,
    dst_port: int | None = None,
    priority: int | None = None,
    description: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Update an existing ACL rule (requires confirm=True)."""
    return await acls_tools.update_acl_rule(
        site_id,
        acl_rule_id,
        settings,
        name,
        action,
        enabled,
        source_type,
        source_id,
        source_network,
        destination_type,
        destination_id,
        destination_network,
        protocol,
        src_port,
        dst_port,
        priority,
        description,
        confirm,
        dry_run,
    )


@mcp.tool()
async def delete_acl_rule(
    site_id: str, acl_rule_id: str, confirm: bool = False, dry_run: bool = False
) -> dict:
    """Delete an ACL rule (requires confirm=True)."""
    return await acls_tools.delete_acl_rule(site_id, acl_rule_id, settings, confirm, dry_run)


# WAN Connections Tool
@mcp.tool()
async def list_wan_connections(site_id: str) -> list[dict]:
    """List all WAN connections for a site."""
    return await wans_tools.list_wan_connections(site_id, settings)


# DPI and Country Tools
@mcp.tool()
async def list_dpi_categories() -> list[dict]:
    """List all DPI categories."""
    return await dpi_new_tools.list_dpi_categories(settings)


@mcp.tool()
async def list_dpi_applications(
    limit: int | None = None,
    offset: int | None = None,
    filter_expr: str | None = None,
) -> list[dict]:
    """List all DPI applications."""
    return await dpi_new_tools.list_dpi_applications(settings, limit, offset, filter_expr)


@mcp.tool()
async def list_countries() -> list[dict]:
    """List all countries for configuration and localization."""
    return await dpi_new_tools.list_countries(settings)


# Zone-Based Firewall Matrix Tools
@mcp.tool()
async def get_zbf_matrix(site_id: str) -> dict:
    """Retrieve zone-to-zone policy matrix."""
    return await zbf_matrix_tools.get_zbf_matrix(site_id, settings)


@mcp.tool()
async def get_zone_policies(site_id: str, zone_id: str) -> list[dict]:
    """Get policies for a specific zone."""
    return await zbf_matrix_tools.get_zone_policies(site_id, zone_id, settings)


@mcp.tool()
async def update_zbf_policy(
    site_id: str,
    source_zone_id: str,
    destination_zone_id: str,
    action: str,
    description: str | None = None,
    priority: int | None = None,
    enabled: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Modify inter-zone firewall policy (requires confirm=True)."""
    return await zbf_matrix_tools.update_zbf_policy(
        site_id,
        source_zone_id,
        destination_zone_id,
        action,
        settings,
        description,
        priority,
        enabled,
        confirm,
        dry_run,
    )


@mcp.tool()
async def block_application_by_zone(
    site_id: str,
    zone_id: str,
    application_id: str,
    action: str = "block",
    enabled: bool = True,
    description: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Block applications using zone-based rules (requires confirm=True)."""
    return await zbf_matrix_tools.block_application_by_zone(
        site_id,
        zone_id,
        application_id,
        settings,
        action,
        enabled,
        description,
        confirm,
        dry_run,
    )


@mcp.tool()
async def list_blocked_applications(site_id: str, zone_id: str | None = None) -> list[dict]:
    """List applications blocked per zone."""
    return await zbf_matrix_tools.list_blocked_applications(site_id, zone_id, settings)


@mcp.tool()
async def assign_network_to_zone(
    site_id: str,
    zone_id: str,
    network_id: str,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Dynamically assign a network to a zone (requires confirm=True)."""
    return await firewall_zones_tools.assign_network_to_zone(
        site_id, zone_id, network_id, settings, confirm, dry_run
    )


@mcp.tool()
async def get_zone_networks(site_id: str, zone_id: str) -> list[dict]:
    """List all networks in a zone."""
    return await firewall_zones_tools.get_zone_networks(site_id, zone_id, settings)


# Traffic Flows Tools
@mcp.tool()
async def get_traffic_flows(
    site_id: str,
    source_ip: str | None = None,
    destination_ip: str | None = None,
    protocol: str | None = None,
    application_id: str | None = None,
    time_range: str = "24h",
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """Retrieve real-time traffic flows."""
    return await traffic_flows_tools.get_traffic_flows(
        site_id,
        settings,
        source_ip,
        destination_ip,
        protocol,
        application_id,
        time_range,
        limit,
        offset,
    )


@mcp.tool()
async def get_flow_statistics(site_id: str, time_range: str = "24h") -> dict:
    """Get aggregate flow statistics."""
    return await traffic_flows_tools.get_flow_statistics(site_id, settings, time_range)


@mcp.tool()
async def get_traffic_flow_details(site_id: str, flow_id: str) -> dict:
    """Get details for a specific traffic flow."""
    return await traffic_flows_tools.get_traffic_flow_details(site_id, flow_id, settings)


@mcp.tool()
async def get_top_flows(
    site_id: str,
    limit: int = 10,
    time_range: str = "24h",
    sort_by: str = "bytes",
) -> list[dict]:
    """Get top bandwidth-consuming flows."""
    return await traffic_flows_tools.get_top_flows(site_id, settings, limit, time_range, sort_by)


@mcp.tool()
async def get_flow_risks(
    site_id: str,
    time_range: str = "24h",
    min_risk_level: str | None = None,
) -> list[dict]:
    """Get risk assessment for flows."""
    return await traffic_flows_tools.get_flow_risks(site_id, settings, time_range, min_risk_level)


@mcp.tool()
async def get_flow_trends(
    site_id: str,
    time_range: str = "7d",
    interval: str = "1h",
) -> list[dict]:
    """Get historical flow trends."""
    return await traffic_flows_tools.get_flow_trends(site_id, settings, time_range, interval)


@mcp.tool()
async def filter_traffic_flows(
    site_id: str,
    filter_expression: str,
    time_range: str = "24h",
    limit: int | None = None,
) -> list[dict]:
    """Filter flows using a complex filter expression."""
    return await traffic_flows_tools.filter_traffic_flows(
        site_id, settings, filter_expression, time_range, limit
    )


# Site Manager Tools
@mcp.tool()
async def list_all_sites_aggregated() -> list[dict]:
    """List all sites with aggregated stats from Site Manager API."""
    return await site_manager_tools.list_all_sites_aggregated(settings)


@mcp.tool()
async def get_internet_health(site_id: str | None = None) -> dict:
    """Get internet health metrics across sites."""
    return await site_manager_tools.get_internet_health(settings, site_id)


@mcp.tool()
async def get_site_health_summary(site_id: str | None = None) -> dict:
    """Get health summary for all sites or a specific site."""
    return await site_manager_tools.get_site_health_summary(settings, site_id)


@mcp.tool()
async def get_cross_site_statistics() -> dict:
    """Get aggregate statistics across multiple sites."""
    return await site_manager_tools.get_cross_site_statistics(settings)


@mcp.tool()
async def list_vantage_points() -> list[dict]:
    """List all Vantage Points."""
    return await site_manager_tools.list_vantage_points(settings)


# Additional MCP Resources
@mcp.resource("sites://{site_id}/firewall/matrix")
async def get_zbf_matrix_resource(site_id: str) -> str:
    """Get ZBF policy matrix for a site.

    Args:
        site_id: Site identifier

    Returns:
        JSON string of ZBF matrix
    """
    matrix = await zbf_matrix_tools.get_zbf_matrix(site_id, settings)
    import json

    return json.dumps(matrix, indent=2)


@mcp.resource("sites://{site_id}/traffic/flows")
async def get_traffic_flows_resource(site_id: str) -> str:
    """Get traffic flows for a site.

    Args:
        site_id: Site identifier

    Returns:
        JSON string of traffic flows
    """
    flows = await traffic_flows_tools.get_traffic_flows(site_id, settings)
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
