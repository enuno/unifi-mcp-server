"""Unit tests for Protect MCP resources."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.resources.protect import ProtectResource


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


class TestProtectResource:
    def test_init(self, mock_settings):
        resource = ProtectResource(mock_settings)
        assert resource.settings == mock_settings

    @pytest.mark.asyncio
    async def test_list_nvrs_success(self, mock_settings, mock_client):
        response = {
            "count": 1,
            "totalCount": 1,
            "data": [{"id": "nvr-1", "name": "Main NVR", "model": "UNVR"}],
        }

        with patch("src.resources.protect.ProtectClient", return_value=mock_client):
            mock_client.get = AsyncMock(return_value=response)
            resource = ProtectResource(mock_settings)
            result = await resource.list_nvrs()

        mock_client.authenticate.assert_awaited_once()
        mock_client.get.assert_awaited_once_with("/integration/v1/nvrs")
        assert len(result) == 1
        assert result[0].id == "nvr-1"

    @pytest.mark.asyncio
    async def test_get_nvr_success(self, mock_settings, mock_client):
        response = {"id": "nvr-1", "name": "Main NVR", "model": "UNVR"}

        with patch("src.resources.protect.ProtectClient", return_value=mock_client):
            mock_client.get = AsyncMock(return_value=response)
            resource = ProtectResource(mock_settings)
            result = await resource.get_nvr("nvr-1")

        mock_client.authenticate.assert_awaited_once()
        mock_client.get.assert_awaited_once_with("/integration/v1/nvrs/nvr-1")
        assert result is not None
        assert result.id == "nvr-1"
        assert result.name == "Main NVR"

    @pytest.mark.asyncio
    async def test_list_nvrs_non_dict_response(self, mock_settings, mock_client):
        with patch("src.resources.protect.ProtectClient", return_value=mock_client):
            mock_client.get = AsyncMock(return_value=[])
            result = await ProtectResource(mock_settings).list_nvrs()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_nvr_empty_returns_none(self, mock_settings, mock_client):
        with patch("src.resources.protect.ProtectClient", return_value=mock_client):
            mock_client.get = AsyncMock(return_value={"data": {}})
            result = await ProtectResource(mock_settings).get_nvr("nvr-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_cameras_success(self, mock_settings, mock_client):
        response = {
            "data": [{"id": "cam-1", "name": "Front Door"}, {"id": "cam-2", "name": "Yard"}]
        }

        with patch("src.resources.protect.ProtectClient", return_value=mock_client):
            mock_client.get = AsyncMock(return_value=response)
            result = await ProtectResource(mock_settings).list_cameras()

        mock_client.authenticate.assert_awaited_once()
        mock_client.get.assert_awaited_once_with("/integration/v1/cameras")
        assert [c.id for c in result] == ["cam-1", "cam-2"]

    @pytest.mark.asyncio
    async def test_list_cameras_non_dict_response(self, mock_settings, mock_client):
        with patch("src.resources.protect.ProtectClient", return_value=mock_client):
            mock_client.get = AsyncMock(return_value=None)
            result = await ProtectResource(mock_settings).list_cameras()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_camera_unwraps_data(self, mock_settings, mock_client):
        response = {"data": {"id": "cam-1", "name": "Front Door"}}

        with patch("src.resources.protect.ProtectClient", return_value=mock_client):
            mock_client.get = AsyncMock(return_value=response)
            result = await ProtectResource(mock_settings).get_camera("cam-1")

        mock_client.get.assert_awaited_once_with("/integration/v1/cameras/cam-1")
        assert result is not None
        assert result.name == "Front Door"

    @pytest.mark.asyncio
    async def test_get_camera_empty_returns_none(self, mock_settings, mock_client):
        with patch("src.resources.protect.ProtectClient", return_value=mock_client):
            mock_client.get = AsyncMock(return_value={})
            result = await ProtectResource(mock_settings).get_camera("cam-1")

        assert result is None
