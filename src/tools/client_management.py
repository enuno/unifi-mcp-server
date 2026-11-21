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
from ..utils.tool_kind import write_tool


@write_tool
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


@write_tool
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


@write_tool
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


@write_tool
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


@write_tool
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


#: The controller's per-client command vocabulary. ``cmd/stamgr`` is the
#: legacy route and takes either a single ``mac`` or a ``macs`` list.
_STAMGR_CMDS = {
    "block": "block-sta",
    "unblock": "unblock-sta",
    "reconnect": "kick-sta",
    "forget": "forget-sta",
}

#: Commands that accept the ``macs`` list shape, so N clients go in one
#: request. ``kick-sta`` does NOT: verified live on Network 10.6.111 it reads
#: only the singular ``mac`` field and answers HTTP 500 when ``mac`` is
#: absent, so a reconnect fan-out uses one request per client.
_BATCH_CMDS = frozenset({"block-sta", "unblock-sta", "forget-sta"})

#: Upper bound on one bulk call, so a mistyped argument cannot turn into a
#: request the controller will not answer.
_MAX_BULK_CLIENTS = 100


@write_tool
async def bulk_client_action(
    site_id: str,
    client_macs: list[str],
    action: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Apply one action to several clients at once, reporting each client.

    Network 11 adds bulk client editing. Live-verified 2026-11-21 against
    Network 10.6.111 (UniFi OS): the legacy ``cmd/stamgr`` route accepts a
    ``macs`` list, so ``block-sta``, ``unblock-sta`` and ``forget-sta`` all
    take N clients in a single request and answer with one record per
    client. ``kick-sta`` is the exception — it reads only the singular
    ``mac`` field — so a reconnect is issued one request per client.

    Unknown MACs are reported and left alone. The controller does not
    validate them: ``block-sta`` on a MAC that has never been seen
    **creates** a blocked client record, so a typo would otherwise leave a
    phantom block behind. Every requested MAC is checked against the site
    inventory first and only the known ones are sent.

    Args:
        site_id: Site identifier
        client_macs: Client MAC addresses to act on
        action: One of ``block``, ``unblock``, ``reconnect``, ``forget``
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, report what would happen without acting

    Returns:
        Per-client results: ``results`` lists every requested client with its
        outcome, ``not_found`` the ones the site does not know, and the
        counts of what was applied and what failed.

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ValidationError: If the action is unknown or the list is empty
    """
    site_id = validate_site_id(site_id)
    action = action.strip().lower()
    if action not in _STAMGR_CMDS:
        raise ValueError(f"action must be one of {sorted(_STAMGR_CMDS)}, got '{action}'")
    if not client_macs:
        raise ValueError("client_macs must not be empty")
    if len(client_macs) > _MAX_BULK_CLIENTS:
        raise ValueError(
            f"client_macs accepts at most {_MAX_BULK_CLIENTS} clients, got {len(client_macs)}"
        )

    macs: list[str] = []
    for raw in client_macs:
        mac = validate_mac_address(raw)
        if mac not in macs:
            macs.append(mac)

    validate_confirmation(confirm, "bulk client management operation", dry_run)
    logger = get_logger(__name__, settings.log_level)
    cmd = _STAMGR_CMDS[action]

    parameters = {"site_id": site_id, "action": action, "client_count": len(macs)}

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would apply '{action}' to {len(macs)} client(s) in site '{site_id}'"
            )
        )
        log_audit(
            operation="bulk_client_action",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {
            "dry-run": True,
            "action": action,
            "command": cmd,
            "client_count": len(macs),
            "batch_request": cmd in _BATCH_CMDS,
        }

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Resolve the requested MACs against the site inventory. A MAC the
            # controller has never seen is not an error to fail on — it is a
            # per-client result, and it must not be sent, because block-sta
            # would create a record for it.
            response = await client.get(f"/ea/sites/{site_id}/stat/alluser")
            clients_data: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )
            known = {validate_mac_address(c.get("mac", "")) for c in clients_data if c.get("mac")}
            present = [m for m in macs if m in known]
            absent = [m for m in macs if m not in known]

            results: list[dict[str, Any]] = [{"mac": m, "status": "not_found"} for m in absent]

            if present:
                if cmd in _BATCH_CMDS:
                    payload = await client.post(
                        f"/ea/sites/{site_id}/cmd/stamgr",
                        json_data={"cmd": cmd, "macs": present},
                    )
                    body = payload.get("data", []) if isinstance(payload, dict) else payload
                    entries = body if isinstance(body, list) else []
                    seen: set[str] = set()
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        mac = str(entry.get("mac", "")).lower()
                        seen.add(mac)
                        results.append(
                            {
                                "mac": mac,
                                "status": "ok",
                                "blocked": entry.get("blocked"),
                            }
                        )
                    for mac in present:
                        if mac not in seen:
                            results.append({"mac": mac, "status": "no_result"})
                else:
                    # kick-sta has no batch form: one request per client.
                    for mac in present:
                        try:
                            payload = await client.post(
                                f"/ea/sites/{site_id}/cmd/stamgr",
                                json_data={"cmd": cmd, "mac": mac},
                            )
                            body = payload.get("data", []) if isinstance(payload, dict) else payload
                            entries = body if isinstance(body, list) else []
                            blocked = (
                                entries[0].get("blocked")
                                if entries and isinstance(entries[0], dict)
                                else None
                            )
                            results.append({"mac": mac, "status": "ok", "blocked": blocked})
                        except Exception as exc:  # noqa: BLE001 - one client, not the batch
                            results.append(
                                {"mac": mac, "status": "failed", "error": str(exc)[:200]}
                            )

            applied = [r for r in results if r["status"] == "ok"]
            failed = [r for r in results if r["status"] in ("failed", "no_result")]
            not_found = [r for r in results if r["status"] == "not_found"]

            logger.info(
                sanitize_log_message(
                    f"Applied '{action}' to {len(applied)} of {len(macs)} client(s) "
                    f"in site '{site_id}'"
                )
            )
            log_audit(
                operation="bulk_client_action",
                parameters=parameters,
                result="success" if not failed else "partial",
                site_id=site_id,
            )

            return {
                "success": not failed,
                "action": action,
                "command": cmd,
                "batch_request": cmd in _BATCH_CMDS,
                "requested": len(macs),
                "applied": len(applied),
                "failed": len(failed),
                "not_found": len(not_found),
                "results": sorted(results, key=lambda r: r["mac"]),
            }

    except Exception as e:
        logger.error(
            sanitize_log_message(
                f"Failed to apply '{action}' to {len(macs)} client(s) in site '{site_id}': {e}"
            )
        )
        log_audit(
            operation="bulk_client_action",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
