"""Controller registry backed by Postgres (docs/FLEET_SCALING_PLAN.md §3.2).

Lookups never query the database: they read an in-memory snapshot that is
reloaded every ``UNIFI_FLEET_REGISTRY_REFRESH_SECONDS`` and right after a
registry change made through this server; with Redis configured, the other
replicas are told to reload at once (``registry:changed``, src/fleet/bus.py). If the database becomes
unreachable, the last snapshot keeps serving and a warning is logged; writes
fail with the database error.
"""

import asyncio
import contextlib

from ..config import Settings
from ..utils.audit import get_audit_logger
from ..utils.exceptions import ConfigurationError, ResourceNotFoundError
from ..utils.logger import get_logger
from .bus import RegistryBus
from .credentials import CredentialCipher
from .db.schema import ensure_current, make_engine
from .db.store import FleetStore
from .registry import ControllerProfile

logger = get_logger(__name__)


class PostgresRegistry:
    """Registry reading controllers from Postgres through a snapshot."""

    def __init__(self, store: FleetStore, settings: Settings) -> None:
        """Create the registry; call :meth:`start` before use.

        Args:
            store: Access to the registry tables
            settings: Process-wide settings (seed source, refresh interval)
        """
        self.store = store
        self._settings = settings
        self._profiles: dict[str, ControllerProfile] | None = None
        self._default: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._bus: RegistryBus | None = None
        self._listener: asyncio.Task[None] | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "PostgresRegistry":
        """Build the registry for DATABASE_URL.

        Raises:
            ConfigurationError: If UNIFI_FLEET_CREDENTIAL_KEY is missing or
                invalid, or DATABASE_URL is not a postgres URL
        """
        if not settings.database_url:
            raise ConfigurationError("DATABASE_URL is not set")
        cipher = CredentialCipher.from_env()
        registry = cls(FleetStore(make_engine(settings.database_url), cipher), settings)
        registry._bus = RegistryBus.from_settings(settings)
        return registry

    async def start(self) -> None:
        """Check the schema, seed an empty registry, load it, and start refreshing.

        Raises:
            FleetSchemaError: If the schema is not at this code's revision
        """
        await ensure_current(self.store.engine)
        if await self.store.seed_from_settings(self._settings):
            logger.info("Fleet registry was empty: registered the UNIFI_* controller as 'default'")
            if self._settings.audit_log_enabled:
                await get_audit_logger(self._settings.audit_log_file).alog_event(
                    "admin", "registry_seeded", "success", controller="default"
                )
        await self.refresh(strict=True)
        self._task = asyncio.create_task(self._refresh_loop())
        if self._bus is not None:
            self._listener = asyncio.create_task(self._bus.listen(self.refresh))

    async def stop(self) -> None:
        """Stop refreshing and close database connections."""
        for task in (self._task, self._listener):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._task = self._listener = None
        await self.store.engine.dispose()

    async def refresh(self, *, strict: bool = False) -> bool:
        """Reload the snapshot from the database.

        Args:
            strict: Raise on failure instead of keeping the last snapshot

        Returns:
            True if the snapshot was reloaded
        """
        try:
            profiles, default = await self.store.load()
        except Exception as e:
            if strict:
                raise
            logger.warning("Fleet registry refresh failed; serving the last snapshot: %s", e)
            return False
        self._profiles = {profile.name: profile for profile in profiles}
        self._default = default
        return True

    async def changed(self) -> None:
        """Reload after a change made through this replica, and tell the others.

        Other replicas reload at once when Redis is configured, and otherwise
        at their next periodic refresh.
        """
        await self.refresh()
        if self._bus is not None:
            await self._bus.publish()

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self._settings.fleet_registry_refresh_seconds)
            await self.refresh()

    def _snapshot(self) -> dict[str, ControllerProfile]:
        if self._profiles is None:
            raise ConfigurationError("The fleet registry has not been loaded yet")
        return self._profiles

    async def list_controllers(self) -> list[ControllerProfile]:
        """Return every enabled controller."""
        return list(self._snapshot().values())

    async def get_controller(self, name: str) -> ControllerProfile:
        """Return the named controller.

        Raises:
            ResourceNotFoundError: If it is unknown or disabled
        """
        try:
            return self._snapshot()[name]
        except KeyError:
            raise ResourceNotFoundError("controller", name) from None

    async def default_controller(self) -> str | None:
        """Return the default controller's name, if one is set."""
        self._snapshot()
        return self._default
