"""Port forwarding management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import (
    ResourceNotFoundError,
    ValidationError,
    get_logger,
    log_audit,
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
        rules_data = response.get("data", [])

        # Apply pagination
        paginated = rules_data[offset : offset + limit]

        logger.info(f"Retrieved {len(paginated)} port forwarding rules for site '{site_id}'")
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
    confirm: bool = False,
    dry_run: bool = False,
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
    validate_confirmation(confirm)
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

            response = await client.post(f"/ea/sites/{site_id}/rest/portforward", json=pf_data)
            created_rule = response.get("data", [{}])[0]

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
        logger.error(f"Failed to create port forward '{name}': {e}")
        log_audit(
            operation="create_port_forward",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def delete_port_forward(
    site_id: str,
    rule_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
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
    validate_confirmation(confirm)
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
            rules_data = response.get("data", [])

            rule_exists = any(rule.get("_id") == rule_id for rule in rules_data)
            if not rule_exists:
                raise ResourceNotFoundError("port_forward_rule", rule_id)

            response = await client.delete(f"/ea/sites/{site_id}/rest/portforward/{rule_id}")

            logger.info(f"Deleted port forwarding rule '{rule_id}' from site '{site_id}'")
            log_audit(
                operation="delete_port_forward",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {"success": True, "deleted_rule_id": rule_id}

    except Exception as e:
        logger.error(f"Failed to delete port forwarding rule '{rule_id}': {e}")
        log_audit(
            operation="delete_port_forward",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
