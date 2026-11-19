"""UniFi Protect NVR model."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProtectNvrFeatureFlags(BaseModel):
    """NVR feature flags from Protect 7.4.96."""

    use_external_alarm_manager: bool | None = Field(
        None,
        alias="useExternalAlarmManager",
        description=(
            "Whether UniFi OS runs the external Alarm Manager instead of Protect. "
            "When true, use the external arm-profile tools; when false, use the "
            "local arm-profile family."
        ),
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectNVR(BaseModel):
    """UniFi Protect NVR details."""

    id: str = Field(..., description="NVR identifier")
    name: str = Field(..., description="NVR name")
    model: str | None = Field(None, validation_alias="type", description="NVR model name")
    state: str | None = Field(None, description="NVR state")
    host: str | None = Field(None, description="NVR host")
    version: str | None = Field(None, alias="firmwareVersion", description="Firmware version")
    uptime: int | None = Field(None, description="Uptime in seconds")
    feature_flags: ProtectNvrFeatureFlags | None = Field(
        None, alias="featureFlags", description="NVR feature flags"
    )
    arm_mode: dict[str, Any] | None = Field(
        None,
        alias="armMode",
        description="Local Alarm Manager arm state when useExternalAlarmManager is false",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")
