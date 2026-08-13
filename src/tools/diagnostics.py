"""Network diagnostics MCP tools."""

import time
from datetime import datetime, timezone
from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models.diagnostics import NetworkReference, SpeedTestResult
from ..utils import (
    ValidationError,
    get_logger,
    sanitize_log_message,
    validate_mac_address,
    validate_site_id,
)


async def get_network_references(
    site_id: str, network_id: str, settings: Settings
) -> dict[str, Any]:
    """Get references to a network from other resources.

    Args:
        site_id: Site identifier
        network_id: Network identifier
        settings: Application settings

    Returns:
        Dictionary with network reference information
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/networkconf/{network_id}/references")
        data = response.get("data", {}) if isinstance(response, dict) else {}
        if not isinstance(data, dict):
            data = {}

        references_data = data.get("referenceResources", []) if isinstance(data, dict) else []
        references = [NetworkReference(**ref).model_dump() for ref in references_data]

        logger.info(
            sanitize_log_message(f"Retrieved {len(references)} references for network {network_id}")
        )
        return {
            "network_id": network_id,
            "site_id": site_id,
            "references": references,
        }


async def run_speed_test(site_id: str, settings: Settings) -> dict[str, Any]:
    """Initiate a WAN speed test on the site.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Dictionary with speed test initiation status
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.post(
            f"/ea/sites/{site_id}/cmd/devmgr",
            json_data={"cmd": "speedtest"},
        )
        data = response.get("data", {}) if isinstance(response, dict) else response
        if not isinstance(data, dict):
            data = {"status": "started"}

        logger.info(sanitize_log_message(f"Initiated speed test for site '{site_id}'"))
        return {
            "site_id": site_id,
            "status": data.get("status", "started"),
            "test_id": data.get("test_id"),
        }


async def get_speed_test_status(site_id: str, settings: Settings) -> dict[str, Any]:
    """Get the current status of a running or completed speed test.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Dictionary with speed test status and results
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/cmd/devmgr/speedtest-status")
        data = response.get("data", {}) if isinstance(response, dict) else response
        if not isinstance(data, dict):
            data = {}

        speed_test = SpeedTestResult(**data)
        logger.info(sanitize_log_message(f"Retrieved speed test status for site '{site_id}'"))
        return speed_test.model_dump()


async def get_speed_test_history(
    site_id: str, settings: Settings, hours: int = 168
) -> list[dict[str, Any]]:
    """Get historical speed test results for a site.

    Reads the ``stat/report/archive.speedtest`` report — the route the
    controller actually stores results under. The previous
    ``rest/speedtest`` resource does not exist and failed every call with
    ``api.err.InvalidObject``.

    Args:
        site_id: Site identifier
        settings: Application settings
        hours: How far back to look (default 168 = 7 days)

    Returns:
        List of speed test result dictionaries, oldest first
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    try:
        hours = int(hours)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"hours must be an integer, got {hours!r}") from exc
    if hours < 1:
        raise ValidationError(f"hours must be at least 1, got {hours}")

    end_ms = int(time.time() * 1000)
    start_ms = end_ms - hours * 3600 * 1000

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.post(
            f"/ea/sites/{site_id}/stat/report/archive.speedtest",
            json_data={
                "attrs": ["time", "xput_download", "xput_upload", "latency"],
                "start": start_ms,
                "end": end_ms,
            },
        )
        data = response.get("data", []) if isinstance(response, dict) else response
        if not isinstance(data, list):
            data = []

        # Archive entries report xput_* in Mbps, latency in ms and time in
        # epoch milliseconds; translate to this module's result shape.
        # Sort explicitly: the docstring promises oldest first, and the
        # report's own ordering is not guaranteed.
        rows = sorted(
            (item for item in data if isinstance(item, dict)),
            key=lambda item: item.get("time") or 0,
        )
        results = []
        for item in rows:
            ts = item.get("time")
            results.append(
                SpeedTestResult(
                    id=item.get("_id"),
                    download_speed_mbps=item.get("xput_download"),
                    upload_speed_mbps=item.get("xput_upload"),
                    ping_ms=item.get("latency"),
                    timestamp=(
                        datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
                        if isinstance(ts, int | float)
                        else None
                    ),
                ).model_dump(exclude_none=True)
            )

        logger.info(
            sanitize_log_message(
                f"Retrieved {len(results)} speed test results for site '{site_id}'"
            )
        )
        return results


