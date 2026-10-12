"""Which worker syncs which controller (docs/FLEET_SCALING_PLAN.md §3.5).

Workers announce themselves in a Redis sorted set (member = worker id, score
= when its heartbeat expires) and split the controllers between the live ones
by rendezvous hashing: each controller goes to the worker with the highest
``hash(worker, controller)``. Every worker computes the same answer from the
same member list, and a worker joining or leaving moves only its own share.

Membership alone can disagree for a moment while a worker joins or dies, so a
worker also takes a lease on each controller it owns (``SET NX PX``) and works
only on controllers whose lease it holds. A dead worker's leases expire after
``lease_seconds`` and the new owner picks the controllers up; a worker giving a
controller away releases the lease at once.

Without Redis there is no coordination: the single worker owns everything.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from ..config import Settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: Namespace of worker keys, outside the ``unifi:v1:`` keys the read cache clears.
KEY_PREFIX = "unifi:worker:v1"
MEMBERS_KEY = f"{KEY_PREFIX}:members"


def lease_key(controller: str) -> str:
    """Return the Redis key of ``controller``'s lease."""
    return f"{KEY_PREFIX}:lease:{controller}"


def _score(worker: str, controller: str) -> int:
    digest = hashlib.blake2b(f"{worker}\0{controller}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def owner(controller: str, workers: Sequence[str]) -> str | None:
    """Return the worker that owns ``controller`` among ``workers`` (None if empty)."""
    if not workers:
        return None
    return max(workers, key=lambda worker: (_score(worker, controller), worker))


class Shards(Protocol):
    """Decides which controllers this worker works on."""

    worker_id: str

    async def claim(self, controllers: Iterable[str]) -> set[str]:
        """Renew this worker's membership and return the controllers it may work on now."""
        ...

    async def leave(self) -> None:
        """Give up membership and every lease (clean shutdown)."""
        ...


class SoloShards:
    """The only worker: owns every controller (no Redis)."""

    def __init__(self, worker_id: str) -> None:
        """Create the shard map of a worker running alone."""
        self.worker_id = worker_id

    async def claim(self, controllers: Iterable[str]) -> set[str]:
        """Return every controller."""
        return set(controllers)

    async def leave(self) -> None:
        """Nothing to give up."""


class RedisShards:
    """Membership, rendezvous ownership and leases in Redis."""

    def __init__(self, settings: Settings, worker_id: str, *, lease_seconds: float) -> None:
        """Create the shard map of one worker.

        Args:
            settings: Settings locating Redis
            worker_id: This worker's identity (unique per process)
            lease_seconds: How long membership and leases last without renewal
        """
        self._settings = settings
        self.worker_id = worker_id
        self.lease_ms = max(1, int(lease_seconds * 1000))
        self._held: set[str] = set()

    def _redis(self) -> Any:
        from .. import cache

        return cache.redis.Redis(connection_pool=cache._shared_pool(self._settings))

    @staticmethod
    async def _now_ms(client: Any) -> int:
        seconds, micros = await client.time()
        return int(seconds) * 1000 + int(micros) // 1000

    async def members(self) -> list[str]:
        """Renew this worker's membership and return every live worker, sorted."""
        client = self._redis()
        now = await self._now_ms(client)
        async with client.pipeline(transaction=True) as pipe:
            pipe.zadd(MEMBERS_KEY, {self.worker_id: now + self.lease_ms})
            pipe.zremrangebyscore(MEMBERS_KEY, "-inf", now)
            pipe.zrange(MEMBERS_KEY, 0, -1)
            *_, raw = await pipe.execute()
        return sorted(str(_text(member)) for member in raw)

    async def claim(self, controllers: Iterable[str]) -> set[str]:
        """Return the controllers this worker owns and holds the lease of.

        Takes or renews the lease of every owned controller and releases the
        leases of controllers that now belong to another worker.
        """
        controllers = list(controllers)
        workers = await self.members()
        mine = [c for c in controllers if owner(c, workers) == self.worker_id]
        client = self._redis()

        async with client.pipeline(transaction=False) as pipe:
            for controller in mine:
                pipe.set(lease_key(controller), self.worker_id, nx=True, px=self.lease_ms)
            taken = await pipe.execute() if mine else []
        held = {c for c, ok in zip(mine, taken, strict=True) if ok}

        # Leases that already existed: renew the ones that are ours.
        existing = [c for c in mine if c not in held]
        if existing:
            async with client.pipeline(transaction=False) as pipe:
                for controller in existing:
                    pipe.get(lease_key(controller))
                holders = await pipe.execute()
            ours = [c for c, h in zip(existing, holders, strict=True) if _text(h) == self.worker_id]
            if ours:
                async with client.pipeline(transaction=False) as pipe:
                    for controller in ours:
                        pipe.pexpire(lease_key(controller), self.lease_ms)
                    await pipe.execute()
            held.update(ours)

        await self._release(client, self._held - set(mine))
        gained, lost = held - self._held, self._held - held
        if gained or lost:
            logger.info(
                "Worker %s now holds %d controllers (+%d, -%d) of %d across %d workers",
                self.worker_id,
                len(held),
                len(gained),
                len(lost),
                len(controllers),
                len(workers),
            )
        self._held = held
        return set(held)

    async def _release(self, client: Any, controllers: Iterable[str]) -> None:
        """Delete the leases of ``controllers`` that this worker still holds."""
        from .. import cache

        for controller in controllers:
            key = lease_key(controller)
            try:
                async with client.pipeline(transaction=True) as pipe:
                    await pipe.watch(key)
                    if _text(await pipe.get(key)) != self.worker_id:
                        await pipe.unwatch()
                        continue
                    pipe.multi()
                    pipe.delete(key)
                    await pipe.execute()
            except cache.redis.WatchError:
                continue  # changed hands meanwhile: not ours to delete

    async def leave(self) -> None:
        """Leave the member set and release every held lease."""
        client = self._redis()
        await self._release(client, self._held)
        self._held = set()
        await client.zrem(MEMBERS_KEY, self.worker_id)


def _text(value: Any) -> str | None:
    if isinstance(value, bytes):
        return value.decode()
    return None if value is None else str(value)
