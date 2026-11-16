"""MCP tools for UniFi Protect events and subscriptions."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectAlarmWebhookResult, ProtectEventMessage, ProtectModelUpdateMessage
from ..utils import (
    ValidationError,
    get_logger,
    sanitize_log_message,
    validate_limit_offset,
    validate_path_segment,
)
from ..utils.tool_kind import read_tool, write_tool
from ..utils.validators import coerce_bool, validate_confirmation

# Defined once in protect_devices, which registers it as an MCP tool. Importing it
# here keeps the compatibility wrappers below working; register_module_tools skips
# imported functions, so the tool is not registered twice.
from .protect_devices import list_protect_device_updates


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


@read_tool
async def get_protect_subscribe_devices(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for device subscription messages."""
    return await list_protect_device_updates(settings, limit=limit, offset=offset)


@read_tool
async def get_protect_device_updates(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for device subscription messages."""
    return await list_protect_device_updates(settings, limit=limit, offset=offset)


@read_tool
async def list_protect_events(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Get Protect event messages."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path("subscribe/events"))

    events_data = _extract_collection(response)
    paginated = events_data[final_offset : final_offset + final_limit]
    events = [
        ProtectEventMessage.model_validate(item).model_dump(by_alias=True) for item in paginated
    ]
    total_count = len(events_data)
    logger.info(sanitize_log_message(f"Retrieved {len(events)} Protect event messages"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(events),
        "totalCount": total_count,
        "data": events,
    }


_ALLOWED_MODEL_KEYS = frozenset(
    {
        "nvr",
        "camera",
        "chime",
        "light",
        "viewer",
        "speaker",
        "bridge",
        "sensor",
        "siren",
        "fob",
        "relay",
        "aiProcessor",
        "aiPort",
        "linkStation",
        "event",
        "externalArmProfile",
    }
)


def _normalize_model_keys(model_keys: list[str] | str) -> list[str]:
    if isinstance(model_keys, str):
        keys = [part.strip() for part in model_keys.split(",") if part.strip()]
    else:
        keys = [str(part).strip() for part in model_keys if str(part).strip()]
    if not keys:
        raise ValidationError("model_keys is required")
    unknown = sorted({key for key in keys if key not in _ALLOWED_MODEL_KEYS})
    if unknown:
        raise ValidationError(
            "model_keys contains unsupported values "
            f"{unknown}; allowed: {sorted(_ALLOWED_MODEL_KEYS)}"
        )
    # Preserve order while dropping duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


@read_tool
async def list_protect_model_updates(
    settings: Settings,
    model_keys: list[str] | str,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Get Protect model update messages for selected model keys.

    Polls GET /v1/subscribe/updates (Protect 7.4.96). This is not the
    devices or events websocket. Pass model keys such as camera, event,
    or externalArmProfile.

    Args:
        settings: Application settings
        model_keys: One or more Protect model keys, or a comma-separated string
        limit: Maximum number of messages to return
        offset: Number of messages to skip
    """
    logger = get_logger(__name__, settings.log_level)
    keys = _normalize_model_keys(model_keys)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("subscribe/updates"),
            params={"modelKeys": ",".join(keys)},
        )

    updates_data = _extract_collection(response)
    paginated = updates_data[final_offset : final_offset + final_limit]
    updates = [
        ProtectModelUpdateMessage.model_validate(item).model_dump(by_alias=True)
        for item in paginated
    ]
    logger.info(sanitize_log_message(f"Retrieved {len(updates)} Protect model update messages"))
    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(updates),
        "totalCount": len(updates_data),
        "modelKeys": keys,
        "data": updates,
    }


@read_tool
async def get_protect_subscribe_events(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for Protect event messages."""
    return await list_protect_events(settings, limit=limit, offset=offset)


@read_tool
async def get_protect_event_messages(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for Protect event messages."""
    return await list_protect_events(settings, limit=limit, offset=offset)


@write_tool
async def send_protect_alarm_webhook(
    webhook_id: str,
    settings: Settings,
    payload: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Send a webhook to the Protect alarm manager.

    Args:
        webhook_id: Alarm webhook identifier
        settings: Application settings
        payload: Webhook payload to send
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The controller response to the webhook call
    """
    validate_confirmation(confirm, "send a Protect alarm webhook", dry_run)
    logger = get_logger(__name__, settings.log_level)
    webhook_id = validate_path_segment(webhook_id, "webhook_id")

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "send_protect_alarm_webhook",
            "webhook_id": webhook_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path(f"alarm-manager/webhook/{webhook_id}"),
            json_data=payload or {},
        )

    result = ProtectAlarmWebhookResult.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Sent Protect alarm webhook {webhook_id}"))
    return result.model_dump(by_alias=True)
