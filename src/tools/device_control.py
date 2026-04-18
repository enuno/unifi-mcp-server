"""Device control MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import (
    ResourceNotFoundError,
    ValidationError,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_confirmation,
    validate_mac_address,
    validate_site_id,
)

# Radio identifiers: UniFi uses "ng" for 2.4GHz, "na" for 5GHz, "6e" for 6GHz
RADIO_BAND_MAP = {
    "2.4": "ng",
    "2.4ghz": "ng",
    "ng": "ng",
    "5": "na",
    "5ghz": "na",
    "na": "na",
    "6": "6e",
    "6ghz": "6e",
    "6e": "6e",
}

# Valid channels per band
VALID_CHANNELS = {
    "ng": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "na": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165],
    "6e": list(range(1, 234, 4)),  # 6GHz channels
}


async def restart_device(
    site_id: str,
    device_mac: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "device control operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "device_mac": device_mac}

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would restart device '{device_mac}' in site '{site_id}'"
            )
        )
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
            devices_data: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

            device_exists = any(
                validate_mac_address(d.get("mac", "")) == device_mac for d in devices_data
            )
            if not device_exists:
                raise ResourceNotFoundError("device", device_mac)

            # Restart the device
            restart_data = {"mac": device_mac, "cmd": "restart"}
            response = await client.post(f"/ea/sites/{site_id}/cmd/devmgr", json_data=restart_data)

            logger.info(
                sanitize_log_message(
                    f"Initiated restart for device '{device_mac}' in site '{site_id}'"
                )
            )
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
        logger.error(sanitize_log_message(f"Failed to restart device '{device_mac}': {e}"))
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "device control operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "device_mac": device_mac, "enabled": enabled}

    action = "enable" if enabled else "disable"

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would {action} locate mode for device '{device_mac}' "
                f"in site '{site_id}'"
            )
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
            devices_data: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

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
                sanitize_log_message(
                    f"{action.capitalize()}d locate mode for device '{device_mac}' "
                    f"in site '{site_id}'"
                )
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
        logger.error(
            sanitize_log_message(f"Failed to {action} locate for device '{device_mac}': {e}")
        )
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "device control operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    parameters = {
        "site_id": site_id,
        "device_mac": device_mac,
        "firmware_url": firmware_url,
    }

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would initiate firmware upgrade for device '{device_mac}' "
                f"in site '{site_id}'"
            )
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
            devices_data: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

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
                sanitize_log_message(
                    f"Initiated firmware upgrade for device '{device_mac}' " f"in site '{site_id}'"
                )
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
        logger.error(sanitize_log_message(f"Failed to upgrade device '{device_mac}': {e}"))
        log_audit(
            operation="upgrade_device",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


def _resolve_radio(band: str) -> str:
    """Resolve a band name to the UniFi radio identifier."""
    key = band.lower().strip()
    radio = RADIO_BAND_MAP.get(key)
    if not radio:
        raise ValidationError(
            f"Invalid radio band '{band}'. Use: 2.4, 5, 6 (or ng, na, 6e)"
        )
    return radio


async def get_ap_radio_config(
    site_id: str,
    device_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get radio configuration for an access point (read-only).

    Returns current channel, channel width (HT mode), and transmit power for
    each radio on the device.

    Args:
        site_id: Site identifier
        device_id: Device ID or MAC address

    Returns:
        Dictionary with device info and radio_table entries
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(
            settings.get_site_api_path(site_id, "stat/device")
        )
        all_devices: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        device = next(
            (
                d
                for d in all_devices
                if d.get("_id") == device_id or d.get("mac") == device_id
            ),
            None,
        )

        if not device:
            raise ResourceNotFoundError("device", device_id)

        radio_table = device.get("radio_table", [])
        radio_table_stats = device.get("radio_table_stats", [])

        # Build a stats lookup by radio name
        stats_by_radio = {r.get("name"): r for r in radio_table_stats}

        radios = []
        for radio in radio_table:
            radio_name = radio.get("radio", radio.get("name", "unknown"))
            band = {"ng": "2.4GHz", "na": "5GHz", "6e": "6GHz"}.get(
                radio_name, radio_name
            )
            stats = stats_by_radio.get(radio_name, {})
            radios.append(
                {
                    "radio": radio_name,
                    "band": band,
                    "channel": radio.get("channel", "auto"),
                    "ht": radio.get("ht"),
                    "tx_power_mode": radio.get("tx_power_mode"),
                    "tx_power": radio.get("tx_power"),
                    "min_rssi_enabled": radio.get("min_rssi_enabled"),
                    "min_rssi": radio.get("min_rssi"),
                    "current_channel": stats.get("channel"),
                    "satisfaction": stats.get("satisfaction"),
                    "num_sta": stats.get("num_sta"),
                }
            )

        logger.info(
            sanitize_log_message(
                f"Retrieved radio config for device '{device_id}' in site '{site_id}'"
            )
        )

        return {
            "device_id": device.get("_id"),
            "device_name": device.get("name"),
            "model": device.get("model"),
            "mac": device.get("mac"),
            "radios": radios,
        }


async def set_ap_radio_channel(
    site_id: str,
    device_id: str,
    band: str,
    channel: int | str,
    settings: Settings,
    ht: str | None = None,
    tx_power_mode: str | None = None,
    tx_power: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Set the radio channel (and optionally width/power) for an access point.

    Args:
        site_id: Site identifier
        device_id: Device ID or MAC address
        band: Radio band — "2.4", "5", or "6" (also accepts "ng", "na", "6e")
        channel: WiFi channel number, or "auto" for automatic channel selection
        settings: Application settings
        ht: Channel width — e.g. "20" for HT20, "40" for HT40, "80" for VHT80,
            "160" for VHT160. If not specified, existing width is preserved.
        tx_power_mode: Transmit power mode — "auto", "medium", "low", "high",
            or "custom". If not specified, existing mode is preserved.
        tx_power: Custom transmit power in dBm (only used when tx_power_mode
            is "custom"). Range varies by device.
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, show what would change without applying

    Returns:
        Updated radio configuration or dry-run preview

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If device not found
        ValidationError: If radio band or channel is invalid
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "device radio configuration", dry_run)
    logger = get_logger(__name__, settings.log_level)

    radio = _resolve_radio(band)

    # Validate channel
    is_auto = str(channel).lower() == "auto"
    if not is_auto:
        channel = int(channel)
        valid = VALID_CHANNELS.get(radio, [])
        if valid and channel not in valid:
            band_label = {"ng": "2.4GHz", "na": "5GHz", "6e": "6GHz"}.get(radio, radio)
            raise ValidationError(
                f"Invalid channel {channel} for {band_label}. Valid: {valid}"
            )

    # Validate HT mode if provided
    if ht is not None:
        ht = str(ht)
        valid_ht = {"ng": ["20", "40"], "na": ["20", "40", "80", "160"], "6e": ["20", "40", "80", "160"]}
        allowed = valid_ht.get(radio, [])
        if ht not in allowed:
            raise ValidationError(
                f"Invalid channel width '{ht}' for {radio}. Valid: {allowed}"
            )

    # Validate tx_power_mode
    if tx_power_mode is not None:
        valid_modes = ["auto", "medium", "low", "high", "custom"]
        if tx_power_mode not in valid_modes:
            raise ValidationError(
                f"Invalid tx_power_mode '{tx_power_mode}'. Valid: {valid_modes}"
            )

    parameters = {
        "site_id": site_id,
        "device_id": device_id,
        "band": band,
        "radio": radio,
        "channel": channel if not is_auto else "auto",
        "ht": ht,
        "tx_power_mode": tx_power_mode,
        "tx_power": tx_power,
    }

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would set {radio} channel to "
                f"{'auto' if is_auto else channel} on device '{device_id}'"
            )
        )
        log_audit(
            operation="set_ap_radio_channel",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_set": parameters}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Fetch full device object via stat/device
            response = await client.get(
                settings.get_site_api_path(site_id, "stat/device")
            )
            all_devices: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

            device = next(
                (
                    d
                    for d in all_devices
                    if d.get("_id") == device_id or d.get("mac") == device_id
                ),
                None,
            )

            if not device:
                raise ResourceNotFoundError("device", device_id)

            radio_table = device.get("radio_table", [])
            if not radio_table:
                raise ValidationError(
                    f"Device '{device_id}' has no radio_table — "
                    "it may not be an access point"
                )

            # Find the target radio entry
            target = None
            for entry in radio_table:
                if entry.get("radio") == radio or entry.get("name") == radio:
                    target = entry
                    break

            if not target:
                available = [
                    e.get("radio", e.get("name")) for e in radio_table
                ]
                raise ValidationError(
                    f"Radio '{radio}' not found on device. "
                    f"Available radios: {available}"
                )

            # Capture old values for the response
            old_channel = target.get("channel")
            old_ht = target.get("ht")

            # Apply changes
            if is_auto:
                target["channel"] = "auto"
            else:
                target["channel"] = channel

            if ht is not None:
                target["ht"] = ht

            if tx_power_mode is not None:
                target["tx_power_mode"] = tx_power_mode

            if tx_power is not None:
                target["tx_power"] = tx_power

            # PUT the full device back
            resolved_id = device["_id"]
            endpoint = settings.get_site_api_path(
                site_id, f"rest/device/{resolved_id}"
            )
            response = await client.put(endpoint, json_data=device)
            if isinstance(response, list):
                updated_device: dict[str, Any] = response[0] if response else {}
            else:
                updated_device = response.get("data", [{}])[0]

            logger.info(
                sanitize_log_message(
                    f"Set {radio} channel to {'auto' if is_auto else channel} "
                    f"on device '{device_id}' in site '{site_id}'"
                )
            )
            log_audit(
                operation="set_ap_radio_channel",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "success": True,
                "device_id": resolved_id,
                "device_name": device.get("name"),
                "radio": radio,
                "band": {"ng": "2.4GHz", "na": "5GHz", "6e": "6GHz"}.get(radio, radio),
                "old_channel": old_channel,
                "new_channel": "auto" if is_auto else channel,
                "old_ht": old_ht,
                "new_ht": ht if ht is not None else old_ht,
            }

    except Exception as e:
        logger.error(
            sanitize_log_message(
                f"Failed to set radio channel on device '{device_id}': {e}"
            )
        )
        log_audit(
            operation="set_ap_radio_channel",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
