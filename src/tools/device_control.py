"""Device control MCP tools."""

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


async def restart_device(
    site_id: str,
    device_mac: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Restart a UniFi device.

    Args:
        site_id: Site identifier
        device_mac: Device MAC address
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't restart the device

    Returns:
        Restart result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If device not found
    """
    site_id = validate_site_id(site_id)
    device_mac = validate_mac_address(device_mac)
    validate_confirmation(confirm, "device control operation")
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "device_mac": device_mac}

    if dry_run:
        logger.info(f"DRY RUN: Would restart device '{device_mac}' in site '{site_id}'")
        log_audit(
            operation="restart_device",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_restart": device_mac}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Verify device exists
            response = await client.get(f"/ea/sites/{site_id}/devices")
            # Client now auto-unwraps the "data" field, so response is the actual data
            devices_data: list[dict[str, Any]] = response if isinstance(response, list) else response.get("data", [])

            device_exists = any(
                validate_mac_address(d.get("mac", "")) == device_mac for d in devices_data
            )
            if not device_exists:
                raise ResourceNotFoundError("device", device_mac)

            # Restart the device
            restart_data = {"mac": device_mac, "cmd": "restart"}
            response = await client.post(f"/ea/sites/{site_id}/cmd/devmgr", json_data=restart_data)

            logger.info(f"Initiated restart for device '{device_mac}' in site '{site_id}'")
            log_audit(
                operation="restart_device",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "success": True,
                "device_mac": device_mac,
                "message": "Device restart initiated",
            }

    except Exception as e:
        logger.error(f"Failed to restart device '{device_mac}': {e}")
        log_audit(
            operation="restart_device",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def locate_device(
    site_id: str,
    device_mac: str,
    settings: Settings,
    enabled: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Enable or disable LED locate mode on a device.

    Args:
        site_id: Site identifier
        device_mac: Device MAC address
        settings: Application settings
        enabled: Enable (True) or disable (False) locate mode
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't change locate state

    Returns:
        Locate result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If device not found
    """
    site_id = validate_site_id(site_id)
    device_mac = validate_mac_address(device_mac)
    validate_confirmation(confirm, "device control operation")
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "device_mac": device_mac, "enabled": enabled}

    action = "enable" if enabled else "disable"

    if dry_run:
        logger.info(
            f"DRY RUN: Would {action} locate mode for device '{device_mac}' " f"in site '{site_id}'"
        )
        log_audit(
            operation="locate_device",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, f"would_{action}": device_mac}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Verify device exists
            response = await client.get(f"/ea/sites/{site_id}/devices")
            # Client now auto-unwraps the "data" field, so response is the actual data
            devices_data: list[dict[str, Any]] = response if isinstance(response, list) else response.get("data", [])

            device_exists = any(
                validate_mac_address(d.get("mac", "")) == device_mac for d in devices_data
            )
            if not device_exists:
                raise ResourceNotFoundError("device", device_mac)

            # Set locate state
            cmd = "set-locate" if enabled else "unset-locate"
            locate_data = {"mac": device_mac, "cmd": cmd}
            response = await client.post(f"/ea/sites/{site_id}/cmd/devmgr", json_data=locate_data)

            logger.info(
                f"{action.capitalize()}d locate mode for device '{device_mac}' "
                f"in site '{site_id}'"
            )
            log_audit(
                operation="locate_device",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "success": True,
                "device_mac": device_mac,
                "locate_enabled": enabled,
                "message": f"Locate mode {action}d",
            }

    except Exception as e:
        logger.error(f"Failed to {action} locate for device '{device_mac}': {e}")
        log_audit(
            operation="locate_device",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def upgrade_device(
    site_id: str,
    device_mac: str,
    settings: Settings,
    firmware_url: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Trigger firmware upgrade for a device.

    Args:
        site_id: Site identifier
        device_mac: Device MAC address
        settings: Application settings
        firmware_url: Optional custom firmware URL (uses latest if not provided)
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't initiate upgrade

    Returns:
        Upgrade result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If device not found
    """
    site_id = validate_site_id(site_id)
    device_mac = validate_mac_address(device_mac)
    validate_confirmation(confirm, "device control operation")
    logger = get_logger(__name__, settings.log_level)

    parameters = {
        "site_id": site_id,
        "device_mac": device_mac,
        "firmware_url": firmware_url,
    }

    if dry_run:
        logger.info(
            f"DRY RUN: Would initiate firmware upgrade for device '{device_mac}' "
            f"in site '{site_id}'"
        )
        log_audit(
            operation="upgrade_device",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_upgrade": device_mac}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Verify device exists and get details
            response = await client.get(f"/ea/sites/{site_id}/devices")
            # Client now auto-unwraps the "data" field, so response is the actual data
            devices_data: list[dict[str, Any]] = response if isinstance(response, list) else response.get("data", [])

            device = None
            for d in devices_data:
                if validate_mac_address(d.get("mac", "")) == device_mac:
                    device = d
                    break

            if not device:
                raise ResourceNotFoundError("device", device_mac)

            # Build upgrade command
            upgrade_data = {"mac": device_mac, "cmd": "upgrade"}

            if firmware_url:
                upgrade_data["url"] = firmware_url

            response = await client.post(f"/ea/sites/{site_id}/cmd/devmgr", json_data=upgrade_data)

            logger.info(
                f"Initiated firmware upgrade for device '{device_mac}' " f"in site '{site_id}'"
            )
            log_audit(
                operation="upgrade_device",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "success": True,
                "device_mac": device_mac,
                "message": "Firmware upgrade initiated",
                "current_version": device.get("version"),
            }

    except Exception as e:
        logger.error(f"Failed to upgrade device '{device_mac}': {e}")
        log_audit(
            operation="upgrade_device",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
