"""BearerFailureLimiter: 429 after too many 401s from one client address."""

from __future__ import annotations

import contextlib

import httpx
import pytest
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from src.utils.auth_throttle import BearerFailureLimiter

TOKEN = "a-long-enough-test-token-value"  # pragma: allowlist secret


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def _protected(request: Request) -> Response:
    if request.headers.get("authorization") != f"Bearer {TOKEN}":
        return JSONResponse({"error": "invalid_token"}, status_code=401)
    return JSONResponse({"ok": True})


async def _healthz(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


def _app(clock: FakeClock, **kwargs) -> Starlette:
    return Starlette(
        routes=[Route("/mcp", _protected, methods=["GET"]), Route("/healthz", _healthz)],
        middleware=[Middleware(BearerFailureLimiter, clock=clock, **kwargs)],
    )


def _client(app, address: str = "203.0.113.7") -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(address, 51000))
    return httpx.AsyncClient(transport=transport, base_url="http://t")


BAD = {"authorization": "Bearer wrong"}
GOOD = {"authorization": f"Bearer {TOKEN}"}


@pytest.mark.asyncio
async def test_locks_out_after_max_failures_and_recovers() -> None:
    clock = FakeClock()
    app = _app(clock, max_failures=3, window_seconds=60)
    async with _client(app) as client:
        for _ in range(3):
            assert (await client.get("/mcp", headers=BAD)).status_code == 401

        blocked = await client.get("/mcp", headers=GOOD)
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"
        assert blocked.json()["error"] == "too_many_requests"

        clock.now += 30
        assert (await client.get("/mcp", headers=BAD)).headers["retry-after"] == "30"

        clock.now += 30.5
        assert (await client.get("/mcp", headers=GOOD)).status_code == 200


@pytest.mark.asyncio
async def test_sliding_window_forgets_old_failures() -> None:
    clock = FakeClock()
    app = _app(clock, max_failures=3, window_seconds=60)
    async with _client(app) as client:
        await client.get("/mcp", headers=BAD)
        await client.get("/mcp", headers=BAD)
        clock.now += 61
        await client.get("/mcp", headers=BAD)
        await client.get("/mcp", headers=BAD)

        assert (await client.get("/mcp", headers=GOOD)).status_code == 200


@pytest.mark.asyncio
async def test_success_does_not_reset_the_count() -> None:
    clock = FakeClock()
    app = _app(clock, max_failures=2)
    async with _client(app) as client:
        await client.get("/mcp", headers=BAD)
        assert (await client.get("/mcp", headers=GOOD)).status_code == 200
        await client.get("/mcp", headers=BAD)

        assert (await client.get("/mcp", headers=GOOD)).status_code == 429


@pytest.mark.asyncio
async def test_addresses_are_counted_separately() -> None:
    clock = FakeClock()
    app = _app(clock, max_failures=1)
    async with _client(app, "203.0.113.7") as attacker, _client(app, "198.51.100.2") as other:
        await attacker.get("/mcp", headers=BAD)

        assert (await attacker.get("/mcp", headers=GOOD)).status_code == 429
        assert (await other.get("/mcp", headers=GOOD)).status_code == 200


@pytest.mark.asyncio
async def test_healthz_is_never_limited() -> None:
    clock = FakeClock()
    app = _app(clock, max_failures=1)
    async with _client(app) as client:
        await client.get("/mcp", headers=BAD)

        assert (await client.get("/healthz")).status_code == 200


@pytest.mark.asyncio
async def test_zero_disables_the_limit() -> None:
    clock = FakeClock()
    app = _app(clock, max_failures=0)
    async with _client(app) as client:
        for _ in range(20):
            await client.get("/mcp", headers=BAD)

        assert (await client.get("/mcp", headers=GOOD)).status_code == 200


def test_tracked_addresses_are_bounded() -> None:
    clock = FakeClock()
    limiter = BearerFailureLimiter(_app(clock), max_failures=5, max_clients=3, clock=clock)
    for i in range(3):
        limiter._record_failure(f"10.0.0.{i}")
    clock.now += 61  # the first three expire
    limiter._record_failure("10.0.0.3")
    assert set(limiter._failures) == {"10.0.0.3"}

    for i in range(4, 7):
        limiter._record_failure(f"10.0.0.{i}")
    assert len(limiter._failures) == 3
    assert "10.0.0.3" not in limiter._failures  # least recently added goes first


@pytest.mark.asyncio
async def test_guards_fastmcp_bearer_endpoint() -> None:
    """End to end: FastMCP's own 401 on /mcp counts toward the limit."""
    mcp = FastMCP(
        "throttle-test",
        auth=StaticTokenVerifier(tokens={TOKEN: {"client_id": "c", "scopes": []}}),
    )
    clock = FakeClock()
    app = mcp.http_app(
        middleware=[Middleware(BearerFailureLimiter, max_failures=2, clock=clock)],
    )
    headers = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "t", "version": "0"},
        },
    }
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(app.router.lifespan_context(app))
        client = await stack.enter_async_context(_client(app))
        good = {**headers, "authorization": f"Bearer {TOKEN}"}
        assert (await client.post("/mcp", headers=good, json=init)).status_code == 200
        for _ in range(2):
            r = await client.post("/mcp", headers={**headers, **BAD}, json=init)
            assert r.status_code == 401

        assert (await client.post("/mcp", headers=good, json=init)).status_code == 429
