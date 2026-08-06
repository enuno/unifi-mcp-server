"""UniFi Protect live view and viewer models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProtectViewer(BaseModel):
    """UniFi Protect viewer record."""

    id: str | None = Field(None, description="Viewer identifier")
    name: str | None = Field(None, description="Viewer name")
    liveview: str | None = Field(None, description="Assigned live view identifier")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectLiveViewSlot(BaseModel):
    """A single live view slot."""

    cameras: list[str] | None = Field(None, description="Camera IDs shown in the slot")
    cycle_mode: str | None = Field(None, alias="cycleMode", description="Slot cycling mode")
    cycle_interval: int | None = Field(
        None, alias="cycleInterval", description="Slot cycling interval"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectLiveView(BaseModel):
    """UniFi Protect live view configuration."""

    id: str | None = Field(None, description="Live view identifier")
    model_key: str | None = Field(None, alias="modelKey", description="Model key")
    name: str | None = Field(None, description="Live view name")
    is_default: bool | None = Field(
        None, alias="isDefault", description="Whether this is the default view"
    )
    is_global: bool | None = Field(None, alias="isGlobal", description="Whether the view is global")
    owner: str | None = Field(None, description="Owner identifier")
    layout: int | None = Field(None, description="Layout index")
    slots: list[ProtectLiveViewSlot] | None = Field(None, description="Live view slots")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectMetaInfo(BaseModel):
    """Protect application metadata."""

    name: str | None = Field(None, description="Application name")
    version: str | None = Field(None, description="Application version")
    model: str | None = Field(None, description="Platform model")

    model_config = ConfigDict(populate_by_name=True, extra="allow")
