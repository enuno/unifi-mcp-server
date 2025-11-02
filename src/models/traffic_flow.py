"""Traffic flow models."""

from typing import Literal

from pydantic import BaseModel, Field


class TrafficFlow(BaseModel):
    """Individual traffic flow record."""

    flow_id: str = Field(..., description="Flow identifier")
    site_id: str = Field(..., description="Site identifier")
    source_ip: str = Field(..., description="Source IP address")
    source_port: int | None = Field(None, description="Source port")
    destination_ip: str = Field(..., description="Destination IP address")
    destination_port: int | None = Field(None, description="Destination port")
    protocol: str = Field(..., description="Protocol (tcp/udp/icmp)")
    application_id: str | None = Field(None, description="DPI application identifier")
    application_name: str | None = Field(None, description="Application name")
    bytes_sent: int = Field(0, description="Bytes sent")
    bytes_received: int = Field(0, description="Bytes received")
    packets_sent: int = Field(0, description="Packets sent")
    packets_received: int = Field(0, description="Packets received")
    start_time: str = Field(..., description="Flow start timestamp (ISO)")
    end_time: str | None = Field(None, description="Flow end timestamp (ISO)")
    duration: int | None = Field(None, description="Flow duration in seconds")
    client_mac: str | None = Field(None, description="Client MAC address")
    device_id: str | None = Field(None, description="Device identifier")


class FlowStatistics(BaseModel):
    """Aggregated flow statistics."""

    site_id: str = Field(..., description="Site identifier")
    time_range: str = Field(..., description="Time range for statistics")
    total_flows: int = Field(0, description="Total number of flows")
    total_bytes_sent: int = Field(0, description="Total bytes sent")
    total_bytes_received: int = Field(0, description="Total bytes received")
    total_bytes: int = Field(0, description="Total bytes")
    total_packets_sent: int = Field(0, description="Total packets sent")
    total_packets_received: int = Field(0, description="Total packets received")
    unique_sources: int = Field(0, description="Number of unique source IPs")
    unique_destinations: int = Field(0, description="Number of unique destination IPs")
    top_applications: list[dict] = Field(
        default_factory=list, description="Top applications by bandwidth"
    )


class FlowRisk(BaseModel):
    """Risk assessment data for a flow."""

    flow_id: str = Field(..., description="Flow identifier")
    risk_score: float = Field(..., description="Risk score (0-100)")
    risk_level: Literal["low", "medium", "high", "critical"] = Field(..., description="Risk level")
    indicators: list[str] = Field(default_factory=list, description="List of risk indicators")
    threat_type: str | None = Field(None, description="Type of threat detected")
    description: str | None = Field(None, description="Risk description")


class FlowView(BaseModel):
    """Saved flow view configuration."""

    view_id: str = Field(..., description="View identifier")
    site_id: str = Field(..., description="Site identifier")
    name: str = Field(..., description="View name")
    description: str | None = Field(None, description="View description")
    filter_expression: str | None = Field(None, description="Filter expression")
    time_range: str = Field("24h", description="Time range")
    created_at: str = Field(..., description="Creation timestamp (ISO)")
