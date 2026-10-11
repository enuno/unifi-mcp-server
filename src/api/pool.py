"""Shared per-controller connections (docs/FLEET_SCALING_PLAN.md §3.4, Phase 3).

Tools build a ``UniFiClient`` (or ``ProtectClient``) per call. While a
:class:`ClientPool` is active for the call (the tool wrapper sets
:data:`active_pool`), those clients share one long-lived connection per
controller instead of opening their own, and with it:

- one ``httpx.AsyncClient`` (TLS sessions and keep-alive reused),
- one rate limiter, so ``UNIFI_RATE_LIMIT_REQUESTS`` applies across calls,
- the authentication probe and site map, reused for :data:`AUTH_TTL_SECONDS`,
- a circuit breaker that fails fast once a controller stops answering.

The pool keeps at most ``max_open`` connections, closing the least recently
used idle ones, and closes connections idle for longer than ``idle_seconds``.
A connection in use by a call is never closed. The per-controller state (auth,
rate limiter, breaker) is small and kept in a separate, much larger LRU
(``max_states``), so closing a connection does not forget the controller: a
fleet larger than ``max_open`` still reuses its authentication probes. Without
an active pool, clients behave exactly as before.
"""

import asyncio
import hashlib
import time
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import Settings
from ..utils.exceptions import NetworkError
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: How long an authentication probe and site map are reused.
AUTH_TTL_SECONDS = 300.0

#: Consecutive unreachable calls that open a controller's circuit.
FAILURE_THRESHOLD = 5

#: How long an open circuit fails fast before letting one call through.
COOLDOWN_SECONDS = 30.0

#: Default for UNIFI_FLEET_MAX_OPEN_CLIENTS.
MAX_OPEN_CONNECTIONS = 256

#: Idle connections older than this are closed.
IDLE_SECONDS = 300.0

#: Controllers whose state (auth, rate limiter, breaker) is remembered.
MAX_STATES = 10_000


class CircuitOpenError(NetworkError):
    """Raised instead of contacting a controller whose circuit is open."""


class CircuitBreaker:
    """Opens after repeated unreachable calls, then lets one call through per cooldown."""

    def __init__(
        self, threshold: int = FAILURE_THRESHOLD, cooldown: float = COOLDOWN_SECONDS
    ) -> None:
        """Create a closed breaker."""
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.opened_at: float | None = None
        #: Wall-clock time the circuit opened, to compare with workers' checks.
        self.opened_wall: float | None = None

    def check(self, label: str) -> None:
        """Raise :class:`CircuitOpenError` while the circuit is open and cooling down."""
        if self.opened_at is None:
            return
        remaining = self.cooldown - (time.monotonic() - self.opened_at)
        if remaining > 0:
            raise CircuitOpenError(
                f"Controller {label} is unreachable ({self.failures} failed calls in a row); "
                f"not contacting it for another {remaining:.0f}s"
            )

    def record_success(self) -> None:
        """Close the circuit."""
        self.failures = 0
        self.opened_at = None
        self.opened_wall = None

    def half_open(self, checked_at: float) -> bool:
        """Let calls through again after a health check that started after the circuit opened.

        One more unreachable call re-opens it. A check that started before
        the circuit opened says nothing about the outage, so it is ignored.

        Args:
            checked_at: When the health check started (``time.time()``)

        Returns:
            True if the circuit was open and is now half-open
        """
        if self.opened_at is None or self.opened_wall is None or checked_at <= self.opened_wall:
            return False
        self.opened_at = None
        self.opened_wall = None
        self.failures = self.threshold - 1
        return True

    def record_failure(self) -> None:
        """Count an unreachable call; open (or re-open) at the threshold."""
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()
            self.opened_wall = time.time()


@dataclass
class AuthState:
    """A controller's verified authentication and site lookups."""

    site_uuid_to_name: dict[str, str]
    site_name_to_uuid: dict[str, str]
    site_id_cache: dict[str, str]
    at: float = field(default_factory=time.monotonic)


@dataclass
class ControllerState:
    """What the pool remembers about a controller, with or without an open connection."""

    breaker: CircuitBreaker
    rate_limiter: Any = None
    auth: AuthState | None = None


class Connection:
    """One controller's shared HTTP client, plus its remembered state."""

    def __init__(
        self, key: str, label: str, client: httpx.AsyncClient, state: ControllerState
    ) -> None:
        """Wrap an open client and the controller's state."""
        self.key = key
        self.label = label
        self.client = client
        self.state = state
        self.active = 0
        self.last_used = time.monotonic()

    @property
    def breaker(self) -> CircuitBreaker:
        """The controller's circuit breaker."""
        return self.state.breaker

    @property
    def rate_limiter(self) -> Any:
        """The controller's rate limiter (created by the first client)."""
        return self.state.rate_limiter

    @rate_limiter.setter
    def rate_limiter(self, value: Any) -> None:
        self.state.rate_limiter = value

    @property
    def auth(self) -> AuthState | None:
        """The controller's last verified authentication."""
        return self.state.auth

    @auth.setter
    def auth(self, value: AuthState | None) -> None:
        self.state.auth = value


