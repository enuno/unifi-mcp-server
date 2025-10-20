"""Client data model."""


from pydantic import BaseModel, ConfigDict, Field


class Client(BaseModel):
    """UniFi network client information."""

    mac: str = Field(..., description="Client MAC address")
    ip: str | None = Field(None, description="Client IP address")
    hostname: str | None = Field(None, description="Client hostname")
    name: str | None = Field(None, description="Client name (user-assigned)")

    # Connection info
    is_wired: bool | None = Field(None, description="Whether client is wired")
    is_guest: bool | None = Field(None, description="Whether client is on guest network")
    essid: str | None = Field(None, description="SSID name (for wireless clients)")
    channel: int | None = Field(None, description="WiFi channel (for wireless clients)")
    radio: str | None = Field(None, description="Radio type (ng, na, etc.)")

    # Signal strength (wireless only)
    signal: int | None = Field(None, description="Signal strength in dBm")
    rssi: int | None = Field(None, description="RSSI value")
    noise: int | None = Field(None, description="Noise level in dBm")

    # Network statistics
    tx_bytes: int | None = Field(None, description="Transmitted bytes")
    rx_bytes: int | None = Field(None, description="Received bytes")
    tx_packets: int | None = Field(None, description="Transmitted packets")
    rx_packets: int | None = Field(None, description="Received packets")
    tx_rate: int | None = Field(None, description="Transmission rate in Kbps")
    rx_rate: int | None = Field(None, description="Receiving rate in Kbps")

    # Session info
    uptime: int | None = Field(None, description="Session uptime in seconds")
    last_seen: int | None = Field(None, description="Last seen timestamp")
    first_seen: int | None = Field(None, description="First seen timestamp")

    # Device info
    oui: str | None = Field(None, description="MAC OUI manufacturer")
    os_class: int | None = Field(None, description="Operating system class")
    os_name: str | None = Field(None, description="Operating system name")

    # Associated device
    ap_mac: str | None = Field(None, description="Access point MAC address")
    sw_mac: str | None = Field(None, description="Switch MAC address")
    gw_mac: str | None = Field(None, description="Gateway MAC address")

    # VLAN
    vlan: int | None = Field(None, description="VLAN ID")
    network: str | None = Field(None, description="Network name")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "mac": "aa:bb:cc:dd:ee:01",
                "ip": "192.168.1.100",
                "hostname": "laptop-001",
                "is_wired": False,
                "signal": -45,
                "tx_bytes": 1024000,
                "rx_bytes": 2048000,
            }
        },
    )
