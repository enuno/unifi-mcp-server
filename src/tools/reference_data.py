"""Reference data MCP tools for supporting resources."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models.radius import RADIUSProfile
from ..models.reference_data import Country, DeviceTag
from ..utils import get_logger, validate_limit_offset, validate_site_id


async def list_radius_profiles(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all RADIUS profiles in a site (read-only).

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of profiles to return
        offset: Number of profiles to skip

    Returns:
        List of RADIUS profile dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/radius/profiles")
        profiles_data: list[dict[str, Any]] = response.get("data", [])

        # Apply pagination
        paginated = profiles_data[offset : offset + limit]

        logger.info(f"Retrieved {len(paginated)} RADIUS profiles for site '{site_id}'")
        return [RADIUSProfile(**profile).model_dump() for profile in paginated]


async def list_device_tags(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all device tags in a site (read-only).

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of tags to return
        offset: Number of tags to skip

    Returns:
        List of device tag dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/device-tags")
        tags_data: list[dict[str, Any]] = response.get("data", [])

        # Apply pagination
        paginated = tags_data[offset : offset + limit]

        logger.info(f"Retrieved {len(paginated)} device tags for site '{site_id}'")
        return [DeviceTag(**tag).model_dump() for tag in paginated]


async def list_countries(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all countries with ISO codes (read-only).

    Args:
        settings: Application settings
        limit: Maximum number of countries to return
        offset: Number of countries to skip

    Returns:
        List of country dictionaries
    """
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get("/integration/v1/countries")
        countries_data: list[dict[str, Any]] = response.get("data", [])

        # Apply pagination
        paginated = countries_data[offset : offset + limit]

        logger.info(f"Retrieved {len(paginated)} countries")
        return [Country(**country).model_dump() for country in paginated]
