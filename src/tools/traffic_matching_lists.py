"""Traffic Matching List management MCP tools."""

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models.traffic_matching_list import (
    TrafficMatchingList,
    TrafficMatchingListCreate,
    TrafficMatchingListUpdate,
)
from ..utils import (
    ResourceNotFoundError,
    ValidationError,
    get_logger,
    log_audit,
    validate_confirmation,
    validate_limit_offset,
    validate_site_id,
)


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

        response = await client.get(f"/integration/v1/sites/{site_id}/traffic-matching-lists")
        lists_data: list[dict[str, Any]] = response.get("data", [])

        # Apply pagination
        paginated = lists_data[offset : offset + limit]

        logger.info(f"Retrieved {len(paginated)} traffic matching lists for site '{site_id}'")
        return [TrafficMatchingList(**lst).model_dump() for lst in paginated]


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

        response = await client.get(
            f"/integration/v1/sites/{site_id}/traffic-matching-lists/{list_id}"
        )

        if isinstance(response, dict) and "data" in response:
            list_data = response["data"]
        else:
            list_data = response

        if not list_data:
            raise ResourceNotFoundError("traffic_matching_list", list_id)

        logger.info(f"Retrieved traffic matching list {list_id}")
        return TrafficMatchingList(**list_data).model_dump()  # type: ignore[no-any-return]


async def create_traffic_matching_list(
    site_id: str,
    list_type: str,
    name: str,
    items: list[str],
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a new traffic matching list.

    Args:
        site_id: Site identifier
        list_type: List type (PORTS, IPV4_ADDRESSES, IPV6_ADDRESSES)
        name: List name
        items: List items (ports, IPs, etc.)
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
    validate_confirmation(confirm, "traffic matching list operation")
    logger = get_logger(__name__, settings.log_level)

    # Validate list type
    valid_types = ["PORTS", "IPV4_ADDRESSES", "IPV6_ADDRESSES"]
    if list_type not in valid_types:
        raise ValidationError(f"Invalid list type '{list_type}'. Must be one of: {valid_types}")

    # Validate items not empty
    if not items or len(items) == 0:
        raise ValidationError("Items list cannot be empty")

    # Build list data
    create_data = TrafficMatchingListCreate(type=list_type, name=name, items=items)

    parameters = {
        "site_id": site_id,
        "type": list_type,
        "name": name,
        "items_count": len(items),
    }

    if dry_run:
        logger.info(f"DRY RUN: Would create traffic matching list '{name}' in site '{site_id}'")
        log_audit(
            operation="create_traffic_matching_list",
            parameters=parameters,
            result="dry_run",
            site_id=site_id,
            dry_run=True,
        )
        return {"dry_run": True, "would_create": create_data.model_dump()}

    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()

            response = await client.post(
                f"/integration/v1/sites/{site_id}/traffic-matching-lists",
                json_data=create_data.model_dump(),
            )
            created_list: dict[str, Any] = response.get("data", response)

            logger.info(f"Created traffic matching list '{name}' in site '{site_id}'")
            log_audit(
                operation="create_traffic_matching_list",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return created_list

    except Exception as e:
        logger.error(f"Failed to create traffic matching list '{name}': {e}")
        log_audit(
            operation="create_traffic_matching_list",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def update_traffic_matching_list(
    site_id: str,
    list_id: str,
    settings: Settings,
    list_type: str | None = None,
    name: str | None = None,
    items: list[str] | None = None,
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Update an existing traffic matching list.

    Args:
        site_id: Site identifier
        list_id: Traffic matching list ID
        settings: Application settings
        list_type: New list type
        name: New list name
        items: New list items
        confirm: Confirmation flag (must be True to execute)
        dry_run: If True, validate but don't update

    Returns:
        Updated list dictionary or dry-run result

    Raises:
        ConfirmationRequiredError: If confirm is not True
        ResourceNotFoundError: If list not found
    """
    site_id = validate_site_id(site_id)
    validate_confirmation(confirm, "traffic matching list operation")
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
        logger.info(f"DRY RUN: Would update traffic matching list '{list_id}' in site '{site_id}'")
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

            # Get existing list
            response = await client.get(
                f"/integration/v1/sites/{site_id}/traffic-matching-lists/{list_id}"
            )
            existing_list = response.get("data", response)

            if not existing_list:
                raise ResourceNotFoundError("traffic_matching_list", list_id)

            # Build update data
            update_data = existing_list.copy()

            if list_type is not None:
                update_data["type"] = list_type
            if name is not None:
                update_data["name"] = name
            if items is not None:
                update_data["items"] = items

            response = await client.put(
                f"/integration/v1/sites/{site_id}/traffic-matching-lists/{list_id}",
                json_data=update_data,
            )
            updated_list: dict[str, Any] = response.get("data", response)

            logger.info(f"Updated traffic matching list '{list_id}' in site '{site_id}'")
            log_audit(
                operation="update_traffic_matching_list",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return updated_list

    except Exception as e:
        logger.error(f"Failed to update traffic matching list '{list_id}': {e}")
        log_audit(
            operation="update_traffic_matching_list",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise


async def delete_traffic_matching_list(
    site_id: str,
    list_id: str,
    settings: Settings,
    confirm: bool = False,
    dry_run: bool = False,
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
    validate_confirmation(confirm, "traffic matching list operation")
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

            # Verify list exists before deleting
            try:
                await client.get(
                    f"/integration/v1/sites/{site_id}/traffic-matching-lists/{list_id}"
                )
            except Exception:
                raise ResourceNotFoundError("traffic_matching_list", list_id)

            response = await client.delete(
                f"/integration/v1/sites/{site_id}/traffic-matching-lists/{list_id}"
            )

            logger.info(f"Deleted traffic matching list '{list_id}' from site '{site_id}'")
            log_audit(
                operation="delete_traffic_matching_list",
                parameters=parameters,
                result="success",
                site_id=site_id,
            )

            return {"success": True, "deleted_list_id": list_id}

    except Exception as e:
        logger.error(f"Failed to delete traffic matching list '{list_id}': {e}")
        log_audit(
            operation="delete_traffic_matching_list",
            parameters=parameters,
            result="failed",
            site_id=site_id,
        )
        raise
