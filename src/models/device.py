"""Device data model."""


from pydantic import BaseModel, ConfigDict, Field


class Device(BaseModel):
    """UniFi network device information."""

    id: str = Field(..., description="Device ID", alias="_id")
    name: str | None = Field(None, description="Device name")
    model: str = Field(..., description="Device model")
    type: str = Field(..., description="Device type (uap, usw, ugw, etc.)")
    mac: str = Field(..., description="Device MAC address")
    ip: str | None = Field(None, description="Device IP address")

    # Status fields
    state: int = Field(..., description="Device state (0=offline, 1=online, etc.)")
    adopted: bool | None = Field(None, description="Whether device is adopted")
    disabled: bool | None = Field(None, description="Whether device is disabled")

    # Hardware info
    version: str | None = Field(None, description="Firmware version")
    uptime: int | None = Field(None, description="Uptime in seconds")

    # Performance metrics
    cpu: float | None = Field(None, description="CPU usage percentage")
    mem: float | None = Field(None, description="Memory usage percentage")
    uplink_depth: int | None = Field(None, description="Uplink depth in network topology")

    # Network stats
    bytes: int | None = Field(None, description="Total bytes transferred")
    tx_bytes: int | None = Field(None, description="Transmitted bytes")
    rx_bytes: int | None = Field(None, description="Received bytes")

    # Additional metadata
    serial: str | None = Field(None, description="Device serial number")
    license_state: str | None = Field(None, description="License state")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "AP-Office",
                "model": "U6-LR",
                "type": "uap",
                "mac": "aa:bb:cc:dd:ee:ff",
                "ip": "192.168.1.10",
                "state": 1,
                "uptime": 86400,
            }
        },
    )
