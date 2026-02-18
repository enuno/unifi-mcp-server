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


# Register debug tool only if DEBUG is enabled
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
    src_address: str | None = None,
    dst_address: str | None = None,
    protocol: str = "all",
    port: int | None = None,
    enabled: bool = True,
    ruleset: str = "WAN_IN",
    rule_index: int = 2000,
    src_networkconf_id: str | None = None,
    src_networkconf_type: str = "NETv4",
    dst_networkconf_id: str | None = None,
    dst_networkconf_type: str = "NETv4",
    state_established: bool = False,
    state_related: bool = False,
    state_new: bool = False,
    state_invalid: bool = False,
    logging: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new firewall rule (requires confirm=True).

    Use src_networkconf_id/dst_networkconf_id for inter-VLAN rules (pass network config ID).
    Use src_address/dst_address for IP-based rules (CIDR or single IP).
    """
    return await firewall_tools.create_firewall_rule(
        site_id=site_id,
        name=name,
        action=action,
        settings=settings,
        src_address=src_address,
        dst_address=dst_address,
        protocol=protocol,
        port=port,
        enabled=enabled,
        ruleset=ruleset,
        rule_index=rule_index,
        src_networkconf_id=src_networkconf_id,
        src_networkconf_type=src_networkconf_type,
        dst_networkconf_id=dst_networkconf_id,
        dst_networkconf_type=dst_networkconf_type,
        state_established=state_established,
        state_related=state_related,
        state_new=state_new,
        state_invalid=state_invalid,
        logging=logging,
        confirm=confirm,
        dry_run=dry_run,
    )


@mcp.tool()
async def update_firewall_rule(
    site_id: str,
    rule_id: str,
    name: str | None = None,
    action: str | None = None,
    src_address: str | None = None,
    dst_address: str | None = None,
    protocol: str | None = None,
    port: int | None = None,
    enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing firewall rule (requires confirm=True)."""
    return await firewall_tools.update_firewall_rule(
        site_id=site_id,
        rule_id=rule_id,
        settings=settings,
        name=name,
        action=action,
        src_address=src_address,
        dst_address=dst_address,
        protocol=protocol,
        port=port,
        enabled=enabled,
        confirm=confirm,
        dry_run=dry_run,
    )


