"""ASGI middleware that slows bearer-token guessing on the HTTP transports.

Every route behind the bearer token (``/mcp``, ``/a2a/*``, ``/metrics``)
answers a wrong or missing token with ``401`` and nothing else, so without a
limit a client can try tokens as fast as the server answers. This middleware
counts ``401`` responses per client address in a sliding window. Once a client
reaches ``max_failures`` within ``window_seconds``, its requests are answered
``429`` with ``Retry-After`` until the oldest failure in the window expires,
without reaching the token check.

A successful request does not clear the count, so a client cannot interleave
valid calls to keep guessing. ``/healthz`` and the webhook receiver are never
limited or counted: a probe behind the same address as a misconfigured client
keeps working, and a controller with a wrong webhook secret neither locks out
MCP clients nor loses its own deliveries to someone else's bad token.

A failure is only known when its ``401`` starts, so each request still waiting
for its first response holds a slot until then. An address is refused once its
recent failures plus its waiting requests reach ``max_failures`` plus
``concurrency_slack``: parallel guesses cannot outrun the count by more than
the slack, and a client with no failures can still have that many requests
waiting at once.

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

#: Requests per address that may wait for their first response at once, on
#: top of ``max_failures``.
DEFAULT_CONCURRENCY_SLACK = 64

#: Paths never limited or counted.
DEFAULT_EXEMPT_PATHS = ("/healthz", "/webhooks/unifi")


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
        exempt_paths: tuple[str, ...] = DEFAULT_EXEMPT_PATHS,
        max_clients: int = DEFAULT_MAX_CLIENTS,
        concurrency_slack: int = DEFAULT_CONCURRENCY_SLACK,
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
            concurrency_slack: Requests per address that may wait for their
                first response at once, beyond ``max_failures``
            clock: Monotonic time source (for tests)
        """
        self.app = app
        self.max_failures = max_failures
        self.window = window_seconds
        self.exempt_paths = frozenset(p.rstrip("/") or "/" for p in exempt_paths)
        self.max_clients = max_clients
        self._clock = clock
        self.concurrency_slack = max(0, concurrency_slack)
        self._failures: dict[str, deque[float]] = {}
        self._waiting: dict[str, int] = {}

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
        failed = len(failures) if failures is not None else 0
        waiting = self._waiting.get(address, 0)
        if failed >= self.max_failures or (
            failed + waiting >= self.max_failures + self.concurrency_slack
        ):
            # Over the failure budget, or too many unanswered requests that
            # could each still turn into a failure.
            oldest = failures[0] if failures else now
            await self._reject(send, retry_after=oldest + self.window - now)
            return

        self._waiting[address] = waiting + 1
        released = False

        def release() -> None:
            nonlocal released
            if released:
                return
            released = True
            left = self._waiting.get(address, 1) - 1
            if left > 0:
                self._waiting[address] = left
            else:
                self._waiting.pop(address, None)

        async def counting_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                if message["status"] == 401:
                    self._record_failure(address)
                release()
            await send(message)

        try:
            await self.app(scope, receive, counting_send)
        finally:
            release()

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
