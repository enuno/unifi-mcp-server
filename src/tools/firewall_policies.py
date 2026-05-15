"""Firewall policies management tools for UniFi v2 API."""

import asyncio
from typing import Any, Literal

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..models.firewall_policy import FirewallPolicy, FirewallPolicyCreate, FirewallZoneV2Mapping
from ..utils import APIError, ResourceNotFoundError, get_logger, log_audit, sanitize_log_message
from ..utils.validators import coerce_bool, validate_limit_offset

logger = get_logger(__name__)

# The v2 `firewall-policies` API uses internal MongoDB ObjectIds for zone_id,
# while the integration API (and most other MCP tools) return the public
# UUIDs as `external_id`. This cache maps both the external UUID, zone name,
# and zone_key to the internal ObjectId, populated on demand.
_zone_cache: dict[str, dict[str, str]] = {}

_VALID_IP_VERSIONS = ("IPV4", "IPV6", "BOTH")
_VALID_PORT_MATCHING_TYPES = ("ANY", "SPECIFIC", "OBJECT")


def _build_match_target(
    *,
    zone_id: str | None,
    matching_target: str,
    port: str | None,
    port_group_id: str | None,
    port_matching_type: str | None,
    match_opposite_ports: bool | None,
    ips: list[str] | None = None,
    network_ids: list[str] | None = None,
    client_macs: list[str] | None = None,
    match_opposite_ips: bool | None = None,
) -> dict[str, Any]:
    """Build a source/destination match-target dict for a firewall policy.

    The v2 ``firewall-policies`` endpoint stores source and destination
    criteria as nested objects with two discriminators:

    **Port matching** (``port_matching_type``):

    * ``ANY`` — no port filter (default)
    * ``SPECIFIC`` — a literal port / range in ``port``
    * ``OBJECT`` — a reference to a firewall port-group via ``port_group_id``

    **Target matching** (``matching_target`` + ``matching_target_type``):

    * ``ANY`` — match everything in the zone
    * ``IP`` — match specific IPs/CIDRs via ``ips`` list (requires
      ``matching_target_type=SPECIFIC``, auto-set when ``ips`` is provided)
    * ``NETWORK`` — match specific VLANs via ``network_ids``
    * ``CLIENT`` — match specific MACs via ``client_macs``
    * ``REGION`` — match by ISO country codes (not wired yet)

    Both discriminators are auto-selected based on which fields the caller
    provides, so callers don't have to think about the mode fields.
    """
    if port and port_group_id:
        raise ValueError(
            "Cannot specify both 'port' and 'port_group_id' on the same "
            "match target — use one or the other."
        )

    if port_matching_type is None:
        if port_group_id:
            resolved_mt = "OBJECT"
        elif port:
            resolved_mt = "SPECIFIC"
        else:
            resolved_mt = "ANY"
    else:
        resolved_mt = port_matching_type.upper()
        if resolved_mt not in _VALID_PORT_MATCHING_TYPES:
            raise ValueError(
                f"Invalid port_matching_type '{port_matching_type}'. "
                f"Must be one of: {list(_VALID_PORT_MATCHING_TYPES)}"
            )

    # Validate consistency: an explicit SPECIFIC requires `port` and
    # OBJECT requires `port_group_id`. Without these the API would receive
    # an incomplete payload and reject it, so fail fast here.
    if resolved_mt == "SPECIFIC" and not port:
        raise ValueError(
            "port_matching_type='SPECIFIC' requires a 'port' value (e.g. '53' or '9000-9010')."
        )
    if resolved_mt == "OBJECT" and not port_group_id:
        raise ValueError(
            "port_matching_type='OBJECT' requires a 'port_group_id' "
            "referencing an existing firewall port-group."
        )

    # Auto-detect matching_target from the provided lists when the caller
    # passes the default "ANY" but also supplies ips/network_ids/client_macs.
    resolved_matching_target = matching_target.upper()
    if resolved_matching_target == "ANY":
        if ips:
            resolved_matching_target = "IP"
        elif network_ids:
            resolved_matching_target = "NETWORK"
        elif client_macs:
            resolved_matching_target = "CLIENT"

    target: dict[str, Any] = {
        "matching_target": resolved_matching_target,
        "port_matching_type": resolved_mt,
    }

    # When matching_target is not ANY, the API requires matching_target_type.
    if resolved_matching_target != "ANY":
        target["matching_target_type"] = "SPECIFIC"

    if zone_id:
        target["zone_id"] = zone_id
    if resolved_mt == "SPECIFIC":
        target["port"] = port
    if resolved_mt == "OBJECT":
        target["port_group_id"] = port_group_id
    if match_opposite_ports is not None:
        target["match_opposite_ports"] = match_opposite_ports
    if ips is not None:
        target["ips"] = list(ips)
    if network_ids is not None:
        target["network_ids"] = list(network_ids)
    if client_macs is not None:
        target["client_macs"] = list(client_macs)
    if match_opposite_ips is not None:
        target["match_opposite_ips"] = match_opposite_ips
    return target


