"""Client data model."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Client(BaseModel):
    """UniFi network client information."""

    mac: str = Field(..., description="Client MAC address")
    ip: Optional[str] = Field(None, description="Client IP address")
    hostname: Optional[str] = Field(None, description="Client hostname")
    name: Optional[str] = Field(None, description="Client name (user-assigned)")

    # Connection info
    is_wired: Optional[bool] = Field(None, description="Whether client is wired")
    is_guest: Optional[bool] = Field(None, description="Whether client is on guest network")
    essid: Optional[str] = Field(None, description="SSID name (for wireless clients)")
    channel: Optional[int] = Field(None, description="WiFi channel (for wireless clients)")
    radio: Optional[str] = Field(None, description="Radio type (ng, na, etc.)")

    # Signal strength (wireless only)
    signal: Optional[int] = Field(None, description="Signal strength in dBm")
    rssi: Optional[int] = Field(None, description="RSSI value")
    noise: Optional[int] = Field(None, description="Noise level in dBm")

    # Network statistics
    tx_bytes: Optional[int] = Field(None, description="Transmitted bytes")
    rx_bytes: Optional[int] = Field(None, description="Received bytes")
    tx_packets: Optional[int] = Field(None, description="Transmitted packets")
    rx_packets: Optional[int] = Field(None, description="Received packets")
    tx_rate: Optional[int] = Field(None, description="Transmission rate in Kbps")
    rx_rate: Optional[int] = Field(None, description="Receiving rate in Kbps")

    # Session info
    uptime: Optional[int] = Field(None, description="Session uptime in seconds")
    last_seen: Optional[int] = Field(None, description="Last seen timestamp")
    first_seen: Optional[int] = Field(None, description="First seen timestamp")

    # Device info
    oui: Optional[str] = Field(None, description="MAC OUI manufacturer")
    os_class: Optional[int] = Field(None, description="Operating system class")
    os_name: Optional[str] = Field(None, description="Operating system name")

    # Associated device
    ap_mac: Optional[str] = Field(None, description="Access point MAC address")
    sw_mac: Optional[str] = Field(None, description="Switch MAC address")
    gw_mac: Optional[str] = Field(None, description="Gateway MAC address")

    # VLAN
    vlan: Optional[int] = Field(None, description="VLAN ID")
    network: Optional[str] = Field(None, description="Network name")

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
