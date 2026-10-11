"""Verify Phase 4 of docs/FLEET_SCALING_PLAN.md with real processes: 3 replicas + 2 workers.

Usage::

    python scripts/verify_fleet_scale.py [--controllers 40]

Starts, on this machine and without Docker:

- Postgres (pgserver, a dev dependency) holding the registry and snapshots,
- Redis (a fakeredis TCP server),
- one HTTPS mock that answers as ``--controllers`` UniFi gateways, told apart
  by API key; one in 20 is unreachable (answers 503),
- three MCP server replicas (``python -m src``, Streamable HTTP) and two
  workers (``python -m src.worker``),

then checks, through MCP clients and the shared stores:

1. the workers split the controllers between them (leases in Redis),
2. every controller's health is recorded (ok, or degraded/down if unreachable),
3. a killed worker's controllers move to the other within the lease plus a tick,
   and their health checks continue,
4. a controller registered through one replica is routable on the others at
   once (registry pub/sub; the periodic refresh is set to 5 minutes),
5. three replicas calling one controller together never exceed its rate limit
   in any window,
6. ``fleet_fanout`` over the fleet returns partial results: ok for reachable
   controllers, an error for each unreachable one,
7. ``fleet_health`` and ``fleet_inventory`` answer from the worker's snapshots.

Prints PASS/FAIL per check and exits 1 if any failed. Takes about a minute
(the first inventory sync lands within ``UNIFI_FLEET_WORKER_SYNC_SECONDS``,
30 here).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TOKEN = "verify-fleet-scale-token"  # noqa: S105 - local test harness only
RATE_LIMIT = 5  # requests per second per controller
LEASE_SECONDS = 3
HEALTH_SECONDS = 5
SYNC_SECONDS = 30
DEVICES_PER_SITE = 2
JITTER_SECONDS = 0.05


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _key(n: int) -> str:
    return f"verify-key-{n:04d}"


def _unreachable(n: int) -> bool:
    return n % 20 == 7


# ---------------------------------------------------------------------------
# Mock controller fleet
# ---------------------------------------------------------------------------


class MockFleet:
    """Answers as many gateways on one HTTPS port, keyed by X-API-KEY."""

    def __init__(self, size: int) -> None:
        """Answer as ``size`` controllers (plus one spare key)."""
        self.size = size
        # One extra key for the controller check 4 registers.
        self.by_key = {_key(n): n for n in range(size + 1)}
        self.requests: dict[int, list[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def app(self) -> Any:
        """The ASGI app answering every controller's requests."""
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def handle(request: Request) -> JSONResponse:
            n = self.by_key.get(request.headers.get("x-api-key", ""))
            if n is None:
                return JSONResponse({"error": "unknown key"}, status_code=401)
            with self.lock:
                self.requests[n].append(time.time())
            if _unreachable(n):
                return JSONResponse({"error": "down"}, status_code=503)
            path = request.url.path
            if path == "/proxy/network/integration/v1/info":
                return JSONResponse({"applicationVersion": "9.4.19"})
            if path == "/proxy/network/integration/v1/sites":
                site = {"id": f"site-{n:04d}", "internalReference": "default", "name": f"S{n}"}
                return JSONResponse(
                    {"data": [site] if request.query_params.get("offset", "0") == "0" else []}
                )
            if path.endswith("/devices"):
                if request.query_params.get("offset", "0") != "0":
                    return JSONResponse({"data": []})
                devices = [
                    {
                        "id": f"dev-{n:04d}-{d}",
                        "macAddress": f"aa:bb:cc:{n // 256:02x}:{n % 256:02x}:{d:02x}",
                        "name": f"AP {n}.{d}",
                        "model": "U7PRO" if d else "UDM-Pro",
                        "firmwareVersion": "4.0.9" if d == 0 and n % 2 else "8.0.10",
                        "state": "ONLINE",
                    }
                    for d in range(DEVICES_PER_SITE)
                ]
                return JSONResponse({"data": devices})
            return JSONResponse({"error": path}, status_code=404)

        return Starlette(routes=[Route("/{path:path}", handle, methods=["GET"])])


def _self_signed(directory: Path) -> tuple[Path, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=1))
        .not_valid_after(now + dt.timedelta(hours=1))
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "mock.crt", directory / "mock.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


