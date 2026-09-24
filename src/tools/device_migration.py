"""Device migration tools (local V1 legacy endpoints).

Two kinds of move are covered:

* **Between sites on this controller** -- ``cmd/sitemgr`` ``move-device``.
  The command takes the *target* site's 24-hex ``_id``, which only the
  legacy ``/api/self/sites`` listing returns (``list_sites`` returns
  Integration API UUIDs), so the target is resolved from that listing by
  ``_id``, short name, or description.
* **To another controller** -- ``cmd/devmgr`` ``migrate`` sets the
  device's inform URL to the new controller; the device then shows up
  there as pending adoption. ``cancel-migrate`` aborts a migration that
  has not completed.

Both commands key on the device MAC. Every tool resolves the device in the
source site first, so a typo fails before anything is sent and the preview
names the device that would move. Local gateway only.
"""

import re
from typing import Any
from urllib.parse import urlsplit

from ..api import UniFiClient
from ..config import APIType, Settings
from ..utils import (
    ResourceNotFoundError,
    ValidationError,
    coerce_bool,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_confirmation,
    validate_mac_address,
    validate_site_id,
)

_OBJECT_ID_RE = re.compile(r"^[a-f0-9]{24}$")
_SITES_ENDPOINT = "/proxy/network/api/self/sites"


def _ensure_local_api(settings: Settings) -> None:
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError(
            "Device migration tools require UNIFI_API_TYPE='local'. The "
            "cmd/devmgr and cmd/sitemgr commands are only reachable on the "
            "local gateway's legacy API."
        )


def _parse_device_ref(device_id: str) -> tuple[str | None, str | None]:
    """Split a device reference into (mac, object_id); exactly one is set."""
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValidationError("device_id cannot be empty")
    # MAC first: it accepts separator-less 12-hex, which is not an ObjectId.
    try:
        return validate_mac_address(device_id.strip()), None
    except ValidationError:
        pass
    lowered = device_id.strip().lower()
    if _OBJECT_ID_RE.match(lowered):
        return None, lowered
    raise ValidationError(
        f"Invalid device reference {device_id!r}: pass the device MAC address "
        "or its 24-hex device ID."
    )


def _data(response: Any) -> list[dict[str, Any]]:
    items = response if isinstance(response, list) else (response or {}).get("data", [])
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


async def _resolve_device(
    client: UniFiClient, settings: Settings, site_id: str, device_id: str
) -> dict[str, Any]:
    """Find the device record in the source site by MAC or device ID."""
    mac, object_id = _parse_device_ref(device_id)
    devices = _data(await client.get(settings.get_site_api_path(site_id, "stat/device")))
    for device in devices:
        if object_id is not None and device.get("_id") == object_id:
            return device
        if mac is not None:
            try:
                if validate_mac_address(str(device.get("mac", ""))) == mac:
                    return device
            except ValidationError:
                continue
    raise ResourceNotFoundError("device", device_id)


def _device_summary(device: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": device.get("_id"),
        "mac": validate_mac_address(str(device.get("mac", ""))),
        "name": device.get("name"),
        "model": device.get("model"),
        "type": device.get("type"),
        "state": device.get("state"),
    }


def _site_summary(site: dict[str, Any]) -> dict[str, Any]:
    return {"id": site.get("_id"), "name": site.get("name"), "description": site.get("desc")}


async def _resolve_target_site(client: UniFiClient, target_site: str) -> dict[str, Any]:
    """Resolve a site by _id, short name, or description (case-insensitive)."""
    sites = _data(await client.get(_SITES_ENDPOINT))
    wanted = target_site.strip().casefold()

    for key in ("_id", "name"):
        for site in sites:
            if str(site.get(key, "")).casefold() == wanted:
                return site

    by_desc = [s for s in sites if str(s.get("desc", "")).casefold() == wanted]
    if len(by_desc) > 1:
        names = ", ".join(str(s.get("name")) for s in by_desc)
        raise ValidationError(
            f"target_site {target_site!r} is ambiguous; it matches the description of "
            f"sites {names}. Pass the site short name or _id instead."
        )
    if by_desc:
        return by_desc[0]
    raise ResourceNotFoundError("site", target_site)


def _validate_inform_url(inform_url: str) -> str:
    """Accept only http(s)://host[:port]/inform, the controller inform endpoint."""
    error = (
        f"Invalid inform_url {inform_url!r}: expected http(s)://<controller-host>[:port]/inform, "
        "e.g. http://controller.example.net:8080/inform"
    )
    if not isinstance(inform_url, str):
        raise ValidationError(error)
    url = inform_url.strip()
    if not url or any(ch.isspace() for ch in url):
        raise ValidationError(error)
    parts = urlsplit(url)
    try:
        port_ok = parts.port is None or 0 < parts.port < 65536
    except ValueError:
        port_ok = False
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or not port_ok
        or parts.path != "/inform"
        or parts.query
        or parts.fragment
    ):
        raise ValidationError(error)
    return url


