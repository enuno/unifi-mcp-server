"""Writes and reads of the worker's snapshots (docs/FLEET_SCALING_PLAN.md §3.5).

The worker (``python -m src.worker``) records each controller's health and
capabilities on ``controllers`` and keeps ``sites`` and ``device_inventory``
in step with what the controller reports. Every sync replaces the previous
snapshot for its scope: rows the controller no longer reports are removed.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ...utils.exceptions import ResourceNotFoundError
from .models import Controller, DeviceInventory, Site

Health = Literal["ok", "degraded", "down"]

#: Longest health detail stored; longer messages are cut.
_DETAIL_LENGTH = 255


@dataclass(frozen=True)
class SiteRecord:
    """One site as a controller reports it."""

    site_uuid: str
    short_name: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class DeviceRecord:
    """One device as a controller reports it."""

    device_id: str
    payload: Mapping[str, Any]
    mac: str | None = None
    name: str | None = None
    model: str | None = None
    version: str | None = None
    state: str | None = None


@dataclass(frozen=True)
class ControllerHealth:
    """A controller's last recorded health."""

    health: Health | None
    detail: str | None
    checked_at: datetime | None
    last_seen_at: datetime | None
    capabilities: dict[str, Any]


@dataclass(frozen=True)
class FleetStatus:
    """One enabled controller's recorded health, for fleet-wide reads."""

    name: str
    api_type: str
    labels: dict[str, str]
    health: ControllerHealth


@dataclass(frozen=True)
class FleetSite:
    """A site of a controller, for fleet-wide reads."""

    controller: str
    site: SiteRecord
    synced_at: datetime


@dataclass(frozen=True)
class FleetDevice:
    """A device of a controller's site, for fleet-wide reads."""

    controller: str
    site_uuid: str
    device: DeviceRecord
    synced_at: datetime


