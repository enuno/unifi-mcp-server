"""Run a fleet worker: ``python -m src.worker``.

Needs DATABASE_URL and UNIFI_FLEET_CREDENTIAL_KEY (the registry), and the
registry schema at this code's revision (``python -m src.fleet.cli migrate``).
With Redis configured (REDIS_URL or REDIS_HOST), any number of workers share
the controllers between them; without it, run exactly one worker.

Exit codes: 0 after a clean shutdown (SIGINT or SIGTERM), 1 on a startup
failure, 2 for missing configuration.
"""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import sys
from uuid import uuid4

from ..config import Settings
from ..utils.exceptions import UniFiMCPException
from ..utils.logger import get_logger
from .shards import Shards

logger = get_logger(__name__)


def worker_id() -> str:
    """Return a unique identity for this worker process."""
    return f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:6]}"


def make_shards(settings: Settings, identity: str) -> Shards:
    """Shard map for this worker: shared through Redis when configured, else solo."""
    from .shards import RedisShards, SoloShards

    configured = bool(settings.redis_url) or "redis_host" in settings.model_fields_set
    if configured:
        from .. import cache

        if cache.REDIS_AVAILABLE:
            return RedisShards(
                settings, identity, lease_seconds=settings.fleet_worker_lease_seconds
            )
        logger.warning("Redis is configured but the redis package is not installed")
    logger.warning(
        "No Redis: this worker handles every controller; run only one worker without Redis"
    )
    return SoloShards(identity)


async def run(settings: Settings, stop: asyncio.Event) -> int:
    """Start the registry and run the worker until ``stop`` is set."""
    from ..fleet.db.snapshots import SnapshotStore
    from ..fleet.postgres_registry import PostgresRegistry
    from .runner import Worker

    registry = PostgresRegistry.from_settings(settings)
    await registry.start(seed=False)
    identity = worker_id()
    worker = Worker(
        settings,
        registry,
        SnapshotStore(registry.store.engine),
        make_shards(settings, identity),
    )
    logger.info("Fleet worker %s started", identity)
    try:
        await worker.run(stop)
    finally:
        await registry.stop()
    logger.info("Fleet worker %s stopped", identity)
    return 0


async def _main() -> int:
    settings = Settings()
    if not settings.database_url:
        print("The fleet worker needs DATABASE_URL (the controller registry)", file=sys.stderr)
        return 2
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop.set)
    try:
        return await run(settings, stop)
    except UniFiMCPException as e:
        print(f"Fleet worker could not start: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Entry point."""
    return asyncio.run(_main())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
