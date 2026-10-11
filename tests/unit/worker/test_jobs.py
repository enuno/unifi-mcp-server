"""The worker's health and sync jobs, against a mock controller over HTTP.

Requests go through the real UniFiClient (pooled, as the worker runs it), so
endpoint translation, envelopes and pagination are exercised; the snapshot
store is a recording fake.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from src.api.pool import ClientPool, active_pool
from src.config.config import Settings
from src.worker import jobs

SITES = [
    {"id": "11111111-aaaa", "internalReference": "default", "name": "Default"},
    {"id": "22222222-bbbb", "internalReference": "lab", "name": "Lab"},
]


class MockController:
    """Answers the integration API routes the jobs use."""

    def __init__(self, *, devices: int = 3, info: Any = None, fail: bool = False) -> None:
        self.devices = devices
        self.info = info if info is not None else {"applicationVersion": "9.4.19"}
        self.fail = fail
        self.paths: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.paths.append(path)
        if self.fail:
            return httpx.Response(503, json={"error": "down"})
        offset = int(request.url.params.get("offset", 0))
        limit = int(request.url.params.get("limit", 25))
        if path == "/proxy/network/integration/v1/sites":
            return httpx.Response(200, json={"data": SITES[offset : offset + limit]})
        if path == "/proxy/network/integration/v1/info":
            return httpx.Response(200, json=self.info)
        if path.endswith("/devices"):
            site = path.split("/")[-2]
            devices = [
                {
                    "id": f"{site}-dev-{n:04d}",
                    "macAddress": f"aa:bb:cc:00:{n // 256:02x}:{n % 256:02x}",
                    "name": f"AP {n}",
                    "model": "U7PRO",
                    "firmwareVersion": "8.0.1",
                    "state": "ONLINE",
                }
                for n in range(self.devices)
            ]
            return httpx.Response(200, json={"data": devices[offset : offset + limit]})
        return httpx.Response(404, json={"error": path})


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    for name in ("REDIS_URL", "REDIS_HOST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", "key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
    monkeypatch.setenv("UNIFI_MAX_RETRIES", "0")
    return Settings()


@pytest.fixture
def controller() -> MockController:
    return MockController()


@pytest.fixture
def pool(controller: MockController) -> Iterator[ClientPool]:
    pool = ClientPool(auth_ttl=0, transport=httpx.MockTransport(controller.handle))
    token = active_pool.set(pool)
    yield pool
    active_pool.reset(token)


@pytest.fixture
def snapshots() -> AsyncMock:
    store = AsyncMock()
    store.replace_sites.side_effect = lambda name, sites: len(sites)
    store.replace_inventory.side_effect = lambda name, site, devices: len(devices)
    return store


class TestCheckHealth:
    async def test_ok_records_version(
        self, settings: Settings, pool: ClientPool, snapshots: AsyncMock
    ) -> None:
        failures = {"hq": 2}

        health = await jobs.check_health("hq", settings, snapshots, failures=failures, down_after=3)

        assert health == "ok"
        assert failures == {}
        snapshots.record_health.assert_awaited_once_with(
            "hq", "ok", capabilities={"api_type": "local", "network_version": "9.4.19"}
        )

    @pytest.mark.parametrize(
        "info", [{"data": [{"applicationVersion": "10.0.1"}]}, [{"applicationVersion": "10.0.1"}]]
    )
    async def test_version_in_an_envelope(
        self,
        settings: Settings,
        pool: ClientPool,
        snapshots: AsyncMock,
        controller: MockController,
        info: Any,
    ) -> None:
        controller.info = info
        await jobs.check_health("hq", settings, snapshots, failures={}, down_after=3)
        capabilities = snapshots.record_health.await_args.kwargs["capabilities"]
        assert capabilities["network_version"] == "10.0.1"

    async def test_missing_info_is_still_healthy(
        self,
        settings: Settings,
        pool: ClientPool,
        snapshots: AsyncMock,
        controller: MockController,
    ) -> None:
        controller.info = {"unexpected": True}
        assert await jobs.check_health("hq", settings, snapshots, failures={}, down_after=3) == "ok"
        assert snapshots.record_health.await_args.kwargs["capabilities"] == {"api_type": "local"}

    async def test_info_error_is_still_healthy(
        self, settings: Settings, pool: ClientPool, snapshots: AsyncMock, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr(
            "src.api.client.UniFiClient.get", AsyncMock(side_effect=RuntimeError("no info"))
        )
        monkeypatch.setattr("src.api.client.UniFiClient.authenticate", AsyncMock())
        assert await jobs.check_health("hq", settings, snapshots, failures={}, down_after=3) == "ok"

    async def test_failures_degrade_then_go_down(
        self,
        settings: Settings,
        pool: ClientPool,
        snapshots: AsyncMock,
        controller: MockController,
    ) -> None:
        controller.fail = True
        failures: dict[str, int] = {}

        outcomes = [
            await jobs.check_health("hq", settings, snapshots, failures=failures, down_after=2)
            for _ in range(3)
        ]

        assert outcomes == ["degraded", "down", "down"]
        detail = snapshots.record_health.await_args.kwargs["detail"]
        assert detail.startswith(("AuthenticationError", "CircuitOpenError"))
        assert "key" not in detail

    async def test_cloud_controller_has_no_version_probe(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch, snapshots: AsyncMock
    ) -> None:
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()
        authenticate = AsyncMock()
        get = AsyncMock()
        monkeypatch.setattr("src.api.client.UniFiClient.authenticate", authenticate)
        monkeypatch.setattr("src.api.client.UniFiClient.get", get)

        assert await jobs.check_health("c", settings, snapshots, failures={}, down_after=3) == "ok"
        get.assert_not_awaited()
        assert snapshots.record_health.await_args.kwargs["capabilities"] == {"api_type": "cloud-ea"}


class TestSyncController:
    async def test_sites_and_devices(
        self, settings: Settings, pool: ClientPool, snapshots: AsyncMock
    ) -> None:
        result = await jobs.sync_controller("hq", settings, snapshots)

        assert result == jobs.SyncResult(sites=2, devices=6)
        name, sites = snapshots.replace_sites.await_args.args
        assert name == "hq"
        assert [(s.site_uuid, s.short_name, s.display_name) for s in sites] == [
            ("11111111-aaaa", "default", "Default"),
            ("22222222-bbbb", "lab", "Lab"),
        ]
        _, site, devices = snapshots.replace_inventory.await_args_list[0].args
        assert site == "11111111-aaaa"
        first = devices[0]
        assert (first.device_id, first.mac, first.model, first.version, first.state) == (
            "11111111-aaaa-dev-0000",
            "aa:bb:cc:00:00:00",
            "U7PRO",
            "8.0.1",
            "ONLINE",
        )
        assert first.payload["name"] == "AP 0"

    async def test_pages_through_large_sites(
        self,
        settings: Settings,
        pool: ClientPool,
        snapshots: AsyncMock,
        controller: MockController,
    ) -> None:
        controller.devices = jobs.PAGE_SIZE * 2 + 5

        result = await jobs.sync_controller("hq", settings, snapshots)

        assert result.devices == 2 * controller.devices
        ids = [d.device_id for d in snapshots.replace_inventory.await_args_list[0].args[2]]
        assert len(ids) == len(set(ids)) == controller.devices

    async def test_controller_failure_leaves_snapshots_alone(
        self,
        settings: Settings,
        pool: ClientPool,
        snapshots: AsyncMock,
        controller: MockController,
    ) -> None:
        controller.fail = True
        with pytest.raises(Exception):  # noqa: B017 - whatever the client raises
            await jobs.sync_controller("hq", settings, snapshots)
        snapshots.replace_sites.assert_not_awaited()
        snapshots.replace_inventory.assert_not_awaited()

    @pytest.mark.parametrize("body", [{}, {"error": "busy"}])
    async def test_a_malformed_listing_keeps_the_snapshot(
        self,
        settings: Settings,
        snapshots: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
        body: Any,
    ) -> None:
        # UniFiClient.get() returns {} for an empty 2xx body: that must not
        # read as "the controller has no sites" and wipe the snapshot.
        monkeypatch.setattr("src.api.client.UniFiClient.authenticate", AsyncMock())
        monkeypatch.setattr("src.api.client.UniFiClient.get", AsyncMock(return_value=body))

        with pytest.raises(ValueError, match="unexpected listing shape"):
            await jobs.sync_controller("hq", settings, snapshots)
        snapshots.replace_sites.assert_not_awaited()
        snapshots.replace_inventory.assert_not_awaited()

    @pytest.mark.parametrize(
        ("api_type", "endpoint"), [("cloud-ea", "/ea/sites"), ("cloud-v1", "/v1/sites")]
    )
    async def test_cloud_controllers_sync_sites_only(
        self,
        settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
        snapshots: AsyncMock,
        api_type: str,
        endpoint: str,
    ) -> None:
        monkeypatch.setenv("UNIFI_API_TYPE", api_type)
        settings = Settings()
        monkeypatch.setattr("src.api.client.UniFiClient.authenticate", AsyncMock())
        get = AsyncMock(
            return_value={
                "data": [
                    {"siteId": "s-1", "meta": {"name": "default", "desc": "Default"}},
                    {"meta": {"name": "no id"}},
                    "junk",
                ]
            }
        )
        monkeypatch.setattr("src.api.client.UniFiClient.get", get)

        result = await jobs.sync_controller("c", settings, snapshots)

        assert result == jobs.SyncResult(sites=1, devices=0)
        get.assert_awaited_once_with(endpoint)
        sites = snapshots.replace_sites.await_args.args[1]
        assert [(s.site_uuid, s.short_name, s.display_name) for s in sites] == [
            ("s-1", "default", "Default")
        ]
        snapshots.replace_inventory.assert_not_awaited()


def test_device_record_skips_entries_without_an_id() -> None:
    assert jobs._device_record({"name": "x"}) is None
    assert jobs._device_record("junk") is None
    record = jobs._device_record({"_id": "d-1", "mac": "aa", "version": "1", "model": ""})
    assert record is not None
    assert (record.device_id, record.mac, record.version, record.model) == ("d-1", "aa", "1", None)


@pytest.mark.parametrize("response", ["junk", {"data": "junk"}, {}, None])
def test_entries_of_unexpected_shapes_raise(response: Any) -> None:
    with pytest.raises(ValueError, match="unexpected listing shape"):
        jobs._entries(response)


def test_empty_listings_are_empty() -> None:
    assert jobs._entries([]) == []
    assert jobs._entries({"data": []}) == []
