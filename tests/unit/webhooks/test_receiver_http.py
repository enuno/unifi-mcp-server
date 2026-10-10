"""HTTP behaviour of the webhook receiver, through a real Starlette app.

Requests go through ``httpx.ASGITransport``, so status codes are what a
UniFi controller would see: the 401 and 429 responses must not be turned
into 500s by the receiver's own error handling.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from starlette.applications import Starlette

from src.webhooks.receiver import WebhookReceiver

SECRET = "test-webhook-secret"  # pragma: allowlist secret
PATH = "/webhooks/unifi"


def _settings(secret: str | None = SECRET) -> MagicMock:
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.webhook_secret = secret
    return settings


def _event(**overrides: Any) -> dict[str, Any]:
    return {
        "event_type": "device.online",
        "timestamp": datetime(2026, 10, 10, 12, 0).isoformat(),
        "site_id": "default",
        "data": {"mac": "00:11:22:33:44:55"},
        "event_id": "evt-1",
        **overrides,
    }


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _post(
    receiver: WebhookReceiver,
    body: bytes,
    signature: str | None = "sign",
) -> httpx.Response:
    app = Starlette()
    receiver.register_routes(app)
    headers = {"content-type": "application/json"}
    if signature == "sign":
        headers["x-unifi-signature"] = _sign(body)
    elif signature is not None:
        headers["x-unifi-signature"] = signature
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(PATH, content=body, headers=headers)


def _body(payload: Any) -> bytes:
    return json.dumps(payload).encode()


class TestAuthentication:
    @pytest.mark.asyncio
    async def test_valid_signature_is_processed(self) -> None:
        receiver = WebhookReceiver(_settings())
        handler = AsyncMock()
        receiver.register_handler("device.online", handler)

        response = await _post(receiver, _body(_event()))

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "event_id": "evt-1",
            "event_type": "device.online",
        }
        handler.assert_awaited_once()
        assert handler.await_args.args[0].site_id == "default"

    @pytest.mark.asyncio
    async def test_invalid_signature_is_401(self) -> None:
        handler = AsyncMock()
        receiver = WebhookReceiver(_settings())
        receiver.register_handler("device.online", handler)

        response = await _post(receiver, _body(_event()), signature="0" * 64)

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid signature"}
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_signature_is_401(self) -> None:
        response = await _post(WebhookReceiver(_settings()), _body(_event()), signature=None)

        assert response.status_code == 401
        assert response.json() == {"detail": "Missing signature"}

    @pytest.mark.asyncio
    async def test_signature_over_other_body_is_401(self) -> None:
        receiver = WebhookReceiver(_settings())
        signature = _sign(_body(_event(site_id="other")))

        response = await _post(receiver, _body(_event()), signature=signature)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_without_secret_every_request_is_refused(self) -> None:
        # Fail closed: an unconfigured receiver must not accept unsigned events.
        handler = AsyncMock()
        receiver = WebhookReceiver(_settings(secret=None))
        receiver.register_handler("device.online", handler)

        response = await _post(receiver, _body(_event()), signature="anything")

        assert response.status_code == 503
        handler.assert_not_called()

    def test_reads_secretstr_values(self) -> None:
        from pydantic import SecretStr

        receiver = WebhookReceiver(_settings(secret=SecretStr(SECRET)))  # type: ignore[arg-type]
        assert receiver.webhook_secret == SECRET

    def test_unconfigured_warns(self) -> None:
        settings = _settings(secret=None)
        logger = MagicMock()
        with pytest.MonkeyPatch.context() as m:
            m.setattr("src.webhooks.receiver.get_logger", lambda *a, **k: logger)
            WebhookReceiver(settings)
        assert "WEBHOOK_SECRET" in logger.warning.call_args.args[0]


class TestPayloadValidation:
    @pytest.mark.asyncio
    async def test_invalid_json_is_400(self) -> None:
        response = await _post(WebhookReceiver(_settings()), b"{not json")

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid JSON payload"}

    @pytest.mark.asyncio
    async def test_non_utf8_body_is_400(self) -> None:
        response = await _post(WebhookReceiver(_settings()), b"\xff\xfe")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_non_object_json_is_400(self) -> None:
        response = await _post(WebhookReceiver(_settings()), _body(["device.online"]))

        assert response.status_code == 400
        assert response.json() == {"detail": "Webhook payload must be a JSON object"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload",
        [_event(event_type="nodot"), {k: v for k, v in _event().items() if k != "site_id"}],
    )
    async def test_invalid_event_is_400(self, payload: dict) -> None:
        response = await _post(WebhookReceiver(_settings()), _body(payload))

        assert response.status_code == 400
        assert response.json()["detail"].startswith("Invalid webhook event")


class TestDeliverySemantics:
    @pytest.mark.asyncio
    async def test_duplicate_event_is_acknowledged_once(self) -> None:
        handler = AsyncMock()
        receiver = WebhookReceiver(_settings())
        receiver.register_handler("device.online", handler)

        first = await _post(receiver, _body(_event()))
        second = await _post(receiver, _body(_event()))

        assert first.json()["status"] == "success"
        assert second.status_code == 200
        assert second.json() == {"status": "duplicate", "event_id": "evt-1"}
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rate_limit_is_429(self) -> None:
        receiver = WebhookReceiver(_settings())
        receiver._check_rate_limit = MagicMock(return_value=False)  # type: ignore[method-assign]

        response = await _post(receiver, _body(_event()))

        assert response.status_code == 429
        assert response.json() == {"detail": "Rate limit exceeded"}

    @pytest.mark.asyncio
    async def test_failing_handler_still_acknowledges(self) -> None:
        receiver = WebhookReceiver(_settings())
        receiver.register_handler("device.online", AsyncMock(side_effect=RuntimeError("boom")))

        response = await _post(receiver, _body(_event()))

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_unexpected_error_is_500(self) -> None:
        receiver = WebhookReceiver(_settings())
        receiver._process_event = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        response = await _post(receiver, _body(_event()))

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}


class TestMounting:
    @pytest.mark.asyncio
    async def test_constructor_mounts_on_app_and_custom_path(self) -> None:
        app = Starlette()
        WebhookReceiver(_settings(), app=app, path="/hooks/u")
        transport = httpx.ASGITransport(app=app)
        body = _body(_event())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/hooks/u", content=body, headers={"x-unifi-signature": _sign(body)}
            )
            not_allowed = await client.get("/hooks/u")

        assert response.status_code == 200
        assert not_allowed.status_code == 405
