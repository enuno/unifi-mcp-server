"""Unit tests for webhook receiver and handlers."""

import hashlib
import hmac
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.webhooks.handlers import WebhookEventHandler
from src.webhooks.receiver import WebhookEvent, WebhookReceiver


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.webhook_secret = "test-webhook-secret"
    return settings


@pytest.fixture
def mock_settings_no_secret():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.webhook_secret = None
    return settings


@pytest.fixture
def receiver(mock_settings):
    return WebhookReceiver(settings=mock_settings)


@pytest.fixture
def receiver_no_secret(mock_settings_no_secret):
    return WebhookReceiver(settings=mock_settings_no_secret)


@pytest.fixture
def handler(mock_settings):
    return WebhookEventHandler(settings=mock_settings)


@pytest.fixture
def valid_event_data():
    return {
        "event_type": "device.online",
        "timestamp": datetime.now().isoformat(),
        "site_id": "default",
        "data": {"mac": "00:11:22:33:44:55", "name": "Test Device"},
        "event_id": "evt-123456",
    }


def create_signature(payload: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class TestWebhookEvent:
    def test_webhook_event_valid(self, valid_event_data):
        event = WebhookEvent(**valid_event_data)

        assert event.event_type == "device.online"
        assert event.site_id == "default"
        assert event.data["mac"] == "00:11:22:33:44:55"
        assert event.event_id == "evt-123456"

    def test_webhook_event_invalid_type(self):
        with pytest.raises(ValueError, match="must be in format"):
            WebhookEvent(
                event_type="invalidformat",
                timestamp=datetime.now(),
                site_id="default",
                data={},
            )

    def test_webhook_event_type_normalized(self):
        event = WebhookEvent(
            event_type="DEVICE.ONLINE",
            timestamp=datetime.now(),
            site_id="default",
            data={},
        )

        assert event.event_type == "device.online"

    def test_webhook_event_optional_event_id(self):
        event = WebhookEvent(
            event_type="client.connected",
            timestamp=datetime.now(),
            site_id="default",
            data={"mac": "aa:bb:cc:dd:ee:ff"},
        )

        assert event.event_id is None


class TestWebhookReceiverSignature:
    def test_verify_signature_valid(self, receiver):
        payload = '{"event_type": "device.online"}'
        signature = create_signature(payload, "test-webhook-secret")

        result = receiver._verify_signature(payload, signature)

        assert result is True

    def test_verify_signature_invalid(self, receiver):
        payload = '{"event_type": "device.online"}'
        wrong_signature = "invalid_signature"

        result = receiver._verify_signature(payload, wrong_signature)

        assert result is False

    def test_verify_signature_no_secret(self, receiver_no_secret):
        payload = '{"event_type": "device.online"}'
        signature = "any_signature"

        result = receiver_no_secret._verify_signature(payload, signature)

        assert result is False


class TestWebhookReceiverDuplicateDetection:
    def test_is_duplicate_new_event(self, receiver):
        event = WebhookEvent(
            event_type="device.online",
            timestamp=datetime.now(),
            site_id="default",
            data={},
            event_id="new-event-id",
        )

        result = receiver._is_duplicate(event)

        assert result is False

    def test_is_duplicate_seen_event(self, receiver):
        event = WebhookEvent(
            event_type="device.online",
            timestamp=datetime.now(),
            site_id="default",
            data={},
            event_id="duplicate-event-id",
        )

        receiver._is_duplicate(event)
        result = receiver._is_duplicate(event)

        assert result is True

    def test_is_duplicate_no_event_id(self, receiver):
        event = WebhookEvent(
            event_type="device.online",
            timestamp=datetime.now(),
            site_id="default",
            data={},
            event_id=None,
        )

        result1 = receiver._is_duplicate(event)
        result2 = receiver._is_duplicate(event)

        assert result1 is False
        assert result2 is False

    def test_duplicate_cache_expires(self, receiver):
        event = WebhookEvent(
            event_type="device.online",
            timestamp=datetime.now(),
            site_id="default",
            data={},
            event_id="expiring-event",
        )

        receiver._event_cache[event.event_id] = datetime.now() - timedelta(minutes=6)

        result = receiver._is_duplicate(event)

        assert result is False


class TestWebhookReceiverRateLimit:
    def test_rate_limit_within_limit(self, receiver):
        result = receiver._check_rate_limit("site-1", max_requests=10, window_seconds=60)

        assert result is True

    def test_rate_limit_exceeded(self, receiver):
        for _ in range(100):
            receiver._check_rate_limit("site-2", max_requests=100, window_seconds=60)

        result = receiver._check_rate_limit("site-2", max_requests=100, window_seconds=60)

        assert result is False

    def test_rate_limit_per_site(self, receiver):
        for _ in range(100):
            receiver._check_rate_limit("site-limited", max_requests=100, window_seconds=60)

        result = receiver._check_rate_limit("site-different", max_requests=100, window_seconds=60)

        assert result is True

    def test_rate_limit_resets_after_window(self, receiver):
        receiver._rate_limit_cache["site-3"] = [
            datetime.now() - timedelta(seconds=120) for _ in range(100)
        ]

        result = receiver._check_rate_limit("site-3", max_requests=100, window_seconds=60)

        assert result is True


class TestWebhookReceiverHandlers:
    def test_register_handler(self, receiver):
        async def test_handler(event):
            pass

        receiver.register_handler("device.online", test_handler)

        assert "device.online" in receiver.handlers
        assert test_handler in receiver.handlers["device.online"]

    def test_unregister_handler(self, receiver):
        async def test_handler(event):
            pass

        receiver.register_handler("device.offline", test_handler)
        receiver.unregister_handler("device.offline", test_handler)

        assert test_handler not in receiver.handlers["device.offline"]

    @pytest.mark.asyncio
    async def test_process_event_calls_handler(self, receiver):
        called = []

        async def test_handler(event):
            called.append(event)

        receiver.register_handler("alert.raised", test_handler)

        event = WebhookEvent(
            event_type="alert.raised",
            timestamp=datetime.now(),
            site_id="default",
            data={"message": "Test alert"},
        )

        await receiver._process_event(event)

        assert len(called) == 1
        assert called[0].event_type == "alert.raised"

    @pytest.mark.asyncio
    async def test_process_event_wildcard_handler(self, receiver):
        called = []

        async def wildcard_handler(event):
            called.append(event)

        receiver.register_handler("device.*", wildcard_handler)

        event = WebhookEvent(
            event_type="device.upgraded",
            timestamp=datetime.now(),
            site_id="default",
            data={},
        )

        await receiver._process_event(event)

        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_process_event_handler_error_logged(self, receiver):
        async def failing_handler(event):
            raise ValueError("Handler error")

        async def working_handler(event):
            pass

        receiver.register_handler("event.test", failing_handler)
        receiver.register_handler("event.test", working_handler)

        event = WebhookEvent(
            event_type="event.test",
            timestamp=datetime.now(),
            site_id="default",
            data={},
        )

        await receiver._process_event(event)


class TestWebhookEventHandler:
    @pytest.mark.asyncio
    async def test_handle_device_online(self, handler):
        event = WebhookEvent(
            event_type="device.online",
            timestamp=datetime.now(),
            site_id="default",
            data={"mac": "00:11:22:33:44:55", "name": "Access Point"},
        )

        with patch("src.cache.invalidate_cache", new_callable=AsyncMock):
            await handler.handle_device_online(event)

    @pytest.mark.asyncio
    async def test_handle_device_offline(self, handler):
        event = WebhookEvent(
            event_type="device.offline",
            timestamp=datetime.now(),
            site_id="default",
            data={"mac": "00:11:22:33:44:55", "name": "Switch"},
        )

        with patch("src.cache.invalidate_cache", new_callable=AsyncMock):
            await handler.handle_device_offline(event)

    @pytest.mark.asyncio
    async def test_handle_client_connected(self, handler):
        event = WebhookEvent(
            event_type="client.connected",
            timestamp=datetime.now(),
            site_id="default",
            data={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "laptop", "essid": "Corp-WiFi"},
        )

        with patch("src.cache.invalidate_cache", new_callable=AsyncMock):
            await handler.handle_client_connected(event)

    @pytest.mark.asyncio
    async def test_handle_client_disconnected(self, handler):
        event = WebhookEvent(
            event_type="client.disconnected",
            timestamp=datetime.now(),
            site_id="default",
            data={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "phone"},
        )

        with patch("src.cache.invalidate_cache", new_callable=AsyncMock):
            await handler.handle_client_disconnected(event)

    @pytest.mark.asyncio
    async def test_handle_alert_raised(self, handler):
        event = WebhookEvent(
            event_type="alert.raised",
            timestamp=datetime.now(),
            site_id="default",
            data={
                "type": "device_disconnected",
                "message": "AP went offline",
                "severity": "warning",
            },
        )

        await handler.handle_alert_raised(event)

    @pytest.mark.asyncio
    async def test_handle_event_occurred(self, handler):
        event = WebhookEvent(
            event_type="event.occurred",
            timestamp=datetime.now(),
            site_id="default",
            data={"key": "EVT_AP_RestartedByUser", "msg": "AP was restarted"},
        )

        await handler.handle_event_occurred(event)

    @pytest.mark.asyncio
    async def test_handle_wildcard(self, handler):
        event = WebhookEvent(
            event_type="unknown.event",
            timestamp=datetime.now(),
            site_id="default",
            data={},
        )

        await handler.handle_wildcard(event)

    def test_get_default_handlers(self, handler):
        handlers = handler.get_default_handlers()

        assert "device.online" in handlers
        assert "device.offline" in handlers
        assert "client.connected" in handlers
        assert "client.disconnected" in handlers
        assert "alert.raised" in handlers
        assert "event.occurred" in handlers
        assert len(handlers) == 6

    def test_register_default_handlers(self, handler, receiver):
        handler.register_default_handlers(receiver)

        assert "device.online" in receiver.handlers
        assert "device.offline" in receiver.handlers
        assert "client.connected" in receiver.handlers
