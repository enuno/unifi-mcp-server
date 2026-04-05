"""Firewall zone management tools."""

import re
from typing import Any, cast

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..models.zbf_matrix import ZoneNetworkAssignment
from ..utils import (
    ValidationError,
    audit_action,
    get_logger,
    sanitize_log_message,
    validate_confirmation,
)

logger = get_logger(__name__)

_UUID_RE = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")


async def _resolve_network_uuid(
    client: UniFiClient, settings: Settings, site_id: str, identifier: str
) -> str:
    """Resolve a network identifier to the integration-API UUID format.

    The integration API ``/firewall/zones`` PUT requires network IDs in UUID
    format (``xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx``). But callers may pass
    a MongoDB ObjectId from the v2/legacy API. This helper:

    1. Returns ``identifier`` as-is if it's already a valid UUID.
    2. Otherwise searches the legacy ``/rest/networkconf`` endpoint for a
       matching ``_id`` and returns its ``external_id`` (the UUID).
    """
    if _UUID_RE.match(identifier.lower()):
        return identifier

    # ObjectId — resolve via legacy networkconf
    try:
        response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")
        items = response if isinstance(response, list) else response.get("data", [])
        for n in items:
            if isinstance(n, dict) and n.get("_id") == identifier:
                ext = n.get("external_id")
                if ext:
                    logger.debug(
                        sanitize_log_message(f"Resolved network ObjectId {identifier} → UUID {ext}")
                    )
                    return ext
    except Exception:
        logger.debug(
            sanitize_log_message(f"Failed to resolve network ObjectId {identifier} via legacy API")
        )

    raise ValueError(
        f"Could not resolve network '{identifier}' to an integration-API UUID. "
        "Pass the UUID from the integration /networks endpoint, or a MongoDB "
        "ObjectId that has an external_id mapping in /rest/networkconf."
    )


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
        logger.info(sanitize_log_message(f"Listing firewall zones for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones")
        response = await client.get(endpoint)
        # Handle both list and dict responses
        data = response if isinstance(response, list) else response.get("data", [])

        # Return raw data - API response may not match model exactly
        return cast(list[dict[str, Any]], data)


async def create_firewall_zone(
    site_id: str,
    name: str,
    settings: Settings,
    description: str | None = None,
    network_ids: list[str] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "create firewall zone", dry_run)

    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Creating firewall zone '{name}' for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload. `networkIds` is required by the integration
        # API even when empty. `description` is silently rejected by the API
        # (`api.request.unknown-property`) so we accept it in the signature for
        # backwards compatibility but log a warning and omit it from the body.
        if description:
            logger.warning(
                sanitize_log_message(
                    "create_firewall_zone: 'description' is not supported by the "
                    "UniFi integration API and will be ignored."
                )
            )

        payload: dict[str, Any] = {
            "name": name,
            "networkIds": network_ids if network_ids else [],
        }

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would create firewall zone '{name}' for site {site_id}"
                )
            )
            return {"dry_run": True, "payload": payload}

        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.post(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones"),
            json_data=payload,
        )
        # Handle both list and dict responses - single object expected
        if isinstance(response, list):
            data = response[0] if response else {}
        else:
            _raw = response.get("data", response)
            data = _raw[0] if isinstance(_raw, list) else _raw

        # Audit the action
        await audit_action(
            settings,
            action_type="create_firewall_zone",
            resource_type="firewall_zone",
            resource_id=data.get("_id", "unknown"),
            site_id=site_id,
            details={"name": name},
        )

        # Return raw data - API response may not match model exactly
        return cast(dict[str, Any], data)


async def update_firewall_zone(
    site_id: str,
    firewall_zone_id: str,
    settings: Settings,
    name: str | None = None,
    description: str | None = None,
    network_ids: list[str] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "update firewall zone", dry_run)

    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(f"Updating firewall zone {firewall_zone_id} for site {site_id}")
        )

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
        if isinstance(current_zone_response, list):
            current_zone = current_zone_response[0] if current_zone_response else {}
        else:
            _raw = current_zone_response.get("data", current_zone_response)
            current_zone = _raw[0] if isinstance(_raw, list) else _raw
        current_network_ids = current_zone.get("networkIds", [])

        # Build request payload - networkIds is required by API. `description`
        # is silently rejected by the integration API (`api.request.unknown-property`);
        # see create_firewall_zone for details.
        if description is not None:
            logger.warning(
                sanitize_log_message(
                    "update_firewall_zone: 'description' is not supported by the "
                    "UniFi integration API and will be ignored."
                )
            )

        payload: dict[str, Any] = {
            "networkIds": network_ids if network_ids is not None else current_network_ids
        }

        if name is not None:
            payload["name"] = name

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would update firewall zone {firewall_zone_id} for site {site_id}"
                )
            )
            return {"dry_run": True, "payload": payload}

        response = await client.put(
            settings.get_integration_path(
                f"sites/{resolved_site_id}/firewall/zones/{firewall_zone_id}"
            ),
            json_data=payload,
        )
        if isinstance(response, list):
            data = response[0] if response else {}
        else:
            _raw = response.get("data", response)
            data = _raw[0] if isinstance(_raw, list) else _raw

        # Audit the action
        await audit_action(
            settings,
            action_type="update_firewall_zone",
            resource_type="firewall_zone",
            resource_id=firewall_zone_id,
            site_id=site_id,
            details=payload,
        )

        # Return raw data - API response may not match model exactly
        return cast(dict[str, Any], data)


