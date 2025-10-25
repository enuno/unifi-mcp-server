"""WAN connection management tools."""

from ..api.client import UniFiClient
from ..config import Settings
from ..models import WANConnection
from ..utils import get_logger

logger = get_logger(__name__)


async def list_wan_connections(site_id: str, settings: Settings) -> list[dict]:
    """List all WAN connections for a site.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        List of WAN connections
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Listing WAN connections for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/wans")
        data = response.get("data", [])

        return [WANConnection(**wan).model_dump() for wan in data]
