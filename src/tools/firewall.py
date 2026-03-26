"""Firewall rules management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import (
    ResourceNotFoundError,
    get_logger,
    log_audit,
    sanitize_log_message,
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
        # Client now auto-unwraps the "data" field, so response is the actual data
        rules_data: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        # Apply pagination
        paginated = rules_data[offset : offset + limit]

        logger.info(sanitize_log_message(f"Retrieved {len(paginated)} firewall rules for site '{site_id}'"))
        return paginated


async def create_firewall_rule(
    site_id: str,
    name: str,
    action: str,
    settings: Settings,
    src_address: str | None = None,
    dst_address: str | None = None,
    protocol: str | None = None,
    port: int | None = None,
    enabled: bool = True,
    ruleset: str = "WAN_IN",
    rule_index: int = 2000,
    src_networkconf_id: str | None = None,
    src_networkconf_type: str = "NETv4",
    dst_networkconf_id: str | None = None,
    dst_networkconf_type: str = "NETv4",
    state_established: bool = False,
    state_related: bool = False,
    state_new: bool = False,
    state_invalid: bool = False,
    logging: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a new firewall rule.

    Args:
        site_id: Site identifier
        name: Rule name
        action: Action to take (accept, drop, reject)
        settings: Application settings
        src_address: Source IP address (CIDR notation or single IP)
        dst_address: Destination IP address (CIDR notation or single IP)
        protocol: Protocol (tcp, udp, icmp, all)
        port: Destination port number
        enabled: Enable the rule immediately
        ruleset: Ruleset to apply rule to (WAN_IN, WAN_OUT, LAN_IN, LAN_OUT, etc.)
        rule_index: Position in firewall chain (higher = lower priority)
        src_networkconf_id: Source network configuration ID (for inter-VLAN rules)
        src_networkconf_type: Source network type (default: NETv4)
        dst_networkconf_id: Destination network configuration ID (for inter-VLAN rules)
        dst_networkconf_type: Destination network type (default: NETv4)
        state_established: Match established connections
        state_related: Match related connections
        state_new: Match new connections
        state_invalid: Match invalid connections
        logging: Enable logging for matched traffic
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't create the rule

    Returns:
        Created firewall rule dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ValidationError: If validation fails
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "firewall operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    # Validate action
    valid_actions = ["accept", "drop", "reject"]
    if action.lower() not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Must be one of: {valid_actions}")

    # Validate protocol if provided
    if protocol:
        valid_protocols = ["tcp", "udp", "icmp", "all"]
        if protocol.lower() not in valid_protocols:
            raise ValueError(f"Invalid protocol '{protocol}'. Must be one of: {valid_protocols}")

    # Build rule data
    rule_data: dict[str, Any] = {
        "name": name,
        "action": action.lower(),
        "enabled": enabled,
        "ruleset": ruleset,
        "rule_index": rule_index,
        "setting_preference": "auto",
        "src_networkconf_type": src_networkconf_type,
        "dst_networkconf_type": dst_networkconf_type,
        "state_new": state_new,
        "state_established": state_established,
        "state_invalid": state_invalid,
        "state_related": state_related,
        "logging": logging,
        "protocol_match_excepted": False,
    }

    if src_networkconf_id is not None:
        rule_data["src_networkconf_id"] = src_networkconf_id

    if dst_networkconf_id is not None:
        rule_data["dst_networkconf_id"] = dst_networkconf_id

    if src_address:
        rule_data["src_address"] = src_address

    if dst_address:
        rule_data["dst_address"] = dst_address

    if protocol:
        rule_data["protocol"] = protocol.lower()

    if port is not None:
        rule_data["dst_port"] = port

    # Log parameters for audit
    parameters = {
        "site_id": site_id,
        "name": name,
        "action": action,
        "src_address": src_address,
        "dst_address": dst_address,
        "protocol": protocol,
        "port": port,
        "enabled": enabled,
    }

    if dry_run:
        logger.info(sanitize_log_message(f"DRY RUN: Would create firewall rule '{name}' in site '{site_id}'"))
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
                f"/ea/sites/{site_id}/rest/firewallrule", json_data=rule_data
            )
            # Client now auto-unwraps the "data" field, so response is the actual data
            if isinstance(response, list):
                created_rule: dict[str, Any] = response[0]
            else:
                data_list = response.get("data", [{}])
                created_rule = data_list[0] if isinstance(data_list, list) else {}

            logger.info(sanitize_log_message(f"Created firewall rule '{name}' in site '{site_id}'"))
            log_audit(
                operation="create_firewall_rule",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return created_rule

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to create firewall rule '{name}': {e}"))
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
    src_address: str | None = None,
    dst_address: str | None = None,
    protocol: str | None = None,
    port: int | None = None,
    enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing firewall rule.

    Args:
        site_id: Site identifier
        rule_id: Firewall rule ID
        settings: Application settings
        name: New rule name
        action: New action (accept, drop, reject)
        src_address: New source network/IP
        dst_address: New destination network/IP
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
    validate_confirmation(confirm, "firewall operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    # Validate action if provided
    if action:
        valid_actions = ["accept", "drop", "reject"]
        if action.lower() not in valid_actions:
            raise ValueError(f"Invalid action '{action}'. Must be one of: {valid_actions}")

    # Validate protocol if provided
    if protocol:
        valid_protocols = ["tcp", "udp", "icmp", "all"]
        if protocol.lower() not in valid_protocols:
            raise ValueError(f"Invalid protocol '{protocol}'. Must be one of: {valid_protocols}")

    parameters = {
        "site_id": site_id,
        "rule_id": rule_id,
        "name": name,
        "action": action,
        "src_address": src_address,
        "dst_address": dst_address,
        "protocol": protocol,
        "port": port,
        "enabled": enabled,
    }

    if dry_run:
        logger.info(sanitize_log_message(f"DRY RUN: Would update firewall rule '{rule_id}' in site '{site_id}'"))
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
            # Client now auto-unwraps the "data" field, so response is the actual data
            rules_data: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

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
            if src_address is not None:
                update_data["src_address"] = src_address
            if dst_address is not None:
                update_data["dst_address"] = dst_address
            if protocol is not None:
                update_data["protocol"] = protocol.lower()
            if port is not None:
                update_data["dst_port"] = port
            if enabled is not None:
                update_data["enabled"] = enabled

            response = await client.put(
                f"/ea/sites/{site_id}/rest/firewallrule/{rule_id}", json_data=update_data
            )
            # Client now auto-unwraps the "data" field, so response is the actual data
            if isinstance(response, list):
                updated_rule: dict[str, Any] = response[0]
            else:
                data_list = response.get("data", [{}])
                updated_rule = data_list[0] if isinstance(data_list, list) else {}

            logger.info(sanitize_log_message(f"Updated firewall rule '{rule_id}' in site '{site_id}'"))
            log_audit(
                operation="update_firewall_rule",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return updated_rule

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to update firewall rule '{rule_id}': {e}"))
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "firewall operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "rule_id": rule_id}

    if dry_run:
        logger.info(sanitize_log_message(f"DRY RUN: Would delete firewall rule '{rule_id}' from site '{site_id}'"))
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
            # Client now auto-unwraps the "data" field, so response is the actual data
            rules_data: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

            rule_exists = any(rule.get("_id") == rule_id for rule in rules_data)
            if not rule_exists:
                raise ResourceNotFoundError("firewall_rule", rule_id)

            response = await client.delete(f"/ea/sites/{site_id}/rest/firewallrule/{rule_id}")

            logger.info(sanitize_log_message(f"Deleted firewall rule '{rule_id}' from site '{site_id}'"))
            log_audit(
                operation="delete_firewall_rule",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {"success": True, "deleted_rule_id": rule_id}

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to delete firewall rule '{rule_id}': {e}"))
        log_audit(
            operation="delete_firewall_rule",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