def start_mock(fleet: MockFleet, directory: Path) -> tuple[int, Any]:
    """Serve ``fleet`` over HTTPS on a free port; return the port and the server."""
    import uvicorn

    cert, key = _self_signed(directory)
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            fleet.app(),
            host="127.0.0.1",
            port=port,
            ssl_certfile=str(cert),
            ssl_keyfile=str(key),
            log_level="warning",
        )
    )
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            return port, server
        time.sleep(0.05)
    raise RuntimeError("mock controller did not start")


def start_redis() -> tuple[str, Any]:
    """Start a fakeredis TCP server; return its URL and the server."""
    import fakeredis

    server = fakeredis.TcpFakeServer(("127.0.0.1", 0))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"redis://127.0.0.1:{server.server_address[1]}/0", server


# ---------------------------------------------------------------------------
# Processes
# ---------------------------------------------------------------------------


class Stack:
    """The registry, the replicas and the workers, and how to reach them."""

    def __init__(self, size: int, directory: Path) -> None:
        """Prepare a stack of ``size`` controllers logging to ``directory``."""
        self.size = size
        self.directory = directory
        self.processes: dict[str, subprocess.Popen[bytes]] = {}
        self.server_ports: list[int] = []
        self.common: dict[str, str] = {}

    def env(self, **extra: str) -> dict[str, str]:
        """Environment for a child process: the shared settings plus ``extra``."""
        base = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("UNIFI_", "REDIS_", "DATABASE_", "MCP_"))
        }
        base.update(self.common)
        base.update(extra)
        return base

    def spawn(self, name: str, args: list[str], **env: str) -> None:
        """Start ``python args`` as ``name``, logging to ``<name>.log``."""
        log = (self.directory / f"{name}.log").open("wb")
        self.processes[name] = subprocess.Popen(  # noqa: S603 - fixed interpreter and argv
            [sys.executable, *args],
            cwd=ROOT,
            env=self.env(UNIFI_AUDIT_LOG_PATH=str(self.directory / f"{name}-audit.log"), **env),
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    def stop(self) -> None:
        """Stop every process (SIGTERM, then SIGKILL after 10 s)."""
        for process in self.processes.values():
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        for process in self.processes.values():
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def _client(port: int) -> Any:
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    return Client(
        StreamableHttpTransport(
            f"http://127.0.0.1:{port}/mcp", headers={"Authorization": f"Bearer {TOKEN}"}
        ),
        timeout=120,
    )


async def call(port: int, name: str, /, **arguments: Any) -> Any:
    """Call tool ``name`` on the replica at ``port``; return its structured result."""
    async with _client(port) as client:
        result = await client.call_tool(name, arguments)
    return result.structured_content


async def wait_for(
    what: str, check: Callable[[], Awaitable[bool]], timeout: float, every: float = 0.5
) -> float:
    """Poll ``check`` until it is true; return how long that took.

    Raises:
        TimeoutError: If it is still false after ``timeout`` seconds
    """
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        try:
            if await check():
                return time.monotonic() - started
        except Exception:  # noqa: S110 - not ready yet
            pass
        await asyncio.sleep(every)
    raise TimeoutError(f"{what} not reached within {timeout:g}s")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


class Report:
    """PASS/FAIL lines and the failure count."""

    def __init__(self) -> None:
        """Start with no failures."""
        self.failures = 0

    def check(self, name: str, ok: bool, detail: str) -> None:
        """Print one check's outcome."""
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)
        self.failures += 0 if ok else 1


async def lease_holders(redis_url: str) -> dict[str, str]:
    """Controller name -> worker id of every worker lease in Redis."""
    import redis.asyncio as aioredis

    from src.worker.shards import KEY_PREFIX

    client = aioredis.from_url(redis_url)
    try:
        holders = {}
        async for key in client.scan_iter(f"{KEY_PREFIX}:lease:*"):
            value = await client.get(key)
            if value is not None:
                holders[_text(key).rsplit(":", 1)[-1]] = _text(value)
        return holders
    finally:
        await client.aclose()


