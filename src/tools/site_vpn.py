"""Site-to-Site VPN management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models.vpn import SiteToSiteVPN
from ..utils import ResourceNotFoundError, get_logger, sanitize_log_message, validate_site_id


async def list_site_to_site_vpns(site_id: str, settings: Settings) -> list[dict[str, Any]]:
    """List all site-to-site VPN configurations."""
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        response = await client.get(f"/proxy/network/api/s/{site_id}/rest/networkconf")
        networks = response if isinstance(response, list) else response.get("data", [])
        vpns = [n for n in networks if n.get("purpose") == "site-vpn"]
        logger.info(sanitize_log_message(f"Retrieved {len(vpns)} site-to-site VPNs"))
        return [SiteToSiteVPN(**v).model_dump() for v in vpns]


async def get_site_to_site_vpn(site_id: str, vpn_id: str, settings: Settings) -> dict[str, Any]:
    """Get details for a specific site-to-site VPN."""
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        response = await client.get(f"/proxy/network/api/s/{site_id}/rest/networkconf")
        networks = response if isinstance(response, list) else response.get("data", [])

        for n in networks:
            if n.get("_id") == vpn_id and n.get("purpose") == "site-vpn":
                logger.info(sanitize_log_message(f"Retrieved VPN {vpn_id}"))
                return SiteToSiteVPN(**n).model_dump()

        raise ResourceNotFoundError("vpn", vpn_id)


async def update_site_to_site_vpn(
    site_id: str,
    vpn_id: str,
    settings: Settings,
    *,
    name: str | None = None,
    enabled: bool | None = None,
    ipsec_peer_ip: str | None = None,
    remote_vpn_subnets: list[str] | None = None,
    x_ipsec_pre_shared_key: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update a site-to-site VPN configuration (requires confirm=True)."""
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # Get current config
        response = await client.get(f"/proxy/network/api/s/{site_id}/rest/networkconf/{vpn_id}")
        current = response if isinstance(response, dict) and "_id" in response else None
        if not current:
            resp_list = response if isinstance(response, list) else response.get("data", [])
            current = resp_list[0] if resp_list else None
        if not current or current.get("purpose") != "site-vpn":
            raise ResourceNotFoundError("vpn", vpn_id)

        # Build update payload
        updates = {}
        if name is not None:
            updates["name"] = name
        if enabled is not None:
            updates["enabled"] = enabled
        if ipsec_peer_ip is not None:
            updates["ipsec_peer_ip"] = ipsec_peer_ip
        if remote_vpn_subnets is not None:
            updates["remote_vpn_subnets"] = remote_vpn_subnets
        if x_ipsec_pre_shared_key is not None:
            updates["x_ipsec_pre_shared_key"] = x_ipsec_pre_shared_key

        if dry_run:
            return {"dry_run": True, "vpn_id": vpn_id, "updates": updates}

        if not confirm:
            return {"error": "confirm=True required", "vpn_id": vpn_id, "updates": updates}

        # Merge and update
        payload = {**current, **updates}
        await client.put(f"/proxy/network/api/s/{site_id}/rest/networkconf/{vpn_id}", payload)
        logger.info(sanitize_log_message(f"Updated VPN {vpn_id}"))
        return {"success": True, "vpn_id": vpn_id, "updates": updates}
