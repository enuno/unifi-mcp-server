"""Controller rate limits shared across replicas (docs/FLEET_SCALING_PLAN.md §3.3).

Without Redis each process keeps its own token bucket (``RateLimiter``), so N
replicas together send N times ``UNIFI_RATE_LIMIT_REQUESTS``. With Redis
configured every replica draws from one sliding window per controller instead.
Calls to api.ui.com share one window per API key, because the cloud API limits
per key, not per console.

The window is a sorted set of request timestamps (Redis ``TIME``, so replica
clocks do not matter) updated in one ``MULTI`` transaction: drop entries older
than the period, add this request, count. Over the limit, the request takes
its entry back out and waits until the oldest entry leaves the window. No Lua
is needed, and unlike a fixed window it cannot burst at a window boundary.

If Redis stops answering, the limiter falls back to a per-process bucket and
logs a warning: calls keep flowing at the old per-replica rate rather than
failing.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any
from uuid import uuid4

from ..config import APIType, Settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: Namespace of the rate-limit windows. Deliberately outside ``unifi:v1:``,
#: which ReadCache.invalidate_all() clears.
KEY_PREFIX = "unifi:ratelimit:v1"

#: Shortest wait before retrying a full window, in seconds.
MIN_WAIT = 0.01

_CLOUD_TYPES = (APIType.CLOUD_V1, APIType.CLOUD_EA)


def _redis_configured(settings: Settings) -> bool:
    # Same rule as src.cache.redis_configured, without importing src.cache
    # (and so redis) when Redis is not configured.
    return bool(settings.redis_url) or "redis_host" in settings.model_fields_set


def bucket_key(settings: Settings) -> str:
    """Return the Redis key of the window ``settings``' controller draws from.

    Cloud controllers share one window per API key; a local controller gets
    one per connection (host, key, TLS settings). The API key itself never
    appears in the key.
    """
    if settings.api_type in _CLOUD_TYPES:
        digest = hashlib.sha256(settings.api_key.encode("utf-8")).hexdigest()[:32]
        return f"{KEY_PREFIX}:cloud:{digest}"
    from .pool import connection_key

    return f"{KEY_PREFIX}:controller:{connection_key(settings)[:32]}"


def make_rate_limiter(settings: Settings) -> Any:
    """Return the rate limiter for one controller connection.

    A shared :class:`RedisRateLimiter` when Redis is configured and the redis
    package is installed, otherwise the per-process ``RateLimiter``.
    """
    from .client import RateLimiter

    local = RateLimiter(settings.rate_limit_requests, settings.rate_limit_period)
    if not _redis_configured(settings):
        return local
    from .. import cache

    if not cache.REDIS_AVAILABLE:
        return local
    return RedisRateLimiter(
        settings,
        key=bucket_key(settings),
        requests_per_period=settings.rate_limit_requests,
        period_seconds=settings.rate_limit_period,
        fallback=local,
    )


class RedisRateLimiter:
    """At most ``requests_per_period`` calls per sliding period, across replicas."""

    def __init__(
        self,
        settings: Settings,
        *,
        key: str,
        requests_per_period: int,
        period_seconds: int,
        fallback: Any,
    ) -> None:
        """Create a limiter drawing from the window at ``key``.

        Args:
            settings: Settings locating Redis
            key: The shared window (see :func:`bucket_key`)
            requests_per_period: Calls allowed per period
            period_seconds: Length of the sliding window
            fallback: Per-process limiter used while Redis is unavailable
        """
        self._settings = settings
        self.key = key
        self.requests_per_period = requests_per_period
        self.period_ms = period_seconds * 1000
        self._fallback = fallback
        self._warned = False

    def _redis(self) -> Any:
        from .. import cache

        return cache.redis.Redis(connection_pool=cache._shared_pool(self._settings))

    async def acquire(self) -> None:
        """Wait until this call fits in the shared window, then claim a slot."""
        from .. import cache

        try:
            while True:
                wait = await self._try_claim()
                if wait is None:
                    return
                await asyncio.sleep(wait)
        except cache.RedisError as e:
            if not self._warned:
                logger.warning(
                    "Shared rate limit unavailable (%s); falling back to a local, per-replica "
                    "limit for %s",
                    e,
                    self.key,
                )
                self._warned = True
            await self._fallback.acquire()

    async def _try_claim(self) -> float | None:
        """Claim a slot, or return how long to wait before trying again."""
        client = self._redis()
        seconds, micros = await client.time()
        now = seconds * 1000 + micros // 1000
        member = f"{now}:{uuid4().hex}"
        async with client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(self.key, 0, now - self.period_ms)
            pipe.zadd(self.key, {member: now})
            pipe.zcard(self.key)
            pipe.pexpire(self.key, self.period_ms)
            _, _, count, _ = await pipe.execute()
        if int(count) <= self.requests_per_period:
            return None
        await client.zrem(self.key, member)
        oldest = await client.zrange(self.key, 0, 0, withscores=True)
        if not oldest:
            return MIN_WAIT
        free_at = float(oldest[0][1]) + self.period_ms
        wait: float = max((free_at - now) / 1000, MIN_WAIT)
        return wait
