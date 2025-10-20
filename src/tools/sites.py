"""Site management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models import Site
from ..utils import ResourceNotFoundError, get_logger, validate_limit_offset, validate_site_id


async def get_site_details(site_id: str, settings: Settings) -> dict[str, Any]:
    """Get detailed site information.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Site details dictionary

    Raises:
        ResourceNotFoundError: If site not found
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get("/ea/sites")
        sites_data = response.get("data", [])

        for site_data in sites_data:
            if site_data.get("_id") == site_id or site_data.get("name") == site_id:
                site = Site(**site_data)
                logger.info(f"Retrieved site details for {site_id}")
                return site.model_dump()

        raise ResourceNotFoundError("site", site_id)


async def list_sites(
    settings: Settings, limit: int | None = None, offset: int | None = None
) -> list[dict[str, Any]]:
    """List all accessible sites.

    Args:
        settings: Application settings
        limit: Maximum number of sites to return
        offset: Number of sites to skip

    Returns:
        List of site dictionaries
    """
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get("/ea/sites")
        sites_data = response.get("data", [])

        # Apply pagination
        paginated = sites_data[offset : offset + limit]

        # Parse into Site models
        sites = [Site(**s).model_dump() for s in paginated]

        logger.info(f"Retrieved {len(sites)} sites (offset={offset}, limit={limit})")
        return sites


async def get_site_statistics(site_id: str, settings: Settings) -> dict[str, Any]:
    """Retrieve site-wide statistics.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Site statistics dictionary
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # Gather statistics from multiple endpoints
        devices_response = await client.get(f"/ea/sites/{site_id}/devices")
        clients_response = await client.get(f"/ea/sites/{site_id}/sta")
        networks_response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")

        devices_data = devices_response.get("data", [])
        clients_data = clients_response.get("data", [])
        networks_data = networks_response.get("data", [])

        # Count device types
        ap_count = sum(1 for d in devices_data if d.get("type") == "uap")
        switch_count = sum(1 for d in devices_data if d.get("type") == "usw")
        gateway_count = sum(1 for d in devices_data if d.get("type") in ["ugw", "udm", "uxg"])

        # Count online/offline devices
        online_devices = sum(1 for d in devices_data if d.get("state") == 1)
        offline_devices = len(devices_data) - online_devices

        # Count wired vs wireless clients
        wired_clients = sum(1 for c in clients_data if c.get("is_wired") is True)
        wireless_clients = len(clients_data) - wired_clients

        # Calculate total bandwidth
        total_tx = sum(c.get("tx_bytes", 0) for c in clients_data)
        total_rx = sum(c.get("rx_bytes", 0) for c in clients_data)

        statistics = {
            "site_id": site_id,
            "devices": {
                "total": len(devices_data),
                "online": online_devices,
                "offline": offline_devices,
                "access_points": ap_count,
                "switches": switch_count,
                "gateways": gateway_count,
            },
            "clients": {
                "total": len(clients_data),
                "wired": wired_clients,
                "wireless": wireless_clients,
            },
            "networks": {
                "total": len(networks_data),
            },
            "bandwidth": {
                "total_tx_bytes": total_tx,
                "total_rx_bytes": total_rx,
                "total_bytes": total_tx + total_rx,
            },
        }

        logger.info(f"Retrieved statistics for site '{site_id}'")
        return statistics
