"""The worker loop: claim a shard, run each controller's jobs when due.

Every tick the worker renews its membership, learns which controllers it holds
(src/worker/shards.py), and starts the jobs that are due. A controller's first
run is offset by a hash of its name, spread over the job's interval, and each
later run is ``interval × [0.9, 1.1)`` after the previous one, so a thousand
controllers are not all polled at once. At most ``UNIFI_FLEET_WORKER_CONCURRENCY``
jobs run together, and a job never overlaps another run of itself.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from ..api.pool import ClientPool, active_pool
from ..config import Settings
from ..fleet.bus import HealthBus
from ..fleet.db.snapshots import SnapshotStore
from ..fleet.registry import ControllerProfile, ControllerRegistry
from ..utils.logger import get_logger
from .jobs import check_health, sync_controller
from .shards import Shards

logger = get_logger(__name__)

JobKind = Literal["health", "sync"]
JOB_KINDS: tuple[JobKind, ...] = ("health", "sync")

#: Longest pause between ticks, in seconds.
MAX_TICK_SECONDS = 5.0


def first_offset(controller: str, kind: str, interval: float) -> float:
    """Return when, within its first interval, a newly held controller's job runs."""
    digest = hashlib.blake2b(f"{kind}\0{controller}".encode(), digest_size=8).digest()
    return interval * (int.from_bytes(digest, "big") / 2**64)


@dataclass
class _Schedule:
    due: float
    task: asyncio.Task[Any] | None = None


class Worker:
    """Runs health and sync jobs for the controllers this worker holds."""

    def __init__(
        self,
        settings: Settings,
        registry: ControllerRegistry,
        snapshots: SnapshotStore,
        shards: Shards,
        *,
        pool: ClientPool | None = None,
        health_bus: HealthBus | None = None,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        """Create a worker.

        Args:
            settings: Process-wide settings (intervals, concurrency, lease)
            registry: The controllers to work on
            snapshots: Where results are stored
            shards: Which of the controllers this worker holds
            pool: Connections for the jobs (one is made if not given)
            health_bus: Announces healthy controllers to the replicas (made
                from the settings when Redis is configured, if not given)
            clock: Monotonic clock (tests)
            rng: Source of jitter (tests)
        """
        self.settings = settings
        self.registry = registry
        self.snapshots = snapshots
        self.shards = shards
        # Not ``pool or ...``: an empty ClientPool is falsy (it has __len__).
        self.pool = (
            pool
            if pool is not None
            else ClientPool(max_open=settings.fleet_max_open_clients, auth_ttl=0)
        )
        self.health_bus = (
            health_bus if health_bus is not None else HealthBus.from_settings(settings)
        )
        self._clock = clock
        self._rng = rng or random.Random()  # noqa: S311 - jitter, not security
        self._semaphore = asyncio.Semaphore(settings.fleet_worker_concurrency)
        self._schedules: dict[tuple[str, JobKind], _Schedule] = {}
        self._failures: dict[str, int] = {}
        self.held: set[str] = set()

    @property
    def tick_seconds(self) -> float:
        """Pause between ticks: well inside the lease, so leases never lapse."""
        return min(self.settings.fleet_worker_lease_seconds / 3, MAX_TICK_SECONDS)

    def _interval(self, kind: JobKind) -> float:
        if kind == "health":
            return float(self.settings.fleet_worker_health_seconds)
        return float(self.settings.fleet_worker_sync_seconds)

    async def tick(self) -> list[asyncio.Task[Any]]:
        """Claim controllers and start every job that is due.

        Returns:
            The jobs started by this tick
        """
        profiles = {profile.name: profile for profile in await self.registry.list_controllers()}
        held = await self.shards.claim(profiles)
        for gone in self.held - held:
            self._forget(gone)
        self.held = held

        now = self._clock()
        started: list[asyncio.Task[Any]] = []
        for name in sorted(held):
            for kind in JOB_KINDS:
                schedule = self._schedules.get((name, kind))
                if schedule is None:
                    offset = first_offset(name, kind, self._interval(kind))
                    self._schedules[(name, kind)] = _Schedule(due=now + offset)
                    continue
                if schedule.task is not None or schedule.due > now:
                    continue
                schedule.task = asyncio.create_task(
                    self._run(name, kind, profiles[name]), name=f"worker-{kind}-{name}"
                )
                started.append(schedule.task)
        return started

    def _forget(self, name: str) -> None:
        """Drop a controller this worker no longer holds.

        A running job keeps its schedule, so it is still tracked (and awaited
        on shutdown) and cannot be started twice if the controller comes
        back; it drops the schedule itself when it finishes.
        """
        for kind in JOB_KINDS:
            schedule = self._schedules.get((name, kind))
            if schedule is not None and schedule.task is None:
                del self._schedules[(name, kind)]
        self._failures.pop(name, None)

    async def _run(self, name: str, kind: JobKind, profile: ControllerProfile) -> None:
        settings = profile.apply_to(self.settings)
        job: Callable[[], Awaitable[Any]]
        if kind == "health":

            def job() -> Awaitable[Any]:
                return check_health(
                    name,
                    settings,
                    self.snapshots,
                    failures=self._failures,
                    down_after=self.settings.fleet_worker_down_after,
                    bus=self.health_bus,
                )

        else:

            def job() -> Awaitable[Any]:
                return sync_controller(name, settings, self.snapshots)

        token = active_pool.set(self.pool)
        try:
            async with self._semaphore:
                result = await job()
            logger.debug("%s of %s: %s", kind, name, result)
        except Exception as e:
            logger.warning("%s of %s failed: %s: %s", kind, name, type(e).__name__, e)
        finally:
            active_pool.reset(token)
            schedule = self._schedules.get((name, kind))
            if schedule is not None:
                if name not in self.held:  # given away while running
                    del self._schedules[(name, kind)]
                else:
                    jitter = self._rng.uniform(0.9, 1.1)
                    schedule.due = self._clock() + self._interval(kind) * jitter
                    schedule.task = None

    async def run(self, stop: asyncio.Event) -> None:
        """Tick until ``stop`` is set, then give up the shard and wait for running jobs."""
        try:
            while not stop.is_set():
                try:
                    await self.tick()
                except Exception as e:  # Redis or the registry: retry next tick
                    logger.warning("Worker tick failed: %s: %s", type(e).__name__, e)
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=self.tick_seconds)
        finally:
            await self.close()

    async def close(self) -> None:
        """Wait for running jobs, release the shard and close connections."""
        running = [s.task for s in self._schedules.values() if s.task is not None]
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        try:
            await self.shards.leave()
        except Exception as e:  # leases expire on their own
            logger.warning("Could not release the worker's leases: %s", e)
        await self.pool.aclose()
