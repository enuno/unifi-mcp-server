"""Zone-Based Firewall matrix management tools."""

from ..api.client import UniFiClient
from ..config import Settings
from ..models.zbf_matrix import ApplicationBlockRule, ZonePolicy, ZonePolicyMatrix
from ..utils import audit_action, get_logger, validate_confirmation

logger = get_logger(__name__)


async def get_zbf_matrix(site_id: str, settings: Settings) -> dict:
    """Retrieve zone-to-zone policy matrix.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Zone policy matrix with all zones and policies
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Retrieving ZBF matrix for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Get matrix endpoint - fallback to zones if matrix doesn't exist
        try:
            response = await client.get(f"/integration/v1/sites/{site_id}/firewall/zones/matrix")
            data = response.get("data", response)
        except Exception:
            # If matrix endpoint doesn't exist, construct from zones
            logger.warning("ZBF matrix endpoint not available, constructing from zones")
            zones_response = await client.get(f"/integration/v1/sites/{site_id}/firewall/zones")
            zones_data = zones_response.get("data", [])
            zone_ids = [zone.get("_id") for zone in zones_data if zone.get("_id")]

            data = {
                "site_id": site_id,
                "zones": zone_ids,
                "policies": [],
                "default_policy": "allow",
            }

        return ZonePolicyMatrix(**data).model_dump()


async def get_zone_policies(site_id: str, zone_id: str, settings: Settings) -> list[dict]:
    """Get policies for a specific zone.

    Args:
        site_id: Site identifier
        zone_id: Zone identifier
        settings: Application settings

    Returns:
        List of policies for the zone
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Retrieving policies for zone {zone_id} on site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(
                f"/integration/v1/sites/{site_id}/firewall/zones/{zone_id}/policies"
            )
            data = response.get("data", [])
        except Exception:
            # If endpoint doesn't exist, return empty list
            logger.warning(f"Zone policies endpoint not available for zone {zone_id}")
            return []

        return [ZonePolicy(**policy).model_dump() for policy in data]


