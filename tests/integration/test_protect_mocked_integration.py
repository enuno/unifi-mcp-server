"""Mocked integration tests for the Protect client, tools, and resources."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.config import Settings
from src.resources.protect import ProtectResource
from src.tools.protect_cameras import get_protect_camera, list_protect_cameras
from src.tools.protect_devices import (
    get_protect_chime,
    get_protect_device,
    get_protect_light,
    get_protect_sensor,
    list_protect_chimes,
    list_protect_devices,
    list_protect_lights,
    list_protect_sensors,
    update_protect_chime,
    update_protect_device,
    update_protect_light,
    update_protect_sensor,
)
from src.tools.protect_events import (
    list_protect_device_updates,
    list_protect_events,
    send_protect_alarm_webhook,
)
from src.tools.protect_nvr import get_protect_nvr, list_protect_nvrs
from src.tools.protect_views import (
    create_protect_live_view,
    get_protect_live_view,
    get_protect_meta_info,
    get_protect_viewer,
    list_protect_live_views,
    list_protect_viewers,
    update_protect_live_view,
    update_protect_viewer,
)


class ProtectMockTransport:
    """Simple route table for mocking httpx AsyncClient requests."""

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], tuple[int, Any]] = {}
        self.requests: list[dict[str, Any]] = []

    def add(self, method: str, path: str, payload: Any, status_code: int = 200) -> None:
        """Register a mocked response for an HTTP method and path."""
        self.routes[(method.upper(), path)] = (status_code, payload)

    async def request(
        self,
        _client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Return a mocked httpx response for the requested path."""
        path = httpx.URL(url).path
        self.requests.append(
            {
                "method": method.upper(),
                "path": path,
                "params": params,
                "json": json,
            }
        )

        status_code, payload = self.routes[(method.upper(), path)]
        return httpx.Response(
            status_code=status_code,
            request=httpx.Request(method.upper(), url, params=params),
            json=payload,
        )

    def last_request(self, method: str, path: str) -> dict[str, Any]:
        """Return the most recent recorded request for an HTTP method and path."""
        for request in reversed(self.requests):
            if request["method"] == method.upper() and request["path"] == path:
                return request
        raise AssertionError(f"No request recorded for {method.upper()} {path}")


@pytest.fixture
def local_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create real Settings for local Protect integration path tests."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "unifi.local")
    monkeypatch.setenv("UNIFI_LOCAL_VERIFY_SSL", "false")
    return Settings()


