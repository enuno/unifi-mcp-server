"""Traffic route and Smart Queue tools.

Note: QoS Profile Management (5 tools), ProAV Profile Management (3 tools),
and Smart Queue Management (3 tools) were removed because they used endpoints
(rest/qosprofile, rest/wanconf) that do not exist on any UniFi API surface
(local gateway or cloud EA). These tools were AI-generated against assumed
endpoint patterns that Ubiquiti never implemented. The unit tests passed
because they mock the HTTP layer, so the non-existent endpoints were never
caught until tested against real hardware.

The traffic route tools had the same defect in a quieter form (issue #171):
they read ``rest/routing`` (which exists, but serves static routes) with a
schema matching no UniFi resource, so ``list_traffic_routes`` always returned
``[]``. ``list_traffic_routes`` now reads UniFi's Traffic Routes from the v2
``trafficroutes`` endpoint. ``create_traffic_route``, ``update_traffic_route``
and ``delete_traffic_route`` were removed until their v2 write paths can be
verified against real hardware.

See: https://developer.ui.com/network/ for documented endpoints.
"""

from typing import Any

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..models.qos_profile import TrafficRoute
from ..utils import (
    APIError,
    ValidationError,
    audit_action,
    coerce_bool,
    first_response_item,
    get_logger,
    sanitize_log_message,
    validate_confirmation,
    validate_limit_offset,
    validate_site_id,
)

logger = get_logger(__name__)


# ============================================================================
# Traffic Routes (v2 API, local gateway only)
# ============================================================================


async def list_traffic_routes(
    site_id: str,
    settings: Settings,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List UniFi Traffic Routes (policy-based routing rules) for a site.

    Reads ``/proxy/network/v2/api/site/{site}/trafficroutes``. Each route
    says what it matches (``matching_target``: INTERNET, DOMAIN, IP or
    REGION, with the matching ``domains`` / ``ip_addresses`` /
    ``ip_ranges`` / ``regions``), which clients or networks it applies to
    (``target_devices``), and the interface traffic egresses through
    (``network_id``, e.g. a VPN client network).

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of routes to return
        offset: Number of routes to skip

    Returns:
        List of traffic routes

    Raises:
        NotImplementedError: When not using the local API (v2 endpoints are
            only reachable on a local gateway)
        APIError: When the controller's response is not a list of routes;
            raised rather than reported as an empty list, so "no routes
            configured" is never confused with "wrong endpoint"
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError(
            "Traffic routes (v2 API) are only available when UNIFI_API_TYPE='local'. "
            "Please configure a local UniFi gateway connection to use this tool."
        )

    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(
                f"Listing traffic routes for site {site_id} (limit={limit}, offset={offset})"
            )
        )

        if not client.is_authenticated:
            await client.authenticate()

        normalized_site_id = client._site_uuid_to_name.get(site_id, site_id)
        response = await client.get(f"{settings.get_v2_api_path(normalized_site_id)}/trafficroutes")

        routes = response.get("data") if isinstance(response, dict) else response
        if not isinstance(routes, list) or not all(isinstance(r, dict) for r in routes):
            raise APIError(
                "Unexpected response from the trafficroutes endpoint: expected a list of "
                f"route objects, got {type(routes).__name__}"
            )

        paginated = routes[offset : offset + limit]
        return [TrafficRoute.model_validate(route).model_dump() for route in paginated]


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
        stored = first_response_item(response)
        if not stored:
            # The controller accepted the write without echoing it; re-read
            # so the caller sees stored state rather than their own input.
            refetched = await client.get(f"/ea/sites/{site_id}/rest/networkconf/{wan_id}")
            stored = first_response_item(refetched)

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
