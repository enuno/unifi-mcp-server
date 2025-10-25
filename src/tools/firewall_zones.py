"""Firewall zone management tools."""

from ..api.client import UniFiClient
from ..config import Settings
from ..models import FirewallZone
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
