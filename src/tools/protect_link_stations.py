"""MCP tools for UniFi Protect link stations (Protect v7 surface, Phase 5a)."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectLinkStation
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset
from ..utils.validators import coerce_bool, validate_confirmation


def _validate_link_station_id(link_station_id: str) -> str:
    link_station_id = link_station_id.strip()
    if not link_station_id:
        raise ValidationError("link_station_id is required")
    return link_station_id


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


async def list_protect_link_stations(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect link stations."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("link-stations"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    link_stations = [
        ProtectLinkStation.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)
    logger.info(sanitize_log_message(f"Listed {len(link_stations)} Protect link stations"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": link_stations,
    }


async def get_protect_link_station(link_station_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect link station."""
    logger = get_logger(__name__, settings.log_level)
    link_station_id = _validate_link_station_id(link_station_id)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path(f"link-stations/{link_station_id}")
        )

    link_station = ProtectLinkStation.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect link station {link_station_id}"))
    return link_station.model_dump(by_alias=True)


async def update_protect_link_station(
    link_station_id: str,
    settings: Settings,
    name: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect link station settings.

    Args:
        link_station_id: Protect link station identifier
        settings: Application settings
        name: New display name
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated record as returned by the controller
    """
    validate_confirmation(confirm, "update Protect link station", dry_run)
    logger = get_logger(__name__, settings.log_level)
    link_station_id = _validate_link_station_id(link_station_id)

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name

    if not payload:
        raise ValidationError("No updates provided: pass at least one of name")

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_protect_link_station",
            "link_station_id": link_station_id,
            "payload": payload,
        }

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.patch(
            settings.get_protect_integration_path(f"link-stations/{link_station_id}"),
            json_data=payload,
        )

    link_station = ProtectLinkStation.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Updated Protect link station {link_station_id}"))
    return link_station.model_dump(by_alias=True)
