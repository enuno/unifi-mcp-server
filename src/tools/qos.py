"""QoS (Quality of Service) management tools."""

from typing import Any

from ..api.client import UniFiClient
from ..config import Settings
from ..models.qos_profile import PROAV_TEMPLATES, REFERENCE_PROFILES, QoSProfile, TrafficRoute
from ..utils import ValidationError, audit_action, get_logger, validate_confirmation

logger = get_logger(__name__)


# ============================================================================
# QoS Profile Management (5 tools)
# ============================================================================


async def list_qos_profiles(
    site_id: str,
    settings: Settings,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List all QoS profiles for a site.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of profiles to return
        offset: Number of profiles to skip

    Returns:
        List of QoS profiles
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Listing QoS profiles for site {site_id} (limit={limit}, offset={offset})")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/qosprofile")
        response = await client.get(endpoint)
        data = response.get("data", [])

        # Apply pagination
        paginated_data = data[offset : offset + limit]

        return [QoSProfile(**profile).model_dump() for profile in paginated_data]  # type: ignore[no-any-return]


async def get_qos_profile(
    site_id: str,
    profile_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get a specific QoS profile by ID.

    Args:
        site_id: Site identifier
        profile_id: QoS profile ID
        settings: Application settings

    Returns:
        QoS profile details
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Getting QoS profile {profile_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/qosprofile/{profile_id}")
        response = await client.get(endpoint)
        data = response.get("data", [])

        if not data:
            raise ValidationError(f"QoS profile {profile_id} not found")

        return QoSProfile(**data[0]).model_dump()  # type: ignore[no-any-return]


async def create_qos_profile(
    site_id: str,
    name: str,
    priority_level: int,
    settings: Settings,
    description: str | None = None,
    dscp_marking: int | None = None,
    bandwidth_limit_down_kbps: int | None = None,
    bandwidth_limit_up_kbps: int | None = None,
    bandwidth_guaranteed_down_kbps: int | None = None,
    bandwidth_guaranteed_up_kbps: int | None = None,
    ports: list[int] | None = None,
    protocols: list[str] | None = None,
    applications: list[str] | None = None,
    categories: list[str] | None = None,
    schedule_enabled: bool = False,
    schedule_days: list[str] | None = None,
    schedule_time_start: str | None = None,
    schedule_time_end: str | None = None,
    enabled: bool = True,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a new QoS profile with comprehensive traffic shaping.

    Args:
        site_id: Site identifier
        name: Profile name
        priority_level: Priority level (0-7, where 7 is highest)
        settings: Application settings
        description: Profile description
        dscp_marking: DSCP value to mark packets (0-63)
        bandwidth_limit_down_kbps: Download bandwidth limit in kbps
        bandwidth_limit_up_kbps: Upload bandwidth limit in kbps
        bandwidth_guaranteed_down_kbps: Guaranteed download bandwidth in kbps
        bandwidth_guaranteed_up_kbps: Guaranteed upload bandwidth in kbps
        ports: Port numbers to match
        protocols: Protocols to match (tcp, udp, icmp)
        applications: Application IDs to match
        categories: Category IDs to match
        schedule_enabled: Enable time-based schedule
        schedule_days: Days active (mon, tue, wed, thu, fri, sat, sun)
        schedule_time_start: Start time (HH:MM format)
        schedule_time_end: End time (HH:MM format)
        enabled: Profile enabled
        confirm: Confirmation flag (required for creation)
        dry_run: If True, validate but don't execute

    Returns:
        Created QoS profile
    """
    validate_confirmation(confirm, "create QoS profile", dry_run)

    # Validate priority level
    if not 0 <= priority_level <= 7:
        raise ValidationError(f"Priority level must be 0-7, got {priority_level}")

    # Validate DSCP marking
    if dscp_marking is not None and not 0 <= dscp_marking <= 63:
        raise ValidationError(f"DSCP marking must be 0-63, got {dscp_marking}")

    # Build profile data
    profile_data: dict[str, Any] = {
        "name": name,
        "priority_level": priority_level,
        "enabled": enabled,
    }

    if description:
        profile_data["description"] = description
    if dscp_marking is not None:
        profile_data["dscp_marking"] = dscp_marking
    if bandwidth_limit_down_kbps is not None:
        profile_data["bandwidth_limit_down_kbps"] = bandwidth_limit_down_kbps
    if bandwidth_limit_up_kbps is not None:
        profile_data["bandwidth_limit_up_kbps"] = bandwidth_limit_up_kbps
    if bandwidth_guaranteed_down_kbps is not None:
        profile_data["bandwidth_guaranteed_down_kbps"] = bandwidth_guaranteed_down_kbps
    if bandwidth_guaranteed_up_kbps is not None:
        profile_data["bandwidth_guaranteed_up_kbps"] = bandwidth_guaranteed_up_kbps
    if ports:
        profile_data["ports"] = ports
    if protocols:
        profile_data["protocols"] = protocols
    if applications:
        profile_data["applications"] = applications
    if categories:
        profile_data["categories"] = categories

    # Schedule configuration
    if schedule_enabled:
        profile_data["schedule_enabled"] = True
        if schedule_days:
            profile_data["schedule_days"] = schedule_days
        if schedule_time_start:
            profile_data["schedule_time_start"] = schedule_time_start
        if schedule_time_end:
            profile_data["schedule_time_end"] = schedule_time_end

    if dry_run:
        logger.info(f"[DRY RUN] Would create QoS profile: {profile_data}")
        return {"dry_run": True, "profile": profile_data}

    async with UniFiClient(settings) as client:
        logger.info(f"Creating QoS profile '{name}' for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/qosprofile")
        response = await client.post(endpoint, json=profile_data)

        data = response.get("data", [])
        if not data:
            raise ValidationError("Failed to create QoS profile")

        result = QoSProfile(**data[0]).model_dump()

        await audit_action(
            settings,
            action_type="create_qos_profile",
            resource_type="qos_profile",
            resource_id=result.get("id", "unknown"),
            details={
                "name": name,
                "priority_level": priority_level,
                "dscp_marking": dscp_marking,
            },
            site_id=resolved_site_id,
        )

        return result  # type: ignore[no-any-return]


async def update_qos_profile(
    site_id: str,
    profile_id: str,
    settings: Settings,
    name: str | None = None,
    priority_level: int | None = None,
    description: str | None = None,
    dscp_marking: int | None = None,
    bandwidth_limit_down_kbps: int | None = None,
    bandwidth_limit_up_kbps: int | None = None,
    bandwidth_guaranteed_down_kbps: int | None = None,
    bandwidth_guaranteed_up_kbps: int | None = None,
    enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing QoS profile.

    Args:
        site_id: Site identifier
        profile_id: QoS profile ID to update
        settings: Application settings
        name: New profile name
        priority_level: New priority level (0-7)
        description: New description
        dscp_marking: New DSCP marking (0-63)
        bandwidth_limit_down_kbps: New download limit
        bandwidth_limit_up_kbps: New upload limit
        bandwidth_guaranteed_down_kbps: New guaranteed download
        bandwidth_guaranteed_up_kbps: New guaranteed upload
        enabled: New enabled state
        confirm: Confirmation flag (required for updates)
        dry_run: If True, validate but don't execute

    Returns:
        Updated QoS profile
    """
    validate_confirmation(confirm, "update QoS profile", dry_run)

    # Validate priority level if provided
    if priority_level is not None and not 0 <= priority_level <= 7:
        raise ValidationError(f"Priority level must be 0-7, got {priority_level}")

    # Validate DSCP marking if provided
    if dscp_marking is not None and not 0 <= dscp_marking <= 63:
        raise ValidationError(f"DSCP marking must be 0-63, got {dscp_marking}")

    # Build update data (only include provided fields)
    update_data: dict[str, Any] = {}
    if name is not None:
        update_data["name"] = name
    if priority_level is not None:
        update_data["priority_level"] = priority_level
    if description is not None:
        update_data["description"] = description
    if dscp_marking is not None:
        update_data["dscp_marking"] = dscp_marking
    if bandwidth_limit_down_kbps is not None:
        update_data["bandwidth_limit_down_kbps"] = bandwidth_limit_down_kbps
    if bandwidth_limit_up_kbps is not None:
        update_data["bandwidth_limit_up_kbps"] = bandwidth_limit_up_kbps
    if bandwidth_guaranteed_down_kbps is not None:
        update_data["bandwidth_guaranteed_down_kbps"] = bandwidth_guaranteed_down_kbps
    if bandwidth_guaranteed_up_kbps is not None:
        update_data["bandwidth_guaranteed_up_kbps"] = bandwidth_guaranteed_up_kbps
    if enabled is not None:
        update_data["enabled"] = enabled

    if not update_data:
        raise ValidationError("No update fields provided")

    if dry_run:
        logger.info(f"[DRY RUN] Would update QoS profile {profile_id}: {update_data}")
        return {"dry_run": True, "profile_id": profile_id, "updates": update_data}

    async with UniFiClient(settings) as client:
        logger.info(f"Updating QoS profile {profile_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/qosprofile/{profile_id}")
        response = await client.put(endpoint, json=update_data)

        data = response.get("data", [])
        if not data:
            raise ValidationError(f"Failed to update QoS profile {profile_id}")

        result = QoSProfile(**data[0]).model_dump()

        await audit_action(
            settings,
            action_type="update_qos_profile",
            resource_type="qos_profile",
            resource_id=profile_id,
            details=update_data,
            site_id=resolved_site_id,
        )

        return result  # type: ignore[no-any-return]


async def delete_qos_profile(
    site_id: str,
    profile_id: str,
    settings: Settings,
    confirm: bool | str = False,
) -> dict[str, Any]:
    """Delete a QoS profile.

    Args:
        site_id: Site identifier
        profile_id: QoS profile ID to delete
        settings: Application settings
        confirm: Confirmation flag (required for deletion)

    Returns:
        Deletion confirmation
    """
    validate_confirmation(confirm, "delete QoS profile")

    async with UniFiClient(settings) as client:
        logger.info(f"Deleting QoS profile {profile_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/qosprofile/{profile_id}")
        await client.delete(endpoint)

        await audit_action(
            settings,
            action_type="delete_qos_profile",
            resource_type="qos_profile",
            resource_id=profile_id,
            details={"deleted": True},
            site_id=resolved_site_id,
        )

        return {  # type: ignore[no-any-return]
            "success": True,
            "message": f"QoS profile {profile_id} deleted successfully",
            "profile_id": profile_id,
        }


# ============================================================================
# ProAV Profile Management (3 tools)
# ============================================================================


async def list_proav_templates(settings: Settings) -> list[dict[str, Any]]:
    """List available ProAV protocol templates.

    Returns predefined templates for professional audio/video protocols:
    - Dante (Audinate)
    - Q-SYS (QSC)
    - SDVoE Alliance
    - AVB (IEEE 802.1)
    - AES67/RAVENNA
    - NDI (NewTek)
    - SMPTE ST 2110

    Args:
        settings: Application settings

    Returns:
        List of ProAV templates with recommended settings
    """
    logger.info("Listing ProAV templates")

    # Return all ProAV templates from models
    templates = []
    for protocol_key, template_data in PROAV_TEMPLATES.items():
        templates.append(
            {
                "protocol": protocol_key,
                **template_data,
            }
        )

    # Also include reference profiles
    for profile_key, profile_data in REFERENCE_PROFILES.items():
        templates.append(
            {
                "profile_type": "reference",
                "key": profile_key,
                **profile_data,
            }
        )

    return templates


async def create_proav_profile(
    site_id: str,
    protocol: str,
    settings: Settings,
    name: str | None = None,
    customize_ports: list[int] | None = None,
    customize_bandwidth_down_kbps: int | None = None,
    customize_bandwidth_up_kbps: int | None = None,
    customize_dscp: int | None = None,
    enabled: bool = True,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a QoS profile from a ProAV template.

    Creates a QoS profile using predefined settings for professional audio/video protocols.
    Supports customization of recommended settings while maintaining best practices.

    Args:
        site_id: Site identifier
        protocol: ProAV protocol (dante, q-sys, sdvoe, avb, ravenna, ndi, smpte-2110)
                  or reference profile (voice-first, video-conferencing, etc.)
        settings: Application settings
        name: Custom profile name (uses template name if not provided)
        customize_ports: Override default ports
        customize_bandwidth_down_kbps: Override download bandwidth
        customize_bandwidth_up_kbps: Override upload bandwidth
        customize_dscp: Override DSCP marking
        enabled: Profile enabled
        confirm: Confirmation flag (required for creation)
        dry_run: If True, validate but don't execute

    Returns:
        Created QoS profile
    """
    validate_confirmation(confirm, "create ProAV profile", dry_run)

    # Check if it's a ProAV template or reference profile
    if protocol in PROAV_TEMPLATES:
        template = PROAV_TEMPLATES[protocol]
        is_reference = False
    elif protocol in REFERENCE_PROFILES:
        template = REFERENCE_PROFILES[protocol]
        is_reference = True
    else:
        available = list(PROAV_TEMPLATES.keys()) + list(REFERENCE_PROFILES.keys())
        raise ValidationError(
            f"Unknown protocol '{protocol}'. " f"Available options: {', '.join(available)}"
        )

    # Build profile from template
    profile_name = name or template["name"]
    priority_level = template["priority_level"]
    dscp_marking = customize_dscp if customize_dscp is not None else template["dscp_marking"]

    # Ports from template or customization
    if is_reference:
        ports = customize_ports or template.get("ports", [])
        protocols_list = template.get("protocols", ["tcp", "udp"])
    else:
        # ProAV template has separate TCP/UDP ports
        if customize_ports:
            ports = customize_ports
        else:
            ports = template.get("udp_ports", []) + template.get("tcp_ports", [])
        protocols_list = []
        if template.get("udp_ports"):
            protocols_list.append("udp")
        if template.get("tcp_ports"):
            protocols_list.append("tcp")

    # Bandwidth settings
    bandwidth_down_kbps = customize_bandwidth_down_kbps
    bandwidth_up_kbps = customize_bandwidth_up_kbps

    # Convert template bandwidth from Mbps to kbps if needed
    if not bandwidth_down_kbps and template.get("min_bandwidth_mbps"):
        bandwidth_down_kbps = template["min_bandwidth_mbps"] * 1000

    # Use guaranteed bandwidth from reference profiles
    if not bandwidth_down_kbps and template.get("bandwidth_guaranteed_down_kbps"):
        bandwidth_down_kbps = template["bandwidth_guaranteed_down_kbps"]
    if not bandwidth_up_kbps and template.get("bandwidth_guaranteed_up_kbps"):
        bandwidth_up_kbps = template["bandwidth_guaranteed_up_kbps"]

    # Use bandwidth limits from reference profiles
    bandwidth_limit_down = template.get("bandwidth_limit_down_kbps")
    bandwidth_limit_up = template.get("bandwidth_limit_up_kbps")

    # Create the profile
    return await create_qos_profile(
        site_id=site_id,
        name=profile_name,
        priority_level=priority_level,
        settings=settings,
        description=template["description"],
        dscp_marking=dscp_marking,
        bandwidth_guaranteed_down_kbps=bandwidth_down_kbps,
        bandwidth_guaranteed_up_kbps=bandwidth_up_kbps,
        bandwidth_limit_down_kbps=bandwidth_limit_down,
        bandwidth_limit_up_kbps=bandwidth_limit_up,
        ports=ports,
        protocols=protocols_list,
        enabled=enabled,
        confirm=confirm,
        dry_run=dry_run,
    )


async def validate_proav_profile(
    protocol: str,
    settings: Settings,
    bandwidth_mbps: int | None = None,
) -> dict[str, Any]:
    """Validate ProAV profile requirements and provide recommendations.

    Checks if the network meets minimum requirements for the specified ProAV protocol.
    Provides warnings and recommendations for optimal performance.

    Args:
        protocol: ProAV protocol to validate
        settings: Application settings
        bandwidth_mbps: Available bandwidth in Mbps (optional, for validation)

    Returns:
        Validation results with warnings and recommendations
    """
    logger.info(f"Validating ProAV profile for protocol: {protocol}")

    if protocol not in PROAV_TEMPLATES:
        raise ValidationError(
            f"Unknown ProAV protocol '{protocol}'. "
            f"Available: {', '.join(PROAV_TEMPLATES.keys())}"
        )

    template = PROAV_TEMPLATES[protocol]
    min_bandwidth = template.get("min_bandwidth_mbps", 0)
    max_latency = template.get("max_latency_ms", 100)

    # Validation results
    validation = {
        "protocol": protocol,
        "valid": True,
        "warnings": [],
        "recommendations": [],
    }

    # Check bandwidth requirements
    if bandwidth_mbps is not None and bandwidth_mbps < min_bandwidth:
        validation["valid"] = False
        validation["warnings"].append(
            f"Insufficient bandwidth: {bandwidth_mbps} Mbps available, "
            f"{min_bandwidth} Mbps required"
        )

    # Protocol-specific recommendations
    if template.get("ptp_enabled"):
        validation["recommendations"].append(
            f"Enable PTP (Precision Time Protocol) with domain {template.get('ptp_domain', 0)}"
        )

    if template.get("multicast_enabled"):
        validation["recommendations"].append(
            f"Configure multicast routing for {template.get('multicast_range', 'N/A')}"
        )

    if max_latency <= 10:
        validation["recommendations"].append("Use dedicated VLAN for time-sensitive traffic")
        validation["recommendations"].append("Enable hardware offload on network switches")

    if min_bandwidth >= 1000:  # >= 1 Gbps
        validation["recommendations"].append(
            "Use 10 Gbps network infrastructure for optimal performance"
        )

    return validation


# ============================================================================
# Smart Queue Management (3 tools)
# ============================================================================


async def get_smart_queue_config(
    site_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get Smart Queue Management (SQM) configuration.

    Returns the current SQM configuration for bufferbloat mitigation.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        SQM configuration
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Getting SQM configuration for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/wanconf")
        response = await client.get(endpoint)
        data = response.get("data", [])

        if not data:
            raise ValidationError("No WAN configuration found")

        # Return first WAN config (primary)
        wan_config = data[0]

        return {  # type: ignore[no-any-return]
            "wan_id": wan_config.get("_id"),
            "enabled": wan_config.get("sqm_enabled", False),
            "algorithm": wan_config.get("sqm_algorithm", "fq_codel"),
            "download_kbps": wan_config.get("sqm_download_kbps", 0),
            "upload_kbps": wan_config.get("sqm_upload_kbps", 0),
            "overhead_bytes": wan_config.get("sqm_overhead_bytes", 44),
        }


async def configure_smart_queue(
    site_id: str,
    wan_id: str,
    download_kbps: int,
    upload_kbps: int,
    settings: Settings,
    algorithm: str = "fq_codel",
    overhead_bytes: int = 44,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Configure Smart Queue Management (SQM) for bufferbloat mitigation.

    Enables and configures SQM using fq_codel or CAKE algorithms to reduce bufferbloat.
    Set bandwidth limits to 90-95% of actual line rate for optimal performance.

    Args:
        site_id: Site identifier
        wan_id: WAN interface ID
        download_kbps: Download bandwidth in kbps (set to 90-95% of line rate)
        upload_kbps: Upload bandwidth in kbps (set to 90-95% of line rate)
        settings: Application settings
        algorithm: Queue algorithm (fq_codel or cake)
        overhead_bytes: Per-packet overhead in bytes (default: 44 for PPPoE)
        confirm: Confirmation flag (required for configuration)
        dry_run: If True, validate but don't execute

    Returns:
        SQM configuration
    """
    validate_confirmation(confirm, "configure Smart Queue Management", dry_run)

    # Validate bandwidth
    if download_kbps <= 0 or upload_kbps <= 0:
        raise ValidationError("Bandwidth must be greater than 0 kbps")

    # Validate algorithm
    if algorithm not in ["fq_codel", "cake"]:
        raise ValidationError(f"Invalid algorithm '{algorithm}'. Use 'fq_codel' or 'cake'")

    # Performance warnings
    warnings = []
    if download_kbps > 300000:  # > 300 Mbps
        warnings.append(
            "SQM may not be effective above 300 Mbps. "
            "Consider hardware-based QoS for gigabit+ connections."
        )

    sqm_config = {
        "sqm_enabled": True,
        "sqm_algorithm": algorithm,
        "sqm_download_kbps": download_kbps,
        "sqm_upload_kbps": upload_kbps,
        "sqm_overhead_bytes": overhead_bytes,
    }

    if dry_run:
        logger.info(f"[DRY RUN] Would configure SQM: {sqm_config}")
        return {
            "dry_run": True,
            "wan_id": wan_id,
            "config": sqm_config,
            "warnings": warnings,
        }

    async with UniFiClient(settings) as client:
        logger.info(f"Configuring SQM for WAN {wan_id} on site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/wanconf/{wan_id}")
        response = await client.put(endpoint, json=sqm_config)

        data = response.get("data", [])
        if not data:
            raise ValidationError(f"Failed to configure SQM for WAN {wan_id}")

        await audit_action(
            settings,
            action_type="configure_smart_queue",
            resource_type="wan_config",
            resource_id=wan_id,
            details=sqm_config,
            site_id=resolved_site_id,
        )

        result = {
            "success": True,
            "wan_id": wan_id,
            "config": sqm_config,
            "warnings": warnings,
        }

        return result  # type: ignore[no-any-return]


async def disable_smart_queue(
    site_id: str,
    wan_id: str,
    settings: Settings,
    confirm: bool | str = False,
) -> dict[str, Any]:
    """Disable Smart Queue Management (SQM).

    Args:
        site_id: Site identifier
        wan_id: WAN interface ID
        settings: Application settings
        confirm: Confirmation flag (required for changes)

    Returns:
        Disabling confirmation
    """
    validate_confirmation(confirm, "disable Smart Queue Management")

    async with UniFiClient(settings) as client:
        logger.info(f"Disabling SQM for WAN {wan_id} on site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/wanconf/{wan_id}")
        response = await client.put(endpoint, json={"sqm_enabled": False})

        data = response.get("data", [])
        if not data:
            raise ValidationError(f"Failed to disable SQM for WAN {wan_id}")

        await audit_action(
            settings,
            action_type="disable_smart_queue",
            resource_type="wan_config",
            resource_id=wan_id,
            details={"sqm_enabled": False},
            site_id=resolved_site_id,
        )

        return {  # type: ignore[no-any-return]
            "success": True,
            "message": f"SQM disabled for WAN {wan_id}",
            "wan_id": wan_id,
        }


# ============================================================================
# Traffic Route Management (4 tools)
# ============================================================================


async def list_traffic_routes(
    site_id: str,
    settings: Settings,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List all traffic routing policies for a site.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of routes to return
        offset: Number of routes to skip

    Returns:
        List of traffic routing policies
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Listing traffic routes for site {site_id} (limit={limit}, offset={offset})")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/routing")
        response = await client.get(endpoint)
        data = response.get("data", [])

        # Apply pagination
        paginated_data = data[offset : offset + limit]

        return [TrafficRoute(**route).model_dump() for route in paginated_data]  # type: ignore[no-any-return]


async def create_traffic_route(
    site_id: str,
    name: str,
    action: str,
    settings: Settings,
    description: str | None = None,
    source_ip: str | None = None,
    destination_ip: str | None = None,
    source_port: int | None = None,
    destination_port: int | None = None,
    protocol: str | None = None,
    vlan_id: int | None = None,
    dscp_marking: int | None = None,
    bandwidth_limit_kbps: int | None = None,
    priority: int = 100,
    enabled: bool = True,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a new traffic routing policy.

    Args:
        site_id: Site identifier
        name: Route name
        action: Route action (allow, deny, mark, shape)
        settings: Application settings
        description: Route description
        source_ip: Source IP address or CIDR
        destination_ip: Destination IP address or CIDR
        source_port: Source port (1-65535)
        destination_port: Destination port (1-65535)
        protocol: Protocol (tcp, udp, icmp, all)
        vlan_id: VLAN ID (1-4094)
        dscp_marking: DSCP value to mark packets (0-63, for mark action)
        bandwidth_limit_kbps: Bandwidth limit in kbps (for shape action)
        priority: Route priority (1-1000, lower = higher priority)
        enabled: Route enabled
        confirm: Confirmation flag (required for creation)
        dry_run: If True, validate but don't execute

    Returns:
        Created traffic route
    """
    validate_confirmation(confirm, "create traffic route", dry_run)

    # Validate action
    valid_actions = ["allow", "deny", "mark", "shape"]
    if action not in valid_actions:
        raise ValidationError(f"Invalid action '{action}'. Use: {', '.join(valid_actions)}")

    # Validate DSCP marking
    if dscp_marking is not None and not 0 <= dscp_marking <= 63:
        raise ValidationError(f"DSCP marking must be 0-63, got {dscp_marking}")

    # Validate priority
    if not 1 <= priority <= 1000:
        raise ValidationError(f"Priority must be 1-1000, got {priority}")

    # Build match criteria
    match_criteria = {}
    if source_ip:
        match_criteria["source_ip"] = source_ip
    if destination_ip:
        match_criteria["destination_ip"] = destination_ip
    if source_port:
        match_criteria["source_port"] = source_port
    if destination_port:
        match_criteria["destination_port"] = destination_port
    if protocol:
        match_criteria["protocol"] = protocol
    if vlan_id:
        match_criteria["vlan_id"] = vlan_id

    # Build route data
    route_data: dict[str, Any] = {
        "name": name,
        "action": action,
        "match_criteria": match_criteria,
        "priority": priority,
        "enabled": enabled,
    }

    if description:
        route_data["description"] = description
    if dscp_marking is not None:
        route_data["dscp_marking"] = dscp_marking
    if bandwidth_limit_kbps is not None:
        route_data["bandwidth_limit_kbps"] = bandwidth_limit_kbps

    if dry_run:
        logger.info(f"[DRY RUN] Would create traffic route: {route_data}")
        return {"dry_run": True, "route": route_data}

    async with UniFiClient(settings) as client:
        logger.info(f"Creating traffic route '{name}' for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/routing")
        response = await client.post(endpoint, json=route_data)

        data = response.get("data", [])
        if not data:
            raise ValidationError("Failed to create traffic route")

        result = TrafficRoute(**data[0]).model_dump()

        await audit_action(
            settings,
            action_type="create_traffic_route",
            resource_type="traffic_route",
            resource_id=result.get("id", "unknown"),
            details={"name": name, "action": action},
            site_id=resolved_site_id,
        )

        return result  # type: ignore[no-any-return]


async def update_traffic_route(
    site_id: str,
    route_id: str,
    settings: Settings,
    name: str | None = None,
    action: str | None = None,
    description: str | None = None,
    enabled: bool | None = None,
    priority: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing traffic routing policy.

    Args:
        site_id: Site identifier
        route_id: Traffic route ID to update
        settings: Application settings
        name: New route name
        action: New route action (allow, deny, mark, shape)
        description: New description
        enabled: New enabled state
        priority: New priority (1-1000)
        confirm: Confirmation flag (required for updates)
        dry_run: If True, validate but don't execute

    Returns:
        Updated traffic route
    """
    validate_confirmation(confirm, "update traffic route", dry_run)

    # Build update data
    update_data: dict[str, Any] = {}
    if name is not None:
        update_data["name"] = name
    if action is not None:
        update_data["action"] = action
    if description is not None:
        update_data["description"] = description
    if enabled is not None:
        update_data["enabled"] = enabled
    if priority is not None:
        if not 1 <= priority <= 1000:
            raise ValidationError(f"Priority must be 1-1000, got {priority}")
        update_data["priority"] = priority

    if not update_data:
        raise ValidationError("No update fields provided")

    if dry_run:
        logger.info(f"[DRY RUN] Would update traffic route {route_id}: {update_data}")
        return {"dry_run": True, "route_id": route_id, "updates": update_data}

    async with UniFiClient(settings) as client:
        logger.info(f"Updating traffic route {route_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/routing/{route_id}")
        response = await client.put(endpoint, json=update_data)

        data = response.get("data", [])
        if not data:
            raise ValidationError(f"Failed to update traffic route {route_id}")

        result = TrafficRoute(**data[0]).model_dump()

        await audit_action(
            settings,
            action_type="update_traffic_route",
            resource_type="traffic_route",
            resource_id=route_id,
            details=update_data,
            site_id=resolved_site_id,
        )

        return result  # type: ignore[no-any-return]


async def delete_traffic_route(
    site_id: str,
    route_id: str,
    settings: Settings,
    confirm: bool | str = False,
) -> dict[str, Any]:
    """Delete a traffic routing policy.

    Args:
        site_id: Site identifier
        route_id: Traffic route ID to delete
        settings: Application settings
        confirm: Confirmation flag (required for deletion)

    Returns:
        Deletion confirmation
    """
    validate_confirmation(confirm, "delete traffic route")

    async with UniFiClient(settings) as client:
        logger.info(f"Deleting traffic route {route_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_api_path(f"s/{resolved_site_id}/rest/routing/{route_id}")
        await client.delete(endpoint)

        await audit_action(
            settings,
            action_type="delete_traffic_route",
            resource_type="traffic_route",
            resource_id=route_id,
            details={"deleted": True},
            site_id=resolved_site_id,
        )

        return {  # type: ignore[no-any-return]
            "success": True,
            "message": f"Traffic route {route_id} deleted successfully",
            "route_id": route_id,
        }
