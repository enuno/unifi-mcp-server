"""MCP tools for UniFi Protect events and subscriptions."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectAlarmWebhookResult, ProtectDeviceUpdateMessage, ProtectEventMessage
from ..utils import (
    ValidationError,
    audit_on_failure,
    coerce_bool,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_confirmation,
    validate_limit_offset,
)


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


async def list_protect_device_updates(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Get Protect device update messages."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path("subscribe/devices"))

    updates_data = _extract_collection(response)
    paginated = updates_data[final_offset : final_offset + final_limit]
    updates = [
        ProtectDeviceUpdateMessage.model_validate(item).model_dump(by_alias=True)
        for item in paginated
    ]
    total_count = len(updates_data)
    logger.info(sanitize_log_message(f"Retrieved {len(updates)} Protect device update messages"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(updates),
        "totalCount": total_count,
        "data": updates,
    }


async def get_protect_subscribe_devices(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for device subscription messages."""
    return await list_protect_device_updates(settings, limit=limit, offset=offset)


async def get_protect_device_updates(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for device subscription messages."""
    return await list_protect_device_updates(settings, limit=limit, offset=offset)


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


async def get_protect_subscribe_events(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for Protect event messages."""
    return await list_protect_events(settings, limit=limit, offset=offset)


async def get_protect_event_messages(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for Protect event messages."""
    return await list_protect_events(settings, limit=limit, offset=offset)


async def send_protect_alarm_webhook(
    webhook_id: str,
    settings: Settings,
    payload: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Send a webhook to the Protect alarm manager."""
    logger = get_logger(__name__, settings.log_level)
    webhook_id = webhook_id.strip()
    if not webhook_id:
        raise ValidationError("webhook_id is required")
    validate_confirmation(confirm, "send Protect alarm webhook", dry_run)
    parameters = {
        "webhook_id": webhook_id,
        "payload_fields": sorted((payload or {}).keys()),
    }

    if coerce_bool(dry_run):
        log_audit(
            operation="send_protect_alarm_webhook",
            parameters=parameters,
            result="dry_run",
            dry_run=True,
        )
        return {"dry_run": True, "would_send": webhook_id, "payload": payload or {}}

    with audit_on_failure("send_protect_alarm_webhook", parameters):
        async with ProtectClient(settings) as client:
            await client.authenticate()
            response = await client.post(
                settings.get_protect_integration_path(f"alarm-manager/webhook/{webhook_id}"),
                json_data=payload or {},
            )

        result = ProtectAlarmWebhookResult.model_validate(_extract_item(response))
        log_audit(
            operation="send_protect_alarm_webhook",
            parameters=parameters,
            result="success",
        )
        logger.info(sanitize_log_message(f"Sent Protect alarm webhook {webhook_id}"))
        return result.model_dump(by_alias=True)
