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
        >>> print(info["application_version"])
    """
    async with UniFiClient(settings) as client:
        logger.info("Fetching application information")

        # Authenticate if not already done
        if not client.is_authenticated:
            await client.authenticate()

        # The documented route is /v1/info; /application/info does not exist
        # and 404s on every controller. The documented response carries a
        # single key, applicationVersion — the version/build/deploymentType/
        # capabilities/systemInfo keys this tool used to report came from
        # nowhere real and were always None.
        response = await client.get(settings.get_integration_path("info"))

        # Extract data from response
        if isinstance(response, list):
            data = response[0] if response else {}
        else:
            _raw = response.get("data", response)
            data = _raw[0] if isinstance(_raw, list) else _raw

        # Report the documented key under this server's snake_case convention
        # and pass anything else through verbatim, so a future controller that
        # says more is not silenced by an allowlist.
        return {
            "application_version": data.get("applicationVersion"),
            **{k: v for k, v in data.items() if k != "applicationVersion"},
        }
