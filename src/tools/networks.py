"""Network information MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models import Network
from ..utils import (
    ResourceNotFoundError,
    get_logger,
    validate_limit_offset,
    validate_site_id,
)


async def get_network_details(
    site_id: str, network_id: str, settings: Settings
) -> dict[str, Any]:
    """Get detailed network configuration.

    Args:
        site_id: Site identifier
        network_id: Network identifier
        settings: Application settings

    Returns:
        Network details dictionary

    Raises:
        ResourceNotFoundError: If network not found
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")
        networks_data = response.get("data", [])

        for network_data in networks_data:
            if network_data.get("_id") == network_id:
                network = Network(**network_data)
                logger.info(f"Retrieved network details for {network_id}")
                return network.model_dump()

        raise ResourceNotFoundError("network", network_id)


async def list_vlans(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all VLANs in a site.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of VLANs to return
        offset: Number of VLANs to skip

    Returns:
        List of VLAN dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")
        networks_data = response.get("data", [])

        # Filter for networks with VLAN configuration
        vlans = [n for n in networks_data if n.get("vlan_id") is not None]

        # Apply pagination
        paginated = vlans[offset : offset + limit]

        # Parse into Network models
        networks = [Network(**n).model_dump() for n in paginated]

        logger.info(f"Retrieved {len(networks)} VLANs for site '{site_id}'")
        return networks


async def get_subnet_info(
    site_id: str, network_id: str, settings: Settings
) -> dict[str, Any]:
    """Get subnet and DHCP information for a network.

    Args:
        site_id: Site identifier
        network_id: Network identifier
        settings: Application settings

    Returns:
        Subnet and DHCP information dictionary

    Raises:
        ResourceNotFoundError: If network not found
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")
        networks_data = response.get("data", [])

        for network_data in networks_data:
            if network_data.get("_id") == network_id:
                # Extract subnet and DHCP information
                subnet_info = {
                    "network_id": network_id,
                    "name": network_data.get("name"),
                    "ip_subnet": network_data.get("ip_subnet"),
                    "vlan_id": network_data.get("vlan_id"),
                    "dhcpd_enabled": network_data.get("dhcpd_enabled", False),
                    "dhcpd_start": network_data.get("dhcpd_start"),
                    "dhcpd_stop": network_data.get("dhcpd_stop"),
                    "dhcpd_leasetime": network_data.get("dhcpd_leasetime"),
                    "dhcpd_dns_1": network_data.get("dhcpd_dns_1"),
                    "dhcpd_dns_2": network_data.get("dhcpd_dns_2"),
                    "dhcpd_gateway": network_data.get("dhcpd_gateway"),
                    "domain_name": network_data.get("domain_name"),
                }
                logger.info(f"Retrieved subnet info for network {network_id}")
                return subnet_info

        raise ResourceNotFoundError("network", network_id)


async def get_network_statistics(
    site_id: str, settings: Settings
) -> dict[str, Any]:
    """Retrieve network usage statistics for a site.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Network statistics dictionary
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # Get network configurations
        networks_response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")
        networks_data = networks_response.get("data", [])

        # Get active clients to count usage per network
        clients_response = await client.get(f"/ea/sites/{site_id}/sta")
        clients_data = clients_response.get("data", [])

        # Calculate statistics per network
        network_stats = []
        for network in networks_data:
            network_id = network.get("_id")
            vlan_id = network.get("vlan_id")

            # Count clients on this network
            clients_on_network = [
                c for c in clients_data if c.get("vlan") == vlan_id
            ]

            # Calculate total bandwidth
            total_tx = sum(c.get("tx_bytes", 0) for c in clients_on_network)
            total_rx = sum(c.get("rx_bytes", 0) for c in clients_on_network)

            network_stats.append(
                {
                    "network_id": network_id,
                    "name": network.get("name"),
                    "vlan_id": vlan_id,
                    "client_count": len(clients_on_network),
                    "total_tx_bytes": total_tx,
                    "total_rx_bytes": total_rx,
                    "total_bytes": total_tx + total_rx,
                }
            )

        logger.info(f"Retrieved network statistics for site '{site_id}'")
        return {"site_id": site_id, "networks": network_stats}
