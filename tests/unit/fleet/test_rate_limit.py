"""Rate limits shared across replicas in Redis (docs/FLEET_SCALING_PLAN.md §3.3, Phase 4).

Each replica used to give every controller the full UNIFI_RATE_LIMIT_REQUESTS
budget, so N replicas sent N times the configured rate. With Redis configured
the budget is one sliding window per controller (per API key for api.ui.com,
which limits per key, not per console), shared by every replica.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

fakeredis = pytest.importorskip("fakeredis")
# Bound at import: tests/unit/test_cache.py later swaps a stand-in into
# sys.modules["redis"], and pytest imports every test module before running any.
import redis.asyncio as aioredis  # noqa: E402

from src.api.client import RateLimiter  # noqa: E402
from src.api.rate_limit import RedisRateLimiter, bucket_key, make_rate_limiter  # noqa: E402
from src.config.config import Settings  # noqa: E402

LIMIT = 4
PERIOD = 1


@pytest.fixture(scope="module")
def redis_port() -> Iterator[int]:
    server = fakeredis.TcpFakeServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


def _settings(monkeypatch: pytest.MonkeyPatch, redis_port: int | None, **env: str) -> Settings:
    for name in ("REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB"):
        monkeypatch.delenv(name, raising=False)
    values = {
        "UNIFI_API_KEY": "key-a",  # pragma: allowlist secret
        "UNIFI_API_TYPE": "local",
        "UNIFI_LOCAL_HOST": "10.0.0.1",
        "UNIFI_RATE_LIMIT_REQUESTS": str(LIMIT),
        "UNIFI_RATE_LIMIT_PERIOD": str(PERIOD),
        **env,
    }
    if redis_port is not None:
        values["REDIS_URL"] = f"redis://127.0.0.1:{redis_port}/0"
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return Settings()


def _make(settings: Settings) -> Any:
    return make_rate_limiter(settings, RateLimiter)


@pytest.fixture(autouse=True)
def _fresh_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fallback buckets are per process; each test is a fresh process.
    monkeypatch.setattr("src.api.rate_limit._fallbacks", {})


@pytest.fixture(autouse=True)
async def _flush(redis_port: int) -> None:
    client = aioredis.Redis(port=redis_port)
    await client.flushdb()
    await client.aclose()


async def _burst(limiters: list[Any], calls: int) -> list[float]:
    """Run ``calls`` acquisitions round-robin over ``limiters``; return start offsets."""
    start = time.monotonic()
    stamps: list[float] = []

    async def one(limiter: Any) -> None:
        await limiter.acquire()
        stamps.append(time.monotonic() - start)

    await asyncio.gather(*(one(limiters[i % len(limiters)]) for i in range(calls)))
    return sorted(stamps)


def _max_in_any_window(stamps: list[float], window: float) -> int:
    return max(sum(1 for t in stamps if s <= t < s + window) for s in stamps)


class TestFactory:
    def test_without_redis_each_process_keeps_its_own_bucket(self, monkeypatch, redis_port):
        assert isinstance(_make(_settings(monkeypatch, None)), RateLimiter)

    def test_with_redis_the_bucket_is_shared(self, monkeypatch, redis_port):
        assert isinstance(_make(_settings(monkeypatch, redis_port)), RedisRateLimiter)


class TestBucketKeys:
    def test_local_controllers_get_separate_buckets(self, monkeypatch, redis_port):
        a = bucket_key(_settings(monkeypatch, redis_port, UNIFI_LOCAL_HOST="10.0.0.1"))
        b = bucket_key(_settings(monkeypatch, redis_port, UNIFI_LOCAL_HOST="10.0.0.2"))
        assert a != b

    def test_cloud_consoles_behind_one_api_key_share_a_bucket(self, monkeypatch, redis_port):
        # api.ui.com rate-limits per API key, whichever console a call is for.
        a = bucket_key(_settings(monkeypatch, redis_port, UNIFI_API_TYPE="cloud-ea"))
        b = bucket_key(
            _settings(
                monkeypatch,
                redis_port,
                UNIFI_API_TYPE="cloud-v1",
                UNIFI_CLOUD_API_URL="https://api.ui.com",
            )
        )
        c = bucket_key(
            _settings(
                monkeypatch,
                redis_port,
                UNIFI_API_TYPE="cloud-ea",
                UNIFI_API_KEY="key-b",  # pragma: allowlist secret
            )
        )
        assert a == b
        assert a != c

    def test_keys_stay_outside_the_read_cache_namespace(self, monkeypatch, redis_port):
        # ReadCache.invalidate_all() deletes unifi:v1:*; it must not reset limits.
        assert not bucket_key(_settings(monkeypatch, redis_port)).startswith("unifi:v1:")

    def test_key_does_not_contain_the_api_key(self, monkeypatch, redis_port):
        assert "key-a" not in bucket_key(_settings(monkeypatch, redis_port))


class TestSharedBudget:
    async def test_three_replicas_never_exceed_one_controllers_budget(
        self, monkeypatch, redis_port
    ):
        settings = _settings(monkeypatch, redis_port)
        replicas = [_make(settings) for _ in range(3)]

        stamps = await _burst(replicas, LIMIT * 2)

        assert _max_in_any_window(stamps, PERIOD * 0.95) <= LIMIT
        assert stamps[LIMIT - 1] < 0.5  # the first window's budget is not delayed
        assert stamps[LIMIT] >= PERIOD * 0.8  # the next call waited for the window

    async def test_per_process_limiters_would_multiply_the_rate(self, monkeypatch, redis_port):
        # What the shared bucket fixes: three local buckets let 3x through at once.
        settings = _settings(monkeypatch, None)
        replicas = [_make(settings) for _ in range(3)]

        stamps = await _burst(replicas, LIMIT * 3)

        assert _max_in_any_window(stamps, PERIOD * 0.95) == LIMIT * 3

    async def test_different_controllers_do_not_share(self, monkeypatch, redis_port):
        a = _make(_settings(monkeypatch, redis_port, UNIFI_LOCAL_HOST="10.0.0.1"))
        b = _make(_settings(monkeypatch, redis_port, UNIFI_LOCAL_HOST="10.0.0.2"))

        stamps = await _burst([a, b], LIMIT * 2)

        assert stamps[-1] < 0.5  # each had its own full budget


class TestRedisUnavailable:
    async def test_falls_back_to_a_local_bucket(self, monkeypatch, redis_port, caplog):
        _settings(monkeypatch, redis_port)
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # nothing listens
        limiter = _make(Settings())

        with caplog.at_level("WARNING"):
            stamps = await _burst([limiter], LIMIT)

        assert len(stamps) == LIMIT
        assert "local" in caplog.text.lower()

    async def test_three_replicas_stay_near_the_budget_during_an_outage(
        self, monkeypatch, redis_port
    ):
        # Without the share, three replicas would each send the full budget.
        _settings(monkeypatch, redis_port, UNIFI_FLEET_EXPECTED_REPLICAS="2")
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # nothing listens
        replicas = []
        for _ in range(2):  # two processes, each with its own fallback bucket
            monkeypatch.setattr("src.api.rate_limit._fallbacks", {})
            replicas.append(_make(Settings()))

        stamps = await _burst(replicas, 2 * LIMIT)

        assert len([t for t in stamps if t < PERIOD * 0.5]) == LIMIT  # 2 x LIMIT/2 at once

    def test_fallback_budget(self, monkeypatch):
        from src.api.rate_limit import fallback_budget

        assert fallback_budget(_settings(monkeypatch, None)) == LIMIT
        assert fallback_budget(_settings(monkeypatch, None, UNIFI_FLEET_EXPECTED_REPLICAS="3")) == 1
        assert (
            fallback_budget(_settings(monkeypatch, None, UNIFI_FLEET_EXPECTED_REPLICAS="99")) == 1
        )
        partial = Settings.model_construct(rate_limit_requests=8, fleet_expected_replicas=None)
        assert fallback_budget(partial) == 8

    async def test_clients_of_one_controller_share_the_fallback(self, monkeypatch, redis_port):
        # MCP resources build a client per read outside the pool; during an
        # outage they must not each get a fresh share of the budget.
        _settings(monkeypatch, redis_port, UNIFI_FLEET_EXPECTED_REPLICAS="2")
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # nothing listens
        clients = [_make(Settings()) for _ in range(3)]

        assert clients[0]._fallback is clients[1]._fallback is clients[2]._fallback
        stamps = await _burst(clients, LIMIT)
        assert len([t for t in stamps if t < PERIOD * 0.5]) == LIMIT // 2

    def test_without_redis_a_replica_keeps_the_full_budget(self, monkeypatch):
        limiter = _make(_settings(monkeypatch, None, UNIFI_FLEET_EXPECTED_REPLICAS="4"))
        assert limiter.requests_per_period == LIMIT


class TestClientWiring:
    async def test_pooled_clients_share_the_redis_limiter(self, monkeypatch, redis_port):
        from src.api.client import UniFiClient
        from src.api.pool import ClientPool, active_pool

        settings = _settings(monkeypatch, redis_port)
        pool = ClientPool()
        token = active_pool.set(pool)
        try:
            first = UniFiClient(settings)
            second = UniFiClient(settings)
        finally:
            active_pool.reset(token)

        assert isinstance(first.rate_limiter, RedisRateLimiter)
        assert first.rate_limiter is second.rate_limiter
        await first.close()
        await second.close()
        await pool.aclose()

    async def test_unpooled_clients_use_the_shared_window_too(self, monkeypatch, redis_port):
        # MCP resources and the debug tool build clients outside the pool.
        from src.api.client import UniFiClient

        settings = _settings(monkeypatch, redis_port)
        client = UniFiClient(settings)

        assert isinstance(client.rate_limiter, RedisRateLimiter)
        assert client.rate_limiter.key == bucket_key(settings)
        await client.close()

    async def test_unpooled_clients_without_redis_keep_a_local_bucket(self, monkeypatch):
        from src.api.client import UniFiClient

        client = UniFiClient(_settings(monkeypatch, None))

        assert type(client.rate_limiter) is RateLimiter
        await client.close()
