"""UniFi Protect device models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProtectLightModeSettings(BaseModel):
    """Light behavior configuration."""

    mode: str | None = Field(None, description="Light mode")
    enable_at: str | None = Field(None, alias="enableAt", description="Activation timestamp")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectLightDeviceSettings(BaseModel):
    """Low-level light device configuration."""

    is_indicator_enabled: bool | None = Field(
        None, alias="isIndicatorEnabled", description="Whether indicator LED is enabled"
    )
    pir_duration: int | None = Field(None, alias="pirDuration", description="PIR duration")
    pir_sensitivity: int | None = Field(None, alias="pirSensitivity", description="PIR sensitivity")
    led_level: int | None = Field(None, alias="ledLevel", description="LED brightness level")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectSensorThresholdSettings(BaseModel):
    """Threshold configuration for a sensor sub-capability."""

    is_enabled: bool | None = Field(None, alias="isEnabled", description="Whether the setting is enabled")
    margin: int | None = Field(None, description="Threshold margin")
    sensitivity: int | None = Field(None, description="Sensitivity value")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectSensorSettings(BaseModel):
    """Sensor behavior configuration."""

    light_settings: ProtectSensorThresholdSettings | None = Field(
        None, alias="lightSettings", description="Light sensing configuration"
    )
    humidity_settings: ProtectSensorThresholdSettings | None = Field(
        None, alias="humiditySettings", description="Humidity sensing configuration"
    )
    temperature_settings: ProtectSensorThresholdSettings | None = Field(
        None, alias="temperatureSettings", description="Temperature sensing configuration"
    )
    motion_settings: ProtectSensorThresholdSettings | None = Field(
        None, alias="motionSettings", description="Motion sensing configuration"
    )
    alarm_settings: ProtectSensorThresholdSettings | None = Field(
        None, alias="alarmSettings", description="Alarm configuration"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectChimeRingSetting(BaseModel):
    """Per-camera chime ring setting."""

    camera_id: str | None = Field(None, alias="cameraId", description="Camera identifier")
    repeat_times: int | None = Field(None, alias="repeatTimes", description="Repeat count")
    ringtone_id: str | None = Field(None, alias="ringtoneId", description="Ringtone identifier")
    volume: int | None = Field(None, description="Volume level")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectDevice(BaseModel):
    """Generic UniFi Protect device record."""

    id: str | None = Field(None, description="Device identifier")
    name: str | None = Field(None, description="Device name")
    model: str | None = Field(None, description="Device model")
    type: str | None = Field(None, description="Device type")
    state: str | int | None = Field(None, description="Device state")
    mac: str | None = Field(None, description="Device MAC address")
    firmware_version: str | None = Field(None, alias="firmwareVersion", description="Firmware version")
    last_seen: str | None = Field(None, alias="lastSeen", description="Last seen timestamp")
    is_online: bool | None = Field(None, alias="isOnline", description="Whether device is online")
    is_adopted: bool | None = Field(None, alias="isAdopted", description="Whether device is adopted")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectLight(ProtectDevice):
    """UniFi Protect light device."""

    is_light_force_enabled: bool | None = Field(
        None, alias="isLightForceEnabled", description="Whether forced light is enabled"
    )
    light_mode_settings: ProtectLightModeSettings | None = Field(
        None, alias="lightModeSettings", description="Light mode settings"
    )
    light_device_settings: ProtectLightDeviceSettings | None = Field(
        None, alias="lightDeviceSettings", description="Light device settings"
    )


class ProtectSensor(ProtectDevice):
    """UniFi Protect sensor device."""

    light_settings: ProtectSensorThresholdSettings | None = Field(
        None, alias="lightSettings", description="Light sensing configuration"
    )
    humidity_settings: ProtectSensorThresholdSettings | None = Field(
        None, alias="humiditySettings", description="Humidity sensing configuration"
    )
    temperature_settings: ProtectSensorThresholdSettings | None = Field(
        None, alias="temperatureSettings", description="Temperature sensing configuration"
    )
    motion_settings: ProtectSensorThresholdSettings | None = Field(
        None, alias="motionSettings", description="Motion sensing configuration"
    )
    alarm_settings: ProtectSensorThresholdSettings | None = Field(
        None, alias="alarmSettings", description="Alarm configuration"
    )


class ProtectChime(ProtectDevice):
    """UniFi Protect chime device."""

    camera_ids: list[str] | None = Field(None, alias="cameraIds", description="Bound camera IDs")
    ring_settings: list[ProtectChimeRingSetting] | None = Field(
        None, alias="ringSettings", description="Configured ring settings"
    )
