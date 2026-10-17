"""ASGI middleware that slows bearer-token guessing on the HTTP transports.

Every route behind the bearer token (``/mcp``, ``/a2a/*``, ``/metrics``)
answers a wrong or missing token with ``401`` and nothing else, so without a
limit a client can try tokens as fast as the server answers. This middleware
counts ``401`` responses per client address in a sliding window. Once a client
reaches ``max_failures`` within ``window_seconds``, its requests are answered
``429`` with ``Retry-After`` until the oldest failure in the window expires,
without reaching the token check.

A successful request does not clear the count, so a client cannot interleave
valid calls to keep guessing. ``/healthz`` is never limited, so a probe behind
the same address as a misconfigured client keeps working.

The client address is the one uvicorn reports. Behind a reverse proxy that is
the proxy's address unless uvicorn trusts its ``X-Forwarded-For`` (uvicorn
trusts ``127.0.0.1`` by default; see ``FORWARDED_ALLOW_IPS``), and then every
client shares one budget: a client guessing tokens locks the others out for
up to one window. Set ``MCP_AUTH_MAX_FAILURES=0`` to turn the limit off.
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .logger import get_logger

logger = get_logger(__name__)

#: Client addresses tracked at once. Past this, addresses with no failure left
#: in the window are dropped first, then the least recently added.
DEFAULT_MAX_CLIENTS = 10_000


def _too_many_requests_body() -> bytes:
    return json.dumps(
        {
            "error": "too_many_requests",
            "error_description": "Too many failed authentication attempts",
        }
    ).encode()


class BearerFailureLimiter:
    """Answer ``429`` to a client address after too many ``401`` responses."""

    def __init__(
        self,
        app: ASGIApp,
        max_failures: int = 10,
        window_seconds: float = 60.0,
        exempt_paths: tuple[str, ...] = ("/healthz",),
        max_clients: int = DEFAULT_MAX_CLIENTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Wrap ``app``.

        Args:
            app: The ASGI application to protect
            max_failures: ``401`` responses allowed per address per window;
                0 or less disables the limit
            window_seconds: Length of the sliding window
            exempt_paths: Paths that are never limited or counted
            max_clients: Most client addresses tracked at once
            clock: Monotonic time source (for tests)
        """
        self.app = app
        self.max_failures = max_failures
        self.window = window_seconds
        self.exempt_paths = frozenset(p.rstrip("/") or "/" for p in exempt_paths)
        self.max_clients = max_clients
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI request."""
        if (
            self.max_failures <= 0
            or scope["type"] != "http"
            or (scope.get("path", "").rstrip("/") or "/") in self.exempt_paths
        ):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        address = client[0] if client else "unknown"
        now = self._clock()
        failures = self._recent_failures(address, now)
        if failures is not None and len(failures) >= self.max_failures:
            await self._reject(send, retry_after=failures[0] + self.window - now)
            return

        async def counting_send(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] == 401:
                self._record_failure(address)
            await send(message)

        await self.app(scope, receive, counting_send)

    def _recent_failures(self, address: str, now: float) -> deque[float] | None:
        failures = self._failures.get(address)
        if failures is None:
            return None
        while failures and failures[0] <= now - self.window:
            failures.popleft()
        if not failures:
            del self._failures[address]
            return None
        return failures

    def _record_failure(self, address: str) -> None:
        now = self._clock()
        failures = self._failures.get(address)
        if failures is None:
            if len(self._failures) >= self.max_clients:
                self._evict(now)
            failures = self._failures[address] = deque()
        failures.append(now)
        if len(failures) == self.max_failures:
            logger.warning(
                "Bearer authentication failed %d times in %.0fs from %s; "
                "answering 429 until the window clears",
                len(failures),
                self.window,
                address,
            )

    def _evict(self, now: float) -> None:
        for address in list(self._failures):
            self._recent_failures(address, now)  # drops an address with none left
        while len(self._failures) >= self.max_clients:
            del self._failures[next(iter(self._failures))]

    @staticmethod
    async def _reject(send: Send, retry_after: float) -> None:
        body = _too_many_requests_body()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"retry-after", str(max(1, math.ceil(retry_after))).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
