"""Worker health checks half-open replicas' circuit breakers (FLEET_SCALING_PLAN.md Phase 5d).

A replica's breaker opens after repeated unreachable calls and fails fast for
its cooldown. When a worker's health check, started after the breaker opened,
reaches the controller, the worker announces it on Redis and every replica
lets calls through again; one more failure re-opens the circuit. The worker
sends how long the check took, and each replica dates it on its own
monotonic clock, so no two hosts' clocks are compared.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from collections.abc import Iterator

import pytest

fakeredis = pytest.importorskip("fakeredis")
# Bound at import, before tests/unit/test_cache.py stubs sys.modules["redis"].
import redis.asyncio  # noqa: E402,F401

from src.api.pool import CircuitBreaker, CircuitOpenError, ClientPool, connection_key  # noqa: E402
from src.config.config import Settings  # noqa: E402
from src.fleet.bus import HEALTH_CHANNEL, HealthBus  # noqa: E402


@pytest.fixture(scope="module")
def redis_port() -> Iterator[int]:
    server = fakeredis.TcpFakeServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


def _settings(monkeypatch: pytest.MonkeyPatch, redis_url: str | None = None) -> Settings:
    for name in ("REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", "base-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
    if redis_url:
        monkeypatch.setenv("REDIS_URL", redis_url)
    return Settings()


def _open(breaker: CircuitBreaker) -> None:
    for _ in range(breaker.threshold):
        breaker.record_failure()


class TestHalfOpen:
    def test_a_closed_circuit_is_left_alone(self) -> None:
        breaker = CircuitBreaker()
        assert breaker.half_open(time.monotonic()) is False
        assert breaker.failures == 0

    def test_a_check_from_before_the_outage_is_ignored(self) -> None:
        breaker = CircuitBreaker()
        before = time.monotonic() - 1
        _open(breaker)
        assert breaker.half_open(before) is False
        with pytest.raises(CircuitOpenError):
            breaker.check("hq")

    def test_a_later_check_lets_calls_through_until_the_next_failure(self) -> None:
        breaker = CircuitBreaker()
        _open(breaker)
        assert breaker.half_open(time.monotonic() + 0.001) is True
        breaker.check("hq")  # no longer fails fast
        breaker.record_failure()
        with pytest.raises(CircuitOpenError):
            breaker.check("hq")


class TestPool:
    def test_unknown_controllers_are_ignored(self) -> None:
        assert ClientPool().health_ok("nope", 0.0) is False

    async def test_an_open_circuit_is_half_opened(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings(monkeypatch)
        pool = ClientPool()
        connection = pool.acquire(settings)
        try:
            _open(connection.breaker)
            key = connection_key(settings)
            # began 10 s ago, before the circuit opened: says nothing about the outage
            assert pool.health_ok(key, took=10.0) is False
            time.sleep(0.002)
            assert pool.health_ok(key, took=0.0) is True  # began after it opened
            connection.breaker.check("hq")
            assert pool.health_ok(key, took=0.0) is False  # closed now
        finally:
            pool.release(connection)
            await pool.aclose()


class TestBus:
    def test_none_without_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert HealthBus.from_settings(_settings(monkeypatch)) is None

    async def test_a_worker_announcement_reaches_a_replica(
        self, monkeypatch: pytest.MonkeyPatch, redis_port: int
    ) -> None:
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        pool = ClientPool()
        connection = pool.acquire(settings)
        _open(connection.breaker)
        replica = HealthBus(settings, instance_id="replica")
        worker = HealthBus(settings, instance_id="worker")
        task = asyncio.create_task(replica.listen(pool.health_ok))
        try:
            await asyncio.wait_for(replica.subscribed.wait(), timeout=5)
            await asyncio.sleep(0.002)
            await worker.publish_ok(connection_key(settings), 0.0)
            deadline = time.monotonic() + 5
            while connection.breaker.opened_at is not None:
                assert time.monotonic() < deadline, "breaker was not half-opened"
                await asyncio.sleep(0.01)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            pool.release(connection)
            await pool.aclose()

    async def test_malformed_and_own_messages_are_ignored(
        self, monkeypatch: pytest.MonkeyPatch, redis_port: int
    ) -> None:
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        seen: list[tuple[str, float]] = []

        async def on_ok(key: str, checked_at: float) -> None:
            seen.append((key, checked_at))

        bus = HealthBus(settings, instance_id="replica")
        task = asyncio.create_task(bus.listen(on_ok))
        try:
            await asyncio.wait_for(bus.subscribed.wait(), timeout=5)
            client = bus._redis()
            await client.publish(HEALTH_CHANNEL, "not json")
            await client.publish(HEALTH_CHANNEL, '{"key": 5, "took": 1}')
            await client.publish(HEALTH_CHANNEL, '{"key": "k", "checked_at": 1}')
            await bus.publish_ok("own", 1.0)  # its own message
            await HealthBus(settings, instance_id="worker").publish_ok("k", 2.0)
            deadline = time.monotonic() + 5
            while not seen:
                assert time.monotonic() < deadline
                await asyncio.sleep(0.01)
            assert seen == [("k", 2.0)]
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_publishing_without_redis_warns_once(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        settings = _settings(monkeypatch, "redis://127.0.0.1:1/0")
        bus = HealthBus(settings, instance_id="worker")
        for _ in range(3):  # one per healthy controller during the outage
            await bus.publish_ok("k", 1.0)
        assert caplog.text.count("recover after the cooldown") == 1

    async def test_recovery_is_logged(
        self, monkeypatch: pytest.MonkeyPatch, redis_port: int, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        bus = HealthBus(settings, instance_id="worker")
        bus._publish_failing = True  # as after an outage
        with caplog.at_level(logging.INFO):
            await bus.publish_ok("k", 1.0)
            await bus.publish_ok("k", 1.0)
        assert caplog.text.count("announcements reach Redis again") == 1


class TestServerWiring:
    def test_no_listener_without_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings(monkeypatch)  # before importing src.main, which reads them
        from src.main import start_health_listener

        assert start_health_listener(settings, ClientPool()) is None

    async def test_listener_with_redis(
        self, monkeypatch: pytest.MonkeyPatch, redis_port: int
    ) -> None:
        settings = _settings(monkeypatch, f"redis://127.0.0.1:{redis_port}/0")
        from src.main import start_health_listener

        task = start_health_listener(settings, ClientPool())
        assert task is not None
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
