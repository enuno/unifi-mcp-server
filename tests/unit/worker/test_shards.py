"""Splitting controllers between workers (docs/FLEET_SCALING_PLAN.md §3.5).

Membership and leases run against a fakeredis server over TCP, the same way
several worker processes would share one Redis.
"""

from __future__ import annotations

import asyncio
import threading
from collections import Counter
from collections.abc import Iterator

import pytest

fakeredis = pytest.importorskip("fakeredis")
from src import cache  # noqa: E402
from src.config.config import Settings  # noqa: E402
from src.worker.shards import MEMBERS_KEY, RedisShards, SoloShards, lease_key, owner  # noqa: E402

# The redis module src.cache (and so the code under test) uses. Not
# ``import redis.asyncio``: tests/unit/test_cache.py swaps a stand-in into
# sys.modules["redis"] at collection, before this directory is collected.
aioredis = cache.redis

CONTROLLERS = [f"site-{n:03d}" for n in range(60)]


@pytest.fixture(scope="module")
def redis_port() -> Iterator[int]:
    server = fakeredis.TcpFakeServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, redis_port: int) -> Settings:
    for name in ("REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", "key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
    monkeypatch.setenv("REDIS_URL", f"redis://127.0.0.1:{redis_port}/0")
    return Settings()


@pytest.fixture(autouse=True)
async def _flush(redis_port: int) -> None:
    client = aioredis.Redis(port=redis_port)
    await client.flushdb()
    await client.aclose()


class TestOwner:
    def test_no_workers(self) -> None:
        assert owner("hq", []) is None

    def test_same_answer_whatever_the_order(self) -> None:
        workers = ["w-a", "w-b", "w-c"]
        assert [owner(c, workers) for c in CONTROLLERS] == [
            owner(c, list(reversed(workers))) for c in CONTROLLERS
        ]

    def test_roughly_balanced(self) -> None:
        controllers = [f"c-{n}" for n in range(3000)]
        counts = Counter(owner(c, ["w-a", "w-b", "w-c"]) for c in controllers)
        assert set(counts) == {"w-a", "w-b", "w-c"}
        assert min(counts.values()) > 800

    def test_leaving_moves_only_the_leavers_share(self) -> None:
        before = {c: owner(c, ["w-a", "w-b", "w-c"]) for c in CONTROLLERS}
        after = {c: owner(c, ["w-a", "w-b"]) for c in CONTROLLERS}
        moved = {c for c in CONTROLLERS if before[c] != after[c]}
        assert moved == {c for c in CONTROLLERS if before[c] == "w-c"}


async def test_solo_owns_everything() -> None:
    shards = SoloShards("only")
    assert await shards.claim(["a", "b"]) == {"a", "b"}
    await shards.leave()


class TestRedisShards:
    async def test_workers_split_every_controller_once(self, settings: Settings) -> None:
        workers = [RedisShards(settings, f"w-{n}", lease_seconds=30) for n in range(3)]
        for worker in workers:  # everyone joins before anyone claims
            await worker.members()

        claims = [await worker.claim(CONTROLLERS) for worker in workers]

        assert set().union(*claims) == set(CONTROLLERS)
        assert sum(len(claim) for claim in claims) == len(CONTROLLERS)
        assert all(claims)

    async def test_claim_renews_its_own_leases(self, settings: Settings, redis_port: int) -> None:
        shards = RedisShards(settings, "w-a", lease_seconds=30)
        assert await shards.claim(["hq"]) == {"hq"}
        client = aioredis.Redis(port=redis_port)
        await client.pexpire(lease_key("hq"), 1000)

        assert await shards.claim(["hq"]) == {"hq"}
        assert await client.pttl(lease_key("hq")) > 1000
        await client.aclose()

    async def test_a_lease_held_by_another_worker_is_not_taken(
        self, settings: Settings, redis_port: int
    ) -> None:
        client = aioredis.Redis(port=redis_port)
        await client.set(lease_key("hq"), "w-old", px=30_000)

        assert await RedisShards(settings, "w-a", lease_seconds=30).claim(["hq"]) == set()
        assert await client.get(lease_key("hq")) == b"w-old"
        await client.aclose()

    async def test_joining_worker_gets_controllers_released_to_it(self, settings: Settings) -> None:
        first = RedisShards(settings, "w-a", lease_seconds=30)
        assert await first.claim(CONTROLLERS) == set(CONTROLLERS)

        second = RedisShards(settings, "w-b", lease_seconds=30)
        await second.members()
        kept = await first.claim(CONTROLLERS)  # gives w-b's share away
        taken = await second.claim(CONTROLLERS)

        assert taken and kept
        assert kept | taken == set(CONTROLLERS)
        assert not kept & taken

    async def test_clean_leave_hands_over_at_once(self, settings: Settings) -> None:
        first = RedisShards(settings, "w-a", lease_seconds=30)
        second = RedisShards(settings, "w-b", lease_seconds=30)
        await first.members()
        await second.members()
        await first.claim(CONTROLLERS)
        await second.claim(CONTROLLERS)

        await first.leave()

        assert await second.claim(CONTROLLERS) == set(CONTROLLERS)

    async def test_dead_worker_is_replaced_after_its_lease(self, settings: Settings) -> None:
        lease = 0.4
        dead = RedisShards(settings, "w-dead", lease_seconds=lease)
        alive = RedisShards(settings, "w-alive", lease_seconds=lease)
        await dead.members()
        await alive.members()
        dead_share = await dead.claim(CONTROLLERS)
        assert dead_share
        assert await alive.claim(CONTROLLERS) == set(CONTROLLERS) - dead_share

        # w-dead stops renewing. Within lease + one tick its share moves over.
        await asyncio.sleep(lease + 0.1)

        assert await alive.members() == ["w-alive"]
        assert await alive.claim(CONTROLLERS) == set(CONTROLLERS)

    async def test_leave_keeps_leases_that_changed_hands(
        self, settings: Settings, redis_port: int
    ) -> None:
        shards = RedisShards(settings, "w-a", lease_seconds=30)
        await shards.claim(["hq"])
        client = aioredis.Redis(port=redis_port)
        await client.set(lease_key("hq"), "w-b", px=30_000)

        await shards.leave()

        assert await client.get(lease_key("hq")) == b"w-b"
        assert await client.zrange(MEMBERS_KEY, 0, -1) == []
        await client.aclose()
