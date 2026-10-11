"""Redis pub/sub between replicas and workers (docs/FLEET_SCALING_PLAN.md §3.3).

``registry:changed`` (:class:`RegistryBus`):

Each replica serves controller lookups from an in-memory snapshot of the
Postgres registry. A change made through one replica's admin tools reloads
that replica's snapshot at once, but the others only at their next periodic
refresh. With Redis configured, the changing replica publishes on
:data:`CHANNEL` and every other replica reloads immediately; the periodic
refresh stays as the backstop for a missed message.

A replica ignores its own messages (it has already refreshed). Redis being
unavailable never fails a registry change: publishing logs a warning, and
the listener keeps retrying.

``health:up`` (:class:`HealthBus`): a worker announces every successful
health check, and each replica moves an open circuit breaker for that
controller to half-open, so calls resume without waiting out the cooldown
(:meth:`~src.api.pool.ClientPool.health_ok`).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from ..config import Settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: Pub/sub channels, outside the ``unifi:v1:`` keys the read cache clears.
CHANNEL = "unifi:registry:v1:changed"
HEALTH_CHANNEL = "unifi:health:v1:up"


def _redis_configured(settings: Settings) -> bool:
    # src.cache.redis_configured, without importing redis when unconfigured.
    return bool(settings.redis_url) or "redis_host" in settings.model_fields_set


class _Bus:
    """One pub/sub channel: publish JSON messages, hand other processes' to a handler."""

    #: The channel this bus uses.
    channel: str = CHANNEL
    #: What the listener's warnings call it.
    label: str = "Registry change"
    #: Seconds between reconnection attempts after Redis fails.
    retry_seconds: float = 5.0

    def __init__(self, settings: Settings, *, instance_id: str | None = None) -> None:
        """Create a bus.

        Args:
            settings: Settings locating Redis
            instance_id: This process's identity, to skip its own messages
                (defaults to the process's audit instance id)
        """
        if instance_id is None:
            from ..utils.audit import INSTANCE_ID

            instance_id = INSTANCE_ID
        self._settings = settings
        self.instance_id = instance_id
        #: Set once the listener is subscribed (tests wait on it).
        self.subscribed = asyncio.Event()

    @classmethod
    def from_settings(cls, settings: Settings) -> Any:
        """Return a bus when Redis is configured and installed, otherwise None."""
        if not _redis_configured(settings):
            return None
        from .. import cache

        if not cache.REDIS_AVAILABLE:
            return None
        return cls(settings)

    def _redis(self) -> Any:
        from .. import cache

        return cache.redis.Redis(connection_pool=cache._shared_pool(self._settings))

    async def _publish(self, payload: dict[str, Any], failure: str) -> None:
        from .. import cache

        try:
            await self._redis().publish(
                self.channel, json.dumps({**payload, "origin": self.instance_id})
            )
        except cache.RedisError as e:
            logger.warning(failure, e)

    async def _listen(self, handler: Callable[[dict[str, Any]], Awaitable[Any]]) -> None:
        """Call ``handler`` with every message another process publishes.

        Runs until cancelled, reconnecting after Redis errors.
        """
        from .. import cache

        while True:
            pubsub = self._redis().pubsub()
            try:
                await pubsub.subscribe(self.channel)
                self.subscribed.set()
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    payload = self._payload(message)
                    if payload.get("origin") == self.instance_id:
                        continue
                    try:
                        await handler(payload)
                    except Exception as e:  # keep listening
                        logger.warning("%s handling failed: %s", self.label, e)
            except cache.RedisError as e:
                self.subscribed.clear()
                logger.warning(
                    "%s listener lost Redis (%s); retrying in %ss",
                    self.label,
                    e,
                    self.retry_seconds,
                )
                await asyncio.sleep(self.retry_seconds)
            finally:
                try:
                    await pubsub.aclose()
                except Exception:  # noqa: S110 - best effort after a failure
                    pass

    @staticmethod
    def _payload(message: dict[str, Any]) -> dict[str, Any]:
        try:
            payload = json.loads(message.get("data") or "{}")
        except (TypeError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}


class RegistryBus(_Bus):
    """Publish and receive registry-change notifications over Redis pub/sub."""

    async def publish(self) -> None:
        """Tell the other replicas the registry changed."""
        await self._publish(
            {},
            "Could not announce a registry change to other replicas (%s); they pick it "
            "up at their next periodic refresh",
        )

    async def listen(self, on_change: Callable[[], Awaitable[Any]]) -> None:
        """Call ``on_change`` for every change announced by another replica.

        An unreadable message also triggers a refresh: refreshing once too
        often is harmless. Runs until cancelled, reconnecting after Redis errors.
        """

        async def handle(payload: dict[str, Any]) -> None:
            await on_change()

        await self._listen(handle)


class HealthBus(_Bus):
    """Workers announce healthy controllers; replicas half-open their circuit breakers."""

    channel = HEALTH_CHANNEL
    label = "Controller health"

    async def publish_ok(self, key: str, checked_at: float) -> None:
        """Announce that the controller with connection key ``key`` answered a health check.

        Args:
            key: :func:`~src.api.pool.connection_key` of its settings (a hash; no
                credential is sent)
            checked_at: When the check started (``time.time()``)
        """
        await self._publish(
            {"key": key, "checked_at": checked_at},
            "Could not announce a healthy controller to the replicas (%s); their circuit "
            "breakers recover after the cooldown instead",
        )

    async def listen(self, on_ok: Callable[[str, float], Any]) -> None:
        """Call ``on_ok(key, checked_at)`` for every healthy controller announced."""

        async def handle(payload: dict[str, Any]) -> None:
            key, checked_at = payload.get("key"), payload.get("checked_at")
            if isinstance(key, str) and isinstance(checked_at, int | float):
                result = on_ok(key, float(checked_at))
                if asyncio.iscoroutine(result):
                    await result

        await self._listen(handle)
