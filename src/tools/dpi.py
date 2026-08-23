"""Deep Packet Inspection (DPI) statistics MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import (
    coerce_bool,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_confirmation,
    validate_limit_offset,
    validate_mac_address,
    validate_site_id,
)


async def get_dpi_statistics(
    site_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get site-wide Deep Packet Inspection statistics.

    Reads the ``stat/sitedpi`` report (``by_app`` and ``by_cat``), the
    route that actually carries site DPI counters. The previous
    ``stat/dpi`` path answers with nothing on current controllers, so the
    tool always reported zero applications. The old ``time_range``
    parameter is gone: the counters are lifetime totals, and no variant of
    this endpoint accepts a window — the parameter changed nothing.

    On current releases traffic identification is exposed through the
    traffic-flow engine; a controller whose classic DPI counters are off
    reports empty lists here, and the ``note`` field says where to look
    instead.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        DPI statistics dictionary with per-application and per-category
        byte counters (``app``/``cat`` are numeric DPI catalog ids —
        translate with list_dpi_applications / list_dpi_categories)
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        async def section(kind: str) -> list[dict[str, Any]]:
            response = await client.post(
                f"/ea/sites/{site_id}/stat/sitedpi", json_data={"type": kind}
            )
            data = response if isinstance(response, list) else response.get("data", [])
            first = data[0] if isinstance(data, list) and data else {}
            rows = first.get(kind, []) if isinstance(first, dict) else []
            return [row for row in rows if isinstance(row, dict)]

        def totalled(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            out = []
            for row in rows:
                tx = row.get("tx_bytes", 0) or 0
                rx = row.get("rx_bytes", 0) or 0
                out.append({**row, "total_bytes": tx + rx})
            out.sort(key=lambda r: r["total_bytes"], reverse=True)
            return out

        applications = totalled(await section("by_app"))
        categories = totalled(await section("by_cat"))

        result: dict[str, Any] = {
            "site_id": site_id,
            "applications": applications,
            "categories": categories,
            "total_applications": len(applications),
            "total_categories": len(categories),
        }
        if not applications and not categories:
            result["note"] = (
                "This controller reports no site DPI counters. Current "
                "releases expose traffic identification through the "
                "traffic-flow tools instead (get_top_flows, "
                "get_flow_analytics)."
            )

        logger.info(sanitize_log_message(f"Retrieved DPI statistics for site '{site_id}'"))
        return result


async def list_top_applications(
    site_id: str,
    settings: Settings,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """List top applications by bandwidth usage.

    See :func:`get_dpi_statistics` for the data source and for why the
    old ``time_range`` parameter is gone.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Number of top applications to return

    Returns:
        List of top application dictionaries sorted by bandwidth
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    dpi_stats = await get_dpi_statistics(site_id, settings)

    top_apps: list[dict[str, Any]] = dpi_stats["applications"][:limit]

    logger.info(
        sanitize_log_message(f"Retrieved top {len(top_apps)} applications for site '{site_id}'")
    )

    return top_apps


