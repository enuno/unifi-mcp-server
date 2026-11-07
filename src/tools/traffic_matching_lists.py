"""Traffic Matching List management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models.traffic_matching_list import (
    TrafficMatchingList,
    TrafficMatchingListCreate,
    normalize_list_items,
)
from ..utils import (
    ResourceNotFoundError,
    ValidationError,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_confirmation,
    validate_limit_offset,
    validate_site_id,
)
from ..utils.tool_kind import read_tool, write_tool


@read_tool
async def list_traffic_matching_lists(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """List all traffic matching lists in a site (read-only).

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of lists to return
        offset: Number of lists to skip

    Returns:
        List of traffic matching list dictionaries
    """
    site_id = validate_site_id(site_id)
    limit, offset = validate_limit_offset(limit, offset)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_integration_path(f"sites/{resolved_site_id}/traffic-matching-lists")
        response = await client.get(endpoint)
        lists_data: list[dict[str, Any]] = (
            response if isinstance(response, list) else response.get("data", [])
        )

        # Apply pagination
        paginated = lists_data[offset : offset + limit]

        logger.info(
            sanitize_log_message(
                f"Retrieved {len(paginated)} traffic matching lists for site '{site_id}'"
            )
        )
        return [
            TrafficMatchingList(**lst).model_dump(mode="json", exclude_none=True)
            for lst in paginated
        ]


@read_tool
async def get_traffic_matching_list(
    site_id: str,
    list_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get details for a specific traffic matching list.

    Args:
        site_id: Site identifier
        list_id: Traffic matching list ID
        settings: Application settings

    Returns:
        Traffic matching list dictionary

    Raises:
        ResourceNotFoundError: If list not found
    """
    site_id = validate_site_id(site_id)
    logger = get_logger(__name__, settings.log_level)

    async with UniFiClient(settings) as client:
        await client.authenticate()

        resolved_site_id = await client.resolve_site_id(site_id)
        endpoint = settings.get_integration_path(
            f"sites/{resolved_site_id}/traffic-matching-lists/{list_id}"
        )
        response = await client.get(endpoint)

        if isinstance(response, dict) and "data" in response:
            list_data = response["data"]
        else:
            list_data = response

        if not list_data:
            raise ResourceNotFoundError("traffic_matching_list", list_id)

        logger.info(sanitize_log_message(f"Retrieved traffic matching list {list_id}"))
        return TrafficMatchingList(**list_data).model_dump(mode="json", exclude_none=True)


