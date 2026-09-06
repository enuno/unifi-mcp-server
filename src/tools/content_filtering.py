"""Content filtering (CyberSecure) management tools (local v2 API).

Manages UniFi's DNS-based content filtering profiles via the v2 endpoint
``/proxy/network/v2/api/site/{site}/content-filtering``. Each profile
blocks a set of category names (from a fixed list the API provides) and
can be scoped to specific VLANs (``network_ids``) or client MACs.

**Limitation:** the v2 endpoint does **not** support POST (returns 405),
so new profiles cannot be created via this API. The initial profile must
be created in the UniFi Network UI (Settings → Security → Content
Filtering → Create). Once it exists, the MCP can fully manage it: toggle
enabled, change categories, adjust VLAN scope, manage domain allow/block
lists, etc.
"""

from typing import Any

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..utils import (
    APIError,
    ResourceNotFoundError,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_site_id,
)
from ..utils.validators import coerce_bool

logger = get_logger(__name__)


def _ensure_local_api(settings: Settings) -> None:
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError(
            "Content filtering tools require UNIFI_API_TYPE='local'. "
            "The cloud/integration API does not expose content filtering."
        )


async def list_content_filters(
    site_id: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    """List all content filtering profiles.

    Returns:
        List of profile dicts with id, name, enabled, categories,
        network_ids, client_macs, allow_list, block_list, safe_search,
        schedule.
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Listing content filters for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        try:
            normalized_site_id = client._site_uuid_to_name.get(site_id, site_id)
            response = await client.get(
                f"{settings.get_v2_api_path(normalized_site_id)}/content-filtering"
            )
        except APIError:
            logger.exception(
                sanitize_log_message(f"Failed to list content filters for site {site_id}")
            )
            raise

        items = response if isinstance(response, list) else response.get("data", [])
        return [_normalize(item) for item in items if isinstance(item, dict)]


async def list_content_filter_categories(
    site_id: str,
    settings: Settings,
) -> list[str]:
    """List all available content filtering categories.

    Returns the full set of category names (e.g. ``ADVERTISEMENT``,
    ``ADULT``, ``GAMBLING``, ``HACKING``, ...) that can be assigned to a
    content filtering profile's ``categories`` list.
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Listing content filter categories for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        try:
            normalized_site_id = client._site_uuid_to_name.get(site_id, site_id)
            response = await client.get(
                f"{settings.get_v2_api_path(normalized_site_id)}/content-filtering/categories"
            )
        except APIError:
            logger.exception(sanitize_log_message("Failed to list content filter categories"))
            raise

        if isinstance(response, list):
            return [c for c in response if isinstance(c, str)]
        return []


async def update_content_filter(
    filter_id: str,
    site_id: str,
    settings: Settings,
    name: str | None = None,
    enabled: bool | None = None,
    categories: list[str] | None = None,
    network_ids: list[str] | None = None,
    client_macs: list[str] | None = None,
    allow_list: list[str] | None = None,
    block_list: list[str] | None = None,
    safe_search: list[str] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update a content filtering profile.

    The v2 endpoint requires the full object on PUT, so this tool does a
    GET (from the list endpoint) → merge overrides → PUT, same pattern as
    ``update_firewall_policy``.

    Args:
        filter_id: Content filter profile ID
        site_id: Site identifier
        settings: Application settings (must be local)
        name: Profile display name
        enabled: Toggle the profile on/off
        categories: Replace the blocked category list (e.g.
            ``["ADVERTISEMENT", "GAMBLING"]``). Use
            ``list_content_filter_categories`` for the full set.
        network_ids: Replace the VLAN scope (internal network IDs).
            Pass ``[]`` to apply to all networks.
        client_macs: Replace the client-MAC scope. Pass ``[]`` for all
            clients.
        allow_list: Replace the domain allow-list (overrides category
            blocks for these domains)
        block_list: Replace the domain block-list (blocks these domains
            regardless of category)
        safe_search: Replace the safe-search engine list
        confirm: REQUIRED True
        dry_run: Preview without applying
    """
    site_id = validate_site_id(site_id)
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
    if enabled is not None:
        overrides["enabled"] = enabled
    if categories is not None:
        overrides["categories"] = list(categories)
    if network_ids is not None:
        overrides["network_ids"] = list(network_ids)
    if client_macs is not None:
        overrides["client_macs"] = list(client_macs)
    if allow_list is not None:
        overrides["allow_list"] = list(allow_list)
    if block_list is not None:
        overrides["block_list"] = list(block_list)
    if safe_search is not None:
        overrides["safe_search"] = list(safe_search)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Updating content filter {filter_id} for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        # Fetch current state (no single-item GET — list endpoint only).
        normalized_site_id = client._site_uuid_to_name.get(site_id, site_id)
        base = f"{settings.get_v2_api_path(normalized_site_id)}/content-filtering"
        try:
            list_response = await client.get(base)
        except APIError:
            logger.exception(
                sanitize_log_message(f"Failed to fetch content filters for site {site_id}")
            )
            raise

        items = list_response if isinstance(list_response, list) else list_response.get("data", [])
        current = None
        for item in items:
            if isinstance(item, dict) and item.get("_id") == filter_id:
                current = item
                break

        if current is None:
            raise ResourceNotFoundError("content_filter", filter_id)

        merged = {**current, **overrides}
        for field in ("_id",):
            merged.pop(field, None)

        if dry_run_bool:
            logger.info(sanitize_log_message(f"DRY RUN: Would update content filter {filter_id}"))
            return {
                "status": "dry_run",
                "filter_id": filter_id,
                "changes": overrides,
                "merged_payload": merged,
            }

        try:
            response = await client.put(f"{base}/{filter_id}", json_data=merged)
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("content_filter", filter_id) from err

        data = response if isinstance(response, dict) else {}

        log_audit(
            operation="update_content_filter",
            parameters={"site_id": site_id, "filter_id": filter_id, **overrides},
            result="success",
            site_id=site_id,
        )

        return _normalize(data)


async def delete_content_filter(
    filter_id: str,
    site_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Delete a content filtering profile.

    Args:
        filter_id: Content filter profile ID
        site_id: Site identifier
        settings: Application settings (must be local)
        confirm: REQUIRED True
        dry_run: Preview without applying
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)

    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)
    if not dry_run_bool and not confirm_bool:
        raise ValueError(
            "This operation deletes a content filter profile. " "Pass confirm=True to proceed."
        )

    if dry_run_bool:
        logger.info(sanitize_log_message(f"DRY RUN: Would delete content filter {filter_id}"))
        return {"status": "dry_run", "filter_id": filter_id, "action": "would_delete"}

    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(f"Deleting content filter {filter_id} from site {site_id}")
        )
        if not client.is_authenticated:
            await client.authenticate()

        try:
            await client.delete(
                f"{settings.get_v2_api_path(site_id)}/content-filtering/{filter_id}"
            )
        except APIError:
            logger.exception(sanitize_log_message(f"Failed to delete content filter {filter_id}"))
            raise

        log_audit(
            operation="delete_content_filter",
            parameters={"site_id": site_id, "filter_id": filter_id},
            result="success",
            site_id=site_id,
        )

        return {"status": "success", "filter_id": filter_id, "action": "deleted"}


def _normalize(item: dict[str, Any]) -> dict[str, Any]:
    """Extract the standard fields from a content filter profile."""
    return {
        "id": item.get("_id"),
        "name": item.get("name"),
        "enabled": item.get("enabled", False),
        "categories": item.get("categories", []),
        "network_ids": item.get("network_ids", []),
        "client_macs": item.get("client_macs", []),
        "allow_list": item.get("allow_list", []),
        "block_list": item.get("block_list", []),
        "safe_search": item.get("safe_search", []),
        "schedule": item.get("schedule"),
    }
