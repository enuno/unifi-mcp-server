"""Reference data models for supporting resources."""

from pydantic import BaseModel, ConfigDict, Field


class DeviceTag(BaseModel):
    """UniFi device tag for WiFi broadcast assignments."""

    id: str = Field(..., description="Tag ID", alias="_id")
    name: str = Field(..., description="Tag name")
    devices: list[str] | None = Field(None, description="Associated device IDs")
    site_id: str | None = Field(None, description="Site ID")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f191e810c19729de860ea",
                "name": "Guest WiFi APs",
                "devices": ["device-id-1", "device-id-2"],
            }
        },
    )


class Country(BaseModel):
    """ISO country code and name."""

    code: str = Field(..., description="ISO 3166-1 alpha-2 country code")
    name: str = Field(..., description="Country name")

    model_config = ConfigDict(
        json_schema_extra={"example": {"code": "US", "name": "United States"}}
    )
