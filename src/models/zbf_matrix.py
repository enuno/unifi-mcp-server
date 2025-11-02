"""Zone-Based Firewall matrix models."""

from pydantic import BaseModel, Field
from typing import Literal


class ZonePolicy(BaseModel):
    """Policy between two zones."""

    source_zone_id: str = Field(..., description="Source zone identifier")
    destination_zone_id: str = Field(..., description="Destination zone identifier")
    action: Literal["allow", "deny"] = Field(..., description="Policy action")
    description: str | None = Field(None, description="Policy description")
    priority: int | None = Field(None, description="Policy priority")
    enabled: bool = Field(True, description="Whether policy is enabled")


class ApplicationBlockRule(BaseModel):
    """Application blocking rule for a zone."""

    zone_id: str = Field(..., description="Zone identifier")
    application_id: str = Field(..., description="DPI application identifier")
    application_name: str | None = Field(None, description="Application name")
    action: Literal["block", "allow"] = Field(..., description="Block or allow action")
    enabled: bool = Field(True, description="Whether rule is enabled")
    description: str | None = Field(None, description="Rule description")


class ZonePolicyMatrix(BaseModel):
    """Matrix of zone-to-zone policies."""

    site_id: str = Field(..., description="Site identifier")
    zones: list[str] = Field(..., description="List of zone IDs in the matrix")
    policies: list[ZonePolicy] = Field(
        default_factory=list, description="List of inter-zone policies"
    )
    default_policy: Literal["allow", "deny"] = Field(
        "allow", description="Default policy for unconfigured zone pairs"
    )


class ZoneNetworkAssignment(BaseModel):
    """Network assignment to a zone."""

    zone_id: str = Field(..., description="Zone identifier")
    network_id: str = Field(..., description="Network identifier")
    network_name: str | None = Field(None, description="Network name")
    assigned_at: str | None = Field(None, description="ISO timestamp of assignment")

