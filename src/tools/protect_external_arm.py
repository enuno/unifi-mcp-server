"""MCP tools for UniFi Protect external arm profiles (Protect 7.4.96).

These are the external Alarm Manager profiles at
``/v1/external/arm-profiles``. They are a different surface from the local
arm-profile family in ``protect_alarm.py``. Read
``nvr.featureFlags.useExternalAlarmManager`` first to know which family
applies.
"""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectExternalArmProfile
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset
from ..utils.tool_kind import read_tool, write_tool
from ..utils.validators import coerce_bool, validate_confirmation

_PIN_KEYS = frozenset({"pin", "pin_code", "pincode", "pincodes"})
_MAX_DELAY_SECONDS = 3600


def _validate_profile_id(arm_profile_id: str) -> str:
    arm_profile_id = arm_profile_id.strip()
    if not arm_profile_id:
        raise ValidationError("arm_profile_id is required")
    return arm_profile_id


def _validate_delay(delay: int, label: str) -> int:
    if not 0 <= delay <= _MAX_DELAY_SECONDS:
        raise ValidationError(f"{label} must be between 0 and {_MAX_DELAY_SECONDS} seconds")
    return delay


def _strip_pin_fields(value: Any) -> Any:
    """Drop PIN-bearing keys from nested mappings so they never leave the tool."""
    if isinstance(value, dict):
        return {
            key: _strip_pin_fields(item)
            for key, item in value.items()
            if key.casefold() not in _PIN_KEYS
        }
    if isinstance(value, list):
        return [_strip_pin_fields(item) for item in value]
    return value


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


def _serialize_profile(item: dict[str, Any]) -> dict[str, Any]:
    cleaned = _strip_pin_fields(item)
    if not isinstance(cleaned, dict):
        return {}
    return ProtectExternalArmProfile.model_validate(cleaned).model_dump(by_alias=True)


