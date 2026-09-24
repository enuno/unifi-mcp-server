"""Tagged MAC management tools (local V1 legacy endpoint).

A tag is a named set of device MAC addresses. The controller stores tags at
the classic V1 internal endpoint ``/proxy/network/api/s/{site}/rest/tag`` as
``{"name": ..., "member_table": [mac, ...]}`` and uses them to target WiFi
broadcasts at a subset of access points. The Integration API only lists
device tags (``list_device_tags``); this legacy endpoint is the writable
surface, so this module is **local-gateway only**.

Membership edits are read-modify-write: ``update_mac_tag`` reads the stored
tag, applies ``add_macs``/``remove_macs`` (or a full ``macs`` replacement),
and PUTs the merged object, so an edit never silently drops members that
another client added. Every write compares the stored result against the
request and attaches ``warnings`` when the controller kept something
different.
"""

import re
from typing import Any

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..models.mac_tag import MacTag
from ..utils import (
    APIError,
    DuplicateResourceError,
    ResourceNotFoundError,
    ValidationError,
    first_response_item,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_mac_address,
    validate_site_id,
)
from ..utils.validators import coerce_bool

logger = get_logger(__name__)

_TAG_ID_RE = re.compile(r"^[a-f0-9]{24}$")

# Fields the controller owns; never sent back on a PUT.
_SERVER_FIELDS = ("_id", "site_id")


def _ensure_local_api(settings: Settings) -> None:
    """Tag endpoints live on the local V1 internal API only."""
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError(
            "MAC tag tools require UNIFI_API_TYPE='local'. The UniFi cloud and "
            "Integration APIs do not expose writable tags; they are only "
            "reachable via the local gateway's legacy /rest/tag endpoint."
        )


def _endpoint(site_id: str, tag_id: str | None = None) -> str:
    """Build the /ea/sites/... path for the tag REST endpoint.

    The client's auto-translator rewrites this to
    /proxy/network/api/s/{site}/rest/tag/... in local mode.
    """
    suffix = f"/{tag_id}" if tag_id else ""
    return f"/ea/sites/{site_id}/rest/tag{suffix}"


def _validate_tag_id(tag_id: str) -> str:
    """Validate a tag ID before it reaches a request path."""
    if not isinstance(tag_id, str) or not _TAG_ID_RE.match(tag_id.lower()):
        raise ValidationError(f"Invalid tag ID format: {tag_id!r} (expected 24-hex ObjectId)")
    return tag_id.lower()


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("Tag name cannot be empty")
    return name.strip()


def _normalize_macs(macs: Any, field: str = "macs") -> list[str]:
    """Validate, normalize and de-duplicate MACs, preserving first-seen order."""
    if not isinstance(macs, list):
        raise ValidationError(f"{field} must be a list of MAC address strings")
    normalized: list[str] = []
    for mac in macs:
        if not isinstance(mac, str):
            raise ValidationError(f"Invalid MAC address format: {mac!r}")
        value = validate_mac_address(mac)
        if value not in normalized:
            normalized.append(value)
    return normalized


def _normalize_stored(macs: Any) -> list[str]:
    """Normalize MACs read back from the controller without rejecting odd values."""
    result: list[str] = []
    for mac in macs if isinstance(macs, list) else []:
        try:
            value = validate_mac_address(str(mac))
        except ValidationError:
            value = str(mac).lower()
        if value not in result:
            result.append(value)
    return result


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


def _to_output(raw: dict[str, Any]) -> dict[str, Any]:
    tag = MacTag(**raw)
    data = tag.model_dump(by_alias=False)
    data["member_count"] = tag.member_count
    return data


def _require_confirm(confirm: bool | str, dry_run: bool | str, action: str) -> bool:
    """Enforce the confirm gate and return the coerced dry_run flag."""
    dry_run_bool = coerce_bool(dry_run)
    if not dry_run_bool and not coerce_bool(confirm):
        raise ValueError(
            f"This operation {action}. Pass confirm=True to proceed, "
            "or dry_run=True to preview it first."
        )
    return dry_run_bool