async def _send(
    *,
    operation: str,
    site_id: str,
    device_id: str,
    settings: Settings,
    confirm: bool | str,
    dry_run: bool | str,
    build: Any,
) -> dict[str, Any]:
    """Resolve the device, then preview or send the command ``build`` returns.

    ``build(client, device, mac)`` is awaited and returns
    ``(endpoint, payload, extra_result_fields)``.
    """
    validate_confirmation(confirm, operation.replace("_", " "), dry_run)
    dry_run_bool = coerce_bool(dry_run)
    logger = get_logger(__name__, settings.log_level)
    parameters: dict[str, Any] = {"site_id": site_id, "device_id": device_id}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()
            device = await _resolve_device(client, settings, site_id, device_id)
            summary = _device_summary(device)
            endpoint, payload, extra = await build(client, device, summary["mac"])
            parameters.update({k: v for k, v in payload.items() if k != "cmd"})

            if dry_run_bool:
                log_audit(
                    operation=operation,
                    parameters=parameters,
                    result="dry_run",
                    site_id=site_id,
                    dry_run=True,
                )
                return {"dry_run": True, "device": summary, "would_send": payload, **extra}

            await client.post(endpoint, json_data=payload)
            log_audit(operation=operation, parameters=parameters, result="success", site_id=site_id)
            logger.info(
                sanitize_log_message(f"{operation}: sent {payload['cmd']} for {summary['mac']}")
            )
            return {"success": True, "mac": summary["mac"], "device": summary, **extra}

    except Exception as e:
        logger.error(sanitize_log_message(f"{operation} failed for '{device_id}': {e}"))
        log_audit(operation=operation, parameters=parameters, result="failed", site_id=site_id)
        raise


async def move_device_to_site(
    site_id: str,
    device_id: str,
    target_site: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Move an adopted device to another site on this controller.

    The device keeps its adoption and reprovisions with the target site's
    configuration, so expect a brief outage on it (and on anything behind
    it, for a switch or gateway).

    Args:
        site_id: Site the device is in now
        device_id: Device MAC address (any common format) or 24-hex device ID
        target_site: Destination site, by its short name (e.g. ``default``),
            its description as shown in the UI, or its 24-hex ``_id``
        settings: Application settings (must be local)
        confirm: Must be True to move the device
        dry_run: Preview the move without sending it

    Returns:
        ``success``, the device, and the resolved ``target_site``. A dry run
        returns the device, the target, and the command it ``would_send``.
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)
    if not isinstance(target_site, str) or not target_site.strip():
        raise ValidationError("target_site cannot be empty")

    async def build(client: UniFiClient, device: dict[str, Any], mac: str) -> Any:
        target = await _resolve_target_site(client, target_site)
        if site_id.casefold() in (
            str(target.get("name", "")).casefold(),
            str(target.get("_id", "")).casefold(),
        ):
            raise ValidationError(f"Device {mac} is already in site {site_id!r}.")
        payload = {"cmd": "move-device", "site": target.get("_id"), "mac": mac}
        return (
            settings.get_site_api_path(site_id, "cmd/sitemgr"),
            payload,
            {"target_site": _site_summary(target)},
        )

    return await _send(
        operation="move_device_to_site",
        site_id=site_id,
        device_id=device_id,
        settings=settings,
        confirm=confirm,
        dry_run=dry_run,
        build=build,
    )


async def migrate_device(
    site_id: str,
    device_id: str,
    inform_url: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Migrate a device to another controller by changing its inform URL.

    After the command the device stops reporting to this controller and
    appears on the new one as pending adoption; adopt it there to finish.
    Until then ``cancel_device_migration`` can abort. An offline device
    only receives the command when it next checks in.

    Args:
        site_id: Site the device is in now
        device_id: Device MAC address (any common format) or 24-hex device ID
        inform_url: The new controller's inform endpoint,
            ``http(s)://<host>[:port]/inform`` (UniFi's default port is 8080)
        settings: Application settings (must be local)
        confirm: Must be True to migrate the device
        dry_run: Preview the migration without sending it

    Returns:
        ``success``, the device, ``inform_url`` and the ``next_step``, plus
        ``warnings`` when the device is offline.
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)
    url = _validate_inform_url(inform_url)

    async def build(client: UniFiClient, device: dict[str, Any], mac: str) -> Any:
        extra: dict[str, Any] = {
            "inform_url": url,
            "next_step": (
                "Adopt the device on the controller at the new inform URL. "
                "Until it is adopted there, cancel_device_migration can abort."
            ),
        }
        if device.get("state") != 1:
            extra["warnings"] = [
                f"Device {mac} is offline (state={device.get('state')}); it will only "
                "receive the migrate command when it next checks in."
            ]
        payload = {"cmd": "migrate", "mac": mac, "inform_url": url}
        return settings.get_site_api_path(site_id, "cmd/devmgr"), payload, extra

    return await _send(
        operation="migrate_device",
        site_id=site_id,
        device_id=device_id,
        settings=settings,
        confirm=confirm,
        dry_run=dry_run,
        build=build,
    )


async def cancel_device_migration(
    site_id: str,
    device_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Cancel a pending device migration (``cancel-migrate``).

    Only useful before the device has been adopted on the new controller.

    Args:
        site_id: Site the device was migrated from
        device_id: Device MAC address (any common format) or 24-hex device ID
        settings: Application settings (must be local)
        confirm: Must be True to send the cancel
        dry_run: Preview without sending

    Returns:
        ``success`` and the device, or the command a dry run ``would_send``.
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)

    async def build(client: UniFiClient, device: dict[str, Any], mac: str) -> Any:
        payload = {"cmd": "cancel-migrate", "mac": mac}
        return settings.get_site_api_path(site_id, "cmd/devmgr"), payload, {}

    return await _send(
        operation="cancel_device_migration",
        site_id=site_id,
        device_id=device_id,
        settings=settings,
        confirm=confirm,
        dry_run=dry_run,
        build=build,
    )
