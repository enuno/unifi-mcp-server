"""Deep Packet Inspection (DPI) statistics MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import get_logger, validate_limit_offset, validate_mac_address, validate_site_id


async def get_dpi_statistics(
    site_id: str,
    settings: Settings,
    time_range: str = "24h",
) -> dict[str, Any]:
    """Get Deep Packet Inspection statistics.

    Args:
        site_id: Site identifier
        settings: Application settings
        time_range: Time range for statistics (1h, 6h, 12h, 24h, 7d, 30d)

    Returns:
        DPI statistics dictionary
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    # Validate time range
    valid_ranges = ["1h", "6h", "12h", "24h", "7d", "30d"]
    if time_range not in valid_ranges:
        raise ValueError(f"Invalid time range '{time_range}'. Must be one of: {valid_ranges}")

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # Get DPI statistics
        response = await client.get(f"/ea/sites/{site_id}/stat/dpi")
        dpi_data = response.get("data", [])

        # Aggregate by application/category
        app_stats = {}
        category_stats = {}

        for entry in dpi_data:
            app = entry.get("app")
            cat = entry.get("cat")
            tx_bytes = entry.get("tx_bytes", 0)
            rx_bytes = entry.get("rx_bytes", 0)
            total_bytes = tx_bytes + rx_bytes

            # Aggregate by application
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

            # Aggregate by category
            if cat:
                if cat not in category_stats:
                    category_stats[cat] = {
                        "category": cat,
                        "tx_bytes": 0,
                        "rx_bytes": 0,
                        "total_bytes": 0,
                        "application_count": 0,
                    }
                category_stats[cat]["tx_bytes"] += tx_bytes
                category_stats[cat]["rx_bytes"] += rx_bytes
                category_stats[cat]["total_bytes"] += total_bytes
                if app:
                    category_stats[cat]["application_count"] += 1

        # Convert to lists and sort by total bytes
        applications = sorted(app_stats.values(), key=lambda x: x["total_bytes"], reverse=True)
        categories = sorted(category_stats.values(), key=lambda x: x["total_bytes"], reverse=True)

        logger.info(f"Retrieved DPI statistics for site '{site_id}' " f"(time range: {time_range})")

        return {
            "site_id": site_id,
            "time_range": time_range,
            "applications": applications,
            "categories": categories,
            "total_applications": len(applications),
            "total_categories": len(categories),
        }


async def list_top_applications(
    site_id: str,
    settings: Settings,
    limit: int = 10,
    time_range: str = "24h",
) -> list[dict[str, Any]]:
    """List top applications by bandwidth usage.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Number of top applications to return
        time_range: Time range for statistics (1h, 6h, 12h, 24h, 7d, 30d)

    Returns:
        List of top application dictionaries sorted by bandwidth
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    # Get full DPI statistics
    dpi_stats = await get_dpi_statistics(site_id, settings, time_range)

    # Get top N applications
    top_apps: list[dict[str, Any]] = dpi_stats["applications"][:limit]

    logger.info(
        f"Retrieved top {len(top_apps)} applications for site '{site_id}' "
        f"(time range: {time_range})"
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
        dpi_data = response.get("data", [])

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
            f"Retrieved DPI statistics for client '{client_mac}' in site '{site_id}' "
            f"(time range: {time_range})"
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
