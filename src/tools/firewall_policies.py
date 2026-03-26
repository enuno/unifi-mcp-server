"""Firewall policies management tools for UniFi v2 API."""

from typing import Any

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..models.firewall_policy import FirewallPolicy, FirewallPolicyCreate
from ..utils import ResourceNotFoundError, get_logger, log_audit, sanitize_log_message
from ..utils.validators import coerce_bool

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
) -> list[dict[str, Any]]:
    """List all firewall policies (Traffic & Firewall Rules) for a site.

    This tool fetches firewall policies from the UniFi v2 API endpoint.
    Only available with local gateway API (api_type="local").

    Args:
        site_id: Site identifier (default: "default")
        settings: Application settings

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

        endpoint = f"{settings.get_v2_api_path(site_id)}/firewall-policies"
        response = await client.get(endpoint)

        policies_data = response if isinstance(response, list) else response.get("data", [])

        return [FirewallPolicy(**policy).model_dump() for policy in policies_data]


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
        logger.info(sanitize_log_message(f"DRY RUN: Would create firewall policy '{name}' in site '{site_id}'"))
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
            logger.info(sanitize_log_message(f"Creating firewall policy '{name}' for site {site_id}"))

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

            logger.info(sanitize_log_message(f"Created firewall policy '{name}' in site '{site_id}'"))
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
    action: str | None = None,
    enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing firewall policy.

    Only provided fields are updated (partial update).

    Args:
        policy_id: ID of policy to update
        site_id: Site identifier
        settings: Application settings
        name: New policy name (optional)
        action: New action ALLOW/BLOCK (optional)
        enabled: Enable/disable (optional)
        confirm: REQUIRED True for mutating operations
        dry_run: Preview changes without applying

    Returns:
        Updated policy object

    Raises:
        NotImplementedError: When using cloud API (v2 endpoints require local access)
        ValueError: If confirmation not provided
        ResourceNotFoundError: If policy not found
    """
    _ensure_local_api(settings)

    if not coerce_bool(dry_run) and not coerce_bool(confirm):
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    # Build update payload with only provided fields
    update_data: dict[str, Any] = {}
    if name is not None:
        update_data["name"] = name
    if action is not None:
        action_upper = action.upper()
        if action_upper not in ["ALLOW", "BLOCK"]:
            raise ValueError(f"Invalid action '{action}'. Must be ALLOW or BLOCK.")
        update_data["action"] = action_upper
    if enabled is not None:
        update_data["enabled"] = enabled

    if dry_run:
        logger.info(sanitize_log_message(f"DRY RUN: Would update firewall policy {policy_id}"))
        return {
            "status": "dry_run",
            "policy_id": policy_id,
            "changes": update_data,
        }

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Updating firewall policy {policy_id} for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        endpoint = f"{settings.get_v2_api_path(site_id)}/firewall-policies/{policy_id}"

        try:
            response = await client.put(endpoint, json_data=update_data)
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_policy", policy_id) from err

        if isinstance(response, dict) and "data" in response:
            data = response["data"]
        else:
            data = response

        logger.info(sanitize_log_message(f"Updated firewall policy {policy_id}"))
        log_audit(
            operation="update_firewall_policy",
            parameters={"policy_id": policy_id, "site_id": site_id, **update_data},
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
        logger.info(sanitize_log_message(f"Deleting firewall policy {policy_id} from site {site_id}"))

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

        logger.info(sanitize_log_message(f"Deleted firewall policy {policy_id} from site {site_id}"))

        return {
            "status": "success",
            "policy_id": policy_id,
            "action": "deleted",
        }
