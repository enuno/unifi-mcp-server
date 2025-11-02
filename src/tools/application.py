"""Application information tools."""

from ..api.client import UniFiClient
from ..config import Settings
from ..utils import get_logger

logger = get_logger(__name__)


async def get_application_info(settings: Settings) -> dict:
    """Get UniFi Network application information.

    Args:
        settings: Application settings

    Returns:
        Application information dictionary

    Example:
        >>> info = await get_application_info(settings)
        >>> print(info["version"])
    """
    async with UniFiClient(settings) as client:
        logger.info("Fetching application information")

        # Authenticate if not already done
        if not client.is_authenticated:
            await client.authenticate()

        # Get application info
        response = await client.get("/integration/v1/application/info")

        # Extract data from response
        data = response.get("data", response)

        return {
            "version": data.get("version"),
            "build": data.get("build"),
            "deployment_type": data.get("deploymentType"),
            "capabilities": data.get("capabilities", []),
            "system_info": data.get("systemInfo", {}),
        }
