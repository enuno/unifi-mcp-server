"""MCP tools for UniFi Protect device read and settings operations."""

from __future__ import annotations

from typing import Any

from ..api import ProtectClient
from ..config import Settings
from ..models import (
    ProtectChime,
    ProtectDevice,
    ProtectDeviceUpdateMessage,
    ProtectLight,
    ProtectSensor,
)
from ..utils import (
    ValidationError,
    audit_on_failure,
    coerce_bool,
    get_logger,
    log_audit,
    sanitize_log_message,
    validate_confirmation,
    validate_limit_offset,
)


def _validate_id(record_id: str, label: str) -> str:
    record_id = record_id.strip()
    if not record_id:
        raise ValidationError(f"{label} is required")
    return record_id


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


def _prepare_mutation(
    operation: str,
    parameters: dict[str, Any],
    confirm: bool | str,
    dry_run: bool | str,
) -> bool:
    """Enforce confirmation and audit a side-effect-free preview."""
    validate_confirmation(confirm, operation, dry_run)
    is_dry_run = coerce_bool(dry_run)
    if is_dry_run:
        log_audit(
            operation=operation,
            parameters=parameters,
            result="dry_run",
            dry_run=True,
        )
    return is_dry_run


async def list_protect_devices(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect devices."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_protect_integration_path("devices"),
            params={"limit": final_limit, "offset": final_offset},
        )

    devices_data = _extract_collection(response)
    paginated = devices_data[final_offset : final_offset + final_limit]
    devices = [ProtectDevice.model_validate(item).model_dump(by_alias=True) for item in paginated]
    total_count = len(devices_data)
    logger.info(sanitize_log_message(f"Listed {len(devices)} Protect devices"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(devices),
        "totalCount": total_count,
        "data": devices,
    }


async def list_protect_device_updates(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Get Protect device update messages."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path("subscribe/devices"))

    updates_data = _extract_collection(response)
    paginated = updates_data[final_offset : final_offset + final_limit]
    updates = [
        ProtectDeviceUpdateMessage.model_validate(item).model_dump(by_alias=True)
        for item in paginated
    ]
    total_count = len(updates_data)
    logger.info(sanitize_log_message(f"Retrieved {len(updates)} Protect device update messages"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(updates),
        "totalCount": total_count,
        "data": updates,
    }


async def get_protect_device(device_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect device."""
    logger = get_logger(__name__, settings.log_level)
    device_id = _validate_id(device_id, "device_id")

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"devices/{device_id}"))

    device = ProtectDevice.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect device {device_id}"))
    return device.model_dump(by_alias=True)


async def update_protect_device(
    device_id: str,
    settings: Settings,
    name: str | None = None,
    model: str | None = None,
    type: str | None = None,
    state: str | int | None = None,
    mac: str | None = None,
    firmware_version: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update a Protect device record."""
    logger = get_logger(__name__, settings.log_level)
    device_id = _validate_id(device_id, "device_id")

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if model is not None:
        payload["model"] = model
    if type is not None:
        payload["type"] = type
    if state is not None:
        payload["state"] = state
    if mac is not None:
        payload["mac"] = mac
    if firmware_version is not None:
        payload["firmwareVersion"] = firmware_version

    parameters = {"device_id": device_id, "changed_fields": sorted(payload)}
    if _prepare_mutation("update_protect_device", parameters, confirm, dry_run):
        return {"dry_run": True, "would_update": device_id, "changes": payload}

    with audit_on_failure("update_protect_device", parameters):
        async with ProtectClient(settings) as client:
            await client.authenticate()
            response = await client.patch(
                settings.get_protect_integration_path(f"devices/{device_id}"),
                json_data=payload,
            )

        device = ProtectDevice.model_validate(_extract_item(response))
        log_audit(operation="update_protect_device", parameters=parameters, result="success")
        logger.info(sanitize_log_message(f"Updated Protect device {device_id}"))
        return device.model_dump(by_alias=True)


async def list_protect_lights(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect lights."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path("lights"))

    lights_data = _extract_collection(response)
    paginated = lights_data[final_offset : final_offset + final_limit]
    lights = [ProtectLight.model_validate(item).model_dump(by_alias=True) for item in paginated]
    total_count = len(lights_data)
    logger.info(sanitize_log_message(f"Listed {len(lights)} Protect lights"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(lights),
        "totalCount": total_count,
        "data": lights,
    }


async def get_protect_light(light_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect light."""
    logger = get_logger(__name__, settings.log_level)
    light_id = _validate_id(light_id, "light_id")

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"lights/{light_id}"))

    light = ProtectLight.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect light {light_id}"))
    return light.model_dump(by_alias=True)


async def update_protect_light(
    light_id: str,
    settings: Settings,
    name: str | None = None,
    is_light_force_enabled: bool | None = None,
    light_mode_settings: dict[str, Any] | None = None,
    light_device_settings: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect light settings."""
    logger = get_logger(__name__, settings.log_level)
    light_id = _validate_id(light_id, "light_id")

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if is_light_force_enabled is not None:
        payload["isLightForceEnabled"] = is_light_force_enabled
    if light_mode_settings is not None:
        payload["lightModeSettings"] = light_mode_settings
    if light_device_settings is not None:
        payload["lightDeviceSettings"] = light_device_settings

    parameters = {"light_id": light_id, "changed_fields": sorted(payload)}
    if _prepare_mutation("update_protect_light", parameters, confirm, dry_run):
        return {"dry_run": True, "would_update": light_id, "changes": payload}

    with audit_on_failure("update_protect_light", parameters):
        async with ProtectClient(settings) as client:
            await client.authenticate()
            response = await client.patch(
                settings.get_protect_integration_path(f"lights/{light_id}"),
                json_data=payload,
            )

        light = ProtectLight.model_validate(_extract_item(response))
        log_audit(operation="update_protect_light", parameters=parameters, result="success")
        logger.info(sanitize_log_message(f"Updated Protect light {light_id}"))
        return light.model_dump(by_alias=True)


async def list_protect_sensors(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect sensors."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path("sensors"))

    sensors_data = _extract_collection(response)
    paginated = sensors_data[final_offset : final_offset + final_limit]
    sensors = [ProtectSensor.model_validate(item).model_dump(by_alias=True) for item in paginated]
    total_count = len(sensors_data)
    logger.info(sanitize_log_message(f"Listed {len(sensors)} Protect sensors"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(sensors),
        "totalCount": total_count,
        "data": sensors,
    }


async def get_protect_sensor(sensor_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect sensor."""
    logger = get_logger(__name__, settings.log_level)
    sensor_id = _validate_id(sensor_id, "sensor_id")

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"sensors/{sensor_id}"))

    sensor = ProtectSensor.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect sensor {sensor_id}"))
    return sensor.model_dump(by_alias=True)


async def update_protect_sensor(
    sensor_id: str,
    settings: Settings,
    name: str | None = None,
    light_settings: dict[str, Any] | None = None,
    humidity_settings: dict[str, Any] | None = None,
    temperature_settings: dict[str, Any] | None = None,
    motion_settings: dict[str, Any] | None = None,
    alarm_settings: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect sensor settings."""
    logger = get_logger(__name__, settings.log_level)
    sensor_id = _validate_id(sensor_id, "sensor_id")

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if light_settings is not None:
        payload["lightSettings"] = light_settings
    if humidity_settings is not None:
        payload["humiditySettings"] = humidity_settings
    if temperature_settings is not None:
        payload["temperatureSettings"] = temperature_settings
    if motion_settings is not None:
        payload["motionSettings"] = motion_settings
    if alarm_settings is not None:
        payload["alarmSettings"] = alarm_settings

    parameters = {"sensor_id": sensor_id, "changed_fields": sorted(payload)}
    if _prepare_mutation("update_protect_sensor", parameters, confirm, dry_run):
        return {"dry_run": True, "would_update": sensor_id, "changes": payload}

    with audit_on_failure("update_protect_sensor", parameters):
        async with ProtectClient(settings) as client:
            await client.authenticate()
            response = await client.patch(
                settings.get_protect_integration_path(f"sensors/{sensor_id}"),
                json_data=payload,
            )

        sensor = ProtectSensor.model_validate(_extract_item(response))
        log_audit(operation="update_protect_sensor", parameters=parameters, result="success")
        logger.info(sanitize_log_message(f"Updated Protect sensor {sensor_id}"))
        return sensor.model_dump(by_alias=True)


async def list_protect_chimes(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List UniFi Protect chimes."""
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path("chimes"))

    chimes_data = _extract_collection(response)
    paginated = chimes_data[final_offset : final_offset + final_limit]
    chimes = [ProtectChime.model_validate(item).model_dump(by_alias=True) for item in paginated]
    total_count = len(chimes_data)
    logger.info(sanitize_log_message(f"Listed {len(chimes)} Protect chimes"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": len(chimes),
        "totalCount": total_count,
        "data": chimes,
    }


async def get_protect_chime(chime_id: str, settings: Settings) -> dict[str, Any]:
    """Get a single UniFi Protect chime."""
    logger = get_logger(__name__, settings.log_level)
    chime_id = _validate_id(chime_id, "chime_id")

    async with ProtectClient(settings) as client:
        await client.authenticate()
        response = await client.get(settings.get_protect_integration_path(f"chimes/{chime_id}"))

    chime = ProtectChime.model_validate(_extract_item(response))
    logger.info(sanitize_log_message(f"Retrieved Protect chime {chime_id}"))
    return chime.model_dump(by_alias=True)


async def update_protect_chime(
    chime_id: str,
    settings: Settings,
    name: str | None = None,
    camera_ids: list[str] | None = None,
    ring_settings: list[dict[str, Any]] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update Protect chime settings."""
    logger = get_logger(__name__, settings.log_level)
    chime_id = _validate_id(chime_id, "chime_id")

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if camera_ids is not None:
        payload["cameraIds"] = camera_ids
    if ring_settings is not None:
        payload["ringSettings"] = ring_settings

    parameters = {"chime_id": chime_id, "changed_fields": sorted(payload)}
    if _prepare_mutation("update_protect_chime", parameters, confirm, dry_run):
        return {"dry_run": True, "would_update": chime_id, "changes": payload}

    with audit_on_failure("update_protect_chime", parameters):
        async with ProtectClient(settings) as client:
            await client.authenticate()
            response = await client.patch(
                settings.get_protect_integration_path(f"chimes/{chime_id}"),
                json_data=payload,
            )

        chime = ProtectChime.model_validate(_extract_item(response))
        log_audit(operation="update_protect_chime", parameters=parameters, result="success")
        logger.info(sanitize_log_message(f"Updated Protect chime {chime_id}"))
        return chime.model_dump(by_alias=True)
