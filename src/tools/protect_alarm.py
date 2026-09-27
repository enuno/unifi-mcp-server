"""MCP tools for UniFi Protect arm profiles and alarm state (Protect v7 surface)."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectArmProfile, ProtectArmSchedule
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset
from ..utils.validators import coerce_bool, validate_confirmation

_ALLOWED_ACTIVATION_DELAYS = (0, 60000, 300000, 600000)


def _validate_arm_profile_id(arm_profile_id: str) -> str:
    arm_profile_id = arm_profile_id.strip()
    if not arm_profile_id:
        raise ValidationError("arm_profile_id is required")
    return arm_profile_id


def _validate_activation_delay(activation_delay: int) -> int:
    if activation_delay not in _ALLOWED_ACTIVATION_DELAYS:
        raise ValidationError(
            "activation_delay must be one of "
            f"{_ALLOWED_ACTIVATION_DELAYS} milliseconds"
        )
    return activation_delay


def _serialize_schedules(schedules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        ProtectArmSchedule.model_validate(schedule).model_dump(by_alias=True)
        for schedule in schedules
    ]


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


async def list_protect_arm_profiles(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect arm profiles."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("arm-profiles"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    profiles = [ProtectArmProfile.model_validate(item).model_dump(by_alias=True) for item in data]
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)
    logger.info(sanitize_log_message(f"Listed {len(profiles)} Protect arm profiles"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": profiles,
    }


async def get_protect_arm_profile(arm_profile_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect arm profile.

    Note: GET on arm-profiles/{id} is not published in the v7.3.68 spec (the
    path exists there for PATCH/DELETE only). This is a convenience read and
    may 404 on some controllers; prefer list_protect_arm_profiles where the
    single fetch is not supported.
    """
    logger = get_logger(__name__, settings.log_level)
    arm_profile_id = _validate_arm_profile_id(arm_profile_id)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path(f"arm-profiles/{arm_profile_id}")
        )

    profile = ProtectArmProfile.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect arm profile {arm_profile_id}"))
    return profile.model_dump(by_alias=True)


async def create_protect_arm_profile(
    settings: Settings,
    name: str,
    automations: list[str],
    schedules: list[dict[str, Any]],
    record_everything: bool,
    activation_delay: int,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a UniFi Protect arm profile.

    Args:
        settings: Application settings
        name: Name of the arm profile
        automations: List of automation IDs associated with this arm profile
        schedules: List of arm schedules (mode, startCron, endCron)
        record_everything: Whether to record everything when this profile is active
        activation_delay: Activation delay in milliseconds (0, 60000, 300000, 600000)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The created record as returned by the controller
    """
    validate_confirmation(confirm, "create Protect arm profile", dry_run)
    logger = get_logger(__name__, settings.log_level)

    payload: dict[str, Any] = {
        "name": name,
        "automations": list(automations),
        "schedules": _serialize_schedules(schedules),
        "recordEverything": bool(record_everything),
        "activationDelay": _validate_activation_delay(activation_delay),
    }

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "create_protect_arm_profile",
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path("arm-profiles"),
            json_data=payload,
        )

    profile = ProtectArmProfile.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Created Protect arm profile {profile.id}"))
    return profile.model_dump(by_alias=True)


async def update_protect_arm_profile(
    arm_profile_id: str,
    settings: Settings,
    name: str | None = None,
    automations: list[str] | None = None,
    schedules: list[dict[str, Any]] | None = None,
    record_everything: bool | None = None,
    activation_delay: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update a UniFi Protect arm profile.

    Args:
        arm_profile_id: Protect arm profile identifier
        settings: Application settings
        name: New display name
        automations: List of automation IDs associated with this arm profile
        schedules: List of arm schedules (mode, startCron, endCron)
        record_everything: Whether to record everything when this profile is active
        activation_delay: Activation delay in milliseconds (0, 60000, 300000, 600000)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated record as returned by the controller
    """
    validate_confirmation(confirm, "update Protect arm profile", dry_run)
    logger = get_logger(__name__, settings.log_level)
    arm_profile_id = _validate_arm_profile_id(arm_profile_id)

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if automations is not None:
        payload["automations"] = list(automations)
    if schedules is not None:
        payload["schedules"] = _serialize_schedules(schedules)
    if record_everything is not None:
        payload["recordEverything"] = bool(record_everything)
    if activation_delay is not None:
        payload["activationDelay"] = _validate_activation_delay(activation_delay)

    if not payload:
        raise ValidationError(
            "No updates provided: pass at least one of name, automations, "
            "schedules, record_everything, activation_delay"
        )

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_protect_arm_profile",
            "arm_profile_id": arm_profile_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path(f"arm-profiles/{arm_profile_id}"),
            json_data=payload,
        )

    profile = ProtectArmProfile.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Updated Protect arm profile {arm_profile_id}"))
    return profile.model_dump(by_alias=True)


async def delete_protect_arm_profile(
    arm_profile_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Delete a UniFi Protect arm profile.

    Args:
        arm_profile_id: Protect arm profile identifier
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "delete Protect arm profile", dry_run)
    logger = get_logger(__name__, settings.log_level)
    arm_profile_id = _validate_arm_profile_id(arm_profile_id)

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "delete_protect_arm_profile",
            "arm_profile_id": arm_profile_id,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        await client.delete(
            settings.get_protect_integration_path(f"arm-profiles/{arm_profile_id}")
        )

    logger.info(sanitize_log_message(f"Deleted Protect arm profile {arm_profile_id}"))
    return {"success": True, "arm_profile_id": arm_profile_id}


async def set_current_protect_arm_profile(
    settings: Settings,
    arm_profile_id: str,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Set the current UniFi Protect arm profile.

    Args:
        settings: Application settings
        arm_profile_id: Protect arm profile identifier to make current
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "set current Protect arm profile", dry_run)
    logger = get_logger(__name__, settings.log_level)
    arm_profile_id = _validate_arm_profile_id(arm_profile_id)

    payload = {"armProfileId": arm_profile_id}

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "set_current_protect_arm_profile",
            "arm_profile_id": arm_profile_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path("arm-profiles/settings"),
            json_data=payload,
        )

    logger.info(sanitize_log_message(f"Set current Protect arm profile {arm_profile_id}"))
    return {"success": True, "arm_profile_id": arm_profile_id, "response": _extract_item(response)}


async def enable_protect_alarm(
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Enable the UniFi Protect alarm.

    Args:
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "enable Protect alarm", dry_run)
    logger = get_logger(__name__, settings.log_level)

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "enable_protect_alarm",
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path("arm-profiles/enable")
        )

    logger.info(sanitize_log_message("Enabled Protect alarm"))
    return {"success": True, "response": _extract_item(response)}


async def disable_protect_alarm(
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Disable the UniFi Protect alarm.

    Args:
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "disable Protect alarm", dry_run)
    logger = get_logger(__name__, settings.log_level)

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "disable_protect_alarm",
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path("arm-profiles/disable")
        )

    logger.info(sanitize_log_message("Disabled Protect alarm"))
    return {"success": True, "response": _extract_item(response)}