def _collect_port_overrides(
    *,
    port: str | None,
    port_group_id: str | None,
    port_matching_type: str | None,
    match_opposite_ports: bool | None,
) -> dict[str, Any] | None:
    """Build the partial port-related override dict applied during update.

    Returns ``None`` when the caller did not request any port-related
    change. The result is a small dict with the keys the v2 API expects on
    the ``source`` / ``destination`` sub-objects: ``port_matching_type``,
    optionally ``port`` or ``port_group_id``, and optionally
    ``match_opposite_ports``. It also clears the field that no longer
    applies (e.g. clearing ``port`` when switching to OBJECT mode) so the
    merged payload remains internally consistent.
    """
    if (
        port is None
        and port_group_id is None
        and port_matching_type is None
        and match_opposite_ports is None
    ):
        return None

    if port and port_group_id:
        raise ValueError(
            "Cannot specify both 'port' and 'port_group_id' on the same "
            "match target — use one or the other."
        )

    if port_matching_type is None:
        if port_group_id:
            resolved_mt: str | None = "OBJECT"
        elif port:
            resolved_mt = "SPECIFIC"
        else:
            resolved_mt = None
    else:
        resolved_mt = port_matching_type.upper()
        if resolved_mt not in _VALID_PORT_MATCHING_TYPES:
            raise ValueError(
                f"Invalid port_matching_type '{port_matching_type}'. "
                f"Must be one of: {list(_VALID_PORT_MATCHING_TYPES)}"
            )

    overrides: dict[str, Any] = {}
    if resolved_mt is not None:
        overrides["port_matching_type"] = resolved_mt
    if port is not None:
        overrides["port"] = port
    if port_group_id is not None:
        overrides["port_group_id"] = port_group_id
    if match_opposite_ports is not None:
        overrides["match_opposite_ports"] = match_opposite_ports
    return overrides