def connection_key(settings: Settings) -> str:
    """Identify a controller connection by everything that shapes it."""
    api_key_hash = hashlib.sha256(settings.api_key.encode("utf-8")).hexdigest()
    parts = (
        settings.api_type.value,
        settings.base_url,
        api_key_hash,
        str(settings.verify_ssl),
        str(settings.request_timeout),
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class ClientPool:
    """Long-lived connections, one per controller, bounded and evicted when idle."""

    def __init__(
        self,
        *,
        max_open: int = MAX_OPEN_CONNECTIONS,
        idle_seconds: float = IDLE_SECONDS,
        auth_ttl: float = AUTH_TTL_SECONDS,
        failure_threshold: int = FAILURE_THRESHOLD,
        cooldown: float = COOLDOWN_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
        max_states: int = MAX_STATES,
    ) -> None:
        """Create an empty pool.

        Args:
            max_open: Most connections kept open
            idle_seconds: Close connections idle this long
            auth_ttl: Reuse an authentication probe this long
            failure_threshold: Unreachable calls that open a circuit
            cooldown: How long an open circuit fails fast
            transport: httpx transport for every connection (tests, benchmarks)
            max_states: Controllers whose state is remembered
        """
        self.max_open = max_open
        self.idle_seconds = idle_seconds
        self.auth_ttl = auth_ttl
        self._failure_threshold = failure_threshold
        self._cooldown = cooldown
        self._transport = transport
        self._connections: OrderedDict[str, Connection] = OrderedDict()
        self._states: OrderedDict[str, ControllerState] = OrderedDict()
        self.max_states = max_states
        self._closing: set[asyncio.Task[None]] = set()

    def __len__(self) -> int:
        """Open connections."""
        return len(self._connections)

    def health_ok(self, key: str, checked_at: float) -> bool:
        """A worker's health check reached the controller: half-open its circuit here.

        Called for ``HealthBus`` announcements (src/fleet/bus.py). Controllers
        this server has never called, or whose circuit is closed, are left alone.

        Returns:
            True if an open circuit was half-opened
        """
        state = self._states.get(key)
        if state is None or not state.breaker.half_open(checked_at):
            return False
        logger.info("A worker reached a controller whose circuit was open here; retrying it now")
        return True

    def acquire(self, settings: Settings) -> Connection:
        """Return the controller's connection, opening it if needed; pair with :meth:`release`."""
        key = connection_key(settings)
        connection = self._connections.get(key)
        if connection is None:
            connection = Connection(
                key=key,
                label=settings.base_url,
                client=httpx.AsyncClient(
                    headers=settings.get_headers(),
                    timeout=settings.request_timeout,
                    verify=settings.verify_ssl,
                    follow_redirects=False,
                    transport=self._transport,
                ),
                state=self._state(key),
            )
            self._connections[key] = connection
        else:
            self._connections.move_to_end(key)
        connection.active += 1
        connection.last_used = time.monotonic()
        self._prune()
        return connection

    def _state(self, key: str) -> ControllerState:
        state = self._states.get(key)
        if state is None:
            state = ControllerState(CircuitBreaker(self._failure_threshold, self._cooldown))
            self._states[key] = state
            while len(self._states) > self.max_states:
                self._states.popitem(last=False)
        else:
            self._states.move_to_end(key)
        return state

    def release(self, connection: Connection) -> None:
        """Mark a call's use of ``connection`` finished."""
        connection.active = max(0, connection.active - 1)
        connection.last_used = time.monotonic()

    def fresh_auth(self, connection: Connection) -> AuthState | None:
        """Return the connection's authentication state if still within the TTL."""
        auth = connection.auth
        if auth is not None and time.monotonic() - auth.at < self.auth_ttl:
            return auth
        return None

    def _prune(self) -> None:
        """Close idle connections past the idle limit, then LRU idle ones over the cap."""
        now = time.monotonic()
        for key, connection in list(self._connections.items()):
            over_cap = len(self._connections) > self.max_open
            idle_too_long = now - connection.last_used > self.idle_seconds
            if connection.active == 0 and (over_cap or idle_too_long):
                self._close(self._connections.pop(key))

    def _close(self, connection: Connection) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover - acquire runs inside tool calls
            return
        task = loop.create_task(connection.client.aclose())
        self._closing.add(task)
        task.add_done_callback(self._closing.discard)

    async def aclose(self) -> None:
        """Close every connection (server shutdown)."""
        connections = list(self._connections.values())
        self._connections.clear()
        await asyncio.gather(*(c.client.aclose() for c in connections), return_exceptions=True)
        if self._closing:
            await asyncio.gather(*self._closing, return_exceptions=True)


#: Pool used by clients built during the current tool call; None outside calls.
active_pool: ContextVar[ClientPool | None] = ContextVar("unifi_active_pool", default=None)
