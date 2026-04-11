"""Access Control List (ACL) management tools."""

from typing import Any

from ..api.client import UniFiClient
from ..config import Settings
from ..models import ACLRule
from ..utils import audit_action, get_logger, sanitize_log_message, validate_confirmation

logger = get_logger(__name__)

# The UniFi integration API accepts only these values on ACL rules.
_VALID_ACTIONS = ("ALLOW", "BLOCK")
_VALID_TYPES = ("IPV4", "MAC")


def _normalise_action(action: str) -> str:
    upper = action.upper()
    if upper not in _VALID_ACTIONS:
        raise ValueError(
            f"Invalid action '{action}'. UniFi integration API accepts only "
            f"{_VALID_ACTIONS}."
        )
    return upper


def _normalise_type(type_value: str) -> str:
    upper = type_value.upper()
    if upper not in _VALID_TYPES:
        raise ValueError(
            f"Invalid type '{type_value}'. UniFi integration API accepts only "
            f"{_VALID_TYPES}."
        )
    return upper


def _warn_deprecated(operation: str, deprecated: dict[str, Any]) -> None:
    """Log a warning when a caller passes parameters that the UniFi integration
    API no longer accepts. Kept in the signature for backwards compatibility."""
    supplied = [name for name, value in deprecated.items() if value is not None]
    if supplied:
        logger.warning(
            sanitize_log_message(
                f"{operation}: parameters {sorted(supplied)} are not accepted by "
                "the UniFi integration API and will be ignored."
            )
        )


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
        logger.info(sanitize_log_message(f"Listing ACL rules for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if filter_expr:
            params["filter"] = filter_expr

        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/acl-rules"),
            params=params,
        )
        data = response if isinstance(response, list) else response.get("data", [])

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
        logger.info(sanitize_log_message(f"Getting ACL rule {acl_rule_id} for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(
                f"sites/{resolved_site_id}/acl-rules/{acl_rule_id}"
            )
        )
        data = response.get("data", response)

        return ACLRule(**data).model_dump()  # type: ignore[no-any-return]


async def create_acl_rule(
    site_id: str,
    name: str,
    action: str,
    settings: Settings,
    type: str = "IPV4",
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
    priority: int | None = None,
    description: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new ACL rule.

    The UniFi integration API accepts only a minimal shape for ACL rule
    creation: ``{name, action, type, enabled}``. The legacy source/destination
    filter parameters (``source_*``, ``destination_*``, ``protocol``,
    ``src_port``, ``dst_port``, ``priority``, ``description``) are kept in the
    signature for backwards compatibility but are ignored by the API and are
    not sent in the request body. A warning is logged if any are passed.

    Args:
        site_id: Site identifier
        name: Rule name
        action: ALLOW or BLOCK (case-insensitive). DROP/REJECT/DENY are not
            accepted by the integration API.
        settings: Application settings
        type: Rule type — IPV4 or MAC. Defaults to IPV4.
        enabled: Whether the rule is enabled (defaults to True)
        source_type: DEPRECATED — not accepted by the integration API.
        source_id: DEPRECATED — not accepted by the integration API.
        source_network: DEPRECATED — not accepted by the integration API.
        destination_type: DEPRECATED — not accepted by the integration API.
        destination_id: DEPRECATED — not accepted by the integration API.
        destination_network: DEPRECATED — not accepted by the integration API.
        protocol: DEPRECATED — not accepted by the integration API.
        src_port: DEPRECATED — not accepted by the integration API.
        dst_port: DEPRECATED — not accepted by the integration API.
        priority: DEPRECATED — not accepted by the integration API.
        description: DEPRECATED — not accepted by the integration API.
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created ACL rule
    """
    validate_confirmation(confirm, "create ACL rule", dry_run)

    normalised_action = _normalise_action(action)
    normalised_type = _normalise_type(type)

    _warn_deprecated(
        "create_acl_rule",
        {
            "source_type": source_type,
            "source_id": source_id,
            "source_network": source_network,
            "destination_type": destination_type,
            "destination_id": destination_id,
            "destination_network": destination_network,
            "protocol": protocol,
            "src_port": src_port,
            "dst_port": dst_port,
            "priority": priority,
            "description": description,
        },
    )

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Creating ACL rule '{name}' for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        payload: dict[str, Any] = {
            "name": name,
            "enabled": enabled,
            "action": normalised_action,
            "type": normalised_type,
        }

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would create ACL rule '{name}' for site {site_id}"
                )
            )
            return {"dry_run": True, "payload": payload}

        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.post(
            settings.get_integration_path(f"sites/{resolved_site_id}/acl-rules"),
            json_data=payload,
        )
        data = response.get("data", response)

        # Audit the action
        await audit_action(
            settings,
            action_type="create_acl_rule",
            resource_type="acl_rule",
            resource_id=data.get("_id", data.get("id", "unknown")),
            site_id=site_id,
            details={"name": name, "action": normalised_action, "type": normalised_type},
        )

        return ACLRule(**data).model_dump()  # type: ignore[no-any-return]


async def update_acl_rule(
    site_id: str,
    acl_rule_id: str,
    settings: Settings,
    name: str | None = None,
    action: str | None = None,
    type: str | None = None,
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
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing ACL rule.

    The UniFi integration API accepts only ``name``, ``action`` (ALLOW/BLOCK),
    ``type`` (IPV4/MAC) and ``enabled`` on ACL rule updates. Legacy filter
    fields are ignored — see :func:`create_acl_rule` for details.

    Args:
        site_id: Site identifier
        acl_rule_id: ACL rule identifier
        settings: Application settings
        name: Rule name
        action: ALLOW or BLOCK (case-insensitive)
        type: Rule type — IPV4 or MAC
        enabled: Whether the rule is enabled
        source_type: DEPRECATED — not accepted by the integration API.
        source_id: DEPRECATED — not accepted by the integration API.
        source_network: DEPRECATED — not accepted by the integration API.
        destination_type: DEPRECATED — not accepted by the integration API.
        destination_id: DEPRECATED — not accepted by the integration API.
        destination_network: DEPRECATED — not accepted by the integration API.
        protocol: DEPRECATED — not accepted by the integration API.
        src_port: DEPRECATED — not accepted by the integration API.
        dst_port: DEPRECATED — not accepted by the integration API.
        priority: DEPRECATED — not accepted by the integration API.
        description: DEPRECATED — not accepted by the integration API.
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Updated ACL rule
    """
    validate_confirmation(confirm, "update ACL rule", dry_run)

    normalised_action = _normalise_action(action) if action is not None else None
    normalised_type = _normalise_type(type) if type is not None else None

    _warn_deprecated(
        "update_acl_rule",
        {
            "source_type": source_type,
            "source_id": source_id,
            "source_network": source_network,
            "destination_type": destination_type,
            "destination_id": destination_id,
            "destination_network": destination_network,
            "protocol": protocol,
            "src_port": src_port,
            "dst_port": dst_port,
            "priority": priority,
            "description": description,
        },
    )

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Updating ACL rule {acl_rule_id} for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if normalised_action is not None:
            payload["action"] = normalised_action
        if normalised_type is not None:
            payload["type"] = normalised_type
        if enabled is not None:
            payload["enabled"] = enabled

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would update ACL rule {acl_rule_id} for site {site_id}"
                )
            )
            return {"dry_run": True, "payload": payload}

        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.put(
            settings.get_integration_path(
                f"sites/{resolved_site_id}/acl-rules/{acl_rule_id}"
            ),
            json_data=payload,
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

        return ACLRule(**data).model_dump()  # type: ignore[no-any-return]


async def delete_acl_rule(
    site_id: str,
    acl_rule_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
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
    validate_confirmation(confirm, "delete ACL rule", dry_run)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Deleting ACL rule {acl_rule_id} for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(sanitize_log_message(f"[DRY RUN] Would delete ACL rule {acl_rule_id}"))
            return {"dry_run": True, "acl_rule_id": acl_rule_id}

        resolved_site_id = await client.resolve_site_id(site_id)
        await client.delete(
            settings.get_integration_path(
                f"sites/{resolved_site_id}/acl-rules/{acl_rule_id}"
            )
        )

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
