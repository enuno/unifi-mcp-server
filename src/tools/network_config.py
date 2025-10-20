"""Network configuration MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import (
    ResourceNotFoundError,
    ValidationError,
    get_logger,
    log_audit,
    validate_confirmation,
    validate_site_id,
)


async def create_network(
    site_id: str,
    name: str,
    vlan_id: int,
    subnet: str,
    settings: Settings,
    purpose: str = "corporate",
    dhcp_enabled: bool = True,
    dhcp_start: str | None = None,
    dhcp_stop: str | None = None,
    dhcp_dns_1: str | None = None,
    dhcp_dns_2: str | None = None,
    domain_name: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a new network/VLAN.

    Args:
        site_id: Site identifier
        name: Network name
        vlan_id: VLAN ID (1-4094)
        subnet: Network subnet in CIDR notation (e.g., "192.168.1.0/24")
        settings: Application settings
        purpose: Network purpose (corporate, guest, vlan-only)
        dhcp_enabled: Enable DHCP server
        dhcp_start: DHCP range start IP
        dhcp_stop: DHCP range stop IP
        dhcp_dns_1: Primary DNS server
        dhcp_dns_2: Secondary DNS server
        domain_name: Domain name for DHCP
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't create the network

    Returns:
        Created network dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ValidationError: If validation fails
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "network configuration operation")
    logger = get_logger(__name__, settings.log_level)

    # Validate VLAN ID
    if not 1 <= vlan_id <= 4094:
        raise ValidationError(f"Invalid VLAN ID {vlan_id}. Must be between 1 and 4094")

    # Validate purpose
    valid_purposes = ["corporate", "guest", "vlan-only", "wan"]
    if purpose not in valid_purposes:
        raise ValidationError(f"Invalid purpose '{purpose}'. Must be one of: {valid_purposes}")

    # Validate subnet format
    if "/" not in subnet:
        raise ValidationError(f"Invalid subnet '{subnet}'. Must be in CIDR notation")

    # Build network data
    network_data = {
        "name": name,
        "purpose": purpose,
        "vlan": vlan_id,
        "ip_subnet": subnet,
        "dhcpd_enabled": dhcp_enabled,
    }

    if dhcp_enabled:
        if dhcp_start:
            network_data["dhcpd_start"] = dhcp_start
        if dhcp_stop:
            network_data["dhcpd_stop"] = dhcp_stop
        if dhcp_dns_1:
            network_data["dhcpd_dns_1"] = dhcp_dns_1
        if dhcp_dns_2:
            network_data["dhcpd_dns_2"] = dhcp_dns_2
        if domain_name:
            network_data["domain_name"] = domain_name

    # Log parameters for audit
    parameters = {
        "site_id": site_id,
        "name": name,
        "vlan_id": vlan_id,
        "subnet": subnet,
        "purpose": purpose,
        "dhcp_enabled": dhcp_enabled,
        "dhcp_start": dhcp_start,
        "dhcp_stop": dhcp_stop,
    }

    if dry_run:
        logger.info(f"DRY RUN: Would create network '{name}' in site '{site_id}'")
        log_audit(
            operation="create_network",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_create": network_data}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            response = await client.post(
                f"/ea/sites/{site_id}/rest/networkconf", json_data=network_data
            )
            created_network: dict[str, Any] = response.get("data", [{}])[0]

            logger.info(f"Created network '{name}' in site '{site_id}'")
            log_audit(
                operation="create_network",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return created_network

    except Exception as e:
        logger.error(f"Failed to create network '{name}': {e}")
        log_audit(
            operation="create_network",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def update_network(
    site_id: str,
    network_id: str,
    settings: Settings,
    name: str | None = None,
    vlan_id: int | None = None,
    subnet: str | None = None,
    purpose: str | None = None,
    dhcp_enabled: bool | None = None,
    dhcp_start: str | None = None,
    dhcp_stop: str | None = None,
    dhcp_dns_1: str | None = None,
    dhcp_dns_2: str | None = None,
    domain_name: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Update an existing network.

    Args:
        site_id: Site identifier
        network_id: Network ID
        settings: Application settings
        name: New network name
        vlan_id: New VLAN ID (1-4094)
        subnet: New subnet in CIDR notation
        purpose: New purpose (corporate, guest, vlan-only)
        dhcp_enabled: Enable/disable DHCP
        dhcp_start: New DHCP range start IP
        dhcp_stop: New DHCP range stop IP
        dhcp_dns_1: New primary DNS server
        dhcp_dns_2: New secondary DNS server
        domain_name: New domain name
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't update the network

    Returns:
        Updated network dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If network not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "network configuration operation")
    logger = get_logger(__name__, settings.log_level)

    # Validate VLAN ID if provided
    if vlan_id is not None and not 1 <= vlan_id <= 4094:
        raise ValidationError(f"Invalid VLAN ID {vlan_id}. Must be between 1 and 4094")

    # Validate purpose if provided
    if purpose is not None:
        valid_purposes = ["corporate", "guest", "vlan-only", "wan"]
        if purpose not in valid_purposes:
            raise ValidationError(f"Invalid purpose '{purpose}'. Must be one of: {valid_purposes}")

    # Validate subnet format if provided
    if subnet is not None and "/" not in subnet:
        raise ValidationError(f"Invalid subnet '{subnet}'. Must be in CIDR notation")

    parameters = {
        "site_id": site_id,
        "network_id": network_id,
        "name": name,
        "vlan_id": vlan_id,
        "subnet": subnet,
        "purpose": purpose,
        "dhcp_enabled": dhcp_enabled,
    }

    if dry_run:
        logger.info(f"DRY RUN: Would update network '{network_id}' in site '{site_id}'")
        log_audit(
            operation="update_network",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_update": parameters}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Get existing network
            response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")
            networks_data: list[dict[str, Any]] = response.get("data", [])

            existing_network = None
            for network in networks_data:
                if network.get("_id") == network_id:
                    existing_network = network
                    break

            if not existing_network:
                raise ResourceNotFoundError("network", network_id)

            # Build update data
            update_data = existing_network.copy()

            if name is not None:
                update_data["name"] = name
            if vlan_id is not None:
                update_data["vlan"] = vlan_id
            if subnet is not None:
                update_data["ip_subnet"] = subnet
            if purpose is not None:
                update_data["purpose"] = purpose
            if dhcp_enabled is not None:
                update_data["dhcpd_enabled"] = dhcp_enabled
            if dhcp_start is not None:
                update_data["dhcpd_start"] = dhcp_start
            if dhcp_stop is not None:
                update_data["dhcpd_stop"] = dhcp_stop
            if dhcp_dns_1 is not None:
                update_data["dhcpd_dns_1"] = dhcp_dns_1
            if dhcp_dns_2 is not None:
                update_data["dhcpd_dns_2"] = dhcp_dns_2
            if domain_name is not None:
                update_data["domain_name"] = domain_name

            response = await client.put(
                f"/ea/sites/{site_id}/rest/networkconf/{network_id}", json_data=update_data
            )
            updated_network: dict[str, Any] = response.get("data", [{}])[0]

            logger.info(f"Updated network '{network_id}' in site '{site_id}'")
            log_audit(
                operation="update_network",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return updated_network

    except Exception as e:
        logger.error(f"Failed to update network '{network_id}': {e}")
        log_audit(
            operation="update_network",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def delete_network(
    site_id: str,
    network_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete a network.

    Args:
        site_id: Site identifier
        network_id: Network ID
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't delete the network

    Returns:
        Deletion result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If network not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "network configuration operation")
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "network_id": network_id}

    if dry_run:
        logger.info(f"DRY RUN: Would delete network '{network_id}' from site '{site_id}'")
        log_audit(
            operation="delete_network",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_delete": network_id}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            # Verify network exists before deleting
            response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")
            networks_data: list[dict[str, Any]] = response.get("data", [])

            network_exists = any(net.get("_id") == network_id for net in networks_data)
            if not network_exists:
                raise ResourceNotFoundError("network", network_id)

            response = await client.delete(f"/ea/sites/{site_id}/rest/networkconf/{network_id}")

            logger.info(f"Deleted network '{network_id}' from site '{site_id}'")
            log_audit(
                operation="delete_network",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {"success": True, "deleted_network_id": network_id}

    except Exception as e:
        logger.error(f"Failed to delete network '{network_id}': {e}")
        log_audit(
            operation="delete_network",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
