"""Site Manager API models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SiteHealthSummary(BaseModel):
    """Health status for a site."""

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    status: Literal["healthy", "degraded", "down"] = Field(..., description="Health status")
    devices_online: int = Field(0, description="Number of online devices")
    devices_total: int = Field(0, description="Total number of devices")
    clients_active: int = Field(0, description="Number of active clients")
    uptime_percentage: float = Field(0.0, description="Uptime percentage")
    last_updated: str = Field(..., description="Last update timestamp (ISO)")


class InternetHealthMetrics(BaseModel):
    """Internet connectivity metrics."""

    site_id: str | None = Field(None, description="Site identifier (None for aggregate)")
    latency_ms: float | None = Field(None, description="Average latency in milliseconds")
    packet_loss_percent: float = Field(0.0, description="Packet loss percentage")
    jitter_ms: float | None = Field(None, description="Jitter in milliseconds")
    bandwidth_up_mbps: float | None = Field(None, description="Upload bandwidth in Mbps")
    bandwidth_down_mbps: float | None = Field(None, description="Download bandwidth in Mbps")
    status: Literal["healthy", "degraded", "down"] = Field(..., description="Health status")
    last_tested: str = Field(..., description="Last test timestamp (ISO)")


class CrossSiteStatistics(BaseModel):
    """Aggregated statistics across multiple sites."""

    total_sites: int = Field(0, description="Total number of sites")
    sites_healthy: int = Field(0, description="Number of healthy sites")
    sites_degraded: int = Field(0, description="Number of degraded sites")
    sites_down: int = Field(0, description="Number of down sites")
    total_devices: int = Field(0, description="Total number of devices")
    devices_online: int = Field(0, description="Total online devices")
    total_clients: int = Field(0, description="Total number of clients")
    total_bandwidth_up_mbps: float = Field(0.0, description="Total upload bandwidth")
    total_bandwidth_down_mbps: float = Field(0.0, description="Total download bandwidth")
    site_summaries: list[SiteHealthSummary] = Field(
        default_factory=list, description="Health summary for each site"
    )


class VantagePoint(BaseModel):
    """Vantage Point information."""

    vantage_point_id: str = Field(..., description="Vantage Point identifier")
    name: str = Field(..., description="Vantage Point name")
    location: str | None = Field(None, description="Location")
    latitude: float | None = Field(None, description="Latitude")
    longitude: float | None = Field(None, description="Longitude")
    status: Literal["active", "inactive"] = Field(..., description="Status")
    site_ids: list[str] = Field(default_factory=list, description="Associated site IDs")


class SiteInventory(BaseModel):
    """Comprehensive inventory for a single site."""

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    device_count: int = Field(0, description="Total devices")
    device_types: dict[str, int] = Field(default_factory=dict, description="Count by device type")
    client_count: int = Field(0, description="Total active clients")
    network_count: int = Field(0, description="Total networks/VLANs")
    ssid_count: int = Field(0, description="Total SSIDs")
    uplink_count: int = Field(0, description="Total WAN uplinks")
    vpn_tunnel_count: int = Field(0, description="Total VPN tunnels")
    firewall_rule_count: int = Field(0, description="Total firewall rules")
    last_updated: str = Field(..., description="Inventory timestamp (ISO)")


class SitePerformanceMetrics(BaseModel):
    """Performance metrics for a single site."""

    site_id: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site name")
    avg_latency_ms: float | None = Field(None, description="Average latency")
    avg_bandwidth_up_mbps: float | None = Field(None, description="Average upload bandwidth")
    avg_bandwidth_down_mbps: float | None = Field(None, description="Average download bandwidth")
    uptime_percentage: float = Field(0.0, description="Uptime percentage")
    device_online_percentage: float = Field(0.0, description="Percentage of devices online")
    client_count: int = Field(0, description="Active clients")
    health_status: Literal["healthy", "degraded", "down"] = Field(..., description="Overall status")


class CrossSitePerformanceComparison(BaseModel):
    """Performance comparison across multiple sites."""

    total_sites: int = Field(0, description="Number of sites compared")
    best_performing_site: SitePerformanceMetrics | None = Field(
        None, description="Site with best overall performance"
    )
    worst_performing_site: SitePerformanceMetrics | None = Field(
        None, description="Site with worst overall performance"
    )
    average_uptime: float = Field(0.0, description="Average uptime across all sites")
    average_latency_ms: float | None = Field(None, description="Average latency across sites")
    site_metrics: list[SitePerformanceMetrics] = Field(
        default_factory=list, description="Metrics for each site"
    )


class CrossSiteSearchResult(BaseModel):
    """Search result from cross-site search."""

    total_results: int = Field(0, description="Total number of results found")
    search_query: str = Field(..., description="Original search query")
    result_type: Literal["device", "client", "network", "all"] = Field(
        ..., description="Type of results"
    )
    results: list[dict] = Field(
        default_factory=list, description="Search results with site context"
    )


class ISPMetrics(BaseModel):
    """ISP metrics from Site Manager API."""

    site_id: str = Field(..., description="Site identifier")
    isp_name: str | None = Field(None, description="ISP name")
    download_bandwidth_mbps: float | None = Field(None, description="Download bandwidth in Mbps")
    upload_bandwidth_mbps: float | None = Field(None, description="Upload bandwidth in Mbps")
    latency_ms: float | None = Field(None, description="Latency in milliseconds")
    jitter_ms: float | None = Field(None, description="Jitter in milliseconds")
    packet_loss_percent: float = Field(0.0, description="Packet loss percentage")
    timestamp: str = Field(..., description="Measurement timestamp (ISO)")


class SDWANConfig(BaseModel):
    """Site Manager SD-WAN summary/detail; preserve version-specific nested data.

    The v1.0.0 list supplies id/name/type only. Detail includes settings, hubs
    and spokes; those nested values are not a typed steering-policy contract.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    type: str
    settings: dict[str, object] | None = None
    hubs: list[dict[str, object]] | None = None
    spokes: list[dict[str, object]] | None = None


