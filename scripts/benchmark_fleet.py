"""Benchmark the connection pool and read cache against a simulated fleet.

Usage::

    python scripts/benchmark_fleet.py --controllers 500 --repeats 5 --latency-ms 20

Every request goes to an in-process mock transport that sleeps ``latency-ms``
and counts what each simulated controller receives. The same workload (each
controller read ``repeats`` times through the real tool wrapper, with bounded
concurrency) runs three ways:

- ``baseline``: no pool, no cache (each call opens a client and re-authenticates)
- ``pool``: shared per-controller connections (auth probe and site map reused);
  sized to the fleet unless ``--max-open`` says otherwise
- ``pool+cache``: the pool plus the Redis read-through cache (fakeredis)

Needs the dev dependencies (fakeredis). Prints one line per mode.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest import mock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.client import UniFiClient  # noqa: E402
from src.api.pool import ClientPool  # noqa: E402
from src.config.config import APIType, Settings  # noqa: E402
from src.fleet.registry import ControllerProfile  # noqa: E402
from src.fleet.router import FleetRouter  # noqa: E402
from src.tool_registry import _make_tool_wrapper  # noqa: E402
from src.utils.exceptions import ResourceNotFoundError  # noqa: E402


class _Registry:
    def __init__(self, profiles: list[ControllerProfile]) -> None:
        self._profiles = {p.name: p for p in profiles}

    async def list_controllers(self) -> list[ControllerProfile]:
        return list(self._profiles.values())

    async def get_controller(self, name: str) -> ControllerProfile:
        try:
            return self._profiles[name]
        except KeyError:
            raise ResourceNotFoundError("controller", name) from None

    async def default_controller(self) -> str | None:
        return None


@dataclass
class Fleet:
    """Counts requests per path; answers like a UniFi gateway, after ``latency`` seconds."""

    latency: float
    requests: int = 0
    probes: int = 0

    async def handle(self, request: httpx.Request) -> httpx.Response:
        """Answer one request like a gateway would, after the simulated latency."""
        self.requests += 1
        await asyncio.sleep(self.latency)
        if request.url.path.endswith("/sites"):
            self.probes += 1
            return httpx.Response(
                200, json={"data": [{"id": "site-uuid", "internalReference": "default"}]}
            )
        return httpx.Response(200, json={"data": [{"mac": "aa:bb:cc:dd:ee:ff", "state": 1}]})


async def list_devices(site_id: str, settings: Any = None) -> dict[str, Any]:
    """A read tool written like the real ones: open a client, authenticate, read."""
    async with UniFiClient(settings) as client:
        await client.authenticate()
        return await client.get(f"/ea/sites/{site_id}/devices")


@dataclass
class Result:
    """One mode's request counts and per-call latencies."""

    mode: str
    calls: int
    requests: int
    probes: int
    latencies: list[float] = field(default_factory=list)

    @property
    def p50_ms(self) -> float:
        """Median call latency in milliseconds."""
        return statistics.median(self.latencies) * 1000

    @property
    def p95_ms(self) -> float:
        """95th-percentile call latency in milliseconds."""
        return statistics.quantiles(self.latencies, n=20)[18] * 1000

    def line(self) -> str:
        """One report line."""
        return (
            f"{self.mode:<11} calls={self.calls:<6} controller_requests={self.requests:<6} "
            f"auth_probes={self.probes:<6} p50={self.p50_ms:7.1f}ms p95={self.p95_ms:7.1f}ms"
        )


def _settings(redis_url: str | None) -> Settings:
    env = {
        "UNIFI_API_KEY": "bench-key",  # pragma: allowlist secret
        "UNIFI_API_TYPE": "local",
        "UNIFI_LOCAL_HOST": "10.255.0.1",
        "UNIFI_MAX_RETRIES": "0",
        "UNIFI_RATE_LIMIT_REQUESTS": "100000",
        "UNIFI_AUDIT_LOG_ENABLED": "false",
    }
    if redis_url:
        env["REDIS_URL"] = redis_url
    with mock.patch.dict(os.environ, env, clear=False):
        os.environ.pop("REDIS_URL", None) if not redis_url else None
        return Settings()


async def run_mode(
    mode: str,
    *,
    controllers: int,
    repeats: int,
    latency: float,
    concurrency: int,
    max_open: int | None = None,
    redis_url: str | None = None,
) -> Result:
    """Run the workload once in ``mode`` (baseline, pool, or pool+cache)."""
    fleet = Fleet(latency=latency)
    transport = httpx.MockTransport(fleet.handle)
    settings = _settings(redis_url if mode == "pool+cache" else None)
    profiles = [
        ControllerProfile(
            name=f"gw-{i:04d}",
            api_type=APIType.LOCAL,
            api_key=f"key-{i}",  # pragma: allowlist secret
            local_host=f"10.{i // 250}.{i % 250}.1",
        )
        for i in range(controllers)
    ]
    router = FleetRouter(settings, _Registry(profiles))

    pool = (
        ClientPool(transport=transport, max_open=max_open or controllers)
        if mode != "baseline"
        else None
    )
    read_cache = None
    if mode == "pool+cache":
        from src.cache import ReadCache

        read_cache = ReadCache.from_settings(settings)
        await read_cache._redis().flushdb()
    tool = _make_tool_wrapper(
        list_devices, settings, router, module="devices", pool=pool, read_cache=read_cache
    )

    real_client = httpx.AsyncClient

    def client_with_transport(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.setdefault("transport", transport)
        return real_client(*args, **kwargs)

    gate = asyncio.Semaphore(concurrency)
    result = Result(mode=mode, calls=controllers * repeats, requests=0, probes=0)

    async def one(name: str) -> None:
        async with gate:
            start = time.perf_counter()
            await tool("default", controller=name)
            result.latencies.append(time.perf_counter() - start)

    with mock.patch("src.api.client.httpx.AsyncClient", client_with_transport):
        for _ in range(repeats):
            await asyncio.gather(*(one(p.name) for p in profiles))
    if pool is not None:
        await pool.aclose()
    result.requests, result.probes = fleet.requests, fleet.probes
    return result


def start_redis() -> tuple[str, Any]:
    """Start a fakeredis TCP server; return its URL and the server."""
    import fakeredis

    server = fakeredis.TcpFakeServer(("127.0.0.1", 0))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"redis://127.0.0.1:{server.server_address[1]}/0", server


async def run_all(
    controllers: int, repeats: int, latency: float, concurrency: int, max_open: int | None = None
) -> dict[str, Result]:
    """Run every mode and return the results by mode."""
    redis_url, server = start_redis()
    try:
        return {
            mode: await run_mode(
                mode,
                controllers=controllers,
                repeats=repeats,
                latency=latency,
                concurrency=concurrency,
                max_open=max_open,
                redis_url=redis_url,
            )
            for mode in ("baseline", "pool", "pool+cache")
        }
    finally:
        server.shutdown()


def main(argv: list[str] | None = None) -> int:
    """Run the benchmark and print one line per mode."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--controllers", type=int, default=500)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--latency-ms", type=float, default=20.0)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument(
        "--max-open",
        type=int,
        default=None,
        help="Pool size (default: one connection per controller); below the fleet size, "
        "LRU eviction drops cached auth and connections",
    )
    args = parser.parse_args(argv)

    results = asyncio.run(
        run_all(
            args.controllers, args.repeats, args.latency_ms / 1000, args.concurrency, args.max_open
        )
    )
    for result in results.values():
        print(result.line())
    saved = 1 - results["pool+cache"].requests / results["baseline"].requests
    print(f"controller requests saved by pool+cache: {saved:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
