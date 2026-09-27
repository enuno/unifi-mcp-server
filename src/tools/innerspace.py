"""MCP tools for the UniFi InnerSpace API (Phase 6).

InnerSpace (indoor location/analytics) is read-only via the Cloud Connector
proxy at
``https://api.ui.com/v1/connector/consoles/{console_id}/proxy/innerspace/{path}``
using the same API-key transport as Site Manager, so these tools reuse
:class:`SiteManagerClient`. Requires ``UNIFI_SITE_MANAGER_ENABLED=true``
(the cloud API key must be configured), matching the Cloud Connector tools'
gating. All tools are reads — no confirmation or dry_run handling.
"""

from __future__ import annotations

from typing import Any

from ..api.site_manager_client import SiteManagerClient
from ..config import Settings
from ..models.innerspace import (
    InnerSpaceAccessPoint,
    InnerSpaceFloorPlan,
    InnerSpaceInventoryItem,
    InnerSpaceProject,
    InnerSpaceSwitch,
)
from ..utils import ValidationError, get_logger, sanitize_log_message


def _require_cloud_api(settings: Settings) -> None:
    if not settings.site_manager_enabled:
        raise ValueError(
            "InnerSpace API is a cloud API. Set UNIFI_SITE_MANAGER_ENABLED=true and configure "
            "your UniFi API key."
        )


def _validate_uuid(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValidationError(f"{label} is required")
    return value


def _extract_collection(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        data = response.get("data", [])
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def _extract_item(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        data = response.get("data", response)
        if isinstance(data, dict):
            return data
        return response
    return {}


def _proxy_endpoint(console_id: str, path: str) -> str:
    return f"connector/consoles/{console_id}/proxy/innerspace/integration/{path}"


async def list_innerspace_access_points(
    console_id: str, settings: Settings
) -> dict[str, Any]:
    """List access points known to InnerSpace on a console.

    Args:
        console_id: Cloud Connector console UUID (from ``list_hosts``)
        settings: Application settings

    Raises:
        ValueError: If the cloud API is not enabled or ``console_id`` is empty.
    """
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    console_id = _validate_uuid(console_id, "console_id")

    async with SiteManagerClient(settings) as client:
        response = await client.get(_proxy_endpoint(console_id, "v1/access_points"))

    data = _extract_collection(response)
    access_points = [
        InnerSpaceAccessPoint.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    logger.info(
        sanitize_log_message(
            f"Listed {len(access_points)} InnerSpace access points on console {console_id}"
        )
    )
    return {"console_id": console_id, "count": len(access_points), "data": access_points}


async def list_innerspace_floor_plans(
    console_id: str, settings: Settings
) -> dict[str, Any]:
    """List InnerSpace floor plans on a console.

    Args:
        console_id: Cloud Connector console UUID (from ``list_hosts``)
        settings: Application settings

    Raises:
        ValueError: If the cloud API is not enabled or ``console_id`` is empty.
    """
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    console_id = _validate_uuid(console_id, "console_id")

    async with SiteManagerClient(settings) as client:
        response = await client.get(_proxy_endpoint(console_id, "v1/floor_plans"))

    data = _extract_collection(response)
    floor_plans = [
        InnerSpaceFloorPlan.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    logger.info(
        sanitize_log_message(
            f"Listed {len(floor_plans)} InnerSpace floor plans on console {console_id}"
        )
    )
    return {"console_id": console_id, "count": len(floor_plans), "data": floor_plans}


async def list_innerspace_inventory(
    console_id: str, settings: Settings
) -> dict[str, Any]:
    """List unplaced devices in InnerSpace inventory on a console.

    Args:
        console_id: Cloud Connector console UUID (from ``list_hosts``)
        settings: Application settings

    Raises:
        ValueError: If the cloud API is not enabled or ``console_id`` is empty.
    """
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    console_id = _validate_uuid(console_id, "console_id")

    async with SiteManagerClient(settings) as client:
        response = await client.get(_proxy_endpoint(console_id, "v1/inventory"))

    data = _extract_collection(response)
    inventory = [
        InnerSpaceInventoryItem.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    logger.info(
        sanitize_log_message(
            f"Listed {len(inventory)} InnerSpace inventory items on console {console_id}"
        )
    )
    return {"console_id": console_id, "count": len(inventory), "data": inventory}


async def get_innerspace_project(
    console_id: str, settings: Settings
) -> dict[str, Any]:
    """Get the InnerSpace project data for the integration on a console.

    Args:
        console_id: Cloud Connector console UUID (from ``list_hosts``)
        settings: Application settings

    Raises:
        ValueError: If the cloud API is not enabled or ``console_id`` is empty.
    """
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    console_id = _validate_uuid(console_id, "console_id")

    async with SiteManagerClient(settings) as client:
        response = await client.get(_proxy_endpoint(console_id, "v1/project"))

    project = InnerSpaceProject.model_validate(_extract_item(response))
    logger.info(
        sanitize_log_message(f"Retrieved InnerSpace project on console {console_id}")
    )
    return project.model_dump(by_alias=True)


async def list_innerspace_switches(
    console_id: str, settings: Settings, site_id: str | None = None
) -> dict[str, Any]:
    """List switches placed on InnerSpace floor plans on a console.

    Args:
        console_id: Cloud Connector console UUID (from ``list_hosts``)
        settings: Application settings
        site_id: Optional site UUID to filter switches by site

    Raises:
        ValueError: If the cloud API is not enabled or ``console_id`` is empty.
    """
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    console_id = _validate_uuid(console_id, "console_id")

    params: dict[str, Any] = {}
    if site_id is not None:
        params["siteId"] = site_id

    async with SiteManagerClient(settings) as client:
        response = await client.get(
            _proxy_endpoint(console_id, "v1/switches"),
            params=params or None,
        )

    data = _extract_collection(response)
    switches = [
        InnerSpaceSwitch.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    logger.info(
        sanitize_log_message(
            f"Listed {len(switches)} InnerSpace switches on console {console_id}"
        )
    )
    return {
        "console_id": console_id,
        "site_id": site_id,
        "count": len(switches),
        "data": switches,
    }


async def download_innerspace_asset(
    console_id: str, plan_id: str, filename: str, settings: Settings
) -> dict[str, Any]:
    """Download an asset (e.g. floor plan image) from InnerSpace.

    Args:
        console_id: Cloud Connector console UUID (from ``list_hosts``)
        plan_id: Floor plan identifier
        filename: Asset filename on the floor plan
        settings: Application settings

    Raises:
        ValueError: If the cloud API is not enabled or any identifier is empty.
    """
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    console_id = _validate_uuid(console_id, "console_id")
    plan_id = _validate_uuid(plan_id, "plan_id")
    filename = _validate_uuid(filename, "filename")

    async with SiteManagerClient(settings) as client:
        response = await client.get(
            _proxy_endpoint(console_id, f"v1/assets/{plan_id}/{filename}")
        )

    if isinstance(response, dict):
        content: Any = _extract_item(response)
    else:
        content = {"raw": response}
    logger.info(
        sanitize_log_message(
            f"Downloaded InnerSpace asset {filename} for plan {plan_id} "
            f"on console {console_id}"
        )
    )
    return {"plan_id": plan_id, "filename": filename, "content": content}
