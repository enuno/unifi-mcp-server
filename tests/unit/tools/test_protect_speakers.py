"""Unit tests for UniFi Protect speaker tools (Protect v7 surface, Phase 5a)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import protect_speakers
from src.tools.protect_speakers import (
    get_protect_speaker,
    list_protect_speakers,
    test_protect_speaker_sound as run_test_sound,
    update_protect_speaker,
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
async def test_list_protect_speakers_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(
        return_value={"count": 2, "totalCount": 2, "data": [
            {"id": "speaker-1", "name": "Porch Speaker", "volume": 80},
            {"id": "speaker-2", "name": "Garage Speaker", "volume": 50},
        ]}
    )
    with patch("src.tools.protect_speakers.ProtectClient", return_value=mock_client):
        result = await list_protect_speakers(mock_settings, limit=10, offset=0)
    mock_client.get.assert_awaited_once_with(
        "/integration/v1/speakers", params={"limit": 10, "offset": 0}
    )
    assert result["count"] == 2
    assert result["data"][0]["id"] == "speaker-1"


@pytest.mark.asyncio
async def test_get_protect_speaker_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"id": "speaker-1", "name": "Porch Speaker"})
    with patch("src.tools.protect_speakers.ProtectClient", return_value=mock_client):
        result = await get_protect_speaker("speaker-1", mock_settings)
    mock_client.get.assert_awaited_once_with("/integration/v1/speakers/speaker-1")
    assert result["id"] == "speaker-1"


# --- Write gates ------------------------------------------------------------

WRITES = [
    ("update_protect_speaker", {"speaker_id": "speaker-1", "name": "x"}),
    ("test_protect_speaker_sound", {"speaker_id": "speaker-1"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[n for n, _ in WRITES])
async def test_write_refused_without_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_speakers.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_speakers, name)(settings=mock_settings, **kwargs)
        client_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[f"{n}-strfalse" for n, _ in WRITES])
async def test_write_refused_with_string_false_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_speakers.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_speakers, name)(
                settings=mock_settings, confirm="false", **kwargs
            )
        client_cls.assert_not_called()


# --- Write happy paths ------------------------------------------------------


@pytest.mark.asyncio
async def test_update_protect_speaker_success(mock_settings, mock_client):
    mock_client.patch = AsyncMock(
        return_value={"id": "speaker-1", "name": "New Name", "volume": 70, "micVolume": 40, "isMicEnabled": True}
    )
    with patch("src.tools.protect_speakers.ProtectClient", return_value=mock_client):
        result = await update_protect_speaker(
            "speaker-1",
            mock_settings,
            name="New Name",
            volume=70,
            mic_volume=40,
            is_mic_enabled=True,
            confirm=True,
        )
    mock_client.patch.assert_awaited_once_with(
        "/integration/v1/speakers/speaker-1",
        json_data={"name": "New Name", "volume": 70, "micVolume": 40, "isMicEnabled": True},
    )
    assert result["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_protect_speaker_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_speakers.ProtectClient", return_value=mock_client):
        result = await update_protect_speaker(
            "speaker-1", mock_settings, volume=70, mic_volume=40, confirm=True, dry_run=True
        )
    assert result["dry_run"] is True
    assert result["payload"] == {"volume": 70, "micVolume": 40}
    mock_client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_update_protect_speaker_requires_a_field(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await update_protect_speaker("speaker-1", mock_settings, confirm=True)


@pytest.mark.asyncio
async def test_update_protect_speaker_validates_volume(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await update_protect_speaker("speaker-1", mock_settings, volume=101, confirm=True)
    with pytest.raises(ValidationError):
        await update_protect_speaker("speaker-1", mock_settings, volume=-1, confirm=True)


@pytest.mark.asyncio
async def test_update_protect_speaker_validates_mic_volume(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await update_protect_speaker("speaker-1", mock_settings, mic_volume=101, confirm=True)
    with pytest.raises(ValidationError):
        await update_protect_speaker("speaker-1", mock_settings, mic_volume=-1, confirm=True)


@pytest.mark.asyncio
async def test_test_sound_success(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"success": True})
    with patch("src.tools.protect_speakers.ProtectClient", return_value=mock_client):
        result = await run_test_sound("speaker-1", mock_settings, volume=40, confirm=True)
    mock_client.post.assert_awaited_once_with(
        "/integration/v1/speakers/speaker-1/test-sound", json_data={"volume": 40}
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_test_sound_rejects_bad_volume(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await run_test_sound("speaker-1", mock_settings, volume=101, confirm=True)


@pytest.mark.asyncio
async def test_test_sound_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_speakers.ProtectClient", return_value=mock_client):
        result = await run_test_sound("speaker-1", mock_settings, volume=40, dry_run=True)
    assert result["dry_run"] is True
    assert result["payload"] == {"volume": 40}
    mock_client.post.assert_not_called()


# --- Input validation -------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_speaker_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await get_protect_speaker("   ", mock_settings)