async def assign_network_to_zone(
    site_id: str,
    zone_id: str,
    network_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "assign network to zone", dry_run)

    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(
                f"Assigning network {network_id} to zone {zone_id} on site {site_id}"
            )
        )

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)

        # The integration API PUT requires UUIDs in networkIds. Resolve
        # ObjectIds to UUIDs if needed (the user may pass either format).
        resolved_network_id = await _resolve_network_uuid(
            client, settings, resolved_site_id, network_id
        )

        # Get network name
        network_name = None
        try:
            network_response = await client.get(
                settings.get_integration_path(
                    f"sites/{resolved_site_id}/networks/{resolved_network_id}"
                )
            )
            if isinstance(network_response, list):
                network_data = network_response[0] if network_response else {}
            else:
                _raw = network_response.get("data", network_response)
                network_data = _raw[0] if isinstance(_raw, list) else _raw
            network_name = network_data.get("name")
        except Exception:
            logger.warning(
                sanitize_log_message(f"Could not fetch network name for {resolved_network_id}")
            )

        # Update zone to include this network
        zone_response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones/{zone_id}")
        )
        if isinstance(zone_response, list):
            zone_data = zone_response[0] if zone_response else {}
        else:
            _raw = zone_response.get("data", zone_response)
            zone_data = _raw[0] if isinstance(_raw, list) else _raw
        current_networks = zone_data.get("networkIds", [])
        zone_name = zone_data.get("name")

        if resolved_network_id in current_networks:
            logger.info(
                sanitize_log_message(
                    f"Network {resolved_network_id} already assigned to zone {zone_id}"
                )
            )
            return ZoneNetworkAssignment(
                zone_id=zone_id,
                network_id=resolved_network_id,
                network_name=network_name,
            ).model_dump()

        updated_networks = list(current_networks) + [resolved_network_id]

        # The integration API PUT requires both networkIds AND name.
        payload: dict[str, Any] = {"networkIds": updated_networks}
        if zone_name is not None:
            payload["name"] = zone_name

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would assign network {network_id} to zone {zone_id}"
                )
            )
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
            resource_id=resolved_network_id,
            site_id=site_id,
            details={"zone_id": zone_id, "network_id": resolved_network_id},
        )

        return ZoneNetworkAssignment(
            zone_id=zone_id,
            network_id=resolved_network_id,
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
        logger.info(sanitize_log_message(f"Listing networks in zone {zone_id} on site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)

        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones/{zone_id}")
        )
        if isinstance(response, list):
            zone_data = response[0] if response else {}
        else:
            _raw = response.get("data", response)
            zone_data = _raw[0] if isinstance(_raw, list) else _raw
        network_ids = zone_data.get("networkIds", [])

        # Fetch network details for each network ID
        networks = []
        for network_id in network_ids:
            try:
                network_response = await client.get(
                    settings.get_integration_path(f"sites/{resolved_site_id}/networks/{network_id}")
                )
                if isinstance(network_response, list):
                    network_data = network_response[0] if network_response else {}
                else:
                    _raw = network_response.get("data", network_response)
                    network_data = _raw[0] if isinstance(_raw, list) else _raw
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "delete firewall zone", dry_run)

    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Deleting firewall zone {zone_id} from site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(sanitize_log_message(f"[DRY RUN] Would delete firewall zone {zone_id}"))
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "unassign network from zone", dry_run)

    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(
                f"Unassigning network {network_id} from zone {zone_id} on site {site_id}"
            )
        )

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)

        # Get current zone configuration
        zone_response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones/{zone_id}")
        )
        if isinstance(zone_response, list):
            zone_data = zone_response[0] if zone_response else {}
        else:
            _raw = zone_response.get("data", zone_response)
            zone_data = _raw[0] if isinstance(_raw, list) else _raw
        current_networks = zone_data.get("networkIds", [])
        zone_name = zone_data.get("name")

        if network_id not in current_networks:
            raise ValueError(f"Network {network_id} is not assigned to zone {zone_id}")

        # Remove network from list
        updated_networks = [nid for nid in current_networks if nid != network_id]

        payload: dict[str, Any] = {"networkIds": updated_networks}
        if zone_name is not None:
            payload["name"] = zone_name

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would remove network {network_id} from zone {zone_id}"
                )
            )
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