def _text(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value


def max_in_window(stamps: list[float], window: float) -> int:
    """Most of ``stamps`` inside any span shorter than ``window`` seconds."""
    stamps = sorted(stamps)
    best, start = 0, 0
    for end, stamp in enumerate(stamps):
        while stamp - stamps[start] >= window:
            start += 1
        best = max(best, end - start + 1)
    return best


async def run_checks(args: argparse.Namespace) -> int:
    """Bring the stack up, run every check, tear it down; return the exit code."""
    import pgserver
    from cryptography.fernet import Fernet

    report = Report()
    size = args.controllers
    unreachable = {f"c-{n:04d}" for n in range(size) if _unreachable(n)}
    with tempfile.TemporaryDirectory(prefix="verify-fleet-") as tmp:
        directory = Path(tmp)
        print(f"Logs in {directory}", flush=True)
        postgres = pgserver.get_server(str(directory / "pg"), cleanup_mode="delete")
        database_url = str(postgres.get_uri())
        redis_url, redis_server = start_redis()
        fleet = MockFleet(size)
        mock_port, mock_server = start_mock(fleet, directory)
        credential_key = Fernet.generate_key().decode()
        stack = Stack(size, directory)
        stack.common = {
            "DATABASE_URL": database_url,
            "REDIS_URL": redis_url,
            "UNIFI_FLEET_CREDENTIAL_KEY": credential_key,
            "UNIFI_API_KEY": _key(0),
            "UNIFI_API_TYPE": "local",
            "UNIFI_LOCAL_HOST": "127.0.0.1",
            "UNIFI_LOCAL_PORT": str(mock_port),
            "UNIFI_LOCAL_VERIFY_SSL": "false",
            "UNIFI_MAX_RETRIES": "0",
            "UNIFI_RATE_LIMIT_REQUESTS": str(RATE_LIMIT),
            "UNIFI_RATE_LIMIT_PERIOD": "1",
            "UNIFI_FLEET_REGISTRY_REFRESH_SECONDS": "300",
            "UNIFI_FLEET_WORKER_HEALTH_SECONDS": str(HEALTH_SECONDS),
            "UNIFI_FLEET_WORKER_SYNC_SECONDS": str(SYNC_SECONDS),
            "UNIFI_FLEET_WORKER_LEASE_SECONDS": str(LEASE_SECONDS),
            "UNIFI_FLEET_FANOUT_TIMEOUT_SECONDS": "10",
            "MCP_AUTH_TOKEN": TOKEN,
        }
        try:
            subprocess.run(  # noqa: S603 - fixed interpreter and argv
                [sys.executable, "-m", "src.fleet.cli", "migrate"],
                cwd=ROOT,
                env=stack.env(),
                check=True,
                capture_output=True,
            )
            await register_fleet(stack, size, mock_port)

            for index in range(3):
                port = _free_port()
                stack.server_ports.append(port)
                stack.spawn(
                    f"replica-{index}",
                    ["-m", "src"],
                    MCP_SERVER_TRANSPORT="streamable_http",
                    MCP_SERVER_HOST="127.0.0.1",
                    MCP_SERVER_PORT=str(port),
                )
            for index in range(2):
                stack.spawn(f"worker-{index}", ["-m", "src.worker"])
            for port in stack.server_ports:

                async def ready(p: int = port) -> bool:
                    return await _lists(p, size)

                await wait_for(f"replica on {port}", ready, timeout=60)

            await check_split(report, redis_url, size)
            await check_health(report, stack, size, unreachable)
            await check_failover(report, stack, redis_url, size)
            await check_pubsub(report, stack, mock_port)
            await check_rate_limit(report, stack, fleet)
            await check_fanout(report, stack, size, unreachable)
            await check_snapshots(report, stack, size, unreachable)
        finally:
            stack.stop()
            mock_server.should_exit = True
            redis_server.shutdown()
            postgres.cleanup()
            if report.failures and args.keep_logs:
                for log in sorted(directory.glob("*.log")):
                    print(f"--- {log.name} (last 20 lines)")
                    print("\n".join(log.read_text(errors="replace").splitlines()[-20:]))
    print(f"{'All checks passed' if not report.failures else f'{report.failures} check(s) failed'}")
    return 1 if report.failures else 0


async def _lists(port: int, size: int) -> bool:
    result = await call(port, "list_controllers")
    return len(result["controllers"]) == size


async def register_fleet(stack: Stack, size: int, port: int) -> None:
    """Register ``size`` controllers, all answered by the mock on ``port``."""
    os.environ["UNIFI_FLEET_CREDENTIAL_KEY"] = stack.common["UNIFI_FLEET_CREDENTIAL_KEY"]
    from src.config.config import APIType
    from src.fleet.credentials import CredentialCipher
    from src.fleet.db.schema import make_engine
    from src.fleet.db.store import FleetStore

    engine = make_engine(stack.common["DATABASE_URL"])
    store = FleetStore(engine, CredentialCipher.from_env())
    try:
        for n in range(size):
            await store.add_controller(
                name=f"c-{n:04d}",
                api_type=APIType.LOCAL,
                api_key=_key(n),
                local_host="127.0.0.1",
                local_port=port,
                local_verify_ssl=False,
                labels={"ring": str(n % 3)},
                make_default=n == 0,
            )
    finally:
        await engine.dispose()


async def _statuses(stack: Stack) -> list[Any]:
    from src.fleet.db.schema import make_engine
    from src.fleet.db.snapshots import SnapshotStore

    engine = make_engine(stack.common["DATABASE_URL"])
    try:
        return await SnapshotStore(engine).fleet_status()
    finally:
        await engine.dispose()


async def check_split(report: Report, redis_url: str, size: int) -> None:
    """Check 1: both workers hold leases, covering every controller."""

    async def split() -> bool:
        holders = await lease_holders(redis_url)
        return len(holders) == size and len(set(holders.values())) == 2

    try:
        await wait_for("both workers holding leases", split, timeout=30)
        counts: dict[str, int] = defaultdict(int)
        for holder in (await lease_holders(redis_url)).values():
            counts[holder] += 1
        report.check(
            "workers split the fleet", True, f"{size} controllers as {sorted(counts.values())}"
        )
    except TimeoutError as e:
        holders = await lease_holders(redis_url)
        report.check("workers split the fleet", False, f"{e}; {len(holders)} leases held")


async def check_health(report: Report, stack: Stack, size: int, unreachable: set[str]) -> None:
    """Check 2: every controller has a recorded health matching reachability."""

    async def recorded() -> bool:
        statuses = await _statuses(stack)
        return len(statuses) == size and all(s.health.health for s in statuses)

    try:
        await wait_for("every controller checked", recorded, timeout=HEALTH_SECONDS * 3 + 10)
    except TimeoutError as e:
        report.check("health recorded", False, str(e))
        return
    statuses = {s.name: s.health.health for s in await _statuses(stack)}
    wrong = [name for name, health in statuses.items() if (health == "ok") == (name in unreachable)]
    report.check(
        "health recorded",
        not wrong,
        f"{sum(h == 'ok' for h in statuses.values())} ok, "
        f"{len(unreachable)} unreachable marked degraded/down"
        + (f"; wrong: {wrong}" if wrong else ""),
    )


async def check_failover(report: Report, stack: Stack, redis_url: str, size: int) -> None:
    """Check 3: a killed worker's controllers move and keep being checked."""
    victim = stack.processes["worker-0"]
    # Worker ids are "<hostname>-<pid>-<random>" (src.worker.__main__.worker_id).
    victim_prefix = f"{socket.gethostname()}-{victim.pid}-"
    share = [c for c, h in (await lease_holders(redis_url)).items() if h.startswith(victim_prefix)]
    victim.kill()
    killed_at = time.monotonic()
    killed_wall = dt.datetime.now(dt.timezone.utc)

    async def taken_over() -> bool:
        current = await lease_holders(redis_url)
        return len(current) == size and not any(
            h.startswith(victim_prefix) for h in current.values()
        )

    try:
        took = await wait_for("one worker holding every lease", taken_over, timeout=30, every=0.2)
    except TimeoutError as e:
        report.check("dead worker's controllers move", False, str(e))
        return
    budget = LEASE_SECONDS + 5 + 2  # lease + one tick (≤5 s) + slack
    report.check(
        "dead worker's controllers move",
        took <= budget,
        f"its {len(share)} controllers held by the survivor {took:.1f}s after SIGKILL "
        f"(budget {budget}s)",
    )

    async def checked_again() -> bool:
        return all(
            s.health.checked_at is not None and s.health.checked_at > killed_wall
            for s in await _statuses(stack)
        )

    try:
        await wait_for("every controller re-checked after the kill", checked_again, timeout=40)
        report.check(
            "health checks continue",
            True,
            f"every controller re-checked {time.monotonic() - killed_at:.1f}s after the kill",
        )
    except TimeoutError as e:
        report.check("health checks continue", False, str(e))


async def check_pubsub(report: Report, stack: Stack, mock_port: int) -> None:
    """Check 4: a controller registered on one replica is listed by the others."""
    first, *others = stack.server_ports
    await call(
        first,
        "register_controller",
        name="c-new",
        api_type="local",
        local_host="127.0.0.1",
        local_port=mock_port,
        local_verify_ssl=False,
        api_key=_key(stack.size),
        confirm=True,
    )

    async def everywhere() -> bool:
        for port in others:
            names = {c["name"] for c in (await call(port, "list_controllers"))["controllers"]}
            if "c-new" not in names:
                return False
        return True

    try:
        took = await wait_for("c-new on every replica", everywhere, timeout=10, every=0.1)
        report.check(
            "registry change reaches every replica",
            True,
            f"listed by the other replicas {took:.2f}s after registering (periodic refresh 300s)",
        )
    except TimeoutError as e:
        report.check("registry change reaches every replica", False, str(e))


async def check_rate_limit(report: Report, stack: Stack, fleet: MockFleet) -> None:
    """Check 5: three replicas together stay within one controller's limit."""
    target, n = "c-0001", 1
    calls_per_replica = 6
    started = time.time()

    async def burst(port: int) -> None:
        for _ in range(calls_per_replica):
            await call(port, "get_application_info", controller=target)

    await asyncio.gather(*(burst(port) for port in stack.server_ports))
    with fleet.lock:
        stamps = [s for s in fleet.requests[n] if s >= started]
    # The limiter admits by Redis time; these stamps are arrival times at the
    # controller, which network jitter can pull a few milliseconds closer.
    peak = max_in_window(stamps, 1.0 - JITTER_SECONDS)
    report.check(
        "replicas share one rate limit",
        peak <= RATE_LIMIT and len(stamps) >= 3 * calls_per_replica,
        f"{len(stamps)} requests to {target} from 3 replicas (and its worker), "
        f"at most {peak} in any 1s window (limit {RATE_LIMIT}; arrival times, "
        f"{JITTER_SECONDS * 1000:.0f} ms allowed for jitter)",
    )


async def check_fanout(report: Report, stack: Stack, size: int, unreachable: set[str]) -> None:
    """Check 6: fleet_fanout reports each unreachable controller separately."""
    result = await call(stack.server_ports[2], "fleet_fanout", tool="get_application_info")
    results = result["results"]
    failed = {name for name, r in results.items() if not r["ok"]}
    expected_failed = unreachable | ({"c-new"} if _unreachable(size) else set())
    ok = failed == expected_failed and result["succeeded"] == len(results) - len(failed)
    report.check(
        "fan-out returns partial results",
        ok,
        f"{result['succeeded']} ok, {result['failed']} failed of {len(results)} "
        f"in {result['elapsed_seconds']}s" + ("" if ok else f"; failed {sorted(failed)}"),
    )


async def check_snapshots(report: Report, stack: Stack, size: int, unreachable: set[str]) -> None:
    """Check 7: fleet_health and fleet_inventory answer from the snapshots."""
    port = stack.server_ports[1]
    # Check 4 registered one more controller, which syncs too.
    reachable = size + 1 - len(unreachable) - (1 if _unreachable(size) else 0)

    async def synced() -> bool:
        inventory = await call(port, "fleet_inventory", limit=1000)
        return bool(inventory["total"] == reachable * DEVICES_PER_SITE)

    try:
        await wait_for("first inventory sync", synced, timeout=SYNC_SECONDS + 30, every=1)
    except TimeoutError as e:
        report.check("snapshot reads", False, str(e))
        return
    health = await call(port, "fleet_health")
    old = await call(port, "fleet_inventory", model="udm", firmware_below="4.1")
    expected_old = sum(1 for n in range(size) if n % 2 and not _unreachable(n))
    ok = health["counts"].get("ok", 0) >= reachable and old["total"] == expected_old
    report.check(
        "snapshot reads",
        ok,
        f"fleet_health counts {health['counts']}; fleet_inventory finds {old['total']} "
        f"UDMs below 4.1 (expected {expected_old})",
    )


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the checks."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--controllers", type=int, default=40)
    parser.add_argument(
        "--keep-logs", action="store_true", help="print the tail of every log on failure"
    )
    return asyncio.run(run_checks(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
