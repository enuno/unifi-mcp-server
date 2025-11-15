"""Firewall zone models."""

from pydantic import BaseModel, ConfigDict, Field


class FirewallZone(BaseModel):
    """Firewall zone model."""

    id: str = Field(..., alias="_id", description="Firewall zone identifier")
    site_id: str = Field(..., description="Site identifier")
    name: str = Field(..., description="Zone name")
    description: str | None = Field(None, description="Zone description")

    # Network assignments
    network_ids: list[str] = Field(
        default_factory=list, alias="networks", description="Network IDs assigned to this zone"
    )

    # Zone type
    zone_type: str | None = Field(None, description="Zone type (lan/wan/guest/custom)")

    # Policy configuration
    default_policy: str | None = Field(None, description="Default policy (allow/deny)")

    # Metadata
    is_predefined: bool = Field(False, description="Whether this is a system-defined zone")

    model_config = ConfigDict(populate_by_name=True, extra="allow")
