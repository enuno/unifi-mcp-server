"""Client management MCP tools."""

import asyncio
from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models import Client
from ..utils import (
    ResourceNotFoundError,
    ValidationError,
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
                return client_obj.model_dump()

        # If not found in active, try all users
        response = await client.get(f"/ea/sites/{site_id}/stat/alluser")
        clients_data = response.get("data", []) if isinstance(response, dict) else response

        for client_data in clients_data:
            if validate_mac_address(client_data.get("mac", "")) == client_mac:
                client_obj = Client(**client_data)
                logger.info(sanitize_log_message(f"Retrieved client details for {client_mac}"))
                return client_obj.model_dump()

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

        # Wired clients report counters under the "wired-" keys; the plain
        # keys are absent or zero for them. The fallback is gated on
        # is_wired so a wireless client's legitimate zero is never replaced
        # by a stray wired- value.
        def counter(record: dict, field: str) -> int:
            plain = record.get(field)
            if record.get("is_wired") is True and not plain:
                return record.get(f"wired-{field}") or 0
            return plain or 0

        for client_data in clients_data:
            if validate_mac_address(client_data.get("mac", "")) == client_mac:
                stats = {
                    "mac": client_mac,
                    "tx_bytes": counter(client_data, "tx_bytes"),
                    "rx_bytes": counter(client_data, "rx_bytes"),
                    "tx_packets": counter(client_data, "tx_packets"),
                    "rx_packets": counter(client_data, "rx_packets"),
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


async def list_client_rf_health(
    site_id: str,
    settings: Settings,
    min_retry_pct: float | None = None,
) -> list[dict[str, Any]]:
    """Per-client RF health: signal, rates, and retry percentages.

    Retries are the leading indicator of airtime trouble -- they climb
    before latency degrades and before satisfaction drops. The sta
    route carries lifetime retry/packet counters per association; this
    tool passes them through with a computed transmit retry percentage,
    wireless clients only, worst first.

    The percentage is retries as a share of total transmit attempts::

        tx_retry_pct = tx_retries / (tx_packets + tx_retries) * 100

    stated explicitly because the other plausible reading -- retries per
    successful packet, ``tx_retries / tx_packets`` -- yields a visibly
    different number for the same client, and callers comparing against
    another tool need to know which one this is.

    It will not match the controller UI, and not because of the
    denominator. The UI's "TX Retries" is a live rate over a short recent
    window: measured on one client it read 12.1%, briefly, while the
    lifetime figure was 24.7% and the two candidate denominators gave
    24.7% and 32.8%. That client's hourly rate ranged from 4.4% to 34.0%
    across a single day, so the UI value moves between glances and the
    lifetime one barely does. Neither is wrong; they answer different
    questions. This tool reports the association's whole history, which
    is stable enough to compare between clients but slow to react -- to
    see a change, compare two readings rather than one against the UI.

    Args:
        site_id: Site identifier
        settings: Application settings
        min_retry_pct: Optional floor in percent, 0..100; clients
            retrying less than this are dropped (e.g. 5 to see only
            strugglers). A client with no transmit activity has no
            percentage to compare, so any floor -- including 0 --
            excludes it.

    Returns:
        List of wireless-client health dictionaries, highest transmit
        retry percentage first
    """
    site_id = validate_site_id(site_id)
    if min_retry_pct is not None:
        # Fail on the argument, not later on a comparison against a str,
        # which raises TypeError from inside a list comprehension and
        # tells the caller nothing useful.
        try:
            min_retry_pct = float(min_retry_pct)
        except (TypeError, ValueError):
            raise ValidationError(
                f"min_retry_pct must be a number, got {min_retry_pct!r}"
            ) from None
        if not 0 <= min_retry_pct <= 100:
            raise ValidationError(f"min_retry_pct must be between 0 and 100, got {min_retry_pct}")
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/sta")
        raw = response.get("data", []) if isinstance(response, dict) else response

        rows: list[dict[str, Any]] = []
        for c in raw if isinstance(raw, list) else []:
            if not isinstance(c, dict) or c.get("is_wired") or not c.get("radio"):
                continue
            # The sta payload can carry entries with no MAC; search_clients
            # already skips those. A row keyed by None cannot be correlated
            # with anything, so it is worse than absent.
            if not c.get("mac"):
                continue
            tx_packets = c.get("tx_packets") or 0
            tx_retries = c.get("tx_retries") or 0
            attempts = tx_packets + tx_retries
            retry_pct = round(100.0 * tx_retries / attempts, 1) if attempts else None
            rows.append(
                {
                    "mac": c.get("mac"),
                    "name": c.get("name") or c.get("hostname"),
                    "ap_mac": c.get("ap_mac"),
                    "radio": c.get("radio"),
                    "channel": c.get("channel"),
                    "signal": c.get("signal"),
                    "tx_rate": c.get("tx_rate"),
                    "rx_rate": c.get("rx_rate"),
                    "tx_packets": tx_packets,
                    "tx_retries": tx_retries,
                    "tx_retry_pct": retry_pct,
                    "rx_packets": c.get("rx_packets"),
                    "satisfaction": c.get("satisfaction"),
                    "uptime": c.get("uptime"),
                }
            )

        if min_retry_pct is not None:
            rows = [r for r in rows if (r["tx_retry_pct"] or 0) >= min_retry_pct]

        rows.sort(
            key=lambda r: r["tx_retry_pct"] if r["tx_retry_pct"] is not None else -1.0, reverse=True
        )
        # The site is the caller's own argument and adds nothing to the
        # log line, while including it trips CodeQL's clear-text-logging
        # rule on new code (sanitize_log_message masks MACs and IPs, not
        # site identifiers, and masking does not break a taint path).
        logger.info(sanitize_log_message(f"RF health for {len(rows)} wireless clients"))
        return rows
