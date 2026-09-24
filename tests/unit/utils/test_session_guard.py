"""Unit tests for the sessionless Streamable HTTP request guard (issue #173)."""

import json

import pytest
from starlette.applications import Starlette
from starlette.authentication import AuthCredentials, AuthenticationBackend, SimpleUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src.utils.session_guard import SessionlessRequestGuard, _is_initialize_request

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
TOOLS_LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}


class TokenBackend(AuthenticationBackend):
    """Authenticate requests carrying ``Authorization: Bearer good``."""

    async def authenticate(self, conn):
        if conn.headers.get("authorization") == "Bearer good":
            return AuthCredentials(["authenticated"]), SimpleUser("client")
        return None


def make_client(with_auth: bool = False) -> tuple[TestClient, list[bytes]]:
    """Build an app whose /mcp endpoint records the bodies it receives."""
    received: list[bytes] = []

    async def endpoint(request: Request) -> JSONResponse:
        if with_auth and not request.user.is_authenticated:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        received.append(await request.body())
        return JSONResponse({"reached": True})

    middleware = []
    if with_auth:
        middleware.append(Middleware(AuthenticationMiddleware, backend=TokenBackend()))
    middleware.append(Middleware(SessionlessRequestGuard, path="/mcp"))
    app = Starlette(
        routes=[
            Route("/mcp", endpoint, methods=["GET", "POST", "DELETE"]),
            Route("/other", endpoint, methods=["GET"]),
        ],
        middleware=middleware,
    )
    return TestClient(app), received


class TestIsInitializeRequest:
    """Tests for _is_initialize_request."""

    def test_single_initialize(self):
        assert _is_initialize_request(json.dumps(INIT).encode())

    def test_batch_containing_initialize(self):
        assert _is_initialize_request(json.dumps([TOOLS_LIST, INIT]).encode())

    def test_other_method(self):
        assert not _is_initialize_request(json.dumps(TOOLS_LIST).encode())

    @pytest.mark.parametrize("body", [b"", b"not json", b"\xff\xfe", b"42", b'["initialize"]'])
    def test_malformed_or_unexpected(self, body):
        assert not _is_initialize_request(body)


class TestSessionlessRequestGuard:
    """Tests for SessionlessRequestGuard."""

    @pytest.mark.parametrize("method", ["GET", "DELETE"])
    def test_sessionless_get_and_delete_rejected(self, method):
        client, received = make_client()
        response = client.request(method, "/mcp")
        assert response.status_code == 400
        assert response.json()["error"]["message"] == "Bad Request: Missing session ID"
        assert received == []

    def test_sessionless_non_initialize_post_rejected(self):
        client, received = make_client()
        response = client.post("/mcp", json=TOOLS_LIST)
        assert response.status_code == 400
        assert received == []

    def test_sessionless_unparseable_post_rejected(self):
        client, received = make_client()
        response = client.post("/mcp", content=b"{not json")
        assert response.status_code == 400
        assert received == []

    def test_initialize_post_passes_with_body_intact(self):
        client, received = make_client()
        body = json.dumps(INIT).encode()
        response = client.post("/mcp", content=body)
        assert response.status_code == 200
        assert received == [body]

    @pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
    def test_requests_with_session_id_pass(self, method):
        client, received = make_client()
        response = client.request(method, "/mcp", headers={"mcp-session-id": "abc"})
        assert response.status_code == 200
        assert len(received) == 1

    def test_trailing_slash_path_is_guarded(self):
        client, received = make_client()
        response = client.get("/mcp/", follow_redirects=False)
        assert response.status_code == 400
        assert received == []

    def test_other_paths_untouched(self):
        client, received = make_client()
        response = client.get("/other")
        assert response.status_code == 200
        assert len(received) == 1

    def test_unauthenticated_request_left_to_auth_layer(self):
        client, received = make_client(with_auth=True)
        response = client.get("/mcp")
        assert response.status_code == 401

    def test_authenticated_sessionless_get_rejected(self):
        client, received = make_client(with_auth=True)
        response = client.get("/mcp", headers={"Authorization": "Bearer good"})
        assert response.status_code == 400
        assert received == []

    def test_authenticated_initialize_passes(self):
        client, received = make_client(with_auth=True)
        response = client.post("/mcp", json=INIT, headers={"Authorization": "Bearer good"})
        assert response.status_code == 200
        assert len(received) == 1

    def test_root_path_normalisation(self):
        guard = SessionlessRequestGuard(app=None, path="/")  # type: ignore[arg-type]
        assert guard.path == "/"
