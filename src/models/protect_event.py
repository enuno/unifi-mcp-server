"""UniFi Protect event and subscription models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProtectDeviceUpdateMessage(BaseModel):
    """An update message from the Protect device subscription feed."""

    id: str | None = Field(None, description="Message identifier")
    type: str | None = Field(None, description="Message type")
    device_id: str | None = Field(None, alias="deviceId", description="Device identifier")
    timestamp: str | None = Field(None, description="Timestamp")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectEventMessage(BaseModel):
    """A Protect event message."""

    id: str | None = Field(None, description="Event identifier")
    type: str | None = Field(None, description="Event type")
    camera_id: str | None = Field(None, alias="cameraId", description="Camera identifier")
    device_id: str | None = Field(None, alias="deviceId", description="Device identifier")
    timestamp: str | None = Field(None, description="Timestamp")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectAlarmWebhookResult(BaseModel):
    """Result returned by the alarm webhook endpoint."""

    success: bool | None = Field(None, description="Whether the call succeeded")
    message: str | None = Field(None, description="Status message")

    model_config = ConfigDict(populate_by_name=True, extra="allow")
