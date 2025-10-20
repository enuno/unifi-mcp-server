"""Client management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import (
    ResourceNotFoundError,
    get_logger,
    log_audit,
    validate_confirmation,
    validate_mac_address,
    validate_site_id,
)


async def block_client(
    site_id: str,
    client_mac: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Block a client from accessing the network.

    Args:
        site_id: Site identifier
        client_mac: Client MAC address
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't block the client

    Returns:
        Block result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If client not found
    """
    site_id = validate_site_id(site_id)
    client_mac = validate_mac_address(client_mac)
    validate_confirmation(confirm, "client management operation")
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "client_mac": client_mac}

    if dry_run:
        logger.info(f"DRY RUN: Would block client '{client_mac}' in site '{site_id}'")
        log_audit(
            operation="block_client",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_block": client_mac}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Verify client exists (check both active and all users)
            response = await client.get(f"/ea/sites/{site_id}/stat/alluser")
            clients_data: list[dict[str, Any]] = response.get("data", [])

            client_exists = any(
                validate_mac_address(c.get("mac", "")) == client_mac for c in clients_data
            )
            if not client_exists:
                raise ResourceNotFoundError("client", client_mac)

            # Block the client
            block_data = {"mac": client_mac, "cmd": "block-sta"}
            response = await client.post(f"/ea/sites/{site_id}/cmd/stamgr", json_data=block_data)

            logger.info(f"Blocked client '{client_mac}' in site '{site_id}'")
            log_audit(
                operation="block_client",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "success": True,
                "client_mac": client_mac,
                "message": "Client blocked from network",
            }

    except Exception as e:
        logger.error(f"Failed to block client '{client_mac}': {e}")
        log_audit(
            operation="block_client",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def unblock_client(
    site_id: str,
    client_mac: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Unblock a previously blocked client.

    Args:
        site_id: Site identifier
        client_mac: Client MAC address
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't unblock the client

    Returns:
        Unblock result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
    """
    site_id = validate_site_id(site_id)
    client_mac = validate_mac_address(client_mac)
    validate_confirmation(confirm, "client management operation")
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "client_mac": client_mac}

    if dry_run:
        logger.info(f"DRY RUN: Would unblock client '{client_mac}' in site '{site_id}'")
        log_audit(
            operation="unblock_client",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_unblock": client_mac}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Unblock the client
            unblock_data = {"mac": client_mac, "cmd": "unblock-sta"}
            await client.post(f"/ea/sites/{site_id}/cmd/stamgr", json_data=unblock_data)

            logger.info(f"Unblocked client '{client_mac}' in site '{site_id}'")
            log_audit(
                operation="unblock_client",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "success": True,
                "client_mac": client_mac,
                "message": "Client unblocked",
            }

    except Exception as e:
        logger.error(f"Failed to unblock client '{client_mac}': {e}")
        log_audit(
            operation="unblock_client",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def reconnect_client(
    site_id: str,
    client_mac: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Force a client to reconnect (disconnect and re-authenticate).

    Args:
        site_id: Site identifier
        client_mac: Client MAC address
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't force reconnection

    Returns:
        Reconnect result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If client not found
    """
    site_id = validate_site_id(site_id)
    client_mac = validate_mac_address(client_mac)
    validate_confirmation(confirm, "client management operation")
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "client_mac": client_mac}

    if dry_run:
        logger.info(f"DRY RUN: Would force reconnect for client '{client_mac}' in site '{site_id}'")
        log_audit(
            operation="reconnect_client",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_reconnect": client_mac}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Verify client is currently connected
            response = await client.get(f"/ea/sites/{site_id}/sta")
            clients_data: list[dict[str, Any]] = response.get("data", [])

            client_exists = any(
                validate_mac_address(c.get("mac", "")) == client_mac for c in clients_data
            )
            if not client_exists:
                raise ResourceNotFoundError("active client", client_mac)

            # Force client reconnection
            reconnect_data = {"mac": client_mac, "cmd": "kick-sta"}
            response = await client.post(
                f"/ea/sites/{site_id}/cmd/stamgr", json_data=reconnect_data
            )

            logger.info(f"Forced reconnect for client '{client_mac}' in site '{site_id}'")
            log_audit(
                operation="reconnect_client",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "success": True,
                "client_mac": client_mac,
                "message": "Client forced to reconnect",
            }

    except Exception as e:
        logger.error(f"Failed to reconnect client '{client_mac}': {e}")
        log_audit(
            operation="reconnect_client",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