class SnapshotStore:
    """The worker's view of the fleet, stored in Postgres."""

    def __init__(self, engine: AsyncEngine) -> None:
        """Create a store on ``engine`` (the registry's DATABASE_URL)."""
        self.engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @staticmethod
    async def _controller_id(session: AsyncSession, name: str) -> UUID:
        controller_id = await session.scalar(select(Controller.id).where(Controller.name == name))
        if controller_id is None:
            raise ResourceNotFoundError("controller", name)
        return controller_id

    async def record_health(
        self,
        name: str,
        health: Health,
        *,
        detail: str | None = None,
        capabilities: Mapping[str, Any] | None = None,
    ) -> None:
        """Record a health check of the named controller.

        Args:
            name: The controller
            health: The outcome
            detail: Why, for anything but ``ok`` (cut to 255 characters)
            capabilities: Replace the stored capabilities (left as they were when None)

        Raises:
            ResourceNotFoundError: If the controller no longer exists
        """
        values: dict[str, Any] = {
            "health": health,
            "health_detail": detail[:_DETAIL_LENGTH] if detail else None,
            "health_checked_at": func.now(),
        }
        if health != "down":
            values["last_seen_at"] = func.now()
        if capabilities is not None:
            values["capabilities"] = dict(capabilities)
        async with self._sessions.begin() as session:
            result = await session.execute(
                update(Controller).where(Controller.name == name).values(**values)
            )
            if not getattr(result, "rowcount", 0):
                raise ResourceNotFoundError("controller", name)

    async def health(self, name: str) -> ControllerHealth:
        """Return the named controller's last recorded health.

        Raises:
            ResourceNotFoundError: If the controller does not exist
        """
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(
                        Controller.health,
                        Controller.health_detail,
                        Controller.health_checked_at,
                        Controller.last_seen_at,
                        Controller.capabilities,
                    ).where(Controller.name == name)
                )
            ).one_or_none()
        if row is None:
            raise ResourceNotFoundError("controller", name)
        return ControllerHealth(
            health=row.health,
            detail=row.health_detail,
            checked_at=row.health_checked_at,
            last_seen_at=row.last_seen_at,
            capabilities=dict(row.capabilities),
        )

    async def replace_sites(self, name: str, sites: Sequence[SiteRecord]) -> int:
        """Make ``sites`` the named controller's site snapshot.

        Sites it no longer reports are removed, with their devices.

        Returns:
            How many sites are stored

        Raises:
            ResourceNotFoundError: If the controller no longer exists
        """
        by_uuid = {site.site_uuid: site for site in sites}
        async with self._sessions.begin() as session:
            controller_id = await self._controller_id(session, name)
            stale = delete(Site).where(Site.controller_id == controller_id)
            if by_uuid:
                stale = stale.where(Site.site_uuid.not_in(list(by_uuid)))
            await session.execute(stale)
            if by_uuid:
                statement = insert(Site).values(
                    [
                        {
                            "controller_id": controller_id,
                            "site_uuid": site.site_uuid,
                            "short_name": site.short_name,
                            "display_name": site.display_name,
                        }
                        for site in by_uuid.values()
                    ]
                )
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[Site.controller_id, Site.site_uuid],
                        set_={
                            "short_name": statement.excluded.short_name,
                            "display_name": statement.excluded.display_name,
                            "synced_at": func.now(),
                        },
                    )
                )
        return len(by_uuid)

    async def list_sites(self, name: str) -> list[SiteRecord]:
        """Return the named controller's site snapshot, by site UUID.

        Raises:
            ResourceNotFoundError: If the controller does not exist
        """
        async with self._sessions() as session:
            controller_id = await self._controller_id(session, name)
            rows = (
                await session.execute(
                    select(Site.site_uuid, Site.short_name, Site.display_name)
                    .where(Site.controller_id == controller_id)
                    .order_by(Site.site_uuid)
                )
            ).all()
        return [SiteRecord(*row) for row in rows]

    async def replace_inventory(
        self, name: str, site_uuid: str, devices: Sequence[DeviceRecord]
    ) -> int:
        """Make ``devices`` the device snapshot of one site of the named controller.

        Returns:
            How many devices are stored for the site

        Raises:
            ResourceNotFoundError: If the controller or the site (in the site
                snapshot) no longer exists
        """
        by_id = {device.device_id: device for device in devices}
        async with self._sessions.begin() as session:
            controller_id = await self._controller_id(session, name)
            known = await session.scalar(
                select(func.count())
                .select_from(Site)
                .where(Site.controller_id == controller_id, Site.site_uuid == site_uuid)
            )
            if not known:
                raise ResourceNotFoundError("site", site_uuid)
            stale = delete(DeviceInventory).where(
                DeviceInventory.controller_id == controller_id,
                DeviceInventory.site_uuid == site_uuid,
            )
            if by_id:
                stale = stale.where(DeviceInventory.device_id.not_in(list(by_id)))
            await session.execute(stale)
            if by_id:
                statement = insert(DeviceInventory).values(
                    [
                        {
                            "controller_id": controller_id,
                            "site_uuid": site_uuid,
                            "device_id": device.device_id,
                            "mac": device.mac,
                            "name": device.name,
                            "model": device.model,
                            "version": device.version,
                            "state": device.state,
                            "payload": dict(device.payload),
                        }
                        for device in by_id.values()
                    ]
                )
                excluded = statement.excluded
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[
                            DeviceInventory.controller_id,
                            DeviceInventory.site_uuid,
                            DeviceInventory.device_id,
                        ],
                        set_={
                            "mac": excluded.mac,
                            "name": excluded.name,
                            "model": excluded.model,
                            "version": excluded.version,
                            "state": excluded.state,
                            "payload": excluded.payload,
                            "synced_at": func.now(),
                        },
                    )
                )
        return len(by_id)

    async def list_inventory(self, name: str, site_uuid: str | None = None) -> list[DeviceRecord]:
        """Return the named controller's device snapshot, optionally for one site.

        Raises:
            ResourceNotFoundError: If the controller does not exist
        """
        async with self._sessions() as session:
            controller_id = await self._controller_id(session, name)
            query = select(DeviceInventory).where(DeviceInventory.controller_id == controller_id)
            if site_uuid is not None:
                query = query.where(DeviceInventory.site_uuid == site_uuid)
            rows = (
                (await session.execute(query.order_by(DeviceInventory.device_id))).scalars().all()
            )
        return [
            DeviceRecord(
                device_id=row.device_id,
                payload=row.payload,
                mac=row.mac,
                name=row.name,
                model=row.model,
                version=row.version,
                state=row.state,
            )
            for row in rows
        ]

    async def fleet_status(self, names: Sequence[str] | None = None) -> list[FleetStatus]:
        """Return the recorded health of every enabled controller, by name.

        Args:
            names: Only these controllers (all when None)
        """
        query = (
            select(
                Controller.name,
                Controller.api_type,
                Controller.labels,
                Controller.health,
                Controller.health_detail,
                Controller.health_checked_at,
                Controller.last_seen_at,
                Controller.capabilities,
            )
            .where(Controller.enabled)
            .order_by(Controller.name)
        )
        if names is not None:
            query = query.where(Controller.name.in_(list(names)))
        async with self._sessions() as session:
            rows = (await session.execute(query)).all()
        return [
            FleetStatus(
                name=row.name,
                api_type=row.api_type,
                labels=dict(row.labels),
                health=ControllerHealth(
                    health=row.health,
                    detail=row.health_detail,
                    checked_at=row.health_checked_at,
                    last_seen_at=row.last_seen_at,
                    capabilities=dict(row.capabilities),
                ),
            )
            for row in rows
        ]

    async def fleet_sites(self, names: Sequence[str]) -> list[FleetSite]:
        """Return the site snapshots of ``names``, by controller then site UUID."""
        query = (
            select(
                Controller.name, Site.site_uuid, Site.short_name, Site.display_name, Site.synced_at
            )
            .join(Controller, Controller.id == Site.controller_id)
            .where(Controller.name.in_(list(names)))
            .order_by(Controller.name, Site.site_uuid)
        )
        async with self._sessions() as session:
            rows = (await session.execute(query)).all()
        return [
            FleetSite(
                controller=row.name,
                site=SiteRecord(row.site_uuid, row.short_name, row.display_name),
                synced_at=row.synced_at,
            )
            for row in rows
        ]

    async def fleet_devices(
        self,
        names: Sequence[str],
        *,
        model: str | None = None,
        state: str | None = None,
    ) -> list[FleetDevice]:
        """Return the device snapshots of ``names``, by controller, site and device.

        Args:
            names: The controllers
            model: Only models containing this (case-insensitive)
            state: Only devices in this state (case-insensitive)
        """
        query = (
            select(DeviceInventory, Controller.name)
            .join(Controller, Controller.id == DeviceInventory.controller_id)
            .where(Controller.name.in_(list(names)))
            .order_by(Controller.name, DeviceInventory.site_uuid, DeviceInventory.device_id)
        )
        if model:
            escaped = model.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.where(DeviceInventory.model.ilike(f"%{escaped}%", escape="\\"))
        if state:
            query = query.where(func.lower(DeviceInventory.state) == state.lower())
        async with self._sessions() as session:
            rows = (await session.execute(query)).all()
        return [
            FleetDevice(
                controller=name,
                site_uuid=row.site_uuid,
                device=DeviceRecord(
                    device_id=row.device_id,
                    payload=row.payload,
                    mac=row.mac,
                    name=row.name,
                    model=row.model,
                    version=row.version,
                    state=row.state,
                ),
                synced_at=row.synced_at,
            )
            for row, name in rows
        ]
