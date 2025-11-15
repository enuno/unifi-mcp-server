"""WAN connection models."""

from pydantic import BaseModel, ConfigDict, Field


class WANConnection(BaseModel):
    """WAN connection model."""

    id: str = Field(..., alias="_id", description="WAN connection identifier")
    site_id: str = Field(..., description="Site identifier")
    name: str = Field(..., description="WAN connection name")

    # Connection type
    wan_type: str = Field(..., description="WAN type (dhcp/static/pppoe)")
    interface: str = Field(..., description="Physical interface (eth0/eth1/etc)")

    # IP configuration
    ip_address: str | None = Field(None, description="WAN IP address")
    netmask: str | None = Field(None, description="Subnet mask")
    gateway: str | None = Field(None, description="Gateway IP")
    dns_servers: list[str] = Field(default_factory=list, description="DNS server IPs")

    # Connection status
    status: str = Field(..., description="Connection status (online/offline/connecting)")
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
    is_backup: bool = Field(False, description="Whether this is a backup WAN")

    # ISP information
    isp_name: str | None = Field(None, description="ISP name")

    model_config = ConfigDict(populate_by_name=True, extra="allow")
