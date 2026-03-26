"""Port forwarding management MCP tools."""

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
    validate_ip_address,
    validate_limit_offset,
    validate_port,
    validate_site_id,
)


async def list_port_forwards(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all port forwarding rules in a site (read-only).

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of rules to return
        offset: Number of rules to skip

    Returns:
        List of port forwarding rule dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/portforward")
        # Handle both list and dict responses
        rules_data: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        # Apply pagination
        paginated = rules_data[offset : offset + limit]

        logger.info(sanitize_log_message(f"Retrieved {len(paginated)} port forwarding rules for site '{site_id}'"))
        return paginated


async def create_port_forward(
    site_id: str,
    name: str,
    dst_port: int,
    fwd_ip: str,
    fwd_port: int,
    settings: Settings,
    protocol: str = "tcp_udp",
    src: str = "any",
    enabled: bool = True,
    log: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a port forwarding rule.

    Args:
        site_id: Site identifier
        name: Rule name/description
        dst_port: Destination port (external/WAN port)
        fwd_ip: Forward to IP address (internal/LAN)
        fwd_port: Forward to port (internal)
        settings: Application settings
        protocol: Protocol (tcp, udp, tcp_udp)
        src: Source restriction (any, or specific IP/network)
        enabled: Enable the rule immediately
        log: Enable logging for this rule
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't create the rule

    Returns:
        Created port forwarding rule dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ValidationError: If validation fails
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "port forwarding operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    # Validate ports
    validate_port(dst_port)
    validate_port(fwd_port)

    # Validate forward IP
    validate_ip_address(fwd_ip)

    # Validate protocol
    valid_protocols = ["tcp", "udp", "tcp_udp"]
    if protocol not in valid_protocols:
        raise ValidationError(f"Invalid protocol '{protocol}'. Must be one of: {valid_protocols}")

    # Validate source if not "any"
    if src != "any":
        validate_ip_address(src.split("/")[0])  # Validate IP part of CIDR

    # Build port forward data
    pf_data = {
        "name": name,
        "dst_port": str(dst_port),
        "fwd": fwd_ip,
        "fwd_port": str(fwd_port),
        "proto": protocol,
        "src": src,
        "enabled": enabled,
        "log": log,
    }

    # Log parameters for audit
    parameters = {
        "site_id": site_id,
        "name": name,
        "dst_port": dst_port,
        "fwd_ip": fwd_ip,
        "fwd_port": fwd_port,
        "protocol": protocol,
        "src": src,
        "enabled": enabled,
    }

    if dry_run:
        logger.info(
            f"DRY RUN: Would create port forward '{name}' "
            f"({dst_port} -> {fwd_ip}:{fwd_port}) in site '{site_id}'"
        )
        log_audit(
            operation="create_port_forward",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_create": pf_data}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            response = await client.post(f"/ea/sites/{site_id}/rest/portforward", json_data=pf_data)
            # Handle both list and dict responses
            created_rule: dict[str, Any] = (
                response[0] if isinstance(response, list) else response.get("data", [{}])[0]
            )

            logger.info(
                f"Created port forward '{name}' "
                f"({dst_port} -> {fwd_ip}:{fwd_port}) in site '{site_id}'"
            )
            log_audit(
                operation="create_port_forward",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return created_rule

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to create port forward '{name}': {e}"))
        log_audit(
            operation="create_port_forward",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def update_port_forward(
    site_id: str,
    rule_id: str,
    settings: Settings,
    name: str | None = None,
    dst_port: int | None = None,
    fwd_ip: str | None = None,
    fwd_port: int | None = None,
    protocol: str | None = None,
    src: str | None = None,
    enabled: bool | None = None,
    log: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing port forwarding rule.

    Args:
        site_id: Site identifier
        rule_id: Port forwarding rule ID
        settings: Application settings
        name: New rule name/description
        dst_port: New destination port (external/WAN port)
        fwd_ip: New forward-to IP address (internal/LAN)
        fwd_port: New forward-to port (internal)
        protocol: New protocol (tcp, udp, tcp_udp)
        src: New source restriction (any, or specific IP/network)
        enabled: Enable or disable the rule
        log: Enable or disable logging for this rule
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't update the rule

    Returns:
        Updated port forwarding rule dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If rule not found
        ValidationError: If validation fails
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "port forwarding operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    # Validate optional fields if provided
    if dst_port is not None:
        validate_port(dst_port)
    if fwd_port is not None:
        validate_port(fwd_port)
    if fwd_ip is not None:
        validate_ip_address(fwd_ip)
    if protocol is not None:
        valid_protocols = ["tcp", "udp", "tcp_udp"]
        if protocol not in valid_protocols:
            raise ValidationError(
                f"Invalid protocol '{protocol}'. Must be one of: {valid_protocols}"
            )
    if src is not None and src != "any":
        validate_ip_address(src.split("/")[0])  # Validate IP part of CIDR

    parameters = {
        "site_id": site_id,
        "rule_id": rule_id,
        "name": name,
        "dst_port": dst_port,
        "fwd_ip": fwd_ip,
        "fwd_port": fwd_port,
        "protocol": protocol,
        "src": src,
        "enabled": enabled,
        "log": log,
    }

    if dry_run:
        logger.info(sanitize_log_message(f"DRY RUN: Would update port forwarding rule '{rule_id}' in site '{site_id}'"))
        log_audit(
            operation="update_port_forward",
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
            response = await client.get(f"/ea/sites/{site_id}/rest/portforward")
            rules_data: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

            existing_rule = next((r for r in rules_data if r.get("_id") == rule_id), None)
            if not existing_rule:
                raise ResourceNotFoundError("port_forward_rule", rule_id)

            # Build update data by merging provided fields into existing rule
            update_data = existing_rule.copy()
            if name is not None:
                update_data["name"] = name
            if dst_port is not None:
                update_data["dst_port"] = str(dst_port)
            if fwd_ip is not None:
                update_data["fwd"] = fwd_ip
            if fwd_port is not None:
                update_data["fwd_port"] = str(fwd_port)
            if protocol is not None:
                update_data["proto"] = protocol
            if src is not None:
                update_data["src"] = src
            if enabled is not None:
                update_data["enabled"] = enabled
            if log is not None:
                update_data["log"] = log

            response = await client.put(
                f"/ea/sites/{site_id}/rest/portforward/{rule_id}", json_data=update_data
            )
            if isinstance(response, list):
                updated_rule: dict[str, Any] = response[0]
            else:
                data_list = response.get("data", [{}])
                updated_rule = data_list[0] if isinstance(data_list, list) else {}

            logger.info(sanitize_log_message(f"Updated port forwarding rule '{rule_id}' in site '{site_id}'"))
            log_audit(
                operation="update_port_forward",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return updated_rule

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to update port forwarding rule '{rule_id}': {e}"))
        log_audit(
            operation="update_port_forward",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def delete_port_forward(
    site_id: str,
    rule_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Delete a port forwarding rule.

    Args:
        site_id: Site identifier
        rule_id: Port forwarding rule ID
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
    validate_confirmation(confirm, "port forwarding operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "rule_id": rule_id}

    if dry_run:
        logger.info(
            f"DRY RUN: Would delete port forwarding rule '{rule_id}' " f"from site '{site_id}'"
        )
        log_audit(
            operation="delete_port_forward",
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
            response = await client.get(f"/ea/sites/{site_id}/rest/portforward")
            # Handle both list and dict responses
            rules_data: list[dict[str, Any]] = (
                response if isinstance(response, list) else response.get("data", [])
            )

            rule_exists = any(rule.get("_id") == rule_id for rule in rules_data)
            if not rule_exists:
                raise ResourceNotFoundError("port_forward_rule", rule_id)

            response = await client.delete(f"/ea/sites/{site_id}/rest/portforward/{rule_id}")

            logger.info(sanitize_log_message(f"Deleted port forwarding rule '{rule_id}' from site '{site_id}'"))
            log_audit(
                operation="delete_port_forward",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {"success": True, "deleted_rule_id": rule_id}

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to delete port forwarding rule '{rule_id}': {e}"))
        log_audit(
            operation="delete_port_forward",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
