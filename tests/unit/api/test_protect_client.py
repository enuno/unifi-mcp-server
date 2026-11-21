"""Unit tests for UniFi Protect API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.protect_client import ProtectClient
from src.config import APIType, Settings
from src.utils.exceptions import APIError, AuthenticationError


class _LocalHTTPSettings(Settings):
    """Real Settings path behavior with HTTP for ephemeral test servers."""

    @property
    def base_url(self) -> str:
        return f"http://{self.local_host}:{self.local_port}"


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
    return _LocalHTTPSettings.model_validate(
        {
            "UNIFI_API_KEY": "test-api-key",  # pragma: allowlist secret
            "UNIFI_API_TYPE": "local",
            "UNIFI_LOCAL_HOST": "192.0.2.1",
            "UNIFI_LOCAL_VERIFY_SSL": False,
        }
    )


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
        assert args[1].startswith("http://192.0.2.1:443/proxy/protect/integration/v1/cameras")
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

        # A second close must not close the shared client the pool still holds.
        connection.client.aclose = AsyncMock()
        await client.close()
        pool.release.assert_called_once()
        connection.client.aclose.assert_not_called()


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

        result = await client.delete("cameras/x")

        assert result == {}
        assert seen[0].method == "DELETE"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [200, 204])
    async def test_successful_empty_response_returns_empty_object(self, mock_settings, status):
        seen, handler = _recorder(status=status, content=b"")
        client = _mock_transport_client(mock_settings, handler)

        result = await client.delete("external/arm-profiles/x")

        assert result == {}
        assert seen[0].method == "DELETE"

    @pytest.mark.asyncio
    async def test_successful_empty_post_returns_empty_object(self, mock_settings):
        seen, handler = _recorder(status=204, content=b"")
        client = _mock_transport_client(mock_settings, handler)

        result = await client.post("speakers/speaker-1/stop-siren")

        assert result == {}
        assert seen[0].method == "POST"

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

        def handler(request):
            raise httpx.ConnectError("down", request=request)

        client = _mock_transport_client(mock_settings, handler)
        with pytest.raises(APIError, match="Unexpected Protect API error: down"):
            await client.get("cameras")


class TestProtectClientWebSocket:
    @pytest.mark.asyncio
    async def test_websocket_url_uses_wss_for_real_local_settings(self):
        settings = Settings.model_validate(
            {
                "UNIFI_API_KEY": "test-api-key",  # pragma: allowlist secret
                "UNIFI_API_TYPE": "local",
                "UNIFI_LOCAL_HOST": "console.example.test",
            }
        )
        client = ProtectClient(settings)

        url = client._build_websocket_url(
            settings.get_protect_integration_path("subscribe/updates"),
            {"modelKeys": "camera,event"},
        )

        assert url == (
            "wss://console.example.test:443/proxy/protect/integration/v1/"
            "subscribe/updates?modelKeys=camera%2Cevent"
        )
        await client.close()

    @pytest.mark.asyncio
    async def test_websocket_tls_context_honors_disabled_verification(self, mock_settings_local):
        import ssl

        client = ProtectClient(mock_settings_local)
        context = client._websocket_ssl_context()

        assert context.check_hostname is False
        assert context.verify_mode == ssl.CERT_NONE
        await client.close()

    @pytest.mark.asyncio
    async def test_websocket_url_rejects_non_http_origin(self, mock_settings_local):
        client = ProtectClient(mock_settings_local)

        with patch.object(client, "_build_url", return_value="ftp://console.example.test/updates"):
            with pytest.raises(APIError, match="must use http or https"):
                client._build_websocket_url("updates", {"modelKeys": "camera"})

        await client.close()

    @pytest.mark.asyncio
    async def test_websocket_tls_context_reuses_configured_context(self, mock_settings_local):
        import ssl

        client = ProtectClient(mock_settings_local)
        configured = ssl.create_default_context()

        with patch("src.api.protect_client.httpx_verify", return_value=configured):
            assert client._websocket_ssl_context() is configured

        await client.close()

    @pytest.mark.asyncio
    async def test_websocket_tls_context_enables_default_verification(self, mock_settings_local):
        import ssl

        client = ProtectClient(mock_settings_local)

        with (
            patch("src.api.protect_client.httpx_verify", return_value=True),
            patch("src.api.protect_client.ssl.create_default_context") as create_context,
        ):
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            create_context.return_value = context
            assert client._websocket_ssl_context() is context

        create_context.assert_called_once_with()
        await client.close()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("duration_seconds", "max_messages", "error"),
        [(0.0, 1, "duration_seconds"), (1.0, 0, "max_messages")],
    )
    async def test_websocket_sample_rejects_non_positive_bounds(
        self, mock_settings_local, duration_seconds, max_messages, error
    ):
        client = ProtectClient(mock_settings_local)

        with pytest.raises(APIError, match=error):
            await client.sample_model_updates(
                ["camera"], duration_seconds=duration_seconds, max_messages=max_messages
            )

        await client.close()

    @pytest.mark.asyncio
    async def test_websocket_upgrade_wraps_transport_error_and_sets_tls_name(self):
        settings = Settings.model_validate(
            {
                "UNIFI_API_KEY": "test-api-key",  # pragma: allowlist secret
                "UNIFI_API_TYPE": "local",
                "UNIFI_LOCAL_HOST": "console.example.test",
                "UNIFI_LOCAL_VERIFY_SSL": True,
                "UNIFI_LOCAL_TLS_SERVER_NAME": "console.internal",
            }
        )
        client = ProtectClient(settings)

        with (
            patch.object(client, "_websocket_ssl_context", return_value=MagicMock()) as tls_context,
            patch(
                "src.api.protect_client.connect", side_effect=RuntimeError("transport down")
            ) as connect,
            pytest.raises(APIError, match="subscription failed: transport down"),
        ):
            await client.sample_model_updates(["camera"], duration_seconds=1.0, max_messages=1)

        tls_context.assert_called_once_with()
        assert connect.call_args.kwargs["server_hostname"] == "console.internal"
        await client.close()

    @pytest.mark.asyncio
    async def test_samples_updates_over_real_websocket_upgrade(self, mock_settings_local):
        import json
        from urllib.parse import parse_qs, urlsplit

        from websockets.asyncio.server import serve

        seen = {}

        async def handler(websocket):
            seen["path"] = websocket.request.path
            seen["header_value"] = websocket.request.headers.get("X-API-KEY")
            await websocket.send(
                json.dumps(
                    {
                        "type": "update",
                        "item": {"id": "cam-1", "modelKey": "camera", "name": "Front"},
                    }
                )
            )
            await websocket.close()

        async with serve(handler, "127.0.0.1", 0) as server:
            port = next(iter(server.sockets)).getsockname()[1]
            mock_settings_local.local_host = "127.0.0.1"
            mock_settings_local.local_port = port
            client = ProtectClient(mock_settings_local)
            sample = await client.sample_model_updates(
                ["camera", "event"], duration_seconds=1.0, max_messages=10
            )
            await client.close()

        parsed = urlsplit(seen["path"])
        assert parsed.path == "/proxy/protect/integration/v1/subscribe/updates"
        assert parse_qs(parsed.query) == {"modelKeys": ["camera,event"]}
        assert seen["header_value"] == "test-api-key"
        assert sample["stop_reason"] == "peer_closed"
        assert sample["messages"] == [
            {
                "type": "update",
                "item": {"id": "cam-1", "modelKey": "camera", "name": "Front"},
            }
        ]

    @pytest.mark.asyncio
    async def test_websocket_sample_stops_at_message_limit(self, mock_settings_local):
        import json

        from websockets.asyncio.server import serve

        async def handler(websocket):
            for item_id in ("cam-1", "cam-2"):
                await websocket.send(
                    json.dumps({"type": "update", "item": {"id": item_id, "modelKey": "camera"}})
                )

        async with serve(handler, "127.0.0.1", 0) as server:
            port = next(iter(server.sockets)).getsockname()[1]
            mock_settings_local.local_host = "127.0.0.1"
            mock_settings_local.local_port = port
            client = ProtectClient(mock_settings_local)
            sample = await client.sample_model_updates(
                ["camera"], duration_seconds=1.0, max_messages=1
            )
            await client.close()

        assert sample["stop_reason"] == "max_messages"
        assert len(sample["messages"]) == 1

    @pytest.mark.asyncio
    async def test_websocket_sample_empty_deadline_is_success(self, mock_settings_local):
        import asyncio

        from websockets.asyncio.server import serve

        async def handler(websocket):
            await asyncio.sleep(1)

        async with serve(handler, "127.0.0.1", 0) as server:
            port = next(iter(server.sockets)).getsockname()[1]
            mock_settings_local.local_host = "127.0.0.1"
            mock_settings_local.local_port = port
            client = ProtectClient(mock_settings_local)
            sample = await client.sample_model_updates(
                ["camera"], duration_seconds=0.05, max_messages=10
            )
            await client.close()

        assert sample["stop_reason"] == "deadline"
        assert sample["messages"] == []

    @pytest.mark.asyncio
    async def test_websocket_sample_rejects_non_object_json(self, mock_settings_local):
        from websockets.asyncio.server import serve

        async def handler(websocket):
            await websocket.send("[]")

        async with serve(handler, "127.0.0.1", 0) as server:
            port = next(iter(server.sockets)).getsockname()[1]
            mock_settings_local.local_host = "127.0.0.1"
            mock_settings_local.local_port = port
            client = ProtectClient(mock_settings_local)
            with pytest.raises(APIError, match="JSON object"):
                await client.sample_model_updates(["camera"], duration_seconds=1.0, max_messages=10)
            await client.close()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("frame", "error"),
        [("not-json", "malformed JSON"), (b"binary", "binary frame")],
    )
    async def test_websocket_sample_rejects_invalid_frames(self, mock_settings_local, frame, error):
        from websockets.asyncio.server import serve

        async def handler(websocket):
            await websocket.send(frame)

        async with serve(handler, "127.0.0.1", 0) as server:
            port = next(iter(server.sockets)).getsockname()[1]
            mock_settings_local.local_host = "127.0.0.1"
            mock_settings_local.local_port = port
            client = ProtectClient(mock_settings_local)
            with pytest.raises(APIError, match=error):
                await client.sample_model_updates(["camera"], duration_seconds=1.0, max_messages=10)
            await client.close()

    @pytest.mark.asyncio
    async def test_websocket_upgrade_timeout_is_error(self, mock_settings_local):
        import asyncio

        from websockets.asyncio.server import serve

        async def process_request(connection, request):
            await asyncio.sleep(1)

        async def handler(websocket):
            pytest.fail("handler must not run before the delayed upgrade completes")

        async with serve(handler, "127.0.0.1", 0, process_request=process_request) as server:
            port = next(iter(server.sockets)).getsockname()[1]
            mock_settings_local.local_host = "127.0.0.1"
            mock_settings_local.local_port = port
            client = ProtectClient(mock_settings_local)
            with pytest.raises(APIError, match="upgrade timed out"):
                await client.sample_model_updates(
                    ["camera"], duration_seconds=0.05, max_messages=10
                )
            await client.close()

    @pytest.mark.asyncio
    async def test_websocket_abnormal_close_is_error(self, mock_settings_local):
        from websockets.asyncio.server import serve

        async def handler(websocket):
            await websocket.close(code=1011, reason="controller failure")

        async with serve(handler, "127.0.0.1", 0) as server:
            port = next(iter(server.sockets)).getsockname()[1]
            mock_settings_local.local_host = "127.0.0.1"
            mock_settings_local.local_port = port
            client = ProtectClient(mock_settings_local)
            with pytest.raises(APIError, match="closed unexpectedly"):
                await client.sample_model_updates(["camera"], duration_seconds=1.0, max_messages=10)
            await client.close()

    @pytest.mark.asyncio
    async def test_websocket_sample_rejects_cloud_connector(self, mock_settings):
        client = ProtectClient(mock_settings)

        with pytest.raises(APIError, match="direct local console access"):
            await client.sample_model_updates(["camera"], duration_seconds=1.0, max_messages=10)

        await client.close()


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
