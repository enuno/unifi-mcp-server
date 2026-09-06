"""Hotspot voucher management tools.

Every route here is the documented Integration v1 hotspot surface,
``/v1/sites/{siteId}/hotspot/vouchers`` (docs/UNIFI_API.md). An earlier
version called ``/sites/{siteId}/vouchers`` — a path no controller serves —
so none of these tools had ever succeeded (issue #108, item B1).
"""

from typing import Any

from ..api.client import UniFiClient
from ..config import Settings
from ..models import Voucher
from ..utils import (
    ValidationError,
    audit_action,
    get_logger,
    sanitize_log_message,
    validate_confirmation,
    validate_site_id,
)

logger = get_logger(__name__)


def _voucher_items(response: Any) -> list[dict]:
    """Unwrap a voucher response into a list of voucher objects.

    Generation replies with the batch nested under a ``vouchers`` key —
    ``{"vouchers": [...]}``, observed live on Network 10.5.67 — while reads
    return the objects directly. Handle both, plus a ``data`` envelope.
    """
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        data = response.get("data", response)
        if isinstance(data, dict) and isinstance(data.get("vouchers"), list):
            data = data["vouchers"]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict) and data:
            return [data]
    return []


async def list_vouchers(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
    filter_expr: str | None = None,
) -> list[dict]:
    """List all hotspot vouchers for a site.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of results (API default 100, max 1000)
        offset: Starting position
        filter_expr: Filter expression

    Returns:
        List of vouchers
    """
    site_id = validate_site_id(site_id)
    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Listing vouchers for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if filter_expr:
            params["filter"] = filter_expr

        response = await client.get(
            settings.get_integration_path(f"sites/{site_id}/hotspot/vouchers"), params=params
        )

        return [
            Voucher(**voucher).model_dump(exclude_none=True) for voucher in _voucher_items(response)
        ]


async def get_voucher(site_id: str, voucher_id: str, settings: Settings) -> dict:
    """Get details for a specific voucher.

    Args:
        site_id: Site identifier
        voucher_id: Voucher identifier (UUID)
        settings: Application settings

    Returns:
        Voucher details
    """
    site_id = validate_site_id(site_id)
    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Getting voucher {voucher_id} for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(
            settings.get_integration_path(f"sites/{site_id}/hotspot/vouchers/{voucher_id}")
        )
        items = _voucher_items(response)
        data = items[0] if items else {}

        return Voucher(**data).model_dump(exclude_none=True)


