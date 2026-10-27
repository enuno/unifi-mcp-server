"""``unifi:webhooks:v1:events`` pub/sub between replicas.

Validated webhook deliveries are fanned out to other processes over Redis so
that any replica or worker can react to UniFi events without every process
receiving the HTTP callback directly.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Iterator
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

fakeredis = pytest.importorskip("fakeredis")
import redis.asyncio  # noqa: E402,F401

from src.config.config import Settings  # noqa: E402
from src.fleet.bus import WebhookBus  # noqa: E402


@pytest.fixture(scope="module")
def redis_port() -> Iterator[int]:
    server = fakeredis.TcpFakeServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


def _settings(monkeypatch: pytest.MonkeyPatch, redis_url: str | None) -> Settings:
    for name in ("REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", "base-key")  # pragma: allowlist secret
    if redis_url:
        monkeypatch.setenv("REDIS_URL", redis_url)
    return Settings()


@contextlib.asynccontextmanager
async def _listening(bus: WebhookBus, on_event):
    task = asyncio.create_task(bus.listen(on_event))
    await asyncio.wait_for(bus.subscribed.wait(), timeout=5)
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def _until(predicate, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


class TestFromSettings:
    def test_none_without_redis(self, monkeypatch):
        assert WebhookBus.from_settings(_settings(monkeypatch, None)) is None

    def test_bus_with_redis(self, monkeypatch, redis_port):
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        assert isinstance(WebhookBus.from_settings(settings), WebhookBus)


class TestDelivery:
    async def test_other_replicas_receive_event(self, monkeypatch, redis_port):
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        sender = WebhookBus(settings, instance_id="sender")
        listener = WebhookBus(settings, instance_id="listener")
        received: list[dict] = []

        async def on_event(payload: dict) -> None:
            received.append(payload)

        async with _listening(listener, on_event):
            await sender.publish(
                event_type="device.online",
                site_id="default",
                event_id="evt-1",
                timestamp=datetime.now().isoformat(),
                data={"mac": "00:11:22:33:44:55"},
            )
            await _until(lambda: len(received) == 1)

        assert received[0]["event_type"] == "device.online"
        assert received[0]["site_id"] == "default"
        assert received[0]["event_id"] == "evt-1"
        assert received[0]["data"]["mac"] == "00:11:22:33:44:55"
        assert "origin" in received[0]

    async def test_own_messages_are_ignored(self, monkeypatch, redis_port):
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        replica = WebhookBus(settings, instance_id="self")
        other = WebhookBus(settings, instance_id="other")
        on_event = AsyncMock()

        async with _listening(replica, on_event):
            await replica.publish(
                event_type="device.online",
                site_id="default",
                event_id="evt-1",
                timestamp=datetime.now().isoformat(),
                data={},
            )
            await other.publish(
                event_type="client.connected",
                site_id="default",
                event_id="evt-2",
                timestamp=datetime.now().isoformat(),
                data={},
            )
            await _until(lambda: on_event.await_count == 1)
            await asyncio.sleep(0.1)

        assert on_event.await_count == 1
        assert on_event.await_args.args[0]["event_type"] == "client.connected"

    async def test_a_failing_handler_does_not_stop_listening(self, monkeypatch, redis_port):
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        listener = WebhookBus(settings, instance_id="l")
        sender = WebhookBus(settings, instance_id="s")
        on_event = AsyncMock(side_effect=[RuntimeError("handler failed"), None])

        async with _listening(listener, on_event):
            await sender.publish(
                event_type="device.online",
                site_id="default",
                event_id="evt-1",
                timestamp=datetime.now().isoformat(),
                data={},
            )
            await sender.publish(
                event_type="device.offline",
                site_id="default",
                event_id="evt-2",
                timestamp=datetime.now().isoformat(),
                data={},
            )
            await _until(lambda: on_event.await_count == 2)


class TestRedisUnavailable:
    async def test_publish_logs_and_carries_on(self, monkeypatch, caplog):
        bus = WebhookBus(_settings(monkeypatch, "redis://127.0.0.1:1/0"), instance_id="x")

        with caplog.at_level("WARNING"):
            await bus.publish(
                event_type="device.online",
                site_id="default",
                event_id="evt-1",
                timestamp=datetime.now().isoformat(),
                data={},
            )

        assert "webhook event" in caplog.text

    async def test_listen_retries_instead_of_raising(self, monkeypatch):
        bus = WebhookBus(_settings(monkeypatch, "redis://127.0.0.1:1/0"), instance_id="x")
        bus.retry_seconds = 0.01
        task = asyncio.create_task(bus.listen(AsyncMock()))

        await asyncio.sleep(0.2)

        assert not task.done()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
