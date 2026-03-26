"""WiFi network (SSID) management MCP tools."""

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
    validate_limit_offset,
    validate_site_id,
)


async def list_wlans(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all wireless networks (SSIDs) in a site (read-only).

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of WLANs to return
        offset: Number of WLANs to skip

    Returns:
        List of WLAN dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/wlanconf")
        # Handle both list and dict responses
        wlans_data: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        # Apply pagination
        paginated = wlans_data[offset : offset + limit]

        logger.info(sanitize_log_message(f"Retrieved {len(paginated)} WLANs for site '{site_id}'"))
        return paginated


async def create_wlan(
    site_id: str,
    name: str,
    security: str,
    settings: Settings,
    password: str | None = None,
    enabled: bool = True,
    is_guest: bool = False,
    wpa_mode: str = "wpa2",
    wpa_enc: str = "ccmp",
    vlan_id: int | None = None,
    networkconf_id: str | None = None,
    ap_group_ids: list[str] | None = None,
    ap_group_mode: str | None = None,
    wlan_bands: list[str] | None = None,
    optimize_iot_wifi_connectivity: bool | None = None,
    minrate_ng_enabled: bool | None = None,
    minrate_ng_data_rate_kbps: int | None = None,
    hide_ssid: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a new wireless network (SSID).

    Args:
        site_id: Site identifier
        name: SSID name
        security: Security type (open, wpapsk, wpaeap)
        settings: Application settings
        password: WiFi password (required for wpapsk)
        enabled: Enable the WLAN immediately
        is_guest: Mark as guest network
        wpa_mode: WPA mode (wpa, wpa2, wpa3)
        wpa_enc: WPA encryption (tkip, ccmp, ccmp-tkip)
        vlan_id: VLAN ID for network isolation
        networkconf_id: Network configuration ID to associate this SSID with
        ap_group_ids: List of AP group IDs to broadcast this SSID on
        ap_group_mode: AP group mode (groups, all). Required when using ap_group_ids.
        wlan_bands: WiFi bands as list (e.g. ["2g"], ["5g"], ["2g", "5g"])
        optimize_iot_wifi_connectivity: Enable IoT WiFi optimizations
        minrate_ng_enabled: Enable minimum data rate for 2.4GHz
        minrate_ng_data_rate_kbps: Minimum 2.4GHz data rate in kbps (e.g. 1000)
        hide_ssid: Hide SSID from broadcast
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't create the WLAN

    Returns:
        Created WLAN dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ValidationError: If validation fails
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "wifi operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    # Validate security type
    valid_security = ["open", "wpapsk", "wpaeap"]
    if security not in valid_security:
        raise ValidationError(
            f"Invalid security type '{security}'. Must be one of: {valid_security}"
        )

    # Validate password required for WPA
    if security == "wpapsk" and not password:
        raise ValidationError("Password required for WPA/WPA2/WPA3 security")

    # Validate WPA mode
    valid_wpa_modes = ["wpa", "wpa2", "wpa3"]
    if wpa_mode not in valid_wpa_modes:
        raise ValidationError(f"Invalid WPA mode '{wpa_mode}'. Must be one of: {valid_wpa_modes}")

    # Validate WPA encryption
    valid_wpa_enc = ["tkip", "ccmp", "ccmp-tkip"]
    if wpa_enc not in valid_wpa_enc:
        raise ValidationError(
            f"Invalid WPA encryption '{wpa_enc}'. Must be one of: {valid_wpa_enc}"
        )

    # Build WLAN data
    wlan_data = {
        "name": name,
        "security": security,
        "enabled": enabled,
        "is_guest": is_guest,
        "hide_ssid": hide_ssid,
    }

    if security == "wpapsk":
        wlan_data["x_passphrase"] = password
        wlan_data["wpa_mode"] = wpa_mode
        wlan_data["wpa_enc"] = wpa_enc

    if vlan_id is not None:
        if not 1 <= vlan_id <= 4094:
            raise ValidationError(f"Invalid VLAN ID {vlan_id}. Must be between 1 and 4094")
        wlan_data["vlan"] = vlan_id
        wlan_data["vlan_enabled"] = True

    if networkconf_id is not None:
        wlan_data["networkconf_id"] = networkconf_id

    if ap_group_ids is not None:
        wlan_data["ap_group_ids"] = ap_group_ids

    if ap_group_mode is not None:
        wlan_data["ap_group_mode"] = ap_group_mode

    if wlan_bands is not None:
        wlan_data["wlan_bands"] = wlan_bands

    if optimize_iot_wifi_connectivity is not None:
        wlan_data["optimize_iot_wifi_connectivity"] = optimize_iot_wifi_connectivity
        if optimize_iot_wifi_connectivity:
            wlan_data["b_supported"] = True
            wlan_data["no2ghz_oui"] = False

    if minrate_ng_enabled is not None:
        wlan_data["minrate_ng_enabled"] = minrate_ng_enabled

    if minrate_ng_data_rate_kbps is not None:
        wlan_data["minrate_ng_data_rate_kbps"] = minrate_ng_data_rate_kbps

    # Log parameters for audit (mask password)
    parameters = {
        "site_id": site_id,
        "name": name,
        "security": security,
        "enabled": enabled,
        "is_guest": is_guest,
        "vlan_id": vlan_id,
        "networkconf_id": networkconf_id,
        "ap_group_ids": ap_group_ids,
        "wlan_bands": wlan_bands,
        "hide_ssid": hide_ssid,
        "password": "***MASKED***" if password else None,
    }

    if dry_run:
        logger.info(sanitize_log_message(f"DRY RUN: Would create WLAN '{name}' in site '{site_id}'"))
        log_audit(
            operation="create_wlan",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        # Don't include password in dry-run output
        safe_data = {k: v for k, v in wlan_data.items() if k != "x_passphrase"}
        return {"dry_run": True, "would_create": safe_data}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            response = await client.post(f"/ea/sites/{site_id}/rest/wlanconf", json_data=wlan_data)
            created_wlan: dict[str, Any] = response.get("data", [{}])[0]

            logger.info(sanitize_log_message(f"Created WLAN '{name}' in site '{site_id}'"))
            log_audit(
                operation="create_wlan",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return created_wlan

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to create WLAN '{name}': {e}"))
        log_audit(
            operation="create_wlan",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def update_wlan(
    site_id: str,
    wlan_id: str,
    settings: Settings,
    name: str | None = None,
    security: str | None = None,
    password: str | None = None,
    enabled: bool | None = None,
    is_guest: bool | None = None,
    wpa_mode: str | None = None,
    wpa_enc: str | None = None,
    vlan_id: int | None = None,
    hide_ssid: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing wireless network.

    Args:
        site_id: Site identifier
        wlan_id: WLAN ID
        settings: Application settings
        name: New SSID name
        security: New security type (open, wpapsk, wpaeap)
        password: New WiFi password
        enabled: Enable/disable the WLAN
        is_guest: Mark as guest network
        wpa_mode: New WPA mode (wpa, wpa2, wpa3)
        wpa_enc: New WPA encryption (tkip, ccmp, ccmp-tkip)
        vlan_id: New VLAN ID
        hide_ssid: Hide/show SSID from broadcast
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't update the WLAN

    Returns:
        Updated WLAN dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If WLAN not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "wifi operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    # Validate security type if provided
    if security is not None:
        valid_security = ["open", "wpapsk", "wpaeap"]
        if security not in valid_security:
            raise ValidationError(
                f"Invalid security type '{security}'. Must be one of: {valid_security}"
            )

    # Validate WPA mode if provided
    if wpa_mode is not None:
        valid_wpa_modes = ["wpa", "wpa2", "wpa3"]
        if wpa_mode not in valid_wpa_modes:
            raise ValidationError(
                f"Invalid WPA mode '{wpa_mode}'. Must be one of: {valid_wpa_modes}"
            )

    # Validate WPA encryption if provided
    if wpa_enc is not None:
        valid_wpa_enc = ["tkip", "ccmp", "ccmp-tkip"]
        if wpa_enc not in valid_wpa_enc:
            raise ValidationError(
                f"Invalid WPA encryption '{wpa_enc}'. Must be one of: {valid_wpa_enc}"
            )

    # Validate VLAN ID if provided
    if vlan_id is not None and not 1 <= vlan_id <= 4094:
        raise ValidationError(f"Invalid VLAN ID {vlan_id}. Must be between 1 and 4094")

    parameters = {
        "site_id": site_id,
        "wlan_id": wlan_id,
        "name": name,
        "security": security,
        "enabled": enabled,
        "is_guest": is_guest,
        "vlan_id": vlan_id,
        "hide_ssid": hide_ssid,
        "password": "***MASKED***" if password else None,
    }

    if dry_run:
        logger.info(sanitize_log_message(f"DRY RUN: Would update WLAN '{wlan_id}' in site '{site_id}'"))
        log_audit(
            operation="update_wlan",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_update": parameters}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Get existing WLAN
            response = await client.get(f"/ea/sites/{site_id}/rest/wlanconf")
            wlans_data: list[dict[str, Any]] = response.get("data", [])

            existing_wlan = None
            for wlan in wlans_data:
                if wlan.get("_id") == wlan_id:
                    existing_wlan = wlan
                    break

            if not existing_wlan:
                raise ResourceNotFoundError("wlan", wlan_id)

            # Build update data
            update_data = existing_wlan.copy()

            if name is not None:
                update_data["name"] = name
            if security is not None:
                update_data["security"] = security
            if password is not None:
                update_data["x_passphrase"] = password
            if enabled is not None:
                update_data["enabled"] = enabled
            if is_guest is not None:
                update_data["is_guest"] = is_guest
            if wpa_mode is not None:
                update_data["wpa_mode"] = wpa_mode
            if wpa_enc is not None:
                update_data["wpa_enc"] = wpa_enc
            if vlan_id is not None:
                update_data["vlan"] = vlan_id
                update_data["vlan_enabled"] = True
            if hide_ssid is not None:
                update_data["hide_ssid"] = hide_ssid

            response = await client.put(
                f"/ea/sites/{site_id}/rest/wlanconf/{wlan_id}", json_data=update_data
            )
            updated_wlan: dict[str, Any] = response.get("data", [{}])[0]

            logger.info(sanitize_log_message(f"Updated WLAN '{wlan_id}' in site '{site_id}'"))
            log_audit(
                operation="update_wlan",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return updated_wlan

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to update WLAN '{wlan_id}': {e}"))
        log_audit(
            operation="update_wlan",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def delete_wlan(
    site_id: str,
    wlan_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Delete a wireless network.

    Args:
        site_id: Site identifier
        wlan_id: WLAN ID
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't delete the WLAN

    Returns:
        Deletion result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If WLAN not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "wifi operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "wlan_id": wlan_id}

    if dry_run:
        logger.info(sanitize_log_message(f"DRY RUN: Would delete WLAN '{wlan_id}' from site '{site_id}'"))
        log_audit(
            operation="delete_wlan",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_delete": wlan_id}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Verify WLAN exists before deleting
            response = await client.get(f"/ea/sites/{site_id}/rest/wlanconf")
            wlans_data: list[dict[str, Any]] = response.get("data", [])

            wlan_exists = any(wlan.get("_id") == wlan_id for wlan in wlans_data)
            if not wlan_exists:
                raise ResourceNotFoundError("wlan", wlan_id)

            response = await client.delete(f"/ea/sites/{site_id}/rest/wlanconf/{wlan_id}")

            logger.info(sanitize_log_message(f"Deleted WLAN '{wlan_id}' from site '{site_id}'"))
            log_audit(
                operation="delete_wlan",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {"success": True, "deleted_wlan_id": wlan_id}

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to delete WLAN '{wlan_id}': {e}"))
        log_audit(
            operation="delete_wlan",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def get_wlan_statistics(
    site_id: str,
    settings: Settings,
    wlan_id: str | None = None,
) -> dict[str, Any]:
    """Get WiFi usage statistics.

    Args:
        site_id: Site identifier
        settings: Application settings
        wlan_id: Optional WLAN ID to filter statistics

    Returns:
        WLAN statistics dictionary
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # Get WLANs
        wlans_response = await client.get(f"/ea/sites/{site_id}/rest/wlanconf")
        wlans_data = wlans_response.get("data", [])

        # Get active clients
        clients_response = await client.get(f"/ea/sites/{site_id}/sta")
        clients_data = clients_response.get("data", [])

        # Calculate statistics per WLAN
        wlan_stats = []
        for wlan in wlans_data:
            wlan_identifier = wlan.get("_id")
            wlan_name = wlan.get("name")

            # Skip if filtering by WLAN ID and this isn't it
            if wlan_id and wlan_identifier != wlan_id:
                continue

            # Count clients on this WLAN (match by essid/name)
            clients_on_wlan = [
                c for c in clients_data if c.get("essid") == wlan_name or c.get("is_wired") is False
            ]

            # Calculate total bandwidth
            total_tx = sum(c.get("tx_bytes", 0) for c in clients_on_wlan)
            total_rx = sum(c.get("rx_bytes", 0) for c in clients_on_wlan)

            wlan_stats.append(
                {
                    "wlan_id": wlan_identifier,
                    "name": wlan_name,
                    "enabled": wlan.get("enabled", False),
                    "security": wlan.get("security"),
                    "is_guest": wlan.get("is_guest", False),
                    "client_count": len(clients_on_wlan),
                    "total_tx_bytes": total_tx,
                    "total_rx_bytes": total_rx,
                    "total_bytes": total_tx + total_rx,
                }
            )

        logger.info(sanitize_log_message(f"Retrieved WLAN statistics for site '{site_id}'"))

        if wlan_id:
            return wlan_stats[0] if wlan_stats else {}
        else:
            return {"site_id": site_id, "wlans": wlan_stats}
