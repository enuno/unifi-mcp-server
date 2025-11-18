"""Site Manager API tools for multi-site management."""

from typing import Any

from ..api.site_manager_client import SiteManagerClient
from ..config import Settings
from ..models.site_manager import (
    CrossSiteStatistics,
    InternetHealthMetrics,
    SiteHealthSummary,
    VantagePoint,
)
from ..utils import get_logger

logger = get_logger(__name__)


async def list_all_sites_aggregated(settings: Settings) -> list[dict[str, Any]]:
    """List all sites with aggregated stats from Site Manager API.

    Args:
        settings: Application settings

    Returns:
        List of sites with aggregated statistics
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    async with SiteManagerClient(settings) as client:
        logger.info("Retrieving aggregated site list from Site Manager API")

        response = await client.list_sites()
        sites_data = response.get("data", response.get("sites", []))

        # Enhance with aggregated stats if available
        sites: list[dict[str, Any]] = []
        for site in sites_data:
            sites.append(site)

        return sites


async def get_internet_health(settings: Settings, site_id: str | None = None) -> dict[str, Any]:
    """Get internet health metrics across sites.

    Args:
        settings: Application settings
        site_id: Optional site identifier. If None, returns aggregate metrics.

    Returns:
        Internet health metrics
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    async with SiteManagerClient(settings) as client:
        logger.info(f"Retrieving internet health metrics (site_id={site_id})")

        response = await client.get_internet_health(site_id)
        data = response.get("data", response)

        return InternetHealthMetrics(**data).model_dump()  # type: ignore[no-any-return]


async def get_site_health_summary(
    settings: Settings, site_id: str | None = None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Get health summary for all sites or a specific site.

    Args:
        settings: Application settings
        site_id: Optional site identifier. If None, returns summary for all sites.

    Returns:
        Health summary
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    async with SiteManagerClient(settings) as client:
        logger.info(f"Retrieving site health summary (site_id={site_id})")

        response = await client.get_site_health(site_id)
        data = response.get("data", response)

        if site_id:
            return SiteHealthSummary(**data).model_dump()  # type: ignore[no-any-return]
        else:
            # Multiple sites
            summaries = data.get("sites", []) if isinstance(data, dict) else data
            return [SiteHealthSummary(**summary).model_dump() for summary in summaries]


async def get_cross_site_statistics(settings: Settings) -> dict[str, Any]:
    """Get aggregate statistics across multiple sites.

    Args:
        settings: Application settings

    Returns:
        Cross-site statistics
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    async with SiteManagerClient(settings) as client:
        logger.info("Retrieving cross-site statistics")

        # Get all sites with health
        sites_response = await client.list_sites()
        sites_data = sites_response.get("data", sites_response.get("sites", []))

        health_response = await client.get_site_health()
        health_data = health_response.get("data", health_response)

        # Aggregate statistics
        total_sites = len(sites_data)
        sites_healthy = 0
        sites_degraded = 0
        sites_down = 0
        total_devices = 0
        devices_online = 0
        total_clients = 0
        total_bandwidth_up_mbps = 0.0
        total_bandwidth_down_mbps = 0.0

        site_summaries: list[SiteHealthSummary] = []
        if isinstance(health_data, list):
            for health in health_data:
                status = health.get("status", "unknown")
                if status == "healthy":
                    sites_healthy += 1
                elif status == "degraded":
                    sites_degraded += 1
                elif status == "down":
                    sites_down += 1

                site_summaries.append(SiteHealthSummary(**health))
                total_devices += health.get("devices_total", 0)
                devices_online += health.get("devices_online", 0)
                total_clients += health.get("clients_active", 0)

        return CrossSiteStatistics(  # type: ignore[no-any-return]
            total_sites=total_sites,
            sites_healthy=sites_healthy,
            sites_degraded=sites_degraded,
            sites_down=sites_down,
            total_devices=total_devices,
            devices_online=devices_online,
            total_clients=total_clients,
            total_bandwidth_up_mbps=total_bandwidth_up_mbps,
            total_bandwidth_down_mbps=total_bandwidth_down_mbps,
            site_summaries=site_summaries,
        ).model_dump()


async def list_vantage_points(settings: Settings) -> list[dict[str, Any]]:
    """List all Vantage Points.

    Args:
        settings: Application settings

    Returns:
        List of Vantage Points
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    async with SiteManagerClient(settings) as client:
        logger.info("Retrieving Vantage Points")

        response = await client.list_vantage_points()
        data = response.get("data", response.get("vantage_points", []))

        return [VantagePoint(**vp).model_dump() for vp in data]
