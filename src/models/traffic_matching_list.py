"""Traffic Matching List data models."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TrafficMatchingListType(str, Enum):
    """Traffic matching list types."""

    PORTS = "PORTS"
    IPV4_ADDRESSES = "IPV4_ADDRESSES"
    IPV6_ADDRESSES = "IPV6_ADDRESSES"


class TrafficMatchingList(BaseModel):
    """UniFi Traffic Matching List configuration."""

    id: str = Field(..., description="Traffic matching list ID", alias="_id")
    type: TrafficMatchingListType = Field(..., description="List type")
    name: str = Field(..., description="List name")
    items: list[str] = Field(default_factory=list, description="List items (ports, IPs, etc.)")
    site_id: str | None = Field(None, description="Site ID")

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "_id": "507f191e810c19729de860ea",
                "type": "PORTS",
                "name": "Common Web Ports",
                "items": ["80", "443", "8080", "8443"],
            }
        },
    )


class TrafficMatchingListCreate(BaseModel):
    """Request model for creating traffic matching list."""

    type: TrafficMatchingListType = Field(..., description="List type")
    name: str = Field(..., description="List name", min_length=1, max_length=128)
    items: list[str] = Field(..., description="List items (non-empty)", min_length=1)

    model_config = ConfigDict(use_enum_values=True)


class TrafficMatchingListUpdate(BaseModel):
    """Request model for updating traffic matching list."""

    type: TrafficMatchingListType | None = Field(None, description="List type")
    name: str | None = Field(None, description="List name", min_length=1, max_length=128)
    items: list[str] | None = Field(None, description="List items", min_length=1)

    model_config = ConfigDict(use_enum_values=True)
