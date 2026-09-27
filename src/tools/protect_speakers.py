"""MCP tools for UniFi Protect speakers (Protect v7 surface, Phase 5a)."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectSpeaker
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset
from ..utils.validators import coerce_bool, validate_confirmation


def _validate_speaker_id(speaker_id: str) -> str:
    speaker_id = speaker_id.strip()
    if not speaker_id:
        raise ValidationError("speaker_id is required")
    return speaker_id


def _validate_volume(volume: int, label: str = "volume") -> int:
    if not 0 <= volume <= 100:
        raise ValidationError(f"{label} must be between 0 and 100")
    return volume


def _extract_collection(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        data = response.get("data", [])
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def _extract_item(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        data = response.get("data", response)
        if isinstance(data, dict):
            return data
        return response
    return {}


async def list_protect_speakers(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect speakers."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("speakers"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    speakers = [ProtectSpeaker.model_validate(item).model_dump(by_alias=True) for item in data]
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)
    logger.info(sanitize_log_message(f"Listed {len(speakers)} Protect speakers"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": speakers,
    }


async def get_protect_speaker(speaker_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect speaker."""
    logger = get_logger(__name__, settings.log_level)
    speaker_id = _validate_speaker_id(speaker_id)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"speakers/{speaker_id}"))

    speaker = ProtectSpeaker.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect speaker {speaker_id}"))
    return speaker.model_dump(by_alias=True)


async def update_protect_speaker(
    speaker_id: str,
    settings: Settings,
    name: str | None = None,
    volume: int | None = None,
    mic_volume: int | None = None,
    is_mic_enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect speaker settings.

    Args:
        speaker_id: Protect speaker identifier
        settings: Application settings
        name: New display name
        volume: Speaker volume (0-100)
        mic_volume: Microphone volume (0-100)
        is_mic_enabled: Whether the microphone is enabled
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated record as returned by the controller
    """
    validate_confirmation(confirm, "update Protect speaker", dry_run)
    logger = get_logger(__name__, settings.log_level)
    speaker_id = _validate_speaker_id(speaker_id)

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if volume is not None:
        payload["volume"] = _validate_volume(volume)
    if mic_volume is not None:
        payload["micVolume"] = _validate_volume(mic_volume, "mic_volume")
    if is_mic_enabled is not None:
        payload["isMicEnabled"] = is_mic_enabled

    if not payload:
        raise ValidationError(
            "No updates provided: pass at least one of name, volume, mic_volume, is_mic_enabled"
        )

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_protect_speaker",
            "speaker_id": speaker_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path(f"speakers/{speaker_id}"),
            json_data=payload,
        )

    speaker = ProtectSpeaker.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Updated Protect speaker {speaker_id}"))
    return speaker.model_dump(by_alias=True)


async def test_protect_speaker_sound(
    speaker_id: str,
    settings: Settings,
    volume: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Test a UniFi Protect speaker sound.

    Args:
        speaker_id: Protect speaker identifier
        settings: Application settings
        volume: Speaker volume for the test (0-100)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "test Protect speaker sound", dry_run)
    logger = get_logger(__name__, settings.log_level)
    speaker_id = _validate_speaker_id(speaker_id)

    payload: dict[str, Any] = {}
    if volume is not None:
        payload["volume"] = _validate_volume(volume)

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "test_protect_speaker_sound",
            "speaker_id": speaker_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path(f"speakers/{speaker_id}/test-sound"),
            json_data=payload or None,
        )

    logger.info(sanitize_log_message(f"Tested Protect speaker sound {speaker_id}"))
    return {"success": True, "speaker_id": speaker_id, "response": _extract_item(response)}
