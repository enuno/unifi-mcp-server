"""Error paths, the ``@cached`` decorator and ``warm_cache`` in src/cache.py.

Redis is replaced with an ``AsyncMock`` patched in as ``src.cache.redis.Redis``.
Errors are raised as ``src.cache.RedisError`` so the tests hold whether the real
redis package or ``tests/unit/test_cache.py``'s stand-in was imported first.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.cache as cache_module
from src.config import Settings


@pytest.fixture
def settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.log_level = "INFO"
    settings.redis_host = "localhost"
    settings.redis_port = 6379
    settings.redis_db = 0
    settings.redis_password = None
    settings.redis_url = None
    return settings


@pytest.fixture(autouse=True)
def _redis_available():
    cache_module._pools.clear()
    with patch("src.cache.REDIS_AVAILABLE", True), patch("src.cache._shared_pool"):
        yield
    cache_module._pools.clear()


@pytest.fixture
def redis_instance() -> AsyncMock:
    instance = AsyncMock()
    with patch("src.cache.redis.Redis", return_value=instance):
        yield instance


async def _connected(settings: MagicMock) -> cache_module.CacheClient:
    client = cache_module.CacheClient(settings)
    assert await client.connect()
    return client


def _error() -> Exception:
    return cache_module.RedisError("redis down")


class TestCacheClientErrorPaths:
    @pytest.mark.asyncio
    async def test_connect_is_idempotent(self, settings, redis_instance) -> None:
        client = await _connected(settings)
        assert await client.connect()
        redis_instance.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_logs_redis_url_without_its_value(self, settings, redis_instance) -> None:
        settings.redis_url = "redis://:secret@host:6379/0"  # pragma: allowlist secret
        logger = MagicMock()
        client = cache_module.CacheClient(settings, logger=logger)

        assert await client.connect()

        message = logger.info.call_args.args[0]
        assert "REDIS_URL" in message
        assert "secret" not in message

    @pytest.mark.asyncio
    async def test_disconnect_error_still_resets(self, settings, redis_instance) -> None:
        redis_instance.aclose.side_effect = RuntimeError("boom")
        client = await _connected(settings)

        await client.disconnect()

        assert client._redis is None
        assert client._connected is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "redis_method", "args", "expected"),
        [
            ("get", "get", ("k",), None),
            ("set", "set", ("k", {"a": 1}), False),
            ("delete", "delete", ("k",), False),
            ("clear", "flushdb", (), False),
            ("exists", "exists", ("k",), False),
        ],
    )
    async def test_redis_errors_degrade(
        self, settings, redis_instance, method, redis_method, args, expected
    ) -> None:
        getattr(redis_instance, redis_method).side_effect = _error()
        client = await _connected(settings)

        assert await getattr(client, method)(*args) == expected

    @pytest.mark.asyncio
    async def test_get_bad_json_is_a_miss(self, settings, redis_instance) -> None:
        redis_instance.get.return_value = "{not json"
        client = await _connected(settings)

        assert await client.get("k") is None

    @pytest.mark.asyncio
    async def test_set_unserialisable_value(self, settings, redis_instance) -> None:
        client = await _connected(settings)

        assert await client.set("k", object()) is False
        redis_instance.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_with_ttl_uses_setex(self, settings, redis_instance) -> None:
        client = await _connected(settings)

        assert await client.set("k", [1], ttl=30) is True
        redis_instance.setex.assert_awaited_once_with("k", 30, "[1]")

    @pytest.mark.asyncio
    async def test_delete_pattern_error(self, settings, redis_instance) -> None:
        def scan_iter(match: str):
            raise _error()

        redis_instance.scan_iter = scan_iter
        client = await _connected(settings)

        assert await client.delete_pattern("sites:*") == 0

    @pytest.mark.asyncio
    async def test_delete_pattern_no_matches(self, settings, redis_instance) -> None:
        async def scan_iter(match: str):
            for key in ():
                yield key

        redis_instance.scan_iter = scan_iter
        client = await _connected(settings)

        assert await client.delete_pattern("sites:*") == 0
        redis_instance.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_exists_true(self, settings, redis_instance) -> None:
        redis_instance.exists.return_value = 1
        client = await _connected(settings)

        assert await client.exists("k") is True


class TestCachedDecorator:
    @pytest.mark.asyncio
    async def test_without_settings_calls_through(self, redis_instance) -> None:
        @cache_module.cached("sites")
        async def fn(x: int) -> int:
            return x * 2

        assert await fn(2) == 4
        redis_instance.ping.assert_not_called()

    @pytest.mark.asyncio
    async def test_hit_skips_function(self, settings, redis_instance) -> None:
        redis_instance.get.return_value = '{"cached": true}'
        inner = AsyncMock(return_value={"cached": False})

        @cache_module.cached("sites", ttl=60)
        async def get_sites(settings: Any, site_id: str) -> Any:
            return await inner()

        assert await get_sites(settings=settings, site_id="default") == {"cached": True}
        redis_instance.get.assert_awaited_once_with("sites:get_sites:default")
        inner.assert_not_called()
        redis_instance.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_miss_stores_with_configured_ttl(self, settings, redis_instance) -> None:
        redis_instance.get.return_value = None

        @cache_module.cached("devices")
        async def list_devices(settings: Any) -> list:
            return [1, 2]

        assert await list_devices(settings=settings) == [1, 2]
        redis_instance.setex.assert_awaited_once_with(
            "devices:list_devices", cache_module.CacheConfig.get_ttl("devices"), "[1, 2]"
        )

    @pytest.mark.asyncio
    async def test_custom_key_builder_and_positional_settings(self, redis_instance) -> None:
        real_settings = MagicMock(spec=Settings)
        real_settings.__class__ = Settings  # isinstance(arg, Settings) for the positional lookup
        real_settings.log_level = "INFO"
        real_settings.redis_url = None
        real_settings.redis_host = "localhost"
        real_settings.redis_port = 6379
        redis_instance.get.return_value = None

        @cache_module.cached("sites", ttl=5, key_builder=lambda s, n: f"custom:{n}")
        async def fn(s: Any, n: int) -> int:
            return n

        assert await fn(real_settings, 7) == 7
        redis_instance.get.assert_awaited_once_with("custom:7")
        redis_instance.setex.assert_awaited_once_with("custom:7", 5, "7")


class TestWarmCache:
    @staticmethod
    def _unifi(responses: dict[str, Any]) -> AsyncMock:
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        async def get(path: str) -> Any:
            value = responses[path]
            if isinstance(value, Exception):
                raise value
            return value

        client.get = AsyncMock(side_effect=get)
        return client

    @pytest.mark.asyncio
    async def test_skipped_without_redis(self, settings) -> None:
        with patch("src.cache.REDIS_AVAILABLE", False):
            assert await cache_module.warm_cache(settings) == {}

    @pytest.mark.asyncio
    async def test_warms_sites_and_devices(self, settings, redis_instance) -> None:
        unifi = self._unifi(
            {
                "/ea/sites": {"data": [{"id": "s1"}, {"id": "s2"}, {"name": "no id"}]},
                "/ea/sites/s1/devices": {"data": [{"id": "d1"}, {"id": "d2"}]},
                "/ea/sites/s2/devices": RuntimeError("controller error"),
            }
        )
        with patch("src.api.UniFiClient", return_value=unifi):
            result = await cache_module.warm_cache(settings)

        assert result == {"sites": 2, "devices": 2, "networks": 0}
        redis_instance.aclose.assert_awaited()

    @pytest.mark.asyncio
    async def test_controller_failure_is_contained(self, settings, redis_instance) -> None:
        unifi = self._unifi({})
        unifi.authenticate.side_effect = RuntimeError("auth failed")
        with patch("src.api.UniFiClient", return_value=unifi):
            result = await cache_module.warm_cache(settings)

        assert result == {"sites": 0, "devices": 0, "networks": 0}
        redis_instance.aclose.assert_awaited()


class TestReadCacheEdges:
    def test_from_settings_without_redis_package(self) -> None:
        settings = MagicMock()
        settings.cache_enabled = True
        settings.redis_url = "redis://cache:6379/0"
        with patch("src.cache.REDIS_AVAILABLE", False):
            assert cache_module.ReadCache.from_settings(settings) is None

    @pytest.mark.asyncio
    async def test_store_failure_still_returns_value(self, settings, redis_instance) -> None:
        redis_instance.setex.side_effect = _error()
        read_cache = cache_module.ReadCache(settings)

        assert await read_cache._load_and_store("k", 10, AsyncMock(return_value={"a": 1})) == {
            "a": 1
        }

    @pytest.mark.asyncio
    async def test_uncacheable_value_is_not_stored(self, settings, redis_instance) -> None:
        read_cache = cache_module.ReadCache(settings)

        value = object()
        assert await read_cache._load_and_store("k", 10, AsyncMock(return_value=value)) is value
        redis_instance.setex.assert_not_called()
