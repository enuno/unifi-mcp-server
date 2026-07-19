"""MCP tools for UniFi Protect camera read operations."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectCamera
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset


def _validate_camera_id(camera_id: str) -> str:
    camera_id = camera_id.strip()
    if not camera_id:
        raise ValidationError("camera_id is required")
    return camera_id


async def list_protect_cameras(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect cameras."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("cameras"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    cameras = [ProtectCamera.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(sanitize_log_message(f"Listed {len(cameras)} Protect cameras"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": cameras,
    }


async def get_protect_camera(camera_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect camera."""
    logger = get_logger(__name__, settings.log_level)
    camera_id = _validate_camera_id(camera_id)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"cameras/{camera_id}"))

    camera_data = response.get("data", response) if isinstance(response, dict) else response
    camera = ProtectCamera.model_validate(camera_data)
    logger.info(sanitize_log_message(f"Retrieved Protect camera {camera_id}"))
    return camera.model_dump(by_alias=True)
