"""Traffic route management tools.

Note: QoS Profile Management (5 tools), ProAV Profile Management (3 tools),
and Smart Queue Management (3 tools) were removed because they used endpoints
(rest/qosprofile, rest/wanconf) that do not exist on any UniFi API surface
(local gateway or cloud EA). These tools were AI-generated against assumed
endpoint patterns that Ubiquiti never implemented. The unit tests passed
because they mock the HTTP layer, so the non-existent endpoints were never
caught until tested against real hardware.

See: https://developer.ui.com/network/ for documented endpoints.
"""

from typing import Any, cast

from ..api.client import UniFiClient
from ..config import Settings
from ..models.qos_profile import TrafficRoute
from ..utils import (
    APIError,
    ValidationError,
    audit_action,
    coerce_bool,
    get_logger,
    sanitize_log_message,
    validate_confirmation,
    validate_site_id,
)

logger = get_logger(__name__)


# ============================================================================
# Traffic Route Management (4 tools)
# ============================================================================


def _first_item(response: object) -> dict:
    """Unwrap the first item of a UniFi list response, else {}.

    Local copy of the shared helper proposed in the empty-response-parsing
    PR; collapse onto it once that lands.
    """
    data = response.get("data") if isinstance(response, dict) else response
    if isinstance(data, dict):
        # Some routes wrap a single object rather than a list of one.
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return {}


async def list_traffic_routes(
    site_id: str,
    settings: Settings,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List all traffic routing policies for a site.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of routes to return
        offset: Number of routes to skip

    Returns:
        List of traffic routing policies
    """
    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(
                f"Listing traffic routes for site {site_id} (limit={limit}, offset={offset})"
            )
        )

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/routing")
        data = cast(
            list[dict[str, Any]],
            response if isinstance(response, list) else response.get("data", []),
        )

        traffic_routes: list[dict[str, Any]] = [
            route
            for route in data
            if "static-route_nexthop" not in route
            and "action" in route
            and "match_criteria" in route
        ]

        skipped_routes = len(data) - len(traffic_routes)
        if skipped_routes:
            logger.info(
                sanitize_log_message(
                    f"Skipped {skipped_routes} non-traffic route(s) returned by /rest/routing"
                )
            )

        # Apply pagination over traffic routes only
        paginated_data = traffic_routes[offset : offset + limit]

        return [TrafficRoute(**route).model_dump() for route in paginated_data]


async def create_traffic_route(
    site_id: str,
    name: str,
    action: str,
    settings: Settings,
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
) -> dict[str, Any]:
    """Create a new traffic routing policy.

    Args:
        site_id: Site identifier
        name: Route name
        action: Route action (allow, deny, mark, shape)
        settings: Application settings
        description: Route description
        source_ip: Source IP address or CIDR
        destination_ip: Destination IP address or CIDR
        source_port: Source port (1-65535)
        destination_port: Destination port (1-65535)
        protocol: Protocol (tcp, udp, icmp, all)
        vlan_id: VLAN ID (1-4094)
        dscp_marking: DSCP value to mark packets (0-63, for mark action)
        bandwidth_limit_kbps: Bandwidth limit in kbps (for shape action)
        priority: Route priority (1-1000, lower = higher priority)
        enabled: Route enabled
        confirm: Confirmation flag (required for creation)
        dry_run: If True, validate but don't execute

    Returns:
        Created traffic route
    """
    validate_confirmation(confirm, "create traffic route", dry_run)

    # Validate action
    valid_actions = ["allow", "deny", "mark", "shape"]
    if action not in valid_actions:
        raise ValidationError(f"Invalid action '{action}'. Use: {', '.join(valid_actions)}")

    # Validate DSCP marking
    if dscp_marking is not None and not 0 <= dscp_marking <= 63:
        raise ValidationError(f"DSCP marking must be 0-63, got {dscp_marking}")

    # Validate priority
    if not 1 <= priority <= 1000:
        raise ValidationError(f"Priority must be 1-1000, got {priority}")

    # Build match criteria
    match_criteria: dict[str, Any] = {}
    if source_ip:
        match_criteria["source_ip"] = source_ip
    if destination_ip:
        match_criteria["destination_ip"] = destination_ip
    if source_port:
        match_criteria["source_port"] = source_port
    if destination_port:
        match_criteria["destination_port"] = destination_port
    if protocol:
        match_criteria["protocol"] = protocol
    if vlan_id:
        match_criteria["vlan_id"] = vlan_id

    # Build route data
    route_data: dict[str, Any] = {
        "name": name,
        "action": action,
        "match_criteria": match_criteria,
        "priority": priority,
        "enabled": enabled,
    }

    if description:
        route_data["description"] = description
    if dscp_marking is not None:
        route_data["dscp_marking"] = dscp_marking
    if bandwidth_limit_kbps is not None:
        route_data["bandwidth_limit_kbps"] = bandwidth_limit_kbps

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"[DRY RUN] Would create traffic route '{name}' for site {site_id}"
            )
        )
        return {"dry_run": True, "route": route_data}

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Creating traffic route '{name}' for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.post(f"/ea/sites/{site_id}/rest/routing", json_data=route_data)

        data = response if isinstance(response, list) else response.get("data", [])
        if not data:
            raise ValidationError("Failed to create traffic route")

        result = TrafficRoute(**data[0]).model_dump()

        await audit_action(
            settings,
            action_type="create_traffic_route",
            resource_type="traffic_route",
            resource_id=result.get("id", "unknown"),
            details={"name": name, "action": action},
            site_id=site_id,
        )

        return result


async def update_traffic_route(
    site_id: str,
    route_id: str,
    settings: Settings,
    name: str | None = None,
    action: str | None = None,
    description: str | None = None,
    enabled: bool | None = None,
    priority: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing traffic routing policy.

    Args:
        site_id: Site identifier
        route_id: Traffic route ID to update
        settings: Application settings
        name: New route name
        action: New route action (allow, deny, mark, shape)
        description: New description
        enabled: New enabled state
        priority: New priority (1-1000)
        confirm: Confirmation flag (required for updates)
        dry_run: If True, validate but don't execute

    Returns:
        Updated traffic route
    """
    validate_confirmation(confirm, "update traffic route", dry_run)

    # Build update data
    update_data: dict[str, Any] = {}
    if name is not None:
        update_data["name"] = name
    if action is not None:
        update_data["action"] = action
    if description is not None:
        update_data["description"] = description
    if enabled is not None:
        update_data["enabled"] = enabled
    if priority is not None:
        if not 1 <= priority <= 1000:
            raise ValidationError(f"Priority must be 1-1000, got {priority}")
        update_data["priority"] = priority

    if not update_data:
        raise ValidationError("No update fields provided")

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"[DRY RUN] Would update traffic route {route_id} for site {site_id}"
            )
        )
        return {"dry_run": True, "route_id": route_id, "updates": update_data}

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Updating traffic route {route_id} for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.put(
            f"/ea/sites/{site_id}/rest/routing/{route_id}", json_data=update_data
        )

        data = response if isinstance(response, list) else response.get("data", [])
        if not data:
            raise ValidationError(f"Failed to update traffic route {route_id}")

        result = TrafficRoute(**data[0]).model_dump()

        await audit_action(
            settings,
            action_type="update_traffic_route",
            resource_type="traffic_route",
            resource_id=route_id,
            details=update_data,
            site_id=site_id,
        )

        return result


