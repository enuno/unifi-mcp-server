"""Shared per-controller connections (src/api/pool.py)."""

import asyncio
from typing import Any

import httpx
import pytest

from src.api.client import UniFiClient
from src.api.pool import CircuitOpenError, ClientPool, active_pool
from src.config.config import Settings
from src.utils.exceptions import APIError, NetworkError


def _settings(monkeypatch: pytest.MonkeyPatch, host: str = "10.0.0.1", **env: str) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", host)
    monkeypatch.setenv("UNIFI_MAX_RETRIES", "0")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Settings()


class Controllers:
    """A fake fleet: counts requests per host and path."""

    def __init__(self, fail_hosts: set[str] | None = None, status: int = 200) -> None:
        self.requests: list[tuple[str, str]] = []
        self.fail_hosts = fail_hosts or set()
        self.status = status

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.url.host, request.url.path))
        if request.url.host in self.fail_hosts:
            raise httpx.ConnectError("unreachable", request=request)
        if request.url.path.endswith("/sites"):
            return httpx.Response(
                200, json={"data": [{"id": "uuid-1", "internalReference": "default"}]}
            )
        return httpx.Response(self.status, json={"data": []})

    def probes(self) -> int:
        """Authentication probes (GET /ea/sites, translated)."""
        return sum(1 for _, path in self.requests if path.endswith("/sites"))

    def calls(self) -> int:
        """Everything that is not an authentication probe."""
        return len(self.requests) - self.probes()


@pytest.fixture
def fleet() -> Controllers:
    return Controllers()


@pytest.fixture
def pool(fleet: Controllers) -> ClientPool:
    return ClientPool(transport=httpx.MockTransport(fleet.handler))


async def _call(
    pool: ClientPool, settings: Settings, endpoint: str = "/ea/sites/default/devices"
) -> Any:
    token = active_pool.set(pool)
    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()
            return await client.get(endpoint)
    finally:
        active_pool.reset(token)


class TestSharing:
    async def test_calls_to_one_controller_share_a_connection(self, pool, monkeypatch):
        settings = _settings(monkeypatch)
        token = active_pool.set(pool)
        try:
            first, second = UniFiClient(settings), UniFiClient(settings)
        finally:
            active_pool.reset(token)

        assert first.client is second.client
        assert first.rate_limiter is second.rate_limiter
        assert len(pool) == 1

    async def test_different_controllers_get_different_connections(self, pool, monkeypatch):
        await _call(pool, _settings(monkeypatch, "10.0.0.1"))
        await _call(pool, _settings(monkeypatch, "10.0.0.2"))

        assert len(pool) == 2

    async def test_closing_a_client_keeps_the_connection_open(self, pool, monkeypatch, fleet):
        settings = _settings(monkeypatch)
        await _call(pool, settings)
        await _call(pool, settings)

        assert len(pool) == 1
        await pool.aclose()
        assert len(pool) == 0

    async def test_without_a_pool_nothing_is_shared(self, monkeypatch):
        settings = _settings(monkeypatch)
        first, second = UniFiClient(settings), UniFiClient(settings)

        assert first.client is not second.client
        await first.close()
        await second.close()


class TestAuthCache:
    async def test_probe_runs_once_per_ttl(self, pool, fleet, monkeypatch):
        settings = _settings(monkeypatch)
        for _ in range(5):
            await _call(pool, settings)

        assert fleet.probes() == 1
        assert fleet.calls() == 5

    async def test_probe_repeats_after_the_ttl(self, fleet, monkeypatch):
        pool = ClientPool(transport=httpx.MockTransport(fleet.handler), auth_ttl=0.05)
        settings = _settings(monkeypatch)
        await _call(pool, settings)
        await asyncio.sleep(0.06)
        await _call(pool, settings)

        assert fleet.probes() == 2

    async def test_site_map_is_reused(self, pool, monkeypatch):
        settings = _settings(monkeypatch)
        await _call(pool, settings)
        token = active_pool.set(pool)
        try:
            async with UniFiClient(settings) as client:
                await client.authenticate()
                assert client._site_name_to_uuid == {"default": "uuid-1"}
        finally:
            active_pool.reset(token)


