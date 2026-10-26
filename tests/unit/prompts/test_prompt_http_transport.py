"""HTTP-transport tests for the native prompt support.

These drive the real Streamable HTTP endpoint with JSON-RPC requests, so they
prove that a gateway or a remote client sees the prompts over the wire. They
also cover the transport authentication, because prompt retrieval must sit
behind the same bearer-token guard as the tools.

The pattern follows tests/unit/test_transport_auth.py: ``src.main`` is
re-imported with a known environment so the server is configured for the
network transport.
"""

from __future__ import annotations

import importlib
import json
import sys
from typing import Any
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

_BASE_ENV = {
    "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
    "UNIFI_API_TYPE": "local",
    "UNIFI_LOCAL_HOST": "127.0.0.1",
    "AGNOST_ENABLED": "false",
}

_ACCEPT = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

_TOKEN = "s3cr3t-token"
_AUTH_HEADERS = {**_ACCEPT, "Authorization": f"Bearer {_TOKEN}"}


def _reload_main(**extra_env: str) -> Any:
    """Re-import src.main with a clean module cache under a known env."""
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]
    with patch.dict("os.environ", {**_BASE_ENV, **extra_env}, clear=False):
        return importlib.import_module("src.main")


def _http_app(**extra_env: str) -> Any:
    """Return the authenticated HTTP app for the MCP endpoint."""
    main = _reload_main(MCP_SERVER_TRANSPORT="streamable_http", MCP_AUTH_TOKEN=_TOKEN, **extra_env)
    return main.mcp.http_app(transport="streamable-http")


def _init_body() -> dict[str, Any]:
    """Return the JSON-RPC body of an initialize request."""
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


def _parse_body(response: Any) -> dict[str, Any]:
    """Return the JSON-RPC body from a response.

    The Streamable HTTP endpoint answers with ``text/event-stream``, so the
    payload arrives as an SSE ``data:`` line. Some responses come back as
    plain JSON, so both shapes are accepted.
    """
    text = response.text
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:") :].strip())
        raise AssertionError(f"no SSE data line in response: {text!r}")
    return json.loads(text)


def _rpc(
    client: TestClient,
    method: str,
    request_id: int,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    session_id: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """Send one JSON-RPC request over the MCP endpoint and return it."""
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    request_headers = dict(headers or _AUTH_HEADERS)
    if session_id:
        request_headers["mcp-session-id"] = session_id
    response = client.post("/mcp/", json=body, headers=request_headers)
    return response.status_code, _parse_body(response)


def _initialized_client(app: Any) -> tuple[TestClient, str | None]:
    """Return a TestClient that has completed the MCP handshake.

    The Streamable HTTP transport hands out a session id in the initialize
    response and requires it on every later request, so it is returned
    alongside the client.
    """
    client = TestClient(app)
    client.__enter__()
    response = client.post("/mcp/", json=_init_body(), headers=_AUTH_HEADERS)
    assert response.status_code < 400, response.text
    session_id = response.headers.get("mcp-session-id")
    client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers={**_AUTH_HEADERS, **({"mcp-session-id": session_id} if session_id else {})},
    )
    return client, session_id


class TestHttpInitialize:
    def test_initialize_advertises_the_prompts_capability(self) -> None:
        with TestClient(_http_app()) as client:
            response = client.post("/mcp/", json=_init_body(), headers=_AUTH_HEADERS)
        assert response.status_code < 400, response.text
        body = _parse_body(response)
        assert "prompts" in body["result"]["capabilities"]

    def test_initialize_rejects_an_unauthenticated_request(self) -> None:
        with TestClient(_http_app()) as client:
            response = client.post("/mcp/", json=_init_body(), headers=_ACCEPT)
        assert response.status_code == 401


