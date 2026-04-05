"""Zone-Based Firewall models."""

from pydantic import BaseModel, Field


class ZoneNetworkAssignment(BaseModel):
    """Network assignment to a zone."""

    zone_id: str = Field(..., description="Zone identifier")
    network_id: str = Field(..., description="Network identifier")
    network_name: str | None = Field(None, description="Network name")
    assigned_at: str | None = Field(None, description="ISO timestamp of assignment")
