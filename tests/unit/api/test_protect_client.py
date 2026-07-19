"""Unit tests for UniFi Protect API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.protect_client import ProtectClient
from src.config import APIType
from src.utils.exceptions import AuthenticationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = APIType.CLOUD_EA
    settings.base_url = "https://api.ui.com"
    settings.request_timeout = 30.0
    settings.verify_ssl = True
    settings.get_headers = MagicMock(return_value={"X-API-Key": "test-api-key"})
    settings.get_protect_integration_path = MagicMock(
        side_effect=lambda endpoint: (
            f"/proxy/protect/integration/v1/{endpoint.lstrip('/')}"
            if settings.api_type == APIType.LOCAL
            else f"/integration/v1/{endpoint.lstrip('/')}"
        )
    )
    return settings


@pytest.fixture
def mock_settings_local():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = APIType.LOCAL
    settings.base_url = "https://192.168.2.1:443"
    settings.request_timeout = 30.0
    settings.verify_ssl = False
    settings.get_headers = MagicMock(return_value={"X-API-Key": "test-api-key"})
    settings.get_protect_integration_path = MagicMock(
        side_effect=lambda endpoint: (
            f"/proxy/protect/integration/v1/{endpoint.lstrip('/')}"
            if settings.api_type == APIType.LOCAL
            else f"/integration/v1/{endpoint.lstrip('/')}"
        )
    )
    return settings


class TestProtectClientInit:
    @pytest.mark.asyncio
    async def test_client_init(self, mock_settings):
        client = ProtectClient(mock_settings)

        assert client.settings == mock_settings
        assert client._authenticated is False
        await client.close()

    @pytest.mark.asyncio
    async def test_client_context_manager(self, mock_settings):
        async with ProtectClient(mock_settings) as client:
            assert client is not None
            assert isinstance(client, ProtectClient)


class TestProtectClientRequests:
    @pytest.mark.asyncio
    async def test_get_uses_requested_path(self, mock_settings):
        client = ProtectClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": [{"id": "cam-1"}]}'
        mock_response.json = MagicMock(return_value={"data": [{"id": "cam-1"}]})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await client.get("/integration/v1/cameras")

        mock_request.assert_awaited_once()
        assert result == {"data": [{"id": "cam-1"}]}
        await client.close()

    @pytest.mark.asyncio
    async def test_authenticate_success(self, mock_settings):
        client = ProtectClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": [{"id": "cam-1"}]}'
        mock_response.json = MagicMock(return_value={"data": [{"id": "cam-1"}]})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            await client.authenticate()

        assert client._authenticated is True
        await client.close()

    @pytest.mark.asyncio
    async def test_authenticate_failure_raises(self, mock_settings):
        client = ProtectClient(mock_settings)

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("Connection refused")

            with pytest.raises(AuthenticationError, match="Failed to authenticate"):
                await client.authenticate()

        await client.close()


class TestProtectClientLocalPathing:
    @pytest.mark.asyncio
    async def test_get_accepts_local_proxy_path(self, mock_settings_local):
        client = ProtectClient(mock_settings_local)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": []}'
        mock_response.json = MagicMock(return_value={"data": []})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            await client.get("/proxy/protect/integration/v1/cameras")

        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert args[1].startswith("https://192.168.2.1:443/proxy/protect/integration/v1/cameras")
        await client.close()
