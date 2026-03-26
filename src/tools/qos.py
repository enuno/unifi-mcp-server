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

from typing import Any

from ..api.client import UniFiClient
from ..config import Settings
from ..models.qos_profile import TrafficRoute
from ..utils import (
    ValidationError,
    audit_action,
    get_logger,
    sanitize_log_message,
    validate_confirmation,
)

logger = get_logger(__name__)


# ============================================================================
# Traffic Route Management (4 tools)
# ============================================================================


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
        logger.info(sanitize_log_message(f"Listing traffic routes for site {site_id} (limit={limit}, offset={offset})"))

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/routing")
        data = response if isinstance(response, list) else response.get("data", [])

        # Apply pagination
        paginated_data = data[offset : offset + limit]

        return [TrafficRoute(**route).model_dump() for route in paginated_data]  # type: ignore[no-any-return]


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
    match_criteria = {}
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
        logger.info(sanitize_log_message(f"[DRY RUN] Would create traffic route '{name}' for site {site_id}"))
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

        return result  # type: ignore[no-any-return]


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
        logger.info(sanitize_log_message(f"[DRY RUN] Would update traffic route {route_id} for site {site_id}"))
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

        return result  # type: ignore[no-any-return]


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

        return {  # type: ignore[no-any-return]
            "success": True,
            "message": f"Traffic route {route_id} deleted successfully",
            "route_id": route_id,
        }
