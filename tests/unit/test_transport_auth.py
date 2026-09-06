"""Tests for MCP network-transport authentication.

Covers the guard that refuses to open a network listener without a bearer
token, the token parsing on ``Settings``, and an end-to-end assertion that
the streamable-http endpoint answers 401 without a valid token and accepts a
request that carries it.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import pytest

from src.config import Settings, TransportMode

_BASE_ENV = {
    "UNIFI_API_KEY": "test-key",
    "UNIFI_API_TYPE": "local",
    "UNIFI_LOCAL_HOST": "127.0.0.1",
    "AGNOST_ENABLED": "false",
}


def _reload_main(**extra_env):
    """Re-import src.main with a clean module cache under a known env."""
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]
    with patch.dict("os.environ", {**_BASE_ENV, **extra_env}, clear=False):
        return importlib.import_module("src.main")


def _settings(**extra_env) -> Settings:
    """Build Settings from _BASE_ENV plus the given overrides."""
    with patch.dict("os.environ", {**_BASE_ENV, **extra_env}, clear=False):
        return Settings()


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


def test_server_host_defaults_to_loopback() -> None:
    """The bind address defaults to loopback, not 0.0.0.0."""
    assert Settings.model_fields["server_host"].default == "127.0.0.1"


def test_auth_tokens_empty_when_unset() -> None:
    settings = _settings()
    assert settings.mcp_auth_token is None
    assert settings.mcp_auth_tokens == []


def test_auth_tokens_split_on_comma() -> None:
    settings = _settings(MCP_AUTH_TOKEN=" a , b ,, c ")
    assert settings.mcp_auth_tokens == ["a", "b", "c"]


# --------------------------------------------------------------------------- #
# build_auth_provider / ensure_network_transport_authenticated
# --------------------------------------------------------------------------- #


def test_build_auth_provider_none_without_token() -> None:
    main = _reload_main()
    assert main.build_auth_provider(_settings()) is None


def test_build_auth_provider_verifier_with_token() -> None:
    from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

    main = _reload_main()
    provider = main.build_auth_provider(_settings(MCP_AUTH_TOKEN="tok-1,tok-2"))
    assert isinstance(provider, StaticTokenVerifier)


def test_stdio_never_requires_a_token() -> None:
    main = _reload_main()
    # No SystemExit even though no token is configured.
    main.ensure_network_transport_authenticated(_settings(MCP_SERVER_TRANSPORT="stdio"), None)


@pytest.mark.parametrize("transport", ["http", "sse", "streamable_http"])
def test_network_transport_refuses_without_token(transport) -> None:
    main = _reload_main()
    settings = _settings(MCP_SERVER_TRANSPORT=transport)
    assert settings.server_transport != TransportMode.STDIO
    with pytest.raises(SystemExit) as excinfo:
        main.ensure_network_transport_authenticated(settings, None)
    assert "MCP_AUTH_TOKEN" in str(excinfo.value)


@pytest.mark.parametrize("transport", ["http", "sse", "streamable_http"])
def test_network_transport_allowed_with_provider(transport) -> None:
    main = _reload_main()
    settings = _settings(MCP_SERVER_TRANSPORT=transport, MCP_AUTH_TOKEN="tok")
    provider = main.build_auth_provider(settings)
    # Must not raise.
    main.ensure_network_transport_authenticated(settings, provider)


# --------------------------------------------------------------------------- #
# End-to-end: the HTTP endpoint enforces the token
# --------------------------------------------------------------------------- #


def _init_request() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }


def _http_app():
    main = _reload_main(MCP_SERVER_TRANSPORT="streamable_http", MCP_AUTH_TOKEN="s3cr3t-token")
    return main.mcp.http_app(transport="streamable-http")


_ACCEPT = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def test_http_endpoint_rejects_missing_token() -> None:
    from starlette.testclient import TestClient

    with TestClient(_http_app()) as client:
        resp = client.post("/mcp/", json=_init_request(), headers=_ACCEPT)
    assert resp.status_code == 401


def test_http_endpoint_rejects_wrong_token() -> None:
    from starlette.testclient import TestClient

    headers = {**_ACCEPT, "Authorization": "Bearer wrong"}
    with TestClient(_http_app()) as client:
        resp = client.post("/mcp/", json=_init_request(), headers=headers)
    assert resp.status_code == 401


def test_http_endpoint_accepts_valid_token() -> None:
    from starlette.testclient import TestClient

    headers = {**_ACCEPT, "Authorization": "Bearer s3cr3t-token"}
    with TestClient(_http_app()) as client:
        resp = client.post("/mcp/", json=_init_request(), headers=headers)
    # A valid token clears authentication; the MCP handshake then answers 2xx.
    assert resp.status_code < 400


# Restore a pristine src.main for any later tests in the session.
def teardown_module(module) -> None:  # noqa: D401
    _reload_main()
