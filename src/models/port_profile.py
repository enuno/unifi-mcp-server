"""Port profile and device port override data models."""

from pydantic import BaseModel, ConfigDict, Field


class PortProfile(BaseModel):
    """UniFi switch port profile configuration."""

    id: str = Field(..., description="Port profile ID", alias="_id")
    site_id: str | None = Field(None, description="Site ID")
    name: str = Field(..., description="Profile name")
    forward: str = Field(
        "all",
        description="Forwarding mode (all, native, customize, disabled)",
    )
    native_networkconf_id: str | None = Field(None, description="Native network configuration ID")
    excluded_networkconf_ids: list[str] = Field(
        default_factory=list, description="Excluded network configuration IDs"
    )
    tagged_networkconf_ids: list[str] = Field(
        default_factory=list, description="Tagged network configuration IDs"
    )
    poe_mode: str | None = Field(None, description="PoE mode (auto, off, pasv24, passthrough)")
    speed: int | None = Field(None, description="Port speed in Mbps")
    full_duplex: bool | None = Field(None, description="Full duplex mode")
    autoneg: bool | None = Field(None, description="Auto-negotiation enabled")
    dot1x_ctrl: str | None = Field(None, description="802.1X control mode")
    lldpmed_enabled: bool | None = Field(None, description="LLDP-MED enabled")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f191e810c19729de860ea",
                "name": "IoT Profile",
                "forward": "native",
                "native_networkconf_id": "60a1b2c3d4e5f6a7b8c9d0e1",
            }
        },
    )


class PortOverride(BaseModel):
    """Device port override configuration."""

    port_idx: int = Field(..., description="Port index (1-based)")
    portconf_id: str = Field(..., description="Port profile configuration ID")
    name: str | None = Field(None, description="Port name/label")
    poe_mode: str | None = Field(None, description="PoE mode override")
    autoneg: bool | None = Field(None, description="Auto-negotiation override")
    speed: int | None = Field(None, description="Speed override in Mbps")
    full_duplex: bool | None = Field(None, description="Full duplex override")

    model_config = ConfigDict(populate_by_name=True)


class PortTableEntry(BaseModel):
    """Device port table entry (read-only status)."""

    port_idx: int = Field(..., description="Port index (1-based)")
    name: str | None = Field(None, description="Port name")
    media: str | None = Field(None, description="Media type (GE, SFP, etc.)")
    speed: int | None = Field(None, description="Current speed in Mbps")
    full_duplex: bool | None = Field(None, description="Full duplex active")
    poe_enable: bool | None = Field(None, description="PoE enabled")
    port_poe: bool | None = Field(None, description="PoE capable")
    portconf_id: str | None = Field(None, description="Applied port profile ID")
    up: bool | None = Field(None, description="Port link status")
    is_uplink: bool | None = Field(None, description="Whether port is an uplink")

    model_config = ConfigDict(populate_by_name=True)
