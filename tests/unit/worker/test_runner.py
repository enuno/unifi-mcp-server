"""The worker loop: staggered first runs, jittered intervals, no overlap, shard changes."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Iterable
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.config.config import APIType, Settings
from src.fleet.registry import ControllerProfile
from src.worker import runner
from src.worker.runner import Worker, first_offset

KEY = "k"  # pragma: allowlist secret


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Registry:
    def __init__(self, names: Iterable[str]) -> None:
        self.profiles = [
            ControllerProfile(name=n, api_type=APIType.LOCAL, api_key=KEY, local_host=f"10.0.0.{i}")
            for i, n in enumerate(names, start=1)
        ]

    async def list_controllers(self) -> list[ControllerProfile]:
        return list(self.profiles)

    async def get_controller(self, name: str) -> ControllerProfile:  # pragma: no cover
        raise NotImplementedError

    async def default_controller(self) -> str | None:  # pragma: no cover
        return None


class Shards:
    def __init__(self, held: set[str] | None = None) -> None:
        self.worker_id = "w-test"
        self.held = held
        self.left = False

    async def claim(self, controllers: Iterable[str]) -> set[str]:
        names = set(controllers)
        return names if self.held is None else names & self.held

    async def leave(self) -> None:
        self.left = True


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", KEY)
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
    monkeypatch.setenv("UNIFI_FLEET_WORKER_HEALTH_SECONDS", "60")
    monkeypatch.setenv("UNIFI_FLEET_WORKER_SYNC_SECONDS", "900")
    monkeypatch.setenv("UNIFI_FLEET_WORKER_CONCURRENCY", "2")
    return Settings()


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """Replace the jobs with recorders."""
    recorded: dict[str, list[Any]] = {"health": [], "sync": []}

    async def health(name: str, settings: Settings, snapshots: Any, **kwargs: Any) -> str:
        recorded["health"].append((name, settings.local_host, kwargs["down_after"]))
        return "ok"

    async def sync(name: str, settings: Settings, snapshots: Any) -> None:
        recorded["sync"].append(name)

    monkeypatch.setattr(runner, "check_health", health)
    monkeypatch.setattr(runner, "sync_controller", sync)
    return recorded


def _worker(settings: Settings, names: Iterable[str], **kwargs: Any) -> tuple[Worker, Clock]:
    clock = Clock()
    shards = kwargs.pop("shards", Shards())
    worker = Worker(
        settings,
        Registry(names),
        AsyncMock(),
        shards,
        pool=AsyncMock(),
        clock=clock,
        rng=random.Random(7),
    )
    return worker, clock


async def _settle(tasks: list[asyncio.Task[Any]]) -> None:
    await asyncio.gather(*tasks)


class TestFirstOffset:
    def test_within_the_interval_and_stable(self) -> None:
        assert 0 <= first_offset("hq", "health", 60) < 60
        assert first_offset("hq", "health", 60) == first_offset("hq", "health", 60)

    def test_spread_over_the_interval(self) -> None:
        offsets = [first_offset(f"c-{n}", "sync", 900) for n in range(1000)]
        buckets = {int(offset // 90) for offset in offsets}
        assert buckets == set(range(10))  # every tenth of the interval is used


class TestTick:
    async def test_first_tick_only_schedules(
        self, settings: Settings, calls: dict[str, list[Any]]
    ) -> None:
        worker, _ = _worker(settings, ["hq", "branch"])
        assert await worker.tick() == []
        assert worker.held == {"hq", "branch"}

    async def test_runs_when_due_with_the_controllers_settings(
        self, settings: Settings, calls: dict[str, list[Any]]
    ) -> None:
        worker, clock = _worker(settings, ["hq", "branch"])
        await worker.tick()

        clock.now += 60
        await _settle(await worker.tick())

        assert sorted(calls["health"]) == [("branch", "10.0.0.2", 3), ("hq", "10.0.0.1", 3)]
        assert calls["sync"] == []  # sync is due within 900 s, not 60

        clock.now += 900
        await _settle(await worker.tick())
        assert sorted(calls["sync"]) == ["branch", "hq"]

    async def test_next_run_is_one_jittered_interval_later(
        self, settings: Settings, calls: dict[str, list[Any]]
    ) -> None:
        worker, clock = _worker(settings, ["hq"])
        await worker.tick()
        clock.now += 60
        await _settle(await worker.tick())

        clock.now += 60 * 0.9 - 1
        assert await worker.tick() == []
        clock.now += 60 * 0.2 + 1
        await _settle(await worker.tick())
        assert len(calls["health"]) == 2

    async def test_a_running_job_is_not_started_again(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        release = asyncio.Event()
        started: list[str] = []

        async def slow(name: str, *args: Any, **kwargs: Any) -> None:
            started.append(name)
            await release.wait()

        monkeypatch.setattr(runner, "check_health", slow)
        monkeypatch.setattr(runner, "sync_controller", AsyncMock())
        worker, clock = _worker(settings, ["hq"])
        await worker.tick()
        clock.now += 60
        first = await worker.tick()
        await asyncio.sleep(0)

        clock.now += 600  # health is due again; sync may be too, and may run
        later = await worker.tick()
        assert not [t for t in later if t.get_name().startswith("worker-health-")]
        assert started == ["hq"]
        release.set()
        await _settle(first + later)

    async def test_concurrency_is_capped(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        running, peak = 0, 0

        async def job(*args: Any, **kwargs: Any) -> None:
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1

        monkeypatch.setattr(runner, "check_health", job)
        monkeypatch.setattr(runner, "sync_controller", job)
        worker, clock = _worker(settings, [f"c-{n}" for n in range(10)])
        await worker.tick()
        clock.now += 1000

        await _settle(await worker.tick())

        assert peak == settings.fleet_worker_concurrency

    async def test_job_failure_is_logged_and_rescheduled(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(runner, "check_health", AsyncMock(side_effect=RuntimeError("boom")))
        monkeypatch.setattr(runner, "sync_controller", AsyncMock())
        worker, clock = _worker(settings, ["hq"])
        await worker.tick()
        clock.now += 60

        await _settle(await worker.tick())

        clock.now += 70
        assert len(await worker.tick()) == 1

    async def test_losing_a_controller_forgets_it(
        self, settings: Settings, calls: dict[str, list[Any]]
    ) -> None:
        shards = Shards({"hq", "branch"})
        worker, clock = _worker(settings, ["hq", "branch"], shards=shards)
        await worker.tick()

        shards.held = {"hq"}
        clock.now += 60
        await _settle(await worker.tick())

        assert [call[0] for call in calls["health"]] == ["hq"]
        assert worker.held == {"hq"}

        # Regained later: scheduled afresh rather than run at once.
        shards.held = {"hq", "branch"}
        assert all("branch" not in t.get_name() for t in await worker.tick())


class TestRun:
    async def test_stops_and_releases(self, settings: Settings, calls: Any) -> None:
        shards = Shards()
        worker, _ = _worker(settings, ["hq"], shards=shards)
        stop = asyncio.Event()
        stop.set()

        await worker.run(stop)

        assert shards.left
        worker.pool.aclose.assert_awaited_once()

    async def test_a_failing_tick_does_not_stop_the_worker(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        worker, _ = _worker(settings, ["hq"])
        stop = asyncio.Event()
        ticks = 0

        async def tick() -> list[Any]:
            nonlocal ticks
            ticks += 1
            if ticks == 2:
                stop.set()
            raise RuntimeError("redis down")

        monkeypatch.setattr(worker, "tick", tick)
        monkeypatch.setattr(runner, "MAX_TICK_SECONDS", 0.01)

        await asyncio.wait_for(worker.run(stop), timeout=5)

        assert ticks == 2

    async def test_close_survives_a_failed_release(self, settings: Settings) -> None:
        shards = Shards()
        shards.leave = AsyncMock(side_effect=RuntimeError("redis down"))  # type: ignore[method-assign]
        worker, _ = _worker(settings, ["hq"], shards=shards)

        await worker.close()

        worker.pool.aclose.assert_awaited_once()

    def test_tick_stays_inside_the_lease(self, settings: Settings) -> None:
        worker, _ = _worker(settings, [])
        assert worker.tick_seconds == runner.MAX_TICK_SECONDS
        assert worker.tick_seconds < settings.fleet_worker_lease_seconds / 2


class TestPool:
    def test_an_empty_pool_passed_in_is_kept(self, settings: Settings) -> None:
        from src.api.pool import ClientPool

        pool = ClientPool()
        assert len(pool) == 0  # falsy, which once made the worker replace it
        worker = Worker(settings, Registry([]), AsyncMock(), Shards(), pool=pool)
        assert worker.pool is pool

    def test_default_pool_probes_on_every_health_check(self, settings: Settings) -> None:
        worker = Worker(settings, Registry([]), AsyncMock(), Shards())
        assert worker.pool.auth_ttl == 0
        assert worker.pool.max_open == settings.fleet_max_open_clients
