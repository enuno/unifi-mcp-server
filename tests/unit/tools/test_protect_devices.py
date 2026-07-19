"""Unit tests for UniFi Protect device tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

protect_devices = pytest.importorskip("src.tools.protect_devices")


def _tool(*names: str):
    for name in names:
        tool = getattr(protect_devices, name, None)
        if tool is not None:
            return tool
    pytest.fail(f"None of the expected tool names exist on {protect_devices.__name__}: {names}")


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.get_protect_integration_path = MagicMock(
        side_effect=lambda endpoint: f"/integration/v1/{endpoint.lstrip('/')}"
    )
    return settings


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_list_protect_device_updates_success(mock_settings, mock_client):
    response = {
        "count": 1,
        "totalCount": 1,
        "data": [{"id": "device-1", "event": "online"}],
    }
    mock_client.get = AsyncMock(return_value=response)
    list_protect_device_updates = _tool(
        "list_protect_device_updates",
    )

    with patch(f"{protect_devices.__name__}.ProtectClient", return_value=mock_client):
        result = await list_protect_device_updates(mock_settings)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/subscribe/devices")
    assert result["count"] == 1
    assert result["totalCount"] == 1
    assert result["data"][0]["event"] == "online"


@pytest.mark.asyncio
async def test_list_protect_device_updates_empty_response(mock_settings, mock_client):
    response = {"count": 0, "totalCount": 0, "data": []}
    mock_client.get = AsyncMock(return_value=response)
    list_protect_device_updates = _tool(
        "list_protect_device_updates",
    )

    with patch(f"{protect_devices.__name__}.ProtectClient", return_value=mock_client):
        result = await list_protect_device_updates(mock_settings)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/subscribe/devices")
    assert result["count"] == 0
    assert result["data"] == []
