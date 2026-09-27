"""MCP tools for UniFi Protect sirens (Protect v7 surface, Phase 5a)."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectSiren
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset
from ..utils.validators import coerce_bool, validate_confirmation


def _validate_siren_id(siren_id: str) -> str:
    siren_id = siren_id.strip()
    if not siren_id:
        raise ValidationError("siren_id is required")
    return siren_id


def _validate_volume(volume: int, label: str = "volume") -> int:
    if not 1 <= volume <= 100:
        raise ValidationError(f"{label} must be between 1 and 100")
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


async def list_protect_sirens(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect sirens."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("sirens"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    sirens = [ProtectSiren.model_validate(item).model_dump(by_alias=True) for item in data]
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)
    logger.info(sanitize_log_message(f"Listed {len(sirens)} Protect sirens"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": sirens,
    }


async def get_protect_siren(siren_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect siren."""
    logger = get_logger(__name__, settings.log_level)
    siren_id = _validate_siren_id(siren_id)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"sirens/{siren_id}"))

    siren = ProtectSiren.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect siren {siren_id}"))
    return siren.model_dump(by_alias=True)


async def update_protect_siren(
    siren_id: str,
    settings: Settings,
    name: str | None = None,
    volume: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect siren settings.

    Args:
        siren_id: Protect siren identifier
        settings: Application settings
        name: New display name
        volume: Siren volume (1-100)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated record as returned by the controller
    """
    validate_confirmation(confirm, "update Protect siren", dry_run)
    logger = get_logger(__name__, settings.log_level)
    siren_id = _validate_siren_id(siren_id)

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if volume is not None:
        payload["volume"] = _validate_volume(volume)

    if not payload:
        raise ValidationError("No updates provided: pass at least one of name, volume")

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_protect_siren",
            "siren_id": siren_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path(f"sirens/{siren_id}"),
            json_data=payload,
        )

    siren = ProtectSiren.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Updated Protect siren {siren_id}"))
    return siren.model_dump(by_alias=True)


async def play_protect_siren(
    siren_id: str,
    settings: Settings,
    duration: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Play a UniFi Protect siren.

    Args:
        siren_id: Protect siren identifier
        settings: Application settings
        duration: Duration of the siren activation in seconds
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "play Protect siren", dry_run)
    logger = get_logger(__name__, settings.log_level)
    siren_id = _validate_siren_id(siren_id)

    payload: dict[str, Any] = {}
    if duration is not None:
        if duration <= 0:
            raise ValidationError("duration must be a positive number of seconds")
        payload["duration"] = duration

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "play_protect_siren",
            "siren_id": siren_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path(f"sirens/{siren_id}/play"),
            json_data=payload or None,
        )

    logger.info(sanitize_log_message(f"Played Protect siren {siren_id}"))
    return {"success": True, "siren_id": siren_id, "response": _extract_item(response)}


async def stop_protect_siren(
    siren_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Stop a UniFi Protect siren.

    Args:
        siren_id: Protect siren identifier
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "stop Protect siren", dry_run)
    logger = get_logger(__name__, settings.log_level)
    siren_id = _validate_siren_id(siren_id)

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "stop_protect_siren",
            "siren_id": siren_id,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path(f"sirens/{siren_id}/stop")
        )

    logger.info(sanitize_log_message(f"Stopped Protect siren {siren_id}"))
    return {"success": True, "siren_id": siren_id, "response": _extract_item(response)}


async def test_protect_siren_sound(
    siren_id: str,
    settings: Settings,
    volume: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Test a UniFi Protect siren sound.

    Args:
        siren_id: Protect siren identifier
        settings: Application settings
        volume: Siren volume for the test (1-100)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "test Protect siren sound", dry_run)
    logger = get_logger(__name__, settings.log_level)
    siren_id = _validate_siren_id(siren_id)

    payload: dict[str, Any] = {}
    if volume is not None:
        payload["volume"] = _validate_volume(volume)

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "test_protect_siren_sound",
            "siren_id": siren_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path(f"sirens/{siren_id}/test-sound"),
            json_data=payload or None,
        )

    logger.info(sanitize_log_message(f"Tested Protect siren sound {siren_id}"))
    return {"success": True, "siren_id": siren_id, "response": _extract_item(response)}
