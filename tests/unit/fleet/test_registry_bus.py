"""``registry:changed`` pub/sub between replicas (docs/FLEET_SCALING_PLAN.md §3.3, Phase 4).

A registry change made on one replica used to reach the others only at their
next periodic refresh (UNIFI_FLEET_REGISTRY_REFRESH_SECONDS). With Redis
configured, the replica that made the change publishes, and every other
replica reloads its snapshot at once.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest

fakeredis = pytest.importorskip("fakeredis")
# Bound at import, before tests/unit/test_cache.py stubs sys.modules["redis"].
import redis.asyncio  # noqa: E402,F401

from src.config.config import Settings  # noqa: E402
from src.fleet.bus import RegistryBus  # noqa: E402
from src.fleet.postgres_registry import PostgresRegistry  # noqa: E402


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
async def _listening(bus: RegistryBus, on_change):
    task = asyncio.create_task(bus.listen(on_change))
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
        assert RegistryBus.from_settings(_settings(monkeypatch, None)) is None

    def test_bus_with_redis(self, monkeypatch, redis_port):
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        assert isinstance(RegistryBus.from_settings(settings), RegistryBus)


class TestDelivery:
    async def test_other_replicas_are_told(self, monkeypatch, redis_port):
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        replica_a = RegistryBus(settings, instance_id="a")
        replica_b = RegistryBus(settings, instance_id="b")
        changes: list[str] = []

        async def on_change() -> None:
            changes.append("b refreshed")

        async with _listening(replica_b, on_change):
            await replica_a.publish()
            await _until(lambda: changes)

        assert changes == ["b refreshed"]

    async def test_own_messages_are_ignored(self, monkeypatch, redis_port):
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        replica = RegistryBus(settings, instance_id="self")
        other = RegistryBus(settings, instance_id="other")
        on_change = AsyncMock()

        async with _listening(replica, on_change):
            await replica.publish()  # ignored: it already refreshed itself
            await other.publish()
            await _until(lambda: on_change.await_count == 1)
            await asyncio.sleep(0.1)

        assert on_change.await_count == 1

    async def test_a_failing_refresh_does_not_stop_listening(self, monkeypatch, redis_port):
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        listener = RegistryBus(settings, instance_id="l")
        sender = RegistryBus(settings, instance_id="s")
        on_change = AsyncMock(side_effect=[RuntimeError("db down"), None])

        async with _listening(listener, on_change):
            await sender.publish()
            await sender.publish()
            await _until(lambda: on_change.await_count == 2)


class TestRedisUnavailable:
    async def test_publish_logs_and_carries_on(self, monkeypatch, caplog):
        bus = RegistryBus(_settings(monkeypatch, "redis://127.0.0.1:1/0"), instance_id="x")

        with caplog.at_level("WARNING"):
            await bus.publish()

        assert "registry change" in caplog.text

    async def test_listen_retries_instead_of_raising(self, monkeypatch):
        bus = RegistryBus(_settings(monkeypatch, "redis://127.0.0.1:1/0"), instance_id="x")
        bus.retry_seconds = 0.01
        task = asyncio.create_task(bus.listen(AsyncMock()))

        await asyncio.sleep(0.2)

        assert not task.done()  # still retrying, not crashed
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


class TestRegistryIntegration:
    def _registry(self, monkeypatch, bus) -> PostgresRegistry:
        store = MagicMock()
        store.load = AsyncMock(return_value=([], None))
        registry = PostgresRegistry(store, _settings(monkeypatch, None))
        registry._bus = bus
        return registry

    async def test_changed_refreshes_then_publishes(self, monkeypatch):
        bus = MagicMock()
        bus.publish = AsyncMock()
        registry = self._registry(monkeypatch, bus)

        await registry.changed()

        registry.store.load.assert_awaited_once()
        bus.publish.assert_awaited_once()

    async def test_changed_without_a_bus_only_refreshes(self, monkeypatch):
        registry = self._registry(monkeypatch, None)

        await registry.changed()

        registry.store.load.assert_awaited_once()
