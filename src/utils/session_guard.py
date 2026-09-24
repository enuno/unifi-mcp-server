"""ASGI guard against sessions leaked by sessionless Streamable HTTP requests.

The ``mcp`` SDK's ``StreamableHTTPSessionManager`` creates and registers a new
transport, plus a server task, for *every* request that arrives without an
``mcp-session-id`` header, before it checks whether that request is an
``initialize`` call. A request the transport then rejects (a ``GET`` with a
bad ``Accept`` header is answered ``406``; one without a session ID is
answered ``400``) leaves its session registered for the lifetime of the
process, because no idle timeout is configured and FastMCP does not expose
one. A health check polling ``/mcp`` once a minute leaked ~54 MiB/day this way
(issue #173).

Per the MCP specification, only an ``initialize`` POST may start a session.
This middleware answers every other sessionless request itself, with the same
``400`` the SDK would have sent, so no session is ever created for it.
"""

from __future__ import annotations

import json
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

MCP_SESSION_ID_HEADER = b"mcp-session-id"
_GUARDED_METHODS = frozenset({"GET", "POST", "DELETE"})


def _is_initialize_request(body: bytes) -> bool:
    """Return True when a JSON-RPC body is (or, as a batch, contains) ``initialize``."""
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return False
    messages = payload if isinstance(payload, list) else [payload]
    return any(isinstance(m, dict) and m.get("method") == "initialize" for m in messages)


def _bad_request_body() -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "server-error",
            "error": {"code": -32600, "message": "Bad Request: Missing session ID"},
        }
    ).encode()


class SessionlessRequestGuard:
    """Reject sessionless MCP requests that could not start a session.

    Requests that are not to the MCP endpoint, carry an ``mcp-session-id``,
    or are not yet authenticated (the auth layer answers those with ``401``
    without creating a session) pass through untouched.
    """

    def __init__(self, app: ASGIApp, path: str = "/mcp") -> None:
        """Wrap ``app``, guarding requests to the MCP endpoint at ``path``."""
        self.app = app
        self.path = path.rstrip("/") or "/"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI request."""
        if not self._should_guard(scope):
            await self.app(scope, receive, send)
            return

        if scope["method"] != "POST":
            await self._reject(send)
            return

        body = await self._read_body(receive)
        if not _is_initialize_request(body):
            await self._reject(send)
            return

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    def _should_guard(self, scope: Scope) -> bool:
        if scope["type"] != "http" or scope.get("method") not in _GUARDED_METHODS:
            return False
        if (scope.get("path", "").rstrip("/") or "/") != self.path:
            return False
        if any(name == MCP_SESSION_ID_HEADER for name, _ in scope.get("headers", [])):
            return False
        user: Any = scope.get("user")
        # With auth configured, AuthenticationMiddleware sets scope["user"];
        # unauthenticated requests are left to it (401, no session created).
        return user is None or bool(getattr(user, "is_authenticated", False))

    @staticmethod
    async def _read_body(receive: Receive) -> bytes:
        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        return b"".join(chunks)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = _bad_request_body()
        await send(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
