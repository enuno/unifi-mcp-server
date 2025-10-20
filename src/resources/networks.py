"""Networks MCP resource implementation."""


from ..api import UniFiClient
from ..config import Settings
from ..models import Network
from ..utils import get_logger, validate_limit_offset, validate_site_id


class NetworksResource:
    """MCP resource for UniFi networks."""

    def __init__(self, settings: Settings) -> None:
        """Initialize networks resource.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)

    async def list_networks(
        self, site_id: str, limit: int | None = None, offset: int | None = None
    ) -> list[Network]:
        """List all networks for a specific site.

        Args:
            site_id: Site identifier
            limit: Maximum number of networks to return
            offset: Number of networks to skip

        Returns:
            List of Network objects
        """
        site_id = validate_site_id(site_id)
        limit, offset = validate_limit_offset(limit, offset)

        async with UniFiClient(self.settings) as client:
            await client.authenticate()

            # Fetch networks from API
            response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")

            # Extract networks data
            networks_data = response.get("data", [])

            # Apply pagination
            paginated_data = networks_data[offset : offset + limit]

            # Parse into Network models
            networks = [Network(**network) for network in paginated_data]

            self.logger.info(
                f"Retrieved {len(networks)} networks for site '{site_id}' "
                f"(offset={offset}, limit={limit})"
            )

            return networks

    async def list_vlans(
        self, site_id: str, limit: int | None = None, offset: int | None = None
    ) -> list[Network]:
        """List all VLANs for a specific site.

        Args:
            site_id: Site identifier
            limit: Maximum number of VLANs to return
            offset: Number of VLANs to skip

        Returns:
            List of Network objects that are VLANs
        """
        networks = await self.list_networks(site_id, limit=1000, offset=0)

        # Filter for networks with VLAN configuration
        vlans = [n for n in networks if n.vlan_id is not None]

        # Apply pagination to filtered results
        limit, offset = validate_limit_offset(limit, offset)
        return vlans[offset : offset + limit]

    def get_uri(self, site_id: str, network_id: str | None = None) -> str:
        """Get the MCP resource URI.

        Args:
            site_id: Site identifier
            network_id: Optional network ID

        Returns:
            Resource URI
        """
        if network_id:
            return f"sites://{site_id}/networks/{network_id}"
        return f"sites://{site_id}/networks"
