"""Clients MCP resource implementation."""

from ..api import UniFiClient
from ..config import Settings
from ..models import Client
from ..utils import get_logger, validate_limit_offset, validate_site_id


class ClientsResource:
    """MCP resource for UniFi network clients."""

    def __init__(self, settings: Settings) -> None:
        """Initialize clients resource.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)

    async def list_clients(
        self,
        site_id: str,
        limit: int | None = None,
        offset: int | None = None,
        active_only: bool = False,
    ) -> list[Client]:
        """List all clients for a specific site.

        Args:
            site_id: Site identifier
            limit: Maximum number of clients to return
            offset: Number of clients to skip
            active_only: If True, only return currently connected clients

        Returns:
            List of Client objects
        """
        site_id = validate_site_id(site_id)
        limit, offset = validate_limit_offset(limit, offset)

        async with UniFiClient(self.settings) as client:
            await client.authenticate()

            # Fetch clients from API
            # Use /sta for active clients or /stat/alluser for all
            endpoint = (
                f"/ea/sites/{site_id}/sta" if active_only else f"/ea/sites/{site_id}/stat/alluser"
            )

            response = await client.get(endpoint)

            # Extract clients data
            clients_data = response.get("data", [])

            # Apply pagination
            paginated_data = clients_data[offset : offset + limit]

            # Parse into Client models
            clients = [Client(**client_data) for client_data in paginated_data]

            self.logger.info(
                f"Retrieved {len(clients)} clients for site '{site_id}' "
                f"(active_only={active_only}, offset={offset}, limit={limit})"
            )

            return clients

    async def filter_by_connection(
        self,
        site_id: str,
        is_wired: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Client]:
        """Filter clients by connection type.

        Args:
            site_id: Site identifier
            is_wired: Filter by wired (True) or wireless (False)
            limit: Maximum number of clients to return
            offset: Number of clients to skip

        Returns:
            Filtered list of Client objects
        """
        clients = await self.list_clients(site_id, limit=1000, offset=0, active_only=True)

        # Filter by connection type
        if is_wired is not None:
            filtered = [c for c in clients if c.is_wired == is_wired]
        else:
            filtered = clients

        # Apply pagination to filtered results
        limit, offset = validate_limit_offset(limit, offset)
        return filtered[offset : offset + limit]

    def get_uri(self, site_id: str, client_mac: str | None = None) -> str:
        """Get the MCP resource URI.

        Args:
            site_id: Site identifier
            client_mac: Optional client MAC address

        Returns:
            Resource URI
        """
        if client_mac:
            return f"sites://{site_id}/clients/{client_mac}"
        return f"sites://{site_id}/clients"