@pytest.fixture
def protect_transport(monkeypatch: pytest.MonkeyPatch) -> ProtectMockTransport:
    """Patch httpx so ProtectClient uses mocked responses."""
    transport = ProtectMockTransport()
    transport.add(
        "GET",
        "/proxy/protect/integration/v1/cameras",
        {
            "count": 2,
            "totalCount": 2,
            "data": [
                {"id": "cam-1", "name": "Front Door", "model": "G4 Pro", "isRecording": True},
                {"id": "cam-2", "name": "Garage", "model": "G5 Bullet", "isRecording": False},
            ],
        },
    )

    async def fake_request(
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await transport.request(client, method, url, params=params, json=json)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    return transport


@pytest.mark.integration
@pytest.mark.asyncio
async def test_protect_camera_tools_and_resources_share_real_client_flow(
    local_settings: Settings,
    protect_transport: ProtectMockTransport,
) -> None:
    """Protect camera tools and resources should use the local Protect path."""
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/cameras/cam-1",
        {"data": {"id": "cam-1", "name": "Front Door", "model": "G4 Pro", "isRecording": True}},
    )

    tool_result = await list_protect_cameras(local_settings, limit=1, offset=0)
    camera_result = await get_protect_camera("cam-1", local_settings)
    resource = ProtectResource(local_settings)
    resource_list = await resource.list_cameras()
    resource_camera = await resource.get_camera("cam-1")

    assert tool_result["count"] == 2
    assert tool_result["data"][0]["id"] == "cam-1"
    assert camera_result["name"] == "Front Door"
    assert [camera.id for camera in resource_list] == ["cam-1", "cam-2"]
    assert resource_camera is not None
    assert resource_camera.id == "cam-1"

    assert any(
        request["method"] == "GET"
        and request["path"] == "/proxy/protect/integration/v1/cameras"
        and request["params"] == {"limit": 1, "offset": 0}
        for request in protect_transport.requests
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_protect_nvr_tools_and_resources_use_local_proxy_paths(
    local_settings: Settings,
    protect_transport: ProtectMockTransport,
) -> None:
    """Protect NVR tools and resources should use the local proxy endpoints."""
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/nvrs",
        {
            "count": 1,
            "totalCount": 1,
            "data": [{"id": "nvr-1", "name": "Main NVR", "model": "UNVR"}],
        },
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/nvrs/nvr-1",
        {"data": {"id": "nvr-1", "name": "Main NVR", "model": "UNVR"}},
    )

    tool_result = await list_protect_nvrs(local_settings)
    nvr_result = await get_protect_nvr("nvr-1", local_settings)
    resource = ProtectResource(local_settings)
    resource_list = await resource.list_nvrs()
    resource_nvr = await resource.get_nvr("nvr-1")

    assert tool_result["count"] == 1
    assert nvr_result["id"] == "nvr-1"
    assert [nvr.id for nvr in resource_list] == ["nvr-1"]
    assert resource_nvr is not None
    assert resource_nvr.name == "Main NVR"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_protect_device_family_tools_cover_devices_lights_sensors_and_chimes(
    local_settings: Settings,
    protect_transport: ProtectMockTransport,
) -> None:
    """Device-family tools should parse and write through the Protect proxy surface."""
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/devices",
        {
            "data": [
                {"id": "device-1", "name": "Camera Hub", "model": "Hub", "type": "hub"},
                {"id": "device-2", "name": "Doorbell", "model": "G4 Doorbell", "type": "camera"},
            ]
        },
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/devices/device-1",
        {"data": {"id": "device-1", "name": "Camera Hub", "model": "Hub", "type": "hub"}},
    )
    protect_transport.add(
        "PATCH",
        "/proxy/protect/integration/v1/devices/device-1",
        {"data": {"id": "device-1", "name": "Updated Hub", "model": "Hub", "type": "hub"}},
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/lights",
        {
            "data": [
                {
                    "id": "light-1",
                    "name": "Porch Light",
                    "isLightForceEnabled": False,
                }
            ]
        },
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/lights/light-1",
        {"data": {"id": "light-1", "name": "Porch Light", "isLightForceEnabled": False}},
    )
    protect_transport.add(
        "PATCH",
        "/proxy/protect/integration/v1/lights/light-1",
        {"data": {"id": "light-1", "name": "Night Light", "isLightForceEnabled": True}},
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/sensors",
        {"data": [{"id": "sensor-1", "name": "Garage Sensor"}]},
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/sensors/sensor-1",
        {"data": {"id": "sensor-1", "name": "Garage Sensor"}},
    )
    protect_transport.add(
        "PATCH",
        "/proxy/protect/integration/v1/sensors/sensor-1",
        {
            "data": {
                "id": "sensor-1",
                "name": "Updated Garage Sensor",
                "motionSettings": {"isEnabled": True},
            }
        },
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/chimes",
        {"data": [{"id": "chime-1", "name": "Front Chime", "cameraIds": ["cam-1"]}]},
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/chimes/chime-1",
        {"data": {"id": "chime-1", "name": "Front Chime", "cameraIds": ["cam-1"]}},
    )
    protect_transport.add(
        "PATCH",
        "/proxy/protect/integration/v1/chimes/chime-1",
        {"data": {"id": "chime-1", "name": "Updated Chime", "cameraIds": ["cam-1"]}},
    )

    devices = await list_protect_devices(local_settings, limit=1, offset=0)
    device = await get_protect_device("device-1", local_settings)
    updated_device = await update_protect_device(
        "device-1", local_settings, name="Updated Hub", confirm=True
    )
    lights = await list_protect_lights(local_settings)
    light = await get_protect_light("light-1", local_settings)
    updated_light = await update_protect_light(
        "light-1",
        local_settings,
        name="Night Light",
        is_light_force_enabled=True,
        confirm=True,
    )
    sensors = await list_protect_sensors(local_settings)
    sensor = await get_protect_sensor("sensor-1", local_settings)
    updated_sensor = await update_protect_sensor(
        "sensor-1",
        local_settings,
        name="Updated Garage Sensor",
        motion_settings={"isEnabled": True},
        confirm=True,
    )
    chimes = await list_protect_chimes(local_settings)
    chime = await get_protect_chime("chime-1", local_settings)
    updated_chime = await update_protect_chime(
        "chime-1",
        local_settings,
        name="Updated Chime",
        camera_ids=["cam-1"],
        confirm=True,
    )

    assert devices["count"] == 1
    assert device["id"] == "device-1"
    assert updated_device["name"] == "Updated Hub"
    assert lights["data"][0]["id"] == "light-1"
    assert light["name"] == "Porch Light"
    assert updated_light["isLightForceEnabled"] is True
    assert sensors["data"][0]["id"] == "sensor-1"
    assert sensor["name"] == "Garage Sensor"
    assert updated_sensor["motionSettings"]["isEnabled"] is True
    assert chimes["data"][0]["id"] == "chime-1"
    assert chime["cameraIds"] == ["cam-1"]
    assert updated_chime["name"] == "Updated Chime"

    assert protect_transport.last_request(
        "PATCH",
        "/proxy/protect/integration/v1/devices/device-1",
    )["json"] == {"name": "Updated Hub"}
    assert protect_transport.last_request(
        "PATCH",
        "/proxy/protect/integration/v1/lights/light-1",
    )[
        "json"
    ] == {"name": "Night Light", "isLightForceEnabled": True}
    assert protect_transport.last_request(
        "PATCH",
        "/proxy/protect/integration/v1/sensors/sensor-1",
    )["json"] == {"name": "Updated Garage Sensor", "motionSettings": {"isEnabled": True}}
    assert protect_transport.last_request(
        "PATCH",
        "/proxy/protect/integration/v1/chimes/chime-1",
    )[
        "json"
    ] == {"name": "Updated Chime", "cameraIds": ["cam-1"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_protect_views_events_and_webhooks_cover_the_registered_phase_three_surface(
    local_settings: Settings,
    protect_transport: ProtectMockTransport,
) -> None:
    """View, event, and webhook tools should use the documented Protect endpoints."""
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/meta/info",
        {"data": {"name": "Protect", "version": "6.2.83", "model": "UNVR"}},
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/viewers",
        {"data": [{"id": "viewer-1", "name": "Lobby Viewer", "liveview": "liveview-1"}]},
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/viewers/viewer-1",
        {"data": {"id": "viewer-1", "name": "Lobby Viewer", "liveview": "liveview-1"}},
    )
    protect_transport.add(
        "PATCH",
        "/proxy/protect/integration/v1/viewers/viewer-1",
        {"data": {"id": "viewer-1", "name": "North Lobby Viewer", "liveview": "liveview-1"}},
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/liveviews",
        {
            "data": [
                {
                    "id": "liveview-1",
                    "name": "Default View",
                    "isDefault": True,
                    "layout": 1,
                    "slots": [],
                }
            ]
        },
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/liveviews/liveview-1",
        {
            "data": {
                "id": "liveview-1",
                "name": "Default View",
                "isDefault": True,
                "layout": 1,
                "slots": [],
            }
        },
    )
    protect_transport.add(
        "POST",
        "/proxy/protect/integration/v1/liveviews",
        {
            "data": {
                "id": "liveview-2",
                "name": "Warehouse View",
                "modelKey": "liveview",
                "layout": 4,
                "slots": [],
            }
        },
    )
    protect_transport.add(
        "PATCH",
        "/proxy/protect/integration/v1/liveviews/liveview-1",
        {
            "data": {
                "id": "liveview-1",
                "name": "Updated View",
                "modelKey": "liveview",
                "layout": 2,
                "slots": [],
            }
        },
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/subscribe/devices",
        {"data": [{"id": "device-msg-1", "deviceId": "device-1", "type": "online"}]},
    )
    protect_transport.add(
        "GET",
        "/proxy/protect/integration/v1/subscribe/events",
        {"data": [{"id": "event-1", "cameraId": "cam-1", "type": "motion"}]},
    )
    protect_transport.add(
        "POST",
        "/proxy/protect/integration/v1/alarm-manager/webhook/webhook-1",
        {"success": True, "message": "accepted"},
    )

    meta = await get_protect_meta_info(local_settings)
    viewers = await list_protect_viewers(local_settings)
    viewer = await get_protect_viewer("viewer-1", local_settings)
    updated_viewer = await update_protect_viewer(
        "viewer-1",
        local_settings,
        name="North Lobby Viewer",
        liveview="liveview-1",
        confirm=True,
    )
    live_views = await list_protect_live_views(local_settings)
    live_view = await get_protect_live_view("liveview-1", local_settings)
    created_live_view = await create_protect_live_view(
        {"name": "Warehouse View", "modelKey": "liveview", "layout": 4, "slots": []},
        local_settings,
        confirm=True,
    )
    updated_live_view = await update_protect_live_view(
        "liveview-1",
        local_settings,
        name="Updated View",
        model_key="liveview",
        layout=2,
        slots=[],
        confirm=True,
    )
    device_updates = await list_protect_device_updates(local_settings)
    events = await list_protect_events(local_settings)
    webhook_result = await send_protect_alarm_webhook(
        "webhook-1",
        local_settings,
        payload={"event": "manual-trigger"},
        confirm=True,
    )

    assert meta["version"] == "6.2.83"
    assert viewers["data"][0]["id"] == "viewer-1"
    assert viewer["name"] == "Lobby Viewer"
    assert updated_viewer["name"] == "North Lobby Viewer"
    assert live_views["data"][0]["id"] == "liveview-1"
    assert live_view["name"] == "Default View"
    assert created_live_view["id"] == "liveview-2"
    assert updated_live_view["name"] == "Updated View"
    assert device_updates["data"][0]["deviceId"] == "device-1"
    assert events["data"][0]["cameraId"] == "cam-1"
    assert webhook_result["success"] is True

    assert protect_transport.last_request(
        "PATCH",
        "/proxy/protect/integration/v1/viewers/viewer-1",
    )["json"] == {"name": "North Lobby Viewer", "liveview": "liveview-1"}
    assert protect_transport.last_request(
        "POST",
        "/proxy/protect/integration/v1/liveviews",
    )["json"] == {
        "name": "Warehouse View",
        "modelKey": "liveview",
        "layout": 4,
        "slots": [],
    }
    assert protect_transport.last_request(
        "PATCH",
        "/proxy/protect/integration/v1/liveviews/liveview-1",
    )["json"] == {"name": "Updated View", "modelKey": "liveview", "layout": 2, "slots": []}
    assert protect_transport.last_request(
        "POST",
        "/proxy/protect/integration/v1/alarm-manager/webhook/webhook-1",
    )["json"] == {"event": "manual-trigger"}