class TestEviction:
    async def test_least_recently_used_idle_connection_is_closed(self, fleet, monkeypatch):
        pool = ClientPool(transport=httpx.MockTransport(fleet.handler), max_open=2)
        for host in ("10.0.0.1", "10.0.0.2", "10.0.0.3"):
            await _call(pool, _settings(monkeypatch, host))

        assert len(pool) == 2
        assert {c.label for c in pool._connections.values()} == {
            "https://10.0.0.2:443",
            "https://10.0.0.3:443",
        }

    async def test_connections_in_use_are_never_closed(self, pool, monkeypatch):
        pool.max_open = 1
        busy = pool.acquire(_settings(monkeypatch, "10.0.0.1"))
        pool.acquire(_settings(monkeypatch, "10.0.0.2"))

        assert busy.key in pool._connections

    async def test_idle_connections_are_closed(self, fleet, monkeypatch):
        pool = ClientPool(transport=httpx.MockTransport(fleet.handler), idle_seconds=0.01)
        await _call(pool, _settings(monkeypatch, "10.0.0.1"))
        await asyncio.sleep(0.02)
        await _call(pool, _settings(monkeypatch, "10.0.0.2"))

        assert len(pool) == 1


class TestCircuitBreaker:
    async def test_opens_fails_fast_then_recovers(self, monkeypatch):
        fleet = Controllers(fail_hosts={"10.0.0.9"})
        pool = ClientPool(
            transport=httpx.MockTransport(fleet.handler), failure_threshold=3, cooldown=0.1
        )
        settings = _settings(monkeypatch, "10.0.0.9")

        # authenticate() reports failures as AuthenticationError; the breaker
        # still sees the NetworkError underneath.
        for _ in range(3):
            with pytest.raises(Exception, match="unreachable"):
                await _call(pool, settings)
        sent = len(fleet.requests)
        with pytest.raises(Exception, match="not contacting it"):
            await _call(pool, settings)
        assert len(fleet.requests) == sent  # failed fast, nothing sent

        fleet.fail_hosts.clear()
        await asyncio.sleep(0.11)
        await _call(pool, settings)  # one trial call goes through and closes the circuit
        await _call(pool, settings)

    async def test_error_responses_do_not_trip_it(self, monkeypatch):
        fleet = Controllers(status=500)
        pool = ClientPool(transport=httpx.MockTransport(fleet.handler), failure_threshold=2)
        settings = _settings(monkeypatch)

        for _ in range(4):
            with pytest.raises(APIError):
                await _call(pool, settings)

    async def test_one_controller_down_does_not_affect_others(self, monkeypatch):
        fleet = Controllers(fail_hosts={"10.0.0.9"})
        pool = ClientPool(transport=httpx.MockTransport(fleet.handler), failure_threshold=1)
        with pytest.raises(Exception, match="unreachable"):
            await _call(pool, _settings(monkeypatch, "10.0.0.9"))

        assert await _call(pool, _settings(monkeypatch, "10.0.0.1")) is not None


async def test_open_circuit_raises_circuit_open_error_directly(monkeypatch):
    """Below authenticate(), the open circuit surfaces as CircuitOpenError (a NetworkError)."""
    fleet = Controllers(fail_hosts={"10.0.0.9"})
    pool = ClientPool(transport=httpx.MockTransport(fleet.handler), failure_threshold=1)
    settings = _settings(monkeypatch, "10.0.0.9")
    token = active_pool.set(pool)
    try:
        async with UniFiClient(settings) as client:
            with pytest.raises(NetworkError):
                await client.get("/ea/sites/default/devices")
            with pytest.raises(CircuitOpenError):
                await client.get("/ea/sites/default/devices")
    finally:
        active_pool.reset(token)


async def test_closing_a_connection_keeps_the_controllers_state(fleet, monkeypatch):
    """A fleet larger than max_open still reuses auth probes and keeps breakers."""
    pool = ClientPool(transport=httpx.MockTransport(fleet.handler), max_open=2)
    hosts = [f"10.0.0.{i}" for i in range(1, 6)]
    for _ in range(3):
        for host in hosts:
            await _call(pool, _settings(monkeypatch, host))

    assert len(pool) == 2  # connections are capped...
    assert fleet.probes() == len(hosts)  # ...but each controller was probed once


async def test_remembered_states_are_bounded(fleet, monkeypatch):
    pool = ClientPool(transport=httpx.MockTransport(fleet.handler), max_open=1, max_states=2)
    for i in range(1, 4):
        await _call(pool, _settings(monkeypatch, f"10.0.0.{i}"))

    assert len(pool._states) == 2


async def test_closing_a_pooled_client_twice_never_closes_the_shared_connection(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    pool = MagicMock()
    connection = MagicMock()
    connection.client.aclose = AsyncMock()
    pool.acquire.return_value = connection
    token = active_pool.set(pool)
    try:
        client = UniFiClient(_settings(monkeypatch))
    finally:
        active_pool.reset(token)

    await client.close()
    await client.close()

    pool.release.assert_called_once_with(connection)
    connection.client.aclose.assert_not_called()
