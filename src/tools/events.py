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
    validate_mac_address,
    validate_site_id,
)
from ..utils.tool_kind import read_tool


@read_tool
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


@read_tool
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


@read_tool
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


#: The v2 system-log row types that describe a client joining or leaving.
_CLIENT_CONNECTION_TYPE = "CLIENT_CONNECTION"

#: The ``key`` prefix for each direction. The console appends a version
#: suffix (``_2``), so the prefix is matched rather than the whole key.
_CLIENT_EVENT_KEYS = {
    "connected": "CLIENT_CONNECTED_WIRELESS",
    "disconnected": "CLIENT_DISCONNECTED_WIRELESS",
}

#: Upper bound on how many pages are pulled in one call.
_MAX_LOG_PAGES = 20


@read_tool
async def list_client_connection_events(
    site_id: str,
    settings: Settings,
    event_type: str = "all",
    client_mac: str | None = None,
    hours: int = 24,
    limit: int = 100,
    page_size: int = 500,
) -> dict[str, Any]:
    """List client connection and disconnection events for a site.

    Network 11 adds an alarm for a client connecting or disconnecting.
    Live-verified 2026-11-21 against Network 10.6.111 (UniFi OS): the
    controller's ``stat/alarm`` route answers **404** there — Network 10.x
    has no alarm route — and the client events live in the v2 system log
    instead, under ``type: CLIENT_CONNECTION`` and
    ``category: CLIENT_DEVICES``.

    The system log's own ``filter`` object is **ignored** by the console:
    filtering by ``category``, ``type`` or ``key`` each returned the same
    unfiltered page. The selection below is therefore done here, on the
    rows the console returns. Pagination does work, so the window is pulled
    page by page until enough matching events are found.

    Args:
        site_id: Site identifier
        settings: Application settings
        event_type: ``all``, ``connected`` or ``disconnected``
        client_mac: Restrict to one client (MAC address)
        hours: How far back to look, in hours (1-720)
        limit: Maximum number of events to return (1-1000)
        page_size: Rows requested per page (1-1000)

    Returns:
        Dictionary with the ``events`` (newest first), the counts, and a
        ``note`` recording the two console behaviours above.

    Raises:
        ValidationError: If the arguments are out of range
    """
    site_id = validate_site_id(site_id)
    event_type = event_type.strip().lower()
    if event_type not in ("all", "connected", "disconnected"):
        raise ValueError(
            f"event_type must be one of 'all', 'connected', 'disconnected', got '{event_type}'"
        )
    if not 1 <= hours <= 720:
        raise ValueError("hours must be between 1 and 720")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000")
    wanted_mac = validate_mac_address(client_mac) if client_mac else None

    logger = get_logger(__name__, settings.log_level)
    now_ms = int(time.time() * 1000)
    window_from = now_ms - hours * 3600 * 1000

    events: list[dict[str, Any]] = []
    scanned = 0
    pages = 0
    last_page_full = False

    async with UniFiClient(settings) as client:
        await client.authenticate()

        while len(events) < limit and pages < _MAX_LOG_PAGES:
            body = {
                "timestampFrom": window_from,
                "timestampTo": now_ms,
                "pageNumber": pages,
                "pageSize": page_size,
            }
            response = await client.post(
                f"/proxy/network/v2/api/site/{site_id}/system-log/all",
                json_data=body,
            )
            rows = (
                response.get("data", response.get("systemLogs", []))
                if isinstance(response, dict)
                else response
            )
            rows = rows if isinstance(rows, list) else []
            pages += 1
            if not rows:
                last_page_full = False
                break
            scanned += len(rows)
            # A short page means the window ended here; a full one means there
            # may be more.
            last_page_full = len(rows) >= page_size

            for row in rows:
                if not isinstance(row, dict):
                    continue
                if row.get("type") != _CLIENT_CONNECTION_TYPE:
                    continue
                key = str(row.get("key", ""))
                if event_type != "all" and not key.startswith(_CLIENT_EVENT_KEYS[event_type]):
                    continue
                params = row.get("parameters") or {}
                client_info = params.get("CLIENT") or {}
                mac = str(client_info.get("id", "")).lower()
                if wanted_mac and mac != wanted_mac:
                    continue
                events.append(_normalize_client_event(row, params, client_info))
                if len(events) >= limit:
                    break

            if len(rows) < page_size:
                break

        # Truncated means the window may hold more matching events than were
        # returned: the limit was reached on a full page, or the page budget
        # ran out on a full page. A short or empty page means the window was
        # scanned to its end, even when the count happens to land on limit.
        truncated = last_page_full and (len(events) >= limit or pages >= _MAX_LOG_PAGES)

    logger.info(
        sanitize_log_message(
            f"Retrieved {len(events)} client connection event(s) for site '{site_id}' "
            f"over {hours}h"
        )
    )
    return {
        "events": events,
        "count": len(events),
        "scanned_rows": scanned,
        "pages_fetched": pages,
        "window_hours": hours,
        "event_type": event_type,
        "truncated": truncated,
        "note": (
            "The console's stat/alarm route answers 404 on Network 10.x; client "
            "connection events come from the v2 system log (type CLIENT_CONNECTION, "
            "category CLIENT_DEVICES). The system log ignores its own filter object, "
            "so the type/key/client selection is applied here. Pagination works."
        ),
    }


def _normalize_client_event(
    row: dict[str, Any],
    params: dict[str, Any],
    client_info: dict[str, Any],
) -> dict[str, Any]:
    """Flatten one system-log row into the fields a caller actually wants."""
    device = params.get("DEVICE") or {}
    wlan = params.get("WLAN") or {}
    key = str(row.get("key", ""))
    # "CLIENT_DISCONNECTED_WIRELESS_2" contains "CONNECT", so the direction is
    # read from the key's prefix, with the event name as the fallback.
    if key.startswith("CLIENT_DISCONNECTED"):
        direction = "disconnected"
    elif key.startswith("CLIENT_CONNECTED"):
        direction = "connected"
    else:
        direction = "disconnected" if "DISCONNECT" in str(row.get("event", "")) else "connected"
    return {
        "timestamp": row.get("timestamp"),
        "event": direction,
        "key": row.get("key"),
        "type": row.get("type"),
        "category": row.get("category"),
        "severity": row.get("severity"),
        "client_mac": str(client_info.get("id", "")).lower() or None,
        "client_name": client_info.get("name"),
        "client_hostname": client_info.get("hostname"),
        "client_ip": client_info.get("ip"),
        "device_mac": str(device.get("id", "")).lower() or None,
        "device_name": device.get("name"),
        "device_model": device.get("model"),
        "device_version": device.get("version"),
        "wlan": wlan.get("name"),
        "network": (params.get("NETWORK") or {}).get("name"),
        "channel": (params.get("CHANNEL") or {}).get("name"),
        "signal_strength": (params.get("SIGNAL_STRENGTH") or {}).get("name"),
        "auth_method": (params.get("AUTH_METHOD") or {}).get("name"),
        "data_up": (params.get("DATA_UP") or {}).get("name"),
        "data_down": (params.get("DATA_DOWN") or {}).get("name"),
        "duration": (params.get("DURATION") or {}).get("name"),
    }
