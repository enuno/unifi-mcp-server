"""Devices MCP resource implementation."""

from ..api import UniFiClient
from ..config import Settings
from ..models import Device
from ..utils import get_logger, validate_limit_offset, validate_site_id


class DevicesResource:
    """MCP resource for UniFi devices."""

    def __init__(self, settings: Settings) -> None:
        """Initialize devices resource.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)

    async def list_devices(
        self, site_id: str, limit: int | None = None, offset: int | None = None
    ) -> list[Device]:
        """List all devices for a specific site.

        Args:
            site_id: Site identifier
            limit: Maximum number of devices to return
            offset: Number of devices to skip

        Returns:
            List of Device objects
        """
        site_id = validate_site_id(site_id)
        limit, offset = validate_limit_offset(limit, offset)

        async with UniFiClient(self.settings) as client:
            await client.authenticate()

            # Fetch devices from API
            response = await client.get(f"/ea/sites/{site_id}/devices")

            # Extract devices data
            devices_data = response.get("data", [])

            # Apply pagination
            paginated_data = devices_data[offset : offset + limit]

            # Parse into Device models
            devices = [Device(**device) for device in paginated_data]

            self.logger.info(
                f"Retrieved {len(devices)} devices for site '{site_id}' "
                f"(offset={offset}, limit={limit})"
            )

            return devices

    async def filter_by_type(
        self,
        site_id: str,
        device_type: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Device]:
        """Filter devices by type.

        Args:
            site_id: Site identifier
            device_type: Device type filter (ap, switch, gateway)
            limit: Maximum number of devices to return
            offset: Number of devices to skip

        Returns:
            Filtered list of Device objects
        """
        devices = await self.list_devices(site_id, limit=1000, offset=0)

        # Filter by type
        filtered = [
            d
            for d in devices
            if d.type.lower() == device_type.lower() or device_type.lower() in d.model.lower()
        ]

        # Apply pagination to filtered results
        limit, offset = validate_limit_offset(limit, offset)
        return filtered[offset : offset + limit]

    def get_uri(self, site_id: str, device_id: str | None = None) -> str:
        """Get the MCP resource URI.

        Args:
            site_id: Site identifier
            device_id: Optional device ID

        Returns:
            Resource URI
        """
        if device_id:
            return f"sites://{site_id}/devices/{device_id}"
        return f"sites://{site_id}/devices"
