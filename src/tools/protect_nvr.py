"""MCP tools for UniFi Protect NVR read operations."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models.protect_nvr import ProtectNVR
from ..utils import ValidationError, get_logger, sanitize_log_message


def _validate_nvr_id(nvr_id: str) -> str:
    nvr_id = nvr_id.strip()
    if not nvr_id:
        raise ValidationError("nvr_id is required")
    return nvr_id


async def list_protect_nvrs(settings: Settings) -> dict[str, Any]:
    """List UniFi Protect NVRs."""
    logger = get_logger(__name__, settings.log_level)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path("nvrs"))

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    nvrs = [ProtectNVR.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(sanitize_log_message(f"Listed {len(nvrs)} Protect NVRs"))

    return {
        "count": count,
        "totalCount": total_count,
        "data": nvrs,
    }


async def get_protect_nvr(nvr_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect NVR."""
    logger = get_logger(__name__, settings.log_level)
    nvr_id = _validate_nvr_id(nvr_id)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"nvrs/{nvr_id}"))

    nvr_data = response.get("data", response) if isinstance(response, dict) else response
    nvr = ProtectNVR.model_validate(nvr_data)
    logger.info(sanitize_log_message(f"Retrieved Protect NVR {nvr_id}"))
    return nvr.model_dump(by_alias=True)
