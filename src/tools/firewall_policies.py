"""Firewall policies management tools for UniFi v2 API."""

import asyncio
from typing import Any, Literal

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..models.firewall_policy import FirewallPolicy, FirewallPolicyCreate
from ..utils import ResourceNotFoundError, get_logger, log_audit
from ..utils.validators import coerce_bool, validate_limit_offset

logger = get_logger(__name__)


def _ensure_local_api(settings: Settings) -> None:
    """Ensure the UniFi controller is accessed via the local API for v2 endpoints."""
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError(
            "Firewall policies (v2 API) are only available when UNIFI_API_TYPE='local'. "
            "Please configure a local UniFi gateway connection to use these tools."
        )


async def list_firewall_policies(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
    source_zone_id: str | None = None,
    destination_zone_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all firewall policies (Traffic & Firewall Rules) for a site.

    This tool fetches firewall policies from the UniFi v2 API endpoint.
    Only available with local gateway API (api_type="local").

    The UniFi v2 API returns all policies in a single response (no server-side
    pagination). When limit/offset are omitted, all matching policies are returned.
    Use limit and offset to page through results client-side.

    Args:
        site_id: Site identifier (default: "default")
        settings: Application settings
        limit: Maximum number of policies to return. When omitted, all matching
            policies are returned.
        offset: Number of policies to skip (only applied when limit is provided)
        source_zone_id: Filter to policies with this source zone ID
        destination_zone_id: Filter to policies with this destination zone ID

    Returns:
        List of firewall policy objects

    Raises:
        NotImplementedError: When using cloud API (v2 endpoints require local access)
        APIError: When API request fails

    Note:
        Cloud API does not support v2 endpoints. Configure UNIFI_API_TYPE=local
        and UNIFI_LOCAL_HOST to use this tool.
    """
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(f"Listing firewall policies for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        endpoint = f"{settings.get_v2_api_path(site_id)}/firewall-policies"
        response = await client.get(endpoint)

        policies_data = response if isinstance(response, list) else response.get("data", [])

        all_policies = [FirewallPolicy(**policy).model_dump() for policy in policies_data]

        # Apply zone filters before pagination
        if source_zone_id is not None:
            all_policies = [
                p for p in all_policies if p.get("source", {}).get("zone_id") == source_zone_id
            ]
        if destination_zone_id is not None:
            all_policies = [
                p
                for p in all_policies
                if p.get("destination", {}).get("zone_id") == destination_zone_id
            ]

        # Only paginate when the caller explicitly requests it
        if limit is not None or offset is not None:
            limit, offset = validate_limit_offset(limit, offset)
            return all_policies[offset : offset + limit]
        return all_policies


async def get_firewall_policy(
    policy_id: str,
    site_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get a specific firewall policy by ID.

    Retrieves detailed information about a single firewall policy
    from the v2 API endpoint.

    Args:
        policy_id: The firewall policy ID
        site_id: Site identifier (default: "default")
        settings: Application settings

    Returns:
        Firewall policy object

    Raises:
        NotImplementedError: When using cloud API (v2 endpoints require local access)
        ResourceNotFoundError: If policy not found
        APIError: When API request fails

    Note:
        Cloud API does not support v2 endpoints. Configure UNIFI_API_TYPE=local
        and UNIFI_LOCAL_HOST to use this tool.

    Example:
        >>> policy = await get_firewall_policy(
        ...     "682a0e42220317278bb0b2cb",
        ...     "default",
        ...     settings
        ... )
        >>> print(f"{policy['name']}: {policy['action']}")
    """
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(f"Getting firewall policy {policy_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        endpoint = f"{settings.get_v2_api_path(site_id)}/firewall-policies/{policy_id}"

        try:
            response = await client.get(endpoint)
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_policy", policy_id) from err

        # Handle both wrapped and unwrapped responses
        if isinstance(response, dict) and "data" in response:
            data = response["data"]
        else:
            data = response

        if not data:
            raise ResourceNotFoundError("firewall_policy", policy_id)

        return FirewallPolicy(**data).model_dump()


async def create_firewall_policy(
    name: str,
    action: str,
    site_id: str,
    settings: Settings,
    source_zone_id: str | None = None,
    destination_zone_id: str | None = None,
    source_matching_target: str = "ANY",
    destination_matching_target: str = "ANY",
    protocol: str = "all",
    enabled: bool = True,
    description: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a new firewall policy (Traffic & Firewall Rule).

    Only available with local gateway API (api_type="local").
    Requires confirm=True to execute. Use dry_run=True to preview.

    Args:
        name: Policy name
        action: ALLOW or BLOCK
        site_id: Site identifier
        settings: Application settings
        source_zone_id: Source zone ID
        destination_zone_id: Destination zone ID
        source_matching_target: ANY, IP, NETWORK, REGION, or CLIENT
        destination_matching_target: ANY, IP, NETWORK, or REGION
        protocol: all, tcp, udp, tcp_udp, or icmpv6
        enabled: Whether policy is active
        description: Optional description
        confirm: REQUIRED True for mutating operations
        dry_run: Preview changes without applying

    Returns:
        Created firewall policy object or dry-run preview

    Raises:
        ValueError: If confirm not True or invalid action
        NotImplementedError: When using cloud API
    """
    _ensure_local_api(settings)

    valid_actions = ["ALLOW", "BLOCK"]
    action_upper = action.upper()
    if action_upper not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Must be one of: {valid_actions}")

    source_config: dict[str, Any] = {"matching_target": source_matching_target.upper()}
    if source_zone_id:
        source_config["zone_id"] = source_zone_id

    destination_config: dict[str, Any] = {"matching_target": destination_matching_target.upper()}
    if destination_zone_id:
        destination_config["zone_id"] = destination_zone_id

    policy_data = FirewallPolicyCreate(
        name=name,
        action=action_upper,
        enabled=enabled,
        protocol=protocol,
        source=source_config,
        destination=destination_config,
        description=description,
    )

    parameters = {
        "site_id": site_id,
        "name": name,
        "action": action_upper,
        "enabled": enabled,
    }

    if dry_run:
        logger.info(f"DRY RUN: Would create firewall policy '{name}' in site '{site_id}'")
        log_audit(
            operation="create_firewall_policy",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {
            "status": "dry_run",
            "message": f"Would create firewall policy '{name}'",
            "policy": policy_data.model_dump(exclude_none=True),
        }

    if not confirm:
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    try:
        async with UniFiClient(settings) as client:
            logger.info(f"Creating firewall policy '{name}' for site {site_id}")

            if not client.is_authenticated:
                await client.authenticate()

            endpoint = f"{settings.get_v2_api_path(site_id)}/firewall-policies"
            response = await client.post(
                endpoint, json_data=policy_data.model_dump(exclude_none=True)
            )

            if isinstance(response, dict) and "data" in response:
                data = response["data"]
            else:
                data = response

            logger.info(f"Created firewall policy '{name}' in site '{site_id}'")
            log_audit(
                operation="create_firewall_policy",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return FirewallPolicy(**data).model_dump()

    except Exception as e:
        logger.error(f"Failed to create firewall policy '{name}': {e}")
        log_audit(
            operation="create_firewall_policy",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def update_firewall_policy(
    policy_id: str,
    site_id: str = "default",
    settings: Settings = None,
    name: str | None = None,
    action: Literal["ALLOW", "BLOCK"] | None = None,
    enabled: bool | None = None,
    description: str | None = None,
    protocol: Literal["all", "tcp", "udp", "tcp_udp", "icmpv6"] | None = None,
    ip_version: Literal["IPV4", "IPV6", "BOTH"] | None = None,
    source_zone_id: str | None = None,
    destination_zone_id: str | None = None,
    source_matching_target: Literal["ANY", "IP", "NETWORK", "REGION", "CLIENT"] | None = None,
    destination_matching_target: Literal["ANY", "IP", "NETWORK", "REGION"] | None = None,
    logging: bool | None = None,
    connection_state_type: Literal["ALL", "RESPOND_ONLY", "CUSTOM"] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing firewall policy.

    The UniFi v2 API requires a full object on PUT (partial payloads return 400).
    This function fetches the current policy, merges the provided changes, then
    PUTs the complete merged object. Only provided (non-None) fields are changed.

    Args:
        policy_id: ID of policy to update
        site_id: Site identifier
        settings: Application settings
        name: Policy name
        action: ALLOW or BLOCK
        enabled: Enable/disable the policy
        description: Policy description
        protocol: all, tcp, udp, tcp_udp, or icmpv6
        ip_version: IPV4, IPV6, or BOTH
        source_zone_id: Source zone ID
        destination_zone_id: Destination zone ID
        source_matching_target: ANY, IP, NETWORK, REGION, or CLIENT
        destination_matching_target: ANY, IP, NETWORK, or REGION
        logging: Enable/disable rule logging
        connection_state_type: ALL, RESPOND_ONLY, or CUSTOM
        confirm: REQUIRED True for mutating operations
        dry_run: Preview changes without applying

    Returns:
        Updated policy object

    Raises:
        NotImplementedError: When using cloud API (v2 endpoints require local access)
        ValueError: If confirmation not provided or an enum-like parameter has an invalid value
        ResourceNotFoundError: If policy not found
    """
    _ensure_local_api(settings)

    if not coerce_bool(dry_run) and not coerce_bool(confirm):
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    # Runtime guards — Literal types enforce at the MCP schema / static-analysis layer,
    # but Python does not check Literal annotations at runtime. These guards catch direct
    # Python calls and any path that bypasses the MCP layer.
    if action is not None and action.upper() not in {"ALLOW", "BLOCK"}:
        raise ValueError(f"Invalid action '{action}'. Must be ALLOW or BLOCK.")
    if protocol is not None and protocol.lower() not in {"all", "tcp", "udp", "tcp_udp", "icmpv6"}:
        raise ValueError(
            f"Invalid protocol '{protocol}'. Must be one of: all, icmpv6, tcp, tcp_udp, udp."
        )
    if ip_version is not None and ip_version.upper() not in {"IPV4", "IPV6", "BOTH"}:
        raise ValueError(f"Invalid ip_version '{ip_version}'. Must be one of: BOTH, IPV4, IPV6.")
    if connection_state_type is not None and connection_state_type.upper() not in {
        "ALL",
        "RESPOND_ONLY",
        "CUSTOM",
    }:
        raise ValueError(
            f"Invalid connection_state_type '{connection_state_type}'. "
            "Must be one of: ALL, CUSTOM, RESPOND_ONLY."
        )
    if source_matching_target is not None and source_matching_target.upper() not in {
        "ANY",
        "IP",
        "NETWORK",
        "REGION",
        "CLIENT",
    }:
        raise ValueError(
            f"Invalid source_matching_target '{source_matching_target}'. "
            "Must be one of: ANY, CLIENT, IP, NETWORK, REGION."
        )
    if destination_matching_target is not None and destination_matching_target.upper() not in {
        "ANY",
        "IP",
        "NETWORK",
        "REGION",
    }:
        raise ValueError(
            f"Invalid destination_matching_target '{destination_matching_target}'. "
            "Must be one of: ANY, IP, NETWORK, REGION."
        )

    async with UniFiClient(settings) as client:
        logger.info(f"Updating firewall policy {policy_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        endpoint = f"{settings.get_v2_api_path(site_id)}/firewall-policies/{policy_id}"

        # Fetch current policy — required because v2 PUT needs the full object
        try:
            current_response = await client.get(endpoint)
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_policy", policy_id) from err

        current_data = (
            current_response["data"]
            if isinstance(current_response, dict) and "data" in current_response
            else current_response
        )
        if not current_data:
            raise ResourceNotFoundError("firewall_policy", policy_id)

        # Start with a copy of the current full object (preserves all fields the API needs)
        payload: dict[str, Any] = dict(current_data)

        # Merge top-level scalar changes
        if name is not None:
            payload["name"] = name
        if action is not None:
            payload["action"] = action.upper()
        if enabled is not None:
            payload["enabled"] = enabled
        if description is not None:
            payload["description"] = description
        if protocol is not None:
            payload["protocol"] = protocol
        if ip_version is not None:
            payload["ip_version"] = ip_version.upper()
        if logging is not None:
            payload["logging"] = logging
        if connection_state_type is not None:
            payload["connection_state_type"] = connection_state_type.upper()

        # Merge source/destination zone and matching target changes
        if source_zone_id is not None or source_matching_target is not None:
            source = dict(payload.get("source", {}))
            if source_zone_id is not None:
                source["zone_id"] = source_zone_id
            if source_matching_target is not None:
                source["matching_target"] = source_matching_target.upper()
            payload["source"] = source

        if destination_zone_id is not None or destination_matching_target is not None:
            destination = dict(payload.get("destination", {}))
            if destination_zone_id is not None:
                destination["zone_id"] = destination_zone_id
            if destination_matching_target is not None:
                destination["matching_target"] = destination_matching_target.upper()
            payload["destination"] = destination

        # Collect what changed for audit log and dry-run output
        changes: dict[str, Any] = {}
        for field in [
            "name",
            "action",
            "enabled",
            "description",
            "protocol",
            "ip_version",
            "logging",
            "connection_state_type",
        ]:
            if payload.get(field) != current_data.get(field):
                changes[field] = payload[field]
        if payload.get("source") != current_data.get("source"):
            changes["source"] = payload["source"]
        if payload.get("destination") != current_data.get("destination"):
            changes["destination"] = payload["destination"]

        if coerce_bool(dry_run):
            logger.info(f"DRY RUN: Would update firewall policy {policy_id}")
            return {
                "status": "dry_run",
                "policy_id": policy_id,
                "changes": changes,
                "full_payload": payload,
            }

        try:
            response = await client.put(endpoint, json_data=payload)
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_policy", policy_id) from err

        updated_data = (
            response["data"] if isinstance(response, dict) and "data" in response else response
        )

        logger.info(f"Updated firewall policy {policy_id}")
        log_audit(
            operation="update_firewall_policy",
            parameters={"policy_id": policy_id, "site_id": site_id, **changes},
            result="success",
            site_id=site_id,
        )

        return FirewallPolicy(**updated_data).model_dump()


async def delete_firewall_policy(
    policy_id: str,
    site_id: str = "default",
    settings: Settings = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Delete a firewall policy.

    Warning: Cannot delete predefined system rules.

    Args:
        policy_id: ID of policy to delete
        site_id: Site identifier
        settings: Application settings
        confirm: REQUIRED True for destructive operations
        dry_run: Preview deletion without applying

    Returns:
        Confirmation of deletion

    Raises:
        NotImplementedError: When using cloud API (v2 endpoints require local access)
        ValueError: If confirmation not provided or attempting to delete predefined rule
        ResourceNotFoundError: If policy not found
    """
    _ensure_local_api(settings)

    if not coerce_bool(dry_run) and not coerce_bool(confirm):
        raise ValueError("This operation deletes a firewall policy. Pass confirm=True to proceed.")

    async with UniFiClient(settings) as client:
        logger.info(f"Deleting firewall policy {policy_id} from site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        endpoint = f"{settings.get_v2_api_path(site_id)}/firewall-policies/{policy_id}"

        try:
            policy_response = await client.get(endpoint)
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_policy", policy_id) from err

        if isinstance(policy_response, dict) and "data" in policy_response:
            policy_data = policy_response["data"]
        else:
            policy_data = policy_response

        if not policy_data:
            raise ResourceNotFoundError("firewall_policy", policy_id)

        policy = FirewallPolicy(**policy_data)

        if policy.predefined:
            raise ValueError(
                f"Cannot delete predefined system rule '{policy.name}' (id={policy_id}). "
                "Predefined rules are managed by the UniFi system."
            )

        if dry_run:
            logger.info(f"DRY RUN: Would delete firewall policy {policy_id}")
            return {
                "status": "dry_run",
                "policy_id": policy_id,
                "action": "would_delete",
                "policy": policy.model_dump(),
            }

        await client.delete(endpoint)

        log_audit(
            operation="delete_firewall_policy",
            parameters={"policy_id": policy_id, "site_id": site_id},
            result="success",
            site_id=site_id,
        )

        logger.info(f"Deleted firewall policy {policy_id} from site {site_id}")

        return {
            "status": "success",
            "policy_id": policy_id,
            "action": "deleted",
        }


async def get_zone_policy_matrix(
    site_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get a snapshot of the zone-based firewall policy matrix.

    Fetches all firewall zones and all policies, then groups policies by
    source/destination zone pair to give a full picture of the current
    security posture.

    Only available with local gateway API (api_type="local").

    Note:
        The v2 policies API uses MongoDB ObjectIDs for zone_id fields, while
        the integration v1 zones API uses UUIDs. These two ID spaces cannot be
        automatically joined — both are returned so you have both the zone names
        (from v1) and the policy groupings (by v2 ObjectID). Use list_firewall_zones
        alongside this result to identify which zone name corresponds to which zone_id.

    Args:
        site_id: Site identifier (default: "default")
        settings: Application settings

    Returns:
        Dictionary with:
        - zones: list of zone objects from the integration API (with names)
        - matrix: list of zone-pair entries, each with source_zone_id,
          destination_zone_id, policy_count, and policies list
        - summary: counts of total zones, policies, and covered zone pairs

    Raises:
        NotImplementedError: When using cloud API
    """
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(f"Building zone policy matrix for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Resolve the site UUID required by the integration v1 zones endpoint
        resolved_site_id = await client.resolve_site_id(site_id)

        # Fetch zones (integration v1) and policies (v2) concurrently —
        # the two requests are independent so we can run them in parallel.
        zones_endpoint = settings.get_integration_path(f"sites/{resolved_site_id}/firewall/zones")
        policies_endpoint = f"{settings.get_v2_api_path(site_id)}/firewall-policies"

        zones_response, policies_response = await asyncio.gather(
            client.get(zones_endpoint),
            client.get(policies_endpoint),
        )

        zones_data = (
            zones_response.get("data", []) if isinstance(zones_response, dict) else zones_response
        )
        policies_data = (
            policies_response
            if isinstance(policies_response, list)
            else policies_response.get("data", [])
        )

        # Build zone summaries
        zones = [
            {
                "id": z.get("id"),
                "name": z.get("name"),
                "network_count": len(z.get("networkIds", [])),
            }
            for z in zones_data
        ]

        # Group policies by (source_zone_id, destination_zone_id)
        pairs: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for policy in policies_data:
            src = policy.get("source", {}).get("zone_id")
            dst = policy.get("destination", {}).get("zone_id")
            if not src or not dst:
                continue
            key = (src, dst)
            if key not in pairs:
                pairs[key] = []
            pairs[key].append(
                {
                    "id": policy.get("_id"),
                    "name": policy.get("name"),
                    "action": policy.get("action"),
                    "enabled": policy.get("enabled"),
                    "predefined": policy.get("predefined", False),
                }
            )

        matrix = [
            {
                "source_zone_id": src,
                "destination_zone_id": dst,
                "policy_count": len(policies),
                "policies": policies,
            }
            for (src, dst), policies in sorted(pairs.items())
        ]

        return {
            "zones": zones,
            "matrix": matrix,
            "summary": {
                "total_zones": len(zones),
                "total_policies": len(policies_data),
                "zone_pairs_with_policies": len(matrix),
            },
            "note": (
                "zone_ids in the matrix use v2 MongoDB ObjectIDs; "
                "zone ids in the zones list use integration v1 UUIDs — "
                "they cannot be automatically joined. "
                "Use policy names and zone names to correlate manually."
            ),
        }
