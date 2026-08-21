"""Channel-planning helper tools.

These tools expose RF-neighbor surfaces used to build deterministic WiFi
channel plans (for example non-overlapping 2.4 GHz assignments).
"""

import asyncio
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

# Early Access API rate limit is 100 req/min; cap concurrent per-AP neighbor
# calls so a large site can't burst past it.
_MAX_CONCURRENT_NEIGHBOR_CALLS = 8


def _resolve_window(
    start_ms: int | None,
    end_ms: int | None,
    min_rssi: int | None,
) -> tuple[int, int]:
    """Validate planning time-window and RSSI floor and return concrete bounds."""
    now_ms = int(time.time() * 1000)
    if end_ms is None:
        end_ms = now_ms
    if start_ms is None:
        start_ms = end_ms - 24 * 3600 * 1000

    if start_ms < 0 or end_ms < 0:
        raise ValidationError("start_ms and end_ms must be non-negative epoch milliseconds")
    if end_ms <= start_ms:
        raise ValidationError("end_ms must be greater than start_ms")
    if min_rssi is not None and not -100 <= min_rssi <= -20:
        raise ValidationError(f"min_rssi must be between -100 and -20, got {min_rssi}")

    return start_ms, end_ms


def _normalize_neighbors(
    rows: Any,
    ap_mac: str,
    min_rssi: int | None,
    internal_set: set[str] | None,
    *,
    exclude_self: bool,
) -> tuple[list[dict[str, Any]], int, int]:
    """Normalize neighbor rows into a deterministic planning shape.

    Returns:
        Tuple of ``(neighbors, dropped, filtered_rssi)`` where ``dropped``
        counts malformed rows and ``filtered_rssi`` counts well-formed rows
        excluded solely because they were below ``min_rssi``.
    """
    dropped = 0
    filtered_rssi = 0
    neighbors: list[dict[str, Any]] = []

    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            dropped += 1
            continue

        neighbor_mac = row.get("mac") or row.get("bssid")
        channel = row.get("channel")
        signal = row.get("signal")
        if neighbor_mac is None or channel is None or signal is None:
            dropped += 1
            continue

        try:
            neighbor_mac_norm = validate_mac_address(str(neighbor_mac))
            channel_num = int(channel)
            signal_num = float(signal)
        except (ValidationError, TypeError, ValueError):
            dropped += 1
            continue

        if min_rssi is not None and signal_num < min_rssi:
            filtered_rssi += 1
            continue
        if internal_set is not None and neighbor_mac_norm not in internal_set:
            continue
        if exclude_self and neighbor_mac_norm == ap_mac:
            continue

        normalized = dict(row)
        normalized["ap_mac"] = ap_mac
        normalized["mac"] = neighbor_mac_norm
        normalized["channel"] = channel_num
        normalized["signal"] = signal_num
        normalized["last_seen"] = (
            row.get("last_seen")
            or row.get("lastSeen")
            or row.get("lastSeenAt")
            or row.get("lastSeenTimestamp")
        )
        normalized["radio"] = row.get("radio") or row.get("band")
        neighbors.append(normalized)

    return neighbors, dropped, filtered_rssi


def _extract_rows(response: Any) -> list[dict[str, Any]]:
    """Return response rows from common API list wrappers."""
    if isinstance(response, list):
        return [r for r in response if isinstance(r, dict)]
    if isinstance(response, dict):
        data = response.get("data", response.get("neighbors", []))
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
    return []


async def list_ap_neighbors_v2(
    site_id: str,
    ap_mac: str,
    settings: Settings,
    start_ms: int | None = None,
    end_ms: int | None = None,
    min_rssi: int | None = None,
    internal_ap_macs: list[str] | None = None,
) -> list[dict[str, Any]]:
    """List v2 neighbors observed by one managed AP.

    This exposes the v2 route used by channel-planning workflows:
    ``/proxy/network/v2/api/site/{site_id}/ap/{ap_mac}/neighbors`` with a
    timestamp window in epoch milliseconds.

    Args:
        site_id: Site identifier (UUID or short-name)
        ap_mac: AP MAC address used as the observation vantage point
        settings: Application settings
        start_ms: Window start timestamp (epoch ms). Defaults to 24h ago.
        end_ms: Window end timestamp (epoch ms). Defaults to now.
        min_rssi: Optional RSSI floor (e.g. -85)
        internal_ap_macs: Optional managed AP MAC allowlist. When provided,
            only neighbor rows whose ``mac`` is in the allowlist are returned.

    Returns:
        List of normalized neighbor dictionaries sorted by strongest RSSI first
    """
    site_id = validate_site_id(site_id)
    ap_mac = validate_mac_address(ap_mac)
    start_ms, end_ms = _resolve_window(start_ms, end_ms, min_rssi)

    logger = get_logger(__name__, settings.log_level)

    internal_set: set[str] | None = None
    if internal_ap_macs is not None:
        internal_set = set()
        for mac in internal_ap_macs:
            try:
                internal_set.add(validate_mac_address(mac))
            except ValidationError:
                logger.warning(
                    sanitize_log_message(f"Skipping invalid internal_ap_macs entry: {mac!r}")
                )

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(
            f"/proxy/network/v2/api/site/{site_id}/ap/{ap_mac}/neighbors",
            params={"start": start_ms, "end": end_ms},
        )

        neighbors, dropped, filtered_rssi = _normalize_neighbors(
            _extract_rows(response),
            ap_mac,
            min_rssi,
            internal_set,
            exclude_self=False,
        )

        neighbors.sort(key=lambda n: n.get("signal") or -999, reverse=True)
        logger.info(
            sanitize_log_message(
                f"Retrieved {len(neighbors)} v2 neighbors for AP '{ap_mac}' in site '{site_id}'"
                f" (dropped {dropped} malformed rows, filtered {filtered_rssi} below min_rssi)"
            )
        )
        return neighbors


