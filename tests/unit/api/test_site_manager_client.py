"""Unit tests for src/api/site_manager_client.py.

The real ``httpx.AsyncClient`` is kept and given an ``httpx.MockTransport``,
so requests go through httpx's URL joining and status handling without
touching the network.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from unittest.mock import MagicMock

import httpx
import pytest

from src.api.site_manager_client import SiteManagerClient
from src.utils.exceptions import APIError, AuthenticationError, NetworkError, ResourceNotFoundError

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def settings() -> MagicMock:
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.request_timeout = 5
    settings.get_headers.return_value = {"X-API-Key": "test-key"}  # pragma: allowlist secret
    return settings


def _client(settings: MagicMock, handler: Handler, *, authenticated: bool = True):
    client = SiteManagerClient(settings)
    client.client = httpx.AsyncClient(
        base_url="https://api.ui.com/v1/",
        headers=settings.get_headers(),
        transport=httpx.MockTransport(handler),
    )
    client._authenticated = authenticated
    return client


def _recorder(response: httpx.Response | None = None):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response if response is not None else httpx.Response(200, json={"data": []})

    return seen, handler


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_context_manager_closes(self, settings: MagicMock) -> None:
        _, handler = _recorder()
        client = _client(settings, handler)
        async with client as entered:
            assert entered is client
        assert client.client.is_closed

    def test_constructor_uses_settings(self, settings: MagicMock) -> None:
        client = SiteManagerClient(settings)
        assert str(client.client.base_url) == "https://api.ui.com/v1/"
        assert client.client.headers["X-API-Key"] == "test-key"
        assert client.is_authenticated is False


class TestAuthenticate:
    @pytest.mark.asyncio
    async def test_success(self, settings: MagicMock) -> None:
        seen, handler = _recorder()
        client = _client(settings, handler, authenticated=False)

        await client.authenticate()

        assert client.is_authenticated
        assert seen[0].url.path == "/v1/sites"

    @pytest.mark.asyncio
    async def test_non_200_fails(self, settings: MagicMock) -> None:
        _, handler = _recorder(httpx.Response(403))
        client = _client(settings, handler, authenticated=False)

        with pytest.raises(AuthenticationError, match="403"):
            await client.authenticate()
        assert not client.is_authenticated

    @pytest.mark.asyncio
    async def test_network_failure_wrapped(self, settings: MagicMock) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down", request=request)

        client = _client(settings, handler, authenticated=False)
        with pytest.raises(AuthenticationError, match="down"):
            await client.authenticate()

    @pytest.mark.asyncio
    async def test_get_authenticates_lazily(self, settings: MagicMock) -> None:
        seen, handler = _recorder()
        client = _client(settings, handler, authenticated=False)

        await client.get("hosts")

        assert [r.url.path for r in seen] == ["/v1/sites", "/v1/hosts"]


class TestGet:
    @pytest.mark.asyncio
    async def test_strips_leading_slash_and_sends_params(self, settings: MagicMock) -> None:
        seen, handler = _recorder(httpx.Response(200, json={"data": [1]}))
        client = _client(settings, handler)

        assert await client.get("/sites", params={"limit": 5}) == {"data": [1]}
        assert seen[0].url.path == "/v1/sites"
        assert seen[0].url.params["limit"] == "5"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status", "error"),
        [(401, AuthenticationError), (404, ResourceNotFoundError), (500, APIError)],
    )
    async def test_status_errors(self, settings: MagicMock, status: int, error: type) -> None:
        _, handler = _recorder(httpx.Response(status, text="nope"))
        client = _client(settings, handler)

        with pytest.raises(error):
            await client.get("sites")

    @pytest.mark.asyncio
    async def test_api_error_carries_status(self, settings: MagicMock) -> None:
        _, handler = _recorder(httpx.Response(502, text="bad gateway"))
        client = _client(settings, handler)

        with pytest.raises(APIError) as excinfo:
            await client.get("sites")
        assert excinfo.value.status_code == 502
        assert "bad gateway" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_network_error(self, settings: MagicMock) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down", request=request)

        client = _client(settings, handler)
        with pytest.raises(NetworkError):
            await client.get("sites")

    @pytest.mark.asyncio
    async def test_unexpected_error_wrapped(self, settings: MagicMock) -> None:
        _, handler = _recorder(httpx.Response(200, text="not json"))
        client = _client(settings, handler)

        with pytest.raises(APIError, match="Unexpected error"):
            await client.get("sites")


class TestMutate:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["post", "put", "patch"])
    async def test_sends_json_body(self, settings: MagicMock, method: str) -> None:
        seen, handler = _recorder(httpx.Response(200, json={"ok": True}))
        client = _client(settings, handler)

        result = await getattr(client, method)("/sdwan/configs", json_data={"a": 1})

        assert result == {"ok": True}
        assert seen[0].method == method.upper()
        assert seen[0].url.path == "/v1/sdwan/configs"
        assert json.loads(seen[0].content) == {"a": 1}

    @pytest.mark.asyncio
    async def test_post_without_body(self, settings: MagicMock) -> None:
        seen, handler = _recorder(httpx.Response(200, json={}))
        client = _client(settings, handler)

        await client.post("sdwan/configs")

        assert seen[0].content == b""

    @pytest.mark.asyncio
    async def test_delete_empty_response(self, settings: MagicMock) -> None:
        seen, handler = _recorder(httpx.Response(204))
        client = _client(settings, handler)

        result = await client.delete("hosts/h1")

        assert result == {}
        assert seen[0].method == "DELETE"

    @pytest.mark.asyncio
    async def test_authenticates_lazily(self, settings: MagicMock) -> None:
        seen, handler = _recorder()
        client = _client(settings, handler, authenticated=False)

        await client.put("hosts/h1", json_data={})

        assert [r.method for r in seen] == ["GET", "PUT"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status", "error"),
        [(401, AuthenticationError), (404, ResourceNotFoundError), (409, APIError)],
    )
    async def test_status_errors(self, settings: MagicMock, status: int, error: type) -> None:
        _, handler = _recorder(httpx.Response(status, text="nope"))
        client = _client(settings, handler)

        with pytest.raises(error):
            await client.post("sdwan/configs", json_data={})

    @pytest.mark.asyncio
    async def test_network_error(self, settings: MagicMock) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadError("reset", request=request)

        client = _client(settings, handler)
        with pytest.raises(NetworkError):
            await client.delete("hosts/h1")

    @pytest.mark.asyncio
    async def test_unexpected_error_wrapped(self, settings: MagicMock) -> None:
        _, handler = _recorder(httpx.Response(200, text="not json"))
        client = _client(settings, handler)

        with pytest.raises(APIError, match="Unexpected error"):
            await client.patch("hosts/h1", json_data={})


class TestEndpoints:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("call", "path", "params"),
        [
            (lambda c: c.list_sites(), "/v1/sites", {}),
            (
                lambda c: c.list_sites(limit=10, offset=20),
                "/v1/sites",
                {"limit": "10", "offset": "20"},
            ),
            (lambda c: c.get_site_health(), "/v1/sites/health", {}),
            (lambda c: c.get_site_health("s1"), "/v1/sites/s1/health", {}),
            (lambda c: c.get_internet_health(), "/v1/internet/health", {}),
            (lambda c: c.get_internet_health("s1"), "/v1/sites/s1/internet/health", {}),
            (lambda c: c.list_vantage_points(), "/v1/vantage-points", {}),
            (lambda c: c.get_isp_metrics("s1"), "/v1/sites/s1/isp/metrics", {}),
            (lambda c: c.query_isp_metrics(), "/v1/isp/metrics", {}),
            (
                lambda c: c.query_isp_metrics("s1", "2026-01-01T00:00:00Z"),
                "/v1/isp/metrics",
                {"site_id": "s1", "start_time": "2026-01-01T00:00:00Z"},
            ),
            (lambda c: c.list_sdwan_configs(), "/v1/sdwan/configs", {}),
            (lambda c: c.get_sdwan_config("c1"), "/v1/sdwan/configs/c1", {}),
            (lambda c: c.get_sdwan_config_status("c1"), "/v1/sdwan/configs/c1/status", {}),
            (lambda c: c.list_hosts(), "/v1/hosts", {}),
            (lambda c: c.list_hosts(limit=5), "/v1/hosts", {"limit": "5"}),
            (lambda c: c.get_host("h1"), "/v1/hosts/h1", {}),
            (lambda c: c.get_version_control(), "/v1/version", {}),
        ],
    )
    async def test_paths(self, settings: MagicMock, call, path: str, params: dict) -> None:
        seen, handler = _recorder()
        client = _client(settings, handler)

        await call(client)

        assert seen[0].url.path == path
        assert dict(seen[0].url.params) == params


class TestReplyShapes:
    """Array replies are returned as arrays, not cast to dict (issue #222)."""

    @pytest.mark.asyncio
    async def test_get_returns_array_reply(self, settings: MagicMock) -> None:
        _, handler = _recorder(httpx.Response(200, json=[{"_id": "r1"}]))
        client = _client(settings, handler)

        assert await client.get("connector/consoles/c1/proxy/network/v2/x") == [{"_id": "r1"}]

    @pytest.mark.asyncio
    async def test_mutate_returns_array_reply(self, settings: MagicMock) -> None:
        _, handler = _recorder(httpx.Response(200, json=[]))
        client = _client(settings, handler)

        assert await client.post("connector/consoles/c1/proxy/network/v2/x") == []

    @pytest.mark.asyncio
    async def test_typed_wrapper_passes_array_reply_through(self, settings: MagicMock) -> None:
        """Some deployments answer hosts and vantage-points with a bare array;
        the tools handle that shape, so the wrapper must not reject it."""
        _, handler = _recorder(httpx.Response(200, json=[{"id": "h1"}]))
        client = _client(settings, handler)

        assert await client.list_hosts() == [{"id": "h1"}]
