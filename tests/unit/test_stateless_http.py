"""MCP_STATELESS_HTTP end to end, through FastMCP's real HTTP app.

In stateless mode every request arrives without ``mcp-session-id``, so the
SessionlessRequestGuard (which answers sessionless non-initialize requests
with 400, issue #173) must not be installed there: it would refuse every
tool call. Stateless transports are torn down after each response, so the
session leak the guard prevents cannot happen in that mode.
"""

from __future__ import annotations

import contextlib
import json

import httpx
import pytest
from fastmcp import FastMCP
from starlette.middleware import Middleware

from src.utils.session_guard import SessionlessRequestGuard

HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
CALL = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {"name": "ping", "arguments": {}},
}


def _server() -> FastMCP:
    mcp = FastMCP("stateless-test")

    @mcp.tool
    def ping() -> str:
        return "pong"

    return mcp


async def _call(app) -> httpx.Response:
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(app.router.lifespan_context(app))
        client = await stack.enter_async_context(
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
        )
        return await client.post("/mcp", headers=HEADERS, json=CALL)


def _text(response: httpx.Response) -> str:
    body = response.text
    if "data:" in body:
        body = [line[5:] for line in body.splitlines() if line.startswith("data:")][-1]
    return json.loads(body)["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_stateless_tool_call_needs_no_session() -> None:
    response = await _call(_server().http_app(stateless_http=True))

    assert response.status_code == 200
    assert _text(response) == "pong"


@pytest.mark.asyncio
async def test_session_guard_would_refuse_every_stateless_call() -> None:
    # Why main() installs the guard only in stateful mode.
    app = _server().http_app(
        stateless_http=True, middleware=[Middleware(SessionlessRequestGuard, path="/mcp")]
    )

    response = await _call(app)

    assert response.status_code == 400
