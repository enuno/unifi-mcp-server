"""Degradation drills (docs/FLEET_SCALING_PLAN.md Phase 5): Postgres or Redis down.

Behavior already covered elsewhere and not repeated here: the registry keeps
serving its last snapshot (test_fleet_store), the audit store refuses writes
but not reads (test_audit_store), token lookups fail closed (test_tokens),
the read cache is bypassed (test_read_cache), the rate limit falls back to a
share of the budget (test_rate_limit) and pub/sub reconnects (test_registry_bus).

These cover what remains: no error from an unreachable database echoes its
credentials, and the worker rides out either store going away.
"""

from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("sqlalchemy")

from src.api.pool import ClientPool  # noqa: E402
from src.config.config import APIType, Settings  # noqa: E402
from src.fleet import ControllerProfile  # noqa: E402
from src.fleet.db import audit_store  # noqa: E402
from src.fleet.db.schema import make_engine  # noqa: E402
from src.fleet.db.snapshots import SnapshotStore  # noqa: E402
from src.fleet.fleet_tools import build_snapshot_tools  # noqa: E402
from src.worker import runner  # noqa: E402
from src.worker.runner import Worker  # noqa: E402
from src.worker.shards import RedisShards, SoloShards  # noqa: E402

from .test_router import StaticRegistry  # noqa: E402

PASSWORD = "drill-db-password-7f3a"  # pragma: allowlist secret
DEAD_DATABASE = f"postgresql://drill:{PASSWORD}@127.0.0.1:1/unifi_mcp"  # nothing listens


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    for name in ("REDIS_URL", "REDIS_HOST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", "drill-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.0.2.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("DATABASE_URL", DEAD_DATABASE)
    return Settings()


@pytest.fixture
async def dead_engine() -> Any:
    engine = make_engine(DEAD_DATABASE)
    yield engine
    await engine.dispose()


@pytest.fixture
def registry() -> StaticRegistry:
    profile = ControllerProfile(
        name="hq",
        api_type=APIType.LOCAL,
        api_key="hq-key",  # pragma: allowlist secret
        local_host="192.0.2.1",
    )
    return StaticRegistry(profile, default="hq")


def _assert_no_secret(error: BaseException) -> None:
    seen = [error, error.__cause__, error.__context__]
    for item in seen:
        if item is not None:
            assert PASSWORD not in str(item), f"{type(item).__name__} echoes the password"
            assert PASSWORD not in repr(item)


class TestPostgresDown:
    @pytest.mark.parametrize("tool", ["health", "sites", "inventory"])
    async def test_snapshot_tools_fail_without_echoing_credentials(
        self, settings: Settings, dead_engine: Any, registry: StaticRegistry, tool: str
    ) -> None:
        health, sites, inventory = build_snapshot_tools(
            registry, SnapshotStore(dead_engine), settings
        )
        call = {"health": health, "sites": sites, "inventory": inventory}[tool]

        with pytest.raises(Exception) as excinfo:  # noqa: B017 - whatever the driver raises
            await asyncio.wait_for(call(settings=settings), timeout=30)

        _assert_no_secret(excinfo.value)

    @pytest.mark.parametrize("query", ["search", "verify", "chain_heads"])
    async def test_audit_queries_fail_without_echoing_credentials(
        self, dead_engine: Any, query: str
    ) -> None:
        calls = {
            "search": lambda: audit_store.search(dead_engine),
            "verify": lambda: audit_store.verify(dead_engine, None),
            "chain_heads": lambda: audit_store.chain_heads(dead_engine),
        }
        with pytest.raises(Exception) as excinfo:  # noqa: B017
            await asyncio.wait_for(calls[query](), timeout=30)

        _assert_no_secret(excinfo.value)

    async def test_worker_keeps_going_and_logs_no_credentials(
        self,
        settings: Settings,
        dead_engine: Any,
        registry: StaticRegistry,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # The controller answers; recording the result is what fails.
        monkeypatch.setattr("src.api.client.UniFiClient.authenticate", AsyncMock())
        monkeypatch.setattr("src.api.client.UniFiClient.get", AsyncMock(return_value={}))
        now = [0.0]
        worker = Worker(
            settings,
            registry,
            SnapshotStore(dead_engine),
            SoloShards("w-drill"),
            pool=ClientPool(auth_ttl=0),
            clock=lambda: now[0],
            rng=random.Random(1),
        )

        with caplog.at_level(logging.WARNING):
            await worker.tick()
            now[0] += settings.fleet_worker_sync_seconds
            jobs = await worker.tick()
            await asyncio.wait_for(asyncio.gather(*jobs), timeout=60)
            now[0] += settings.fleet_worker_sync_seconds * 2
            again = await worker.tick()  # rescheduled, not wedged
            await asyncio.wait_for(asyncio.gather(*again), timeout=60)

        assert jobs and again
        assert "failed" in caplog.text
        assert PASSWORD not in caplog.text


class TestRedisDown:
    async def test_worker_pauses_instead_of_double_working(
        self,
        settings: Settings,
        registry: StaticRegistry,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Without Redis no worker can know its shard: it runs nothing (rather
        # than everything, which every worker would then do) and keeps trying.
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # nothing listens
        monkeypatch.setattr(runner, "MAX_TICK_SECONDS", 0.01)
        redis_settings = Settings()
        job = AsyncMock()
        monkeypatch.setattr(runner, "check_health", job)
        monkeypatch.setattr(runner, "sync_controller", job)
        worker = Worker(
            redis_settings,
            registry,
            AsyncMock(),
            RedisShards(redis_settings, "w-drill", lease_seconds=3),
            pool=AsyncMock(),
        )
        stop = asyncio.Event()

        async def stop_later() -> None:
            await asyncio.sleep(0.2)
            stop.set()

        with caplog.at_level(logging.WARNING):
            await asyncio.gather(worker.run(stop), stop_later())

        job.assert_not_awaited()
        assert worker.held == set()
        assert caplog.text.count("Worker tick failed") >= 2  # kept retrying
