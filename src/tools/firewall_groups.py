"""Firewall group management tools (local V1 legacy endpoint).

Firewall groups are the reusable match objects that zone-based firewall
policies and legacy firewall rules reference for ports and IP addresses.
They live at the classic V1 internal endpoint
``/proxy/network/api/s/{site}/rest/firewallgroup``, which the UniFi v2
API does not replicate — so this module is **local-gateway only**. The
API key on current UDM firmware authenticates against this legacy surface
just like it does for the v2 firewall-policies endpoint, so no session
login is required.

Three group types exist:

* ``port-group`` — ``group_members`` is a list of port strings. Individual
  ports (``"53"``) and ranges (``"9000-9010"``) are both accepted.
* ``address-group`` — ``group_members`` is a list of IPv4 addresses or
  CIDR blocks.
* ``ipv6-address-group`` — ``group_members`` is a list of IPv6 addresses
  or CIDR blocks.
"""

from typing import Any

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..models.firewall_group import FirewallGroup, FirewallGroupCreate
from ..utils import APIError, ResourceNotFoundError, get_logger, log_audit, sanitize_log_message
from ..utils.validators import coerce_bool

logger = get_logger(__name__)

_VALID_GROUP_TYPES = ("port-group", "address-group", "ipv6-address-group")


def _ensure_local_api(settings: Settings) -> None:
    """Firewall group endpoints live on the local V1 internal API only."""
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError(
            "Firewall group tools require UNIFI_API_TYPE='local'. The UniFi "
            "cloud/integration API does not expose firewall groups; they are "
            "only reachable via the local gateway's legacy "
            "/rest/firewallgroup endpoint."
        )


def _endpoint(site_id: str, group_id: str | None = None) -> str:
    """Build the /ea/sites/... path for the firewall groups REST endpoint.

    The client's auto-translator rewrites this to
    /proxy/network/api/s/{site}/rest/firewallgroup/... in local mode.
    """
    suffix = f"/{group_id}" if group_id else ""
    return f"/ea/sites/{site_id}/rest/firewallgroup{suffix}"


def _unwrap(response: Any) -> list[dict[str, Any]]:
    """Extract a list of items from a `{meta, data: [...]}` response."""
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        inner = response.get("data")
        if isinstance(inner, list):
            return [item for item in inner if isinstance(item, dict)]
        if isinstance(inner, dict):
            return [inner]
    return []


def _first_or_raise(response: Any, group_id: str) -> dict[str, Any]:
    items = _unwrap(response)
    if not items:
        raise ResourceNotFoundError("firewall_group", group_id)
    return items[0]


# --------------------------------------------------------------------------- #
# Read                                                                        #
# --------------------------------------------------------------------------- #


async def list_firewall_groups(
    site_id: str,
    settings: Settings,
    group_type: str | None = None,
) -> list[dict[str, Any]]:
    """List firewall groups on a site.

    Args:
        site_id: Site identifier
        settings: Application settings (must be local)
        group_type: Optional filter — ``port-group`` / ``address-group`` /
            ``ipv6-address-group``. Pass ``None`` to list every group.

    Returns:
        List of firewall group dicts.
    """
    _ensure_local_api(settings)

    if group_type is not None and group_type not in _VALID_GROUP_TYPES:
        raise ValueError(
            f"Invalid group_type '{group_type}'. Must be one of: {list(_VALID_GROUP_TYPES)}"
        )

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Listing firewall groups for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(_endpoint(site_id))
        except APIError:
            logger.exception(
                sanitize_log_message(f"Failed to list firewall groups for site {site_id}")
            )
            raise

        items = _unwrap(response)
        if group_type is not None:
            items = [g for g in items if g.get("group_type") == group_type]
        return [FirewallGroup(**g).model_dump(by_alias=False) for g in items]


async def get_firewall_group(
    group_id: str,
    site_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get a single firewall group by id."""
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Getting firewall group {group_id} for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(_endpoint(site_id, group_id))
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_group", group_id) from err
        except APIError:
            logger.exception(sanitize_log_message(f"Failed to get firewall group {group_id}"))
            raise

        data = _first_or_raise(response, group_id)
        return FirewallGroup(**data).model_dump(by_alias=False)


# --------------------------------------------------------------------------- #
# Create                                                                      #
# --------------------------------------------------------------------------- #


async def create_firewall_group(
    name: str,
    group_type: str,
    group_members: list[str],
    site_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a new firewall group.

    Args:
        name: Display name
        group_type: ``port-group`` / ``address-group`` / ``ipv6-address-group``
        group_members: Members list — ports (``"53"``, ``"9000-9010"``) for
            port-groups; IPv4 addresses / CIDR blocks for address-groups;
            IPv6 for ipv6-address-groups.
        site_id: Site identifier
        settings: Application settings (must be local)
        confirm: REQUIRED True for mutating operations
        dry_run: Preview without applying
    """
    _ensure_local_api(settings)

    if group_type not in _VALID_GROUP_TYPES:
        raise ValueError(
            f"Invalid group_type '{group_type}'. Must be one of: {list(_VALID_GROUP_TYPES)}"
        )
    if not isinstance(group_members, list):
        raise ValueError("group_members must be a list of strings")

    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)
    if not dry_run_bool and not confirm_bool:
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    create_model = FirewallGroupCreate(
        name=name,
        group_type=group_type,
        group_members=list(group_members),
    )
    payload = create_model.model_dump()

    if dry_run_bool:
        logger.info(sanitize_log_message(f"DRY RUN: Would create firewall group '{name}'"))
        return {"status": "dry_run", "payload": payload}

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Creating {group_type} '{name}' for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        response = await client.post(_endpoint(site_id), json_data=payload)
        data = _first_or_raise(response, group_id="<created>")

        log_audit(
            operation="create_firewall_group",
            parameters={"site_id": site_id, "name": name, "group_type": group_type},
            result="success",
            site_id=site_id,
        )
        return FirewallGroup(**data).model_dump(by_alias=False)


