"""MCP tools for the UniFi Carrier Fabric API (Phase 6).

Carrier Fabric is a cloud API on ``https://api.ui.com/v1/carrier/...`` using
the same API-key transport as Site Manager, so these tools reuse
:class:`SiteManagerClient` rather than adding a new transport. Requires
``UNIFI_SITE_MANAGER_ENABLED=true`` (the cloud API key must be configured),
matching the Cloud Connector tools' gating.
"""

from __future__ import annotations

from typing import Any

from ..api.site_manager_client import SiteManagerClient
from ..config import Settings
from ..models.carrier import CarrierServicePlan, CarrierSubscriber
from ..utils import ValidationError, get_logger, sanitize_log_message, validate_limit_offset
from ..utils.validators import coerce_bool, validate_confirmation


def _require_cloud_api(settings: Settings) -> None:
    if not settings.site_manager_enabled:
        raise ValueError(
            "Carrier Fabric API is a cloud API. Set UNIFI_SITE_MANAGER_ENABLED=true and "
            "configure your UniFi API key."
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


# ── service plans ────────────────────────────────────────────────────


async def list_carrier_service_plans(settings: Settings) -> dict[str, Any]:
    """List UniFi Carrier Fabric service plans.

    Args:
        settings: Application settings

    Returns:
        Dictionary with ``count`` and ``data`` (list of service plans)
    """
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)

    async with SiteManagerClient(settings) as client:
        response = await client.get("carrier/service-plans")

    data = _extract_collection(response)
    plans = [CarrierServicePlan.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(sanitize_log_message(f"Listed {len(plans)} Carrier service plans"))
    return {"count": len(plans), "data": plans}


async def get_carrier_service_plan(plan_id: str, settings: Settings) -> dict[str, Any]:
    """Get a UniFi Carrier Fabric service plan by ID.

    Args:
        plan_id: Service plan identifier
        settings: Application settings

    Returns:
        The service plan as a dictionary
    """
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    plan_id = _validate_uuid(plan_id, "plan_id")

    async with SiteManagerClient(settings) as client:
        response = await client.get(f"carrier/service-plans/{plan_id}")

    plan = CarrierServicePlan.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Carrier service plan {plan_id}"))
    return plan.model_dump(by_alias=True)


# ── subscribers ──────────────────────────────────────────────────────


async def list_carrier_subscribers(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
    plan_id: str | None = None,
    suspended: bool | None = None,
) -> dict[str, Any]:
    """List UniFi Carrier Fabric subscribers.

    Args:
        settings: Application settings
        limit: Maximum number of items to return
        offset: Number of items to skip
        plan_id: Filter by assigned service plan ID
        suspended: Filter by suspended state

    Returns:
        Dictionary with pagination info and ``data`` (list of subscribers)
    """
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    params: dict[str, Any] = {"limit": final_limit, "offset": final_offset}
    if plan_id is not None:
        params["planId"] = plan_id
    if suspended is not None:
        params["suspended"] = suspended

    async with SiteManagerClient(settings) as client:
        response = await client.get("carrier/subscribers", params=params)

    data = _extract_collection(response)
    subscribers = [
        CarrierSubscriber.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    logger.info(sanitize_log_message(f"Listed {len(subscribers)} Carrier subscribers"))
    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(subscribers),
        "data": subscribers,
    }


async def create_carrier_subscriber(
    settings: Settings,
    subscriber_number: str,
    name: str | None = None,
    email: str | None = None,
    notes: str | None = None,
    service_address: str | None = None,
    plan_id: str | None = None,
    host_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a UniFi Carrier Fabric subscriber.

    Args:
        settings: Application settings
        subscriber_number: Operator-supplied external reference (1-32 characters, required)
        name: Display name
        email: Contact email
        notes: Operator notes
        service_address: Free-text service address
        plan_id: Service plan to assign
        host_id: Gateway host to attach
        metadata: Free-form metadata dictionary
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The created subscriber as a dictionary
    """
    validate_confirmation(confirm, "create Carrier subscriber", dry_run)
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)

    subscriber_number = subscriber_number.strip()
    if not 1 <= len(subscriber_number) <= 32:
        raise ValidationError("subscriber_number must be between 1 and 32 characters")

    payload: dict[str, Any] = {"subscriberNumber": subscriber_number}
    if name is not None:
        payload["name"] = name
    if email is not None:
        payload["email"] = email
    if notes is not None:
        payload["notes"] = notes
    if service_address is not None:
        payload["serviceAddress"] = service_address
    if plan_id is not None:
        payload["planId"] = plan_id
    if host_id is not None:
        payload["hostId"] = host_id
    if metadata is not None:
        payload["metadata"] = metadata

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "create_carrier_subscriber",
            "payload": payload,
        }

    async with SiteManagerClient(settings) as client:
        response = await client.post("carrier/subscribers", json_data=payload)

    subscriber = CarrierSubscriber.model_validate(_extract_item(response))
    logger.info(
        sanitize_log_message(f"Created Carrier subscriber {subscriber_number}")
    )
    return subscriber.model_dump(by_alias=True)


async def get_carrier_subscriber(subscriber_id: str, settings: Settings) -> dict[str, Any]:
    """Get a UniFi Carrier Fabric subscriber by ID.

    Args:
        subscriber_id: Subscriber identifier
        settings: Application settings

    Returns:
        The subscriber as a dictionary
    """
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    subscriber_id = _validate_uuid(subscriber_id, "subscriber_id")

    async with SiteManagerClient(settings) as client:
        response = await client.get(f"carrier/subscribers/{subscriber_id}")

    subscriber = CarrierSubscriber.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Carrier subscriber {subscriber_id}"))
    return subscriber.model_dump(by_alias=True)


async def update_carrier_subscriber(
    subscriber_id: str,
    settings: Settings,
    name: str | None = None,
    email: str | None = None,
    notes: str | None = None,
    service_address: str | None = None,
    plan_id: str | None = None,
    host_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update a UniFi Carrier Fabric subscriber.

    Only provided fields are sent to the API. Spec semantics: an absent field
    leaves it unchanged, while an explicit null clears the field. This tool
    only sends provided fields, so use plan_id="" style clearing via direct
    API if ever needed.

    Args:
        subscriber_id: Subscriber identifier
        settings: Application settings
        name: Display name
        email: Contact email
        notes: Operator notes
        service_address: Free-text service address
        plan_id: Service plan to assign
        host_id: Gateway host to attach
        metadata: Free-form metadata dictionary
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated subscriber as a dictionary
    """
    validate_confirmation(confirm, "update Carrier subscriber", dry_run)
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    subscriber_id = _validate_uuid(subscriber_id, "subscriber_id")

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if email is not None:
        payload["email"] = email
    if notes is not None:
        payload["notes"] = notes
    if service_address is not None:
        payload["serviceAddress"] = service_address
    if plan_id is not None:
        payload["planId"] = plan_id
    if host_id is not None:
        payload["hostId"] = host_id
    if metadata is not None:
        payload["metadata"] = metadata

    if not payload:
        raise ValidationError("No updates provided")

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_carrier_subscriber",
            "subscriber_id": subscriber_id,
            "payload": payload,
        }

    async with SiteManagerClient(settings) as client:
        response = await client.patch(f"carrier/subscribers/{subscriber_id}", json_data=payload)

    subscriber = CarrierSubscriber.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Updated Carrier subscriber {subscriber_id}"))
    return subscriber.model_dump(by_alias=True)


async def attach_carrier_subscriber_host(
    subscriber_id: str,
    settings: Settings,
    host_id: str,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Attach a gateway host to a UniFi Carrier Fabric subscriber.

    Args:
        subscriber_id: Subscriber identifier
        settings: Application settings
        host_id: Gateway host identifier (required)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated subscriber as a dictionary
    """
    validate_confirmation(confirm, "attach host to Carrier subscriber", dry_run)
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    subscriber_id = _validate_uuid(subscriber_id, "subscriber_id")
    host_id = _validate_uuid(host_id, "host_id")

    payload = {"hostId": host_id}
    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "attach_carrier_subscriber_host",
            "subscriber_id": subscriber_id,
            "payload": payload,
        }

    async with SiteManagerClient(settings) as client:
        response = await client.put(
            f"carrier/subscribers/{subscriber_id}/host", json_data=payload
        )

    subscriber = CarrierSubscriber.model_validate(_extract_item(response))
    logger.info(
        sanitize_log_message(f"Attached host {host_id} to Carrier subscriber {subscriber_id}")
    )
    return subscriber.model_dump(by_alias=True)


async def detach_carrier_subscriber_host(
    subscriber_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Detach the gateway host from a UniFi Carrier Fabric subscriber.

    Args:
        subscriber_id: Subscriber identifier
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated subscriber as a dictionary
    """
    validate_confirmation(confirm, "detach host from Carrier subscriber", dry_run)
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    subscriber_id = _validate_uuid(subscriber_id, "subscriber_id")

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "detach_carrier_subscriber_host",
            "subscriber_id": subscriber_id,
        }

    async with SiteManagerClient(settings) as client:
        response = await client.delete(f"carrier/subscribers/{subscriber_id}/host")

    subscriber = CarrierSubscriber.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Detached host from Carrier subscriber {subscriber_id}"))
    return subscriber.model_dump(by_alias=True)


async def assign_carrier_subscriber_plan(
    subscriber_id: str,
    settings: Settings,
    plan_id: str,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Assign a service plan to a UniFi Carrier Fabric subscriber.

    Args:
        subscriber_id: Subscriber identifier
        settings: Application settings
        plan_id: Service plan identifier (required)
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated subscriber as a dictionary
    """
    validate_confirmation(confirm, "assign plan to Carrier subscriber", dry_run)
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    subscriber_id = _validate_uuid(subscriber_id, "subscriber_id")
    plan_id = _validate_uuid(plan_id, "plan_id")

    payload = {"planId": plan_id}
    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "assign_carrier_subscriber_plan",
            "subscriber_id": subscriber_id,
            "payload": payload,
        }

    async with SiteManagerClient(settings) as client:
        response = await client.put(
            f"carrier/subscribers/{subscriber_id}/plan", json_data=payload
        )

    subscriber = CarrierSubscriber.model_validate(_extract_item(response))
    logger.info(
        sanitize_log_message(f"Assigned plan {plan_id} to Carrier subscriber {subscriber_id}")
    )
    return subscriber.model_dump(by_alias=True)


async def resume_carrier_subscriber(
    subscriber_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Resume a suspended UniFi Carrier Fabric subscriber.

    Args:
        subscriber_id: Subscriber identifier
        settings: Application settings
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated subscriber as a dictionary
    """
    validate_confirmation(confirm, "resume Carrier subscriber", dry_run)
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    subscriber_id = _validate_uuid(subscriber_id, "subscriber_id")

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "resume_carrier_subscriber",
            "subscriber_id": subscriber_id,
        }

    async with SiteManagerClient(settings) as client:
        response = await client.post(f"carrier/subscribers/{subscriber_id}/resume")

    subscriber = CarrierSubscriber.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Resumed Carrier subscriber {subscriber_id}"))
    return subscriber.model_dump(by_alias=True)


async def suspend_carrier_subscriber(
    subscriber_id: str,
    settings: Settings,
    reason: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Suspend a UniFi Carrier Fabric subscriber.

    Args:
        subscriber_id: Subscriber identifier
        settings: Application settings
        reason: Optional suspension reason
        confirm: Must be true to apply the change (required unless dry_run)
        dry_run: Preview the change without applying it

    Returns:
        The updated subscriber as a dictionary
    """
    validate_confirmation(confirm, "suspend Carrier subscriber", dry_run)
    _require_cloud_api(settings)
    logger = get_logger(__name__, settings.log_level)
    subscriber_id = _validate_uuid(subscriber_id, "subscriber_id")

    payload: dict[str, Any] = {}
    if reason is not None:
        payload["reason"] = reason

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "suspend_carrier_subscriber",
            "subscriber_id": subscriber_id,
            "payload": payload,
        }

    async with SiteManagerClient(settings) as client:
        if payload:
            response = await client.post(
                f"carrier/subscribers/{subscriber_id}/suspend", json_data=payload
            )
        else:
            response = await client.post(f"carrier/subscribers/{subscriber_id}/suspend")

    subscriber = CarrierSubscriber.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Suspended Carrier subscriber {subscriber_id}"))
    return subscriber.model_dump(by_alias=True)
