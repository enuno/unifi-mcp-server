"""The worker's snapshots (sites, device inventory, health), on a real Postgres."""

from typing import Any

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import text  # noqa: E402

from src.config.config import APIType  # noqa: E402
from src.fleet.credentials import CredentialCipher  # noqa: E402
from src.fleet.db.snapshots import DeviceRecord, SiteRecord, SnapshotStore  # noqa: E402
from src.fleet.db.store import FleetStore  # noqa: E402
from src.utils.exceptions import ResourceNotFoundError  # noqa: E402

KEY = "hq-api-key-0123456789"  # pragma: allowlist secret


@pytest.fixture
async def snapshots(migrated_engine: Any, credential_key: str) -> SnapshotStore:
    fleet = FleetStore(migrated_engine, CredentialCipher.from_env())
    for name in ("hq", "branch"):
        await fleet.add_controller(
            name=name, api_type=APIType.LOCAL, api_key=KEY, local_host="10.0.0.1"
        )
    return SnapshotStore(migrated_engine)


def _device(device_id: str, **fields: Any) -> DeviceRecord:
    return DeviceRecord(device_id=device_id, payload={"id": device_id, **fields}, **fields)


class TestHealth:
    async def test_unchecked_controller(self, snapshots: SnapshotStore) -> None:
        health = await snapshots.health("hq")
        assert health.health is None
        assert health.checked_at is None
        assert health.capabilities == {}

    async def test_ok_records_last_seen_and_capabilities(self, snapshots: SnapshotStore) -> None:
        await snapshots.record_health("hq", "ok", capabilities={"network_version": "9.4.19"})

        health = await snapshots.health("hq")
        assert health.health == "ok"
        assert health.checked_at is not None
        assert health.last_seen_at is not None
        assert health.capabilities == {"network_version": "9.4.19"}

    async def test_down_keeps_last_seen_and_capabilities(self, snapshots: SnapshotStore) -> None:
        await snapshots.record_health("hq", "ok", capabilities={"network_version": "9.4.19"})
        seen = (await snapshots.health("hq")).last_seen_at

        await snapshots.record_health("hq", "down", detail="x" * 400)

        health = await snapshots.health("hq")
        assert health.health == "down"
        assert health.detail == "x" * 255
        assert health.last_seen_at == seen
        assert health.capabilities == {"network_version": "9.4.19"}

    async def test_degraded_does_not_count_as_seen(self, snapshots: SnapshotStore) -> None:
        await snapshots.record_health("hq", "ok")
        seen = (await snapshots.health("hq")).last_seen_at

        await snapshots.record_health("hq", "degraded", detail="ConnectError")

        health = await snapshots.health("hq")
        assert health.health == "degraded"
        assert health.last_seen_at == seen

    async def test_unknown_controller(self, snapshots: SnapshotStore) -> None:
        with pytest.raises(ResourceNotFoundError):
            await snapshots.record_health("gone", "ok")
        with pytest.raises(ResourceNotFoundError):
            await snapshots.health("gone")

    async def test_invalid_health_is_refused_by_the_database(
        self, snapshots: SnapshotStore
    ) -> None:
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            await snapshots.record_health("hq", "unknown")  # type: ignore[arg-type]


class TestSites:
    async def test_replace_adds_updates_and_removes(self, snapshots: SnapshotStore) -> None:
        await snapshots.replace_sites(
            "hq", [SiteRecord("s-1", "default", "Default"), SiteRecord("s-2", "lab", "Lab")]
        )
        stored = await snapshots.replace_sites(
            "hq", [SiteRecord("s-1", "default", "Head office"), SiteRecord("s-3", "new")]
        )

        assert stored == 2
        assert await snapshots.list_sites("hq") == [
            SiteRecord("s-1", "default", "Head office"),
            SiteRecord("s-3", "new", None),
        ]

    async def test_snapshots_are_per_controller(self, snapshots: SnapshotStore) -> None:
        await snapshots.replace_sites("hq", [SiteRecord("s-1", "default")])
        await snapshots.replace_sites("branch", [SiteRecord("s-1", "default")])
        await snapshots.replace_sites("branch", [])

        assert await snapshots.list_sites("branch") == []
        assert await snapshots.list_sites("hq") == [SiteRecord("s-1", "default")]

    async def test_unknown_controller(self, snapshots: SnapshotStore) -> None:
        with pytest.raises(ResourceNotFoundError):
            await snapshots.replace_sites("gone", [])
        with pytest.raises(ResourceNotFoundError):
            await snapshots.list_sites("gone")


class TestInventory:
    async def test_replace_per_site(self, snapshots: SnapshotStore) -> None:
        await snapshots.replace_sites("hq", [SiteRecord("s-1"), SiteRecord("s-2")])
        await snapshots.replace_inventory(
            "hq", "s-1", [_device("d-1", model="UDM", version="4.0.6"), _device("d-2")]
        )
        await snapshots.replace_inventory("hq", "s-2", [_device("d-9")])

        stored = await snapshots.replace_inventory(
            "hq", "s-1", [_device("d-1", model="UDM", version="4.1.0", state="ONLINE")]
        )

        assert stored == 1
        site_one = await snapshots.list_inventory("hq", "s-1")
        assert [d.device_id for d in site_one] == ["d-1"]
        assert site_one[0].version == "4.1.0"
        assert site_one[0].state == "ONLINE"
        assert site_one[0].payload == {
            "id": "d-1",
            "model": "UDM",
            "version": "4.1.0",
            "state": "ONLINE",
        }
        assert [d.device_id for d in await snapshots.list_inventory("hq")] == ["d-1", "d-9"]

    async def test_empty_replace_clears_the_site(self, snapshots: SnapshotStore) -> None:
        await snapshots.replace_sites("hq", [SiteRecord("s-1")])
        await snapshots.replace_inventory("hq", "s-1", [_device("d-1")])

        assert await snapshots.replace_inventory("hq", "s-1", []) == 0
        assert await snapshots.list_inventory("hq") == []

    async def test_removing_a_site_removes_its_devices(self, snapshots: SnapshotStore) -> None:
        await snapshots.replace_sites("hq", [SiteRecord("s-1"), SiteRecord("s-2")])
        await snapshots.replace_inventory("hq", "s-1", [_device("d-1")])
        await snapshots.replace_inventory("hq", "s-2", [_device("d-2")])

        await snapshots.replace_sites("hq", [SiteRecord("s-2")])

        assert [d.device_id for d in await snapshots.list_inventory("hq")] == ["d-2"]

    async def test_unknown_site_or_controller(self, snapshots: SnapshotStore) -> None:
        with pytest.raises(ResourceNotFoundError, match="s-1"):
            await snapshots.replace_inventory("hq", "s-1", [])
        with pytest.raises(ResourceNotFoundError):
            await snapshots.replace_inventory("gone", "s-1", [])
        with pytest.raises(ResourceNotFoundError):
            await snapshots.list_inventory("gone")

    async def test_deleting_a_controller_removes_its_snapshots(
        self, snapshots: SnapshotStore
    ) -> None:
        await snapshots.replace_sites("hq", [SiteRecord("s-1")])
        await snapshots.replace_inventory("hq", "s-1", [_device("d-1")])

        async with snapshots.engine.begin() as conn:
            await conn.execute(text("DELETE FROM controllers WHERE name = 'hq'"))
            sites = await conn.scalar(text("SELECT count(*) FROM sites"))
            devices = await conn.scalar(text("SELECT count(*) FROM device_inventory"))

        assert (sites, devices) == (0, 0)
