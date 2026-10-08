"""Tests for the GET /metrics custom route (bearer-token behaviour)."""

from __future__ import annotations

import importlib
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request

from src.utils.metrics import REGISTRY

_BASE_ENV = {
    "UNIFI_API_KEY": "test-key",
    "UNIFI_API_TYPE": "cloud-ea",
    "AGNOST_ENABLED": "false",
}


def _load_main() -> Any:
    """Import src.main with a clean module cache and a valid minimal env."""
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]
    with patch.dict("os.environ", _BASE_ENV, clear=False):
        return importlib.import_module("src.main")


class StubServer:
    """Capture custom_route registrations like FastMCP does."""

    def __init__(self) -> None:
        self.routes: dict[tuple[str, tuple[str, ...]], Any] = {}

    def custom_route(self, path: str, methods: list[str] | None = None) -> Any:
        def decorator(handler: Any) -> Any:
            self.routes[(path, tuple(methods or []))] = handler
            return handler

        return decorator


def _request(authorization: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/metrics",
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope)


async def test_metrics_route_requires_bearer_token_when_auth_configured() -> None:
    main = _load_main()
    auth_provider = MagicMock()
    auth_provider.verify_token = AsyncMock(return_value={"client_id": "mcp-client"})

    server = StubServer()
    with patch.object(REGISTRY, "render", return_value="# fake\n") as mock_render:
        main.register_metrics_route(server, auth_provider)  # type: ignore[arg-type]
        handler = server.routes[("/metrics", ("GET",))]

        unauthorized = await handler(_request())
        assert unauthorized.status_code == 401
        assert unauthorized.headers["WWW-Authenticate"] == "Bearer"
        mock_render.assert_not_called()

        wrong_scheme = await handler(_request("Basic abc"))
        assert wrong_scheme.status_code == 401

        ok = await handler(_request("Bearer good-token"))
        assert ok.status_code == 200
        assert ok.headers["content-type"].startswith("text/plain")
        mock_render.assert_called_once()


async def test_metrics_route_serves_without_auth_when_no_provider() -> None:
    main = _load_main()
    server = StubServer()

    with patch.object(REGISTRY, "render", return_value="# fake\n") as mock_render:
        main.register_metrics_route(server, None)  # type: ignore[arg-type]
        handler = server.routes[("/metrics", ("GET",))]

        response = await handler(_request())
        assert response.status_code == 200
        mock_render.assert_called_once()
