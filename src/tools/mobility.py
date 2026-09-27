"""MCP tools for the UniFi Mobility API (Phase 6).

Mobility is a cloud API on ``https://api.ui.com/v1/mobility/...`` using the
same API-key transport as Site Manager, so these tools reuse
:class:`SiteManagerClient` rather than adding a new transport. Requires
``UNIFI_SITE_MANAGER_ENABLED=true`` (the cloud API key must be configured),
matching the Cloud Connector tools' gating.
"""

from __future__ import annotations

from typing import Any

from ..api.site_manager_client import SiteManagerClient
from ..config import Settings
from ..models import (
    MobilityDevice,
    MobilityDeviceClient,
    MobilityWorkspace,
    MobilityWorkspaceAdmin,
)
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset
from ..utils.validators import coerce_bool, validate_confirmation

_DHCP_MODES = ("dhcp", "none")


def _require_cloud_api(settings: Settings) -> None:
    if not settings.site_manager_enabled:
        raise ValueError(
            "Mobility API is a cloud API. Set UNIFI_SITE_MANAGER_ENABLED=true and configure "
            "your UniFi API key."
        )


def _validate_uuid(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValidationError(f"{label} is required")
    return value


def _extract_collection(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        data = response.get("data", [])
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def _extract_item(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        data = response.get("data", response)
        if isinstance(data, dict):
            return data
        return response
    return {}


async def list_mobility_workspaces(settings: Settings) -> dict[str, Any]:
    """List UniFi Mobility workspaces."""
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)

    async with SiteManagerClient(settings) as client:
        response = await client.get("mobility/workspaces")

    data = _extract_collection(response)
    workspaces = [
        MobilityWorkspace.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    logger.info(sanitize_log_message(f"Listed {len(workspaces)} Mobility workspaces"))
    return {"count": len(workspaces), "data": workspaces}


async def list_mobility_workspace_admins(
    workspace_id: str, settings: Settings
) -> dict[str, Any]:
    """List admins of a UniFi Mobility workspace."""
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    workspace_id = _validate_uuid(workspace_id, "workspace_id")

    async with SiteManagerClient(settings) as client:
        response = await client.get(f"mobility/workspaces/{workspace_id}/admins")

    data = _extract_collection(response)
    admins = [
        MobilityWorkspaceAdmin.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    logger.info(
        sanitize_log_message(f"Listed {len(admins)} admins for workspace {workspace_id}")
    )
    return {"workspace_id": workspace_id, "count": len(admins), "data": admins}


async def list_mobility_devices(
    workspace_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List devices in a UniFi Mobility workspace."""
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    workspace_id = _validate_uuid(workspace_id, "workspace_id")
    final_limit, final_offset = validate_limit_offset(limit, offset)
    if final_limit is not None and not 1 <= final_limit <= 200:
        raise ValidationError("limit must be between 1 and 200")

    async with SiteManagerClient(settings) as client:
        response = await client.get(
            f"mobility/workspaces/{workspace_id}/devices",
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    devices = [MobilityDevice.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(
        sanitize_log_message(f"Listed {len(devices)} devices in workspace {workspace_id}")
    )
    return {
        "workspace_id": workspace_id,
        "offset": final_offset,
        "limit": final_limit,
        "count": len(devices),
        "data": devices,
    }


async def get_mobility_device(
    workspace_id: str, device_id: str, settings: Settings
) -> dict[str, Any]:
    """Get detail for a UniFi Mobility device."""
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    workspace_id = _validate_uuid(workspace_id, "workspace_id")
    device_id = _validate_uuid(device_id, "device_id")

    async with SiteManagerClient(settings) as client:
        response = await client.get(f"mobility/workspaces/{workspace_id}/devices/{device_id}")

    device = MobilityDevice.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Mobility device {device_id}"))
    return device.model_dump(by_alias=True)


async def update_mobility_device(
    workspace_id: str,
    device_id: str,
    settings: Settings,
    name: str,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Rename a UniFi Mobility device.

    Args:
        workspace_id: Workspace UUID
        device_id: Device UUID
        settings: Application settings
        name: New device name (1-32 characters, required)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "update Mobility device", dry_run)
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    workspace_id = _validate_uuid(workspace_id, "workspace_id")
    device_id = _validate_uuid(device_id, "device_id")
    name = name.strip()
    if not 1 <= len(name) <= 32:
        raise ValidationError("name must be between 1 and 32 characters")

    payload = {"name": name}
    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_mobility_device",
            "workspace_id": workspace_id,
            "device_id": device_id,
            "payload": payload,
        }

    async with SiteManagerClient(settings) as client:
        response = await client.put(
            f"mobility/workspaces/{workspace_id}/devices/{device_id}", json_data=payload
        )

    device = MobilityDevice.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Renamed Mobility device {device_id}"))
    return device.model_dump(by_alias=True)


async def list_mobility_device_clients(
    workspace_id: str,
    device_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List clients attached to a UniFi Mobility device."""
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    workspace_id = _validate_uuid(workspace_id, "workspace_id")
    device_id = _validate_uuid(device_id, "device_id")
    final_limit, final_offset = validate_limit_offset(limit, offset)
    if final_limit is not None and not 1 <= final_limit <= 200:
        raise ValidationError("limit must be between 1 and 200")

    async with SiteManagerClient(settings) as client:
        response = await client.get(
            f"mobility/workspaces/{workspace_id}/devices/{device_id}/clients",
            params={"limit": final_limit, "offset": final_offset},
        )

    data = _extract_collection(response)
    clients = [
        MobilityDeviceClient.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    logger.info(
        sanitize_log_message(f"Listed {len(clients)} clients on Mobility device {device_id}")
    )
    return {
        "workspace_id": workspace_id,
        "device_id": device_id,
        "offset": final_offset,
        "limit": final_limit,
        "count": len(clients),
        "data": clients,
    }


async def update_mobility_device_network(
    workspace_id: str,
    device_id: str,
    settings: Settings,
    host_address: str | None = None,
    dhcp_mode: str | None = None,
    dhcp_range_start: str | None = None,
    dhcp_range_stop: str | None = None,
    dhcp_lease_time: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update LAN / DHCP settings on a UniFi Mobility device.

    Args:
        workspace_id: Workspace UUID
        device_id: Device UUID
        settings: Application settings
        host_address: LAN address of the device (CIDR)
        dhcp_mode: ``dhcp`` to enable DHCP serving, ``none`` to disable
        dhcp_range_start: First address of the DHCP pool
        dhcp_range_stop: Last address of the DHCP pool
        dhcp_lease_time: Lease time in seconds (0 = infinite)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "update Mobility device network settings", dry_run)
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    workspace_id = _validate_uuid(workspace_id, "workspace_id")
    device_id = _validate_uuid(device_id, "device_id")

    payload: dict[str, Any] = {}
    if host_address is not None:
        payload["host_address"] = host_address
    if dhcp_mode is not None:
        if dhcp_mode not in _DHCP_MODES:
            raise ValidationError(f"dhcp_mode must be one of {list(_DHCP_MODES)}")
        payload["dhcp_mode"] = dhcp_mode
    if dhcp_range_start is not None:
        payload["dhcp_range_start"] = dhcp_range_start
    if dhcp_range_stop is not None:
        payload["dhcp_range_stop"] = dhcp_range_stop
    if dhcp_lease_time is not None:
        if dhcp_lease_time < 0:
            raise ValidationError("dhcp_lease_time must be >= 0 (0 = infinite)")
        payload["dhcp_lease_time"] = dhcp_lease_time

    if not payload:
        raise ValidationError("No updates provided")

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_mobility_device_network",
            "workspace_id": workspace_id,
            "device_id": device_id,
            "payload": payload,
        }

    async with SiteManagerClient(settings) as client:
        response = await client.put(
            f"mobility/workspaces/{workspace_id}/devices/{device_id}/network",
            json_data=payload,
        )

    logger.info(sanitize_log_message(f"Updated network settings on Mobility device {device_id}"))
    return _extract_item(response) or {"success": True, "payload_sent": payload}


async def update_mobility_device_wireless(
    workspace_id: str,
    device_id: str,
    settings: Settings,
    ssid: str,
    password: str,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update WiFi settings on a UniFi Mobility device.

    Args:
        workspace_id: Workspace UUID
        device_id: Device UUID
        settings: Application settings
        ssid: WiFi network name (required)
        password: WPA2-PSK password (required)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it
    """
    validate_confirmation(confirm, "update Mobility device WiFi settings", dry_run)
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    workspace_id = _validate_uuid(workspace_id, "workspace_id")
    device_id = _validate_uuid(device_id, "device_id")
    ssid = ssid.strip()
    if not ssid:
        raise ValidationError("ssid is required")
    if not password:
        raise ValidationError("password is required")

    payload = {"ssid": ssid, "password": password}
    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_mobility_device_wireless",
            "workspace_id": workspace_id,
            "device_id": device_id,
            "payload": payload,
        }

    async with SiteManagerClient(settings) as client:
        response = await client.put(
            f"mobility/workspaces/{workspace_id}/devices/{device_id}/wireless",
            json_data=payload,
        )

    logger.info(sanitize_log_message(f"Updated WiFi settings on Mobility device {device_id}"))
    return _extract_item(response) or {"success": True, "payload_sent": payload}
