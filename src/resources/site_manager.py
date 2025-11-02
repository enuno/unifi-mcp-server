"""Site Manager API resources."""

from ..api.site_manager_client import SiteManagerClient
from ..config import Settings
from ..utils import get_logger

logger = get_logger(__name__)


class SiteManagerResource:
    """Resource handler for Site Manager API."""

    def __init__(self, settings: Settings) -> None:
        """Initialize Site Manager resource handler.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)

    async def get_all_sites(self) -> str:
        """Get all sites across organization.

        Returns:
            JSON string of sites list
        """
        if not self.settings.site_manager_enabled:
            return "Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true"

        async with SiteManagerClient(self.settings) as client:
            response = await client.list_sites()
            sites = response.get("data", response.get("sites", []))
            return "\n".join([f"Site: {s.get('name', 'Unknown')} ({s.get('id', 'unknown')})" for s in sites])

    async def get_health_metrics(self) -> str:
        """Get cross-site health metrics.

        Returns:
            JSON string of health metrics
        """
        if not self.settings.site_manager_enabled:
            return "Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true"

        async with SiteManagerClient(self.settings) as client:
            response = await client.get_site_health()
            health_data = response.get("data", response)
            return f"Health Status: {health_data}"

    async def get_internet_health_status(self) -> str:
        """Get internet connectivity status.

        Returns:
            JSON string of internet health
        """
        if not self.settings.site_manager_enabled:
            return "Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true"

        async with SiteManagerClient(self.settings) as client:
            response = await client.get_internet_health()
            health_data = response.get("data", response)
            return f"Internet Health: {health_data}"

