"""VPN management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models.vpn import VPNServer, VPNTunnel
from ..utils import get_logger, validate_limit_offset, validate_site_id


async def list_vpn_tunnels(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all site-to-site VPN tunnels in a site (read-only).

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of tunnels to return
        offset: Number of tunnels to skip

    Returns:
        List of VPN tunnel dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/vpn/site-to-site-tunnels")
        tunnels_data: list[dict[str, Any]] = response.get("data", [])

        # Apply pagination
        paginated = tunnels_data[offset : offset + limit]

        logger.info(f"Retrieved {len(paginated)} VPN tunnels for site '{site_id}'")
        return [VPNTunnel(**tunnel).model_dump() for tunnel in paginated]


async def list_vpn_servers(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all VPN servers in a site (read-only).

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of servers to return
        offset: Number of servers to skip

    Returns:
        List of VPN server dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/vpn/servers")
        servers_data: list[dict[str, Any]] = response.get("data", [])

        # Apply pagination
        paginated = servers_data[offset : offset + limit]

        logger.info(f"Retrieved {len(paginated)} VPN servers for site '{site_id}'")
        return [VPNServer(**server).model_dump() for server in paginated]