def _member_warnings(requested: list[str], stored: list[str]) -> list[str]:
    """Describe any difference between the requested and stored member lists."""
    warnings: list[str] = []
    missing = [m for m in requested if m not in stored]
    extra = [m for m in stored if m not in requested]
    if missing:
        warnings.append(f"Controller did not store requested MAC(s): {', '.join(missing)}")
    if extra:
        warnings.append(f"Controller stored MAC(s) that were not requested: {', '.join(extra)}")
    return warnings


def _find_by_name(
    tags: list[dict[str, Any]], name: str, exclude_id: str | None = None
) -> dict[str, Any] | None:
    wanted = name.casefold()
    for tag in tags:
        if str(tag.get("name", "")).casefold() == wanted and tag.get("_id") != exclude_id:
            return tag
    return None


async def _open(client: UniFiClient) -> None:
    if not client.is_authenticated:
        await client.authenticate()


async def _get_tag_raw(client: UniFiClient, site_id: str, tag_id: str) -> dict[str, Any]:
    try:
        response = await client.get(_endpoint(site_id, tag_id))
    except ResourceNotFoundError as err:
        raise ResourceNotFoundError("mac_tag", tag_id) from err
    items = _unwrap(response)
    if not items:
        raise ResourceNotFoundError("mac_tag", tag_id)
    return items[0]


# --------------------------------------------------------------------------- #
# Read                                                                        #
# --------------------------------------------------------------------------- #


async def list_mac_tags(site_id: str, settings: Settings) -> list[dict[str, Any]]:
    """List MAC tags on a site with the device MACs assigned to each.

    Args:
        site_id: Site identifier
        settings: Application settings (must be local)

    Returns:
        List of tags: ``id``, ``name``, ``member_table`` (device MACs) and
        ``member_count``.
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Listing MAC tags for site {site_id}"))
        await _open(client)
        try:
            response = await client.get(_endpoint(site_id))
        except APIError:
            logger.exception(sanitize_log_message(f"Failed to list MAC tags for site {site_id}"))
            raise
        return [_to_output(tag) for tag in _unwrap(response)]


async def get_mac_tag(tag_id: str, site_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single MAC tag by ID.

    Args:
        tag_id: Tag ID (24-hex ObjectId, from ``list_mac_tags``)
        site_id: Site identifier
        settings: Application settings (must be local)

    Returns:
        The tag: ``id``, ``name``, ``member_table`` and ``member_count``.
    """
    site_id = validate_site_id(site_id)
    tag_id = _validate_tag_id(tag_id)
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Getting MAC tag {tag_id} for site {site_id}"))
        await _open(client)
        return _to_output(await _get_tag_raw(client, site_id, tag_id))


# --------------------------------------------------------------------------- #
# Create                                                                      #
# --------------------------------------------------------------------------- #


