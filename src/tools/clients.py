"""Client management MCP tools."""

import asyncio
from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models import Client
from ..utils import (
    ResourceNotFoundError,
    get_logger,
    sanitize_log_message,
    validate_limit_offset,
    validate_mac_address,
    validate_site_id,
)


async def get_client_details(site_id: str, client_mac: str, settings: Settings) -> dict[str, Any]:
    """Get detailed information for a specific client.

    Args:
        site_id: Site identifier
        client_mac: Client MAC address
        settings: Application settings

    Returns:
        Client details dictionary

    Raises:
        ResourceNotFoundError: If client not found
    """
    site_id = validate_site_id(site_id)
    client_mac = validate_mac_address(client_mac)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # Try active clients first
        response = await client.get(f"/ea/sites/{site_id}/sta")
        clients_data = response.get("data", []) if isinstance(response, dict) else response

        for client_data in clients_data:
            if validate_mac_address(client_data.get("mac", "")) == client_mac:
                client_obj = Client(**client_data)
                logger.info(sanitize_log_message(f"Retrieved client details for {client_mac}"))
                return client_obj.model_dump()  # type: ignore[no-any-return]

        # If not found in active, try all users
        response = await client.get(f"/ea/sites/{site_id}/stat/alluser")
        clients_data = response.get("data", []) if isinstance(response, dict) else response

        for client_data in clients_data:
            if validate_mac_address(client_data.get("mac", "")) == client_mac:
                client_obj = Client(**client_data)
                logger.info(sanitize_log_message(f"Retrieved client details for {client_mac}"))
                return client_obj.model_dump()  # type: ignore[no-any-return]

        raise ResourceNotFoundError("client", client_mac)


async def get_client_statistics(
    site_id: str, client_mac: str, settings: Settings
) -> dict[str, Any]:
    """Retrieve bandwidth and connection statistics for a client.

    Args:
        site_id: Site identifier
        client_mac: Client MAC address
        settings: Application settings

    Returns:
        Client statistics dictionary

    Raises:
        ResourceNotFoundError: If client not found
    """
    site_id = validate_site_id(site_id)
    client_mac = validate_mac_address(client_mac)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # Get from active clients
        response = await client.get(f"/ea/sites/{site_id}/sta")
        clients_data = response.get("data", []) if isinstance(response, dict) else response

        for client_data in clients_data:
            if validate_mac_address(client_data.get("mac", "")) == client_mac:
                # Extract statistics
                stats = {
                    "mac": client_mac,
                    "tx_bytes": client_data.get("tx_bytes", 0),
                    "rx_bytes": client_data.get("rx_bytes", 0),
                    "tx_packets": client_data.get("tx_packets", 0),
                    "rx_packets": client_data.get("rx_packets", 0),
                    "tx_rate": client_data.get("tx_rate"),
                    "rx_rate": client_data.get("rx_rate"),
                    "signal": client_data.get("signal"),
                    "rssi": client_data.get("rssi"),
                    "noise": client_data.get("noise"),
                    "uptime": client_data.get("uptime", 0),
                    "is_wired": client_data.get("is_wired", False),
                }
                logger.info(sanitize_log_message(f"Retrieved statistics for client {client_mac}"))
                return stats

        raise ResourceNotFoundError("client", client_mac)


async def list_active_clients(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List currently connected clients.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of clients to return
        offset: Number of clients to skip

    Returns:
        List of active client dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/sta")
        clients_data = response.get("data", []) if isinstance(response, dict) else response

        # Apply pagination
        paginated = clients_data[offset : offset + limit]

        # Parse into Client models
        clients = [Client(**c).model_dump() for c in paginated]

        logger.info(
            sanitize_log_message(f"Retrieved {len(clients)} active clients for site '{site_id}'")
        )
        return clients


async def search_clients(
    site_id: str,
    query: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """Search clients by MAC, IP, or hostname.

    Args:
        site_id: Site identifier
        query: Search query string
        settings: Application settings
        limit: Maximum number of clients to return
        offset: Number of clients to skip

    Returns:
        List of matching client dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # Concurrently query active and historical clients for better performance
        active_response, alluser_response = await asyncio.gather(
            client.get(f"/ea/sites/{site_id}/sta"),
            client.get(f"/ea/sites/{site_id}/stat/alluser"),
        )

        # Helper to extract data from API response
        def _extract_data(response: dict | list) -> list:
            """Extract data array from API response."""
            return response.get("data", []) if isinstance(response, dict) else response or []

        active_data = _extract_data(active_response)
        alluser_data = _extract_data(alluser_response)

        # Merge results: deduplicate by MAC, with active clients taking priority
        # Use dictionary comprehensions with walrus operator for concise, Pythonic code
        clients_by_mac = {mac: c for c in alluser_data if (mac := c.get("mac"))}
        clients_by_mac.update({mac: c for c in active_data if (mac := c.get("mac"))})

        clients_data = list(clients_by_mac.values())

        # Search by MAC, IP, hostname, or name (with None-safe handling)
        query_lower = query.lower()
        filtered = [
            c
            for c in clients_data
            if query_lower in (c.get("mac") or "").lower()
            or query_lower in (c.get("ip") or "").lower()
            or query_lower in (c.get("hostname") or "").lower()
            or query_lower in (c.get("name") or "").lower()
        ]

        # Apply pagination
        paginated = filtered[offset : offset + limit]

        # Parse into Client models
        clients = [Client(**c).model_dump() for c in paginated]

        logger.info(
            sanitize_log_message(
                f"Found {len(clients)} clients matching '{query}' in site '{site_id}'"
            )
        )
        return clients
