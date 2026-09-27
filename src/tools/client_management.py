"""Client management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import (
    ResourceNotFoundError,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_confirmation,
    validate_mac_address,
    validate_site_id,
)


async def block_client(
    site_id: str,
    client_mac: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "client management operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "client_mac": client_mac}

    if dry_run:
        logger.info(
            sanitize_log_message(f"DRY RUN: Would block client '{client_mac}' in site '{site_id}'")
        )
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
            # Client now auto-unwraps the "data" field, so response is the actual data
            clients_data: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

            client_exists = any(
                validate_mac_address(c.get("mac", "")) == client_mac for c in clients_data
            )
            if not client_exists:
                raise ResourceNotFoundError("client", client_mac)

            # Block the client
            block_data = {"mac": client_mac, "cmd": "block-sta"}
            response = await client.post(f"/ea/sites/{site_id}/cmd/stamgr", json_data=block_data)

            logger.info(sanitize_log_message(f"Blocked client '{client_mac}' in site '{site_id}'"))
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
        logger.error(sanitize_log_message(f"Failed to block client '{client_mac}': {e}"))
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "client management operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "client_mac": client_mac}

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would unblock client '{client_mac}' in site '{site_id}'"
            )
        )
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

            logger.info(
                sanitize_log_message(f"Unblocked client '{client_mac}' in site '{site_id}'")
            )
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
        logger.error(sanitize_log_message(f"Failed to unblock client '{client_mac}': {e}"))
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "client management operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "client_mac": client_mac}

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would force reconnect for client '{client_mac}' in site '{site_id}'"
            )
        )
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
            # Client now auto-unwraps the "data" field, so response is the actual data
            clients_data: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

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

            logger.info(
                sanitize_log_message(
                    f"Forced reconnect for client '{client_mac}' in site '{site_id}'"
                )
            )
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
        logger.error(sanitize_log_message(f"Failed to reconnect client '{client_mac}': {e}"))
        log_audit(
            operation="reconnect_client",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def authorize_guest(
    site_id: str,
    client_id: str,
    duration: int,
    settings: Settings,
    upload_limit_kbps: int | None = None,
    download_limit_kbps: int | None = None,
    data_usage_limit_mbytes: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Authorize a guest client for network access.

    Hardware-verified 2026-09-27 against Integration API v10.6.106 (U7
    Express, Network 10.x): the spec route ``/clients/{id}/actions`` answers
    with a 400 ``api.request.unknown-type-id`` for unknown actions (endpoint
    exists and validates), while the legacy singular ``/action`` route
    returns 404 "No endpoint". Payload follows the spec's
    ``AUTHORIZE_GUEST_ACCESS`` discriminator: limits ride at the top level
    (no ``params`` wrapper).

    Args:
        site_id: Site identifier
        client_id: Client MAC address or Integration API client UUID
            (UUID verified live; controllers generally accept either)
        duration: Access duration in seconds (converted to the spec's
            timeLimitMinutes; 1 minute minimum, controller default applies
            when omitted — pass 0 to omit)
        settings: Application settings
        upload_limit_kbps: Upload rate limit (spec txRateLimitKbps, 2-100000)
        download_limit_kbps: Download rate limit (spec rxRateLimitKbps, 2-100000)
        data_usage_limit_mbytes: Data cap in MB (1-1048576)
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't authorize

    Returns:
        Authorization result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
    """
    site_id = validate_site_id(site_id)
    client_id = client_id.strip()
    if not client_id:
        raise ValueError("client_id must not be empty")
    validate_confirmation(confirm, "client management operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    if duration < 0:
        raise ValueError("duration must be >= 0 seconds")
    if upload_limit_kbps is not None and not 2 <= upload_limit_kbps <= 100000:
        raise ValueError("upload_limit_kbps must be between 2 and 100000")
    if download_limit_kbps is not None and not 2 <= download_limit_kbps <= 100000:
        raise ValueError("download_limit_kbps must be between 2 and 100000")
    if data_usage_limit_mbytes is not None and not 1 <= data_usage_limit_mbytes <= 1048576:
        raise ValueError("data_usage_limit_mbytes must be between 1 and 1048576")

    parameters = {
        "site_id": site_id,
        "client_id": client_id,
        "duration": duration,
    }

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would authorize guest client '{client_id}' for {duration}s in site '{site_id}'"
            )
        )
        log_audit(
            operation="authorize_guest",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_authorize": client_id, "duration": duration}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Spec: AUTHORIZE_GUEST_ACCESS with top-level optional limits
            payload: dict[str, Any] = {"action": "AUTHORIZE_GUEST_ACCESS"}
            if duration > 0:
                payload["timeLimitMinutes"] = max(1, -(-duration // 60))
            if upload_limit_kbps is not None:
                payload["txRateLimitKbps"] = upload_limit_kbps
            if download_limit_kbps is not None:
                payload["rxRateLimitKbps"] = download_limit_kbps
            if data_usage_limit_mbytes is not None:
                payload["dataUsageLimitMBytes"] = data_usage_limit_mbytes

            await client.post(
                f"/integration/v1/sites/{site_id}/clients/{client_id}/actions",
                json_data=payload,
            )

            logger.info(
                sanitize_log_message(
                    f"Authorized guest client '{client_id}' for {duration}s in site '{site_id}'"
                )
            )
            log_audit(
                operation="authorize_guest",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "success": True,
                "client_id": client_id,
                "duration": duration,
                "message": f"Guest authorized for {duration} seconds",
            }

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to authorize guest client '{client_id}': {e}"))
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Apply bandwidth restrictions to a client.

    Deprecated: the Integration API v10.6.106 defines no bandwidth-only
    client action (hardware-verified — the legacy endpoint 404s). This tool
    now raises ``NotImplementedError`` with migration guidance; use
    ``authorize_guest`` with ``upload_limit_kbps``/``download_limit_kbps``
    to carry limits at authorization time.

    Args:
        site_id: Site identifier
        client_mac: Client MAC address
        settings: Application settings
        upload_limit_kbps: Upload speed limit in kbps
        download_limit_kbps: Download speed limit in kbps
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't apply limits

    Raises:
        NotImplementedError: Always — no spec equivalent exists.
    """
    site_id = validate_site_id(site_id)
    client_mac = validate_mac_address(client_mac)
    validate_confirmation(confirm, "client management operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    # Validate bandwidth limits
    if upload_limit_kbps is not None and upload_limit_kbps <= 0:
        raise ValueError("Upload limit must be positive")
    if download_limit_kbps is not None and download_limit_kbps <= 0:
        raise ValueError("Download limit must be positive")

    parameters = {
        "site_id": site_id,
        "client_mac": client_mac,
        "upload_limit_kbps": upload_limit_kbps,
        "download_limit_kbps": download_limit_kbps,
    }

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would apply bandwidth limits to client '{client_mac}' in site '{site_id}'"
            )
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

    # The v10.6.106 Integration API defines exactly two client actions —
    # AUTHORIZE_GUEST_ACCESS and UNAUTHORIZE_GUEST_ACCESS — and no
    # bandwidth-only action. Hardware verification 2026-09-27 confirmed the
    # legacy "limit-bandwidth" endpoint the tool used returns 404 "No
    # endpoint" on current controllers. Bandwidth limits are carried by
    # authorize_guest's txRateLimitKbps/rxRateLimitKbps instead.
    raise NotImplementedError(
        "limit_bandwidth has no Integration API v10.6.106 equivalent — the "
        "legacy 'limit-bandwidth' endpoint returns 404 on current controllers "
        "(hardware-verified 2026-09-27). Apply limits while authorizing via "
        "authorize_guest(upload_limit_kbps=..., download_limit_kbps=...) "
        "instead. For an already-authorized guest, unauthorize and re-authorize "
        "with the desired limits."
    )