async def delete_traffic_route(
    site_id: str,
    route_id: str,
    settings: Settings,
    confirm: bool | str = False,
) -> dict[str, Any]:
    """Delete a traffic routing policy.

    Args:
        site_id: Site identifier
        route_id: Traffic route ID to delete
        settings: Application settings
        confirm: Confirmation flag (required for deletion)

    Returns:
        Deletion confirmation
    """
    validate_confirmation(confirm, "delete traffic route")

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Deleting traffic route {route_id} for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        await client.delete(f"/ea/sites/{site_id}/rest/routing/{route_id}")

        await audit_action(
            settings,
            action_type="delete_traffic_route",
            resource_type="traffic_route",
            resource_id=route_id,
            details={"deleted": True},
            site_id=site_id,
        )

        return {
            "success": True,
            "message": f"Traffic route {route_id} deleted successfully",
            "route_id": route_id,
        }


# ============================================================================
# WAN Smart Queues (fq_codel)
# ============================================================================


async def _find_wan_network(
    client: UniFiClient, site_id: str, wan_network_id: str | None
) -> dict[str, Any]:
    """Locate the WAN networkconf record Smart Queues live on.

    Smart Queues are fields on the WAN network configuration
    (``wan_smartq_enabled``, ``wan_smartq_down_rate``,
    ``wan_smartq_up_rate``) — not the ``rest/wanconf`` resource the
    removed tools invented, which exists on no controller. The rate
    fields are stored in **kbps** (verified live: writing 840 shaped the
    line to 0.84 Mbps), even though the controller UI displays Mbps.

    Args:
        client: Authenticated API client
        site_id: Site identifier
        wan_network_id: Explicit WAN networkconf _id, or None for the
            primary WAN (first record with purpose ``wan``)

    Returns:
        The WAN networkconf record

    Raises:
        APIError: If no WAN network matches
    """
    response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")
    networks = response if isinstance(response, list) else response.get("data", [])
    wans = [
        n
        for n in (networks if isinstance(networks, list) else [])
        if isinstance(n, dict) and n.get("purpose") == "wan"
    ]
    if wan_network_id is not None:
        for wan in wans:
            if wan.get("_id") == wan_network_id:
                return wan
        raise APIError(f"No WAN network with id {wan_network_id} on this site")
    if not wans:
        raise APIError("This site has no WAN network to configure Smart Queues on")
    return wans[0]


