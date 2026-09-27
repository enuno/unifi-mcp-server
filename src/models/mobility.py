"""UniFi Mobility API models (Phase 6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MobilityWorkspace(BaseModel):
    """UniFi Mobility workspace."""

    id: str | None = Field(None, description="Workspace UUID")
    name: str | None = Field(None, description="Workspace name")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MobilityWorkspaceAdmin(BaseModel):
    """Admin user granted access to a Mobility workspace."""

    id: str | None = Field(None, description="Admin identifier")
    email: str | None = Field(None, description="Admin email address")
    role: str | None = Field(None, description="Admin role within the workspace")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MobilityDevice(BaseModel):
    """UniFi Mobility device (LTE/5G gateway)."""

    id: str | None = Field(None, description="Device UUID")
    name: str | None = Field(None, description="Device name")
    model: str | None = Field(None, description="Device model")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MobilityDeviceClient(BaseModel):
    """Client attached to a Mobility device."""

    id: str | None = Field(None, description="Client identifier")
    name: str | None = Field(None, description="Client name")
    mac: str | None = Field(None, description="Client MAC address")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


__all__ = [
    "MobilityDevice",
    "MobilityDeviceClient",
    "MobilityWorkspace",
    "MobilityWorkspaceAdmin",
]
