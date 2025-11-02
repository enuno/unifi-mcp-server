"""Firewall zone management tools."""

from ..api.client import UniFiClient
from ..config import Settings
from ..models import FirewallZone
from ..models.zbf_matrix import ZoneNetworkAssignment
from ..utils import audit_action, get_logger, validate_confirmation

logger = get_logger(__name__)


async def list_firewall_zones(
    site_id: str,
    settings: Settings,
) -> list[dict]:
    """List all firewall zones for a site.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        List of firewall zones
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Listing firewall zones for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/firewall/zones")
        data = response.get("data", [])

        return [FirewallZone(**zone).model_dump() for zone in data]


async def create_firewall_zone(
    site_id: str,
    name: str,
    settings: Settings,
    description: str | None = None,
    network_ids: list[str] | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
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

    async with UniFiClient(settings) as client:
        logger.info(f"Creating firewall zone '{name}' for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload
        payload = {
            "name": name,
        }

        if description:
            payload["description"] = description
        if network_ids:
            payload["networks"] = network_ids

        if dry_run:
            logger.info(f"[DRY RUN] Would create firewall zone with payload: {payload}")
            return {"dry_run": True, "payload": payload}

        response = await client.post(
            f"/integration/v1/sites/{site_id}/firewall/zones", json_data=payload
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

        return FirewallZone(**data).model_dump()


async def update_firewall_zone(
    site_id: str,
    firewall_zone_id: str,
    settings: Settings,
    name: str | None = None,
    description: str | None = None,
    network_ids: list[str] | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
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

    async with UniFiClient(settings) as client:
        logger.info(f"Updating firewall zone {firewall_zone_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload with only provided fields
        payload = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if network_ids is not None:
            payload["networks"] = network_ids

        if dry_run:
            logger.info(f"[DRY RUN] Would update firewall zone with payload: {payload}")
            return {"dry_run": True, "payload": payload}

        response = await client.put(
            f"/integration/v1/sites/{site_id}/firewall/zones/{firewall_zone_id}",
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

        return FirewallZone(**data).model_dump()


async def assign_network_to_zone(
    site_id: str,
    zone_id: str,
    network_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
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

    async with UniFiClient(settings) as client:
        logger.info(f"Assigning network {network_id} to zone {zone_id} on site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Get network name
        network_name = None
        try:
            network_response = await client.get(
                f"/integration/v1/sites/{site_id}/networks/{network_id}"
            )
            network_data = network_response.get("data", {})
            network_name = network_data.get("name")
        except Exception:
            logger.warning(f"Could not fetch network name for {network_id}")

        # Update zone to include this network
        zone_response = await client.get(
            f"/integration/v1/sites/{site_id}/firewall/zones/{zone_id}"
        )
        zone_data = zone_response.get("data", {})
        current_networks = zone_data.get("networks", [])

        if network_id in current_networks:
            logger.info(f"Network {network_id} already assigned to zone {zone_id}")
            return ZoneNetworkAssignment(
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
            f"/integration/v1/sites/{site_id}/firewall/zones/{zone_id}",
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

        return ZoneNetworkAssignment(
            zone_id=zone_id,
            network_id=network_id,
            network_name=network_name,
        ).model_dump()


async def get_zone_networks(site_id: str, zone_id: str, settings: Settings) -> list[dict]:
    """List all networks in a zone.

    Args:
        site_id: Site identifier
        zone_id: Zone identifier
        settings: Application settings

    Returns:
        List of networks in the zone
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Listing networks in zone {zone_id} on site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/firewall/zones/{zone_id}")
        zone_data = response.get("data", {})
        network_ids = zone_data.get("networks", [])

        # Fetch network details for each network ID
        networks = []
        for network_id in network_ids:
            try:
                network_response = await client.get(
                    f"/integration/v1/sites/{site_id}/networks/{network_id}"
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