async def get_client_dpi(
    site_id: str,
    client_mac: str,
    settings: Settings,
    time_range: str = "24h",
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Get DPI statistics for a specific client.

    Args:
        site_id: Site identifier
        client_mac: Client MAC address
        settings: Application settings
        time_range: Time range for statistics (1h, 6h, 12h, 24h, 7d, 30d)
        limit: Maximum number of applications to return
        offset: Number of applications to skip

    Returns:
        Client DPI statistics dictionary
    """
    site_id = validate_site_id(site_id)
    client_mac = validate_mac_address(client_mac)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    # Validate time range
    valid_ranges = ["1h", "6h", "12h", "24h", "7d", "30d"]
    if time_range not in valid_ranges:
        raise ValueError(f"Invalid time range '{time_range}'. Must be one of: {valid_ranges}")

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # Get client-specific DPI data
        response = await client.get(f"/ea/sites/{site_id}/stat/stadpi/{client_mac}")
        # Handle both list and dict responses
        dpi_data = response if isinstance(response, list) else response.get("data", [])

        # Aggregate by application
        app_stats = {}
        total_tx = 0
        total_rx = 0

        for entry in dpi_data:
            app = entry.get("app")
            cat = entry.get("cat")
            tx_bytes = entry.get("tx_bytes", 0)
            rx_bytes = entry.get("rx_bytes", 0)
            total_bytes = tx_bytes + rx_bytes

            total_tx += tx_bytes
            total_rx += rx_bytes

            if app:
                if app not in app_stats:
                    app_stats[app] = {
                        "application": app,
                        "category": cat,
                        "tx_bytes": 0,
                        "rx_bytes": 0,
                        "total_bytes": 0,
                    }
                app_stats[app]["tx_bytes"] += tx_bytes
                app_stats[app]["rx_bytes"] += rx_bytes
                app_stats[app]["total_bytes"] += total_bytes

        # Convert to list and sort by total bytes
        applications = sorted(app_stats.values(), key=lambda x: x["total_bytes"], reverse=True)

        # Apply pagination
        paginated_apps = applications[offset : offset + limit]

        # Calculate percentages
        total_bytes = total_tx + total_rx
        for app in paginated_apps:
            if total_bytes > 0:
                app["percentage"] = (app["total_bytes"] / total_bytes) * 100
            else:
                app["percentage"] = 0

        logger.info(
            sanitize_log_message(
                f"Retrieved DPI statistics for client '{client_mac}' in site '{site_id}' "
                f"(time range: {time_range})"
            )
        )

        return {
            "site_id": site_id,
            "client_mac": client_mac,
            "time_range": time_range,
            "total_tx_bytes": total_tx,
            "total_rx_bytes": total_rx,
            "total_bytes": total_bytes,
            "applications": paginated_apps,
            "total_applications": len(applications),
        }


async def update_dpi_settings(
    site_id: str,
    settings: Settings,
    enabled: bool = True,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Enable or disable DPI (traffic identification) on a site.

    DPI is the passive per-flow application classifier behind the DPI
    statistics tools; without it those counters stay empty. Read-modify-
    write of the ``dpi`` settings section (``get/setting/dpi`` then
    ``set/setting/dpi/{_id}``), preserving every other key the section
    carries, with the stored state re-read and verified.

    Args:
        site_id: Site identifier
        settings: Application settings
        enabled: Desired DPI state
        confirm: Confirmation flag (required)
        dry_run: If True, preview the write without sending it

    Returns:
        Dictionary with the verified stored state
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "DPI settings change", dry_run)
    dry_run = coerce_bool(dry_run)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/get/setting/dpi")
        data = response.get("data", []) if isinstance(response, dict) else response
        section = (
            next((s for s in data if isinstance(s, dict)), {}) if isinstance(data, list) else {}
        )
        settings_id = section.get("_id")

        payload = {k: v for k, v in section.items() if not k.startswith("_")}
        payload["enabled"] = enabled
        # Per-client application tracking is what makes the statistics
        # useful; keep it in lockstep unless the section already sets it.
        payload.setdefault("fingerprintingEnabled", enabled)

        if dry_run:
            return {
                "dry_run": True,
                "current_enabled": section.get("enabled"),
                "would_set": payload,
            }

        endpoint = f"/ea/sites/{site_id}/set/setting/dpi"
        if settings_id:
            endpoint += f"/{settings_id}"
        await client.post(endpoint, json_data=payload)

        verify = await client.get(f"/ea/sites/{site_id}/get/setting/dpi")
        vdata = verify.get("data", []) if isinstance(verify, dict) else verify
        stored = (
            next((s for s in vdata if isinstance(s, dict)), {}) if isinstance(vdata, list) else {}
        )

        # Require the key to be present, rather than coercing with bool().
        # A controller that drops `enabled` entirely returns None, and
        # bool(None) is False -- so a disable request would have been
        # reported as a confirmed success while the stored state was in
        # fact unknown. Absent is not the same as false.
        confirmed = "enabled" in stored and bool(stored["enabled"]) == enabled

        log_audit(
            operation="update_dpi_settings",
            parameters={"site_id": site_id, "enabled": enabled},
            result="success" if confirmed else "unconfirmed",
            site_id=site_id,
        )
        result: dict[str, Any] = {
            "success": confirmed,
            "enabled": stored.get("enabled"),
            "fingerprintingEnabled": stored.get("fingerprintingEnabled"),
        }
        if not confirmed:
            result["warning"] = (
                "Controller did not report the requested DPI state"
                if "enabled" in stored
                else "Controller did not echo an 'enabled' value; state unconfirmed"
            )
            logger.warning(sanitize_log_message(result["warning"]))
        return result
