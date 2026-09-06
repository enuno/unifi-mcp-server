"""MCP tools for UniFi Protect live views and viewer settings."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectLiveView, ProtectMetaInfo, ProtectViewer
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset
from ..utils.validators import coerce_bool, validate_confirmation


def _validate_id(record_id: str, label: str) -> str:
    record_id = record_id.strip()
    if not record_id:
        raise ValidationError(f"{label} is required")
    return record_id


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


async def get_protect_meta_info(settings: Settings) -> dict[str, Any]:
    """Get Protect application metadata."""
    logger = get_logger(__name__, settings.log_level)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path("meta/info"))

    meta = ProtectMetaInfo.model_validate(_extract_item(response))
    logger.info(sanitize_log_message("Retrieved Protect application metadata"))
    return meta.model_dump(by_alias=True)


async def list_protect_viewers(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List Protect viewers."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path("viewers"))

    viewers_data = _extract_collection(response)
    paginated = viewers_data[final_offset : final_offset + final_limit]
    viewers = [ProtectViewer.model_validate(item).model_dump(by_alias=True) for item in paginated]
    total_count = len(viewers_data)
    logger.info(sanitize_log_message(f"Listed {len(viewers)} Protect viewers"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(viewers),
        "totalCount": total_count,
        "data": viewers,
    }


async def get_protect_viewer(viewer_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single Protect viewer."""
    logger = get_logger(__name__, settings.log_level)
    viewer_id = _validate_id(viewer_id, "viewer_id")

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"viewers/{viewer_id}"))

    viewer = ProtectViewer.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect viewer {viewer_id}"))
    return viewer.model_dump(by_alias=True)


async def update_protect_viewer(
    viewer_id: str,
    settings: Settings,
    name: str | None = None,
    liveview: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect viewer settings.

    Args:
        viewer_id: Protect viewer identifier
        settings: Application settings
        name: New display name
        liveview: Live view to display on the viewer
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated record as returned by the controller
    """
    validate_confirmation(confirm, "update Protect viewer", dry_run)
    logger = get_logger(__name__, settings.log_level)
    viewer_id = _validate_id(viewer_id, "viewer_id")

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if liveview is not None:
        payload["liveview"] = liveview

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_protect_viewer",
            "viewer_id": viewer_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path(f"viewers/{viewer_id}"),
            json_data=payload,
        )

    viewer = ProtectViewer.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Updated Protect viewer {viewer_id}"))
    return viewer.model_dump(by_alias=True)


async def list_protect_live_views(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List Protect live views."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path("liveviews"))

    live_views_data = _extract_collection(response)
    paginated = live_views_data[final_offset : final_offset + final_limit]
    live_views = [
        ProtectLiveView.model_validate(item).model_dump(by_alias=True) for item in paginated
    ]
    total_count = len(live_views_data)
    logger.info(sanitize_log_message(f"Listed {len(live_views)} Protect live views"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(live_views),
        "totalCount": total_count,
        "data": live_views,
    }


async def get_protect_live_view(live_view_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single Protect live view."""
    logger = get_logger(__name__, settings.log_level)
    live_view_id = _validate_id(live_view_id, "live_view_id")

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path(f"liveviews/{live_view_id}")
        )

    live_view = ProtectLiveView.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect live view {live_view_id}"))
    return live_view.model_dump(by_alias=True)


async def create_protect_live_view(
    live_view: dict[str, Any],
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a Protect live view.

    Args:
        live_view: Live view definition to create
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The created live view as returned by the controller
    """
    validate_confirmation(confirm, "create a Protect live view", dry_run)
    logger = get_logger(__name__, settings.log_level)

    if coerce_bool(dry_run):
        return {"dry_run": True, "operation": "create_protect_live_view"}

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.post(
            settings.get_protect_integration_path("liveviews"),
            json_data=live_view,
        )

    created = ProtectLiveView.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Created Protect live view {created.id or 'unknown'}"))
    return created.model_dump(by_alias=True)


async def update_protect_live_view(
    live_view_id: str,
    settings: Settings,
    name: str | None = None,
    model_key: str | None = None,
    is_default: bool | None = None,
    is_global: bool | None = None,
    owner: str | None = None,
    layout: int | None = None,
    slots: list[dict[str, Any]] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect live view settings.

    Args:
        live_view_id: Protect live view identifier
        settings: Application settings
        name: New display name
        model_key: Live view model key
        is_default: Mark this live view as the default
        is_global: Share the live view across users
        owner: Live view owner identifier
        layout: Live view layout identifier
        slots: Live view slot configuration
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated record as returned by the controller
    """
    validate_confirmation(confirm, "update Protect live view", dry_run)
    logger = get_logger(__name__, settings.log_level)
    live_view_id = _validate_id(live_view_id, "live_view_id")

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if model_key is not None:
        payload["modelKey"] = model_key
    if is_default is not None:
        payload["isDefault"] = is_default
    if is_global is not None:
        payload["isGlobal"] = is_global
    if owner is not None:
        payload["owner"] = owner
    if layout is not None:
        payload["layout"] = layout
    if slots is not None:
        payload["slots"] = slots

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_protect_live_view",
            "live_view_id": live_view_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path(f"liveviews/{live_view_id}"),
            json_data=payload,
        )

    live_view = ProtectLiveView.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Updated Protect live view {live_view_id}"))
    return live_view.model_dump(by_alias=True)