async def update_zbf_policy(
    site_id: str,
    source_zone_id: str,
    destination_zone_id: str,
    action: str,
    settings: Settings,
    description: str | None = None,
    priority: int | None = None,
    enabled: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Modify inter-zone firewall policy.

    Args:
        site_id: Site identifier
        source_zone_id: Source zone identifier
        destination_zone_id: Destination zone identifier
        action: Policy action (allow/deny)
        settings: Application settings
        description: Policy description
        priority: Policy priority
        enabled: Whether policy is enabled
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Updated policy
    """
    validate_confirmation(confirm, "update ZBF policy")

    if action not in ("allow", "deny"):
        raise ValueError("Action must be 'allow' or 'deny'")

    async with UniFiClient(settings) as client:
        logger.info(f"Updating ZBF policy from zone {source_zone_id} to {destination_zone_id}")

        if not client.is_authenticated:
            await client.authenticate()

        payload = {
            "source_zone_id": source_zone_id,
            "destination_zone_id": destination_zone_id,
            "action": action,
            "enabled": enabled,
        }

        if description:
            payload["description"] = description
        if priority is not None:
            payload["priority"] = priority

        if dry_run:
            logger.info(f"[DRY RUN] Would update ZBF policy with payload: {payload}")
            return {"dry_run": True, "payload": payload}

        try:
            response = await client.put(
                f"/integration/v1/sites/{site_id}/firewall/zones/{source_zone_id}/policies",
                json_data=payload,
            )
            data = response.get("data", response)
        except Exception as e:
            logger.error(f"Failed to update ZBF policy: {e}")
            # If endpoint doesn't exist, return dry-run result
            if "404" in str(e) or "not found" in str(e).lower():
                logger.warning("ZBF policy endpoint not available, returning dry-run result")
                return {"dry_run": True, "payload": payload, "note": "Endpoint not available"}
            raise

        # Audit the action
        await audit_action(
            settings,
            action_type="update_zbf_policy",
            resource_type="zbf_policy",
            resource_id=f"{source_zone_id}-{destination_zone_id}",
            site_id=site_id,
            details=payload,
        )

        return ZonePolicy(**data).model_dump()


async def block_application_by_zone(
    site_id: str,
    zone_id: str,
    application_id: str,
    settings: Settings,
    action: str = "block",
    enabled: bool = True,
    description: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Block applications using zone-based rules.

    Args:
        site_id: Site identifier
        zone_id: Zone identifier
        application_id: DPI application identifier
        settings: Application settings
        action: Action to take (block/allow)
        enabled: Whether rule is enabled
        description: Rule description
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created application block rule
    """
    validate_confirmation(confirm, "block application by zone")

    if action not in ("block", "allow"):
        raise ValueError("Action must be 'block' or 'allow'")

    async with UniFiClient(settings) as client:
        logger.info(f"Blocking application {application_id} in zone {zone_id} on site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Get application name from DPI applications
        application_name = None
        try:
            dpi_response = await client.get("/integration/v1/dpi/applications")
            dpi_data = dpi_response.get("data", [])
            for app in dpi_data:
                if app.get("_id") == application_id:
                    application_name = app.get("name")
                    break
        except Exception:
            logger.warning(f"Could not fetch application name for {application_id}")

        payload = {
            "zone_id": zone_id,
            "application_id": application_id,
            "action": action,
            "enabled": enabled,
        }

        if description:
            payload["description"] = description
        if application_name:
            payload["application_name"] = application_name

        if dry_run:
            logger.info(f"[DRY RUN] Would block application with payload: {payload}")
            return {"dry_run": True, "payload": payload}

        try:
            response = await client.post(
                f"/integration/v1/sites/{site_id}/firewall/zones/{zone_id}/applications/block",
                json_data=payload,
            )
            data = response.get("data", response)
        except Exception as e:
            logger.error(f"Failed to block application: {e}")
            # If endpoint doesn't exist, return dry-run result
            if "404" in str(e) or "not found" in str(e).lower():
                logger.warning(
                    "Application blocking endpoint not available, returning dry-run result"
                )
                return {"dry_run": True, "payload": payload, "note": "Endpoint not available"}
            raise

        # Audit the action
        await audit_action(
            settings,
            action_type="block_application_by_zone",
            resource_type="application_block_rule",
            resource_id=application_id,
            site_id=site_id,
            details={"zone_id": zone_id, "application_id": application_id},
        )

        return ApplicationBlockRule(**data).model_dump()


async def list_blocked_applications(
    site_id: str, zone_id: str | None = None, settings: Settings | None = None
) -> list[dict]:
    """List applications blocked per zone.

    Args:
        site_id: Site identifier
        zone_id: Optional zone identifier to filter by
        settings: Application settings

    Returns:
        List of blocked applications
    """
    if settings is None:
        raise ValueError("Settings is required")

    async with UniFiClient(settings) as client:
        logger.info(f"Listing blocked applications for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        endpoint = f"/integration/v1/sites/{site_id}/firewall/zones/applications/blocked"
        if zone_id:
            endpoint = (
                f"/integration/v1/sites/{site_id}/firewall/zones/{zone_id}/applications/blocked"
            )

        try:
            response = await client.get(endpoint)
            data = response.get("data", [])
        except Exception:
            # If endpoint doesn't exist, return empty list
            logger.warning("Blocked applications endpoint not available")
            return []

        return [ApplicationBlockRule(**rule).model_dump() for rule in data]


async def get_zone_matrix_policy(
    site_id: str,
    source_zone_id: str,
    destination_zone_id: str,
    settings: Settings,
) -> dict:
    """Get a specific zone-to-zone policy.

    Args:
        site_id: Site identifier
        source_zone_id: Source zone identifier
        destination_zone_id: Destination zone identifier
        settings: Application settings

    Returns:
        Zone-to-zone policy details

    Raises:
        ValueError: If policy not found
    """
    async with UniFiClient(settings) as client:
        logger.info(
            f"Retrieving policy from zone {source_zone_id} to {destination_zone_id} on site {site_id}"
        )

        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(
                f"/integration/v1/sites/{site_id}/firewall/zones/{source_zone_id}/policies/{destination_zone_id}"
            )
            data = response.get("data", response)
        except Exception:
            # If endpoint doesn't exist, try getting all policies and filter
            logger.warning("Specific policy endpoint not available, fetching all policies")
            all_policies = await get_zone_policies(site_id, source_zone_id, settings)

            for policy in all_policies:
                if policy.get("destination_zone_id") == destination_zone_id:
                    return policy

            raise ValueError(
                f"Policy from zone {source_zone_id} to {destination_zone_id} not found"
            )

        return ZonePolicy(**data).model_dump()


async def delete_zbf_policy(
    site_id: str,
    source_zone_id: str,
    destination_zone_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Delete a zone-to-zone policy (revert to default action).

    Args:
        site_id: Site identifier
        source_zone_id: Source zone identifier
        destination_zone_id: Destination zone identifier
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion confirmation

    Raises:
        ValueError: If confirmation not provided
    """
    validate_confirmation(confirm, "delete ZBF policy")

    async with UniFiClient(settings) as client:
        logger.info(
            f"Deleting ZBF policy from zone {source_zone_id} to {destination_zone_id} on site {site_id}"
        )

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(
                f"[DRY RUN] Would delete policy from {source_zone_id} to {destination_zone_id}"
            )
            return {
                "dry_run": True,
                "source_zone_id": source_zone_id,
                "destination_zone_id": destination_zone_id,
                "action": "would_delete",
            }

        try:
            await client.delete(
                f"/integration/v1/sites/{site_id}/firewall/zones/{source_zone_id}/policies/{destination_zone_id}"
            )
        except Exception as e:
            logger.error(f"Failed to delete ZBF policy: {e}")
            # If endpoint doesn't exist, return dry-run result
            if "404" in str(e) or "not found" in str(e).lower():
                logger.warning("ZBF policy delete endpoint not available, returning dry-run result")
                return {
                    "dry_run": True,
                    "source_zone_id": source_zone_id,
                    "destination_zone_id": destination_zone_id,
                    "note": "Endpoint not available",
                }
            raise

        # Audit the action
        await audit_action(
            settings,
            action_type="delete_zbf_policy",
            resource_type="zbf_policy",
            resource_id=f"{source_zone_id}-{destination_zone_id}",
            site_id=site_id,
            details={"source_zone_id": source_zone_id, "destination_zone_id": destination_zone_id},
        )

        return {
            "status": "success",
            "source_zone_id": source_zone_id,
            "destination_zone_id": destination_zone_id,
            "action": "deleted",
        }
