"""Site Manager API tools for multi-site management."""

from functools import wraps
from typing import Any

from ..api.site_manager_client import SiteManagerClient
from ..config import Settings
from ..models.site_manager import (
    CrossSitePerformanceComparison,
    CrossSiteSearchResult,
    CrossSiteStatistics,
    Host,
    InternetHealthMetrics,
    ISPMetrics,
    SDWANConfig,
    SDWANConfigStatus,
    SiteHealthSummary,
    SiteInventory,
    SitePerformanceMetrics,
    VantagePoint,
    VersionControl,
)
from ..utils import get_logger, sanitize_log_message

logger = get_logger(__name__)


def require_site_manager(func):
    """Decorator to ensure Site Manager API is enabled before calling function.

    Args:
        func: The async function to wrap

    Returns:
        Wrapped function that checks settings.site_manager_enabled

    Raises:
        ValueError: If Site Manager API is not enabled
    """

    @wraps(func)
    async def wrapper(settings: Settings, *args, **kwargs):
        if not settings.site_manager_enabled:
            raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")
        return await func(settings, *args, **kwargs)

    return wrapper


@require_site_manager
async def list_all_sites_aggregated(settings: Settings) -> list[dict[str, Any]]:
    """List all sites with aggregated stats from Site Manager API.

    Args:
        settings: Application settings

    Returns:
        List of sites with aggregated statistics
    """

    async with SiteManagerClient(settings) as client:
        logger.info("Retrieving aggregated site list from Site Manager API")

        response = await client.list_sites()
        sites_data = response.get("data", response.get("sites", []))

        # Enhance with aggregated stats if available
        sites: list[dict[str, Any]] = []
        for site in sites_data:
            sites.append(site)

        return sites


@require_site_manager
async def get_internet_health(settings: Settings, site_id: str | None = None) -> dict[str, Any]:
    """Get internet health metrics across sites.

    Args:
        settings: Application settings
        site_id: Optional site identifier. If None, returns aggregate metrics.

    Returns:
        Internet health metrics
    """

    async with SiteManagerClient(settings) as client:
        logger.info(sanitize_log_message(f"Retrieving internet health metrics (site_id={site_id})"))

        response = await client.get_internet_health(site_id)
        data = response.get("data", response)

        return InternetHealthMetrics(**data).model_dump()  # type: ignore[no-any-return]


@require_site_manager
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

    async with SiteManagerClient(settings) as client:
        logger.info(sanitize_log_message(f"Retrieving site health summary (site_id={site_id})"))

        response = await client.get_site_health(site_id)
        # Client now auto-unwraps the "data" field, so response is the actual data
        data = response

        if site_id:
            return SiteHealthSummary(**data).model_dump()  # type: ignore[no-any-return]
        else:
            # Multiple sites - response is already a list or dict with sites
            summaries = data.get("sites", []) if isinstance(data, dict) else data
            return [SiteHealthSummary(**summary).model_dump() for summary in summaries]


@require_site_manager
async def get_cross_site_statistics(settings: Settings) -> dict[str, Any]:
    """Get aggregate statistics across multiple sites.

    Args:
        settings: Application settings

    Returns:
        Cross-site statistics
    """

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


@require_site_manager
async def list_vantage_points(settings: Settings) -> list[dict[str, Any]]:
    """List all Vantage Points.

    Args:
        settings: Application settings

    Returns:
        List of Vantage Points
    """

    async with SiteManagerClient(settings) as client:
        logger.info("Retrieving Vantage Points")

        response = await client.list_vantage_points()
        # Client now auto-unwraps the "data" field, so response is the actual data
        data = response.get("vantage_points", []) if isinstance(response, dict) else response

        return [VantagePoint(**vp).model_dump() for vp in data]


