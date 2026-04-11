"""Device management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models import Device
from ..utils import (
    APIError,
    ResourceNotFoundError,
    audit_action,
    get_logger,
    sanitize_log_message,
    validate_confirmation,
    validate_device_id,
    validate_limit_offset,
    validate_site_id,
)


async def get_device_details(site_id: str, device_id: str, settings: Settings) -> dict[str, Any]:
    """Get detailed information for a specific device.

    Uses the integration API so ``device_id`` matches the UUIDs returned by
    ``get_network_topology`` and other integration tools. Also accepts the
    legacy internal-stats MongoDB ObjectId (``_id``) as a fallback, so callers
    that already store the legacy ID continue to work.

    Args:
        site_id: Site identifier
        device_id: Device integration-API UUID (or legacy ``_id``)
        settings: Application settings

    Returns:
        Device details dictionary

    Raises:
        ResourceNotFoundError: If device not found
    """
    site_id = validate_site_id(site_id)
    device_id = validate_device_id(device_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)

        # Fast path: direct lookup on the integration API.
        try:
            response = await client.get(
                settings.get_integration_path(
                    f"sites/{resolved_site_id}/devices/{device_id}"
                )
            )
            if isinstance(response, dict):
                device_data = response.get("data", response)
                # Direct lookup returns a single device object; a list means
                # we hit a collection endpoint (mocked or otherwise) — fall
                # through to the list scan below.
                if isinstance(device_data, dict) and device_data:
                    logger.info(
                        sanitize_log_message(f"Retrieved device details for {device_id}")
                    )
                    return Device(**device_data).model_dump()  # type: ignore[no-any-return]
        except (ResourceNotFoundError, APIError) as e:
            # Direct lookup is a best-effort fast path. A 404 / missing-resource
            # response just means we should fall through to the paginated list
            # scan below. Any other exception (auth, network, pydantic) should
            # propagate — we intentionally don't swallow it.
            logger.debug(
                sanitize_log_message(
                    f"Direct device lookup returned no match, falling back to list scan: {e}"
                )
            )

        # Fallback: page through the integration devices list and match on
        # either ``id`` (integration UUID) or ``_id`` (legacy ObjectId).
        offset = 0
        while True:
            response = await client.get(
                settings.get_integration_path(f"sites/{resolved_site_id}/devices"),
                params={"offset": offset, "limit": 100},
            )
            devices_data = (
                response if isinstance(response, list) else response.get("data", [])
            )
            if not devices_data:
                break
            for device_data in devices_data:
                if (
                    device_data.get("id") == device_id
                    or device_data.get("_id") == device_id
                ):
                    logger.info(
                        sanitize_log_message(f"Retrieved device details for {device_id}")
                    )
                    return Device(**device_data).model_dump()  # type: ignore[no-any-return]
            if len(devices_data) < 100:
                break
            offset += len(devices_data)

        raise ResourceNotFoundError("device", device_id)


async def get_device_statistics(site_id: str, device_id: str, settings: Settings) -> dict[str, Any]:
    """Retrieve real-time statistics for a device.

    Args:
        site_id: Site identifier
        device_id: Device identifier
        settings: Application settings

    Returns:
        Device statistics dictionary
    """
    site_id = validate_site_id(site_id)
    device_id = validate_device_id(device_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/devices")
        devices_data = response.get("data", []) if isinstance(response, dict) else response

        for device_data in devices_data:
            if device_data.get("_id") == device_id:
                # Extract statistics
                stats = {
                    "device_id": device_id,
                    "uptime": device_data.get("uptime", 0),
                    "cpu": device_data.get("cpu"),
                    "mem": device_data.get("mem"),
                    "tx_bytes": device_data.get("tx_bytes", 0),
                    "rx_bytes": device_data.get("rx_bytes", 0),
                    "bytes": device_data.get("bytes", 0),
                    "state": device_data.get("state"),
                    "uplink_depth": device_data.get("uplink_depth"),
                }
                logger.info(sanitize_log_message(f"Retrieved statistics for device {device_id}"))
                return stats

        raise ResourceNotFoundError("device", device_id)


async def list_devices_by_type(
    site_id: str,
    device_type: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """Filter devices by type (AP, switch, gateway).

    Args:
        site_id: Site identifier
        device_type: Device type filter (uap, usw, ugw, etc.)
        settings: Application settings
        limit: Maximum number of devices to return
        offset: Number of devices to skip

    Returns:
        List of device dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/devices")
        devices_data = response.get("data", []) if isinstance(response, dict) else response

        # Filter by type
        filtered = [
            d
            for d in devices_data
            if d.get("type", "").lower() == device_type.lower()
            or device_type.lower() in d.get("model", "").lower()
        ]

        # Apply pagination
        paginated = filtered[offset : offset + limit]

        # Parse into Device models
        devices = [Device(**d).model_dump() for d in paginated]

        logger.info(
            sanitize_log_message(
                f"Retrieved {len(devices)} devices of type '{device_type}' for site '{site_id}'"
            )
        )
        return devices


