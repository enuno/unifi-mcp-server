"""RADIUS profile data models."""

from pydantic import BaseModel, ConfigDict, Field


class RADIUSProfile(BaseModel):
    """UniFi RADIUS authentication profile."""

    id: str = Field(..., description="RADIUS profile ID", alias="_id")
    name: str = Field(..., description="Profile name")
    auth_server: str | None = Field(None, description="Authentication server IP/hostname")
    auth_port: int | None = Field(None, description="Authentication port")
    acct_server: str | None = Field(None, description="Accounting server IP/hostname")
    acct_port: int | None = Field(None, description="Accounting port")
    enabled: bool | None = Field(None, description="Whether profile is enabled")
    vlan_enabled: bool | None = Field(None, description="VLAN assignment enabled")
    site_id: str | None = Field(None, description="Site ID")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f191e810c19729de860ea",
                "name": "Corporate RADIUS",
                "auth_server": "radius.example.com",
                "auth_port": 1812,
                "acct_port": 1813,
                "enabled": True,
            }
        },
    )
