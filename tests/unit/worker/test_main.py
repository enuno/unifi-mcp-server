"""``python -m src.worker``: configuration checks, shard choice, startup and shutdown."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config.config import Settings
from src.utils.exceptions import ConfigurationError
from src.worker import __main__ as worker_main
from src.worker.shards import RedisShards, SoloShards


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("REDIS_URL", "REDIS_HOST", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", "k")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")


def test_worker_ids_are_unique() -> None:
    assert worker_main.worker_id() != worker_main.worker_id()


class TestMakeShards:
    def test_solo_without_redis(self, env: None) -> None:
        assert isinstance(worker_main.make_shards(Settings(), "w"), SoloShards)

    def test_redis_when_configured(self, env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
        monkeypatch.setenv("UNIFI_FLEET_WORKER_LEASE_SECONDS", "12")
        shards = worker_main.make_shards(Settings(), "w")
        assert isinstance(shards, RedisShards)
        assert shards.lease_ms == 12_000

    def test_solo_when_redis_is_not_installed(
        self, env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REDIS_HOST", "redis")
        monkeypatch.setattr("src.cache.REDIS_AVAILABLE", False)
        assert isinstance(worker_main.make_shards(Settings(), "w"), SoloShards)


def test_needs_a_database(env: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert worker_main.main() == 2
    assert "DATABASE_URL" in capsys.readouterr().err


def test_startup_failure_exits_1(
    env: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@localhost/db")
    monkeypatch.setattr(
        worker_main, "run", AsyncMock(side_effect=ConfigurationError("no credential key"))
    )
    assert worker_main.main() == 1
    assert "no credential key" in capsys.readouterr().err


async def test_run_starts_without_seeding_and_stops_the_registry(
    env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = MagicMock()
    registry.start = AsyncMock()
    registry.stop = AsyncMock()
    registry.list_controllers = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "src.fleet.postgres_registry.PostgresRegistry.from_settings", lambda s: registry
    )
    seen: dict[str, Any] = {}

    async def fake_run(self: Any, stop: asyncio.Event) -> None:
        seen["worker"] = self

    monkeypatch.setattr("src.worker.runner.Worker.run", fake_run)
    stop = asyncio.Event()

    assert await worker_main.run(Settings(), stop) == 0

    registry.start.assert_awaited_once_with(seed=False)
    registry.stop.assert_awaited_once()
    assert isinstance(seen["worker"].shards, SoloShards)
