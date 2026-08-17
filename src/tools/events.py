"""Controller event and alarm visibility tools.

The controller logs every client disconnect, roam, DHCP event, AP restart
and DFS hit on the legacy ``stat/event`` route, and raises alarms on
``stat/alarm`` — the primary instruments for reliability work. Network
10.x retires both classic routes; the tools fall back to the v2
system-log API. Neighboring
BSSIDs seen by the APs' background scans live on ``stat/rogueap``.
"""

import time
from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import (
    APIError,
    ResourceNotFoundError,
    ValidationError,
    get_logger,
    sanitize_log_message,
    validate_site_id,
)


async def list_events(
    site_id: str,
    settings: Settings,
    hours: int = 24,
    limit: int = 1000,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    """List recent controller events for a site.

    Events carry a ``key`` (e.g. ``EVT_WU_Disconnected``,
    ``EVT_AP_RestartedUnknown``, ``EVT_WU_Roam``), the affected
    client/device identifiers, and an epoch-ms ``time``. On the v2
    system-log fallback the client identity is nested under
    ``parameters.CLIENT`` (``id`` is the MAC).

    Args:
        site_id: Site identifier
        settings: Application settings
        hours: How far back to look (default 24)
        limit: Maximum events to return (default 1000, newest first —
            a busy home site logs several hundred events per day, so a
            small limit silently truncates rate measurements)
        event_type: Optional case-insensitive substring filter on the
            event ``key`` (e.g. "disconnect", "roam", "restart")

    Returns:
        List of event dictionaries, newest first
    """
    site_id = validate_site_id(site_id)
    if hours < 1:
        raise ValidationError(f"hours must be at least 1, got {hours}")
    if not 1 <= limit <= 3000:
        raise ValidationError(f"limit must be between 1 and 3000, got {limit}")
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        events: list[dict[str, Any]] = []
        try:
            response = await client.post(
                f"/ea/sites/{site_id}/stat/event",
                json_data={"_limit": limit, "within": hours, "_sort": "-time"},
            )
            data = response.get("data", []) if isinstance(response, dict) else response
            events = [e for e in (data if isinstance(data, list) else []) if isinstance(e, dict)]
        except (APIError, ResourceNotFoundError):
            # Network 10.x retires the classic stat/event; the system log
            # moved to the v2 API.
            now_ms = int(time.time() * 1000)
            response = await client.post(
                f"/proxy/network/v2/api/site/{site_id}/system-log/all",
                json_data={
                    "timestampFrom": now_ms - hours * 3600 * 1000,
                    "timestampTo": now_ms,
                    "pageNumber": 0,
                    "pageSize": limit,
                },
            )
            if isinstance(response, dict):
                raw = response.get("data", response.get("systemLogs", []))
            else:
                raw = response
            events = [e for e in (raw if isinstance(raw, list) else []) if isinstance(e, dict)]

        if event_type:
            needle = event_type.lower()
            events = [e for e in events if needle in str(e.get("key", "")).lower()]

        logger.info(
            sanitize_log_message(
                f"Retrieved {len(events)} events for site '{site_id}' (last {hours}h)"
            )
        )
        return events


async def list_alarms(
    site_id: str,
    settings: Settings,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    """List controller alarms for a site.

    Alarms are the controller's own escalations — device offline, radar
    detection, IPS hits — and stay active until archived.

    Args:
        site_id: Site identifier
        settings: Application settings
        include_archived: Also return archived (acknowledged) alarms

    Returns:
        List of alarm dictionaries, newest first
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        alarms: list[dict[str, Any]] = []
        try:
            endpoint = f"/ea/sites/{site_id}/stat/alarm"
            if not include_archived:
                endpoint += "?archived=false"
            response = await client.get(endpoint)
            data = response.get("data", []) if isinstance(response, dict) else response
            alarms = [a for a in (data if isinstance(data, list) else []) if isinstance(a, dict)]
        except (APIError, ResourceNotFoundError):
            # Network 10.x folds alarms into the v2 system log's critical
            # tab; window the last week.
            now_ms = int(time.time() * 1000)
            response = await client.post(
                f"/proxy/network/v2/api/site/{site_id}/system-log/critical",
                json_data={
                    "timestampFrom": now_ms - 7 * 24 * 3600 * 1000,
                    "timestampTo": now_ms,
                    "pageNumber": 0,
                    "pageSize": 200,
                },
            )
            if isinstance(response, dict):
                raw = response.get("data", response.get("systemLogs", []))
            else:
                raw = response
            alarms = [a for a in (raw if isinstance(raw, list) else []) if isinstance(a, dict)]

        logger.info(sanitize_log_message(f"Retrieved {len(alarms)} alarms for site '{site_id}'"))
        return alarms


async def list_neighboring_aps(
    site_id: str,
    settings: Settings,
    min_rssi: int | None = None,
) -> list[dict[str, Any]]:
    """List neighboring access points seen by the site's APs.

    Read from ``stat/rogueap`` — every foreign BSSID the APs observe in
    background scans, with SSID, channel, band and signal. The primary
    instrument for channel-congestion analysis.

    Args:
        site_id: Site identifier
        settings: Application settings
        min_rssi: Optional floor; neighbors weaker than this are dropped
            (e.g. -85 to ignore distant networks)

    Returns:
        List of neighbor dictionaries, strongest first
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/stat/rogueap")
        data = response.get("data", []) if isinstance(response, dict) else response
        neighbors = [n for n in (data if isinstance(data, list) else []) if isinstance(n, dict)]

        if min_rssi is not None:
            neighbors = [
                n
                for n in neighbors
                if isinstance(n.get("signal"), int | float) and n["signal"] >= min_rssi
            ]

        neighbors.sort(key=lambda n: n.get("signal") or -999, reverse=True)
        logger.info(
            sanitize_log_message(f"Retrieved {len(neighbors)} neighboring APs for site '{site_id}'")
        )
        return neighbors
