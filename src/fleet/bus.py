"""``registry:changed`` notifications between replicas (docs/FLEET_SCALING_PLAN.md §3.3).

Each replica serves controller lookups from an in-memory snapshot of the
Postgres registry. A change made through one replica's admin tools reloads
that replica's snapshot at once, but the others only at their next periodic
refresh. With Redis configured, the changing replica publishes on
:data:`CHANNEL` and every other replica reloads immediately; the periodic
refresh stays as the backstop for a missed message.

A replica ignores its own messages (it has already refreshed). Redis being
unavailable never fails a registry change: publishing logs a warning, and
the listener keeps retrying.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from ..config import Settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: Pub/sub channel, outside the ``unifi:v1:`` keys the read cache clears.
CHANNEL = "unifi:registry:v1:changed"


def _redis_configured(settings: Settings) -> bool:
    # src.cache.redis_configured, without importing redis when unconfigured.
    return bool(settings.redis_url) or "redis_host" in settings.model_fields_set


class RegistryBus:
    """Publish and receive registry-change notifications over Redis pub/sub."""

    #: Seconds between reconnection attempts after Redis fails.
    retry_seconds: float = 5.0

    def __init__(self, settings: Settings, *, instance_id: str | None = None) -> None:
        """Create a bus.

        Args:
            settings: Settings locating Redis
            instance_id: This replica's identity, to skip its own messages
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
    def from_settings(cls, settings: Settings) -> RegistryBus | None:
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

    async def publish(self) -> None:
        """Tell the other replicas the registry changed."""
        from .. import cache

        try:
            await self._redis().publish(CHANNEL, json.dumps({"origin": self.instance_id}))
        except cache.RedisError as e:
            logger.warning(
                "Could not announce a registry change to other replicas (%s); they pick it "
                "up at their next periodic refresh",
                e,
            )

    async def listen(self, on_change: Callable[[], Awaitable[Any]]) -> None:
        """Call ``on_change`` for every change announced by another replica.

        Runs until cancelled, reconnecting after Redis errors.
        """
        from .. import cache

        while True:
            pubsub = self._redis().pubsub()
            try:
                await pubsub.subscribe(CHANNEL)
                self.subscribed.set()
                async for message in pubsub.listen():
                    if message.get("type") == "message" and self._from_elsewhere(message):
                        try:
                            await on_change()
                        except Exception as e:  # keep listening; the next refresh retries
                            logger.warning("Registry refresh after a change failed: %s", e)
            except cache.RedisError as e:
                self.subscribed.clear()
                logger.warning(
                    "Registry change listener lost Redis (%s); retrying in %ss",
                    e,
                    self.retry_seconds,
                )
                await asyncio.sleep(self.retry_seconds)
            finally:
                try:
                    await pubsub.aclose()
                except Exception:  # noqa: S110 - best effort after a failure
                    pass

    def _from_elsewhere(self, message: dict[str, Any]) -> bool:
        try:
            origin = json.loads(message.get("data") or "{}").get("origin")
        except (TypeError, ValueError):
            return True  # unreadable: refreshing once too often is harmless
        return bool(origin != self.instance_id)