@mcp.tool()
async def delete_firewall_rule(
    site_id: str, rule_id: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Delete a firewall rule (requires confirm=True)."""
    return await firewall_tools.delete_firewall_rule(site_id, rule_id, settings, confirm, dry_run)


# Backup and Restore Tools (Phase 4)
@mcp.tool()
async def trigger_backup(
    site_id: str,
    backup_type: str,
    retention_days: int = 30,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Trigger a backup operation on the UniFi controller (requires confirm=True).

    Args:
        site_id: Site identifier
        backup_type: Type of backup ("network" or "system")
        retention_days: Number of days to retain the backup (default: 30, -1 for indefinite)
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't create the backup

    Returns:
        Backup operation result including download URL and metadata
    """
    return await backups_tools.trigger_backup(
        site_id, backup_type, settings, retention_days, confirm, dry_run
    )


@mcp.tool()
async def list_backups(site_id: str) -> list[dict]:
    """List all available backups for a site.

    Args:
        site_id: Site identifier

    Returns:
        List of backup metadata dictionaries
    """
    return await backups_tools.list_backups(site_id, settings)


@mcp.tool()
async def get_backup_details(site_id: str, backup_filename: str) -> dict:
    """Get detailed information about a specific backup.

    Args:
        site_id: Site identifier
        backup_filename: Backup filename (e.g., "backup_2025-01-29.unf")

    Returns:
        Detailed backup metadata dictionary
    """
    return await backups_tools.get_backup_details(site_id, backup_filename, settings)


@mcp.tool()
async def download_backup(
    site_id: str,
    backup_filename: str,
    output_path: str,
    verify_checksum: bool = True,
) -> dict:
    """Download a backup file to local storage.

    Args:
        site_id: Site identifier
        backup_filename: Backup filename to download
        output_path: Local filesystem path to save the backup
        verify_checksum: Whether to calculate and verify file checksum

    Returns:
        Download result with file path and metadata
    """
    return await backups_tools.download_backup(
        site_id, backup_filename, output_path, settings, verify_checksum
    )


@mcp.tool()
async def delete_backup(
    site_id: str,
    backup_filename: str,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Delete a backup file from the controller (requires confirm=True).

    Args:
        site_id: Site identifier
        backup_filename: Backup filename to delete
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't delete the backup

    Returns:
        Deletion result

    Warning:
        This operation permanently deletes the backup file.
    """
    return await backups_tools.delete_backup(site_id, backup_filename, settings, confirm, dry_run)


@mcp.tool()
async def restore_backup(
    site_id: str,
    backup_filename: str,
    create_pre_restore_backup: bool = True,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Restore the UniFi controller from a backup file (requires confirm=True).

    This is a DESTRUCTIVE operation that will restore the controller to the state
    captured in the backup. The controller may restart during the restore process.

    Args:
        site_id: Site identifier
        backup_filename: Backup filename to restore from
        create_pre_restore_backup: Create automatic backup before restore (recommended)
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't restore

    Returns:
        Restore operation result including pre-restore backup info

    Warning:
        This operation will restore all configuration from the backup and may
        cause controller restart. ALWAYS use create_pre_restore_backup=True
        for safety.
    """
    return await backups_tools.restore_backup(
        site_id, backup_filename, settings, create_pre_restore_backup, confirm, dry_run
    )


@mcp.tool()
async def validate_backup(site_id: str, backup_filename: str) -> dict:
    """Validate a backup file before restore.

    Performs integrity checks on a backup file to ensure it's valid and compatible
    with the current controller version.

    Args:
        site_id: Site identifier
        backup_filename: Backup filename to validate

    Returns:
        Validation result with details and warnings
    """
    return await backups_tools.validate_backup(site_id, backup_filename, settings)


@mcp.tool()
async def get_backup_status(operation_id: str) -> dict:
    """Get the status of an ongoing or completed backup operation.

    Monitor the progress of a backup operation. Useful for tracking long-running
    system backups.

    Args:
        operation_id: Backup operation identifier (returned by trigger_backup)

    Returns:
        Backup operation status including progress and result
    """
    return await backups_tools.get_backup_status(operation_id, settings)


@mcp.tool()
async def get_restore_status(operation_id: str) -> dict:
    """Get the status of an ongoing or completed restore operation.

    Monitor the progress of a restore operation. Critical for tracking restore
    progress as controller may restart during restore.

    Args:
        operation_id: Restore operation identifier (returned by restore_backup)

    Returns:
        Restore operation status with rollback availability
    """
    return await backups_tools.get_restore_status(operation_id, settings)


@mcp.tool()
async def schedule_backups(
    site_id: str,
    backup_type: str,
    frequency: str,
    time_of_day: str,
    enabled: bool = True,
    retention_days: int = 30,
    max_backups: int = 10,
    day_of_week: int | None = None,
    day_of_month: int | None = None,
    cloud_backup_enabled: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Configure automated backup schedule (requires confirm=True).

    Set up recurring backups to run automatically at specified intervals.

    Args:
        site_id: Site identifier
        backup_type: "network" or "system"
        frequency: "daily", "weekly", or "monthly"
        time_of_day: Time in HH:MM format (24-hour)
        enabled: Whether schedule is enabled (default: True)
        retention_days: Days to retain backups (1-365, default: 30)
        max_backups: Maximum backups to keep (1-100, default: 10)
        day_of_week: For weekly: 0=Monday, 6=Sunday
        day_of_month: For monthly: 1-31
        cloud_backup_enabled: Sync to cloud (default: False)
        confirm: Must be True to execute
        dry_run: Validate without configuring (default: False)

    Returns:
        Backup schedule configuration details
    """
    return await backups_tools.schedule_backups(
        site_id,
        backup_type,
        frequency,
        time_of_day,
        settings,
        enabled,
        retention_days,
        max_backups,
        day_of_week,
        day_of_month,
        cloud_backup_enabled,
        confirm,
        dry_run,
    )


@mcp.tool()
async def get_backup_schedule(site_id: str) -> dict:
    """Get the configured automated backup schedule for a site.

    Retrieve details about the current backup schedule including frequency,
    retention policy, and next scheduled execution.

    Args:
        site_id: Site identifier

    Returns:
        Backup schedule configuration, or indication if no schedule exists
    """
    return await backups_tools.get_backup_schedule(site_id, settings)


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
    dhcp_dns_3: str | None = None,
    dhcp_dns_4: str | None = None,
    domain_name: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new network/VLAN (requires confirm=True)."""
    return await network_config_tools.create_network(
        site_id=site_id,
        name=name,
        vlan_id=vlan_id,
        subnet=subnet,
        settings=settings,
        purpose=purpose,
        dhcp_enabled=dhcp_enabled,
        dhcp_start=dhcp_start,
        dhcp_stop=dhcp_stop,
        dhcp_dns_1=dhcp_dns_1,
        dhcp_dns_2=dhcp_dns_2,
        dhcp_dns_3=dhcp_dns_3,
        dhcp_dns_4=dhcp_dns_4,
        domain_name=domain_name,
        confirm=confirm,
        dry_run=dry_run,
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
    dhcp_dns_3: str | None = None,
    dhcp_dns_4: str | None = None,
    domain_name: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing network (requires confirm=True)."""
    return await network_config_tools.update_network(
        site_id=site_id,
        network_id=network_id,
        settings=settings,
        name=name,
        vlan_id=vlan_id,
        subnet=subnet,
        purpose=purpose,
        dhcp_enabled=dhcp_enabled,
        dhcp_start=dhcp_start,
        dhcp_stop=dhcp_stop,
        dhcp_dns_1=dhcp_dns_1,
        dhcp_dns_2=dhcp_dns_2,
        dhcp_dns_3=dhcp_dns_3,
        dhcp_dns_4=dhcp_dns_4,
        domain_name=domain_name,
        confirm=confirm,
        dry_run=dry_run,
    )


@mcp.tool()
async def delete_network(
    site_id: str, network_id: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Delete a network (requires confirm=True)."""
    return await network_config_tools.delete_network(
        site_id, network_id, settings, confirm, dry_run
    )


# Device Control Tools (Phase 4)
@mcp.tool()
async def restart_device(
    site_id: str, device_mac: str, confirm: bool | str = False, dry_run: bool | str = False
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Trigger firmware upgrade for a device (requires confirm=True)."""
    return await device_control_tools.upgrade_device(
        site_id, device_mac, settings, firmware_url, confirm, dry_run
    )


# Client Management Tools (Phase 4)
@mcp.tool()
async def block_client(
    site_id: str, client_mac: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Block a client from accessing the network (requires confirm=True)."""
    return await client_mgmt_tools.block_client(site_id, client_mac, settings, confirm, dry_run)


@mcp.tool()
async def unblock_client(
    site_id: str, client_mac: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Unblock a previously blocked client (requires confirm=True)."""
    return await client_mgmt_tools.unblock_client(site_id, client_mac, settings, confirm, dry_run)


@mcp.tool()
async def reconnect_client(
    site_id: str, client_mac: str, confirm: bool | str = False, dry_run: bool | str = False
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
    networkconf_id: str | None = None,
    ap_group_ids: list[str] | None = None,
    ap_group_mode: str | None = None,
    wlan_bands: list[str] | None = None,
    optimize_iot_wifi_connectivity: bool | None = None,
    minrate_ng_enabled: bool | None = None,
    minrate_ng_data_rate_kbps: int | None = None,
    hide_ssid: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new wireless network/SSID (requires confirm=True)."""
    return await wifi_tools.create_wlan(
        site_id=site_id,
        name=name,
        security=security,
        settings=settings,
        password=password,
        enabled=enabled,
        is_guest=is_guest,
        wpa_mode=wpa_mode,
        wpa_enc=wpa_enc,
        vlan_id=vlan_id,
        networkconf_id=networkconf_id,
        ap_group_ids=ap_group_ids,
        ap_group_mode=ap_group_mode,
        wlan_bands=wlan_bands,
        optimize_iot_wifi_connectivity=optimize_iot_wifi_connectivity,
        minrate_ng_enabled=minrate_ng_enabled,
        minrate_ng_data_rate_kbps=minrate_ng_data_rate_kbps,
        hide_ssid=hide_ssid,
        confirm=confirm,
        dry_run=dry_run,
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing wireless network (requires confirm=True)."""
    return await wifi_tools.update_wlan(
        site_id=site_id,
        wlan_id=wlan_id,
        settings=settings,
        name=name,
        security=security,
        password=password,
        enabled=enabled,
        is_guest=is_guest,
        wpa_mode=wpa_mode,
        wpa_enc=wpa_enc,
        vlan_id=vlan_id,
        hide_ssid=hide_ssid,
        confirm=confirm,
        dry_run=dry_run,
    )


@mcp.tool()
async def delete_wlan(
    site_id: str, wlan_id: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Delete a wireless network (requires confirm=True)."""
    return await wifi_tools.delete_wlan(
        site_id=site_id, wlan_id=wlan_id, settings=settings, confirm=confirm, dry_run=dry_run
    )


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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    site_id: str, rule_id: str, confirm: bool | str = False, dry_run: bool | str = False
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    site_id: str, voucher_id: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Delete a specific voucher (requires confirm=True)."""
    return await vouchers_tools.delete_voucher(site_id, voucher_id, settings, confirm, dry_run)


@mcp.tool()
async def bulk_delete_vouchers(
    site_id: str, filter_expr: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Bulk delete vouchers using a filter expression (requires confirm=True)."""
    return await vouchers_tools.bulk_delete_vouchers(
        site_id, filter_expr, settings, confirm, dry_run
    )


# RADIUS Profile Tools
@mcp.tool()
async def list_radius_profiles(site_id: str) -> list[dict]:
    """List all RADIUS profiles for a site."""
    return await radius_tools.list_radius_profiles(site_id, settings)


@mcp.tool()
async def get_radius_profile(site_id: str, profile_id: str) -> dict:
    """Get details for a specific RADIUS profile."""
    return await radius_tools.get_radius_profile(site_id, profile_id, settings)


@mcp.tool()
async def create_radius_profile(
    site_id: str,
    name: str,
    auth_server: str,
    auth_secret: str,
    auth_port: int = 1812,
    acct_server: str | None = None,
    acct_port: int = 1813,
    acct_secret: str | None = None,
    use_same_secret: bool = True,
    vlan_enabled: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new RADIUS profile (requires confirm=True)."""
    return await radius_tools.create_radius_profile(
        site_id,
        name,
        auth_server,
        auth_secret,
        settings,
        auth_port,
        acct_server,
        acct_port,
        acct_secret,
        use_same_secret,
        vlan_enabled,
        confirm,
        dry_run,
    )


@mcp.tool()
async def update_radius_profile(
    site_id: str,
    profile_id: str,
    name: str | None = None,
    auth_server: str | None = None,
    auth_secret: str | None = None,
    auth_port: int | None = None,
    acct_server: str | None = None,
    acct_port: int | None = None,
    acct_secret: str | None = None,
    vlan_enabled: bool | None = None,
    enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing RADIUS profile (requires confirm=True)."""
    return await radius_tools.update_radius_profile(
        site_id,
        profile_id,
        settings,
        name,
        auth_server,
        auth_secret,
        auth_port,
        acct_server,
        acct_port,
        acct_secret,
        vlan_enabled,
        enabled,
        confirm,
        dry_run,
    )


@mcp.tool()
async def delete_radius_profile(
    site_id: str, profile_id: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Delete a RADIUS profile (requires confirm=True)."""
    return await radius_tools.delete_radius_profile(site_id, profile_id, settings, confirm, dry_run)


# RADIUS Account Tools
@mcp.tool()
async def list_radius_accounts(site_id: str) -> list[dict]:
    """List all RADIUS accounts for a site."""
    return await radius_tools.list_radius_accounts(site_id, settings)


@mcp.tool()
async def get_radius_account(site_id: str, account_id: str) -> dict:
    """Get details for a specific RADIUS account."""
    return await radius_tools.get_radius_account(site_id, account_id, settings)


@mcp.tool()
async def create_radius_account(
    site_id: str,
    username: str,
    password: str,
    vlan_id: int | None = None,
    tunnel_type: int | None = None,
    tunnel_medium_type: int | None = None,
    enabled: bool = True,
    note: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new RADIUS account / local credential (requires confirm=True).

    For VLAN assignment, set vlan_id and tunnel_type/tunnel_medium_type will auto-populate
    (13=VLAN, 6=802 media type).
    """
    return await radius_tools.create_radius_account(
        site_id=site_id,
        username=username,
        password=password,
        settings=settings,
        vlan_id=vlan_id,
        tunnel_type=tunnel_type,
        tunnel_medium_type=tunnel_medium_type,
        enabled=enabled,
        note=note,
        confirm=confirm,
        dry_run=dry_run,
    )


@mcp.tool()
async def update_radius_account(
    site_id: str,
    account_id: str,
    username: str | None = None,
    password: str | None = None,
    vlan_id: int | None = None,
    tunnel_type: int | None = None,
    tunnel_medium_type: int | None = None,
    enabled: bool | None = None,
    note: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing RADIUS account (requires confirm=True).

    At least one updatable field must be provided. For VLAN assignment, set vlan_id.
    """
    return await radius_tools.update_radius_account(
        site_id=site_id,
        account_id=account_id,
        settings=settings,
        username=username,
        password=password,
        vlan_id=vlan_id,
        tunnel_type=tunnel_type,
        tunnel_medium_type=tunnel_medium_type,
        enabled=enabled,
        note=note,
        confirm=confirm,
        dry_run=dry_run,
    )


@mcp.tool()
async def delete_radius_account(
    site_id: str, account_id: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Delete a RADIUS account (requires confirm=True)."""
    return await radius_tools.delete_radius_account(site_id, account_id, settings, confirm, dry_run)


# Guest Portal Tools
@mcp.tool()
async def get_guest_portal_config(site_id: str) -> dict:
    """Get guest portal configuration for a site."""
    return await radius_tools.get_guest_portal_config(site_id, settings)


@mcp.tool()
async def configure_guest_portal(
    site_id: str,
    portal_title: str | None = None,
    auth_method: str | None = None,
    password: str | None = None,
    session_timeout: int | None = None,
    redirect_enabled: bool | None = None,
    redirect_url: str | None = None,
    terms_of_service_enabled: bool | None = None,
    terms_of_service_text: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Configure guest portal settings (requires confirm=True)."""
    return await radius_tools.configure_guest_portal(
        site_id,
        settings,
        portal_title,
        auth_method,
        password,
        session_timeout,
        redirect_enabled,
        redirect_url,
        terms_of_service_enabled,
        terms_of_service_text,
        confirm,
        dry_run,
    )


# Hotspot Package Tools
@mcp.tool()
async def list_hotspot_packages(site_id: str) -> list[dict]:
    """List all hotspot packages for a site."""
    return await radius_tools.list_hotspot_packages(site_id, settings)


@mcp.tool()
async def get_hotspot_package(site_id: str, package_id: str) -> dict:
    """Get details for a specific hotspot package."""
    return await radius_tools.get_hotspot_package(site_id, package_id, settings)


@mcp.tool()
async def create_hotspot_package(
    site_id: str,
    name: str,
    duration_minutes: int,
    download_limit_kbps: int | None = None,
    upload_limit_kbps: int | None = None,
    download_quota_mb: int | None = None,
    upload_quota_mb: int | None = None,
    price: float | None = None,
    currency: str = "USD",
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new hotspot package (requires confirm=True)."""
    return await radius_tools.create_hotspot_package(
        site_id,
        name,
        duration_minutes,
        settings,
        download_limit_kbps,
        upload_limit_kbps,
        download_quota_mb,
        upload_quota_mb,
        price,
        currency,
        confirm,
        dry_run,
    )


@mcp.tool()
async def update_hotspot_package(
    site_id: str,
    package_id: str,
    name: str | None = None,
    duration_minutes: int | None = None,
    download_limit_kbps: int | None = None,
    upload_limit_kbps: int | None = None,
    download_quota_mb: int | None = None,
    upload_quota_mb: int | None = None,
    price: float | None = None,
    currency: str | None = None,
    enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing hotspot package (requires confirm=True).

    At least one updatable field must be provided.
    """
    return await radius_tools.update_hotspot_package(
        site_id=site_id,
        package_id=package_id,
        settings=settings,
        name=name,
        duration_minutes=duration_minutes,
        download_limit_kbps=download_limit_kbps,
        upload_limit_kbps=upload_limit_kbps,
        download_quota_mb=download_quota_mb,
        upload_quota_mb=upload_quota_mb,
        price=price,
        currency=currency,
        enabled=enabled,
        confirm=confirm,
        dry_run=dry_run,
    )


@mcp.tool()
async def delete_hotspot_package(
    site_id: str, package_id: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Delete a hotspot package (requires confirm=True)."""
    return await radius_tools.delete_hotspot_package(
        site_id, package_id, settings, confirm, dry_run
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing firewall zone (requires confirm=True)."""
    return await firewall_zones_tools.update_firewall_zone(
        site_id, firewall_zone_id, settings, name, description, network_ids, confirm, dry_run
    )


# QoS Profile Management Tools
@mcp.tool()
async def list_qos_profiles(
    site_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List all QoS profiles for traffic prioritization and shaping."""
    return await qos_tools.list_qos_profiles(site_id, settings, limit, offset)


@mcp.tool()
async def get_qos_profile(site_id: str, profile_id: str) -> dict:
    """Get details for a specific QoS profile."""
    return await qos_tools.get_qos_profile(site_id, profile_id, settings)


@mcp.tool()
async def create_qos_profile(
    site_id: str,
    name: str,
    priority_level: int,
    description: str | None = None,
    dscp_marking: int | None = None,
    bandwidth_limit_down_kbps: int | None = None,
    bandwidth_limit_up_kbps: int | None = None,
    bandwidth_guaranteed_down_kbps: int | None = None,
    bandwidth_guaranteed_up_kbps: int | None = None,
    ports: list[int] | None = None,
    protocols: list[str] | None = None,
    applications: list[str] | None = None,
    categories: list[str] | None = None,
    schedule_enabled: bool = False,
    schedule_days: list[str] | None = None,
    schedule_time_start: str | None = None,
    schedule_time_end: str | None = None,
    enabled: bool = True,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new QoS profile with comprehensive traffic shaping (requires confirm=True)."""
    return await qos_tools.create_qos_profile(
        site_id,
        name,
        priority_level,
        settings,
        description,
        dscp_marking,
        bandwidth_limit_down_kbps,
        bandwidth_limit_up_kbps,
        bandwidth_guaranteed_down_kbps,
        bandwidth_guaranteed_up_kbps,
        ports,
        protocols,
        applications,
        categories,
        schedule_enabled,
        schedule_days,
        schedule_time_start,
        schedule_time_end,
        enabled,
        confirm,
        dry_run,
    )


@mcp.tool()
async def update_qos_profile(
    site_id: str,
    profile_id: str,
    name: str | None = None,
    priority_level: int | None = None,
    description: str | None = None,
    dscp_marking: int | None = None,
    bandwidth_limit_down_kbps: int | None = None,
    bandwidth_limit_up_kbps: int | None = None,
    bandwidth_guaranteed_down_kbps: int | None = None,
    bandwidth_guaranteed_up_kbps: int | None = None,
    enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing QoS profile (requires confirm=True)."""
    return await qos_tools.update_qos_profile(
        site_id,
        profile_id,
        settings,
        name,
        priority_level,
        description,
        dscp_marking,
        bandwidth_limit_down_kbps,
        bandwidth_limit_up_kbps,
        bandwidth_guaranteed_down_kbps,
        bandwidth_guaranteed_up_kbps,
        enabled,
        confirm,
        dry_run,
    )


@mcp.tool()
async def delete_qos_profile(site_id: str, profile_id: str, confirm: bool | str = False) -> dict:
    """Delete a QoS profile (requires confirm=True)."""
    return await qos_tools.delete_qos_profile(site_id, profile_id, settings, confirm)


# ProAV Profile Management Tools
@mcp.tool()
async def list_proav_templates() -> list[dict]:
    """List available ProAV protocol templates (Dante, Q-SYS, SDVoE, AVB, RAVENNA, NDI, SMPTE 2110) and reference profiles."""
    return await qos_tools.list_proav_templates(settings)


@mcp.tool()
async def create_proav_profile(
    site_id: str,
    protocol: str,
    name: str | None = None,
    customize_ports: list[int] | None = None,
    customize_bandwidth_down_kbps: int | None = None,
    customize_bandwidth_up_kbps: int | None = None,
    customize_dscp: int | None = None,
    enabled: bool = True,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a QoS profile from a ProAV or reference template (requires confirm=True)."""
    return await qos_tools.create_proav_profile(
        site_id,
        protocol,
        settings,
        name,
        customize_ports,
        customize_bandwidth_down_kbps,
        customize_bandwidth_up_kbps,
        customize_dscp,
        enabled,
        confirm,
        dry_run,
    )


@mcp.tool()
async def validate_proav_profile(protocol: str, bandwidth_mbps: int | None = None) -> dict:
    """Validate ProAV profile requirements and provide recommendations."""
    return await qos_tools.validate_proav_profile(protocol, settings, bandwidth_mbps)


# Smart Queue Management Tools
@mcp.tool()
async def get_smart_queue_config(site_id: str) -> dict:
    """Get Smart Queue Management (SQM) configuration for bufferbloat mitigation."""
    return await qos_tools.get_smart_queue_config(site_id, settings)


@mcp.tool()
async def configure_smart_queue(
    site_id: str,
    wan_id: str,
    download_kbps: int,
    upload_kbps: int,
    algorithm: str = "fq_codel",
    overhead_bytes: int = 44,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Configure Smart Queue Management (SQM) for bufferbloat mitigation (requires confirm=True)."""
    return await qos_tools.configure_smart_queue(
        site_id,
        wan_id,
        download_kbps,
        upload_kbps,
        settings,
        algorithm,
        overhead_bytes,
        confirm,
        dry_run,
    )


@mcp.tool()
async def disable_smart_queue(site_id: str, wan_id: str, confirm: bool | str = False) -> dict:
    """Disable Smart Queue Management (SQM) (requires confirm=True)."""
    return await qos_tools.disable_smart_queue(site_id, wan_id, settings, confirm)


# Traffic Route Management Tools
@mcp.tool()
async def list_traffic_routes(
    site_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List all policy-based traffic routing rules."""
    return await qos_tools.list_traffic_routes(site_id, settings, limit, offset)


@mcp.tool()
async def create_traffic_route(
    site_id: str,
    name: str,
    action: str,
    description: str | None = None,
    source_ip: str | None = None,
    destination_ip: str | None = None,
    source_port: int | None = None,
    destination_port: int | None = None,
    protocol: str | None = None,
    vlan_id: int | None = None,
    dscp_marking: int | None = None,
    bandwidth_limit_kbps: int | None = None,
    priority: int = 100,
    enabled: bool = True,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new policy-based traffic routing rule (requires confirm=True)."""
    return await qos_tools.create_traffic_route(
        site_id,
        name,
        action,
        settings,
        description,
        source_ip,
        destination_ip,
        source_port,
        destination_port,
        protocol,
        vlan_id,
        dscp_marking,
        bandwidth_limit_kbps,
        priority,
        enabled,
        confirm,
        dry_run,
    )


@mcp.tool()
async def update_traffic_route(
    site_id: str,
    route_id: str,
    name: str | None = None,
    action: str | None = None,
    description: str | None = None,
    enabled: bool | None = None,
    priority: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing traffic routing rule (requires confirm=True)."""
    return await qos_tools.update_traffic_route(
        site_id,
        route_id,
        settings,
        name,
        action,
        description,
        enabled,
        priority,
        confirm,
        dry_run,
    )


@mcp.tool()
async def delete_traffic_route(site_id: str, route_id: str, confirm: bool | str = False) -> dict:
    """Delete a traffic routing rule (requires confirm=True)."""
    return await qos_tools.delete_traffic_route(site_id, route_id, settings, confirm)


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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    site_id: str, acl_rule_id: str, confirm: bool | str = False, dry_run: bool | str = False
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
async def list_countries(
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """List all countries with ISO codes (read-only)."""
    return await ref_tools.list_countries(settings, limit, offset)


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


@mcp.tool()
async def assign_network_to_zone(
    site_id: str,
    zone_id: str,
    network_id: str,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Dynamically assign a network to a zone (requires confirm=True)."""
    return await firewall_zones_tools.assign_network_to_zone(
        site_id, zone_id, network_id, settings, confirm, dry_run
    )


@mcp.tool()
async def get_zone_networks(site_id: str, zone_id: str) -> list[dict]:
    """List all networks in a zone."""
    return await firewall_zones_tools.get_zone_networks(site_id, zone_id, settings)


@mcp.tool()
async def delete_firewall_zone(
    site_id: str,
    zone_id: str,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Delete a firewall zone (requires confirm=True)."""
    return await firewall_zones_tools.delete_firewall_zone(
        site_id, zone_id, settings, confirm, dry_run
    )


@mcp.tool()
async def unassign_network_from_zone(
    site_id: str,
    zone_id: str,
    network_id: str,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Remove a network from a firewall zone (requires confirm=True)."""
    return await firewall_zones_tools.unassign_network_from_zone(
        site_id, zone_id, network_id, settings, confirm, dry_run
    )


# ⚠️ REMOVED: get_zone_statistics - endpoint does not exist
# Zone statistics endpoint (/firewall/zones/{id}/statistics) does not exist in UniFi API v10.0.156.
# Monitor traffic via /sites/{siteId}/clients endpoint instead.

# ⚠️ REMOVED: get_zone_matrix_policy - endpoint does not exist
# Zone matrix policy endpoint does not exist in UniFi API v10.0.156.

# ⚠️ REMOVED: delete_zbf_policy - endpoint does not exist
# Zone policy delete endpoint does not exist in UniFi API v10.0.156.


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


# Traffic Matching Lists Tools
@mcp.tool()
async def list_traffic_matching_lists(
    site_id: str,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """List all traffic matching lists in a site (read-only)."""
    return await tml_tools.list_traffic_matching_lists(site_id, settings, limit, offset)


@mcp.tool()
async def get_traffic_matching_list(site_id: str, list_id: str) -> dict:
    """Get details for a specific traffic matching list."""
    return await tml_tools.get_traffic_matching_list(site_id, list_id, settings)


@mcp.tool()
async def create_traffic_matching_list(
    site_id: str,
    list_type: str,
    name: str,
    items: list[str],
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new traffic matching list (requires confirm=True)."""
    return await tml_tools.create_traffic_matching_list(
        site_id, list_type, name, items, settings, confirm, dry_run
    )


@mcp.tool()
async def update_traffic_matching_list(
    site_id: str,
    list_id: str,
    list_type: str | None = None,
    name: str | None = None,
    items: list[str] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing traffic matching list (requires confirm=True)."""
    return await tml_tools.update_traffic_matching_list(
        site_id, list_id, settings, list_type, name, items, confirm, dry_run
    )


@mcp.tool()
async def delete_traffic_matching_list(
    site_id: str,
    list_id: str,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Delete a traffic matching list (requires confirm=True)."""
    return await tml_tools.delete_traffic_matching_list(
        site_id, list_id, settings, confirm, dry_run
    )


# Network Topology Tools
@mcp.tool()
async def get_network_topology(
    site_id: str,
    include_coordinates: bool = False,
) -> dict:
    """
    Retrieve complete network topology graph.

    Fetches the network topology including all devices, clients, and their
    interconnections. Optionally includes position coordinates for visualization.

    Args:
        site_id: Site identifier ("default" for default site)
        include_coordinates: Whether to calculate node position coordinates

    Returns:
        Network diagram with nodes, connections, and statistics
    """
    return await topology_tools.get_network_topology(site_id, settings, include_coordinates)


@mcp.tool()
async def get_device_connections(
    site_id: str,
    device_id: str | None = None,
) -> list[dict]:
    """
    Get device interconnection details.

    Retrieves detailed connection information for a specific device or all devices.

    Args:
        site_id: Site identifier
        device_id: Specific device ID, or None for all devices

    Returns:
        List of connection dictionaries
    """
    return await topology_tools.get_device_connections(site_id, device_id, settings)


@mcp.tool()
async def get_port_mappings(
    site_id: str,
    device_id: str,
) -> dict:
    """
    Get port-level connection mappings for a device.

    Retrieves detailed information about which ports are connected to which devices/clients.

    Args:
        site_id: Site identifier
        device_id: Device ID

    Returns:
        Dictionary with device_id and port mapping information
    """
    return await topology_tools.get_port_mappings(site_id, device_id, settings)


@mcp.tool()
async def export_topology(
    site_id: str,
    format: str,
) -> str:
    """
    Export network topology in various formats.

    Exports the network topology as JSON, GraphML (XML), or DOT (Graphviz) format.

    Args:
        site_id: Site identifier
        format: Export format ("json", "graphml", or "dot")

    Returns:
        Topology data as a formatted string
    """
    return await topology_tools.export_topology(site_id, format, settings)  # type: ignore


@mcp.tool()
async def get_topology_statistics(
    site_id: str,
) -> dict:
    """
    Get network topology statistics.

    Retrieves statistical summary of the network topology including device counts,
    client counts, connection counts, and network depth.

    Args:
        site_id: Site identifier

    Returns:
        Dictionary with topology statistics
    """
    return await topology_tools.get_topology_statistics(site_id, settings)


# Port Profile & Device Port Override Tools
@mcp.tool()
async def list_port_profiles(
    site_id: str, limit: int | None = None, offset: int | None = None
) -> list[dict]:
    """List all switch port profiles in a site."""
    return await port_profile_tools.list_port_profiles(site_id, settings, limit, offset)


@mcp.tool()
async def get_port_profile(site_id: str, profile_id: str) -> dict:
    """Get details for a specific port profile."""
    return await port_profile_tools.get_port_profile(site_id, profile_id, settings)


@mcp.tool()
async def create_port_profile(
    site_id: str,
    name: str,
    forward: str,
    native_networkconf_id: str | None = None,
    excluded_networkconf_ids: list[str] | None = None,
    tagged_networkconf_ids: list[str] | None = None,
    poe_mode: str | None = None,
    speed: int | None = None,
    full_duplex: bool | None = None,
    autoneg: bool | None = None,
    dot1x_ctrl: str | None = None,
    lldpmed_enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new switch port profile (requires confirm=True)."""
    return await port_profile_tools.create_port_profile(
        site_id=site_id,
        name=name,
        forward=forward,
        settings=settings,
        native_networkconf_id=native_networkconf_id,
        excluded_networkconf_ids=excluded_networkconf_ids,
        tagged_networkconf_ids=tagged_networkconf_ids,
        poe_mode=poe_mode,
        speed=speed,
        full_duplex=full_duplex,
        autoneg=autoneg,
        dot1x_ctrl=dot1x_ctrl,
        lldpmed_enabled=lldpmed_enabled,
        confirm=confirm,
        dry_run=dry_run,
    )


@mcp.tool()
async def update_port_profile(
    site_id: str,
    profile_id: str,
    name: str | None = None,
    forward: str | None = None,
    native_networkconf_id: str | None = None,
    excluded_networkconf_ids: list[str] | None = None,
    tagged_networkconf_ids: list[str] | None = None,
    poe_mode: str | None = None,
    speed: int | None = None,
    full_duplex: bool | None = None,
    autoneg: bool | None = None,
    dot1x_ctrl: str | None = None,
    lldpmed_enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing port profile (requires confirm=True)."""
    return await port_profile_tools.update_port_profile(
        site_id=site_id,
        profile_id=profile_id,
        settings=settings,
        name=name,
        forward=forward,
        native_networkconf_id=native_networkconf_id,
        excluded_networkconf_ids=excluded_networkconf_ids,
        tagged_networkconf_ids=tagged_networkconf_ids,
        poe_mode=poe_mode,
        speed=speed,
        full_duplex=full_duplex,
        autoneg=autoneg,
        dot1x_ctrl=dot1x_ctrl,
        lldpmed_enabled=lldpmed_enabled,
        confirm=confirm,
        dry_run=dry_run,
    )


@mcp.tool()
async def delete_port_profile(
    site_id: str, profile_id: str, confirm: bool | str = False, dry_run: bool | str = False
) -> dict:
    """Delete a port profile (requires confirm=True)."""
    return await port_profile_tools.delete_port_profile(
        site_id, profile_id, settings, confirm, dry_run
    )


@mcp.tool()
async def get_device_port_overrides(site_id: str, device_id: str) -> dict:
    """Get port overrides and port table for a device."""
    return await port_profile_tools.get_device_port_overrides(site_id, device_id, settings)


@mcp.tool()
async def set_device_port_overrides(
    site_id: str,
    device_id: str,
    port_overrides: list[dict],
    merge: bool = True,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Set port overrides on a device (requires confirm=True).

    Each override must include port_idx and portconf_id.
    When merge=True (default), merges with existing overrides by port_idx.
    When merge=False, replaces all overrides.
    """
    return await port_profile_tools.set_device_port_overrides(
        site_id=site_id,
        device_id=device_id,
        port_overrides=port_overrides,
        settings=settings,
        merge=merge,
        confirm=confirm,
        dry_run=dry_run,
    )


@mcp.tool()
async def get_device_by_mac(site_id: str, mac: str) -> dict:
    """Get a device by its MAC address."""
    return await port_profile_tools.get_device_by_mac(site_id, mac, settings)


# VPN Management Tools
@mcp.tool()
async def list_vpn_tunnels(
    site_id: str,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """List all site-to-site VPN tunnels (read-only)."""
    return await vpn_tools.list_vpn_tunnels(site_id, settings, limit, offset)


@mcp.tool()
async def list_vpn_servers(
    site_id: str,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """List all VPN servers (read-only)."""
    return await vpn_tools.list_vpn_servers(site_id, settings, limit, offset)


@mcp.tool()
async def list_site_to_site_vpns(site_id: str) -> list[dict]:
    """List all site-to-site IPsec VPN configurations."""
    return await site_vpn_tools.list_site_to_site_vpns(site_id, settings)


@mcp.tool()
async def get_site_to_site_vpn(site_id: str, vpn_id: str) -> dict:
    """Get details for a specific site-to-site VPN."""
    return await site_vpn_tools.get_site_to_site_vpn(site_id, vpn_id, settings)


@mcp.tool()
async def update_site_to_site_vpn(
    site_id: str,
    vpn_id: str,
    name: str | None = None,
    enabled: bool | None = None,
    ipsec_peer_ip: str | None = None,
    remote_vpn_subnets: list[str] | None = None,
    x_ipsec_pre_shared_key: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update a site-to-site VPN configuration (requires confirm=True)."""
    return await site_vpn_tools.update_site_to_site_vpn(
        site_id,
        vpn_id,
        settings,
        name=name,
        enabled=enabled,
        ipsec_peer_ip=ipsec_peer_ip,
        remote_vpn_subnets=remote_vpn_subnets,
        x_ipsec_pre_shared_key=x_ipsec_pre_shared_key,
        confirm=confirm,
        dry_run=dry_run,
    )


# Reference Data Tools
@mcp.tool()
async def list_device_tags(
    site_id: str,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """List all device tags in a site (read-only)."""
    return await ref_tools.list_device_tags(site_id, settings, limit, offset)


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
    return await site_manager_tools.get_site_health_summary(settings, site_id)  # type: ignore[return-value]


@mcp.tool()
async def get_cross_site_statistics() -> dict:
    """Get aggregate statistics across multiple sites."""
    return await site_manager_tools.get_cross_site_statistics(settings)


@mcp.tool()
async def list_vantage_points() -> list[dict]:
    """List all Vantage Points."""
    return await site_manager_tools.list_vantage_points(settings)


@mcp.tool()
async def get_site_inventory(site_id: str | None = None) -> dict:
    """Get comprehensive inventory for a site or all sites."""
    return await site_manager_tools.get_site_inventory(settings, site_id)  # type: ignore[return-value]


@mcp.tool()
async def compare_site_performance() -> dict:
    """Compare performance metrics across all sites."""
    return await site_manager_tools.compare_site_performance(settings)


@mcp.tool()
async def search_across_sites(query: str, search_type: str = "all") -> dict:
    """Search for resources across all sites (device/client/network)."""
    return await site_manager_tools.search_across_sites(settings, query, search_type)


# Site Manager - ISP Metrics Tools (added 2026-02-16)
@mcp.tool()
async def get_isp_metrics(site_id: str) -> dict:
    """Get ISP metrics for a specific site."""
    return await site_manager_tools.get_isp_metrics(settings, site_id)


@mcp.tool()
async def query_isp_metrics(
    site_id: str | None = None, start_time: str | None = None, end_time: str | None = None
) -> list[dict]:
    """Query ISP metrics with optional filters."""
    return await site_manager_tools.query_isp_metrics(settings, site_id, start_time, end_time)


# Site Manager - SD-WAN Configuration Tools (added 2026-02-16)
@mcp.tool()
async def list_sdwan_configs() -> list[dict]:
    """List all SD-WAN configurations."""
    return await site_manager_tools.list_sdwan_configs(settings)


@mcp.tool()
async def get_sdwan_config(config_id: str) -> dict:
    """Get SD-WAN configuration by ID."""
    return await site_manager_tools.get_sdwan_config(settings, config_id)


@mcp.tool()
async def get_sdwan_config_status(config_id: str) -> dict:
    """Get SD-WAN configuration deployment status."""
    return await site_manager_tools.get_sdwan_config_status(settings, config_id)


# Site Manager - Host Management Tools (added 2026-02-16)
@mcp.tool()
async def list_hosts(limit: int | None = None, offset: int | None = None) -> list[dict]:
    """List all managed hosts/consoles."""
    return await site_manager_tools.list_hosts(settings, limit, offset)


@mcp.tool()
async def get_host(host_id: str) -> dict:
    """Get host details by ID."""
    return await site_manager_tools.get_host(settings, host_id)


# Site Manager - Version Control Tool (added 2026-02-16)
@mcp.tool()
async def get_version_control() -> dict:
    """Get API version control information."""
    return await site_manager_tools.get_version_control(settings)


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
