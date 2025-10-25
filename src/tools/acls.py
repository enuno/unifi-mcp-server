"""Access Control List (ACL) management tools."""

from ..api.client import UniFiClient
from ..config import Settings
from ..models import ACLRule
from ..utils import audit_action, get_logger, validate_confirmation

logger = get_logger(__name__)


async def list_acl_rules(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
    filter_expr: str | None = None,
) -> list[dict]:
    """List all ACL rules for a site.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of results
        offset: Starting position
        filter_expr: Filter expression

    Returns:
        List of ACL rules
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Listing ACL rules for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if filter_expr:
            params["filter"] = filter_expr

        response = await client.get(f"/integration/v1/sites/{site_id}/acls", params=params)
        data = response.get("data", [])

        return [ACLRule(**rule).model_dump() for rule in data]


async def get_acl_rule(site_id: str, acl_rule_id: str, settings: Settings) -> dict:
    """Get details for a specific ACL rule.

    Args:
        site_id: Site identifier
        acl_rule_id: ACL rule identifier
        settings: Application settings

    Returns:
        ACL rule details
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Getting ACL rule {acl_rule_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/acls/{acl_rule_id}")
        data = response.get("data", response)

        return ACLRule(**data).model_dump()


async def create_acl_rule(
    site_id: str,
    name: str,
    action: str,
    settings: Settings,
    enabled: bool = True,
    source_type: str | None = None,
    source_id: str | None = None,
    source_network: str | None = None,
    destination_type: str | None = None,
    destination_id: str | None = None,
    destination_network: str | None = None,
    protocol: str | None = None,
    src_port: int | None = None,
    dst_port: int | None = None,
    priority: int = 100,
    description: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Create a new ACL rule.

    Args:
        site_id: Site identifier
        name: Rule name
        action: Action to take (allow/deny)
        settings: Application settings
        enabled: Whether the rule is enabled
        source_type: Source type (network/device/ip/any)
        source_id: Source identifier
        source_network: Source network CIDR
        destination_type: Destination type
        destination_id: Destination identifier
        destination_network: Destination network CIDR
        protocol: Protocol (tcp/udp/icmp/all)
        src_port: Source port
        dst_port: Destination port
        priority: Rule priority (lower = higher priority)
        description: Rule description
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created ACL rule
    """
    validate_confirmation(confirm, "create ACL rule")

    async with UniFiClient(settings) as client:
        logger.info(f"Creating ACL rule '{name}' for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload
        payload = {
            "name": name,
            "enabled": enabled,
            "action": action,
            "priority": priority,
        }

        if description:
            payload["description"] = description
        if source_type:
            payload["sourceType"] = source_type
        if source_id:
            payload["sourceId"] = source_id
        if source_network:
            payload["sourceNetwork"] = source_network
        if destination_type:
            payload["destinationType"] = destination_type
        if destination_id:
            payload["destinationId"] = destination_id
        if destination_network:
            payload["destinationNetwork"] = destination_network
        if protocol:
            payload["protocol"] = protocol
        if src_port is not None:
            payload["srcPort"] = src_port
        if dst_port is not None:
            payload["dstPort"] = dst_port

        if dry_run:
            logger.info(f"[DRY RUN] Would create ACL rule with payload: {payload}")
            return {"dry_run": True, "payload": payload}

        response = await client.post(f"/integration/v1/sites/{site_id}/acls", json_data=payload)
        data = response.get("data", response)

        # Audit the action
        await audit_action(
            settings,
            action_type="create_acl_rule",
            resource_type="acl_rule",
            resource_id=data.get("_id", "unknown"),
            site_id=site_id,
            details={"name": name, "action": action},
        )

        return ACLRule(**data).model_dump()


async def update_acl_rule(
    site_id: str,
    acl_rule_id: str,
    settings: Settings,
    name: str | None = None,
    action: str | None = None,
    enabled: bool | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    source_network: str | None = None,
    destination_type: str | None = None,
    destination_id: str | None = None,
    destination_network: str | None = None,
    protocol: str | None = None,
    src_port: int | None = None,
    dst_port: int | None = None,
    priority: int | None = None,
    description: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Update an existing ACL rule.

    Args:
        site_id: Site identifier
        acl_rule_id: ACL rule identifier
        settings: Application settings
        name: Rule name
        action: Action to take
        enabled: Whether the rule is enabled
        source_type: Source type
        source_id: Source identifier
        source_network: Source network CIDR
        destination_type: Destination type
        destination_id: Destination identifier
        destination_network: Destination network CIDR
        protocol: Protocol
        src_port: Source port
        dst_port: Destination port
        priority: Rule priority
        description: Rule description
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Updated ACL rule
    """
    validate_confirmation(confirm, "update ACL rule")

    async with UniFiClient(settings) as client:
        logger.info(f"Updating ACL rule {acl_rule_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload with only provided fields
        payload = {}
        if name is not None:
            payload["name"] = name
        if action is not None:
            payload["action"] = action
        if enabled is not None:
            payload["enabled"] = enabled
        if priority is not None:
            payload["priority"] = priority
        if description is not None:
            payload["description"] = description
        if source_type is not None:
            payload["sourceType"] = source_type
        if source_id is not None:
            payload["sourceId"] = source_id
        if source_network is not None:
            payload["sourceNetwork"] = source_network
        if destination_type is not None:
            payload["destinationType"] = destination_type
        if destination_id is not None:
            payload["destinationId"] = destination_id
        if destination_network is not None:
            payload["destinationNetwork"] = destination_network
        if protocol is not None:
            payload["protocol"] = protocol
        if src_port is not None:
            payload["srcPort"] = src_port
        if dst_port is not None:
            payload["dstPort"] = dst_port

        if dry_run:
            logger.info(f"[DRY RUN] Would update ACL rule with payload: {payload}")
            return {"dry_run": True, "payload": payload}

        response = await client.put(
            f"/integration/v1/sites/{site_id}/acls/{acl_rule_id}", json_data=payload
        )
        data = response.get("data", response)

        # Audit the action
        await audit_action(
            settings,
            action_type="update_acl_rule",
            resource_type="acl_rule",
            resource_id=acl_rule_id,
            site_id=site_id,
            details=payload,
        )

        return ACLRule(**data).model_dump()


async def delete_acl_rule(
    site_id: str,
    acl_rule_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict:
    """Delete an ACL rule.

    Args:
        site_id: Site identifier
        acl_rule_id: ACL rule identifier
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion status
    """
    validate_confirmation(confirm, "delete ACL rule")

    async with UniFiClient(settings) as client:
        logger.info(f"Deleting ACL rule {acl_rule_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(f"[DRY RUN] Would delete ACL rule {acl_rule_id}")
            return {"dry_run": True, "acl_rule_id": acl_rule_id}

        await client.delete(f"/integration/v1/sites/{site_id}/acls/{acl_rule_id}")

        # Audit the action
        await audit_action(
            settings,
            action_type="delete_acl_rule",
            resource_type="acl_rule",
            resource_id=acl_rule_id,
            site_id=site_id,
            details={},
        )

        return {"success": True, "message": f"ACL rule {acl_rule_id} deleted successfully"}
