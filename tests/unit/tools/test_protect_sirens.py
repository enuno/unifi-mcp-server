"""Unit tests for UniFi Protect siren tools (Protect v7 surface, Phase 5a)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import protect_sirens
from src.tools.protect_sirens import (
    get_protect_siren,
    list_protect_sirens,
    play_protect_siren,
    stop_protect_siren,
    update_protect_siren,
)
from src.utils.exceptions import ValidationError

run_test_sound = protect_sirens.test_protect_siren_sound


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
async def test_list_protect_sirens_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(
        return_value={
            "count": 2,
            "totalCount": 2,
            "data": [
                {"id": "siren-1", "name": "Yard Siren", "volume": 80},
                {"id": "siren-2", "name": "Hall Siren", "volume": 50},
            ],
        }
    )
    with patch("src.tools.protect_sirens.ProtectClient", return_value=mock_client):
        result = await list_protect_sirens(mock_settings, limit=10, offset=0)
    mock_client.get.assert_awaited_once_with(
        "/integration/v1/sirens", params={"limit": 10, "offset": 0}
    )
    assert result["count"] == 2
    assert result["data"][0]["id"] == "siren-1"


@pytest.mark.asyncio
async def test_get_protect_siren_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"id": "siren-1", "name": "Yard Siren"})
    with patch("src.tools.protect_sirens.ProtectClient", return_value=mock_client):
        result = await get_protect_siren("siren-1", mock_settings)
    mock_client.get.assert_awaited_once_with("/integration/v1/sirens/siren-1")
    assert result["id"] == "siren-1"


# --- Write gates ------------------------------------------------------------

WRITES = [
    ("update_protect_siren", {"siren_id": "siren-1", "name": "x"}),
    ("play_protect_siren", {"siren_id": "siren-1"}),
    ("stop_protect_siren", {"siren_id": "siren-1"}),
    ("test_protect_siren_sound", {"siren_id": "siren-1"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[n for n, _ in WRITES])
async def test_write_refused_without_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_sirens.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_sirens, name)(settings=mock_settings, **kwargs)
        client_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[f"{n}-strfalse" for n, _ in WRITES])
async def test_write_refused_with_string_false_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_sirens.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_sirens, name)(settings=mock_settings, confirm="false", **kwargs)
        client_cls.assert_not_called()


# --- Write happy paths ------------------------------------------------------


@pytest.mark.asyncio
async def test_update_protect_siren_success(mock_settings, mock_client):
    mock_client.patch = AsyncMock(return_value={"id": "siren-1", "name": "New Name", "volume": 70})
    with patch("src.tools.protect_sirens.ProtectClient", return_value=mock_client):
        result = await update_protect_siren(
            "siren-1", mock_settings, name="New Name", volume=70, confirm=True
        )
    mock_client.patch.assert_awaited_once_with(
        "/integration/v1/sirens/siren-1", json_data={"name": "New Name", "volume": 70}
    )
    assert result["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_protect_siren_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_sirens.ProtectClient", return_value=mock_client):
        result = await update_protect_siren(
            "siren-1", mock_settings, volume=70, confirm=True, dry_run=True
        )
    assert result["dry_run"] is True
    assert result["payload"] == {"volume": 70}
    mock_client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_update_protect_siren_requires_a_field(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await update_protect_siren("siren-1", mock_settings, confirm=True)


@pytest.mark.asyncio
async def test_update_protect_siren_validates_volume(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await update_protect_siren("siren-1", mock_settings, volume=200, confirm=True)


@pytest.mark.asyncio
async def test_play_protect_siren_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_sirens.ProtectClient", return_value=mock_client):
        result = await play_protect_siren("siren-1", mock_settings, duration=30, confirm=True)
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/sirens/siren-1/play", json_data={"duration": 30}
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_play_protect_siren_rejects_bad_duration(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await play_protect_siren("siren-1", mock_settings, duration=-5, confirm=True)


@pytest.mark.asyncio
async def test_stop_protect_siren_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_sirens.ProtectClient", return_value=mock_client):
        result = await stop_protect_siren("siren-1", mock_settings, confirm=True)
    mock_client.post.assert_awaited_once_with("/integration/v1/sirens/siren-1/stop")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_test_sound_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_sirens.ProtectClient", return_value=mock_client):
        result = await run_test_sound("siren-1", mock_settings, volume=40, confirm=True)
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/sirens/siren-1/test-sound", json_data={"volume": 40}
    )
    assert result["success"] is True


# --- Input validation -------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_siren_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await get_protect_siren("   ", mock_settings)
