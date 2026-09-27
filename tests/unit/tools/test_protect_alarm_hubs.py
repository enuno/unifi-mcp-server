"""Unit tests for UniFi Protect alarm hub tools (Protect v7 surface, Phase 5a)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import protect_alarm_hubs
from src.tools.protect_alarm_hubs import (
    get_protect_alarm_hub,
    list_protect_alarm_hubs,
    trigger_protect_alarm_hub_output,
    update_protect_alarm_hub,
)
from src.utils.exceptions import ValidationError


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
    client.patch = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# --- Read paths -------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_protect_alarm_hubs_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(
        return_value={"count": 2, "totalCount": 2, "data": [
            {"id": "hub-1", "name": "Main Hub"},
            {"id": "hub-2", "name": "Backup Hub"},
        ]}
    )
    with patch("src.tools.protect_alarm_hubs.ProtectClient", return_value=mock_client):
        result = await list_protect_alarm_hubs(mock_settings, limit=10, offset=0)
    mock_client.get.assert_awaited_once_with(
        "/integration/v1/alarm-hubs", params={"limit": 10, "offset": 0}
    )
    assert result["count"] == 2
    assert result["data"][0]["id"] == "hub-1"


@pytest.mark.asyncio
async def test_get_protect_alarm_hub_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"id": "hub-1", "name": "Main Hub"})
    with patch("src.tools.protect_alarm_hubs.ProtectClient", return_value=mock_client):
        result = await get_protect_alarm_hub("hub-1", mock_settings)
    mock_client.get.assert_awaited_once_with("/integration/v1/alarm-hubs/hub-1")
    assert result["id"] == "hub-1"


# --- Write gates ------------------------------------------------------------

WRITES = [
    ("update_protect_alarm_hub", {"alarm_hub_id": "hub-1", "name": "x"}),
    (
        "trigger_protect_alarm_hub_output",
        {"alarm_hub_id": "hub-1", "output_id": "out-1", "enable": True},
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[n for n, _ in WRITES])
async def test_write_refused_without_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_alarm_hubs.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_alarm_hubs, name)(settings=mock_settings, **kwargs)
        client_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[f"{n}-strfalse" for n, _ in WRITES])
async def test_write_refused_with_string_false_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_alarm_hubs.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_alarm_hubs, name)(
                settings=mock_settings, confirm="false", **kwargs
            )
        client_cls.assert_not_called()


# --- Update happy paths -----------------------------------------------------


@pytest.mark.asyncio
async def test_update_protect_alarm_hub_success(mock_settings, mock_client):
    mock_client.patch = AsyncMock(return_value={"id": "hub-1", "name": "New Name"})
    with patch("src.tools.protect_alarm_hubs.ProtectClient", return_value=mock_client):
        result = await update_protect_alarm_hub(
            "hub-1", mock_settings, name="New Name", confirm=True
        )
    mock_client.patch.assert_awaited_once_with(
        "/integration/v1/alarm-hubs/hub-1", json_data={"name": "New Name"}
    )
    assert result["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_protect_alarm_hub_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_alarm_hubs.ProtectClient", return_value=mock_client):
        result = await update_protect_alarm_hub(
            "hub-1", mock_settings, name="New Name", confirm=True, dry_run=True
        )
    assert result["dry_run"] is True
    assert result["payload"] == {"name": "New Name"}
    mock_client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_update_protect_alarm_hub_requires_a_field(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await update_protect_alarm_hub("hub-1", mock_settings, confirm=True)


# --- Trigger output happy paths ----------------------------------------------


@pytest.mark.asyncio
async def test_trigger_output_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_alarm_hubs.ProtectClient", return_value=mock_client):
        result = await trigger_protect_alarm_hub_output(
            "hub-1", "out-1", mock_settings, enable=True, delay=500, duration=1000, confirm=True
        )
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/alarm-hubs/hub-1/outputs/out-1/trigger",
        json_data={"enable": True, "delay": 500, "duration": 1000},
    )
    assert result["success"] is True
    assert result["alarm_hub_id"] == "hub-1"
    assert result["output_id"] == "out-1"


@pytest.mark.asyncio
async def test_trigger_output_toggle_omits_enable(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_alarm_hubs.ProtectClient", return_value=mock_client):
        await trigger_protect_alarm_hub_output("hub-1", "out-1", mock_settings, confirm=True)
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/alarm-hubs/hub-1/outputs/out-1/trigger", json_data=None
    )


@pytest.mark.asyncio
async def test_trigger_output_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_alarm_hubs.ProtectClient", return_value=mock_client):
        result = await trigger_protect_alarm_hub_output(
            "hub-1",
            "out-1",
            mock_settings,
            enable=False,
            duration=0,
            confirm=True,
            dry_run=True,
        )
    assert result["dry_run"] is True
    assert result["payload"] == {"enable": False, "duration": 0}
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_output_rejects_negative_delay(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await trigger_protect_alarm_hub_output(
            "hub-1", "out-1", mock_settings, delay=-1, confirm=True
        )


@pytest.mark.asyncio
async def test_trigger_output_rejects_negative_duration(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await trigger_protect_alarm_hub_output(
            "hub-1", "out-1", mock_settings, duration=-5, confirm=True
        )


# --- Input validation -------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_alarm_hub_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await get_protect_alarm_hub("   ", mock_settings)


@pytest.mark.asyncio
async def test_trigger_output_rejects_empty_output_id(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await trigger_protect_alarm_hub_output(
            "hub-1", "   ", mock_settings, enable=True, confirm=True
        )
