"""Site Manager API models."""

from pydantic import BaseModel, Field
from typing import Literal


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
    site_ids: list[str] = Field(
        default_factory=list, description="Associated site IDs"
    )