async def create_vouchers(
    site_id: str,
    name: str,
    time_limit_minutes: int,
    settings: Settings,
    count: int = 1,
    authorized_guest_limit: int | None = None,
    data_usage_limit_mb: int | None = None,
    rx_rate_limit_kbps: int | None = None,
    tx_rate_limit_kbps: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create new hotspot vouchers.

    The parameters mirror the documented request body: ``name`` (a note
    duplicated across the batch) and ``time_limit_minutes`` are the two
    fields the API requires. The previous signature sent ``duration`` in
    seconds plus qos_* limits — a body the endpoint never accepted.

    Args:
        site_id: Site identifier
        name: Voucher note, duplicated across all generated vouchers
        time_limit_minutes: Access duration in minutes (1-1000000)
        settings: Application settings
        count: Number of vouchers to generate (1-1000, default 1)
        authorized_guest_limit: Max guests per voucher (>= 1)
        data_usage_limit_mb: Data usage limit in megabytes (1-1048576)
        rx_rate_limit_kbps: Download rate limit in kbps (2-100000)
        tx_rate_limit_kbps: Upload rate limit in kbps (2-100000)
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created vouchers, including their access codes
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "create vouchers", dry_run)

    if not name:
        raise ValidationError("Voucher name is required")
    if not 1 <= time_limit_minutes <= 1_000_000:
        raise ValidationError("time_limit_minutes must be between 1 and 1000000")
    if not 1 <= count <= 1000:
        raise ValidationError("count must be between 1 and 1000")
    if authorized_guest_limit is not None and authorized_guest_limit < 1:
        raise ValidationError("authorized_guest_limit must be at least 1")
    if data_usage_limit_mb is not None and not 1 <= data_usage_limit_mb <= 1_048_576:
        raise ValidationError("data_usage_limit_mb must be between 1 and 1048576")
    for label, value in (
        ("rx_rate_limit_kbps", rx_rate_limit_kbps),
        ("tx_rate_limit_kbps", tx_rate_limit_kbps),
    ):
        if value is not None and not 2 <= value <= 100_000:
            raise ValidationError(f"{label} must be between 2 and 100000")

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Creating {count} vouchers for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        payload: dict[str, Any] = {
            "count": count,
            "name": name,
            "timeLimitMinutes": time_limit_minutes,
        }

        if authorized_guest_limit is not None:
            payload["authorizedGuestLimit"] = authorized_guest_limit
        if data_usage_limit_mb is not None:
            payload["dataUsageLimitMBytes"] = data_usage_limit_mb
        if rx_rate_limit_kbps is not None:
            payload["rxRateLimitKbps"] = rx_rate_limit_kbps
        if tx_rate_limit_kbps is not None:
            payload["txRateLimitKbps"] = tx_rate_limit_kbps

        if dry_run:
            logger.info(
                sanitize_log_message(f"[DRY RUN] Would create {count} vouchers for site {site_id}")
            )
            return {"dry_run": True, "payload": payload}

        response = await client.post(
            settings.get_integration_path(f"sites/{site_id}/hotspot/vouchers"), json_data=payload
        )
        vouchers = [
            Voucher(**voucher).model_dump(exclude_none=True) for voucher in _voucher_items(response)
        ]

        # Audit the action
        await audit_action(
            settings,
            action_type="create_vouchers",
            resource_type="voucher",
            resource_id="bulk",
            site_id=site_id,
            details={"count": count, "time_limit_minutes": time_limit_minutes},
        )

        return {"success": True, "count": count, "vouchers": vouchers}


async def delete_voucher(
    site_id: str,
    voucher_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Delete a specific voucher.

    Args:
        site_id: Site identifier
        voucher_id: Voucher identifier (UUID)
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion status
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "delete voucher", dry_run)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Deleting voucher {voucher_id} for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(sanitize_log_message(f"[DRY RUN] Would delete voucher {voucher_id}"))
            return {"dry_run": True, "voucher_id": voucher_id}

        await client.delete(
            settings.get_integration_path(f"sites/{site_id}/hotspot/vouchers/{voucher_id}")
        )

        # Audit the action
        await audit_action(
            settings,
            action_type="delete_voucher",
            resource_type="voucher",
            resource_id=voucher_id,
            site_id=site_id,
            details={},
        )

        return {"success": True, "message": f"Voucher {voucher_id} deleted successfully"}


async def bulk_delete_vouchers(
    site_id: str,
    filter_expr: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Bulk delete vouchers using a filter expression.

    Args:
        site_id: Site identifier
        filter_expr: Filter expression selecting the vouchers (required by
            the API — there is no delete-all)
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion status with the controller's reported count
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "bulk delete vouchers", dry_run)

    if not filter_expr:
        raise ValidationError("A filter expression is required for bulk deletion")

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Bulk deleting vouchers for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(
                sanitize_log_message(f"[DRY RUN] Would bulk delete vouchers for site {site_id}")
            )
            return {"dry_run": True, "filter": filter_expr}

        params = {"filter": filter_expr}
        response = await client.delete(
            settings.get_integration_path(f"sites/{site_id}/hotspot/vouchers"), params=params
        )

        # Audit the action
        await audit_action(
            settings,
            action_type="bulk_delete_vouchers",
            resource_type="voucher",
            resource_id="bulk",
            site_id=site_id,
            details={"filter": filter_expr},
        )

        # The documented response is {"vouchersDeleted": N}.
        deleted = response.get("vouchersDeleted") if isinstance(response, dict) else None
        return {
            "success": True,
            "message": "Vouchers deleted successfully",
            "deleted_count": deleted if isinstance(deleted, int) else 0,
        }
