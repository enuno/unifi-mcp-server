"""Unit tests for UniFi Protect event and webhook tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.exceptions import ValidationError

protect_events = pytest.importorskip("src.tools.protect_events")


def _tool(*names: str):
    for name in names:
        tool = getattr(protect_events, name, None)
        if tool is not None:
            return tool
    pytest.fail(f"None of the expected tool names exist on {protect_events.__name__}: {names}")


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
    client.post = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_list_protect_device_updates_success(mock_settings, mock_client):
    response = {"data": [{"id": "device-1", "event": "online"}], "count": 1, "totalCount": 1}
    mock_client.get = AsyncMock(return_value=response)
    list_protect_device_updates = _tool(
        "list_protect_device_updates",
    )

    with patch(f"{protect_events.__name__}.ProtectClient", return_value=mock_client):
        result = await list_protect_device_updates(mock_settings)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/subscribe/devices")
    assert result["count"] == 1
    assert result["data"][0]["event"] == "online"


@pytest.mark.asyncio
async def test_list_protect_events_success(mock_settings, mock_client):
    response = {"data": [{"id": "event-1", "type": "motion"}], "count": 1, "totalCount": 1}
    mock_client.get = AsyncMock(return_value=response)
    list_protect_events = _tool(
        "list_protect_events",
    )

    with patch(f"{protect_events.__name__}.ProtectClient", return_value=mock_client):
        result = await list_protect_events(mock_settings)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/subscribe/events")
    assert result["count"] == 1
    assert result["data"][0]["type"] == "motion"


@pytest.mark.asyncio
async def test_send_protect_alarm_webhook_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"ok": True})
    send_protect_alarm_webhook = _tool("send_protect_alarm_webhook")

    with patch(f"{protect_events.__name__}.ProtectClient", return_value=mock_client):
        result = await send_protect_alarm_webhook("webhook-1", mock_settings)

    mock_client.authenticate.assert_awaited_once()
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/alarm-manager/webhook/webhook-1", json_data={}
    )
    assert result == {"success": None, "message": None, "ok": True}


@pytest.mark.asyncio
async def test_send_protect_alarm_webhook_empty_id_raises(mock_settings):
    send_protect_alarm_webhook = _tool("send_protect_alarm_webhook")

    with pytest.raises(ValidationError, match="webhook_id"):
        await send_protect_alarm_webhook("", mock_settings)
