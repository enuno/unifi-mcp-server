"""Unit tests for UniFi Protect camera tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.protect_cameras import get_protect_camera, list_protect_cameras
from src.utils.exceptions import ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.get_protect_integration_path = MagicMock(side_effect=lambda endpoint: f"/integration/v1/{endpoint.lstrip('/')}")
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
async def test_list_protect_cameras_success(mock_settings, mock_client):
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 2,
        "totalCount": 2,
        "data": [
            {"id": "cam-1", "name": "Front Door", "model": "G4 Pro", "isRecording": True},
            {"id": "cam-2", "name": "Garage", "model": "G5 Bullet", "isRecording": False},
        ],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.protect_cameras.ProtectClient", return_value=mock_client):
        result = await list_protect_cameras(mock_settings, limit=10, offset=0)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/cameras", params={"limit": 10, "offset": 0})
    assert result["count"] == 2
    assert result["data"][0]["id"] == "cam-1"
    assert result["data"][0]["name"] == "Front Door"


@pytest.mark.asyncio
async def test_get_protect_camera_success(mock_settings, mock_client):
    mock_response = {"id": "cam-1", "name": "Front Door", "model": "G4 Pro", "isRecording": True}
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.protect_cameras.ProtectClient", return_value=mock_client):
        result = await get_protect_camera("cam-1", mock_settings)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/cameras/cam-1")
    assert result["id"] == "cam-1"
    assert result["model"] == "G4 Pro"


@pytest.mark.asyncio
async def test_get_protect_camera_empty_id_raises(mock_settings):
    with pytest.raises(ValidationError, match="camera_id"):
        await get_protect_camera("", mock_settings)
