"""MCP tools for UniFi Protect users and ULP users (Protect v7 surface)."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import ProtectUlpUser, ProtectUser
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset


def _validate_user_id(user_id: str, label: str = "user_id") -> str:
    user_id = user_id.strip()
    if not user_id:
        raise ValidationError(f"{label} is required")
    return user_id


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


async def list_protect_users(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect users."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("users"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    users = [ProtectUser.model_validate(item).model_dump(by_alias=True) for item in data]
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)
    logger.info(sanitize_log_message(f"Listed {len(users)} Protect users"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": users,
    }


async def get_protect_user(user_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect user."""
    logger = get_logger(__name__, settings.log_level)
    user_id = _validate_user_id(user_id)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"users/{user_id}"))

    user = ProtectUser.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect user {user_id}"))
    return user.model_dump(by_alias=True)


async def list_protect_ulp_users(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Identity (ULP) users."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("ulp-users"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    users = [ProtectUlpUser.model_validate(item).model_dump(by_alias=True) for item in data]
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)
    logger.info(sanitize_log_message(f"Listed {len(users)} Protect ULP users"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": users,
    }


async def get_protect_ulp_user(ulp_user_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Identity (ULP) user."""
    logger = get_logger(__name__, settings.log_level)
    ulp_user_id = _validate_user_id(ulp_user_id, label="ulp_user_id")

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path(f"ulp-users/{ulp_user_id}")
        )

    user = ProtectUlpUser.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect ULP user {ulp_user_id}"))
    return user.model_dump(by_alias=True)
