"""UniFi Protect NVR model."""

from pydantic import BaseModel, ConfigDict, Field


class ProtectNVR(BaseModel):
    """UniFi Protect NVR details."""

    id: str = Field(..., description="NVR identifier")
    name: str = Field(..., description="NVR name")
    model: str | None = Field(None, description="NVR model")
    state: str | None = Field(None, description="NVR state")
    host: str | None = Field(None, description="NVR host")
    version: str | None = Field(None, alias="firmwareVersion", description="Firmware version")
    uptime: int | None = Field(None, description="Uptime in seconds")

    model_config = ConfigDict(populate_by_name=True)