async def get_smart_queue_status(
    site_id: str,
    settings: Settings,
    wan_network_id: str | None = None,
) -> dict[str, Any]:
    """Read the Smart Queue (fq_codel) configuration of a WAN.

    Args:
        site_id: Site identifier
        settings: Application settings
        wan_network_id: Optional WAN networkconf _id; defaults to the
            primary WAN

    Returns:
        Dictionary with the WAN's smart queue state; rates are Mbps
    """
    site_id = validate_site_id(site_id)

    async with UniFiClient(settings) as client:
        if not client.is_authenticated:
            await client.authenticate()

        wan = await _find_wan_network(client, site_id, wan_network_id)
        logger.info(sanitize_log_message(f"Read smart queue state for WAN '{wan.get('name')}'"))
        down_kbps = wan.get("wan_smartq_down_rate")
        up_kbps = wan.get("wan_smartq_up_rate")
        return {
            "wan_network_id": wan.get("_id"),
            "wan_name": wan.get("name"),
            "enabled": bool(wan.get("wan_smartq_enabled", False)),
            "download_mbps": down_kbps / 1000 if isinstance(down_kbps, int | float) else None,
            "upload_mbps": up_kbps / 1000 if isinstance(up_kbps, int | float) else None,
        }


async def configure_smart_queue(
    site_id: str,
    settings: Settings,
    enabled: bool = True,
    download_mbps: int | None = None,
    upload_mbps: int | None = None,
    wan_network_id: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Enable, retune, or disable Smart Queues (fq_codel) on a WAN.

    Writes the ``wan_smartq_*`` fields onto the WAN networkconf. The
    tool takes rates in Mbps and converts to the kbps the controller
    stores — writing Mbps-scale numbers raw shapes the line to roughly
    nothing (verified live). Both rates are required when enabling.
    Applying the change triggers a gateway reprovision, which can
    briefly interrupt WAN traffic.

    Args:
        site_id: Site identifier
        settings: Application settings
        enabled: Turn the shaper on or off
        download_mbps: Shaped download rate in Mbps (required to enable)
        upload_mbps: Shaped upload rate in Mbps (required to enable)
        wan_network_id: Optional WAN networkconf _id; defaults to the
            primary WAN
        confirm: Confirmation flag (required)
        dry_run: If True, preview the write without sending it

    Returns:
        The WAN's stored smart queue state after the write (re-read from
        the controller, so callers see what actually stuck)
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "configure smart queue", dry_run)
    dry_run = coerce_bool(dry_run)

    if enabled:
        for label, value in (("download_mbps", download_mbps), ("upload_mbps", upload_mbps)):
            if value is None:
                raise ValidationError(f"{label} is required when enabling smart queues")
            if not 1 <= value <= 100_000:
                raise ValidationError(f"{label} must be between 1 and 100000 Mbps, got {value}")

    async with UniFiClient(settings) as client:
        if not client.is_authenticated:
            await client.authenticate()

        wan = await _find_wan_network(client, site_id, wan_network_id)
        wan_id = wan.get("_id")

        payload: dict[str, Any] = {"wan_smartq_enabled": enabled}
        if download_mbps is not None:
            payload["wan_smartq_down_rate"] = int(download_mbps * 1000)
        if upload_mbps is not None:
            payload["wan_smartq_up_rate"] = int(upload_mbps * 1000)

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would write smart queue config to WAN '{wan.get('name')}'"
                )
            )
            return {"dry_run": True, "wan_network_id": wan_id, "payload": payload}

        response = await client.put(
            f"/ea/sites/{site_id}/rest/networkconf/{wan_id}", json_data=payload
        )
        stored = _first_item(response)
        if not stored:
            # The controller accepted the write without echoing it; re-read
            # so the caller sees stored state rather than their own input.
            refetched = await client.get(f"/ea/sites/{site_id}/rest/networkconf/{wan_id}")
            stored = _first_item(refetched)

        await audit_action(
            settings,
            action_type="configure_smart_queue",
            resource_type="network",
            resource_id=wan_id or "unknown",
            site_id=site_id,
            details={"enabled": enabled, "down": download_mbps, "up": upload_mbps},
        )

        logger.info(
            sanitize_log_message(
                f"Smart queue config written to WAN '{wan.get('name')}' "
                f"(enabled={enabled}, down={download_mbps}, up={upload_mbps})"
            )
        )
        stored_down = stored.get("wan_smartq_down_rate")
        stored_up = stored.get("wan_smartq_up_rate")
        return {
            "wan_network_id": wan_id,
            "wan_name": stored.get("name", wan.get("name")),
            "enabled": bool(stored.get("wan_smartq_enabled", False)),
            "download_mbps": (stored_down / 1000 if isinstance(stored_down, int | float) else None),
            "upload_mbps": stored_up / 1000 if isinstance(stored_up, int | float) else None,
        }
