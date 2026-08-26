"""Regression tests for validated server security boundaries."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastmcp import FastMCP
from starlette.responses import JSONResponse

from src.api import validate_controller_relative_endpoint
from src.config import APIType, Settings
from src.mcp_auth import ConfiguredBearerTokenVerifier, require_authenticated_request
from src.utils.exceptions import ValidationError


def _reload_main(env: dict[str, str]) -> ModuleType:
    """Import ``src.main`` with only the supplied environment."""
    sys.modules.pop("src.main", None)
    with patch.dict(os.environ, env, clear=True):
        return importlib.import_module("src.main")


def test_network_transport_requires_mcp_auth_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Network listeners must fail closed when no client token is configured."""
    monkeypatch.setenv("UNIFI_API_KEY", "controller-key")  # pragma: allowlist secret
    monkeypatch.setenv("MCP_SERVER_TRANSPORT", "streamable_http")
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)

    with pytest.raises(ValueError, match="MCP_AUTH_TOKEN"):
        Settings()


@pytest.mark.asyncio
async def test_network_transport_installs_bearer_auth() -> None:
    """The configured MCP token must actually protect the FastMCP server."""
    main = _reload_main(
        {
            "UNIFI_API_KEY": "controller-key",  # pragma: allowlist secret
            "MCP_SERVER_TRANSPORT": "streamable_http",
            "MCP_AUTH_TOKEN": "mcp-client-token-with-sufficient-entropy",
        }
    )

    assert main.mcp.auth is not None
    assert await main.mcp.auth.verify_token("wrong-token") is None
    assert await main.mcp.auth.verify_token("mcp-client-token-with-sufficient-entropy") is not None


@pytest.mark.asyncio
async def test_network_transport_rejects_unauthenticated_http_requests() -> None:
    """FastMCP's HTTP boundary must return 401 before MCP request handling."""
    token = "mcp-client-token-with-sufficient-entropy"
    main = _reload_main(
        {
            "UNIFI_API_KEY": "controller-key",  # pragma: allowlist secret
            "MCP_SERVER_TRANSPORT": "streamable_http",
            "MCP_AUTH_TOKEN": token,
        }
    )
    app = main.mcp.http_app()
    transport = httpx.ASGITransport(app=app)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "security-test", "version": "1"},
        },
    }

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            missing = await client.post("/mcp", json=payload)
            wrong = await client.post(
                "/mcp", headers={"Authorization": "Bearer wrong"}, json=payload
            )
            accepted = await client.post(
                "/mcp", headers={"Authorization": f"Bearer {token}"}, json=payload
            )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert accepted.status_code != 401


@pytest.mark.asyncio
async def test_custom_network_routes_require_bearer_auth() -> None:
    """Custom A2A-style routes must share the network authentication boundary."""
    token = "mcp-client-token-with-sufficient-entropy"
    server = FastMCP("security-test", auth=ConfiguredBearerTokenVerifier(token))

    @server.custom_route("/custom", methods=["GET"])
    async def protected_route(request):
        require_authenticated_request(request)
        return JSONResponse({"status": "authenticated"})

    app = server.http_app()
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            missing = await client.get("/custom")
            wrong = await client.get("/custom", headers={"Authorization": "Bearer wrong"})
            accepted = await client.get("/custom", headers={"Authorization": f"Bearer {token}"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert accepted.status_code == 200


def test_settings_do_not_load_working_directory_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An untrusted workspace .env must not redirect a process-environment key."""
    (tmp_path / ".env").write_text(
        "UNIFI_API_TYPE=local\n"
        "UNIFI_LOCAL_HOST=attacker-controlled.example\n"
        "UNIFI_LOCAL_VERIFY_SSL=false\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UNIFI_API_KEY", "controller-key")  # pragma: allowlist secret

    settings = Settings()

    assert settings.api_type == APIType.CLOUD_EA
    assert settings.base_url == "https://api.ui.com"


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://attacker.example/capture",
        "http://attacker.example/capture",
        "HTTPS://attacker.example/capture",
        "//attacker.example/capture",
        "attacker.example/capture",
        "/\\attacker.example/capture",
    ],
)
def test_controller_endpoint_rejects_origin_changing_forms(endpoint: str) -> None:
    """Credentialed API requests must accept only one-slash relative paths."""
    with pytest.raises(ValidationError):
        validate_controller_relative_endpoint(endpoint)


def test_controller_endpoint_accepts_normal_unifi_path() -> None:
    """Legitimate UniFi controller paths remain compatible."""
    endpoint = "/proxy/network/api/s/default/stat/device"
    assert validate_controller_relative_endpoint(endpoint) == endpoint


@pytest.mark.asyncio
async def test_debug_tool_rejects_absolute_url_before_creating_client() -> None:
    """Debug endpoints must remain relative to the configured UniFi origin."""
    main = _reload_main(
        {"UNIFI_API_KEY": "controller-key", "DEBUG": "true"}  # pragma: allowlist secret
    )

    with patch("src.api.UniFiClient") as client_class:
        with pytest.raises(ValidationError, match="relative"):
            await main.debug_api_request("https://attacker.example/capture")

    client_class.assert_not_called()


def test_unknown_profile_fails_closed() -> None:
    """A profile typo must never fall back to the complete mutation surface."""
    with pytest.raises(ValueError, match="UNIFI_PROFILE"):
        _reload_main(
            {
                "UNIFI_API_KEY": "controller-key",  # pragma: allowlist secret
                "UNIFI_PROFILE": "netwrok",
            }
        )


def test_api_incompatible_profile_fails_closed() -> None:
    """A known profile with no cloud modules must not fall back to all tools."""
    with pytest.raises(ValueError, match="no tools compatible"):
        _reload_main(
            {
                "UNIFI_API_KEY": "controller-key",  # pragma: allowlist secret
                "UNIFI_PROFILE": "protect",
            }
        )


def test_minimal_profile_is_compatible_with_cloud_mode() -> None:
    """The least-privilege Docker default must remain usable in cloud mode."""
    main = _reload_main(
        {
            "UNIFI_API_KEY": "controller-key",  # pragma: allowlist secret
            "UNIFI_API_TYPE": "cloud-ea",
            "UNIFI_PROFILE": "minimal",
        }
    )

    assert main.mcp._registered_tool_names
    assert "list_sites" in main.mcp._registered_tool_names


def test_read_only_profile_registers_only_read_tools() -> None:
    """The documented read-only profile must exclude every mutation tool."""
    main = _reload_main(
        {
            "UNIFI_API_KEY": "controller-key",  # pragma: allowlist secret
            "UNIFI_PROFILE": "read-only",
        }
    )
    names = main.mcp._registered_tool_names
    allowed_prefixes = ("get_", "list_", "stat_", "search_")

    assert names
    assert "create_network" not in names
    assert all(name == "health_check" or name.startswith(allowed_prefixes) for name in names)


@pytest.mark.asyncio
async def test_debug_delete_requires_confirmation() -> None:
    """The debug tool must not provide an unconfirmed DELETE bypass."""
    main = _reload_main(
        {"UNIFI_API_KEY": "controller-key", "DEBUG": "true"}  # pragma: allowlist secret
    )
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.api.UniFiClient", return_value=mock_client):
        with pytest.raises(ValidationError, match="confirmation"):
            await main.debug_api_request("/proxy/network/api/s/default/rest/networkconf", "DELETE")

    mock_client.delete.assert_not_awaited()