async def create_mac_tag(
    name: str,
    macs: list[str],
    site_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a MAC tag and assign devices to it.

    MACs may use any common separator (``aa:bb:..``, ``AA-BB-..``,
    ``aabb.ccdd.eeff``); they are normalized to lowercase colon form and
    de-duplicated. A tag whose name matches an existing tag
    (case-insensitive) is rejected rather than created as a duplicate.

    Args:
        name: Tag display name
        macs: Device MAC addresses to assign (may be empty)
        site_id: Site identifier
        settings: Application settings (must be local)
        confirm: Must be True to create the tag
        dry_run: Preview the payload without creating anything

    Returns:
        The created tag, with ``warnings`` if the stored members differ from
        the request. ``status: "unconfirmed"`` means the controller accepted
        the write but the tag could not be read back.
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)
    name = _validate_name(name)
    members = _normalize_macs(macs)
    dry_run_bool = _require_confirm(confirm, dry_run, "creates a MAC tag")

    payload = {"name": name, "member_table": members}

    async with UniFiClient(settings) as client:
        await _open(client)
        existing = _unwrap(await client.get(_endpoint(site_id)))
        clash = _find_by_name(existing, name)
        if clash is not None:
            raise DuplicateResourceError("mac_tag", name, str(clash.get("_id", "")))

        if dry_run_bool:
            logger.info(sanitize_log_message(f"DRY RUN: Would create MAC tag '{name}'"))
            return {"status": "dry_run", "payload": payload}

        logger.info(sanitize_log_message(f"Creating MAC tag '{name}' for site {site_id}"))
        response = await client.post(_endpoint(site_id), json_data=payload)
        created = first_response_item(response)
        if not created:
            # Accepted without an echo: find the stored tag by name.
            created = _find_by_name(_unwrap(await client.get(_endpoint(site_id))), name) or {}

        log_audit(
            operation="create_mac_tag",
            parameters={"site_id": site_id, "name": name, "member_count": len(members)},
            result="success",
            site_id=site_id,
        )

        if not created:
            return {
                "status": "unconfirmed",
                "payload": payload,
                "warnings": [
                    "Controller accepted the create but the tag could not be read back; "
                    "check list_mac_tags before retrying."
                ],
            }

        result = _to_output(created)
        warnings = _member_warnings(members, _normalize_stored(created.get("member_table")))
        if warnings:
            for warning in warnings:
                logger.warning(sanitize_log_message(warning))
            result["warnings"] = warnings
        return result


# --------------------------------------------------------------------------- #
# Update                                                                      #
# --------------------------------------------------------------------------- #


