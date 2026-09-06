"""Network diagnostics MCP tools."""

import time
from datetime import datetime, timezone
from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models.diagnostics import NetworkReference, SpeedTestResult
from ..utils import (
    APIError,
    ValidationError,
    coerce_bool,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_confirmation,
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


async def run_speed_test(
    site_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Initiate a WAN speed test on the site.

    Args:
        site_id: Site identifier
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        Dictionary with speed test initiation status
    """
    validate_confirmation(confirm, "start a speed test", dry_run)
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    if coerce_bool(dry_run):
        return {"dry_run": True, "operation": "run_speed_test", "site_id": site_id}

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

    The state lives on the gateway's ``stat/device`` record: a
    ``speedtest-status`` object carries the last result
    (``xput_download``/``xput_upload`` in Mbps, ``latency`` in ms,
    ``rundate`` in epoch seconds, per-phase ``status_*`` codes), the
    ``uplink`` object carries the outcome string, and
    ``speedtest-pending-interfaces`` is non-empty while a test runs —
    verified live on Network 10.5.67. The
    ``cmd/devmgr/speedtest-status`` resource this tool previously GETed
    does not exist on any controller, so every call 404'd.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Dictionary with speed test status and results; fields the gateway
        does not report are omitted
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # stat/device is the record that carries speedtest-status --
        # matching the docstring and the route verified live.
        response = await client.get(f"/ea/sites/{site_id}/stat/device")
        devices = response.get("data", []) if isinstance(response, dict) else response

        gateway = None
        for device in devices if isinstance(devices, list) else []:
            if not isinstance(device, dict):
                continue
            # Gateways report type "ugw"/"udm"/"uxg" -- the same set sites.py
            # counts. "usg" is a model-string token (helpers.py), never a
            # device type, so it matched nothing while a real USG went unfound
            # whenever it had no speedtest-status key to fall back on.
            if "speedtest-status" in device or device.get("type") in ("ugw", "udm", "uxg"):
                gateway = device
                break
        if gateway is None:
            raise APIError(
                "No gateway device on this site reports speed test state; "
                "speed tests run on the gateway."
            )

        status_obj = gateway.get("speedtest-status")
        if not isinstance(status_obj, dict) or not status_obj:
            logger.info(sanitize_log_message(f"No speed test recorded yet for site '{site_id}'"))
            return {
                "status": "no_result",
                "message": "The gateway has not recorded a speed test yet. "
                "Start one with run_speed_test.",
            }

        uplink = gateway.get("uplink") or {}
        running = bool(gateway.get("speedtest-pending-interfaces"))
        rundate = status_obj.get("rundate")
        server = status_obj.get("server") or {}

        speed_test = SpeedTestResult(
            status="running" if running else (uplink.get("speedtest_status") or "unknown"),
            download_speed_mbps=status_obj.get("xput_download"),
            upload_speed_mbps=status_obj.get("xput_upload"),
            ping_ms=status_obj.get("latency"),
            timestamp=(
                datetime.fromtimestamp(rundate, tz=timezone.utc).isoformat()
                if isinstance(rundate, int | float)
                else None
            ),
            server_name=server.get("provider"),
        )
        logger.info(sanitize_log_message(f"Retrieved speed test status for site '{site_id}'"))
        return speed_test.model_dump(exclude_none=True)


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


# Report archive intervals and subjects the controller maintains. Attrs
# differ by subject; "time" is always required for a usable series.
REPORT_INTERVALS = ("5minutes", "hourly", "daily", "monthly")
REPORT_SUBJECTS = ("site", "ap", "user", "gw")

_DEFAULT_REPORT_ATTRS: dict[str, list[str]] = {
    "site": [
        "time",
        "bytes",
        "wlan_bytes",
        "num_sta",
        "wlan-num_sta",
        "wan-tx_bytes",
        "wan-rx_bytes",
    ],
    # Airtime attrs are band-prefixed in the archives ("ng-"/"na-"); the
    # bare "cu_total" family exists in live stat/device blobs but comes
    # back empty from stat/report (verified live on Network 10.5).
    "ap": [
        "time",
        "bytes",
        "num_sta",
        "ng-cu_total",
        "ng-cu_self_rx",
        "ng-cu_self_tx",
        "na-cu_total",
        "na-cu_self_rx",
        "na-cu_self_tx",
    ],
    "user": ["time", "rx_bytes", "tx_bytes", "signal"],
    # Gateway latency is not archived on stat/report (verified live on
    # Network 10.5) — read it from live monitoring surfaces instead.
    "gw": ["time", "mem", "cpu", "wan-rx_bytes", "wan-tx_bytes"],
}


async def get_historical_stats(
    site_id: str,
    settings: Settings,
    subject: str = "ap",
    interval: str = "hourly",
    hours: int = 24,
    macs: list[str] | str | None = None,
    attrs: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Read archived time-series statistics from the controller.

    The controller keeps rollup archives on
    ``stat/report/{interval}.{subject}`` — the only place historical
    airtime, per-client signal, and gateway latency live. Instantaneous
    tools answer "now"; this answers "since when" and "how often".

    Args:
        site_id: Site identifier
        settings: Application settings
        subject: What the series describes — "site", "ap" (per-AP
            airtime/clients), "user" (per-client traffic/signal), or
            "gw" (gateway cpu/mem/WAN latency)
        interval: Rollup granularity — "5minutes", "hourly", "daily",
            or "monthly" (5-minute archives are retained briefly;
            hourly/daily reach back much further)
        hours: Window ending now (default 24)
        macs: Optional MAC or list of MACs to filter to specific
            devices/clients (required in practice for "user" series)
        attrs: Report attributes to request; defaults per subject.
            "time" is always included

    Returns:
        List of samples, oldest first, each carrying epoch-ms ``time``
    """
    site_id = validate_site_id(site_id)
    if interval not in REPORT_INTERVALS:
        raise ValidationError(f"interval must be one of {REPORT_INTERVALS}, got '{interval}'")
    if subject not in REPORT_SUBJECTS:
        raise ValidationError(f"subject must be one of {REPORT_SUBJECTS}, got '{subject}'")
    if not 1 <= hours <= 2160:
        raise ValidationError(f"hours must be between 1 and 2160, got {hours}")
    if isinstance(macs, str):
        macs = [macs]
    if macs is not None:
        macs = [validate_mac_address(m) for m in macs]
    logger = get_logger(__name__, settings.log_level)

    requested = list(attrs) if attrs else list(_DEFAULT_REPORT_ATTRS[subject])
    if "time" not in requested:
        requested.insert(0, "time")

    now_ms = int(time.time() * 1000)
    body: dict[str, Any] = {
        "attrs": requested,
        "start": now_ms - hours * 3600 * 1000,
        "end": now_ms,
    }
    if macs:
        body["macs"] = macs

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.post(
            f"/ea/sites/{site_id}/stat/report/{interval}.{subject}",
            json_data=body,
        )
        data = response.get("data", []) if isinstance(response, dict) else response
        samples = [s for s in (data if isinstance(data, list) else []) if isinstance(s, dict)]
        samples.sort(key=lambda s: s.get("time") or 0)

        logger.info(
            sanitize_log_message(
                f"Retrieved {len(samples)} {interval}.{subject} samples for '{site_id}' "
                f"(last {hours}h)"
            )
        )
        return samples


async def start_spectrum_scan(
    site_id: str,
    settings: Settings,
    ap_mac: str = "",
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Start an RF spectrum scan on an access point.

    DISRUPTIVE: the AP takes its radios offline for the duration of the
    scan (typically 5-10 minutes) and every client on it is dropped —
    they must roam elsewhere or wait. Run during a quiet window. Read
    results with :func:`get_spectrum_scan` /
    :func:`list_spectrum_interference`; the scan state reports
    ``spectrum_scanning`` true until the scan completes.

    Args:
        site_id: Site identifier
        settings: Application settings
        ap_mac: MAC address of the AP to scan
        confirm: Confirmation flag (required — clients will drop)
        dry_run: If True, preview without starting the scan

    Returns:
        Dictionary with the scan request status
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "spectrum scan", dry_run)
    dry_run = coerce_bool(dry_run)
    ap_mac = validate_mac_address(ap_mac)
    logger = get_logger(__name__, settings.log_level)

    if dry_run:
        return {"dry_run": True, "would_scan": ap_mac, "warning": "clients on this AP will drop"}

    async with UniFiClient(settings) as client:
        await client.authenticate()

        await client.post(
            f"/ea/sites/{site_id}/cmd/devmgr",
            json_data={"cmd": "spectrum-scan", "mac": ap_mac},
        )
        log_audit(
            operation="start_spectrum_scan",
            parameters={"site_id": site_id, "ap_mac": ap_mac},
            result="success",
            site_id=site_id,
        )
        logger.info(sanitize_log_message(f"Spectrum scan started on {ap_mac}"))
        return {"success": True, "ap_mac": ap_mac, "status": "scan started"}
