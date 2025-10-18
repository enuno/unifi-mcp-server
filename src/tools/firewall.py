"""Firewall rules management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import (
    ConfirmationRequiredError,
    ResourceNotFoundError,
    get_logger,
    log_audit,
    validate_confirmation,
    validate_limit_offset,
    validate_site_id,
)


async def list_firewall_rules(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all firewall rules in a site (read-only).

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of rules to return
        offset: Number of rules to skip

    Returns:
        List of firewall rule dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/firewallrule")
        rules_data = response.get("data", [])

        # Apply pagination
        paginated = rules_data[offset : offset + limit]

        logger.info(f"Retrieved {len(paginated)} firewall rules for site '{site_id}'")
        return paginated


async def create_firewall_rule(
    site_id: str,
    name: str,
    action: str,
    settings: Settings,
    source: str | None = None,
    destination: str | None = None,
    protocol: str | None = None,
    port: int | None = None,
    enabled: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a new firewall rule.

    Args:
        site_id: Site identifier
        name: Rule name
        action: Action to take (accept, drop, reject)
        settings: Application settings
        source: Source network/IP (CIDR notation)
        destination: Destination network/IP (CIDR notation)
        protocol: Protocol (tcp, udp, icmp, all)
        port: Destination port number
        enabled: Enable the rule immediately
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't create the rule

    Returns:
        Created firewall rule dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ValidationError: If validation fails
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm)
    logger = get_logger(__name__, settings.log_level)

    # Validate action
    valid_actions = ["accept", "drop", "reject"]
    if action.lower() not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Must be one of: {valid_actions}")

    # Validate protocol if provided
    if protocol:
        valid_protocols = ["tcp", "udp", "icmp", "all"]
        if protocol.lower() not in valid_protocols:
            raise ValueError(
                f"Invalid protocol '{protocol}'. Must be one of: {valid_protocols}"
            )

    # Build rule data
    rule_data = {
        "name": name,
        "action": action.lower(),
        "enabled": enabled,
    }

    if source:
        rule_data["src_address"] = source

    if destination:
        rule_data["dst_address"] = destination

    if protocol:
        rule_data["protocol"] = protocol.lower()

    if port is not None:
        rule_data["dst_port"] = port

    # Log parameters for audit
    parameters = {
        "site_id": site_id,
        "name": name,
        "action": action,
        "source": source,
        "destination": destination,
        "protocol": protocol,
        "port": port,
        "enabled": enabled,
    }

    if dry_run:
        logger.info(f"DRY RUN: Would create firewall rule '{name}' in site '{site_id}'")
        log_audit(
            operation="create_firewall_rule",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_create": rule_data}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            response = await client.post(
                f"/ea/sites/{site_id}/rest/firewallrule", json=rule_data
            )
            created_rule = response.get("data", [{}])[0]

            logger.info(f"Created firewall rule '{name}' in site '{site_id}'")
            log_audit(
                operation="create_firewall_rule",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return created_rule

    except Exception as e:
        logger.error(f"Failed to create firewall rule '{name}': {e}")
        log_audit(
            operation="create_firewall_rule",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def update_firewall_rule(
    site_id: str,
    rule_id: str,
    settings: Settings,
    name: str | None = None,
    action: str | None = None,
    source: str | None = None,
    destination: str | None = None,
    protocol: str | None = None,
    port: int | None = None,
    enabled: bool | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Update an existing firewall rule.

    Args:
        site_id: Site identifier
        rule_id: Firewall rule ID
        settings: Application settings
        name: New rule name
        action: New action (accept, drop, reject)
        source: New source network/IP
        destination: New destination network/IP
        protocol: New protocol (tcp, udp, icmp, all)
        port: New destination port
        enabled: Enable/disable the rule
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't update the rule

    Returns:
        Updated firewall rule dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If rule not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm)
    logger = get_logger(__name__, settings.log_level)

    # Validate action if provided
    if action:
        valid_actions = ["accept", "drop", "reject"]
        if action.lower() not in valid_actions:
            raise ValueError(
                f"Invalid action '{action}'. Must be one of: {valid_actions}"
            )

    # Validate protocol if provided
    if protocol:
        valid_protocols = ["tcp", "udp", "icmp", "all"]
        if protocol.lower() not in valid_protocols:
            raise ValueError(
                f"Invalid protocol '{protocol}'. Must be one of: {valid_protocols}"
            )

    parameters = {
        "site_id": site_id,
        "rule_id": rule_id,
        "name": name,
        "action": action,
        "source": source,
        "destination": destination,
        "protocol": protocol,
        "port": port,
        "enabled": enabled,
    }

    if dry_run:
        logger.info(f"DRY RUN: Would update firewall rule '{rule_id}' in site '{site_id}'")
        log_audit(
            operation="update_firewall_rule",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_update": parameters}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Get existing rule
            response = await client.get(f"/ea/sites/{site_id}/rest/firewallrule")
            rules_data = response.get("data", [])

            existing_rule = None
            for rule in rules_data:
                if rule.get("_id") == rule_id:
                    existing_rule = rule
                    break

            if not existing_rule:
                raise ResourceNotFoundError("firewall_rule", rule_id)

            # Build update data
            update_data = existing_rule.copy()

            if name is not None:
                update_data["name"] = name
            if action is not None:
                update_data["action"] = action.lower()
            if source is not None:
                update_data["src_address"] = source
            if destination is not None:
                update_data["dst_address"] = destination
            if protocol is not None:
                update_data["protocol"] = protocol.lower()
            if port is not None:
                update_data["dst_port"] = port
            if enabled is not None:
                update_data["enabled"] = enabled

            response = await client.put(
                f"/ea/sites/{site_id}/rest/firewallrule/{rule_id}", json=update_data
            )
            updated_rule = response.get("data", [{}])[0]

            logger.info(f"Updated firewall rule '{rule_id}' in site '{site_id}'")
            log_audit(
                operation="update_firewall_rule",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return updated_rule

    except Exception as e:
        logger.error(f"Failed to update firewall rule '{rule_id}': {e}")
        log_audit(
            operation="update_firewall_rule",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def delete_firewall_rule(
    site_id: str,
    rule_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete a firewall rule.

    Args:
        site_id: Site identifier
        rule_id: Firewall rule ID
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't delete the rule

    Returns:
        Deletion result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If rule not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm)
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "rule_id": rule_id}

    if dry_run:
        logger.info(f"DRY RUN: Would delete firewall rule '{rule_id}' from site '{site_id}'")
        log_audit(
            operation="delete_firewall_rule",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_delete": rule_id}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Verify rule exists before deleting
            response = await client.get(f"/ea/sites/{site_id}/rest/firewallrule")
            rules_data = response.get("data", [])

            rule_exists = any(rule.get("_id") == rule_id for rule in rules_data)
            if not rule_exists:
                raise ResourceNotFoundError("firewall_rule", rule_id)

            response = await client.delete(
                f"/ea/sites/{site_id}/rest/firewallrule/{rule_id}"
            )

            logger.info(f"Deleted firewall rule '{rule_id}' from site '{site_id}'")
            log_audit(
                operation="delete_firewall_rule",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {"success": True, "deleted_rule_id": rule_id}

    except Exception as e:
        logger.error(f"Failed to delete firewall rule '{rule_id}': {e}")
        log_audit(
            operation="delete_firewall_rule",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
