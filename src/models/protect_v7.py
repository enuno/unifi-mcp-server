"""UniFi Protect v7 device and alarm models (Phase 5a).

Slim permissive models for the Protect v7.3.68 surface: sirens, speakers,
fobs, relays, bridges, link stations, alarm hubs, arm profiles, users, and
ULP (UniFi Identity) users. All models allow extra fields — the Protect API
returns far more than we model, and unknown fields must not break parsing.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _ProtectV7Base(BaseModel):
    """Common fields shared by all Protect v7 device records."""

    id: str | None = Field(None, description="Record identifier")
    name: str | None = Field(None, description="Display name")
    model_key: str | None = Field(None, alias="modelKey", description="Protect model key")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectSiren(_ProtectV7Base):
    """UniFi Protect siren."""

    volume: int | None = Field(None, description="Siren volume (1-100)")


class ProtectSpeaker(_ProtectV7Base):
    """UniFi Protect speaker."""

    volume: int | None = Field(None, description="Speaker volume (0-100)")
    mic_volume: int | None = Field(None, alias="micVolume", description="Mic volume (0-100)")
    is_mic_enabled: bool | None = Field(
        None, alias="isMicEnabled", description="Whether the microphone is enabled"
    )


class ProtectFob(_ProtectV7Base):
    """UniFi Protect key fob."""


class ProtectRelay(_ProtectV7Base):
    """UniFi Protect relay."""


class ProtectBridge(_ProtectV7Base):
    """UniFi Protect bridge."""


class ProtectLinkStation(_ProtectV7Base):
    """UniFi Protect link station."""


class ProtectAlarmHub(_ProtectV7Base):
    """UniFi Protect alarm hub."""


class ProtectArmSchedule(BaseModel):
    """Arm schedule entry within an arm profile."""

    mode: str | None = Field(None, description="Arm mode for the schedule window")
    start_cron: str | None = Field(
        None, alias="startCron", description="Cron expression for window start"
    )
    end_cron: str | None = Field(
        None, alias="endCron", description="Cron expression for window end"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProtectArmProfile(_ProtectV7Base):
    """UniFi Protect arm profile."""

    automations: list[str] | None = Field(
        None, description="Automation IDs associated with this profile"
    )
    schedules: list[ProtectArmSchedule] | None = Field(None, description="Arm schedules")
    record_everything: bool | None = Field(
        None, alias="recordEverything", description="Record everything while armed"
    )
    activation_delay: int | None = Field(
        None, alias="activationDelay", description="Activation delay in milliseconds"
    )


class ProtectUser(_ProtectV7Base):
    """UniFi Protect user."""


class ProtectUlpUser(_ProtectV7Base):
    """UniFi Identity (ULP) user."""


class ProtectPosTransactionResult(BaseModel):
    """Result of ingesting a POS transaction."""

    accepted: bool | None = Field(None, description="Whether the transaction was accepted")
    external_id: str | None = Field(
        None, alias="externalId", description="Caller-supplied transaction id"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


# Reusable type alias for device categories that share the CRUD+action shape.
ProtectV7DeviceModel = (
    ProtectSiren
    | ProtectSpeaker
    | ProtectFob
    | ProtectRelay
    | ProtectBridge
    | ProtectLinkStation
    | ProtectAlarmHub
)

__all__ = [
    "ProtectAlarmHub",
    "ProtectArmProfile",
    "ProtectArmSchedule",
    "ProtectBridge",
    "ProtectFob",
    "ProtectLinkStation",
    "ProtectPosTransactionResult",
    "ProtectRelay",
    "ProtectSiren",
    "ProtectSpeaker",
    "ProtectUlpUser",
    "ProtectUser",
    "ProtectV7DeviceModel",
]