@read_tool
async def list_protect_external_arm_profiles(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect external Alarm Manager arm profiles.

    Use when ``nvr.featureFlags.useExternalAlarmManager`` is true. These
    profiles are not the local ``arm-profiles`` family.

    Args:
        settings: Application settings
        limit: Maximum number of profiles to return
        offset: Number of profiles to skip
    """
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("external/arm-profiles"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    profiles = [_serialize_profile(item) for item in data]
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)
    logger.info(sanitize_log_message(f"Listed {len(profiles)} Protect external arm profiles"))
    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": profiles,
    }


@read_tool
async def get_protect_external_arm_profile(
    arm_profile_id: str, settings: Settings
) -> dict[str, Any]:
    """Get a single UniFi Protect external arm profile.

    Args:
        arm_profile_id: External arm profile identifier
        settings: Application settings
    """
    logger = get_logger(__name__, settings.log_level)
    arm_profile_id = _validate_profile_id(arm_profile_id)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path(f"external/arm-profiles/{arm_profile_id}")
        )

    profile = _serialize_profile(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect external arm profile {arm_profile_id}"))
    return profile


@write_tool
async def create_protect_external_arm_profile(
    settings: Settings,
    title: str,
    activation_delay: int | None = None,
    deactivation_delay: int | None = None,
    schedule: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create an external Alarm Manager arm profile.

    Args:
        settings: Application settings
        title: Profile title
        activation_delay: Arm delay in seconds (0-3600)
        deactivation_delay: Disarm delay in seconds (0-3600)
        schedule: Optional weekly schedule object from the Protect 7.4.96 spec
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "create Protect external arm profile", dry_run)
    logger = get_logger(__name__, settings.log_level)
    title = title.strip()
    if not title:
        raise ValidationError("title is required")

    payload: dict[str, Any] = {"title": title}
    if activation_delay is not None:
        payload["activation_delay"] = _validate_delay(activation_delay, "activation_delay")
    if deactivation_delay is not None:
        payload["deactivation_delay"] = _validate_delay(deactivation_delay, "deactivation_delay")
    if schedule is not None:
        payload["schedule"] = schedule

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "create_protect_external_arm_profile",
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path("external/arm-profiles"),
            json_data=payload,
        )

    profile = _serialize_profile(_extract_item(response))
    logger.info(sanitize_log_message("Created Protect external arm profile"))
    return profile


@write_tool
async def update_protect_external_arm_profile(
    arm_profile_id: str,
    settings: Settings,
    title: str | None = None,
    activation_delay: int | None = None,
    deactivation_delay: int | None = None,
    schedule: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an external Alarm Manager arm profile.

    Omitted fields are left unchanged. PIN values are never accepted.

    Args:
        arm_profile_id: External arm profile identifier
        settings: Application settings
        title: New title (cannot be cleared)
        activation_delay: Arm delay in seconds (0-3600)
        deactivation_delay: Disarm delay in seconds (0-3600)
        schedule: Replacement weekly schedule
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "update Protect external arm profile", dry_run)
    logger = get_logger(__name__, settings.log_level)
    arm_profile_id = _validate_profile_id(arm_profile_id)

    payload: dict[str, Any] = {}
    if title is not None:
        title = title.strip()
        if not title:
            raise ValidationError("title cannot be empty")
        payload["title"] = title
    if activation_delay is not None:
        payload["activation_delay"] = _validate_delay(activation_delay, "activation_delay")
    if deactivation_delay is not None:
        payload["deactivation_delay"] = _validate_delay(deactivation_delay, "deactivation_delay")
    if schedule is not None:
        payload["schedule"] = schedule

    if not payload:
        raise ValidationError(
            "No updates provided: pass at least one of title, activation_delay, "
            "deactivation_delay, schedule"
        )

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_protect_external_arm_profile",
            "arm_profile_id": arm_profile_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path(f"external/arm-profiles/{arm_profile_id}"),
            json_data=payload,
        )

    profile = _serialize_profile(_extract_item(response))
    logger.info(sanitize_log_message(f"Updated Protect external arm profile {arm_profile_id}"))
    return profile


@write_tool
async def delete_protect_external_arm_profile(
    arm_profile_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Delete an external Alarm Manager arm profile.

    Args:
        arm_profile_id: External arm profile identifier
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "delete Protect external arm profile", dry_run)
    logger = get_logger(__name__, settings.log_level)
    arm_profile_id = _validate_profile_id(arm_profile_id)

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "delete_protect_external_arm_profile",
            "arm_profile_id": arm_profile_id,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        await client.delete(
            settings.get_protect_integration_path(f"external/arm-profiles/{arm_profile_id}")
        )

    logger.info(sanitize_log_message(f"Deleted Protect external arm profile {arm_profile_id}"))
    return {"success": True, "arm_profile_id": arm_profile_id}


@write_tool
async def arm_protect_external_arm_profile(
    arm_profile_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Arm an external Alarm Manager profile.

    This changes the live security posture of the space. Confirm the
    target profile first. Mock-tested only; not live-verified.

    Args:
        arm_profile_id: External arm profile identifier
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "arm Protect external arm profile", dry_run)
    logger = get_logger(__name__, settings.log_level)
    arm_profile_id = _validate_profile_id(arm_profile_id)

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "arm_protect_external_arm_profile",
            "arm_profile_id": arm_profile_id,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path(
                f"external/arm-profiles/{arm_profile_id}/actions/arm"
            )
        )

    logger.info(sanitize_log_message(f"Armed Protect external arm profile {arm_profile_id}"))
    return {
        "success": True,
        "arm_profile_id": arm_profile_id,
        "response": _serialize_profile(_extract_item(response)) if response else {},
    }


@write_tool
async def disarm_protect_external_arm_profile(
    arm_profile_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Disarm an external Alarm Manager profile.

    This changes the live security posture of the space. Mock-tested only;
    not live-verified.

    Args:
        arm_profile_id: External arm profile identifier
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "disarm Protect external arm profile", dry_run)
    logger = get_logger(__name__, settings.log_level)
    arm_profile_id = _validate_profile_id(arm_profile_id)

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "disarm_protect_external_arm_profile",
            "arm_profile_id": arm_profile_id,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path(
                f"external/arm-profiles/{arm_profile_id}/actions/disarm"
            )
        )

    logger.info(sanitize_log_message(f"Disarmed Protect external arm profile {arm_profile_id}"))
    return {
        "success": True,
        "arm_profile_id": arm_profile_id,
        "response": _serialize_profile(_extract_item(response)) if response else {},
    }
