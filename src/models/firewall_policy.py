from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PolicyAction(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class MatchingTarget(str, Enum):
    ANY = "ANY"
    IP = "IP"
    NETWORK = "NETWORK"
    REGION = "REGION"
    CLIENT = "CLIENT"
    APP = "APP"


class ConnectionStateType(str, Enum):
    ALL = "ALL"
    CUSTOM = "CUSTOM"
    RESPOND_ONLY = "RESPOND_ONLY"


class IPVersion(str, Enum):
    BOTH = "BOTH"
    IPV4 = "IPV4"
    IPV6 = "IPV6"


class MatchTarget(BaseModel):
    zone_id: str = Field(..., description="Firewall zone ID")
    matching_target: MatchingTarget = Field(..., description="Target matching type")
    matching_target_type: str | None = Field(None, description="Target type qualifier")
    port_matching_type: str | None = Field(
        None,
        description="Port matching mode: ANY (no filter), SPECIFIC (use 'port'), OBJECT (use 'port_group_id')",
    )
    port: str | None = Field(
        None,
        description="Port value for SPECIFIC mode — single port '53' or range '9000-9010'",
    )
    port_group_id: str | None = Field(
        None,
        description="Firewall port-group id for OBJECT mode (see firewall_groups tools)",
    )
    match_opposite_ports: bool | None = Field(None, description="Invert port matching")
    ips: list[str] | None = Field(None, description="IP addresses for IP matching")
    match_opposite_ips: bool | None = Field(None, description="Invert IP matching")
    network_ids: list[str] | None = Field(None, description="Network IDs for NETWORK matching")
    match_opposite_networks: bool | None = Field(None, description="Invert network matching")
    regions: list[str] | None = Field(None, description="ISO country codes for REGION matching")
    client_macs: list[str] | None = Field(None, description="MAC addresses for CLIENT matching")
    match_mac: bool | None = Field(None, description="Match by MAC address")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class Schedule(BaseModel):
    mode: str = Field(..., description="Schedule mode (ALWAYS/CUSTOM)")
    date_start: str | None = Field(None, description="Start date YYYY-MM-DD")
    date_end: str | None = Field(None, description="End date YYYY-MM-DD")
    time_all_day: bool | None = Field(None, description="All day or specific time")
    time_range_start: str | None = Field(None, description="Start time HH:MM")
    time_range_end: str | None = Field(None, description="End time HH:MM")
    repeat_on_days: list[str] | None = Field(None, description="Days to repeat")

    model_config = ConfigDict(extra="allow")


class FirewallPolicy(BaseModel):
    id: str = Field(..., alias="_id", description="Unique policy identifier")
    name: str = Field(..., description="Policy name")
    action: PolicyAction = Field(..., description="Policy action (ALLOW/BLOCK)")
    enabled: bool = Field(True, description="Whether policy is active")
    predefined: bool = Field(False, description="Whether this is a system rule")
    index: int = Field(10000, description="Priority order (lower = higher priority)")
    protocol: str = Field("all", description="Protocol (all/tcp/udp/tcp_udp/icmpv6)")
    ip_version: IPVersion = Field(IPVersion.BOTH, description="IP version filter")
    connection_state_type: ConnectionStateType = Field(
        ConnectionStateType.ALL, description="Connection state matching type"
    )
    connection_states: list[str] | None = Field(
        None, description="Connection states when type is CUSTOM"
    )
    create_allow_respond: bool | None = Field(None, description="Auto-allow response traffic")
    logging: bool | None = Field(None, description="Enable rule logging")
    match_ip_sec: bool | None = Field(None, description="Match IPsec traffic")
    match_opposite_protocol: bool | None = Field(None, description="Match opposite protocol")
    icmp_typename: str | None = Field(None, description="ICMP type name")
    icmp_v6_typename: str | None = Field(None, description="ICMPv6 type name")
    description: str | None = Field(None, description="Policy description")
    origin_id: str | None = Field(None, description="Related origin object ID")
    origin_type: str | None = Field(None, description="Origin type (e.g. port_forward)")
    source: MatchTarget = Field(..., description="Source matching criteria")
    destination: MatchTarget = Field(..., description="Destination matching criteria")
    schedule: Schedule | None = Field(None, description="Time-based scheduling")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FirewallPolicyCreate(BaseModel):
    name: str = Field(..., description="Policy name")
    action: str = Field(..., description="Policy action (ALLOW/BLOCK)")
    enabled: bool = Field(True, description="Whether policy is active")
    protocol: str = Field("all", description="Protocol")
    ip_version: str = Field("BOTH", description="IP version filter")
    connection_state_type: str = Field("ALL", description="Connection state type")
    connection_states: list[str] | None = Field(None, description="Connection states")
    icmp_typename: str | None = Field(
        None, description="ICMP type name filter (e.g. 'ANY', 'echo')"
    )
    icmp_v6_typename: str | None = Field(None, description="ICMPv6 type name filter")
    match_ip_sec: bool | None = Field(None, description="Match IPsec traffic only")
    match_opposite_protocol: bool | None = Field(None, description="Invert protocol matching")
    source: dict = Field(..., description="Source matching criteria")
    destination: dict = Field(..., description="Destination matching criteria")
    description: str | None = Field(None, description="Policy description")
    index: int | None = Field(None, description="Priority order")
    schedule: dict | None = Field(None, description="Time-based scheduling")
    create_allow_respond: bool | None = Field(
        None,
        description="Allow response traffic. Must be False for BLOCK rules.",
    )

    model_config = ConfigDict(extra="allow")


class FirewallZoneV2Mapping(BaseModel):
    """Zone listing entry from the v2 ``/firewall/zone`` endpoint.

    Exposes both the internal MongoDB ObjectId (used by the v2
    ``firewall-policies`` endpoint) and the external UUID (used by the public
    integration API and most other MCP tools), plus the display name and
    ``zone_key``. Callers can hand any of these identifiers to
    ``create_firewall_policy`` / ``update_firewall_policy`` and the zone
    resolver will map them to the internal id.
    """

    internal_id: str | None = Field(
        None,
        description="MongoDB ObjectId used by the v2 firewall-policies endpoint",
    )
    external_id: str | None = Field(
        None,
        description="UUID returned by the public integration API",
    )
    name: str | None = Field(None, description="Display name")
    zone_key: str | None = Field(
        None,
        description="Internal zone key (e.g. 'internal', 'external', 'dmz')",
    )
    default_zone: bool = Field(
        False,
        description="Whether this is a UniFi-defined default zone",
    )
    network_ids: list[str] = Field(
        default_factory=list,
        description="Internal network _ids assigned to this zone",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FirewallPolicyUpdate(BaseModel):
    name: str | None = Field(None, description="Policy name")
    action: str | None = Field(None, description="Policy action")
    enabled: bool | None = Field(None, description="Whether policy is active")
    protocol: str | None = Field(None, description="Protocol")
    ip_version: str | None = Field(None, description="IP version filter")
    connection_state_type: str | None = Field(None, description="Connection state type")
    connection_states: list[str] | None = Field(None, description="Connection states")
    icmp_typename: str | None = Field(None, description="ICMP type name filter")
    icmp_v6_typename: str | None = Field(None, description="ICMPv6 type name filter")
    match_ip_sec: bool | None = Field(None, description="Match IPsec traffic only")
    match_opposite_protocol: bool | None = Field(None, description="Invert protocol matching")
    source: dict | None = Field(None, description="Source matching criteria")
    destination: dict | None = Field(None, description="Destination matching criteria")
    description: str | None = Field(None, description="Policy description")
    index: int | None = Field(None, description="Priority order")
    schedule: dict | None = Field(None, description="Time-based scheduling")

    model_config = ConfigDict(extra="allow")