def _merge_port_overrides(existing: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge port overrides into an existing source/destination sub-dict.

    Clears the now-unused field when switching modes — e.g. switching from
    SPECIFIC to OBJECT removes the stale ``port``; switching to ANY removes
    both ``port`` and ``port_group_id``.
    """
    merged = {**existing, **overrides}
    new_mode = merged.get("port_matching_type")
    if new_mode == "ANY":
        merged.pop("port", None)
        merged.pop("port_group_id", None)
    elif new_mode == "SPECIFIC":
        merged.pop("port_group_id", None)
    elif new_mode == "OBJECT":
        merged.pop("port", None)
    return merged


def _extract_zone_list(response: Any) -> list[dict[str, Any]]:
    """Normalize a zone-listing response into a plain list of dicts.

    Handles the three shapes ``UniFiClient`` can return:
    - raw list (when the API response is ``{"data": [...]}``)
    - dict with ``data`` field (may be ``None`` or another list)
    - bare dict payload (unusual but defensively handled)
    """
    if isinstance(response, list):
        return [z for z in response if isinstance(z, dict)]
    if isinstance(response, dict):
        inner = response.get("data")
        if inner is None:
            return []
        if isinstance(inner, list):
            return [z for z in inner if isinstance(z, dict)]
    return []


def _ensure_local_api(settings: Settings) -> None:
    """Ensure the UniFi controller is accessed via the local API for v2 endpoints."""
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError(
            "Firewall policies (v2 API) are only available when UNIFI_API_TYPE='local'. "
            "Please configure a local UniFi gateway connection to use these tools."
        )


async def _load_zone_index(client: UniFiClient, settings: Settings, site_id: str) -> dict[str, str]:
    """Fetch the v2 zone list and build a name/UUID → internal-_id index."""
    endpoint = f"{settings.get_v2_api_path(site_id)}/firewall/zone"
    response = await client.get(endpoint)
    zones = _extract_zone_list(response)

    index: dict[str, str] = {}
    for zone in zones:
        internal_id = zone.get("_id")
        if not internal_id:
            continue
        # Index the internal _id as itself so callers that already know the
        # ObjectId continue to work.
        index[internal_id] = internal_id
        if external_id := zone.get("external_id"):
            index[external_id] = internal_id
        if name := zone.get("name"):
            index[name.lower()] = internal_id
        if zone_key := zone.get("zone_key"):
            index[zone_key.lower()] = internal_id
    _zone_cache[site_id] = index
    return index


async def _resolve_zone_id(
    client: UniFiClient, settings: Settings, site_id: str, identifier: str
) -> str:
    """Resolve a zone identifier to the v2 API's internal zone _id.

    Accepts a zone name, external UUID, or internal ObjectId.
    Raises ValueError if no match is found.
    """
    if not identifier:
        raise ValueError("Zone identifier is required")
    index = _zone_cache.get(site_id) or await _load_zone_index(client, settings, site_id)
    if identifier in index:
        return index[identifier]
    lowered = identifier.lower()
    if lowered in index:
        return index[lowered]
    # Refresh once in case the zone was created after the cache was populated.
    index = await _load_zone_index(client, settings, site_id)
    if identifier in index:
        return index[identifier]
    if lowered in index:
        return index[lowered]
    known_internal_ids = sorted(set(index.values()))
    raise ValueError(
        f"Could not resolve firewall zone '{identifier}'. Pass a zone name "
        f"(e.g. 'Internal'), external UUID, or internal _id. "
        f"Known internal zone ids: {known_internal_ids}"
    )


async def list_firewall_zones_v2(
    site_id: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    """List firewall zones from the v2 API with internal + external IDs.

    The v2 ``firewall-policies`` endpoint uses internal MongoDB ObjectIds for
    zone_id, not the public integration API UUIDs. This tool returns the
    mapping so callers can hand either identifier (or the zone name) to
    ``create_firewall_policy`` / ``update_firewall_policy``.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        List of :class:`FirewallZoneV2Mapping` dicts.

    Raises:
        NotImplementedError: When using cloud API
        APIError: When the API request fails
    """
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Listing v2 firewall zones for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        endpoint = f"{settings.get_v2_api_path(site_id)}/firewall/zone"
        try:
            response = await client.get(endpoint)
        except APIError:
            logger.exception(
                sanitize_log_message(f"Failed to list v2 firewall zones for site {site_id}")
            )
            raise

        zones = _extract_zone_list(response)

        return [
            FirewallZoneV2Mapping(
                internal_id=z.get("_id"),
                external_id=z.get("external_id"),
                name=z.get("name"),
                zone_key=z.get("zone_key"),
                default_zone=z.get("default_zone") or False,
                network_ids=z.get("network_ids") or [],
            ).model_dump()
            for z in zones
        ]


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
        logger.info(sanitize_log_message(f"Listing firewall policies for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        normalized_site_id = client._site_uuid_to_name.get(site_id, site_id)
        endpoint = f"{settings.get_v2_api_path(normalized_site_id)}/firewall-policies"
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
        logger.info(sanitize_log_message(f"Getting firewall policy {policy_id} for site {site_id}"))

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
    source_port: str | None = None,
    destination_port: str | None = None,
    source_port_group_id: str | None = None,
    destination_port_group_id: str | None = None,
    source_port_matching_type: str | None = None,
    destination_port_matching_type: str | None = None,
    source_match_opposite_ports: bool | None = None,
    destination_match_opposite_ports: bool | None = None,
    source_ips: list[str] | None = None,
    destination_ips: list[str] | None = None,
    source_network_ids: list[str] | None = None,
    destination_network_ids: list[str] | None = None,
    source_client_macs: list[str] | None = None,
    destination_client_macs: list[str] | None = None,
    source_match_opposite_ips: bool | None = None,
    destination_match_opposite_ips: bool | None = None,
    protocol: str = "all",
    enabled: bool = True,
    description: str | None = None,
    ip_version: str = "BOTH",
    create_allow_respond: bool | None = None,
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
        source_zone_id: Source zone — accepts a zone name (e.g. "Internal"),
            public integration-API UUID, or internal ObjectId. All forms are
            resolved to the v2 API's internal zone _id automatically.
        destination_zone_id: Destination zone (same identifier flexibility as
            source)
        source_matching_target: ANY, IP, NETWORK, REGION, or CLIENT
        destination_matching_target: ANY, IP, NETWORK, or REGION
        source_port: Source port — single port "53" or range "9000-9010".
            Implies ``source_port_matching_type=SPECIFIC``.
        destination_port: Destination port — same format as source_port.
            Implies ``destination_port_matching_type=SPECIFIC``.
        source_port_group_id: Reference a firewall port-group on the source
            side. Implies ``source_port_matching_type=OBJECT``. Use the
            ``firewall_groups`` tools to create / list port groups.
        destination_port_group_id: Same as source_port_group_id but on the
            destination side.
        source_port_matching_type: Override auto-detection of port matching
            mode (ANY/SPECIFIC/OBJECT). Usually you don't need this — pass
            ``source_port`` or ``source_port_group_id`` and the mode is set
            automatically.
        destination_port_matching_type: Same as source_port_matching_type
            but on the destination side.
        source_match_opposite_ports: Invert the source port match (NOT)
        destination_match_opposite_ports: Invert the destination port match
        source_ips: List of source IPs or CIDRs (e.g. ``["10.0.100.0/24"]``).
            Auto-sets ``source_matching_target=IP`` +
            ``matching_target_type=SPECIFIC``.
        destination_ips: List of destination IPs or CIDRs. Auto-sets
            ``destination_matching_target=IP``.
        source_network_ids: List of source network (VLAN) internal IDs.
            Auto-sets ``source_matching_target=NETWORK``.
        destination_network_ids: List of destination network IDs.
        source_client_macs: List of source client MAC addresses.
            Auto-sets ``source_matching_target=CLIENT``.
        destination_client_macs: List of destination client MACs.
        source_match_opposite_ips: Invert the source IP match (NOT)
        destination_match_opposite_ips: Invert the destination IP match
        protocol: all, tcp, udp, tcp_udp, or icmpv6
        enabled: Whether policy is active
        description: Optional description
        ip_version: IPV4, IPV6, or BOTH (required by API; defaults to BOTH)
        create_allow_respond: When True, automatically create a paired ALLOW
            RESPOND rule for stateful TCP/UDP sessions.
        confirm: REQUIRED True for mutating operations
        dry_run: Preview changes without applying

    Returns:
        Created firewall policy object or dry-run preview

    Raises:
        ValueError: If confirm not True, invalid action, or zone cannot be
            resolved.
        NotImplementedError: When using cloud API
    """
    _ensure_local_api(settings)

    valid_actions = ["ALLOW", "BLOCK"]
    action_upper = action.upper()
    if action_upper not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Must be one of: {valid_actions}")

    ip_version_upper = ip_version.upper()
    if ip_version_upper not in _VALID_IP_VERSIONS:
        raise ValueError(
            f"Invalid ip_version '{ip_version}'. Must be one of: {list(_VALID_IP_VERSIONS)}"
        )

    # Coerce string inputs ("true"/"false") to real booleans — MCP clients
    # may serialise these flags as strings and plain truthiness would treat
    # "False" as True, bypassing the confirmation gate entirely.
    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)

    if not dry_run_bool and not confirm_bool:
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    parameters = {
        "site_id": site_id,
        "name": name,
        "action": action_upper,
        "enabled": enabled,
        "source_zone_id": source_zone_id,
        "destination_zone_id": destination_zone_id,
    }

    try:
        async with UniFiClient(settings) as client:
            logger.info(
                sanitize_log_message(f"Creating firewall policy '{name}' for site {site_id}")
            )

            if not client.is_authenticated:
                await client.authenticate()

            # Resolve zone identifiers to the internal _ids the v2 API
            # requires (accepting zone name / external UUID / internal _id).
            resolved_source_zone = (
                await _resolve_zone_id(client, settings, site_id, source_zone_id)
                if source_zone_id
                else None
            )
            resolved_destination_zone = (
                await _resolve_zone_id(client, settings, site_id, destination_zone_id)
                if destination_zone_id
                else None
            )

            source_config = _build_match_target(
                zone_id=resolved_source_zone,
                matching_target=source_matching_target,
                port=source_port,
                port_group_id=source_port_group_id,
                port_matching_type=source_port_matching_type,
                match_opposite_ports=source_match_opposite_ports,
                ips=source_ips,
                network_ids=source_network_ids,
                client_macs=source_client_macs,
                match_opposite_ips=source_match_opposite_ips,
            )
            destination_config = _build_match_target(
                zone_id=resolved_destination_zone,
                matching_target=destination_matching_target,
                port=destination_port,
                port_group_id=destination_port_group_id,
                port_matching_type=destination_port_matching_type,
                match_opposite_ports=destination_match_opposite_ports,
                ips=destination_ips,
                network_ids=destination_network_ids,
                client_macs=destination_client_macs,
                match_opposite_ips=destination_match_opposite_ips,
            )

            # The v2 firewall-policies endpoint requires `schedule` and
            # `ip_version`; the API 400s (with an obfuscated Spring error)
            # if either is omitted. Default to an always-on rule.
            #
            # create_allow_respond must be False for BLOCK rules — the API
            # rejects BLOCK + respond-traffic enabled. Auto-set when the
            # caller doesn't specify.
            if create_allow_respond is None:
                resolved_allow_respond = action_upper != "BLOCK"
            else:
                resolved_allow_respond = create_allow_respond

            policy_data = FirewallPolicyCreate(
                name=name,
                action=action_upper,
                enabled=enabled,
                protocol=protocol,
                ip_version=ip_version_upper,
                source=source_config,
                destination=destination_config,
                description=description,
                schedule={"mode": "ALWAYS"},
                create_allow_respond=resolved_allow_respond,
            )

            if dry_run_bool:
                logger.info(
                    sanitize_log_message(
                        f"DRY RUN: Would create firewall policy '{name}' in site '{site_id}'"
                    )
                )
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

            endpoint = f"{settings.get_v2_api_path(site_id)}/firewall-policies"
            response = await client.post(
                endpoint, json_data=policy_data.model_dump(exclude_none=True)
            )

            if isinstance(response, dict) and "data" in response:
                data = response["data"]
            else:
                data = response

            logger.info(
                sanitize_log_message(f"Created firewall policy '{name}' in site '{site_id}'")
            )
            log_audit(
                operation="create_firewall_policy",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return FirewallPolicy(**data).model_dump()

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to create firewall policy '{name}': {e}"))
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
    logging: bool | None = None,
    ip_version: str | None = None,
    protocol: str | None = None,
    description: str | None = None,
    source_zone_id: str | None = None,
    destination_zone_id: str | None = None,
    source_port: str | None = None,
    destination_port: str | None = None,
    source_port_group_id: str | None = None,
    destination_port_group_id: str | None = None,
    source_port_matching_type: str | None = None,
    destination_port_matching_type: str | None = None,
    source_match_opposite_ports: bool | None = None,
    destination_match_opposite_ports: bool | None = None,
    source_ips: list[str] | None = None,
    destination_ips: list[str] | None = None,
    source_network_ids: list[str] | None = None,
    destination_network_ids: list[str] | None = None,
    source_client_macs: list[str] | None = None,
    destination_client_macs: list[str] | None = None,
    source_match_opposite_ips: bool | None = None,
    destination_match_opposite_ips: bool | None = None,
    create_allow_respond: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing firewall policy.

    The v2 ``firewall-policies`` PUT endpoint requires the **full** policy
    object — a partial payload like ``{"logging": true}`` is rejected with
    ``Validation failed ... field 'action': rejected value [null]``. To
    support partial updates from the caller's perspective, this tool
    fetches the existing policy, merges in the provided field overrides,
    strips ``_id`` / ``predefined`` (which the API controls), and PUTs the
    merged object back.

    Args:
        policy_id: ID of policy to update
        site_id: Site identifier
        settings: Application settings
        name: New policy name
        action: New action ALLOW/BLOCK
        enabled: Enable/disable the policy
        logging: Toggle firewall rule logging. Forces CPU inspection of the
            matched flows, which makes them visible in the v2 traffic-flows
            endpoint (default-allowed inter-VLAN traffic is normally
            hardware-offloaded and never reaches the flow table).
        ip_version: IPV4 / IPV6 / BOTH
        protocol: Transport protocol (all, tcp, udp, tcp_udp, icmpv6)
        description: Free-form description
        source_port: Source port — single port "53" or range "9000-9010".
            Auto-sets ``source_port_matching_type=SPECIFIC``.
        destination_port: Destination port — same format as source_port.
        source_port_group_id: Reference a firewall port-group on the source
            side. Auto-sets ``source_port_matching_type=OBJECT``.
        destination_port_group_id: Reference a firewall port-group on the
            destination side.
        source_port_matching_type: Override auto-detection of port matching
            mode (ANY/SPECIFIC/OBJECT). To clear an existing port filter,
            pass ``"ANY"`` explicitly.
        destination_port_matching_type: Same as source_port_matching_type.
        source_match_opposite_ports: Invert the source port match (NOT)
        destination_match_opposite_ports: Invert the destination port match
        source_zone_id: New source zone — name, UUID, or ObjectId
        destination_zone_id: New destination zone — name, UUID, or ObjectId
        source_ips: Replace source IP/CIDR list (sets matching_target=IP)
        destination_ips: Replace destination IP/CIDR list
        source_network_ids: Replace source network ID list
        destination_network_ids: Replace destination network ID list
        source_client_macs: Replace source MAC list
        destination_client_macs: Replace destination MAC list
        source_match_opposite_ips: Invert the source IP match (NOT)
        destination_match_opposite_ips: Invert the destination IP match
        create_allow_respond: Create a paired stateful respond rule
        confirm: REQUIRED True for mutating operations
        dry_run: Preview changes without applying

    Returns:
        Updated policy object

    Raises:
        NotImplementedError: When using cloud API (v2 endpoints require local access)
        ValueError: If confirmation not provided or an invalid value is supplied
        ResourceNotFoundError: If policy not found
    """
    _ensure_local_api(settings)

    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)

    if not dry_run_bool and not confirm_bool:
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    # Validate overrides up-front so we fail fast before hitting the API.
    action_upper: str | None = None
    if action is not None:
        action_upper = action.upper()
        if action_upper not in ("ALLOW", "BLOCK"):
            raise ValueError(f"Invalid action '{action}'. Must be ALLOW or BLOCK.")

    ip_version_upper: str | None = None
    if ip_version is not None:
        ip_version_upper = ip_version.upper()
        if ip_version_upper not in _VALID_IP_VERSIONS:
            raise ValueError(
                f"Invalid ip_version '{ip_version}'. Must be one of: {list(_VALID_IP_VERSIONS)}"
            )

    if protocol is not None and protocol.lower() not in {"all", "tcp", "udp", "tcp_udp", "icmpv6"}:
        raise ValueError(
            f"Invalid protocol '{protocol}'. Must be one of: all, icmpv6, tcp, tcp_udp, udp."
        )

    # Collect top-level overrides so we can both preview them and merge them.
    overrides: dict[str, Any] = {}
    if name is not None:
        overrides["name"] = name
    if action_upper is not None:
        overrides["action"] = action_upper
    if enabled is not None:
        overrides["enabled"] = enabled
    if logging is not None:
        overrides["logging"] = logging
    if ip_version_upper is not None:
        overrides["ip_version"] = ip_version_upper
    if protocol is not None:
        overrides["protocol"] = protocol
    if description is not None:
        overrides["description"] = description
    if create_allow_respond is not None:
        overrides["create_allow_respond"] = create_allow_respond

    # Validate / collect port overrides; these merge into the source and
    # destination sub-dicts inside the policy, not as top-level fields.
    source_port_overrides: dict[str, Any] | None = _collect_port_overrides(
        port=source_port,
        port_group_id=source_port_group_id,
        port_matching_type=source_port_matching_type,
        match_opposite_ports=source_match_opposite_ports,
    )
    destination_port_overrides: dict[str, Any] | None = _collect_port_overrides(
        port=destination_port,
        port_group_id=destination_port_group_id,
        port_matching_type=destination_port_matching_type,
        match_opposite_ports=destination_match_opposite_ports,
    )

    # Collect zone + IP/network/client matching overrides for the source/dest
    # sub-dicts. Zone changes go into the same sub-dict as other target
    # matching fields.
    source_target_overrides: dict[str, Any] = {}
    # Note: source_zone_id resolution is deferred to inside the UniFiClient
    # context manager where _resolve_zone_id can make API calls.
    if source_ips is not None:
        source_target_overrides["matching_target"] = "IP"
        source_target_overrides["matching_target_type"] = "SPECIFIC"
        source_target_overrides["ips"] = list(source_ips)
    if source_network_ids is not None:
        source_target_overrides["matching_target"] = "NETWORK"
        source_target_overrides["matching_target_type"] = "SPECIFIC"
        source_target_overrides["network_ids"] = list(source_network_ids)
    if source_client_macs is not None:
        source_target_overrides["matching_target"] = "CLIENT"
        source_target_overrides["matching_target_type"] = "SPECIFIC"
        source_target_overrides["client_macs"] = list(source_client_macs)
    if source_match_opposite_ips is not None:
        source_target_overrides["match_opposite_ips"] = source_match_opposite_ips

    destination_target_overrides: dict[str, Any] = {}
    # Note: destination_zone_id resolution also deferred to the client context.
    if destination_ips is not None:
        destination_target_overrides["matching_target"] = "IP"
        destination_target_overrides["matching_target_type"] = "SPECIFIC"
        destination_target_overrides["ips"] = list(destination_ips)
    if destination_network_ids is not None:
        destination_target_overrides["matching_target"] = "NETWORK"
        destination_target_overrides["matching_target_type"] = "SPECIFIC"
        destination_target_overrides["network_ids"] = list(destination_network_ids)
    if destination_client_macs is not None:
        destination_target_overrides["matching_target"] = "CLIENT"
        destination_target_overrides["matching_target_type"] = "SPECIFIC"
        destination_target_overrides["client_macs"] = list(destination_client_macs)
    if destination_match_opposite_ips is not None:
        destination_target_overrides["match_opposite_ips"] = destination_match_opposite_ips

    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(f"Updating firewall policy {policy_id} for site {site_id}")
        )

        if not client.is_authenticated:
            await client.authenticate()

        # Normalize site UUID to short-name for API endpoint (Bug #73)
        normalized_site_id = client._site_uuid_to_name.get(site_id, site_id)

        # Resolve zone identifiers to internal _ids (accepts name, UUID, or
        # ObjectId — same flexibility as create_firewall_policy).
        if source_zone_id is not None:
            source_target_overrides["zone_id"] = await _resolve_zone_id(
                client, settings, normalized_site_id, source_zone_id
            )
        if destination_zone_id is not None:
            destination_target_overrides["zone_id"] = await _resolve_zone_id(
                client, settings, normalized_site_id, destination_zone_id
            )

        endpoint = f"{settings.get_v2_api_path(normalized_site_id)}/firewall-policies/{policy_id}"

        # Fetch the existing policy so we can merge + PUT the full object.
        try:
            current_response = await client.get(endpoint)
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_policy", policy_id) from err

        current = (
            current_response.get("data", current_response)
            if isinstance(current_response, dict)
            else current_response
        )
        if not current or not isinstance(current, dict):
            raise ResourceNotFoundError("firewall_policy", policy_id)

        if current.get("predefined"):
            raise ValueError(
                f"Cannot update predefined system rule '{current.get('name', policy_id)}'."
            )

        merged = {**current, **overrides}
        # Apply port and target-matching overrides to the existing source /
        # destination sub-dicts so other fields survive.
        if source_port_overrides or source_target_overrides:
            src = dict(merged.get("source", {}))
            if source_port_overrides:
                src = _merge_port_overrides(src, source_port_overrides)
            src.update(source_target_overrides)
            merged["source"] = src
        if destination_port_overrides or destination_target_overrides:
            dst = dict(merged.get("destination", {}))
            if destination_port_overrides:
                dst = _merge_port_overrides(dst, destination_port_overrides)
            dst.update(destination_target_overrides)
            merged["destination"] = dst
        # Strip fields the API controls; sending them back causes validation errors.
        for field in ("_id", "predefined"):
            merged.pop(field, None)

        if dry_run_bool:
            logger.info(sanitize_log_message(f"DRY RUN: Would update firewall policy {policy_id}"))
            return {
                "status": "dry_run",
                "policy_id": policy_id,
                "changes": overrides,
                "merged_payload": merged,
            }

        try:
            response = await client.put(endpoint, json_data=merged)
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_policy", policy_id) from err

        data = response.get("data", response) if isinstance(response, dict) else response

        logger.info(sanitize_log_message(f"Updated firewall policy {policy_id}"))
        log_audit(
            operation="update_firewall_policy",
            parameters={"policy_id": policy_id, "site_id": site_id, **overrides},
            result="success",
            site_id=site_id,
        )

        return FirewallPolicy(**data).model_dump()


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
        logger.info(
            sanitize_log_message(f"Deleting firewall policy {policy_id} from site {site_id}")
        )

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
            logger.info(sanitize_log_message(f"DRY RUN: Would delete firewall policy {policy_id}"))
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

        logger.info(
            sanitize_log_message(f"Deleted firewall policy {policy_id} from site {site_id}")
        )

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
