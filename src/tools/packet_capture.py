"""Gateway packet-capture tools for direct local UniFi consoles."""

import hashlib
import os
from pathlib import Path
from typing import Any

from ..api import UniFiClient
from ..config import APIType, Settings
from ..utils import (
    ValidationError,
    coerce_bool,
    validate_confirmation,
    validate_mac_address,
    validate_site_id,
)
from ..utils.tool_kind import read_tool, write_tool


def _require_local(settings: Settings) -> None:
    """Reject modes without an observed packet-capture route."""
    if settings.api_type != APIType.LOCAL:
        raise ValidationError(
            "Packet capture requires direct local-console access; "
            "no Cloud Connector route is documented"
        )


def _capture_base(site_id: str, settings: Settings) -> str:
    """Return the observed site-scoped packet-capture route prefix.

    Args:
        site_id: Site short name, already passed through
            :func:`validate_site_id` by the caller.
        settings: Application settings.

    Returns:
        The ``/proxy/network/v2/api/site/{site}`` prefix for capture routes.
    """
    _require_local(settings)
    return settings.get_v2_api_path(site_id)


def _resolve_capture_destination(output_path: str, settings: Settings) -> Path:
    """Confine a capture filename to the configured download directory."""
    name = os.path.basename(str(output_path).strip())
    if not name or name in (".", ".."):
        raise ValidationError(f"Invalid output_path: {output_path!r} (no filename component)")
    base_dir = Path(settings.packet_capture_download_dir).expanduser().resolve()
    destination = (base_dir / name).resolve()
    if destination.parent != base_dir:
        raise ValidationError(f"Refusing to write outside {base_dir}: {output_path!r}")
    return destination


def _write_capture(destination: Path, content: bytes) -> None:
    """Write sensitive capture bytes privately without following symlinks."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags, 0o600)
    try:
        os.write(descriptor, content)
    finally:
        os.close(descriptor)


@write_tool
async def start_gateway_packet_capture(
    site_id: str,
    gateway_mac: str,
    network_id: str,
    settings: Settings,
    duration_seconds: int = 60,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Start a bounded wired packet capture on a site's gateway.

    Args:
        site_id: Network site short name, such as ``default``.
        gateway_mac: Gateway MAC address.
        network_id: Controller network object ID to capture.
        settings: Application settings.
        duration_seconds: Capture duration from 30 through 300 seconds.
        confirm: Must be true to start the capture.
        dry_run: Return the request payload without starting a capture.

    Returns:
        The controller response and capture target metadata.

    Raises:
        ValidationError: If confirmation is missing, an argument is invalid,
            or cloud mode is selected.
    """
    validate_confirmation(confirm, "start gateway packet capture", dry_run)
    site_id = validate_site_id(site_id)
    base = _capture_base(site_id, settings)
    gateway_mac = validate_mac_address(gateway_mac)
    network_id = str(network_id).strip()
    if not network_id:
        raise ValidationError("network_id must not be empty")
    if not 30 <= duration_seconds <= 300:
        raise ValidationError("duration_seconds must be between 30 and 300")
    payload = {
        "mac": gateway_mac,
        "network_id": network_id,
        "traffic_type": "WIRED",
        "duration": duration_seconds,
    }
    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "start_gateway_packet_capture",
            "site_id": site_id,
            "payload": payload,
        }
    async with UniFiClient(settings) as client:
        await client.authenticate()
        response = await client.post(f"{base}/pcap-start", json_data=payload)
    return {
        "site_id": site_id,
        "gateway_mac": gateway_mac,
        "controller_response": response,
    }


@read_tool
async def get_gateway_packet_capture_status(
    site_id: str, gateway_mac: str, settings: Settings
) -> dict[str, Any]:
    """Get gateway packet-capture progress from the local console.

    Args:
        site_id: Network site short name, such as ``default``.
        gateway_mac: Gateway MAC address.
        settings: Application settings.

    Returns:
        The controller's capture-status response and target metadata.
    """
    site_id = validate_site_id(site_id)
    base = _capture_base(site_id, settings)
    gateway_mac = validate_mac_address(gateway_mac)
    async with UniFiClient(settings) as client:
        await client.authenticate()
        response = await client.get(f"{base}/pcap-status/{gateway_mac}")
    return {
        "site_id": site_id,
        "gateway_mac": gateway_mac,
        "controller_response": response,
    }


@write_tool
async def stop_gateway_packet_capture(
    site_id: str,
    gateway_mac: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Stop an active gateway packet capture.

    Args:
        site_id: Network site short name, such as ``default``.
        gateway_mac: Gateway MAC address.
        settings: Application settings.
        confirm: Must be true to stop the capture.
        dry_run: Preview the stop operation without making a request.

    Returns:
        The controller response, or a dry-run description.
    """
    validate_confirmation(confirm, "stop gateway packet capture", dry_run)
    site_id = validate_site_id(site_id)
    base = _capture_base(site_id, settings)
    gateway_mac = validate_mac_address(gateway_mac)
    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "stop_gateway_packet_capture",
            "site_id": site_id,
            "gateway_mac": gateway_mac,
        }
    async with UniFiClient(settings) as client:
        await client.authenticate()
        response = await client.post(f"{base}/pcap-stop/{gateway_mac}", json_data={})
    return {
        "site_id": site_id,
        "gateway_mac": gateway_mac,
        "controller_response": response,
    }


@write_tool
async def download_gateway_packet_capture(
    site_id: str,
    gateway_mac: str,
    output_path: str,
    settings: Settings,
    text_format: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Download a completed gateway capture into a confined local directory.

    Captures can contain credentials and private traffic. Files are therefore
    written with mode ``0600`` under ``UNIFI_PACKET_CAPTURE_DOWNLOAD_DIR``;
    any directory component supplied in ``output_path`` is discarded.

    The ``/txt`` rendering selected by ``text_format`` is taken from the
    Network UI's own download helper but is not live-verified: with no capture
    present the console answered ``406``, so its success path is unconfirmed.

    Args:
        site_id: Network site short name, such as ``default``.
        gateway_mac: Gateway MAC address.
        output_path: Destination filename; directory components are ignored.
        settings: Application settings.
        text_format: Download the controller's text representation instead.
        confirm: Must be true to write the capture to disk.
        dry_run: Return the destination and endpoint without downloading.

    Returns:
        Absolute local path, byte size, and SHA-256 checksum.
    """
    validate_confirmation(confirm, "download gateway packet capture", dry_run)
    site_id = validate_site_id(site_id)
    base = _capture_base(site_id, settings)
    gateway_mac = validate_mac_address(gateway_mac)
    destination = _resolve_capture_destination(output_path, settings)
    suffix = "/txt" if text_format else ""
    endpoint = f"{base}/pcap-get/{gateway_mac}{suffix}"
    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "download_gateway_packet_capture",
            "site_id": site_id,
            "gateway_mac": gateway_mac,
            "local_path": str(destination),
            "text_format": text_format,
        }
    async with UniFiClient(settings) as client:
        await client.authenticate()
        content = await client.download_bytes(endpoint)
    _write_capture(destination, content)
    return {
        "site_id": site_id,
        "gateway_mac": gateway_mac,
        "local_path": str(destination),
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "text_format": text_format,
    }
