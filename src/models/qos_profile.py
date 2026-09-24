"""Traffic route data models.

Note: QoSProfile, ProAVTemplate, SmartQueueConfig and related models were
removed because they backed tools using non-existent API endpoints
(rest/qosprofile, rest/wanconf). See src/tools/qos.py docstring for details.

``TrafficRoute`` models UniFi's **Traffic Routes** feature (policy-based
routing, e.g. sending selected clients or domains through a VPN), as served by
the local v2 API at ``/proxy/network/v2/api/site/{site}/trafficroutes``. The
previous model (``action`` / ``match_criteria`` / ``dscp_marking`` / ...)
matched no UniFi resource and was removed along with ``RouteAction``,
``MatchCriteria`` and ``RouteSchedule`` (issue #171).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrafficRouteTargetDevice(BaseModel):
    """A client or network whose traffic a route applies to."""

    model_config = ConfigDict(extra="allow")

    type: str | None = Field(None, description="Target kind: CLIENT or NETWORK")
    client_mac: str | None = Field(None, description="Client MAC (type CLIENT)")
    network_id: str | None = Field(None, description="Network _id (type NETWORK)")


class TrafficRoute(BaseModel):
    """A UniFi Traffic Route (policy-based routing rule).

    Unknown keys are kept, so fields added by newer controller versions pass
    through to callers instead of being dropped.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(alias="_id", description="Route ID")
    description: str | None = Field(None, description="Route description")
    enabled: bool | None = Field(None, description="Whether the route is active")
    matching_target: str | None = Field(
        None, description="What the route matches: INTERNET, DOMAIN, IP or REGION"
    )
    network_id: str | None = Field(
        None, description="Network _id of the interface (e.g. VPN client, WAN) traffic egresses"
    )
    next_hop: str | None = Field(None, description="Explicit next-hop address, if set")
    kill_switch_enabled: bool | None = Field(
        None, description="Block matching traffic when the egress interface is down"
    )
    domains: list[dict[str, Any]] = Field(
        default_factory=list, description="Domain matches (matching_target DOMAIN)"
    )
    ip_addresses: list[dict[str, Any]] = Field(
        default_factory=list, description="IP / subnet matches (matching_target IP)"
    )
    ip_ranges: list[dict[str, Any]] = Field(
        default_factory=list, description="IP range matches (matching_target IP)"
    )
    regions: list[str] = Field(
        default_factory=list, description="Country codes (matching_target REGION)"
    )
    target_devices: list[TrafficRouteTargetDevice] = Field(
        default_factory=list, description="Clients and networks the route applies to"
    )
