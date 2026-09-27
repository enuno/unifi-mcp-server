"""MCP tools for UniFi Protect relays (Protect v7 surface, Phase 5a)."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectRelay
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset
from ..utils.validators import coerce_bool, validate_confirmation


def _validate_relay_id(relay_id: str) -> str:
    relay_id = relay_id.strip()
    if not relay_id:
        raise ValidationError("relay_id is required")
    return relay_id


def _validate_output_id(output_id: str) -> str:
    output_id = output_id.strip()
    if not output_id:
        raise ValidationError("output_id is required")
    return output_id


def _validate_state(state: str) -> str:
    if state not in ("on", "off"):
        raise ValidationError("state must be 'on' or 'off'")
    return state


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


async def list_protect_relays(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect relays."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("relays"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    relays = [ProtectRelay.model_validate(item).model_dump(by_alias=True) for item in data]
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)
    logger.info(sanitize_log_message(f"Listed {len(relays)} Protect relays"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": relays,
    }


async def get_protect_relay(relay_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect relay."""
    logger = get_logger(__name__, settings.log_level)
    relay_id = _validate_relay_id(relay_id)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"relays/{relay_id}"))

    relay = ProtectRelay.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect relay {relay_id}"))
    return relay.model_dump(by_alias=True)


async def update_protect_relay(
    relay_id: str,
    settings: Settings,
    name: str | None = None,
    led_settings: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect relay settings.

    Args:
        relay_id: Protect relay identifier
        settings: Application settings
        name: New display name
        led_settings: Status LED settings (e.g. {"isEnabled": true})
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated record as returned by the controller
    """
    validate_confirmation(confirm, "update Protect relay", dry_run)
    logger = get_logger(__name__, settings.log_level)
    relay_id = _validate_relay_id(relay_id)

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if led_settings is not None:
        payload["ledSettings"] = led_settings

    if not payload:
        raise ValidationError("No updates provided: pass at least one of name, led_settings")

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_protect_relay",
            "relay_id": relay_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path(f"relays/{relay_id}"),
            json_data=payload,
        )

    relay = ProtectRelay.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Updated Protect relay {relay_id}"))
    return relay.model_dump(by_alias=True)


async def activate_protect_relay_output(
    relay_id: str,
    output_id: str,
    settings: Settings,
    state: str | None = None,
    pulse_duration: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Activate a UniFi Protect relay output.

    Args:
        relay_id: Protect relay identifier
        output_id: Relay output identifier
        settings: Application settings
        state: Desired output state ('on' or 'off'); toggles current state if omitted
        pulse_duration: Auto-off duration in milliseconds (only applies when state is 'on')
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "activate Protect relay output", dry_run)
    logger = get_logger(__name__, settings.log_level)
    relay_id = _validate_relay_id(relay_id)
    output_id = _validate_output_id(output_id)

    payload: dict[str, Any] = {}
    if state is not None:
        payload["state"] = _validate_state(state)
    if pulse_duration is not None:
        if pulse_duration < 0:
            raise ValidationError("pulse_duration must be a non-negative number of milliseconds")
        payload["pulseDuration"] = pulse_duration

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "activate_protect_relay_output",
            "relay_id": relay_id,
            "output_id": output_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path(f"relays/{relay_id}/outputs/{output_id}/activate"),
            json_data=payload or None,
        )

    logger.info(sanitize_log_message(f"Activated Protect relay {relay_id} output {output_id}"))
    return {
        "success": True,
        "relay_id": relay_id,
        "output_id": output_id,
        "response": _extract_item(response),
    }
