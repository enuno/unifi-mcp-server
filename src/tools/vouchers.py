"""Hotspot voucher management tools."""

from ..api.client import UniFiClient
from ..config import Settings
from ..models import Voucher
from ..utils import audit_action, get_logger, validate_confirmation

logger = get_logger(__name__)


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
        limit: Maximum number of results
        offset: Starting position
        filter_expr: Filter expression

    Returns:
        List of vouchers
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Listing vouchers for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if filter_expr:
            params["filter"] = filter_expr

        response = await client.get(f"/integration/v1/sites/{site_id}/vouchers", params=params)
        data = response.get("data", [])

        return [Voucher(**voucher).model_dump() for voucher in data]


async def get_voucher(site_id: str, voucher_id: str, settings: Settings) -> dict:
    """Get details for a specific voucher.

    Args:
        site_id: Site identifier
        voucher_id: Voucher identifier
        settings: Application settings

    Returns:
        Voucher details
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Getting voucher {voucher_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/vouchers/{voucher_id}")
        data = response.get("data", response)

        return Voucher(**data).model_dump()


async def create_vouchers(
    site_id: str,
    count: int,
    duration: int,
    settings: Settings,
    upload_limit_kbps: int | None = None,
    download_limit_kbps: int | None = None,
    upload_quota_mb: int | None = None,
    download_quota_mb: int | None = None,
    note: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Create new hotspot vouchers.

    Args:
        site_id: Site identifier
        count: Number of vouchers to create
        duration: Duration in seconds
        settings: Application settings
        upload_limit_kbps: Upload speed limit in kbps
        download_limit_kbps: Download speed limit in kbps
        upload_quota_mb: Upload quota in MB
        download_quota_mb: Download quota in MB
        note: Admin notes
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created voucher codes
    """
    validate_confirmation(confirm, "create vouchers")

    async with UniFiClient(settings) as client:
        logger.info(f"Creating {count} vouchers for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload
        payload = {
            "count": count,
            "duration": duration,
        }

        if upload_limit_kbps is not None:
            payload["uploadLimit"] = upload_limit_kbps
        if download_limit_kbps is not None:
            payload["downloadLimit"] = download_limit_kbps
        if upload_quota_mb is not None:
            payload["uploadQuota"] = upload_quota_mb
        if download_quota_mb is not None:
            payload["downloadQuota"] = download_quota_mb
        if note:
            payload["note"] = note

        if dry_run:
            logger.info(f"[DRY RUN] Would create vouchers with payload: {payload}")
            return {"dry_run": True, "payload": payload}

        response = await client.post(f"/integration/v1/sites/{site_id}/vouchers", json_data=payload)
        data = response.get("data", response)

        # Audit the action
        await audit_action(
            settings,
            action_type="create_vouchers",
            resource_type="voucher",
            resource_id="bulk",
            site_id=site_id,
            details={"count": count, "duration": duration},
        )

        return {
            "success": True,
            "count": count,
            "vouchers": data if isinstance(data, list) else [data],
        }


async def delete_voucher(
    site_id: str,
    voucher_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Delete a specific voucher.

    Args:
        site_id: Site identifier
        voucher_id: Voucher identifier
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion status
    """
    validate_confirmation(confirm, "delete voucher")

    async with UniFiClient(settings) as client:
        logger.info(f"Deleting voucher {voucher_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(f"[DRY RUN] Would delete voucher {voucher_id}")
            return {"dry_run": True, "voucher_id": voucher_id}

        await client.delete(f"/integration/v1/sites/{site_id}/vouchers/{voucher_id}")

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
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Bulk delete vouchers using a filter expression.

    Args:
        site_id: Site identifier
        filter_expr: Filter expression to select vouchers
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion status
    """
    validate_confirmation(confirm, "bulk delete vouchers")

    async with UniFiClient(settings) as client:
        logger.info(f"Bulk deleting vouchers for site {site_id} with filter: {filter_expr}")

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(f"[DRY RUN] Would bulk delete vouchers with filter: {filter_expr}")
            return {"dry_run": True, "filter": filter_expr}

        params = {"filter": filter_expr}
        response = await client.delete(f"/integration/v1/sites/{site_id}/vouchers", params=params)

        # Audit the action
        await audit_action(
            settings,
            action_type="bulk_delete_vouchers",
            resource_type="voucher",
            resource_id="bulk",
            site_id=site_id,
            details={"filter": filter_expr},
        )

        return {
            "success": True,
            "message": "Vouchers deleted successfully",
            "deleted_count": response.get("data", {}).get("count", 0),
        }