class TestHttpPromptOperations:
    def test_prompts_list_over_http(self) -> None:
        app = _http_app()
        client, session_id = _initialized_client(app)
        try:
            status, body = _rpc(client, "prompts/list", 2, session_id=session_id)
        finally:
            client.__exit__(None, None, None)
        assert status == 200, body
        names = [prompt["name"] for prompt in body["result"]["prompts"]]
        assert "network_health_check" in names
        assert "plan_network_change" in names

    def test_prompts_list_includes_argument_metadata_over_http(self) -> None:
        app = _http_app()
        client, session_id = _initialized_client(app)
        try:
            status, body = _rpc(client, "prompts/list", 2, session_id=session_id)
        finally:
            client.__exit__(None, None, None)
        assert status == 200, body
        prompts = {prompt["name"]: prompt for prompt in body["result"]["prompts"]}
        arguments = {
            argument["name"]: argument
            for argument in prompts["network_health_check"].get("arguments", [])
        }
        assert arguments["site_id"]["required"] is True
        assert arguments["focus"]["required"] is False
        assert arguments["site_id"]["description"]

    def test_prompts_get_over_http(self) -> None:
        app = _http_app()
        client, session_id = _initialized_client(app)
        try:
            status, body = _rpc(
                client,
                "prompts/get",
                3,
                {"name": "network_health_check", "arguments": {"site_id": "default"}},
                session_id=session_id,
            )
        finally:
            client.__exit__(None, None, None)
        assert status == 200, body
        messages = body["result"]["messages"]
        assert messages
        assert messages[0]["role"] == "user"
        assert "default" in messages[0]["content"]["text"]

    def test_prompts_get_rejects_a_missing_argument_over_http(self) -> None:
        app = _http_app()
        client, session_id = _initialized_client(app)
        try:
            status, body = _rpc(
                client,
                "prompts/get",
                4,
                {"name": "network_health_check", "arguments": {}},
                session_id=session_id,
            )
        finally:
            client.__exit__(None, None, None)
        assert status == 200, body
        assert "error" in body
        assert "site_id" in body["error"]["message"]

    def test_prompts_get_rejects_an_unknown_prompt_over_http(self) -> None:
        app = _http_app()
        client, session_id = _initialized_client(app)
        try:
            status, body = _rpc(
                client, "prompts/get", 5, {"name": "no_such_prompt"}, session_id=session_id
            )
        finally:
            client.__exit__(None, None, None)
        assert status == 200, body
        assert "error" in body


class TestHttpPromptAuthentication:
    """Prompt retrieval must sit behind the transport's bearer-token guard."""

    @pytest.mark.parametrize(
        "headers",
        [{}, {"Authorization": "Bearer wrong"}, {"Authorization": _TOKEN}],
        ids=["missing", "wrong-token", "no-scheme"],
    )
    def test_prompts_are_rejected_without_a_valid_token(self, headers: dict[str, str]) -> None:
        app = _http_app()
        with TestClient(app) as client:
            response = client.post("/mcp/", json=_init_body(), headers={**_ACCEPT, **headers})
        assert response.status_code == 401

    def test_prompts_list_rejects_an_unauthenticated_request(self) -> None:
        app = _http_app()
        with TestClient(app) as client:
            response = client.post(
                "/mcp/",
                json={"jsonrpc": "2.0", "id": 2, "method": "prompts/list"},
                headers=_ACCEPT,
            )
        assert response.status_code == 401

    def test_prompts_get_rejects_an_unauthenticated_request(self) -> None:
        app = _http_app()
        with TestClient(app) as client:
            response = client.post(
                "/mcp/",
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "prompts/get",
                    "params": {"name": "network_health_check", "arguments": {"site_id": "default"}},
                },
                headers=_ACCEPT,
            )
        assert response.status_code == 401

    def test_prompts_are_served_with_a_valid_token(self) -> None:
        app = _http_app()
        client, session_id = _initialized_client(app)
        try:
            status, body = _rpc(client, "prompts/list", 6, session_id=session_id)
        finally:
            client.__exit__(None, None, None)
        assert status == 200, body
        assert body["result"]["prompts"]


def teardown_module(module: Any) -> None:  # noqa: D401
    """Restore a pristine src.main for any later tests in the session."""
    _reload_main()
