"""Unit tests for UniFi Protect relay tools (Protect v7 surface, Phase 5a)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import protect_relays
from src.tools.protect_relays import (
    activate_protect_relay_output,
    get_protect_relay,
    list_protect_relays,
    update_protect_relay,
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
async def test_list_protect_relays_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(
        return_value={"count": 2, "totalCount": 2, "data": [
            {"id": "relay-1", "name": "Gate Relay"},
            {"id": "relay-2", "name": "Door Relay"},
        ]}
    )
    with patch("src.tools.protect_relays.ProtectClient", return_value=mock_client):
        result = await list_protect_relays(mock_settings, limit=10, offset=0)
    mock_client.get.assert_awaited_once_with(
        "/integration/v1/relays", params={"limit": 10, "offset": 0}
    )
    assert result["count"] == 2
    assert result["data"][0]["id"] == "relay-1"


@pytest.mark.asyncio
async def test_get_protect_relay_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"id": "relay-1", "name": "Gate Relay"})
    with patch("src.tools.protect_relays.ProtectClient", return_value=mock_client):
        result = await get_protect_relay("relay-1", mock_settings)
    mock_client.get.assert_awaited_once_with("/integration/v1/relays/relay-1")
    assert result["id"] == "relay-1"


# --- Write gates ------------------------------------------------------------

WRITES = [
    ("update_protect_relay", {"relay_id": "relay-1", "name": "x"}),
    ("activate_protect_relay_output", {"relay_id": "relay-1", "output_id": "out-1"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[n for n, _ in WRITES])
async def test_write_refused_without_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_relays.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_relays, name)(settings=mock_settings, **kwargs)
        client_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[f"{n}-strfalse" for n, _ in WRITES])
async def test_write_refused_with_string_false_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_relays.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_relays, name)(
                settings=mock_settings, confirm="false", **kwargs
            )
        client_cls.assert_not_called()


# --- Write happy paths ------------------------------------------------------


@pytest.mark.asyncio
async def test_update_protect_relay_success(mock_settings, mock_client):
    mock_client.patch = AsyncMock(
        return_value={"id": "relay-1", "name": "New Name", "ledSettings": {"isEnabled": True}}
    )
    with patch("src.tools.protect_relays.ProtectClient", return_value=mock_client):
        result = await update_protect_relay(
            "relay-1",
            mock_settings,
            name="New Name",
            led_settings={"isEnabled": True},
            confirm=True,
        )
    mock_client.patch.assert_awaited_once_with(
        "/integration/v1/relays/relay-1",
        json_data={"name": "New Name", "ledSettings": {"isEnabled": True}},
    )
    assert result["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_protect_relay_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_relays.ProtectClient", return_value=mock_client):
        result = await update_protect_relay(
            "relay-1", mock_settings, led_settings={"isEnabled": False}, confirm=True, dry_run=True
        )
    assert result["dry_run"] is True
    assert result["payload"] == {"ledSettings": {"isEnabled": False}}
    mock_client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_update_protect_relay_requires_a_field(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await update_protect_relay("relay-1", mock_settings, confirm=True)


@pytest.mark.asyncio
async def test_activate_protect_relay_output_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_relays.ProtectClient", return_value=mock_client):
        result = await activate_protect_relay_output(
            "relay-1", "out-1", mock_settings, state="on", pulse_duration=5000, confirm=True
        )
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/relays/relay-1/outputs/out-1/activate",
        json_data={"state": "on", "pulseDuration": 5000},
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_activate_protect_relay_output_toggle_only(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_relays.ProtectClient", return_value=mock_client):
        result = await activate_protect_relay_output("relay-1", "out-1", mock_settings, confirm=True)
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/relays/relay-1/outputs/out-1/activate", json_data=None
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_activate_protect_relay_output_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_relays.ProtectClient", return_value=mock_client):
        result = await activate_protect_relay_output(
            "relay-1", "out-1", mock_settings, state="off", confirm=True, dry_run=True
        )
    assert result["dry_run"] is True
    assert result["payload"] == {"state": "off"}
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_activate_protect_relay_output_rejects_bad_state(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await activate_protect_relay_output(
            "relay-1", "out-1", mock_settings, state="blink", confirm=True
        )


@pytest.mark.asyncio
async def test_activate_protect_relay_output_rejects_bad_pulse_duration(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await activate_protect_relay_output(
            "relay-1", "out-1", mock_settings, state="on", pulse_duration=-1, confirm=True
        )


# --- Input validation -------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_relay_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await get_protect_relay("   ", mock_settings)


@pytest.mark.asyncio
async def test_empty_output_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await activate_protect_relay_output("relay-1", "   ", mock_settings, confirm=True)
