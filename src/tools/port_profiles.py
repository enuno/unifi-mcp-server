"""Port profile and device port override MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models.port_profile import PortOverride, PortProfile, PortTableEntry
from ..utils import (
    DuplicateResourceError,
    ResourceNotFoundError,
    ValidationError,
    first_response_item,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_confirmation,
    validate_limit_offset,
    validate_mac_address,
    validate_site_id,
)

# Current controllers drive tagged VLAN handling from tagged_vlan_mgmt and
# derive the legacy `forward` field from it. "block_all" is the access-port
# case: native network untagged, no tagged VLANs carried.
VALID_TAGGED_VLAN_MGMT = ["auto", "block_all", "custom"]


def _stored_value_warnings(requested: dict[str, Any], stored: dict[str, Any]) -> list[str]:
    """Report requested fields the controller did not store as asked.

    The controller silently normalizes some fields -- notably ``forward``, which
    it may rewrite to ``customize`` regardless of the value sent. Returning
    success while the stored configuration differs from the requested one hides
    a real difference in port behaviour, so surface it to the caller instead.

    Args:
        requested: Field values sent to the controller
        stored: Field values the controller echoed back

    Returns:
        One human-readable warning per field that differs or was dropped,
        empty if everything was stored as requested
    """
    warnings = []
    for key, value in requested.items():
        if key not in stored:
            # A dropped field is the same silent-ignore this helper exists
            # to expose; absence from the stored profile means the write
            # cannot be confirmed.
            warnings.append(f"Controller did not store {key} (requested {value!r})")
        elif stored[key] != value:
            warnings.append(f"Controller stored {key}={stored[key]!r}, not the requested {value!r}")
    return warnings


async def list_port_profiles(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all switch port profiles in a site (read-only).

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of profiles to return
        offset: Number of profiles to skip

    Returns:
        List of port profile dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/portconf")
        raw_profiles: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        paginated = raw_profiles[offset : offset + limit]
        profiles = [
            PortProfile.model_validate(p).model_dump(by_alias=True, exclude_none=True)
            for p in paginated
        ]

        logger.info(
            sanitize_log_message(f"Retrieved {len(profiles)} port profiles for site '{site_id}'")
        )
        return profiles


async def get_port_profile(
    site_id: str,
    profile_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get details for a specific port profile.

    Args:
        site_id: Site identifier
        profile_id: Port profile ID
        settings: Application settings

    Returns:
        Port profile dictionary

    Raises:
        ResourceNotFoundError: If profile not found
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    if not profile_id:
        raise ValidationError("Profile ID cannot be empty")

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/portconf/{profile_id}")
        raw_profiles: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        if not raw_profiles:
            raise ResourceNotFoundError("port_profile", profile_id)

        profile = PortProfile.model_validate(raw_profiles[0])
        logger.info(
            sanitize_log_message(f"Retrieved port profile '{profile_id}' for site '{site_id}'")
        )
        return profile.model_dump(by_alias=True, exclude_none=True)


async def create_port_profile(
    site_id: str,
    name: str,
    forward: str,
    settings: Settings,
    native_networkconf_id: str | None = None,
    excluded_networkconf_ids: list[str] | None = None,
    tagged_networkconf_ids: list[str] | None = None,
    tagged_vlan_mgmt: str | None = None,
    poe_mode: str | None = None,
    speed: int | None = None,
    full_duplex: bool | None = None,
    autoneg: bool | None = None,
    dot1x_ctrl: str | None = None,
    lldpmed_enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a new switch port profile.

    Args:
        site_id: Site identifier
        name: Profile name
        forward: Legacy forwarding mode (all, native, customize, disabled).
            On current controllers this is derived from tagged_vlan_mgmt rather
            than honoured directly -- sending forward alone leaves the profile
            on the controller's default. Set tagged_vlan_mgmt to choose.
        settings: Application settings
        native_networkconf_id: Native network configuration ID
        excluded_networkconf_ids: Excluded network configuration IDs
        tagged_networkconf_ids: Tagged network configuration IDs
        tagged_vlan_mgmt: Tagged VLAN management (auto, block_all, custom).
            block_all makes the port carry only its native network untagged,
            which is what an access port needs.
        poe_mode: PoE mode (auto, off, pasv24, passthrough)
        speed: Port speed in Mbps
        full_duplex: Full duplex mode
        autoneg: Auto-negotiation enabled
        dot1x_ctrl: 802.1X control mode
        lldpmed_enabled: LLDP-MED enabled
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't create

    Returns:
        Created port profile dictionary or dry-run result

    Raises:
        ValidationError: If validation fails
        DuplicateResourceError: If profile name already exists
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "port profile creation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    # Validate forward mode
    valid_forwards = ["all", "native", "customize", "disabled"]
    if forward not in valid_forwards:
        raise ValidationError(f"Invalid forward mode '{forward}'. Must be one of: {valid_forwards}")

    if tagged_vlan_mgmt is not None and tagged_vlan_mgmt not in VALID_TAGGED_VLAN_MGMT:
        raise ValidationError(
            f"Invalid tagged VLAN management '{tagged_vlan_mgmt}'. "
            f"Must be one of: {VALID_TAGGED_VLAN_MGMT}"
        )

    # Build profile data
    profile_data: dict[str, Any] = {
        "name": name,
        "forward": forward,
    }

    if native_networkconf_id is not None:
        profile_data["native_networkconf_id"] = native_networkconf_id
    if excluded_networkconf_ids is not None:
        profile_data["excluded_networkconf_ids"] = excluded_networkconf_ids
    if tagged_networkconf_ids is not None:
        profile_data["tagged_networkconf_ids"] = tagged_networkconf_ids
    if tagged_vlan_mgmt is not None:
        profile_data["tagged_vlan_mgmt"] = tagged_vlan_mgmt
    if poe_mode is not None:
        profile_data["poe_mode"] = poe_mode
    if speed is not None:
        profile_data["speed"] = speed
    if full_duplex is not None:
        profile_data["full_duplex"] = full_duplex
    if autoneg is not None:
        profile_data["autoneg"] = autoneg
    if dot1x_ctrl is not None:
        profile_data["dot1x_ctrl"] = dot1x_ctrl
    if lldpmed_enabled is not None:
        profile_data["lldpmed_enabled"] = lldpmed_enabled

    parameters = {
        "site_id": site_id,
        "name": name,
        "forward": forward,
        "native_networkconf_id": native_networkconf_id,
    }

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Check for duplicate name
            existing_response = await client.get(f"/ea/sites/{site_id}/rest/portconf")
            existing_profiles: list[dict[str, Any]] = (
                existing_response
                if isinstance(existing_response, list)
                else existing_response.get("data", [])
            )
            for profile in existing_profiles:
                if profile.get("name") == name:
                    raise DuplicateResourceError(
                        "port_profile", name, profile.get("_id", "unknown")
                    )

            if dry_run:
                logger.info(
                    sanitize_log_message(
                        f"DRY RUN: Would create port profile '{name}' in site '{site_id}'"
                    )
                )
                log_audit(
                    operation="create_port_profile",
                    parameters=parameters,
                    result="dry_run",
                    site_id=site_id,
                    dry_run=True,
                )
                return {"dry_run": True, "would_create": profile_data}

            response = await client.post(
                f"/ea/sites/{site_id}/rest/portconf", json_data=profile_data
            )
            created = first_response_item(response)

            warnings = _stored_value_warnings(profile_data, created)
            if warnings:
                for warning in warnings:
                    logger.warning(sanitize_log_message(warning))
                created = {**created, "warnings": warnings}

            logger.info(sanitize_log_message(f"Created port profile '{name}' in site '{site_id}'"))
            log_audit(
                operation="create_port_profile",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return created

    except (DuplicateResourceError, ValidationError):
        raise
    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to create port profile '{name}': {e}"))
        log_audit(
            operation="create_port_profile",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def update_port_profile(
    site_id: str,
    profile_id: str,
    settings: Settings,
    name: str | None = None,
    forward: str | None = None,
    native_networkconf_id: str | None = None,
    excluded_networkconf_ids: list[str] | None = None,
    tagged_networkconf_ids: list[str] | None = None,
    tagged_vlan_mgmt: str | None = None,
    poe_mode: str | None = None,
    speed: int | None = None,
    full_duplex: bool | None = None,
    autoneg: bool | None = None,
    dot1x_ctrl: str | None = None,
    lldpmed_enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing port profile (fetch-then-merge).

    Args:
        site_id: Site identifier
        profile_id: Port profile ID
        settings: Application settings
        name: New profile name
        forward: New legacy forwarding mode (all, native, customize, disabled).
            Derived from tagged_vlan_mgmt on current controllers; set that
            instead to change how tagged VLANs are handled.
        native_networkconf_id: New native network configuration ID
        excluded_networkconf_ids: New excluded network configuration IDs
        tagged_networkconf_ids: New tagged network configuration IDs
        tagged_vlan_mgmt: New tagged VLAN management (auto, block_all, custom)
        poe_mode: New PoE mode
        speed: New port speed in Mbps
        full_duplex: New full duplex mode
        autoneg: New auto-negotiation setting
        dot1x_ctrl: New 802.1X control mode
        lldpmed_enabled: New LLDP-MED setting
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't update

    Returns:
        Updated port profile dictionary or dry-run result

    Raises:
        ValidationError: If validation fails
        ResourceNotFoundError: If profile not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "port profile update", dry_run)
    logger = get_logger(__name__, settings.log_level)

    if not profile_id:
        raise ValidationError("Profile ID cannot be empty")

    # Validate forward mode if provided
    if forward is not None:
        valid_forwards = ["all", "native", "customize", "disabled"]
        if forward not in valid_forwards:
            raise ValidationError(
                f"Invalid forward mode '{forward}'. Must be one of: {valid_forwards}"
            )

    if tagged_vlan_mgmt is not None and tagged_vlan_mgmt not in VALID_TAGGED_VLAN_MGMT:
        raise ValidationError(
            f"Invalid tagged VLAN management '{tagged_vlan_mgmt}'. "
            f"Must be one of: {VALID_TAGGED_VLAN_MGMT}"
        )

    parameters = {
        "site_id": site_id,
        "profile_id": profile_id,
        "name": name,
        "forward": forward,
    }

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would update port profile '{profile_id}' in site '{site_id}'"
            )
        )
        log_audit(
            operation="update_port_profile",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_update": parameters}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Fetch existing profile
            response = await client.get(f"/ea/sites/{site_id}/rest/portconf/{profile_id}")
            profiles: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

            if not profiles:
                raise ResourceNotFoundError("port_profile", profile_id)

            # Collect only the fields the caller explicitly provided, so the
            # post-write comparison does not flag pre-existing values.
            changes: dict[str, Any] = {}
            if name is not None:
                changes["name"] = name
            if forward is not None:
                changes["forward"] = forward
            if native_networkconf_id is not None:
                changes["native_networkconf_id"] = native_networkconf_id
            if excluded_networkconf_ids is not None:
                changes["excluded_networkconf_ids"] = excluded_networkconf_ids
            if tagged_networkconf_ids is not None:
                changes["tagged_networkconf_ids"] = tagged_networkconf_ids
            if tagged_vlan_mgmt is not None:
                changes["tagged_vlan_mgmt"] = tagged_vlan_mgmt
            if poe_mode is not None:
                changes["poe_mode"] = poe_mode
            if speed is not None:
                changes["speed"] = speed
            if full_duplex is not None:
                changes["full_duplex"] = full_duplex
            if autoneg is not None:
                changes["autoneg"] = autoneg
            if dot1x_ctrl is not None:
                changes["dot1x_ctrl"] = dot1x_ctrl
            if lldpmed_enabled is not None:
                changes["lldpmed_enabled"] = lldpmed_enabled

            update_data = {**profiles[0], **changes}

            response = await client.put(
                f"/ea/sites/{site_id}/rest/portconf/{profile_id}",
                json_data=update_data,
            )
            updated = first_response_item(response)

            # An accepted write is not always echoed back. Re-read rather than
            # returning an empty dict, so the caller sees what is actually
            # stored and the comparison below has something to check against.
            if not updated:
                updated = first_response_item(
                    await client.get(f"/ea/sites/{site_id}/rest/portconf/{profile_id}")
                )

            warnings = _stored_value_warnings(changes, updated)
            if warnings:
                for warning in warnings:
                    logger.warning(sanitize_log_message(warning))
                updated = {**updated, "warnings": warnings}

            logger.info(
                sanitize_log_message(f"Updated port profile '{profile_id}' in site '{site_id}'")
            )
            log_audit(
                operation="update_port_profile",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return updated

    except (ResourceNotFoundError, ValidationError):
        raise
    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to update port profile '{profile_id}': {e}"))
        log_audit(
            operation="update_port_profile",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def delete_port_profile(
    site_id: str,
    profile_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Delete a port profile.

    Args:
        site_id: Site identifier
        profile_id: Port profile ID
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't delete

    Returns:
        Deletion result dictionary

    Raises:
        ResourceNotFoundError: If profile not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "port profile deletion", dry_run)
    logger = get_logger(__name__, settings.log_level)

    if not profile_id:
        raise ValidationError("Profile ID cannot be empty")

    parameters = {"site_id": site_id, "profile_id": profile_id}

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would delete port profile '{profile_id}' from site '{site_id}'"
            )
        )
        log_audit(
            operation="delete_port_profile",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_delete": profile_id}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Verify profile exists
            response = await client.get(f"/ea/sites/{site_id}/rest/portconf/{profile_id}")
            profiles: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

            if not profiles:
                raise ResourceNotFoundError("port_profile", profile_id)

            await client.delete(f"/ea/sites/{site_id}/rest/portconf/{profile_id}")

            logger.info(
                sanitize_log_message(f"Deleted port profile '{profile_id}' from site '{site_id}'")
            )
            log_audit(
                operation="delete_port_profile",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {"success": True, "deleted_profile_id": profile_id}

    except ResourceNotFoundError:
        raise
    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to delete port profile '{profile_id}': {e}"))
        log_audit(
            operation="delete_port_profile",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def get_device_port_overrides(
    site_id: str,
    device_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get port overrides and port table for a device.

    Args:
        site_id: Site identifier
        device_id: Device ID
        settings: Application settings

    Returns:
        Dictionary with port_overrides and port_table

    Raises:
        ResourceNotFoundError: If device not found
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    if not device_id:
        raise ValidationError("Device ID cannot be empty")

    async with UniFiClient(settings) as client:
        await client.authenticate()

        # Use stat/device to read device data (rest/device/{id} GET is not supported)
        response = await client.get(f"/ea/sites/{site_id}/stat/device")
        all_devices: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        # Filter by _id or MAC address
        device = next(
            (d for d in all_devices if d.get("_id") == device_id or d.get("mac") == device_id),
            None,
        )

        if not device:
            raise ResourceNotFoundError("device", device_id)

        logger.info(
            sanitize_log_message(
                f"Retrieved port overrides for device '{device_id}' in site '{site_id}'"
            )
        )

        overrides = [
            PortOverride.model_validate(o).model_dump(exclude_none=True)
            for o in device.get("port_overrides", [])
        ]
        port_table = [
            PortTableEntry.model_validate(e).model_dump(exclude_none=True)
            for e in device.get("port_table", [])
        ]

        return {
            "device_id": device.get("_id"),
            "name": device.get("name"),
            "mac": device.get("mac"),
            "model": device.get("model"),
            "port_overrides": overrides,
            "port_table": port_table,
        }


async def set_device_port_overrides(
    site_id: str,
    device_id: str,
    port_overrides: list[dict[str, Any]],
    settings: Settings,
    merge: bool = True,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Set port overrides on a device.

    When merge=True (default), fetches existing overrides and merges by port_idx.
    When merge=False, replaces all overrides with the provided list.

    Args:
        site_id: Site identifier
        device_id: Device ID
        port_overrides: List of port override dicts (port_idx and portconf_id required)
        settings: Application settings
        merge: If True, merge with existing overrides by port_idx (default True)
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't apply

    Returns:
        Updated device port overrides or dry-run result

    Raises:
        ValidationError: If validation fails
        ResourceNotFoundError: If device not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "device port override", dry_run)
    logger = get_logger(__name__, settings.log_level)

    if not device_id:
        raise ValidationError("Device ID cannot be empty")

    # Validate port overrides
    if not port_overrides:
        raise ValidationError("port_overrides cannot be empty")

    # port_idx identifies the port and is genuinely required. portconf_id is
    # not: a port with no profile inherits the site default, and overrides that
    # only set a name, PoE mode or speed are both valid and common. Demanding
    # it made it impossible to rename a port or disable its PoE without also
    # reassigning its profile.
    for override in port_overrides:
        if "port_idx" not in override:
            raise ValidationError("Each port override must include 'port_idx'")
        # At least one field must actually be set: a bare port_idx or one
        # whose only companions are None values would apply nothing. Keys
        # are deliberately not whitelisted -- the controller accepts more
        # override fields than this tool enumerates.
        if not any(v is not None for k, v in override.items() if k != "port_idx"):
            raise ValidationError(
                f"Port override for port_idx {override['port_idx']} sets no "
                "fields. Include at least one of portconf_id, name, poe_mode, "
                "speed, autoneg, full_duplex."
            )

    parameters = {
        "site_id": site_id,
        "device_id": device_id,
        "merge": merge,
        "port_overrides_count": len(port_overrides),
    }

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Use stat/device to read device data (rest/device/{id} GET is not supported)
            response = await client.get(f"/ea/sites/{site_id}/stat/device")
            all_devices: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

            device = next(
                (d for d in all_devices if d.get("_id") == device_id or d.get("mac") == device_id),
                None,
            )

            if not device:
                raise ResourceNotFoundError("device", device_id)

            if merge:
                # Merge by port_idx: new overrides take precedence
                existing = {o["port_idx"]: o for o in device.get("port_overrides", [])}
                for override in port_overrides:
                    existing[override["port_idx"]] = override
                final_overrides = list(existing.values())
            else:
                final_overrides = port_overrides

            if dry_run:
                logger.info(
                    f"DRY RUN: Would set {len(final_overrides)} port overrides "
                    f"on device '{device_id}' in site '{site_id}'"
                )
                log_audit(
                    operation="set_device_port_overrides",
                    parameters=parameters,
                    result="dry_run",
                    site_id=site_id,
                    dry_run=True,
                )
                return {
                    "dry_run": True,
                    "would_set_overrides": final_overrides,
                    "merge": merge,
                }

            # PUT the full device with updated port_overrides
            device["port_overrides"] = final_overrides
            # Use resolved _id for writes (device_id may be a MAC address)
            resolved_id = device["_id"]
            endpoint = settings.get_site_api_path(site_id, f"rest/device/{resolved_id}")
            response = await client.put(
                endpoint,
                json_data=device,
            )
            updated_device = first_response_item(response)

            logger.info(
                f"Set {len(final_overrides)} port overrides on device "
                f"'{device_id}' in site '{site_id}'"
            )
            log_audit(
                operation="set_device_port_overrides",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {
                "device_id": updated_device.get("_id"),
                "port_overrides": updated_device.get("port_overrides", []),
            }

    except (ResourceNotFoundError, ValidationError):
        raise
    except Exception as e:
        logger.error(
            sanitize_log_message(f"Failed to set port overrides on device '{device_id}': {e}")
        )
        log_audit(
            operation="set_device_port_overrides",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def get_device_by_mac(
    site_id: str,
    mac: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get a device by its MAC address.

    Args:
        site_id: Site identifier
        mac: Device MAC address
        settings: Application settings

    Returns:
        Full device dictionary

    Raises:
        ValidationError: If MAC address is invalid
        ResourceNotFoundError: If device not found
    """
    site_id = validate_site_id(site_id)
    mac = validate_mac_address(mac)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/stat/device/{mac}")
        devices: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        if not devices:
            masked = f"{mac[:8]}:xx:xx:xx" if len(mac) >= 8 else "**:**:**:**:**:**"
            raise ResourceNotFoundError("device", masked)

        logger.info(sanitize_log_message(f"Retrieved device by MAC in site '{site_id}'"))
        return devices[0]
