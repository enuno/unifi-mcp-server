"""Traffic flow models.

These map the UniFi local v2 API ``/firewall-policies/../traffic-flows``
response shape, which is what the live controller returns.  The integration
API does not expose traffic flows at all, so there is no cloud-mode
equivalent for these models.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TrafficFlowEndpoint(BaseModel):
    """Source or destination side of a traffic flow.

    Matches the nested object the v2 ``traffic-flows`` endpoint returns.
    Most fields are optional because UniFi omits them when they aren't
    relevant (e.g. ``client_name``/``mac`` only appear on the source side
    for LAN endpoints, ``region``/``domains`` only on the external
    destination side).
    """

    id: str | None = Field(None, description="Endpoint identifier (MAC or IP)")
    ip: str | None = Field(None, description="IP address")
    port: int | None = Field(None, description="Port number")
    mac: str | None = Field(None, description="MAC address (LAN endpoints only)")
    client_name: str | None = Field(None, description="Client display name")
    client_oui: str | None = Field(None, description="Client OUI / vendor string")
    network_id: str | None = Field(None, description="Network (VLAN) internal id")
    network_name: str | None = Field(None, description="Network (VLAN) display name")
    subnet: str | None = Field(None, description="Network subnet in CIDR form")
    zone_id: str | None = Field(None, description="Firewall zone internal id")
    zone_name: str | None = Field(None, description="Firewall zone display name")
    region: str | None = Field(None, description="ISO country code (external endpoints)")
    domains: list[str] = Field(
        default_factory=list, description="Resolved domains for this endpoint"
    )
    client_fingerprint: dict[str, Any] | None = Field(
        None, description="Device fingerprint (category, vendor, OS)"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TrafficFlowData(BaseModel):
    """Byte / packet counters for a flow."""

    bytes_tx: int = Field(0, description="Bytes transmitted from source to destination")
    bytes_rx: int = Field(0, description="Bytes received from destination back to source")
    bytes_total: int = Field(0, description="Total bytes transferred")
    packets_tx: int = Field(0, description="Packets transmitted from source")
    packets_rx: int = Field(0, description="Packets received back from destination")
    packets_total: int = Field(0, description="Total packets transferred")

    model_config = ConfigDict(extra="allow")


class TrafficFlowPolicy(BaseModel):
    """Reference to the firewall policy that matched a flow."""

    type: str | None = Field(None, description="Policy category, e.g. 'FIREWALL'")
    internal_type: str | None = Field(None, description="Internal match type, e.g. 'CONNTRACK'")
    id: str | None = Field(None, description="Policy id (when available)")

    model_config = ConfigDict(extra="allow")


class TrafficFlow(BaseModel):
    """Individual traffic flow record from the v2 ``traffic-flows`` endpoint.

    Every flow carries both sides of the connection (``source``,
    ``destination``), the transport protocol, the action the firewall took,
    the matched policies, byte / packet counters, and start/end timestamps.
    """

    id: str = Field(..., description="Flow identifier")
    action: Literal["allowed", "blocked"] | str = Field(
        ..., description="Firewall action taken on this flow"
    )
    count: int = Field(1, description="Number of identical flows aggregated")
    direction: Literal["outgoing", "incoming"] | str = Field(
        ..., description="Flow direction relative to the controller"
    )
    protocol: str = Field(..., description="Transport protocol (TCP/UDP/ICMP/...)")
    service: str | None = Field(None, description="Identified service, e.g. 'DNS', 'OTHER'")
    risk: str | None = Field(None, description="Risk classification (low/medium/high)")
    source: TrafficFlowEndpoint = Field(..., description="Source endpoint (usually LAN client)")
    destination: TrafficFlowEndpoint = Field(
        ..., description="Destination endpoint (external IP or LAN peer)"
    )
    traffic_data: TrafficFlowData = Field(
        default_factory=lambda: TrafficFlowData(
            bytes_tx=0, bytes_rx=0, bytes_total=0, packets_tx=0, packets_rx=0, packets_total=0
        ),
        description="Byte and packet counters",
    )
    policies: list[TrafficFlowPolicy] = Field(
        default_factory=list, description="Firewall policies that matched this flow"
    )
    duration_milliseconds: int | None = Field(None, description="Flow duration in milliseconds")
    flow_start_time: int | None = Field(None, description="Flow start timestamp (epoch ms)")
    flow_end_time: int | None = Field(None, description="Flow end timestamp (epoch ms)")
    time: int | None = Field(None, description="Flow record timestamp (epoch ms)")
    in_network: dict[str, Any] | None = Field(
        None,
        alias="in",
        description="Ingress network metadata (raw v2 'in' field)",
    )
    out_network: dict[str, Any] | None = Field(
        None,
        alias="out",
        description="Egress network metadata (raw v2 'out' field)",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FlowStatistics(BaseModel):
    """Aggregated statistics over a sample of traffic flows.

    The statistics are computed over the default rolling snapshot of the
    50 most-recent completed flows, so they describe that snapshot rather
    than a time range.
    """

    site_id: str = Field(..., description="Site identifier")
    sample_size: int = Field(
        0, description="Number of flows aggregated (the rolling snapshot holds 50)"
    )
    total_flows: int = Field(0, description="Total flow records seen")
    total_bytes: int = Field(0, description="Total bytes across all flows in the sample")
    total_bytes_tx: int = Field(0, description="Total bytes transmitted from sources")
    total_bytes_rx: int = Field(0, description="Total bytes received by sources")
    total_packets: int = Field(0, description="Total packets across all flows")
    unique_sources: int = Field(0, description="Distinct source endpoints (by id)")
    unique_destinations: int = Field(0, description="Distinct destination endpoints (by ip)")
    protocol_breakdown: dict[str, int] = Field(
        default_factory=dict, description="Flow count per protocol"
    )
    action_breakdown: dict[str, int] = Field(
        default_factory=dict, description="Flow count per firewall action"
    )
    top_destinations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top destination endpoints by total bytes",
    )

    model_config = ConfigDict(extra="allow")


class FlowRuleReferenceMatch(BaseModel):
    """A flow that matches a proposed firewall rule intent.

    Used by :func:`find_flows_for_rule_reference` so the caller can show
    the LLM the concrete traffic a draft rule would have affected before
    the rule is created.
    """

    flow_id: str = Field(..., description="Flow identifier")
    source_label: str = Field(..., description="Human-readable source label")
    destination_label: str = Field(..., description="Human-readable destination label")
    protocol: str = Field(..., description="Protocol")
    destination_port: int | None = Field(None, description="Destination port")
    bytes_total: int = Field(0, description="Total bytes for this flow")
    action: str = Field(..., description="Current firewall action for the flow")
    source_zone_name: str | None = Field(None, description="Source zone name")
    destination_zone_name: str | None = Field(None, description="Destination zone name")
    source_network_name: str | None = Field(None, description="Source VLAN name")
    flow_start_time: int | None = Field(None, description="Flow start timestamp (epoch ms)")

    model_config = ConfigDict(extra="allow")


class BlockFlowAction(BaseModel):
    """Result of a flow block action (creates a firewall rule)."""

    action_id: str = Field(..., description="Block action identifier")
    block_type: Literal["source_ip", "destination_ip", "application"] = Field(
        ..., description="Type of block"
    )
    blocked_target: str = Field(..., description="Blocked IP or application id")
    rule_id: str | None = Field(None, description="Created firewall rule id")
    zone_id: str | None = Field(None, description="Zone id if using ZBF")
    duration: Literal["permanent", "temporary"] | None = Field(
        None, description="Block duration type"
    )
    expires_at: str | None = Field(None, description="Expiration timestamp for temporary blocks")
    created_at: str = Field(..., description="Creation timestamp (ISO)")

    model_config = ConfigDict(extra="allow")


class ClientFlowAggregation(BaseModel):
    """Client-level aggregation computed from the flow sample."""

    client_mac: str = Field(..., description="Client MAC address")
    client_name: str | None = Field(None, description="Client display name")
    client_ip: str | None = Field(None, description="Client IP address")
    site_id: str = Field(..., description="Site identifier")
    sample_size: int = Field(0, description="Number of flows aggregated for this client")
    total_bytes: int = Field(0, description="Total bytes across the client's flows")
    total_packets: int = Field(0, description="Total packets across the client's flows")
    top_destinations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top destination endpoints for this client",
    )
    protocol_breakdown: dict[str, int] = Field(
        default_factory=dict, description="Protocol distribution"
    )

    model_config = ConfigDict(extra="allow")


class FlowExportConfig(BaseModel):
    """Configuration for flow export."""

    export_format: Literal["csv", "json"] = Field(..., description="Export format")
    include_fields: list[str] | None = Field(
        None, description="Specific fields to include (None = all)"
    )
    max_records: int | None = Field(None, description="Maximum number of records")

    model_config = ConfigDict(extra="allow")


# --- Backwards-compat placeholders -------------------------------------------------
#
# The following models exist only to preserve import compatibility for the
# ``get_flow_trends``, ``stream_traffic_flows``, and ``get_connection_states``
# functions in ``traffic_flows.py`` which now raise ``NotImplementedError``.
# They can be removed once all call sites migrate.


class FlowRisk(BaseModel):
    """Stub — the v2 endpoint returns ``risk`` inline on each flow record."""

    flow_id: str = Field(..., description="Flow identifier")
    risk_level: str = Field(..., description="Risk level")

    model_config = ConfigDict(extra="allow")


class FlowStreamUpdate(BaseModel):
    """Stub — streaming is not supported by the v2 endpoint."""

    update_type: Literal["new", "update", "closed"] = Field(..., description="Update type")
    flow: TrafficFlow = Field(..., description="Flow data")
    timestamp: str = Field(..., description="Update timestamp (ISO)")

    model_config = ConfigDict(extra="allow")


class ConnectionState(BaseModel):
    """Stub — the v2 endpoint does not report explicit connection state."""

    flow_id: str = Field(..., description="Flow identifier")
    state: Literal["active", "closed", "timed_out"] = Field(..., description="State")
    last_seen: str = Field(..., description="Last activity timestamp (ISO)")

    model_config = ConfigDict(extra="allow")


class FlowView(BaseModel):
    """Stub — saved flow views are no longer supported."""

    view_id: str = Field(..., description="View identifier")
    site_id: str = Field(..., description="Site identifier")
    name: str = Field(..., description="View name")

    model_config = ConfigDict(extra="allow")
