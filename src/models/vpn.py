"""VPN data models."""

from pydantic import BaseModel, ConfigDict, Field


class VPNTunnel(BaseModel):
    """UniFi Site-to-Site VPN Tunnel."""

    id: str = Field(..., description="VPN tunnel ID", alias="_id")
    name: str = Field(..., description="Tunnel name")
    enabled: bool | None = Field(None, description="Whether tunnel is enabled")
    peer_address: str | None = Field(None, description="Remote peer address")
    local_network: str | None = Field(None, description="Local network CIDR")
    remote_network: str | None = Field(None, description="Remote network CIDR")
    status: str | None = Field(None, description="Connection status")
    ipsec_profile: str | None = Field(None, description="IPSec profile name")
    site_id: str | None = Field(None, description="Site ID")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f191e810c19729de860ea",
                "name": "Office-to-Datacenter",
                "enabled": True,
                "peer_address": "203.0.113.10",
                "local_network": "192.168.1.0/24",
                "remote_network": "10.0.0.0/24",
                "status": "connected",
            }
        },
    )


class VPNServer(BaseModel):
    """UniFi VPN Server configuration."""

    id: str = Field(..., description="VPN server ID", alias="_id")
    name: str = Field(..., description="Server name")
    enabled: bool | None = Field(None, description="Whether server is enabled")
    server_type: str | None = Field(None, description="VPN type (L2TP, PPTP, etc.)")
    network: str | None = Field(None, description="VPN client network")
    dns_servers: list[str] | None = Field(None, description="DNS servers for clients")
    max_connections: int | None = Field(None, description="Maximum concurrent connections")
    site_id: str | None = Field(None, description="Site ID")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f191e810c19729de860ea",
                "name": "Remote Access VPN",
                "enabled": True,
                "server_type": "L2TP",
                "network": "192.168.250.0/24",
                "max_connections": 50,
            }
        },
    )
