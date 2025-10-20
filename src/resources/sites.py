"""Sites MCP resource implementation."""


from ..api import UniFiClient
from ..config import Settings
from ..models import Site
from ..utils import get_logger, validate_limit_offset


class SitesResource:
    """MCP resource for UniFi sites."""

    def __init__(self, settings: Settings) -> None:
        """Initialize sites resource.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)

    async def list_sites(self, limit: int | None = None, offset: int | None = None) -> list[Site]:
        """List all UniFi sites.

        Args:
            limit: Maximum number of sites to return
            offset: Number of sites to skip

        Returns:
            List of Site objects
        """
        limit, offset = validate_limit_offset(limit, offset)

        async with UniFiClient(self.settings) as client:
            # Authenticate first
            await client.authenticate()

            # Fetch sites from API
            response = await client.get("/ea/sites")

            # Extract sites data
            sites_data = response.get("data", [])

            # Apply pagination
            paginated_data = sites_data[offset : offset + limit]

            # Parse into Site models
            sites = [Site(**site) for site in paginated_data]

            self.logger.info(f"Retrieved {len(sites)} sites (offset={offset}, limit={limit})")

            return sites

    async def get_site(self, site_id: str) -> Site | None:
        """Get a specific site by ID.

        Args:
            site_id: Site identifier

        Returns:
            Site object or None if not found
        """
        async with UniFiClient(self.settings) as client:
            await client.authenticate()

            response = await client.get("/ea/sites")
            sites_data = response.get("data", [])

            # Find the specific site
            for site_data in sites_data:
                if site_data.get("_id") == site_id or site_data.get("name") == site_id:
                    return Site(**site_data)

            return None

    def get_uri(self, site_id: str | None = None) -> str:
        """Get the MCP resource URI.

        Args:
            site_id: Optional site ID

        Returns:
            Resource URI
        """
        if site_id:
            return f"sites://{site_id}"
        return "sites://"
