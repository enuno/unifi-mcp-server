"""WAN connection models."""

from pydantic import BaseModel, ConfigDict, Field


class WANConnection(BaseModel):
    """WAN connection model."""

    # Only ``id`` and ``name`` are guaranteed: the Integration v1
    # ``/sites/{site_id}/wans`` endpoint returns just those two fields, and
    # there is no per-WAN detail route to enrich them from. Everything below is
    # optional so a sparse response validates instead of raising, and every
    # optional field defaults to ``None`` rather than to a concrete value, so an
    # omitted field is never reported as an empty list or a ``False`` flag.
    id: str = Field(..., alias="_id", description="WAN connection identifier")
    site_id: str | None = Field(None, description="Site identifier")
    name: str = Field(..., description="WAN connection name")

    # Connection type
    wan_type: str | None = Field(None, description="WAN type (dhcp/static/pppoe)")
    interface: str | None = Field(None, description="Physical interface (eth0/eth1/etc)")

    # IP configuration
    ip_address: str | None = Field(None, description="WAN IP address")
    netmask: str | None = Field(None, description="Subnet mask")
    gateway: str | None = Field(None, description="Gateway IP")
    dns_servers: list[str] | None = Field(None, description="DNS server IPs")

    # Connection status
    status: str | None = Field(None, description="Connection status (online/offline/connecting)")
    uptime: int | None = Field(None, description="Connection uptime in seconds")

    # Statistics
    rx_bytes: int | None = Field(None, description="Received bytes")
    tx_bytes: int | None = Field(None, description="Transmitted bytes")
    rx_packets: int | None = Field(None, description="Received packets")
    tx_packets: int | None = Field(None, description="Transmitted packets")
    rx_errors: int | None = Field(None, description="Receive errors")
    tx_errors: int | None = Field(None, description="Transmit errors")

    # Speed and link
    speed: int | None = Field(None, description="Link speed in Mbps")
    full_duplex: bool | None = Field(None, description="Full duplex status")

    # Failover configuration
    failover_priority: int | None = Field(
        None, description="Failover priority (lower = higher priority)"
    )
    is_backup: bool | None = Field(None, description="Whether this is a backup WAN")

    # ISP information
    isp_name: str | None = Field(None, description="ISP name")

    model_config = ConfigDict(populate_by_name=True, extra="allow")
