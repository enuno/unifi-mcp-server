"""Firewall zone management tools."""

from typing import Any

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..models import FirewallZone
from ..models.zbf_matrix import ZoneNetworkAssignment
from ..utils import ValidationError, audit_action, get_logger, validate_confirmation

logger = get_logger(__name__)


def _ensure_local_api(settings: Settings) -> None:
    """Ensure the UniFi controller is accessed via the local API for ZBF operations."""
    if settings.api_type != APIType.LOCAL:
        raise ValidationError(
            "Zone-Based Firewall endpoints are only available when UNIFI_API_TYPE='local'. "
            "Please configure a local UniFi gateway connection to use these tools."
        )


async def list_firewall_zones(
    site_id: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    """List all firewall zones for a site.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        List of firewall zones
    """
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(f"Listing firewall zones for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones")
        response = await client.get(endpoint)
        data = response.get("data", [])

        return [FirewallZone(**zone).model_dump() for zone in data]  # type: ignore[no-any-return]


async def create_firewall_zone(
    site_id: str,
    name: str,
    settings: Settings,
    description: str | None = None,
    network_ids: list[str] | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a new firewall zone.

    Args:
        site_id: Site identifier
        name: Zone name
        settings: Application settings
        description: Zone description
        network_ids: Network IDs to assign to this zone
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created firewall zone
    """
    validate_confirmation(confirm, "create firewall zone")

    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(f"Creating firewall zone '{name}' for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload
        payload: dict[str, Any] = {
            "name": name,
        }

        if description:
            payload["description"] = description
        if network_ids:
            payload["networks"] = network_ids

        if dry_run:
            logger.info(f"[DRY RUN] Would create firewall zone with payload: {payload}")
            return {"dry_run": True, "payload": payload}

        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.post(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones"),
            json_data=payload,
        )
        data = response.get("data", response)

        # Audit the action
        await audit_action(
            settings,
            action_type="create_firewall_zone",
            resource_type="firewall_zone",
            resource_id=data.get("_id", "unknown"),
            site_id=site_id,
            details={"name": name},
        )

        return FirewallZone(**data).model_dump()  # type: ignore[no-any-return]


async def update_firewall_zone(
    site_id: str,
    firewall_zone_id: str,
    settings: Settings,
    name: str | None = None,
    description: str | None = None,
    network_ids: list[str] | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Update an existing firewall zone.

    Args:
        site_id: Site identifier
        firewall_zone_id: Firewall zone identifier
        settings: Application settings
        name: Zone name
        description: Zone description
        network_ids: Network IDs to assign to this zone
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Updated firewall zone
    """
    validate_confirmation(confirm, "update firewall zone")

    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(f"Updating firewall zone {firewall_zone_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)

        # Fetch current zone to get existing networkIds if not provided
        # API requires networkIds field to always be present
        current_zone_response = await client.get(
            settings.get_integration_path(
                f"sites/{resolved_site_id}/firewall/zones/{firewall_zone_id}"
            )
        )
        current_zone = current_zone_response.get("data", current_zone_response)
        current_network_ids = current_zone.get("networkIds", [])

        # Build request payload - networkIds is required by API
        payload: dict[str, Any] = {
            "networkIds": network_ids if network_ids is not None else current_network_ids
        }

        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description

        if dry_run:
            logger.info(f"[DRY RUN] Would update firewall zone with payload: {payload}")
            return {"dry_run": True, "payload": payload}

        response = await client.put(
            settings.get_integration_path(
                f"sites/{resolved_site_id}/firewall/zones/{firewall_zone_id}"
            ),
            json_data=payload,
        )
        data = response.get("data", response)

        # Audit the action
        await audit_action(
            settings,
            action_type="update_firewall_zone",
            resource_type="firewall_zone",
            resource_id=firewall_zone_id,
            site_id=site_id,
            details=payload,
        )

        return FirewallZone(**data).model_dump()  # type: ignore[no-any-return]


async def assign_network_to_zone(
    site_id: str,
    zone_id: str,
    network_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Dynamically assign a network to a zone.

    Args:
        site_id: Site identifier
        zone_id: Zone identifier
        network_id: Network identifier to assign
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Network assignment information
    """
    validate_confirmation(confirm, "assign network to zone")

    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(f"Assigning network {network_id} to zone {zone_id} on site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)

        # Get network name
        network_name = None
        try:
            network_response = await client.get(
                settings.get_integration_path(f"sites/{resolved_site_id}/networks/{network_id}")
            )
            network_data = network_response.get("data", {})
            network_name = network_data.get("name")
        except Exception:
            logger.warning(f"Could not fetch network name for {network_id}")

        # Update zone to include this network
        zone_response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones/{zone_id}")
        )
        zone_data = zone_response.get("data", {})
        current_networks = zone_data.get("networks", [])

        if network_id in current_networks:
            logger.info(f"Network {network_id} already assigned to zone {zone_id}")
            return ZoneNetworkAssignment(  # type: ignore[no-any-return]
                zone_id=zone_id,
                network_id=network_id,
                network_name=network_name,
            ).model_dump()

        updated_networks = list(current_networks) + [network_id]

        payload = {"networks": updated_networks}

        if dry_run:
            logger.info(f"[DRY RUN] Would assign network {network_id} to zone {zone_id}")
            return {"dry_run": True, "payload": payload}

        await client.put(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones/{zone_id}"),
            json_data=payload,
        )

        # Audit the action
        await audit_action(
            settings,
            action_type="assign_network_to_zone",
            resource_type="zone_network_assignment",
            resource_id=network_id,
            site_id=site_id,
            details={"zone_id": zone_id, "network_id": network_id},
        )

        return ZoneNetworkAssignment(  # type: ignore[no-any-return]
            zone_id=zone_id,
            network_id=network_id,
            network_name=network_name,
        ).model_dump()


async def get_zone_networks(site_id: str, zone_id: str, settings: Settings) -> list[dict[str, Any]]:
    """List all networks in a zone.

    Args:
        site_id: Site identifier
        zone_id: Zone identifier
        settings: Application settings

    Returns:
        List of networks in the zone
    """
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(f"Listing networks in zone {zone_id} on site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)

        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones/{zone_id}")
        )
        zone_data = response.get("data", {})
        network_ids = zone_data.get("networks", [])

        # Fetch network details for each network ID
        networks = []
        for network_id in network_ids:
            try:
                network_response = await client.get(
                    settings.get_integration_path(f"sites/{resolved_site_id}/networks/{network_id}")
                )
                network_data = network_response.get("data", {})
                networks.append(
                    ZoneNetworkAssignment(
                        zone_id=zone_id,
                        network_id=network_id,
                        network_name=network_data.get("name"),
                    ).model_dump()
                )
            except Exception:
                # If network fetch fails, still include the assignment with just IDs
                networks.append(
                    ZoneNetworkAssignment(
                        zone_id=zone_id,
                        network_id=network_id,
                    ).model_dump()
                )

        return networks


async def delete_firewall_zone(
    site_id: str,
    zone_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete a firewall zone.

    Args:
        site_id: Site identifier
        zone_id: Zone identifier to delete
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion confirmation

    Raises:
        ValueError: If confirmation not provided
    """
    validate_confirmation(confirm, "delete firewall zone")

    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(f"Deleting firewall zone {zone_id} from site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(f"[DRY RUN] Would delete firewall zone {zone_id}")
            return {"dry_run": True, "zone_id": zone_id, "action": "would_delete"}

        resolved_site_id = await client.resolve_site_id(site_id)
        await client.delete(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones/{zone_id}")
        )

        # Audit the action
        await audit_action(
            settings,
            action_type="delete_firewall_zone",
            resource_type="firewall_zone",
            resource_id=zone_id,
            site_id=site_id,
            details={"zone_id": zone_id},
        )

        return {"status": "success", "zone_id": zone_id, "action": "deleted"}


async def unassign_network_from_zone(
    site_id: str,
    zone_id: str,
    network_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Remove a network from a firewall zone.

    Args:
        site_id: Site identifier
        zone_id: Zone identifier
        network_id: Network identifier to remove
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Network unassignment confirmation

    Raises:
        ValueError: If confirmation not provided or network not in zone
    """
    validate_confirmation(confirm, "unassign network from zone")

    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(f"Unassigning network {network_id} from zone {zone_id} on site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)

        # Get current zone configuration
        zone_response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones/{zone_id}")
        )
        zone_data = zone_response.get("data", {})
        current_networks = zone_data.get("networks", [])

        if network_id not in current_networks:
            raise ValueError(f"Network {network_id} is not assigned to zone {zone_id}")

        # Remove network from list
        updated_networks = [nid for nid in current_networks if nid != network_id]

        payload = {"networks": updated_networks}

        if dry_run:
            logger.info(f"[DRY RUN] Would remove network {network_id} from zone {zone_id}")
            return {"dry_run": True, "payload": payload}

        await client.put(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones/{zone_id}"),
            json_data=payload,
        )

        # Audit the action
        await audit_action(
            settings,
            action_type="unassign_network_from_zone",
            resource_type="zone_network_assignment",
            resource_id=network_id,
            site_id=site_id,
            details={"zone_id": zone_id, "network_id": network_id},
        )

        return {
            "status": "success",
            "zone_id": zone_id,
            "network_id": network_id,
            "action": "unassigned",
        }


async def get_zone_statistics(
    site_id: str,
    zone_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get traffic statistics for a firewall zone.

    ⚠️ **DEPRECATED - ENDPOINT DOES NOT EXIST**

    This endpoint has been verified to NOT EXIST in UniFi Network API v10.0.156.
    Tested on UniFi Express 7 and UDM Pro on 2025-11-18.

    Zone traffic statistics are not available via the API.
    Monitor traffic via /sites/{siteId}/clients endpoint instead.

    See tests/verification/PHASE2_FINDINGS.md for details.

    Args:
        site_id: Site identifier
        zone_id: Zone identifier
        settings: Application settings

    Returns:
        Zone traffic statistics including bandwidth usage and connection counts

    Raises:
        NotImplementedError: This endpoint does not exist in the UniFi API
    """
    logger.warning(
        f"get_zone_statistics called for zone {zone_id} but endpoint does not exist in UniFi API v10.0.156."
    )
    raise NotImplementedError(
        "Zone statistics endpoint does not exist in UniFi Network API v10.0.156. "
        "Verified on U7 Express and UDM Pro (2025-11-18). "
        "Monitor traffic via /sites/{siteId}/clients endpoint instead. "
        "See tests/verification/PHASE2_FINDINGS.md for details."
    )
