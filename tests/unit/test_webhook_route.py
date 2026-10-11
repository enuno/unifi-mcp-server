"""``POST /webhooks/unifi`` is mounted on the server only when WEBHOOK_SECRET is set.

The route is exercised through FastMCP's real HTTP app, so these tests also
show that it needs no MCP bearer token: UniFi cannot send one, and the HMAC
signature is what authenticates the caller.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import sys
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastmcp import FastMCP

SECRET = "route-test-secret"  # pragma: allowlist secret

_BASE_ENV = {
    "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
    "UNIFI_API_TYPE": "cloud-ea",
    "AGNOST_ENABLED": "false",
}


def _load_main() -> Any:
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]
    with patch.dict("os.environ", _BASE_ENV, clear=False):
        return importlib.import_module("src.main")


@pytest.fixture(scope="module")
def main_mod() -> Any:
    return _load_main()


def _settings(secret: str | None) -> MagicMock:
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.webhook_secret = secret
    return settings


def _paths(server: FastMCP) -> set[str]:
    return {getattr(route, "path", None) for route in server.http_app().routes}


def test_not_mounted_without_secret(main_mod: Any) -> None:
    server = FastMCP("t")

    assert main_mod.register_webhook_route(server, _settings(None)) is None
    assert "/webhooks/unifi" not in _paths(server)


def test_mounted_with_secret_and_default_handlers(main_mod: Any) -> None:
    server = FastMCP("t")

    receiver = main_mod.register_webhook_route(server, _settings(SECRET))

    assert receiver is not None
    assert "/webhooks/unifi" in _paths(server)
    assert "device.online" in receiver.handlers


@pytest.mark.asyncio
async def test_signed_delivery_is_accepted_without_a_bearer_token(main_mod: Any) -> None:
    server = FastMCP("t")
    main_mod.register_webhook_route(server, _settings(SECRET))
    body = json.dumps(
        {
            "event_type": "alert.raised",
            "timestamp": datetime(2026, 10, 10).isoformat(),
            "site_id": "default",
            "data": {"message": "test"},
            "event_id": "evt-route-1",
        }
    ).encode()
    signature = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

    transport = httpx.ASGITransport(app=server.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.post(
            "/webhooks/unifi", content=body, headers={"x-unifi-signature": signature}
        )
        unsigned = await client.post("/webhooks/unifi", content=body)

    assert ok.status_code == 200
    assert ok.json()["status"] == "success"
    assert unsigned.status_code == 401