class SDWANStatusConnection(BaseModel):
    """Known connection shape; keep documented tunnel extensions intact."""

    model_config = ConfigDict(extra="allow")

    tunnels: list[dict[str, object]] | None = None


class SDWANStatusSite(BaseModel):
    """Hub/spoke status with independently validated apply and tunnel state."""

    model_config = ConfigDict(extra="allow")

    applyStatus: (
        Literal[
            "ok", "creating", "updating", "removing", "createFailed", "updateFailed", "removeFailed"
        ]
        | None
    ) = None
    connections: list[SDWANStatusConnection] | None = None
    primaryWanStatus: dict[str, object] | None = None
    secondaryWanStatus: dict[str, object] | None = None


class SDWANConfigStatus(BaseModel):
    """Site Manager deployment/generation status, not an inferred health score.

    The upstream response contains hub/spoke apply states and tunnel records;
    preserve them, including future fields, without inventing healthy defaults.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    fingerprint: str | None = None
    generateStatus: Literal["OK", "GENERATING", "GENERATE_FAILED"] | None = None
    hubs: list[SDWANStatusSite] | None = None
    spokes: list[SDWANStatusSite] | None = None
    errors: list[object] | None = None
    warnings: list[object] | None = None


class Host(BaseModel):
    """Managed host/console from Site Manager API."""

    host_id: str = Field(..., description="Host identifier")
    hostname: str = Field(..., description="Hostname")
    ip_address: str | None = Field(None, description="IP address")
    mac_address: str | None = Field(None, description="MAC address")
    model: str | None = Field(None, description="Device model")
    version: str | None = Field(None, description="Firmware/software version")
    site_count: int = Field(0, description="Number of associated sites")
    status: Literal["online", "offline", "unreachable"] = Field(..., description="Host status")
    last_seen: str = Field(..., description="Last seen timestamp (ISO)")


class VersionControl(BaseModel):
    """Version control information from Site Manager API."""

    current_version: str = Field(..., description="Current API version")
    latest_version: str = Field(..., description="Latest available version")
    deprecated_versions: list[str] = Field(
        default_factory=list, description="List of deprecated API versions"
    )
    changelog_url: str | None = Field(None, description="Changelog URL")
    upgrade_recommended: bool = Field(False, description="Whether upgrade is recommended")
    min_supported_version: str = Field(..., description="Minimum supported version")
