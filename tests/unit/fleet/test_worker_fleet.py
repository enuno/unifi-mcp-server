"""A worker end to end: Postgres registry in, mock controllers over HTTP, snapshots out."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

pytest.importorskip("sqlalchemy")

from src.api.pool import ClientPool  # noqa: E402
from src.config.config import APIType, Settings  # noqa: E402
from src.fleet.db.snapshots import SnapshotStore  # noqa: E402
from src.fleet.postgres_registry import PostgresRegistry  # noqa: E402
from src.worker.runner import Worker  # noqa: E402
from src.worker.shards import SoloShards  # noqa: E402

KEY = "fleet-key-0123456789"  # pragma: allowlist secret


def _controller(request: httpx.Request) -> httpx.Response:
    host, path = request.url.host, request.url.path
    if host == "10.0.0.2":  # the branch office is unreachable
        raise httpx.ConnectError("unreachable", request=request)
    if path == "/proxy/network/integration/v1/sites":
        return httpx.Response(200, json={"data": [{"id": "s-1", "internalReference": "default"}]})
    if path == "/proxy/network/integration/v1/info":
        return httpx.Response(200, json={"applicationVersion": "9.4.19"})
    if path == "/proxy/network/integration/v1/sites/s-1/devices":
        return httpx.Response(
            200, json={"data": [{"id": "d-1", "model": "UDM", "firmwareVersion": "4.0.6"}]}
        )
    return httpx.Response(404)


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, database_url: str, credential_key: str
) -> Settings:
    for name in ("REDIS_URL", "REDIS_HOST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", KEY)
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
    monkeypatch.setenv("UNIFI_MAX_RETRIES", "0")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UNIFI_FLEET_WORKER_DOWN_AFTER", "1")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr("src.utils.audit._audit_logger", None)
    return Settings()


async def test_worker_fills_the_snapshots(settings: Settings, migrated_engine: Any) -> None:
    registry = PostgresRegistry.from_settings(settings)
    await registry.store.add_controller(
        name="hq", api_type=APIType.LOCAL, api_key=KEY, local_host="10.0.0.1"
    )
    await registry.store.add_controller(
        name="branch", api_type=APIType.LOCAL, api_key=KEY, local_host="10.0.0.2"
    )
    await registry.start(seed=False)
    snapshots = SnapshotStore(registry.store.engine)
    clock = Clock()
    worker = Worker(
        settings,
        registry,
        snapshots,
        SoloShards("w-1"),
        pool=ClientPool(auth_ttl=0, transport=httpx.MockTransport(_controller)),
        clock=clock,
    )
    try:
        await worker.tick()
        clock.now += settings.fleet_worker_sync_seconds
        await asyncio.gather(*await worker.tick())

        hq, branch = await snapshots.health("hq"), await snapshots.health("branch")
        assert (hq.health, hq.capabilities) == (
            "ok",
            {"api_type": "local", "network_version": "9.4.19"},
        )
        assert branch.health == "down"
        assert branch.last_seen_at is None
        assert [s.short_name for s in await snapshots.list_sites("hq")] == ["default"]
        devices = await snapshots.list_inventory("hq")
        assert [(d.device_id, d.model, d.version) for d in devices] == [("d-1", "UDM", "4.0.6")]
        assert await snapshots.list_sites("branch") == []
    finally:
        await worker.close()
        await registry.stop()