@require_site_manager
async def get_site_inventory(
    settings: Settings, site_id: str | None = None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Get comprehensive inventory for a site or all sites.

    Provides detailed breakdown of resources including devices, clients,
    networks, SSIDs, VPN tunnels, and firewall rules.

    Args:
        settings: Application settings
        site_id: Optional site identifier. If None, returns inventory for all sites.

    Returns:
        Site inventory or list of site inventories
    """

    async with SiteManagerClient(settings) as client:
        logger.info(sanitize_log_message(f"Retrieving site inventory (site_id={site_id})"))

        if site_id:
            # Get inventory for specific site
            site_response = await client.get(f"sites/{site_id}")
            site_data = site_response.get("data", site_response)

            # Fetch detailed counts (these would come from various endpoints)
            # For now, using available data from site response
            inventory = SiteInventory(
                site_id=site_id,
                site_name=site_data.get("name", site_id),
                device_count=site_data.get("device_count", 0),
                device_types=site_data.get("device_types", {}),
                client_count=site_data.get("client_count", 0),
                network_count=site_data.get("network_count", 0),
                ssid_count=site_data.get("ssid_count", 0),
                uplink_count=site_data.get("uplink_count", 0),
                vpn_tunnel_count=site_data.get("vpn_tunnel_count", 0),
                firewall_rule_count=site_data.get("firewall_rule_count", 0),
                last_updated=site_data.get("last_updated", ""),
            )
            return inventory.model_dump()  # type: ignore[no-any-return]
        else:
            # Get inventory for all sites
            sites_response = await client.list_sites()
            sites_data = sites_response.get("data", sites_response.get("sites", []))

            inventories = []
            for site in sites_data:
                inventory = SiteInventory(
                    site_id=site.get("site_id", ""),
                    site_name=site.get("name", ""),
                    device_count=site.get("device_count", 0),
                    device_types=site.get("device_types", {}),
                    client_count=site.get("client_count", 0),
                    network_count=site.get("network_count", 0),
                    ssid_count=site.get("ssid_count", 0),
                    uplink_count=site.get("uplink_count", 0),
                    vpn_tunnel_count=site.get("vpn_tunnel_count", 0),
                    firewall_rule_count=site.get("firewall_rule_count", 0),
                    last_updated=site.get("last_updated", ""),
                )
                inventories.append(inventory.model_dump())

            return inventories


@require_site_manager
async def compare_site_performance(settings: Settings) -> dict[str, Any]:
    """Compare performance metrics across all sites.

    Analyzes uptime, latency, bandwidth, and health status to identify
    best and worst performing sites.

    Args:
        settings: Application settings

    Returns:
        Performance comparison with rankings and metrics
    """

    async with SiteManagerClient(settings) as client:
        logger.info("Comparing performance across sites")

        # Get site health data
        health_response = await client.get_site_health()
        health_data = health_response.get("data", health_response)

        # Get internet health data for bandwidth/latency
        internet_response = await client.get_internet_health()
        internet_data = internet_response.get("data", internet_response)

        site_metrics: list[SitePerformanceMetrics] = []

        # Process health data
        if isinstance(health_data, list):
            for health in health_data:
                site_id = health.get("site_id", "")

                # Calculate device online percentage
                devices_total = health.get("devices_total", 0)
                devices_online = health.get("devices_online", 0)
                device_online_pct = (
                    (devices_online / devices_total * 100) if devices_total > 0 else 0.0
                )

                # Find matching internet health data
                internet_health = None
                if isinstance(internet_data, list):
                    internet_health = next(
                        (i for i in internet_data if i.get("site_id") == site_id), None
                    )
                elif isinstance(internet_data, dict) and internet_data.get("site_id") == site_id:
                    internet_health = internet_data

                metrics = SitePerformanceMetrics(
                    site_id=site_id,
                    site_name=health.get("site_name", site_id),
                    avg_latency_ms=internet_health.get("latency_ms") if internet_health else None,
                    avg_bandwidth_up_mbps=(
                        internet_health.get("bandwidth_up_mbps") if internet_health else None
                    ),
                    avg_bandwidth_down_mbps=(
                        internet_health.get("bandwidth_down_mbps") if internet_health else None
                    ),
                    uptime_percentage=health.get("uptime_percentage", 0.0),
                    device_online_percentage=device_online_pct,
                    client_count=health.get("clients_active", 0),
                    health_status=health.get("status", "down"),
                )
                site_metrics.append(metrics)

        # Calculate best and worst performers
        # Best = highest uptime and device online percentage
        best_site = None
        worst_site = None

        if site_metrics:
            # Sort by uptime (primary) and device online percentage (secondary)
            sorted_sites = sorted(
                site_metrics,
                key=lambda s: (s.uptime_percentage, s.device_online_percentage),
                reverse=True,
            )
            best_site = sorted_sites[0] if sorted_sites else None
            worst_site = sorted_sites[-1] if sorted_sites else None

        # Calculate average uptime
        avg_uptime = (
            sum(m.uptime_percentage for m in site_metrics) / len(site_metrics)
            if site_metrics
            else 0.0
        )

        # Calculate average latency (excluding None values)
        latencies = [m.avg_latency_ms for m in site_metrics if m.avg_latency_ms is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else None

        comparison = CrossSitePerformanceComparison(
            total_sites=len(site_metrics),
            best_performing_site=best_site,
            worst_performing_site=worst_site,
            average_uptime=avg_uptime,
            average_latency_ms=avg_latency,
            site_metrics=site_metrics,
        )

        return comparison.model_dump()  # type: ignore[no-any-return]


@require_site_manager
async def search_across_sites(
    settings: Settings,
    query: str,
    search_type: str = "all",
) -> dict[str, Any]:
    """Search for resources across all sites.

    Search for devices, clients, or networks across all managed sites.
    Useful for locating resources in multi-site deployments.

    Args:
        settings: Application settings
        query: Search query (device name, MAC address, client name, network name)
        search_type: Type of search - "device", "client", "network", or "all"

    Returns:
        Search results with site context
    """

    valid_types = ["device", "client", "network", "all"]
    if search_type not in valid_types:
        raise ValueError(f"search_type must be one of {valid_types}, got '{search_type}'")

    async with SiteManagerClient(settings) as client:
        logger.info(sanitize_log_message(f"Searching across sites: query='{query}', type={search_type}"))

        # Get all sites first
        sites_response = await client.list_sites()
        sites_data = sites_response.get("data", sites_response.get("sites", []))

        results: list[dict[str, Any]] = []
        query_lower = query.lower()

        # Search across each site
        for site in sites_data:
            site_id = site.get("site_id", "")
            site_name = site.get("name", site_id)

            # Search devices
            if search_type in ["device", "all"]:
                try:
                    # This would query the devices endpoint for each site
                    # For now, checking if site data includes device information
                    devices = site.get("devices", [])
                    for device in devices:
                        device_name = device.get("name", "").lower()
                        device_mac = device.get("mac", "").lower()
                        if query_lower in device_name or query_lower in device_mac:
                            results.append(
                                {
                                    "type": "device",
                                    "site_id": site_id,
                                    "site_name": site_name,
                                    "resource": device,
                                }
                            )
                except Exception as e:
                    logger.debug(sanitize_log_message(f"Error searching devices in site {site_id}: {e}"))

            # Search clients
            if search_type in ["client", "all"]:
                try:
                    clients = site.get("clients", [])
                    for client_obj in clients:
                        client_name = client_obj.get("name", "").lower()
                        client_mac = client_obj.get("mac", "").lower()
                        client_ip = client_obj.get("ip", "").lower()
                        if (
                            query_lower in client_name
                            or query_lower in client_mac
                            or query_lower in client_ip
                        ):
                            results.append(
                                {
                                    "type": "client",
                                    "site_id": site_id,
                                    "site_name": site_name,
                                    "resource": client_obj,
                                }
                            )
                except Exception as e:
                    logger.debug(sanitize_log_message(f"Error searching clients in site {site_id}: {e}"))

            # Search networks
            if search_type in ["network", "all"]:
                try:
                    networks = site.get("networks", [])
                    for network in networks:
                        network_name = network.get("name", "").lower()
                        if query_lower in network_name:
                            results.append(
                                {
                                    "type": "network",
                                    "site_id": site_id,
                                    "site_name": site_name,
                                    "resource": network,
                                }
                            )
                except Exception as e:
                    logger.debug(sanitize_log_message(f"Error searching networks in site {site_id}: {e}"))

        search_result = CrossSiteSearchResult(
            total_results=len(results),
            search_query=query,
            result_type=search_type,  # type: ignore[arg-type]
            results=results,
        )

        return search_result.model_dump()  # type: ignore[no-any-return]


# ISP Metrics Tools (added 2026-02-16)
@require_site_manager
async def get_isp_metrics(settings: Settings, site_id: str) -> dict[str, Any]:
    """Get ISP metrics for a specific site.

    Args:
        settings: Application settings
        site_id: Site identifier

    Returns:
        ISP metrics data including bandwidth, latency, jitter, and packet loss
    """
    async with SiteManagerClient(settings) as client:
        logger.info(sanitize_log_message(f"Retrieving ISP metrics for site: {site_id}"))

        response = await client.get_isp_metrics(site_id)
        data = response.get("data", response)

        return ISPMetrics(**data).model_dump()  # type: ignore[no-any-return]


@require_site_manager
async def query_isp_metrics(
    settings: Settings,
    site_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict[str, Any]]:
    """Query ISP metrics with optional filters.

    Args:
        settings: Application settings
        site_id: Optional site identifier (None for all sites)
        start_time: Optional start time in ISO format (e.g., "2026-02-01T00:00:00Z")
        end_time: Optional end time in ISO format

    Returns:
        List of ISP metrics matching the query
    """

    async with SiteManagerClient(settings) as client:
        logger.info(sanitize_log_message(f"Querying ISP metrics (site_id={site_id}, start={start_time}, end={end_time})"))

        response = await client.query_isp_metrics(site_id, start_time, end_time)
        data = response.get("data", response)

        # Handle both single result and list of results
        if isinstance(data, list):
            return [ISPMetrics(**item).model_dump() for item in data]
        if isinstance(data, dict):
            return [ISPMetrics(**data).model_dump()]
        return []


# SD-WAN Configuration Tools (added 2026-02-16)
@require_site_manager
async def list_sdwan_configs(settings: Settings) -> list[dict[str, Any]]:
    """List all SD-WAN configurations.

    Args:
        settings: Application settings

    Returns:
        List of SD-WAN configurations
    """

    async with SiteManagerClient(settings) as client:
        logger.info("Retrieving SD-WAN configurations")

        response = await client.list_sdwan_configs()
        data = response.get("data", response.get("configs", []))

        if isinstance(data, list):
            return [SDWANConfig(**config).model_dump() for config in data]
        else:
            return []


@require_site_manager
async def get_sdwan_config(settings: Settings, config_id: str) -> dict[str, Any]:
    """Get SD-WAN configuration by ID.

    Args:
        settings: Application settings
        config_id: Configuration identifier

    Returns:
        SD-WAN configuration details
    """

    async with SiteManagerClient(settings) as client:
        logger.info(sanitize_log_message(f"Retrieving SD-WAN configuration: {config_id}"))

        response = await client.get_sdwan_config(config_id)
        data = response.get("data", response)

        return SDWANConfig(**data).model_dump()  # type: ignore[no-any-return]


@require_site_manager
async def get_sdwan_config_status(settings: Settings, config_id: str) -> dict[str, Any]:
    """Get SD-WAN configuration deployment status.

    Args:
        settings: Application settings
        config_id: Configuration identifier

    Returns:
        SD-WAN configuration deployment status
    """

    async with SiteManagerClient(settings) as client:
        logger.info(sanitize_log_message(f"Retrieving SD-WAN configuration status: {config_id}"))

        response = await client.get_sdwan_config_status(config_id)
        data = response.get("data", response)

        return SDWANConfigStatus(**data).model_dump()  # type: ignore[no-any-return]


# Host Management Tools (added 2026-02-16)
@require_site_manager
async def list_hosts(
    settings: Settings, limit: int | None = None, offset: int | None = None
) -> list[dict[str, Any]]:
    """List all managed hosts/consoles.

    Args:
        settings: Application settings
        limit: Optional maximum number of hosts to return
        offset: Optional number of hosts to skip (for pagination)

    Returns:
        List of managed hosts
    """

    async with SiteManagerClient(settings) as client:
        logger.info(sanitize_log_message(f"Retrieving hosts list (limit={limit}, offset={offset})"))

        response = await client.list_hosts(limit, offset)
        data = response.get("data", response.get("hosts", []))

        if isinstance(data, list):
            return [Host(**host).model_dump() for host in data]
        else:
            return []


@require_site_manager
async def get_host(settings: Settings, host_id: str) -> dict[str, Any]:
    """Get host details by ID.

    Args:
        settings: Application settings
        host_id: Host identifier

    Returns:
        Host details
    """

    async with SiteManagerClient(settings) as client:
        logger.info(sanitize_log_message(f"Retrieving host details: {host_id}"))

        response = await client.get_host(host_id)
        data = response.get("data", response)

        return Host(**data).model_dump()  # type: ignore[no-any-return]


# Version Control Tool (added 2026-02-16)
@require_site_manager
async def get_version_control(settings: Settings) -> dict[str, Any]:
    """Get API version control information.

    Args:
        settings: Application settings

    Returns:
        Version control information including current, latest, and deprecated versions
    """

    async with SiteManagerClient(settings) as client:
        logger.info("Retrieving API version control information")

        response = await client.get_version_control()
        data = response.get("data", response)

        return VersionControl(**data).model_dump()  # type: ignore[no-any-return]
