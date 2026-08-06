"""UniFi Protect camera model."""

from pydantic import BaseModel, ConfigDict, Field


class ProtectCamera(BaseModel):
    """UniFi Protect camera details."""

    id: str = Field(..., description="Camera identifier")
    name: str = Field(..., description="Camera name")
    model: str | None = Field(None, description="Camera model")
    type: str | None = Field(None, description="Camera type")
    state: str | None = Field(None, description="Camera state")
    is_recording: bool | None = Field(
        None, alias="isRecording", description="Whether recording is enabled"
    )
    has_speaker: bool | None = Field(
        None, alias="hasSpeaker", description="Whether speaker is available"
    )
    has_mic: bool | None = Field(
        None, alias="hasMic", description="Whether microphone is available"
    )
    can_ptz: bool | None = Field(
        None, alias="canPtz", description="Whether PTZ control is supported"
    )
    mac: str | None = Field(None, description="Camera MAC address")
    firmware_version: str | None = Field(
        None, alias="firmwareVersion", description="Camera firmware version"
    )

    model_config = ConfigDict(populate_by_name=True)