async def update_mac_tag(
    tag_id: str,
    site_id: str,
    settings: Settings,
    name: str | None = None,
    macs: list[str] | None = None,
    add_macs: list[str] | None = None,
    remove_macs: list[str] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Rename a MAC tag or change which device MACs carry it.

    Use ``add_macs``/``remove_macs`` for incremental edits; they are applied
    to the tag's current members, so devices added by someone else are kept.
    Use ``macs`` to replace the member list outright (``[]`` clears it);
    ``macs`` cannot be combined with ``add_macs``/``remove_macs``.

    Args:
        tag_id: Tag ID (24-hex ObjectId, from ``list_mac_tags``)
        site_id: Site identifier
        settings: Application settings (must be local)
        name: New display name
        macs: Full replacement member list
        add_macs: MACs to add to the current members
        remove_macs: MACs to remove from the current members
        confirm: Must be True to apply the change
        dry_run: Preview the change without applying it

    Returns:
        The updated tag, with ``warnings`` if the stored members differ from
        the request or a removed MAC was not a member. A dry run returns
        ``changes`` (``added_macs``/``removed_macs``/``name``) and the
        ``merged_payload`` that would be sent.
    """
    site_id = validate_site_id(site_id)
    tag_id = _validate_tag_id(tag_id)
    _ensure_local_api(settings)

    if name is None and macs is None and add_macs is None and remove_macs is None:
        raise ValidationError("Nothing to update: pass name, macs, add_macs or remove_macs.")
    if macs is not None and (add_macs is not None or remove_macs is not None):
        raise ValidationError(
            "Pass either macs (full replacement) or add_macs/remove_macs, not both."
        )

    new_name = _validate_name(name) if name is not None else None
    replace = _normalize_macs(macs) if macs is not None else None
    to_add = _normalize_macs(add_macs, "add_macs") if add_macs is not None else []
    to_remove = _normalize_macs(remove_macs, "remove_macs") if remove_macs is not None else []
    overlap = [m for m in to_add if m in to_remove]
    if overlap:
        raise ValidationError(f"MAC(s) in both add_macs and remove_macs: {', '.join(overlap)}")

    dry_run_bool = _require_confirm(confirm, dry_run, "modifies a MAC tag")

    async with UniFiClient(settings) as client:
        await _open(client)
        current = await _get_tag_raw(client, site_id, tag_id)
        current_members = _normalize_stored(current.get("member_table"))

        warnings: list[str] = []
        if replace is not None:
            members = replace
        else:
            not_members = [m for m in to_remove if m not in current_members]
            if not_members:
                warnings.append(
                    f"Nothing to remove, not a member of this tag: {', '.join(not_members)}"
                )
            members = [m for m in current_members if m not in to_remove]
            members += [m for m in to_add if m not in members]

        if new_name is not None and new_name.casefold() != str(current.get("name", "")).casefold():
            clash = _find_by_name(_unwrap(await client.get(_endpoint(site_id))), new_name, tag_id)
            if clash is not None:
                raise DuplicateResourceError("mac_tag", new_name, str(clash.get("_id", "")))

        merged = {**current, "member_table": members}
        if new_name is not None:
            merged["name"] = new_name
        for field in _SERVER_FIELDS:
            merged.pop(field, None)

        changes: dict[str, Any] = {
            "added_macs": [m for m in members if m not in current_members],
            "removed_macs": [m for m in current_members if m not in members],
        }
        if new_name is not None:
            changes["name"] = new_name

        if dry_run_bool:
            logger.info(sanitize_log_message(f"DRY RUN: Would update MAC tag {tag_id}"))
            preview: dict[str, Any] = {
                "status": "dry_run",
                "tag_id": tag_id,
                "changes": changes,
                "merged_payload": merged,
            }
            if warnings:
                preview["warnings"] = warnings
            return preview

        logger.info(sanitize_log_message(f"Updating MAC tag {tag_id} for site {site_id}"))
        try:
            response = await client.put(_endpoint(site_id, tag_id), json_data=merged)
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("mac_tag", tag_id) from err

        updated = first_response_item(response)
        if not updated:
            updated = await _get_tag_raw(client, site_id, tag_id)

        log_audit(
            operation="update_mac_tag",
            parameters={"site_id": site_id, "tag_id": tag_id, **changes},
            result="success",
            site_id=site_id,
        )

        warnings += _member_warnings(members, _normalize_stored(updated.get("member_table")))
        result = _to_output(updated)
        if warnings:
            for warning in warnings:
                logger.warning(sanitize_log_message(warning))
            result["warnings"] = warnings
        return result


# --------------------------------------------------------------------------- #
# Delete                                                                      #
# --------------------------------------------------------------------------- #


async def delete_mac_tag(
    tag_id: str,
    site_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Delete a MAC tag.

    Deleting a tag removes it from every device; a WLAN that broadcasts only
    on this tag's access points may stop broadcasting.

    Args:
        tag_id: Tag ID (24-hex ObjectId, from ``list_mac_tags``)
        site_id: Site identifier
        settings: Application settings (must be local)
        confirm: Must be True to delete the tag
        dry_run: Preview without deleting
    """
    site_id = validate_site_id(site_id)
    tag_id = _validate_tag_id(tag_id)
    _ensure_local_api(settings)
    dry_run_bool = _require_confirm(confirm, dry_run, "deletes a MAC tag")

    if dry_run_bool:
        logger.info(sanitize_log_message(f"DRY RUN: Would delete MAC tag {tag_id}"))
        return {"status": "dry_run", "tag_id": tag_id, "action": "would_delete"}

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Deleting MAC tag {tag_id} from site {site_id}"))
        await _open(client)
        try:
            await client.delete(_endpoint(site_id, tag_id))
        except ResourceNotFoundError as err:
            raise ResourceNotFoundError("mac_tag", tag_id) from err

        log_audit(
            operation="delete_mac_tag",
            parameters={"site_id": site_id, "tag_id": tag_id},
            result="success",
            site_id=site_id,
        )
        return {"status": "success", "tag_id": tag_id, "action": "deleted"}