async def _spectrum_scan_targets(
    client: UniFiClient, site_id: str, ap_mac: str | None
) -> list[str]:
    """Resolve which access points to query for spectrum data.

    Args:
        client: Authenticated API client
        site_id: Site identifier
        ap_mac: Explicit AP MAC, or None to enumerate the site's APs

    Returns:
        List of AP MAC addresses
    """
    if ap_mac:
        return [ap_mac]
    response = await client.get(f"/ea/sites/{site_id}/devices")
    devices = response.get("data", []) if isinstance(response, dict) else response
    if not isinstance(devices, list):
        return []
    return [
        d.get("mac")
        for d in devices
        if isinstance(d, dict) and d.get("type") == "uap" and d.get("mac")
    ]


async def get_spectrum_scan(
    site_id: str, settings: Settings, ap_mac: str | None = None
) -> dict[str, Any]:
    """Get RF spectrum scan state and results.

    Spectrum data is per access point: the route is
    ``stat/spectrum-scan/{ap_mac}``. The previous site-wide
    ``stat/spectrumscan`` path does not exist and 404'd on every call.
    Without ``ap_mac``, every AP on the site is queried.

    An AP that has never run an RF scan reports empty ``spectrum_table``
    lists — run a scan from the controller first if results are expected.

    Args:
        site_id: Site identifier
        settings: Application settings
        ap_mac: Optional single AP to query

    Returns:
        Dictionary with per-AP scan state and radio tables
    """
    site_id = validate_site_id(site_id)
    if ap_mac is not None:
        # Fail fast with a clear ValidationError rather than interpolating a
        # malformed value into the request path.
        ap_mac = validate_mac_address(ap_mac)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        aps: list[dict[str, Any]] = []
        for mac in await _spectrum_scan_targets(client, site_id, ap_mac):
            response = await client.get(f"/ea/sites/{site_id}/stat/spectrum-scan/{mac}")
            data = response.get("data", []) if isinstance(response, dict) else response
            for entry in data if isinstance(data, list) else []:
                if isinstance(entry, dict):
                    aps.append(entry)

        logger.info(
            sanitize_log_message(f"Retrieved spectrum state for {len(aps)} APs in '{site_id}'")
        )
        return {"site_id": site_id, "aps": aps}


async def list_spectrum_interference(
    site_id: str, settings: Settings, ap_mac: str | None = None
) -> list[dict[str, Any]]:
    """List spectrum interference entries from RF scans.

    Flattens each AP radio's ``spectrum_table`` (see
    :func:`get_spectrum_scan` for the route story). Entries are passed
    through as the controller reports them, annotated with the AP MAC and
    radio; an empty list usually means no RF scan has been run.

    Args:
        site_id: Site identifier
        settings: Application settings
        ap_mac: Optional single AP to query

    Returns:
        List of interference entries across all queried APs
    """
    scan = await get_spectrum_scan(site_id, settings, ap_mac=ap_mac)

    logger = get_logger(__name__, settings.log_level)
    entries: list[dict[str, Any]] = []
    for ap in scan.get("aps", []):
        for radio_scan in ap.get("scans", []) or []:
            if not isinstance(radio_scan, dict):
                continue
            for row in radio_scan.get("spectrum_table", []) or []:
                if isinstance(row, dict):
                    # Annotations come last so a controller-provided key of
                    # the same name can never overwrite them.
                    entries.append(
                        {
                            **row,
                            "ap_mac": ap.get("mac"),
                            "radio": radio_scan.get("radio"),
                            "radio_name": radio_scan.get("name"),
                        }
                    )

    logger.info(
        sanitize_log_message(f"Retrieved {len(entries)} interference entries for '{site_id}'")
    )
    return entries
