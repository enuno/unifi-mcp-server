"""Network data model."""


from pydantic import BaseModel, ConfigDict, Field


class Network(BaseModel):
    """UniFi network configuration."""

    id: str = Field(..., description="Network ID", alias="_id")
    name: str = Field(..., description="Network name")
    purpose: str = Field(..., description="Network purpose (corporate, guest, etc.)")

    # Network configuration
    vlan: int | None = Field(None, description="VLAN ID", alias="vlan_enabled")
    vlan_id: int | None = Field(None, description="VLAN number")
    enabled: bool | None = Field(None, description="Whether network is enabled")

    # IP configuration
    ip_subnet: str | None = Field(None, description="IP subnet (CIDR notation)")
    networkgroup: str | None = Field(None, description="Network group")
    domain_name: str | None = Field(None, description="Domain name")

    # DHCP settings
    dhcpd_enabled: bool | None = Field(None, description="Whether DHCP is enabled")
    dhcpd_start: str | None = Field(None, description="DHCP range start")
    dhcpd_stop: str | None = Field(None, description="DHCP range end")
    dhcpd_leasetime: int | None = Field(None, description="DHCP lease time in seconds")
    dhcpd_dns_enabled: bool | None = Field(None, description="Whether DHCP DNS is enabled")
    dhcpd_dns_1: str | None = Field(None, description="Primary DNS server")
    dhcpd_dns_2: str | None = Field(None, description="Secondary DNS server")
    dhcpd_gateway_enabled: bool | None = Field(
        None, description="Whether DHCP gateway is enabled"
    )
    dhcpd_gateway: str | None = Field(None, description="DHCP gateway IP")

    # IGMP settings
    igmp_snooping: bool | None = Field(None, description="IGMP snooping enabled")

    # IPv6
    ipv6_interface_type: str | None = Field(None, description="IPv6 interface type")
    ipv6_pd_start: str | None = Field(None, description="IPv6 prefix delegation start")
    ipv6_pd_stop: str | None = Field(None, description="IPv6 prefix delegation stop")

    # Site association
    site_id: str | None = Field(None, description="Site ID")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f191e810c19729de860ea",
                "name": "LAN",
                "purpose": "corporate",
                "vlan_enabled": True,
                "vlan_id": 1,
                "ip_subnet": "192.168.1.0/24",
                "dhcpd_enabled": True,
                "dhcpd_start": "192.168.1.100",
                "dhcpd_stop": "192.168.1.254",
            }
        },
    )
