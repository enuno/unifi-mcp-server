"""MCP tool for UniFi Protect POS transaction ingestion (Protect v7 surface)."""

from __future__ import annotations

import re
import time
from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectPosTransactionResult
from ..utils import ValidationError, get_logger, sanitize_log_message
from ..utils.validators import coerce_bool, validate_confirmation

_POS_TRANSACTION_TYPES = ("sale", "refund")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
# Timestamps must be within the last 24 hours and no more than 5 minutes in the future.
_MAX_PAST_MS = 24 * 60 * 60 * 1000
_MAX_FUTURE_MS = 5 * 60 * 1000


def _validate_camera_id(camera_id: str) -> str:
    camera_id = camera_id.strip()
    if not camera_id:
        raise ValidationError("camera_id is required")
    return camera_id


def _validate_location_id(location_id: str) -> str:
    location_id = location_id.strip()
    if not location_id:
        raise ValidationError("location_id is required")
    return location_id


def _validate_pos_type(tx_type: str) -> str:
    if tx_type not in _POS_TRANSACTION_TYPES:
        raise ValidationError(
            f"type must be one of {list(_POS_TRANSACTION_TYPES)}, got {tx_type!r}"
        )
    return tx_type


def _validate_amount(amount: float | int) -> float | int:
    if not isinstance(amount, int | float) or isinstance(amount, bool):
        raise ValidationError("amount must be a number greater than 0")
    if amount <= 0:
        raise ValidationError("amount must be a number greater than 0")
    return amount


def _validate_currency(currency: str) -> str:
    currency = currency.strip()
    if not _CURRENCY_RE.match(currency):
        raise ValidationError("currency must be an uppercase ISO 4217 3-letter code (e.g. USD)")
    return currency


def _validate_timestamp(timestamp: int) -> int:
    if not isinstance(timestamp, int) or isinstance(timestamp, bool):
        raise ValidationError("timestamp must be epoch milliseconds (integer)")
    now_ms = int(time.time() * 1000)
    if timestamp < now_ms - _MAX_PAST_MS:
        raise ValidationError("timestamp must be within the last 24 hours")
    if timestamp > now_ms + _MAX_FUTURE_MS:
        raise ValidationError("timestamp must not be more than 5 minutes in the future")
    return timestamp


def _extract_item(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        data = response.get("data", response)
        if isinstance(data, dict):
            return data
        return response
    return {}


async def ingest_pos_transaction(
    camera_id: str,
    settings: Settings,
    type: str,
    external_id: str,
    amount: float | int,
    location_id: str,
    location_name: str | None = None,
    currency: str | None = None,
    line_items: list[dict[str, Any]] | None = None,
    payment_types: list[str] | None = None,
    timestamp: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Ingest a POS transaction for a UniFi Protect camera.

    Args:
        camera_id: Protect camera identifier
        settings: Application settings
        type: Transaction type, "sale" or "refund" (required)
        external_id: Caller-supplied unique transaction id (required)
        amount: Transaction total amount, must be greater than 0 (required)
        location_id: Location or register identifier (required)
        location_name: Human-readable location or register name
        currency: Uppercase ISO 4217 3-letter currency code (e.g. USD)
        line_items: Purchased line items
        payment_types: Payment method names
        timestamp: Transaction time in epoch milliseconds; defaults to now.
            Must be within the last 24 hours and no more than 5 minutes in the future.
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The ingestion result as returned by the controller
    """
    validate_confirmation(confirm, "ingest POS transaction", dry_run)
    logger = get_logger(__name__, settings.log_level)
    camera_id = _validate_camera_id(camera_id)
    location_id = _validate_location_id(location_id)

    payload: dict[str, Any] = {
        "type": _validate_pos_type(type),
        "externalId": external_id,
        "amount": _validate_amount(amount),
        "location": {"id": location_id},
    }
    if location_name is not None:
        payload["location"]["name"] = location_name
    if currency is not None:
        payload["currency"] = _validate_currency(currency)
    if line_items is not None:
        payload["lineItems"] = line_items
    if payment_types is not None:
        payload["paymentTypes"] = payment_types
    payload["timestamp"] = (
        _validate_timestamp(timestamp) if timestamp is not None else int(time.time() * 1000)
    )

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "ingest_pos_transaction",
            "camera_id": camera_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path(f"pos/cameras/{camera_id}/transactions"),
            json_data=payload,
        )

    result = ProtectPosTransactionResult.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Ingested POS transaction for camera {camera_id}"))
    return result.model_dump(by_alias=True)