async def search_devices(
    site_id: str,
    query: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """Search devices by name, MAC, or IP address.

    Args:
        site_id: Site identifier
        query: Search query string
        settings: Application settings
        limit: Maximum number of devices to return
        offset: Number of devices to skip

    Returns:
        List of matching device dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/devices")
        devices_data = response.get("data", []) if isinstance(response, dict) else response

        # Search by name, MAC, or IP
        query_lower = query.lower()
        filtered = [
            d
            for d in devices_data
            if query_lower in d.get("name", "").lower()
            or query_lower in d.get("mac", "").lower()
            or query_lower in d.get("ip", "").lower()
            or query_lower in d.get("model", "").lower()
        ]

        # Apply pagination
        paginated = filtered[offset : offset + limit]

        # Parse into Device models
        devices = [Device(**d).model_dump() for d in paginated]

        logger.info(sanitize_log_message(f"Found {len(devices)} devices matching '{query}' in site '{site_id}'"))
        return devices


async def list_pending_devices(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List devices awaiting adoption on the specified site.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of devices to return
        offset: Number of devices to skip

    Returns:
        List of pending device dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        response = await client.get(
            f"/integration/v1/sites/{site_id}/devices/pending", params=params
        )
        devices_data = response.get("data", [])

        # Parse into Device models
        devices = [Device(**d).model_dump() for d in devices_data]

        logger.info(sanitize_log_message(f"Retrieved {len(devices)} pending devices for site '{site_id}'"))
        return devices


async def adopt_device(
    site_id: str,
    device_id: str,
    settings: Settings,
    name: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Adopt a pending device onto the specified site.

    Args:
        site_id: Site identifier
        device_id: Device identifier to adopt
        settings: Application settings
        name: Optional device name
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Adopted device information
    """
    validate_confirmation(confirm, "adopt device", dry_run)
    site_id = validate_site_id(site_id)
    device_id = validate_device_id(device_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        payload = {}
        if name:
            payload["name"] = name

        if dry_run:
            logger.info(sanitize_log_message(f"[DRY RUN] Would adopt device {device_id}"))
            return {"dry_run": True, "device_id": device_id, "payload": payload}

        response = await client.post(
            f"/integration/v1/sites/{site_id}/devices/{device_id}/adopt", json_data=payload
        )
        data = response.get("data", response)

        # Audit the action
        await audit_action(
            settings,
            action_type="adopt_device",
            resource_type="device",
            resource_id=device_id,
            site_id=site_id,
            details={"name": name} if name else {},
        )

        logger.info(sanitize_log_message(f"Successfully adopted device {device_id}"))
        return Device(**data).model_dump()  # type: ignore[no-any-return]


async def execute_port_action(
    site_id: str,
    device_id: str,
    port_idx: int,
    action: str,
    settings: Settings,
    params: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Execute an action on a specific port of a device.

    Args:
        site_id: Site identifier
        device_id: Device identifier
        port_idx: Port index number
        action: Action to perform (power-cycle, enable, disable)
        settings: Application settings
        params: Additional action parameters
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Action result
    """
    validate_confirmation(confirm, f"execute port action '{action}'", dry_run)
    site_id = validate_site_id(site_id)
    device_id = validate_device_id(device_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        payload = {"action": action, "params": params or {}}

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would execute port action '{action}' on device {device_id} port {port_idx}"
                )
            )
            return {
                "dry_run": True,
                "device_id": device_id,
                "port_idx": port_idx,
                "payload": payload,
            }

        response = await client.post(
            f"/integration/v1/sites/{site_id}/devices/{device_id}/ports/{port_idx}/action",
            json_data=payload,
        )
        data = response.get("data", response)

        # Audit the action
        await audit_action(
            settings,
            action_type="port_action",
            resource_type="device_port",
            resource_id=f"{device_id}:{port_idx}",
            site_id=site_id,
            details={"action": action},
        )

        logger.info(sanitize_log_message(f"Successfully executed port action '{action}' on port {port_idx}"))
        return {"success": True, "action": action, "port_idx": port_idx, "result": data}
