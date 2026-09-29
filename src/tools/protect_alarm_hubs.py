"""MCP tools for UniFi Protect alarm hubs (Protect v7 surface, Phase 5a)."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectAlarmHub
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset
from ..utils.validators import coerce_bool, validate_confirmation


def _validate_alarm_hub_id(alarm_hub_id: str) -> str:
    alarm_hub_id = alarm_hub_id.strip()
    if not alarm_hub_id:
        raise ValidationError("alarm_hub_id is required")
    return alarm_hub_id


def _validate_output_id(output_id: str) -> str:
    output_id = output_id.strip()
    if not output_id:
        raise ValidationError("output_id is required")
    return output_id


def _validate_delay_duration(value: int, label: str) -> int:
    if value < 0:
        raise ValidationError(f"{label} must be greater than or equal to 0")
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


async def list_protect_alarm_hubs(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect alarm hubs."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("alarm-hubs"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    alarm_hubs = [ProtectAlarmHub.model_validate(item).model_dump(by_alias=True) for item in data]
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)
    logger.info(sanitize_log_message(f"Listed {len(alarm_hubs)} Protect alarm hubs"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": alarm_hubs,
    }


async def get_protect_alarm_hub(alarm_hub_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect alarm hub."""
    logger = get_logger(__name__, settings.log_level)
    alarm_hub_id = _validate_alarm_hub_id(alarm_hub_id)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path(f"alarm-hubs/{alarm_hub_id}")
        )

    alarm_hub = ProtectAlarmHub.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect alarm hub {alarm_hub_id}"))
    return alarm_hub.model_dump(by_alias=True)


async def update_protect_alarm_hub(
    alarm_hub_id: str,
    settings: Settings,
    name: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect alarm hub settings.

    Args:
        alarm_hub_id: Protect alarm hub identifier
        settings: Application settings
        name: New display name
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated record as returned by the controller
    """
    validate_confirmation(confirm, "update Protect alarm hub", dry_run)
    logger = get_logger(__name__, settings.log_level)
    alarm_hub_id = _validate_alarm_hub_id(alarm_hub_id)

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name

    if not payload:
        raise ValidationError("No updates provided: pass at least one of name")

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_protect_alarm_hub",
            "alarm_hub_id": alarm_hub_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path(f"alarm-hubs/{alarm_hub_id}"),
            json_data=payload,
        )

    alarm_hub = ProtectAlarmHub.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Updated Protect alarm hub {alarm_hub_id}"))
    return alarm_hub.model_dump(by_alias=True)


async def trigger_protect_alarm_hub_output(
    alarm_hub_id: str,
    output_id: str,
    settings: Settings,
    enable: bool | None = None,
    delay: int | None = None,
    duration: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Trigger a UniFi Protect alarm hub output.

    Args:
        alarm_hub_id: Protect alarm hub identifier
        output_id: Alarm hub output identifier
        settings: Application settings
        enable: True to turn on, false to turn off. If omitted, toggles current state
        delay: Delay in milliseconds before the output activates
        duration: Duration in milliseconds to keep the output active. 0 means
            indefinite until manually turned off
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "trigger Protect alarm hub output", dry_run)
    logger = get_logger(__name__, settings.log_level)
    alarm_hub_id = _validate_alarm_hub_id(alarm_hub_id)
    output_id = _validate_output_id(output_id)

    payload: dict[str, Any] = {}
    if enable is not None:
        payload["enable"] = enable
    if delay is not None:
        payload["delay"] = _validate_delay_duration(delay, "delay")
    if duration is not None:
        payload["duration"] = _validate_delay_duration(duration, "duration")

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "trigger_protect_alarm_hub_output",
            "alarm_hub_id": alarm_hub_id,
            "output_id": output_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path(
                f"alarm-hubs/{alarm_hub_id}/outputs/{output_id}/trigger"
            ),
            json_data=payload or None,
        )

    logger.info(
        sanitize_log_message(f"Triggered output {output_id} on Protect alarm hub {alarm_hub_id}")
    )
    return {
        "success": True,
        "alarm_hub_id": alarm_hub_id,
        "output_id": output_id,
        "response": _extract_item(response),
    }
