"""DPI (Deep Packet Inspection) and country information tools."""

from typing import Any

from ..api.client import UniFiClient
from ..config import Settings
from ..models import Country, DPIApplication, DPICategory
from ..utils import get_logger

logger = get_logger(__name__)


async def list_dpi_categories(settings: Settings) -> list[dict]:
    """List all DPI categories.

    Args:
        settings: Application settings

    Returns:
        List of DPI categories
    """
    async with UniFiClient(settings) as client:
        logger.info("Listing DPI categories")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get("/integration/v1/dpi/categories")
        data = response.get("data", [])

        return [DPICategory(**category).model_dump() for category in data]


async def list_dpi_applications(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
    filter_expr: str | None = None,
) -> list[dict]:
    """List all DPI applications.

    Args:
        settings: Application settings
        limit: Maximum number of results
        offset: Starting position
        filter_expr: Filter expression

    Returns:
        List of DPI applications
    """
    async with UniFiClient(settings) as client:
        logger.info("Listing DPI applications")

        if not client.is_authenticated:
            await client.authenticate()

        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if filter_expr:
            params["filter"] = filter_expr

        response = await client.get("/integration/v1/dpi/applications", params=params)
        data = response.get("data", [])

        return [DPIApplication(**app).model_dump() for app in data]


async def list_countries(settings: Settings) -> list[dict]:
    """List all countries for configuration and localization.

    Args:
        settings: Application settings

    Returns:
        List of countries
    """
    async with UniFiClient(settings) as client:
        logger.info("Listing countries")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get("/integration/v1/countries")
        data = response.get("data", [])

        return [Country(**country).model_dump() for country in data]
