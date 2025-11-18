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


async def authorize_guest(
    site_id: str,
    client_mac: str,
    duration: int,
    settings: Settings,
    upload_limit_kbps: int | None = None,
    download_limit_kbps: int | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Authorize a guest client for network access.

    Args:
        site_id: Site identifier
        client_mac: Client MAC address
        duration: Access duration in seconds
        settings: Application settings
        upload_limit_kbps: Upload speed limit in kbps
        download_limit_kbps: Download speed limit in kbps
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't authorize

    Returns:
        Authorization result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
    """
    site_id = validate_site_id(site_id)
    client_mac = validate_mac_address(client_mac)
    validate_confirmation(confirm, "client management operation")
    logger = get_logger(__name__, settings.log_level)

    parameters = {
        "site_id": site_id,
        "client_mac": client_mac,
        "duration": duration,
    }

    if dry_run:
        logger.info(
            f"DRY RUN: Would authorize guest client '{client_mac}' for {duration}s in site '{site_id}'"
        )
        log_audit(
            operation="authorize_guest",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_authorize": client_mac, "duration": duration}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Build authorization payload
            auth_data = {
                "action": "authorize-guest",
                "params": {
                    "duration": duration,
                },
            }

            if upload_limit_kbps is not None:
                auth_data["params"]["uploadLimit"] = upload_limit_kbps  # type: ignore[index]
            if download_limit_kbps is not None:
                auth_data["params"]["downloadLimit"] = download_limit_kbps  # type: ignore[index]

            # Authorize guest using new API endpoint
            await client.post(
                f"/integration/v1/sites/{site_id}/clients/{client_mac}/action",
                json_data=auth_data,
            )

            logger.info(
                f"Authorized guest client '{client_mac}' for {duration}s in site '{site_id}'"
            )
            log_audit(
                operation="authorize_guest",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "success": True,
                "client_mac": client_mac,
                "duration": duration,
                "message": f"Guest authorized for {duration} seconds",
            }

    except Exception as e:
        logger.error(f"Failed to authorize guest client '{client_mac}': {e}")
        log_audit(
            operation="authorize_guest",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def limit_bandwidth(
    site_id: str,
    client_mac: str,
    settings: Settings,
    upload_limit_kbps: int | None = None,
    download_limit_kbps: int | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply bandwidth restrictions to a client.

    Args:
        site_id: Site identifier
        client_mac: Client MAC address
        settings: Application settings
        upload_limit_kbps: Upload speed limit in kbps
        download_limit_kbps: Download speed limit in kbps
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't apply limits

    Returns:
        Bandwidth limit result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
    """
    site_id = validate_site_id(site_id)
    client_mac = validate_mac_address(client_mac)
    validate_confirmation(confirm, "client management operation")
    logger = get_logger(__name__, settings.log_level)

    parameters = {
        "site_id": site_id,
        "client_mac": client_mac,
        "upload_limit_kbps": upload_limit_kbps,
        "download_limit_kbps": download_limit_kbps,
    }

    if dry_run:
        logger.info(
            f"DRY RUN: Would apply bandwidth limits to client '{client_mac}' in site '{site_id}'"
        )
        log_audit(
            operation="limit_bandwidth",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {
            "dry_run": True,
            "would_limit": client_mac,
            "upload_limit_kbps": upload_limit_kbps,
            "download_limit_kbps": download_limit_kbps,
        }

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Build bandwidth limit payload
            limit_data = {
                "action": "limit-bandwidth",
                "params": {},
            }

            if upload_limit_kbps is not None:
                limit_data["params"]["uploadLimit"] = upload_limit_kbps  # type: ignore[index]
            if download_limit_kbps is not None:
                limit_data["params"]["downloadLimit"] = download_limit_kbps  # type: ignore[index]

            # Apply bandwidth limits using new API endpoint
            await client.post(
                f"/integration/v1/sites/{site_id}/clients/{client_mac}/action",
                json_data=limit_data,
            )

            logger.info(f"Applied bandwidth limits to client '{client_mac}' in site '{site_id}'")
            log_audit(
                operation="limit_bandwidth",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "success": True,
                "client_mac": client_mac,
                "upload_limit_kbps": upload_limit_kbps,
                "download_limit_kbps": download_limit_kbps,
                "message": "Bandwidth limits applied",
            }

    except Exception as e:
        logger.error(f"Failed to apply bandwidth limits to client '{client_mac}': {e}")
        log_audit(
            operation="limit_bandwidth",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
