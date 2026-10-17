"""The Redis read-through cache in the tool wrapper (plan §3.3, Phase 3), on a Redis protocol server."""

import asyncio
import threading
from collections.abc import Iterator
from typing import Any

import pytest

fakeredis = pytest.importorskip("fakeredis")

from fastmcp.server.auth import AccessToken  # noqa: E402

from src.access import PermissionDeniedError  # noqa: E402
from src.cache import CacheConfig, ReadCache  # noqa: E402
from src.config.config import APIType, Settings  # noqa: E402
from src.fleet import ControllerProfile  # noqa: E402
from src.fleet.router import FleetRouter  # noqa: E402
from src.tool_registry import _make_tool_wrapper  # noqa: E402
from src.utils import tool_kind  # noqa: E402
from src.utils.metrics import MetricsRegistry  # noqa: E402

from .test_router import StaticRegistry  # noqa: E402


@pytest.fixture(scope="module")
def redis_port() -> Iterator[int]:
    server = fakeredis.TcpFakeServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, redis_port: int) -> Settings:
    for name in ("REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", "base-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("REDIS_URL", f"redis://127.0.0.1:{redis_port}/0")
    monkeypatch.setattr("src.utils.audit._audit_logger", None)
    return Settings()


@pytest.fixture
async def cache(settings: Settings) -> ReadCache:
    cache = ReadCache.from_settings(settings)
    assert cache is not None
    await cache._redis().flushdb()
    return cache


@pytest.fixture
def metrics(monkeypatch: pytest.MonkeyPatch) -> MetricsRegistry:
    registry = MetricsRegistry()
    monkeypatch.setattr("src.cache.METRICS", registry)
    return registry


def _profile(name: str, host: str, **labels: str) -> ControllerProfile:
    return ControllerProfile(
        name=name,
        api_type=APIType.LOCAL,
        api_key=f"{name}-key",  # pragma: allowlist secret
        local_host=host,
        labels=labels,
    )


@pytest.fixture
def router(settings: Settings) -> FleetRouter:
    registry = StaticRegistry(
        _profile("hq", "10.0.0.1", group="retail"), _profile("branch", "10.0.1.1"), default="hq"
    )
    return FleetRouter(settings, registry)


class Controller:
    """Counts the reads and writes that reach a controller."""

    def __init__(self) -> None:
        self.reads = 0
        self.version = 1

    @tool_kind.read_tool
    async def list_devices(self, site_id: str, settings: Any = None) -> dict:
        self.reads += 1
        return {"host": settings.local_host, "site": site_id, "version": self.version}

    @tool_kind.write_tool
    async def update_device(
        self, site_id: str, confirm: bool = False, dry_run: bool = False, settings: Any = None
    ) -> dict:
        if not dry_run:
            self.version += 1
        return {"ok": True}


def _tools(
    controller: Controller, settings: Settings, router: FleetRouter, cache: ReadCache
) -> Any:
    read = _make_tool_wrapper(
        controller.list_devices, settings, router, module="devices", read_cache=cache
    )
    write = _make_tool_wrapper(
        controller.update_device, settings, router, module="devices", read_cache=cache
    )
    return read, write


class TestActivation:
    def test_only_with_explicit_redis_configuration(self, monkeypatch):
        for name in ("REDIS_URL", "REDIS_HOST"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("UNIFI_API_KEY", "k")  # pragma: allowlist secret

        assert ReadCache.from_settings(Settings()) is None
        monkeypatch.setenv("REDIS_HOST", "localhost")
        assert ReadCache.from_settings(Settings()) is not None
        monkeypatch.setenv("UNIFI_CACHE_ENABLED", "false")
        assert ReadCache.from_settings(Settings()) is None


class TestReadThrough:
    async def test_repeated_reads_reach_the_controller_once(self, settings, router, cache, metrics):
        controller = Controller()
        read, _ = _tools(controller, settings, router, cache)

        results = [await read("default", controller="hq") for _ in range(5)]

        assert controller.reads == 1
        assert all(r == results[0] for r in results)
        body = metrics.render(version="0", api_type="local")
        assert 'unifi_mcp_cache_requests_total{result="hit"} 4' in body
        assert 'unifi_mcp_cache_requests_total{result="miss"} 1' in body

    async def test_fresh_bypasses_and_refreshes(self, settings, router, cache):
        controller = Controller()
        read, _ = _tools(controller, settings, router, cache)
        await read("default", controller="hq")
        controller.version = 99  # changed outside the server

        assert (await read("default", controller="hq"))["version"] == 1
        assert (await read("default", controller="hq", fresh=True))["version"] == 99
        assert (await read("default", controller="hq"))["version"] == 99
        assert controller.reads == 2

    async def test_keys_separate_arguments_and_controllers(self, settings, router, cache):
        controller = Controller()
        read, _ = _tools(controller, settings, router, cache)

        await read("default", controller="hq")
        await read("other", controller="hq")
        branch = await read("default", controller="branch")

        assert controller.reads == 3
        assert branch["host"] == "10.0.1.1"

    async def test_a_write_invalidates_that_controller_only(self, settings, router, cache):
        controller = Controller()
        read, write = _tools(controller, settings, router, cache)
        await read("default", controller="hq")
        await read("default", controller="branch")

        await write("default", confirm=True, controller="hq")

        assert (await read("default", controller="hq"))["version"] == 2  # not stale
        await read("default", controller="branch")
        assert controller.reads == 3  # branch still served from cache

    async def test_dry_run_writes_do_not_invalidate(self, settings, router, cache):
        controller = Controller()
        read, write = _tools(controller, settings, router, cache)
        await read("default", controller="hq")

        await write("default", dry_run=True, controller="hq")
        await read("default", controller="hq")

        assert controller.reads == 1

    async def test_entries_expire(self, settings, router, cache, monkeypatch):
        monkeypatch.setattr(CacheConfig, "DEVICES", 1)
        controller = Controller()
        read, _ = _tools(controller, settings, router, cache)
        await read("default", controller="hq")
        await asyncio.sleep(1.2)
        await read("default", controller="hq")

        assert controller.reads == 2

    async def test_concurrent_misses_share_one_controller_call(self, settings, router, cache):
        calls = 0

        @tool_kind.read_tool
        async def slow_devices(site_id: str, settings: Any = None) -> dict:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.05)
            return {"devices": []}

        read = _make_tool_wrapper(
            slow_devices, settings, router, module="devices", read_cache=cache
        )
        results = await asyncio.gather(*(read("default", controller="hq") for _ in range(10)))

        assert calls == 1
        assert all(r == {"devices": []} for r in results)

    async def test_results_that_do_not_round_trip_are_not_cached(self, settings, router, cache):
        calls = 0

        @tool_kind.read_tool
        async def tuple_devices(site_id: str, settings: Any = None) -> dict:
            nonlocal calls
            calls += 1
            return {"devices": ("a", "b")}  # JSON would turn this into a list

        read = _make_tool_wrapper(
            tuple_devices, settings, router, module="devices", read_cache=cache
        )
        await read("default", controller="hq")
        await read("default", controller="hq")

        assert calls == 2

    async def test_invalidate_all_clears_every_controller(self, settings, router, cache):
        controller = Controller()
        read, _ = _tools(controller, settings, router, cache)
        await read("default", controller="hq")
        await read("default", controller="branch")
        await cache._redis().set("unrelated:key", "1")

        await cache.invalidate_all()

        await read("default", controller="hq")
        await read("default", controller="branch")
        assert controller.reads == 4  # both re-read from the controller
        assert await cache._redis().get("unrelated:key") == "1"  # other keys untouched

    async def test_redis_down_bypasses_the_cache(self, monkeypatch, router):
        monkeypatch.setenv("UNIFI_API_KEY", "k")  # pragma: allowlist secret
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
        settings = Settings()
        cache = ReadCache.from_settings(settings)
        controller = Controller()
        read, write = _tools(controller, settings, router, cache)

        assert (await read("default", controller="hq"))["host"] == "10.0.0.1"
        await write("default", confirm=True, controller="hq")
        await read("default", controller="hq")
        assert controller.reads == 2


class TestOnlyAfterAuthorization:
    async def test_cached_reads_still_check_the_label_scope(
        self, settings, router, cache, monkeypatch
    ):
        controller = Controller()
        read, _ = _tools(controller, settings, router, cache)
        await read("default", controller="branch")  # cached by a break-glass caller

        token = AccessToken(
            token="umcp_x",  # noqa: S106
            client_id="t",
            scopes=[],
            claims={
                "token_id": "1",
                "name": "t",
                "role": "admin",
                "controller_labels": {"group": "retail"},
            },
        )
        monkeypatch.setattr("src.access.get_access_token", lambda: token)
        with pytest.raises(PermissionDeniedError):
            await read("default", controller="branch")


class TestSchema:
    def test_only_cached_reads_gain_fresh(self, settings, router, cache):
        import inspect

        from src.tools import devices

        cached = _make_tool_wrapper(devices.search_devices, settings, router, read_cache=cache)
        statistics = _make_tool_wrapper(
            devices.get_device_statistics, settings, router, read_cache=cache
        )
        uncached = _make_tool_wrapper(devices.search_devices, settings, router)

        assert "fresh" in inspect.signature(cached).parameters
        assert "fresh" not in inspect.signature(statistics).parameters
        assert "fresh" not in inspect.signature(uncached).parameters
