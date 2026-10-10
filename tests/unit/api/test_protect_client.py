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


def _mock_transport_client(settings, handler):
    import httpx

    client = ProtectClient(settings)
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


def _recorder(status=200, **response_kwargs):
    import httpx

    seen = []

    def handler(request):
        seen.append(request)
        if not response_kwargs:
            return httpx.Response(status, json={"data": []})
        return httpx.Response(status, **response_kwargs)

    return seen, handler


class TestProtectClientPooling:
    @pytest.mark.asyncio
    async def test_reuses_pooled_connection_and_releases_it(self, mock_settings):
        from src.api.pool import active_pool

        pool = MagicMock()
        connection = MagicMock()
        pool.acquire.return_value = connection
        token = active_pool.set(pool)
        try:
            client = ProtectClient(mock_settings)
        finally:
            active_pool.reset(token)

        pool.acquire.assert_called_once_with(mock_settings)
        assert client.client is connection.client
        await client.close()
        pool.release.assert_called_once_with(connection)
        connection.client.aclose.assert_not_called()

        # A second close falls through to closing the (pooled) client.
        connection.client.aclose = AsyncMock()
        await client.close()
        pool.release.assert_called_once()


class TestProtectClientHttp:
    @pytest.mark.parametrize(
        ("endpoint", "path"),
        [
            ("cameras", "/integration/v1/cameras"),
            ("/v1/meta", "/v1/meta"),
            ("integration/v1/nvrs", "/integration/v1/nvrs"),
            ("proxy/protect/x", "/proxy/protect/x"),
        ],
    )
    def test_build_url(self, mock_settings, endpoint, path):
        assert ProtectClient(mock_settings)._build_url(endpoint) == f"https://api.ui.com{path}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["post", "put", "patch"])
    async def test_write_methods_send_json_and_params(self, mock_settings, method):
        import json

        seen, handler = _recorder(json={"id": "x"})
        client = _mock_transport_client(mock_settings, handler)

        result = await getattr(client, method)("cameras/x", json_data={"a": 1}, params={"q": "1"})

        assert result == {"id": "x"}
        assert seen[0].method == method.upper()
        assert seen[0].url.path == "/integration/v1/cameras/x"
        assert seen[0].url.params["q"] == "1"
        assert json.loads(seen[0].content) == {"a": 1}

    @pytest.mark.asyncio
    async def test_delete(self, mock_settings):
        seen, handler = _recorder(json={})
        client = _mock_transport_client(mock_settings, handler)

        assert await client.delete("cameras/x") == {}
        assert seen[0].method == "DELETE"

    @pytest.mark.asyncio
    async def test_error_status_raises_api_error(self, mock_settings):
        from src.utils.exceptions import APIError

        _, handler = _recorder(status=403, text="forbidden")
        client = _mock_transport_client(mock_settings, handler)

        with pytest.raises(APIError, match=r"\(403\): forbidden"):
            await client.get("cameras")

    @pytest.mark.asyncio
    async def test_undecodable_body_raises_api_error(self, mock_settings):
        from src.utils.exceptions import APIError

        _, handler = _recorder(text="<html>")
        client = _mock_transport_client(mock_settings, handler)

        with pytest.raises(APIError, match="Failed to decode"):
            await client.get("cameras")

    @pytest.mark.asyncio
    async def test_transport_error_wrapped(self, mock_settings):
        import httpx

        from src.utils.exceptions import APIError

        def handler(request):
            raise httpx.ConnectError("down", request=request)

        client = _mock_transport_client(mock_settings, handler)
        with pytest.raises(APIError, match="Unexpected Protect API error: down"):
            await client.get("cameras")


class TestProtectClientAuthenticateShapes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ([], True),
            ({"meta": {"rc": "ok"}}, True),
            ({"count": 0}, True),
            ({"meta": {"rc": "error"}}, False),
            ("text", False),
        ],
    )
    async def test_response_shapes(self, mock_settings, body, expected):
        client = ProtectClient(mock_settings)
        client.get = AsyncMock(return_value=body)

        await client.authenticate()

        assert client.is_authenticated is expected
