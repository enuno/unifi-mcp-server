"""Device control MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import (
    APIError,
    ResourceNotFoundError,
    ValidationError,
    coerce_bool,
    first_response_item,
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
    "na": [
        36,
        40,
        44,
        48,
        52,
        56,
        60,
        64,
        100,
        104,
        108,
        112,
        116,
        120,
        124,
        128,
        132,
        136,
        140,
        144,
        149,
        153,
        157,
        161,
        165,
    ],
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
                f"DRY RUN: Would {action} locate mode for device '{device_mac}' in site '{site_id}'"
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
                    f"Initiated firmware upgrade for device '{device_mac}' in site '{site_id}'"
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
        raise ValidationError(f"Invalid radio band '{band}'. Use: 2.4, 5, 6 (or ng, na, 6e)")
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
        settings: Application settings

    Returns:
        Dictionary with device info and radio_table entries
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(settings.get_site_api_path(site_id, "stat/device"))
        all_devices: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        device = next(
            (d for d in all_devices if d.get("_id") == device_id or d.get("mac") == device_id),
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
            band = {"ng": "2.4GHz", "na": "5GHz", "6e": "6GHz"}.get(radio_name, radio_name)
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
            raise ValidationError(f"Invalid channel {channel} for {band_label}. Valid: {valid}")

    # Validate HT mode if provided
    if ht is not None:
        ht = str(ht)
        valid_ht = {
            "ng": ["20", "40"],
            "na": ["20", "40", "80", "160"],
            "6e": ["20", "40", "80", "160"],
        }
        allowed = valid_ht.get(radio, [])
        if ht not in allowed:
            raise ValidationError(f"Invalid channel width '{ht}' for {radio}. Valid: {allowed}")

    # Validate tx_power_mode
    if tx_power_mode is not None:
        valid_modes = ["auto", "medium", "low", "high", "custom"]
        if tx_power_mode not in valid_modes:
            raise ValidationError(f"Invalid tx_power_mode '{tx_power_mode}'. Valid: {valid_modes}")

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

            # Enumerate on stat/device (rest/device serves no collection GET
            # on current controllers -- verified live: the list URL answers
            # NotFound), then fetch the CONFIG record by id. Writing the
            # stat/device operational blob back is answered with HTTP 200
            # while the radio change is silently dropped; observed live
            # when a tx_power write did not stick.
            response = await client.get(settings.get_site_api_path(site_id, "stat/device"))
            all_devices: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

            stat_device = next(
                (d for d in all_devices if d.get("_id") == device_id or d.get("mac") == device_id),
                None,
            )

            if not stat_device:
                raise ResourceNotFoundError("device", device_id)

            resolved_id = stat_device["_id"]
            try:
                config_response = await client.get(
                    settings.get_site_api_path(site_id, f"rest/device/{resolved_id}")
                )
                device = first_response_item(config_response)
            except APIError:
                device = {}
            if not device:
                # Older surfaces may not serve the per-id config GET either;
                # the stat record's radio_table mirrors applied config and
                # the write below sends only that table.
                device = stat_device

            radio_table = device.get("radio_table", [])
            if not radio_table:
                raise ValidationError(
                    f"Device '{device_id}' has no radio_table — it may not be an access point"
                )

            # Find the target radio entry
            target = None
            for entry in radio_table:
                if entry.get("radio") == radio or entry.get("name") == radio:
                    target = entry
                    break

            if not target:
                available = [e.get("radio", e.get("name")) for e in radio_table]
                raise ValidationError(
                    f"Radio '{radio}' not found on device. Available radios: {available}"
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

            # PUT only the radio_table, and verify the echo: a 200 alone
            # does not prove the controller stored the change.
            endpoint = settings.get_site_api_path(site_id, f"rest/device/{resolved_id}")
            put_response = await client.put(endpoint, json_data={"radio_table": radio_table})

            stored_device = first_response_item(put_response)
            stored_entry: dict[str, Any] = {}
            for entry in stored_device.get("radio_table", []) or []:
                if isinstance(entry, dict) and (
                    entry.get("radio") == radio or entry.get("name") == radio
                ):
                    stored_entry = entry
                    break

            warnings: list[str] = []
            if stored_entry:
                checks: list[tuple[str, Any]] = []
                if not is_auto:
                    checks.append(("channel", channel))
                if ht is not None:
                    checks.append(("ht", ht))
                if tx_power_mode is not None:
                    checks.append(("tx_power_mode", tx_power_mode))
                if tx_power is not None:
                    checks.append(("tx_power", tx_power))
                for key, requested_value in checks:
                    stored_value = stored_entry.get(key)
                    if str(stored_value) != str(requested_value):
                        warnings.append(
                            f"Controller stored {key}={stored_value!r}, "
                            f"not the requested {requested_value!r}"
                        )
            else:
                warnings.append(
                    "Controller did not echo the radio table; the change " "could not be confirmed"
                )

            logger.info(
                sanitize_log_message(
                    f"Set {radio} channel to {'auto' if is_auto else channel} "
                    f"on device '{device_id}' in site '{site_id}'"
                )
            )
            log_audit(
                operation="set_ap_radio_channel",
                parameters=parameters,
                # The audit record must agree with the tool result: an
                # unconfirmed or mismatched echo is not a success.
                result="success" if not warnings else "unconfirmed",
                site_id=site_id,
            )

            result: dict[str, Any] = {
                "success": not warnings,
                "device_id": resolved_id,
                "device_name": device.get("name"),
                "radio": radio,
                "band": {"ng": "2.4GHz", "na": "5GHz", "6e": "6GHz"}.get(radio, radio),
                "old_channel": old_channel,
                "new_channel": "auto" if is_auto else channel,
                "old_ht": old_ht,
                "new_ht": ht if ht is not None else old_ht,
                "stored_tx_power": stored_entry.get("tx_power"),
                "stored_tx_power_mode": stored_entry.get("tx_power_mode"),
            }
            if warnings:
                for warning in warnings:
                    logger.warning(sanitize_log_message(warning))
                result["warnings"] = warnings
            return result

    except Exception as e:
        logger.error(
            sanitize_log_message(f"Failed to set radio channel on device '{device_id}': {e}")
        )
        log_audit(
            operation="set_ap_radio_channel",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def force_provision_device(
    site_id: str,
    device_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Push the stored configuration to a device now (force provision).

    A direct config write (e.g. a radio_table change via rest/device) is
    stored by the controller but not always pushed to the device;
    observed live: a channel change that sat stored-but-not-applied for
    minutes. Force provision closes that gap without a reboot -- the
    device re-applies config with only a brief service pause.

    Args:
        site_id: Site identifier
        device_id: Device ID or MAC address (any common MAC format)
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, preview without provisioning

    Returns:
        Dictionary with the provision request status
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "force provision", dry_run)
    dry_run = coerce_bool(dry_run)
    logger = get_logger(__name__, settings.log_level)
    parameters = {"site_id": site_id, "device_id": device_id}

    # cmd/devmgr keys on the MAC. Try MAC validation first: it accepts
    # every common format including separator-less 12-hex, which a
    # substring test would misroute into the id lookup.
    try:
        mac: str | None = validate_mac_address(device_id)
    except ValidationError:
        mac = None

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            if mac is None:
                response = await client.get(settings.get_site_api_path(site_id, "stat/device"))
                devices = response if isinstance(response, list) else response.get("data", [])
                found = next(
                    (d for d in devices if isinstance(d, dict) and d.get("_id") == device_id),
                    None,
                )
                if not found:
                    raise ResourceNotFoundError("device", device_id)
                mac = validate_mac_address(found.get("mac", ""))

            if dry_run:
                log_audit(
                    operation="force_provision_device",
                    parameters=parameters,
                    result="dry_run",
                    site_id=site_id,
                    dry_run=True,
                )
                return {
                    "dry_run": True,
                    "would_provision": mac,
                }

            await client.post(
                settings.get_site_api_path(site_id, "cmd/devmgr"),
                json_data={"cmd": "force-provision", "mac": mac},
            )
            log_audit(
                operation="force_provision_device",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )
            logger.info(sanitize_log_message(f"Force provision requested for {mac}"))
            return {"success": True, "mac": mac, "status": "provision requested"}

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to force provision '{device_id}': {e}"))
        log_audit(
            operation="force_provision_device",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def set_ap_min_rssi(
    site_id: str,
    device_id: str,
    band: str,
    settings: Settings,
    enabled: bool = True,
    min_rssi: int = -75,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Set the minimum client RSSI on one AP radio.

    Reads the device record, edits one radio_table entry, PUTs it back and
    verifies the echo. The read prefers the config record
    (``rest/device/{id}``), but that route answers GET with 404 on current
    controllers -- verified on Network 10.5 against both an online and an
    offline AP -- so in practice the stat record supplies the radio table
    and the write is only as trustworthy as that blob. Echo verification
    is what makes that acceptable: a divergent stored value is reported,
    never assumed.

    The PUT is a partial update rather than a full-record replace:
    sending only ``radio_table`` was measured to leave the other 113 keys
    of the device record untouched.

    Below the floor the AP refuses/evicts the association, so a client
    camped on a distant AP at a weak signal re-places itself onto a
    nearer one. Per-radio and per-AP -- unlike the WLAN-wide roaming
    assistant, a floor on one AP leaves every other radio accepting
    weak clients (e.g. yard coverage on a different AP).

    Args:
        site_id: Site identifier
        device_id: Device ID or MAC address
        band: Radio band -- "2.4", "5", or "6" (also ng/na/6e)
        settings: Application settings
        enabled: Enable (True) or disable (False) the floor
        min_rssi: Floor in dBm, -90..-60. Ignored when ``enabled`` is
            False -- writing a number back beside a disabled floor leaves
            a value in the radio_table that reads like a floor still in
            force.
        confirm: Confirmation flag (required)
        dry_run: If True, preview without writing

    Returns:
        Dictionary with stored state, echo-verified
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "min-RSSI change", dry_run)
    dry_run = coerce_bool(dry_run)
    radio = RADIO_BAND_MAP.get(str(band).lower())
    if radio is None:
        raise ValidationError(
            f"Unknown band '{band}'; accepted: " + ", ".join(sorted(RADIO_BAND_MAP))
        )
    if not -90 <= min_rssi <= -60:
        raise ValidationError(f"min_rssi must be -90..-60 dBm, got {min_rssi}")
    logger = get_logger(__name__, settings.log_level)
    parameters = {
        "site_id": site_id,
        "device_id": device_id,
        "radio": radio,
        "enabled": enabled,
        "min_rssi": min_rssi,
    }

    if dry_run:
        return {"dry_run": True, "would_set": parameters}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            response = await client.get(settings.get_site_api_path(site_id, "stat/device"))
            devices = response if isinstance(response, list) else response.get("data", [])
            stat_device = next(
                (
                    d
                    for d in devices
                    if isinstance(d, dict)
                    and (d.get("_id") == device_id or d.get("mac") == device_id)
                ),
                None,
            )
            if not stat_device:
                raise ResourceNotFoundError("device", device_id)
            resolved_id = stat_device["_id"]

            try:
                config_response = await client.get(
                    settings.get_site_api_path(site_id, f"rest/device/{resolved_id}")
                )
                device = first_response_item(config_response)
            except APIError:
                device = {}
            if not device:
                device = stat_device

            radio_table = device.get("radio_table", [])
            target = next(
                (
                    e
                    for e in radio_table
                    if isinstance(e, dict) and (e.get("radio") == radio or e.get("name") == radio)
                ),
                None,
            )
            if target is None:
                raise ValidationError(f"Device has no {radio} radio")
            target["min_rssi_enabled"] = enabled
            if enabled:
                target["min_rssi"] = min_rssi

            put_response = await client.put(
                settings.get_site_api_path(site_id, f"rest/device/{resolved_id}"),
                json_data={"radio_table": radio_table},
            )
            stored = first_response_item(put_response)
            stored_entry = next(
                (
                    e
                    for e in stored.get("radio_table", []) or []
                    if isinstance(e, dict) and (e.get("radio") == radio or e.get("name") == radio)
                ),
                {},
            )
            warnings: list[str] = []
            if stored_entry:
                if bool(stored_entry.get("min_rssi_enabled")) != enabled:
                    warnings.append(
                        f"Controller stored min_rssi_enabled={stored_entry.get('min_rssi_enabled')!r}"
                    )
                if enabled and stored_entry.get("min_rssi") != min_rssi:
                    warnings.append(f"Controller stored min_rssi={stored_entry.get('min_rssi')!r}")
            else:
                warnings.append("Controller did not echo the radio table; change unconfirmed")

            log_audit(
                operation="set_ap_min_rssi",
                parameters=parameters,
                result="success" if not warnings else "unconfirmed",
                site_id=site_id,
            )
            result: dict[str, Any] = {
                "success": not warnings,
                "device_id": resolved_id,
                "device_name": device.get("name"),
                "radio": radio,
                "min_rssi_enabled": stored_entry.get("min_rssi_enabled"),
                "min_rssi": stored_entry.get("min_rssi"),
            }
            if warnings:
                for w in warnings:
                    logger.warning(sanitize_log_message(w))
                result["warnings"] = warnings
            return result
    except Exception as e:
        # Mirrors force_provision_device: a write that raises still
        # gets an audit row, otherwise a partial or failed change
        # leaves no trace at all.
        logger.error(sanitize_log_message(f"Failed to set min RSSI on '{device_id}': {e}"))
        log_audit(
            operation="set_ap_min_rssi",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