@write_tool
async def create_traffic_matching_list(
    site_id: str,
    list_type: str,
    name: str,
    items: list[str | dict[str, Any]],
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a new traffic matching list.

    Items may be plain values (``"80"``, ``"192.168.3.0/24"``) or the
    API's own object shape (``{"type": "PORT_NUMBER", "value": 80}``).
    Plain values are mapped onto the object shape the list type calls
    for: a port for ``PORTS``, and an address or CIDR for the IP lists.

    Args:
        site_id: Site identifier
        list_type: List type (PORTS, IPV4_ADDRESSES, IPV6_ADDRESSES)
        name: List name
        items: List items (ports, IPs, etc.), as values or API-shaped objects
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't create

    Returns:
        Created list dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ValidationError: If validation fails
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "traffic matching list operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    # Validate list type
    valid_types = ["PORTS", "IPV4_ADDRESSES", "IPV6_ADDRESSES"]
    if list_type not in valid_types:
        raise ValidationError(f"Invalid list type '{list_type}'. Must be one of: {valid_types}")

    # Validate items not empty
    if not items or len(items) == 0:
        raise ValidationError("Items list cannot be empty")

    # Map items onto the API's object shape ({type, value}) — the API
    # rejects a bare string with "Missing $.items[0].type value".
    try:
        normalized_items = normalize_list_items(list_type, items)
    except ValueError as e:
        raise ValidationError(str(e)) from e

    # Build list data
    create_data = TrafficMatchingListCreate.model_validate(
        {"type": list_type, "name": name, "items": normalized_items}
    )

    parameters = {
        "site_id": site_id,
        "type": list_type,
        "name": name,
        "items_count": len(items),
    }

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would create traffic matching list '{name}' in site '{site_id}'"
            )
        )
        log_audit(
            operation="create_traffic_matching_list",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {
            "dry_run": True,
            "would_create": create_data.model_dump(mode="json", exclude_none=True),
        }

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            resolved_site_id = await client.resolve_site_id(site_id)
            endpoint = settings.get_integration_path(
                f"sites/{resolved_site_id}/traffic-matching-lists"
            )
            # exclude_none: an item carries either `value` or `start`/`stop`,
            # and the API rejects the unused one as an unknown property
            # ("Unknown request body property '$.items[0].start'").
            response = await client.post(
                endpoint,
                json_data=create_data.model_dump(mode="json", exclude_none=True),
            )
            created_list: dict[str, Any] = (
                response if isinstance(response, list) else response.get("data", response)
            )

            logger.info(
                sanitize_log_message(f"Created traffic matching list '{name}' in site '{site_id}'")
            )
            log_audit(
                operation="create_traffic_matching_list",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return created_list

    except Exception as e:
        logger.error(sanitize_log_message(f"Failed to create traffic matching list '{name}': {e}"))
        log_audit(
            operation="create_traffic_matching_list",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


@write_tool
async def update_traffic_matching_list(
    site_id: str,
    list_id: str,
    settings: Settings,
    list_type: str | None = None,
    name: str | None = None,
    items: list[str | dict[str, Any]] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update an existing traffic matching list.

    Args:
        site_id: Site identifier
        list_id: Traffic matching list ID
        settings: Application settings
        list_type: New list type
        name: New list name
        items: New list items, as values or API-shaped objects
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't update

    Returns:
        Updated list dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If list not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "traffic matching list operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    # Validate list type if provided
    if list_type is not None:
        valid_types = ["PORTS", "IPV4_ADDRESSES", "IPV6_ADDRESSES"]
        if list_type not in valid_types:
            raise ValidationError(f"Invalid list type '{list_type}'. Must be one of: {valid_types}")

    # Validate items if provided
    if items is not None and len(items) == 0:
        raise ValidationError("Items list cannot be empty")

    parameters = {
        "site_id": site_id,
        "list_id": list_id,
        "type": list_type,
        "name": name,
        "items_count": len(items) if items else None,
    }

    if dry_run:
        logger.info(
            sanitize_log_message(
                f"DRY RUN: Would update traffic matching list '{list_id}' in site '{site_id}'"
            )
        )
        log_audit(
            operation="update_traffic_matching_list",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_update": parameters}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            resolved_site_id = await client.resolve_site_id(site_id)

            # Get existing list
            endpoint = settings.get_integration_path(
                f"sites/{resolved_site_id}/traffic-matching-lists/{list_id}"
            )
            response = await client.get(endpoint)
            existing_list = (
                response if isinstance(response, list) else response.get("data", response)
            )

            if not existing_list:
                raise ResourceNotFoundError("traffic_matching_list", list_id)

            # The API accepts type, name and items on a write and rejects
            # anything else ("Unknown request body property '$.id'"), so
            # the body is built from those three rather than copied from
            # the list the controller returned.
            existing = TrafficMatchingList.model_validate(existing_list)
            effective_type = list_type or existing.type
            if not isinstance(effective_type, str):
                raise ValidationError("Cannot determine the list type for the list")

            if items is not None:
                # Map items onto the API's object shape ({type, value}).
                try:
                    update_items = normalize_list_items(effective_type, items)
                except ValueError as e:
                    raise ValidationError(str(e)) from e
            else:
                update_items = [
                    item.model_dump(mode="json", exclude_none=True) for item in existing.items
                ]

            update_data: dict[str, Any] = {
                "type": effective_type,
                "name": name if name is not None else existing.name,
                "items": update_items,
            }

            endpoint = settings.get_integration_path(
                f"sites/{resolved_site_id}/traffic-matching-lists/{list_id}"
            )
            response = await client.put(
                endpoint,
                json_data=update_data,
            )
            updated_list: dict[str, Any] = (
                response if isinstance(response, list) else response.get("data", response)
            )

            logger.info(
                sanitize_log_message(
                    f"Updated traffic matching list '{list_id}' in site '{site_id}'"
                )
            )
            log_audit(
                operation="update_traffic_matching_list",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return updated_list

    except Exception as e:
        logger.error(
            sanitize_log_message(f"Failed to update traffic matching list '{list_id}': {e}")
        )
        log_audit(
            operation="update_traffic_matching_list",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


@write_tool
async def delete_traffic_matching_list(
    site_id: str,
    list_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Delete a traffic matching list.

    Args:
        site_id: Site identifier
        list_id: Traffic matching list ID
        settings: Application settings
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't delete

    Returns:
        Deletion result dictionary

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If list not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "traffic matching list operation", dry_run)
    logger = get_logger(__name__, settings.log_level)

    parameters = {"site_id": site_id, "list_id": list_id}

    if dry_run:
        logger.info(
            f"DRY RUN: Would delete traffic matching list '{list_id}' from site '{site_id}'"
        )
        log_audit(
            operation="delete_traffic_matching_list",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_delete": list_id}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            resolved_site_id = await client.resolve_site_id(site_id)

            # Verify list exists before deleting
            endpoint = settings.get_integration_path(
                f"sites/{resolved_site_id}/traffic-matching-lists/{list_id}"
            )
            try:
                await client.get(endpoint)
            except Exception as err:
                raise ResourceNotFoundError("traffic_matching_list", list_id) from err

            await client.delete(endpoint)

            logger.info(
                sanitize_log_message(
                    f"Deleted traffic matching list '{list_id}' from site '{site_id}'"
                )
            )
            log_audit(
                operation="delete_traffic_matching_list",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {"success": True, "deleted_list_id": list_id}

    except Exception as e:
        logger.error(
            sanitize_log_message(f"Failed to delete traffic matching list '{list_id}': {e}")
        )
        log_audit(
            operation="delete_traffic_matching_list",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
