"""Unit tests for webhook receiver and handlers."""

import asyncio
import hashlib
import hmac
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.webhooks import receiver as receiver_module
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

    @pytest.mark.asyncio
    async def test_process_event_publishes_to_bus(self, mock_settings):
        event_bus = AsyncMock()
        receiver = WebhookReceiver(settings=mock_settings, event_bus=event_bus)

        event = WebhookEvent(
            event_type="device.online",
            timestamp=datetime.now(),
            site_id="default",
            data={"mac": "00:11:22:33:44:55"},
            event_id="evt-bus-1",
        )

        await receiver._process_event(event)
        await receiver.aclose()

        event_bus.publish.assert_awaited_once()
        call_kwargs = event_bus.publish.await_args.kwargs
        assert call_kwargs["event_type"] == "device.online"
        assert call_kwargs["site_id"] == "default"
        assert call_kwargs["event_id"] == "evt-bus-1"
        assert call_kwargs["data"]["mac"] == "00:11:22:33:44:55"

    @pytest.mark.asyncio
    async def test_process_event_publishes_even_with_no_handlers(self, mock_settings):
        event_bus = AsyncMock()
        receiver = WebhookReceiver(settings=mock_settings, event_bus=event_bus)

        event = WebhookEvent(
            event_type="unknown.event",
            timestamp=datetime.now(),
            site_id="default",
            data={},
            event_id="evt-bus-2",
        )

        await receiver._process_event(event)
        await receiver.aclose()

        event_bus.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_event_publishes_even_when_handler_fails(self, mock_settings):
        async def failing_handler(event):
            raise ValueError("Handler error")

        event_bus = AsyncMock()
        receiver = WebhookReceiver(settings=mock_settings, event_bus=event_bus)
        receiver.register_handler("event.test", failing_handler)

        event = WebhookEvent(
            event_type="event.test",
            timestamp=datetime.now(),
            site_id="default",
            data={},
            event_id="evt-bus-3",
        )

        await receiver._process_event(event)
        await receiver.aclose()

        event_bus.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_event_bus_failure_is_logged(self, mock_settings, caplog):
        event_bus = AsyncMock()
        event_bus.publish = AsyncMock(side_effect=RuntimeError("Redis down"))
        receiver = WebhookReceiver(settings=mock_settings, event_bus=event_bus)

        event = WebhookEvent(
            event_type="device.online",
            timestamp=datetime.now(),
            site_id="default",
            data={},
            event_id="evt-bus-4",
        )

        with caplog.at_level("WARNING"):
            await receiver._process_event(event)
            await receiver.aclose()

        assert "Could not publish webhook event to bus" in caplog.text
        event_bus.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_event_does_not_wait_for_a_hung_publish(self, mock_settings):
        """A Redis that accepts connections but never answers must not delay the ack."""
        release = asyncio.Event()

        async def hanging_publish(**kwargs):
            await release.wait()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock(side_effect=hanging_publish)
        receiver = WebhookReceiver(settings=mock_settings, event_bus=event_bus)

        event = WebhookEvent(
            event_type="device.online",
            timestamp=datetime.now(),
            site_id="default",
            data={},
            event_id="evt-bus-hung",
        )

        # Returns while the publish is still blocked; a synchronous await here
        # would hang until the bus gave up.
        await asyncio.wait_for(receiver._process_event(event), timeout=1)

        assert len(receiver._publish_tasks) == 1
        release.set()
        await receiver.aclose()
        assert not receiver._publish_tasks

    @pytest.mark.asyncio
    async def test_publishes_are_dropped_once_too_many_are_in_flight(self, mock_settings, caplog):
        """A stalled Redis must not let in-flight publishes grow without bound."""
        release = asyncio.Event()

        async def hanging_publish(**kwargs):
            await release.wait()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock(side_effect=hanging_publish)
        receiver = WebhookReceiver(settings=mock_settings, event_bus=event_bus)

        def _event(index: int) -> WebhookEvent:
            return WebhookEvent(
                event_type="device.online",
                timestamp=datetime.now(),
                site_id="default",
                data={},
                event_id=f"evt-flood-{index}",
            )

        for index in range(receiver_module.MAX_PENDING_PUBLISHES):
            receiver._dispatch_publish(_event(index))
        assert len(receiver._publish_tasks) == receiver_module.MAX_PENDING_PUBLISHES

        with caplog.at_level("WARNING"):
            receiver._dispatch_publish(_event(receiver_module.MAX_PENDING_PUBLISHES))

        assert len(receiver._publish_tasks) == receiver_module.MAX_PENDING_PUBLISHES
        assert "Dropping webhook event" in caplog.text

        release.set()
        await receiver.aclose()

    @pytest.mark.asyncio
    async def test_aclose_cancels_a_publish_that_never_finishes(self, mock_settings, caplog):
        async def never_finishes(**kwargs):
            await asyncio.Event().wait()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock(side_effect=never_finishes)
        receiver = WebhookReceiver(settings=mock_settings, event_bus=event_bus)

        receiver._dispatch_publish(
            WebhookEvent(
                event_type="device.online",
                timestamp=datetime.now(),
                site_id="default",
                data={},
                event_id="evt-shutdown",
            )
        )

        with caplog.at_level("WARNING"):
            await receiver.aclose(timeout=0.05)

        assert "had not reached Redis at shutdown" in caplog.text
        assert not receiver._publish_tasks

    @pytest.mark.asyncio
    async def test_aclose_without_a_bus_is_a_no_op(self, receiver):
        await receiver.aclose()


class TestWebhookEventHandler:
    @pytest.mark.asyncio
    async def test_handle_device_online(self, handler):
        event = WebhookEvent(
            event_type="device.online",
            timestamp=datetime.now(),
            site_id="default",
            data={"mac": "00:11:22:33:44:55", "name": "Access Point"},
        )

        await handler.handle_device_online(event)

    @pytest.mark.asyncio
    async def test_handle_device_offline(self, handler):
        event = WebhookEvent(
            event_type="device.offline",
            timestamp=datetime.now(),
            site_id="default",
            data={"mac": "00:11:22:33:44:55", "name": "Switch"},
        )

        await handler.handle_device_offline(event)

    @pytest.mark.asyncio
    async def test_handle_client_connected(self, handler):
        event = WebhookEvent(
            event_type="client.connected",
            timestamp=datetime.now(),
            site_id="default",
            data={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "laptop", "essid": "Corp-WiFi"},
        )

        await handler.handle_client_connected(event)

    @pytest.mark.asyncio
    async def test_handle_client_disconnected(self, handler):
        event = WebhookEvent(
            event_type="client.disconnected",
            timestamp=datetime.now(),
            site_id="default",
            data={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "phone"},
        )

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
