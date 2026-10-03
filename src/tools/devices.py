"""Device management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models import Device, IntegrationDevice
from ..utils import (
    APIError,
    ResourceNotFoundError,
    ValidationError,
    audit_action,
    get_logger,
    sanitize_log_message,
    validate_confirmation,
    validate_device_id,
    validate_limit_offset,
    validate_mac_address,
    validate_site_id,
)


async def get_device_details(site_id: str, device_id: str, settings: Settings) -> dict[str, Any]:
    """Get detailed information for a specific device.

    Accepts any identifier a caller is likely to already hold, across the
    three ID spaces UniFi uses (issue #183 — the integration API only keys
    records by UUID, so a legacy ``_id`` or MAC input previously failed with
    "device not found" even though the device existed):

    * integration-API UUID (what ``get_network_topology`` returns) — direct
      detail-lookup fast path, then list-scan fallback;
    * legacy MongoDB ObjectId (``_id`` from the legacy stats surface) — the
      integration records carry no ``_id``, so it is resolved to a MAC via the
      legacy stats list and matched by MAC;
    * MAC address — matched against ``macAddress`` (integration shape) or
      ``mac`` (legacy shape), case/colon-insensitively.

    The response is parsed with ``IntegrationDevice`` rather than the legacy
    ``Device`` model, because the two endpoints report different shapes: the
    integration API sends ``macAddress`` (not ``mac``), a string ``state``
    (``"ONLINE"``, not ``1``) and no ``type`` field at all. Fields the
    controller does not report are omitted rather than returned as ``null``.

    Args:
        site_id: Site identifier
        device_id: Device integration-API UUID, legacy ``_id``, or MAC address
        settings: Application settings

    Returns:
        Device details dictionary

    Raises:
        ValidationError: If ``device_id`` matches no known identifier format
        ResourceNotFoundError: If device not found
    """
    site_id = validate_site_id(site_id)
    try:
        device_id = validate_device_id(device_id)
        is_mac = False
    except ValidationError:
        # Not a UUID/ObjectId — try the third ID space.
        device_id = validate_mac_address(device_id)
        is_mac = True
    logger = get_logger(__name__, settings.log_level)

    def _norm_mac(value: str) -> str:
        return value.lower().replace(":", "")

    async with UniFiClient(settings) as client:
        await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)

        async def _integration_devices() -> list[dict[str, Any]]:
            devices: list[dict[str, Any]] = []
            offset = 0
            while True:
                response = await client.get(
                    settings.get_integration_path(f"sites/{resolved_site_id}/devices"),
                    params={"offset": offset, "limit": 100},
                )
                batch = response if isinstance(response, list) else response.get("data", [])
                if not batch:
                    break
                devices.extend(batch)
                if len(batch) < 100:
                    break
                offset += len(batch)
            return devices

        # Fast path: direct detail lookup. Only meaningful for UUID/ObjectId
        # identifiers; a MAC is never a valid detail-route segment.
        if not is_mac:
            try:
                response = await client.get(
                    settings.get_integration_path(f"sites/{resolved_site_id}/devices/{device_id}")
                )
                if isinstance(response, dict):
                    device_data = response.get("data", response)
                    # A list means we hit a collection endpoint (mocked or
                    # otherwise) — fall through to the list scan below.
                    if isinstance(device_data, dict) and device_data:
                        logger.info(
                            sanitize_log_message(f"Retrieved device details for {device_id}")
                        )
                        return IntegrationDevice.model_validate(device_data).model_dump(
                            exclude_none=True
                        )
            except (ResourceNotFoundError, APIError) as e:
                # Best-effort fast path: a 404/missing-resource response just
                # means we fall through to the list scan. Any other exception
                # (auth, network, pydantic) propagates — not swallowed.
                logger.debug(
                    sanitize_log_message(
                        f"Direct device lookup returned no match, falling back to list scan: {e}"
                    )
                )

        devices = await _integration_devices()

        # Legacy ObjectId resolution: integration records carry no ``_id``, so
        # map the ObjectId to a MAC through the legacy stats list and match on
        # MAC below.
        mac_probe: str | None = _norm_mac(device_id) if is_mac else None
        if mac_probe is None and len(device_id) == 24 and all(
            c in "0123456789abcdef" for c in device_id
        ):
            try:
                legacy = await client.get(f"/ea/sites/{resolved_site_id}/devices")
                legacy_items = legacy if isinstance(legacy, list) else legacy.get("data", [])
                for item in legacy_items:
                    if item.get("_id") == device_id and item.get("mac"):
                        mac_probe = _norm_mac(item["mac"])
                        break
            except (ResourceNotFoundError, APIError) as e:
                logger.debug(
                    sanitize_log_message(f"Legacy ObjectId resolution failed, continuing: {e}")
                )

        for device_data in devices:
            if is_mac:
                reported = device_data.get("macAddress") or device_data.get("mac") or ""
                if reported and _norm_mac(reported) == mac_probe:
                    logger.info(sanitize_log_message(f"Retrieved device details for {device_id}"))
                    return IntegrationDevice.model_validate(device_data).model_dump(
                        exclude_none=True
                    )
            elif (
                device_data.get("id") == device_id
                or device_data.get("_id") == device_id
                or (
                    mac_probe is not None
                    and bool(device_data.get("macAddress") or device_data.get("mac"))
                    and _norm_mac(device_data.get("macAddress") or device_data["mac"]) == mac_probe
                )
            ):
                logger.info(sanitize_log_message(f"Retrieved device details for {device_id}"))
                return IntegrationDevice.model_validate(device_data).model_dump(exclude_none=True)

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


_INTEGRATION_PAGE_SIZE = 100

# The integration API reports no ``type``. The capability names under ``features`` stand in for
# the legacy ``uap`` / ``usw`` values.
_TYPE_FEATURES = {"uap": "accessPoint", "usw": "switching"}


async def _list_integration_devices(
    client: UniFiClient, settings: Settings, site_id: str
) -> list[dict[str, Any]]:
    """List every device of a site through the integration API.

    In local mode the client rewrites ``/ea/sites/{site}/devices`` to the controller's legacy
    route, which does not accept an API key (issue #187). The integration API does, in every
    API mode.

    Args:
        client: Authenticated UniFi client
        settings: Application settings
        site_id: Site identifier, resolved to the controller's UUID before the request

    Returns:
        Device records in the integration API's shape
    """
    resolved_site_id = await client.resolve_site_id(site_id)
    devices: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/devices"),
            params={"offset": offset, "limit": _INTEGRATION_PAGE_SIZE},
        )
        batch = response if isinstance(response, list) else response.get("data", [])
        if not batch:
            break
        devices.extend(batch)
        if len(batch) < _INTEGRATION_PAGE_SIZE:
            break
        offset += len(batch)
    return devices


def _device_matches_type(device: dict[str, Any], device_type: str) -> bool:
    """Check whether a device matches a requested type.

    Args:
        device: Device record from the integration API
        device_type: ``uap`` or ``usw``, a capability name, or part of the model

    Returns:
        True if the device matches
    """
    wanted = device_type.lower()
    # ``features`` is an object of capabilities or, on some devices, a list of their names
    capabilities = {str(name).lower() for name in device.get("features") or []}
    return (
        wanted == (device.get("type") or "").lower()
        or _TYPE_FEATURES.get(wanted, wanted).lower() in capabilities
        or wanted in (device.get("model") or "").lower()
    )


async def list_devices_by_type(
    site_id: str,
    device_type: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """Filter devices by type (AP, switch, gateway).

    Devices are read from the integration API, which reports no ``type`` field. ``uap`` and
    ``usw`` match the ``accessPoint`` and ``switching`` capabilities. Any other value matches a
    capability name or part of the model, for example ``udm``.

    Args:
        site_id: Site identifier
        device_type: Device type filter (uap, usw, a capability name, or part of the model)
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

        devices_data = await _list_integration_devices(client, settings, site_id)

        # Filter by type
        filtered = [d for d in devices_data if _device_matches_type(d, device_type)]

        # Apply pagination
        paginated = filtered[offset : offset + limit]

        # Parse into IntegrationDevice models, the shape the integration API reports
        devices = [
            IntegrationDevice.model_validate(d).model_dump(exclude_none=True) for d in paginated
        ]

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

    Devices are read from the integration API, which reports ``macAddress`` and ``ipAddress``.
    The legacy ``mac`` and ``ip`` keys are matched as well.

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

        devices_data = await _list_integration_devices(client, settings, site_id)

        # Search by name, MAC, IP or model, ignoring fields the controller reports as null
        query_lower = query.lower()
        filtered = [
            d
            for d in devices_data
            if any(
                query_lower in str(value).lower()
                for value in (
                    d.get("name"),
                    d.get("macAddress") or d.get("mac"),
                    d.get("ipAddress") or d.get("ip"),
                    d.get("model"),
                )
                if value
            )
        ]

        # Apply pagination
        paginated = filtered[offset : offset + limit]

        # Parse into IntegrationDevice models, the shape the integration API reports
        devices = [
            IntegrationDevice.model_validate(d).model_dump(exclude_none=True) for d in paginated
        ]

        logger.info(
            sanitize_log_message(
                f"Found {len(devices)} devices matching '{query}' in site '{site_id}'"
            )
        )
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

        # The Integration v1 API has no pending-devices route: a request to
        # /devices/pending matches /devices/{deviceId} and is rejected with
        # "'pending' is not a valid 'deviceId' value". Unadopted devices are
        # only visible on the legacy stat route, as entries with adopted=false.
        response = await client.get(f"/ea/sites/{site_id}/stat/device")
        devices_data = response if isinstance(response, list) else response.get("data", [])

        pending = [d for d in devices_data if d.get("adopted") is False]
        paginated = pending[offset : offset + limit]

        # The legacy payload is what the legacy Device model describes, so no
        # shape mismatch here (unlike the Integration v1 routes, see #109).
        devices = [Device(**d).model_dump() for d in paginated]

        logger.info(
            sanitize_log_message(f"Retrieved {len(devices)} pending devices for site '{site_id}'")
        )
        return devices


async def adopt_device(
    site_id: str,
    mac: str,
    settings: Settings,
    ignore_device_limit: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Adopt a pending device onto the specified site.

    Hardware-verified 2026-09-27 against Integration API v10.6.106 (U7
    Express, Network 10.x): the spec endpoint answers with
    ``api.device.adoption.unknown-device`` for unknown MACs (i.e. it exists
    and validates), while the legacy ``/devices/{id}/adopt`` route the tool
    used before returns 404 "No endpoint" on current controllers.

    Args:
        site_id: Site identifier
        mac: Device MAC address (spec identifies the device by MAC, not ID)
        settings: Application settings
        ignore_device_limit: Bypass the controller's device-count limit
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Adoption result information
    """
    validate_confirmation(confirm, "adopt device", dry_run)
    site_id = validate_site_id(site_id)
    mac = validate_mac_address(mac)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        payload = {"macAddress": mac, "ignoreDeviceLimit": bool(ignore_device_limit)}

        if dry_run:
            logger.info(sanitize_log_message(f"[DRY RUN] Would adopt device {mac}"))
            return {"dry_run": True, "mac": mac, "payload": payload}

        response = await client.post(
            f"/integration/v1/sites/{site_id}/devices", json_data=payload
        )
        data = response[0] if isinstance(response, list) and response else (
            response.get("data", response) if isinstance(response, dict) else {}
        )

        await audit_action(
            settings,
            action_type="adopt_device",
            resource_type="device",
            resource_id=mac,
            site_id=site_id,
            details={"ignore_device_limit": ignore_device_limit},
        )

        logger.info(sanitize_log_message(f"Successfully adopted device {mac}"))
        return {"success": True, "mac": mac, "result": data}



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

    Hardware-verified 2026-09-27 against Integration API v10.6.106 (U7
    Express, Network 10.x): the spec route
    ``/devices/{id}/interfaces/ports/{idx}/actions`` answers with a 400
    ``api.request.unknown-type-id`` for unknown actions (endpoint exists and
    validates), while the legacy ``/ports/{idx}/action`` route returns 404
    "No endpoint".

    The v10.6.106 spec defines exactly one port action: ``POWER_CYCLE``
    (PoE power-cycle). ``params`` is not a spec property and is accepted
    for backwards compatibility but never sent.

    Args:
        site_id: Site identifier
        device_id: Device identifier
        port_idx: Port index number
        action: ``power_cycle`` (the only Integration API port action)
        settings: Application settings
        params: Deprecated, ignored (no spec carrier)
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Action result
    """
    validate_confirmation(confirm, f"execute port action '{action}'", dry_run)
    site_id = validate_site_id(site_id)
    device_id = validate_device_id(device_id)
    logger = get_logger(__name__, settings.log_level)

    normalized = action.strip().upper().replace("-", "_")
    if normalized != "POWER_CYCLE":
        raise ValidationError(
            f"unsupported port action '{action}': the Integration API v10.6.106 "
            "defines only 'power_cycle'"
        )

    async with UniFiClient(settings) as client:
        await client.authenticate()

        payload = {"action": "POWER_CYCLE"}

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would power-cycle port {port_idx} on device {device_id}"
                )
            )
            return {
                "dry_run": True,
                "device_id": device_id,
                "port_idx": port_idx,
                "payload": payload,
            }

        response = await client.post(
            f"/integration/v1/sites/{site_id}/devices/{device_id}"
            f"/interfaces/ports/{port_idx}/actions",
            json_data=payload,
        )
        if isinstance(response, list):
            data = response[0] if response else {}
        else:
            _raw = response.get("data", response)
            data = _raw[0] if isinstance(_raw, list) else _raw

        # Audit the action
        await audit_action(
            settings,
            action_type="port_action",
            resource_type="device_port",
            resource_id=f"{device_id}:{port_idx}",
            site_id=site_id,
            details={"action": "POWER_CYCLE"},
        )

        logger.info(
            sanitize_log_message(f"Successfully power-cycled port {port_idx}")
        )
        return {"success": True, "action": "POWER_CYCLE", "port_idx": port_idx, "result": data}
