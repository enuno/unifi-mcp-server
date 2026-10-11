"""Unit tests for the Protect device, light, sensor and chime tools.

Every family in ``src/tools/protect_devices.py`` follows the same list / get /
update shape, so the tests are parametrised over the four families.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import protect_devices as pd
from src.utils.exceptions import ValidationError

FAMILIES = [
    # (endpoint, list tool, get tool, update tool, id kwarg label)
    (
        "devices",
        pd.list_protect_devices,
        pd.get_protect_device,
        pd.update_protect_device,
        "device_id",
    ),
    ("lights", pd.list_protect_lights, pd.get_protect_light, pd.update_protect_light, "light_id"),
    (
        "sensors",
        pd.list_protect_sensors,
        pd.get_protect_sensor,
        pd.update_protect_sensor,
        "sensor_id",
    ),
    ("chimes", pd.list_protect_chimes, pd.get_protect_chime, pd.update_protect_chime, "chime_id"),
]
FAMILY_IDS = [f[0] for f in FAMILIES]

# update kwargs -> expected camelCase payload, per family
UPDATES: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    "devices": (
        {"name": "Hub", "model": "UP-HUB", "type": "hub", "state": "CONNECTED",
         "mac": "aa:bb:cc:dd:ee:ff", "firmware_version": "1.2.3"},
        {"name": "Hub", "model": "UP-HUB", "type": "hub", "state": "CONNECTED",
         "mac": "aa:bb:cc:dd:ee:ff", "firmwareVersion": "1.2.3"},
    ),
    "lights": (
        {"name": "Porch", "is_light_force_enabled": True, "light_mode_settings": {},
         "light_device_settings": {}},
        {"name": "Porch", "isLightForceEnabled": True, "lightModeSettings": {},
         "lightDeviceSettings": {}},
    ),
    "sensors": (
        {"name": "Door", "light_settings": {}, "humidity_settings": {},
         "temperature_settings": {}, "motion_settings": {}, "alarm_settings": {}},
        {"name": "Door", "lightSettings": {}, "humiditySettings": {},
         "temperatureSettings": {}, "motionSettings": {}, "alarmSettings": {}},
    ),
    "chimes": (
        {"name": "Hall", "camera_ids": ["cam-1"], "ring_settings": []},
        {"name": "Hall", "cameraIds": ["cam-1"], "ringSettings": []},
    ),
}  # fmt: skip


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.get_protect_integration_path = MagicMock(
        side_effect=lambda endpoint: f"/integration/v1/{endpoint.lstrip('/')}"
    )
    return settings


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock()
    client.patch = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _patch(client: AsyncMock):
    return patch("src.tools.protect_devices.ProtectClient", return_value=client)


class TestHelpers:
    def test_validate_id_strips(self) -> None:
        assert pd._validate_id("  abc ", "x") == "abc"

    def test_validate_id_rejects_blank(self) -> None:
        with pytest.raises(ValidationError, match="x is required"):
            pd._validate_id("   ", "x")

    @pytest.mark.parametrize(
        ("response", "expected"),
        [
            ([{"id": 1}, "x"], [{"id": 1}]),
            ({"data": [{"id": 1}, 2]}, [{"id": 1}]),
            ({"data": {"id": 1}}, []),
            (None, []),
        ],
    )
    def test_extract_collection(self, response: Any, expected: list) -> None:
        assert pd._extract_collection(response) == expected

    @pytest.mark.parametrize(
        ("response", "expected"),
        [
            ({"data": {"id": 1}}, {"id": 1}),
            ({"id": 1}, {"id": 1}),
            ({"data": [1]}, {"data": [1]}),
            ([{"id": 1}], {}),
        ],
    )
    def test_extract_item(self, response: Any, expected: dict) -> None:
        assert pd._extract_item(response) == expected


@pytest.mark.parametrize(
    ("endpoint", "list_tool", "_get", "_update", "_label"), FAMILIES, ids=FAMILY_IDS
)
class TestList:
    @pytest.mark.asyncio
    async def test_paginates_locally(
        self, mock_settings, mock_client, endpoint, list_tool, _get, _update, _label
    ) -> None:
        mock_client.get.return_value = {"data": [{"id": f"{endpoint}-{i}"} for i in range(5)]}
        with _patch(mock_client):
            result = await list_tool(mock_settings, limit=2, offset=1)

        mock_client.authenticate.assert_awaited_once()
        # One full fetch, paginated locally: no limit/offset sent to the API.
        mock_client.get.assert_awaited_once_with(f"/integration/v1/{endpoint}")
        assert result["count"] == 2
        assert result["totalCount"] == 5
        assert (result["offset"], result["limit"]) == (1, 2)
        assert [d["id"] for d in result["data"]] == [f"{endpoint}-1", f"{endpoint}-2"]

    @pytest.mark.asyncio
    async def test_bare_list_response(
        self, mock_settings, mock_client, endpoint, list_tool, _get, _update, _label
    ) -> None:
        mock_client.get.return_value = [{"id": "a", "name": "A"}]
        with _patch(mock_client):
            result = await list_tool(mock_settings)

        assert result["data"][0]["name"] == "A"


@pytest.mark.parametrize(
    ("endpoint", "_list", "get_tool", "_update", "_label"), FAMILIES, ids=FAMILY_IDS
)
class TestGet:
    @pytest.mark.asyncio
    async def test_returns_record(
        self, mock_settings, mock_client, endpoint, _list, get_tool, _update, _label
    ) -> None:
        mock_client.get.return_value = {"data": {"id": "x1", "name": "Thing", "isOnline": True}}
        with _patch(mock_client):
            result = await get_tool(" x1 ", mock_settings)

        mock_client.get.assert_awaited_once_with(f"/integration/v1/{endpoint}/x1")
        assert result["id"] == "x1"
        assert result["isOnline"] is True

    @pytest.mark.asyncio
    async def test_rejects_blank_id(
        self, mock_settings, mock_client, endpoint, _list, get_tool, _update, _label
    ) -> None:
        with _patch(mock_client), pytest.raises(ValidationError):
            await get_tool("", mock_settings)
        mock_client.get.assert_not_called()


@pytest.mark.parametrize(
    ("endpoint", "_list", "_get", "update_tool", "label"), FAMILIES, ids=FAMILY_IDS
)
class TestUpdate:
    @pytest.mark.asyncio
    async def test_requires_confirm(
        self, mock_settings, mock_client, endpoint, _list, _get, update_tool, label
    ) -> None:
        with _patch(mock_client), pytest.raises(ValidationError, match="confirm"):
            await update_tool("x1", mock_settings, name="n")
        mock_client.patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_builds_payload(
        self, mock_settings, mock_client, endpoint, _list, _get, update_tool, label
    ) -> None:
        kwargs, expected = UPDATES[endpoint]
        with _patch(mock_client):
            result = await update_tool("x1", mock_settings, dry_run="true", **kwargs)

        assert result["dry_run"] is True
        assert result[label] == "x1"
        assert result["payload"] == expected
        mock_client.patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_applies_patch(
        self, mock_settings, mock_client, endpoint, _list, _get, update_tool, label
    ) -> None:
        mock_client.patch.return_value = {"id": "x1", "name": "Renamed"}
        with _patch(mock_client):
            result = await update_tool("x1", mock_settings, name="Renamed", confirm=True)

        mock_client.authenticate.assert_awaited_once()
        mock_client.patch.assert_awaited_once_with(
            f"/integration/v1/{endpoint}/x1", json_data={"name": "Renamed"}
        )
        assert result["name"] == "Renamed"

    @pytest.mark.asyncio
    async def test_rejects_blank_id(
        self, mock_settings, mock_client, endpoint, _list, _get, update_tool, label
    ) -> None:
        with pytest.raises(ValidationError, match=f"{label} is required"):
            await update_tool(" ", mock_settings, name="n", confirm=True)


class TestDeviceUpdates:
    @pytest.mark.asyncio
    async def test_paginates(self, mock_settings, mock_client) -> None:
        mock_client.get.return_value = [{"id": f"d{i}"} for i in range(3)]
        with _patch(mock_client):
            result = await pd.list_protect_device_updates(mock_settings, limit=1, offset=2)

        assert result["totalCount"] == 3
        assert [m["id"] for m in result["data"]] == ["d2"]