async def list_site_internal_ap_neighbors_v2(
    site_id: str,
    settings: Settings,
    start_ms: int | None = None,
    end_ms: int | None = None,
    min_rssi: int | None = None,
) -> dict[str, Any]:
    """Build the internal AP-to-AP neighbor graph for one site.

    This helper discovers managed AP MACs for the site, calls the v2 per-AP
    neighbors endpoint for each AP, and keeps only rows where neighbor ``mac``
    belongs to the same managed AP set.

    Request budget: one ``/ea/sites/{site_id}/devices`` call plus one v2
    neighbors call per managed AP, issued with bounded concurrency (max
    ``_MAX_CONCURRENT_NEIGHBOR_CALLS`` in flight) to stay well under the
    Early Access API's 100 requests/minute limit.

    Args:
        site_id: Site identifier (UUID or short-name)
        settings: Application settings
        start_ms: Window start timestamp (epoch ms). Defaults to 24h ago.
        end_ms: Window end timestamp (epoch ms). Defaults to now.
        min_rssi: Optional RSSI floor (e.g. -85)

    Returns:
        Site-scoped internal-neighbor graph with metadata and normalized edges
    """
    site_id = validate_site_id(site_id)
    start_ms, end_ms = _resolve_window(start_ms, end_ms, min_rssi)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        devices_response = await client.get(f"/ea/sites/{site_id}/devices")
        devices = _extract_rows(devices_response)

        ap_macs: list[str] = []
        for device in devices:
            if str(device.get("type") or "").lower() != "uap":
                continue
            mac = device.get("mac") or device.get("macAddress") or device.get("mac_address")
            if not isinstance(mac, str):
                continue
            try:
                ap_macs.append(validate_mac_address(mac))
            except ValidationError:
                continue

        ap_macs = sorted(set(ap_macs))
        internal_set = set(ap_macs)

        edges: list[dict[str, Any]] = []
        skipped_aps: list[dict[str, str]] = []
        dropped_total = 0
        filtered_rssi_total = 0

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_NEIGHBOR_CALLS)

        async def _fetch_ap_neighbors(ap_mac: str) -> tuple[str, Any]:
            async with semaphore:
                response = await client.get(
                    f"/proxy/network/v2/api/site/{site_id}/ap/{ap_mac}/neighbors",
                    params={"start": start_ms, "end": end_ms},
                )
                return ap_mac, response

        results = await asyncio.gather(
            *(_fetch_ap_neighbors(ap_mac) for ap_mac in ap_macs),
            return_exceptions=True,
        )

        for ap_mac, outcome in zip(ap_macs, results, strict=True):
            if isinstance(outcome, BaseException):
                if isinstance(outcome, (APIError, ResourceNotFoundError, ValidationError)):
                    skipped_aps.append({"ap_mac": ap_mac, "reason": str(outcome)})
                    continue
                raise outcome

            _, response = outcome
            normalized, dropped, filtered_rssi = _normalize_neighbors(
                _extract_rows(response),
                ap_mac,
                min_rssi,
                internal_set,
                exclude_self=True,
            )
            edges.extend(normalized)
            dropped_total += dropped
            filtered_rssi_total += filtered_rssi

        edges.sort(
            key=lambda row: (
                str(row.get("ap_mac")),
                str(row.get("mac")),
                -float(row.get("signal", -999)),
            )
        )

        result = {
            "site_id": site_id,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "min_rssi": min_rssi,
            "managed_ap_count": len(ap_macs),
            "internal_neighbor_edges": edges,
            "internal_neighbor_edge_count": len(edges),
            "dropped_rows": dropped_total,
            "filtered_rssi_rows": filtered_rssi_total,
            "skipped_aps": skipped_aps,
        }

        logger.info(
            sanitize_log_message(
                f"Built internal v2 AP-neighbor graph for site '{site_id}' "
                f"with {len(edges)} edges across {len(ap_macs)} APs"
            )
        )
        return result
