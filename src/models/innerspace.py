"""UniFi InnerSpace API models (Phase 6).

InnerSpace (indoor location/analytics) is read-only via the Cloud Connector
proxy; all models are permissive record shapes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InnerSpaceAccessPoint(BaseModel):
    """Access point placed on an InnerSpace floor plan."""

    id: str | None = Field(None, description="Access point identifier")
    name: str | None = Field(None, description="Access point name")
    site_id: str | None = Field(None, alias="siteId", description="Associated site")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class InnerSpaceFloorPlan(BaseModel):
    """InnerSpace floor plan."""

    id: str | None = Field(None, description="Plan identifier")
    name: str | None = Field(None, description="Plan name")
    site_id: str | None = Field(None, alias="siteId", description="Associated site")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class InnerSpaceInventoryItem(BaseModel):
    """Unplaced device in InnerSpace inventory."""

    id: str | None = Field(None, description="Device identifier")
    name: str | None = Field(None, description="Device name")
    site_id: str | None = Field(None, alias="siteId", description="Associated site")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class InnerSpaceProject(BaseModel):
    """InnerSpace project data for integration."""

    id: str | None = Field(None, description="Project identifier")
    name: str | None = Field(None, description="Project name")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class InnerSpaceSwitch(BaseModel):
    """Switch placed on an InnerSpace floor plan."""

    id: str | None = Field(None, description="Switch identifier")
    name: str | None = Field(None, description="Switch name")
    site_id: str | None = Field(None, alias="siteId", description="Associated site")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


__all__ = [
    "InnerSpaceAccessPoint",
    "InnerSpaceFloorPlan",
    "InnerSpaceInventoryItem",
    "InnerSpaceProject",
    "InnerSpaceSwitch",
]