async def create_port_group(
    name: str,
    ports: list[str],
    site_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Convenience wrapper to create a port-group.

    ``ports`` accepts individual port strings (``"53"``) and ranges
    (``"9000-9010"``).
    """
    return await create_firewall_group(
        name=name,
        group_type="port-group",
        group_members=ports,
        site_id=site_id,
        settings=settings,
        confirm=confirm,
        dry_run=dry_run,
    )


async def create_address_group(
    name: str,
    addresses: list[str],
    site_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Convenience wrapper to create an IPv4 address-group."""
    return await create_firewall_group(
        name=name,
        group_type="address-group",
        group_members=addresses,
        site_id=site_id,
        settings=settings,
        confirm=confirm,
        dry_run=dry_run,
    )


# --------------------------------------------------------------------------- #
# Update                                                                      #
# --------------------------------------------------------------------------- #


async def update_firewall_group(
    group_id: str,
    site_id: str,
    settings: Settings,
    name: str | None = None,
    group_members: list[str] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update a firewall group by merging overrides with the existing object.

    The legacy V1 ``rest/firewallgroup`` PUT endpoint accepts partial bodies,
    but to match the behaviour of ``update_firewall_policy`` (and to avoid
    future API strictness regressions) this tool does a GET-merge-PUT so
    callers can reason about the final object that will be persisted.

    ``group_members`` replaces the existing members entirely when supplied.
    """
    _ensure_local_api(settings)

    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)
    if not dry_run_bool and not confirm_bool:
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    overrides: dict[str, Any] = {}
    if name is not None:
        overrides["name"] = name
    if group_members is not None:
        if not isinstance(group_members, list):
            raise ValueError("group_members must be a list of strings")
        overrides["group_members"] = list(group_members)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Updating firewall group {group_id} for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        try:
            current_response = await client.get(_endpoint(site_id, group_id))
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_group", group_id) from err

        current = _first_or_raise(current_response, group_id)
        merged = {**current, **overrides}
        # Strip server-controlled fields before PUT.
        for field in ("_id", "site_id", "external_id"):
            merged.pop(field, None)

        if dry_run_bool:
            logger.info(sanitize_log_message(f"DRY RUN: Would update firewall group {group_id}"))
            return {
                "status": "dry_run",
                "group_id": group_id,
                "changes": overrides,
                "merged_payload": merged,
            }

        try:
            response = await client.put(_endpoint(site_id, group_id), json_data=merged)
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_group", group_id) from err

        data = _first_or_raise(response, group_id)
        log_audit(
            operation="update_firewall_group",
            parameters={"site_id": site_id, "group_id": group_id, **overrides},
            result="success",
            site_id=site_id,
        )
        return FirewallGroup(**data).model_dump(by_alias=False)


# --------------------------------------------------------------------------- #
# Delete                                                                      #
# --------------------------------------------------------------------------- #


async def delete_firewall_group(
    group_id: str,
    site_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Delete a firewall group.

    Warning: this tool does not verify that the group is unreferenced. If a
    firewall policy or legacy rule references it, the UniFi controller will
    reject the delete with an error.
    """
    _ensure_local_api(settings)

    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)
    if not dry_run_bool and not confirm_bool:
        raise ValueError("This operation deletes a firewall group. Pass confirm=True to proceed.")

    if dry_run_bool:
        logger.info(sanitize_log_message(f"DRY RUN: Would delete firewall group {group_id}"))
        return {
            "status": "dry_run",
            "group_id": group_id,
            "action": "would_delete",
        }

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Deleting firewall group {group_id} from site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        try:
            await client.delete(_endpoint(site_id, group_id))
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("firewall_group", group_id) from err

        log_audit(
            operation="delete_firewall_group",
            parameters={"site_id": site_id, "group_id": group_id},
            result="success",
            site_id=site_id,
        )
        return {"status": "success", "group_id": group_id, "action": "deleted"}
