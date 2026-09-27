"""UniFi Carrier Fabric API models (Phase 6)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CarrierServicePlan(BaseModel):
    """Carrier Fabric service plan."""

    id: str | None = Field(None, description="Plan identifier")
    name: str | None = Field(None, description="Plan display name")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class CarrierSubscriber(BaseModel):
    """Carrier Fabric subscriber."""

    id: str | None = Field(None, description="Subscriber identifier")
    subscriber_number: str | None = Field(
        None, alias="subscriberNumber", description="Operator-supplied external reference"
    )
    name: str | None = Field(None, description="Display name")
    email: str | None = Field(None, description="Contact email")
    notes: str | None = Field(None, description="Operator notes")
    service_address: str | None = Field(
        None, alias="serviceAddress", description="Free-text service address"
    )
    plan_id: str | None = Field(None, alias="planId", description="Assigned service plan")
    host_id: str | None = Field(None, alias="hostId", description="Attached gateway host")
    suspended: bool | None = Field(None, description="Whether service is suspended")
    metadata: dict[str, Any] | None = Field(None, description="Free-form metadata")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


__all__ = ["CarrierServicePlan", "CarrierSubscriber"]
