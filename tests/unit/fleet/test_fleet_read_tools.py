"""fleet_health, fleet_sites and fleet_inventory over the worker's snapshots, on Postgres."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")

from fastmcp.server.auth import AccessToken  # noqa: E402
from sqlalchemy import text  # noqa: E402

from src.config.config import APIType, Settings  # noqa: E402
from src.fleet.db.snapshots import DeviceRecord, SiteRecord, SnapshotStore  # noqa: E402
from src.fleet.fleet_tools import build_snapshot_tools, version_key  # noqa: E402
from src.fleet.postgres_registry import PostgresRegistry  # noqa: E402
from src.utils.exceptions import ValidationError  # noqa: E402

KEY = "fleet-key-0123456789"  # pragma: allowlist secret


@pytest.fixture
def settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, database_url: str, credential_key: str
) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", KEY)
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UNIFI_FLEET_WORKER_HEALTH_SECONDS", "60")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr("src.utils.audit._audit_logger", None)
    return Settings()


def _device(device_id: str, model: str, version: str | None, state: str = "ONLINE") -> Any:
    return DeviceRecord(
        device_id=device_id,
        payload={"id": device_id},
        mac=f"aa:bb:cc:00:00:{device_id[-2:]}",
        name=f"Device {device_id}",
        model=model,
        version=version,
        state=state,
    )


@pytest.fixture
async def tools(settings: Settings, migrated_engine: Any) -> Any:
    registry = PostgresRegistry.from_settings(settings)
    store = registry.store
    await store.add_controller(
        name="hq",
        api_type=APIType.LOCAL,
        api_key=KEY,
        local_host="10.0.0.1",
        labels={"group": "retail"},
    )
    await store.add_controller(
        name="branch", api_type=APIType.LOCAL, api_key=KEY, local_host="10.0.1.1"
    )
    await store.add_controller(name="cloud", api_type=APIType.CLOUD_EA, api_key=KEY)
    await store.add_controller(
        name="retired", api_type=APIType.LOCAL, api_key=KEY, local_host="10.0.9.1", enabled=False
    )
    await registry.start(seed=False)
    snapshots = SnapshotStore(registry.store.engine)

    await snapshots.record_health("hq", "ok", capabilities={"network_version": "9.4.19"})
    await snapshots.record_health("branch", "down", detail="ConnectError")
    await snapshots.replace_sites("hq", [SiteRecord("s-hq", "default", "Head office")])
    await snapshots.replace_sites("branch", [SiteRecord("s-br", "default", "Branch")])
    await snapshots.replace_inventory(
        "hq",
        "s-hq",
        [
            _device("d-01", "UDM-Pro", "4.0.9"),
            _device("d-02", "U7PRO", "8.0.10"),
            _device("d-03", "U7PRO", "7.6.1", state="OFFLINE"),
            _device("d-04", "USW_24", None),
        ],
    )
    await snapshots.replace_inventory("branch", "s-br", [_device("d-11", "UDM", "4.1.0")])
    tools_list = build_snapshot_tools(registry, snapshots, settings)
    names = [t.__name__ for t in tools_list]
    yield {
        "health": tools_list[names.index("fleet_health")],
        "sites": tools_list[names.index("fleet_sites")],
        "inventory": tools_list[names.index("fleet_inventory")],
        "compare_versions": tools_list[names.index("fleet_compare_versions")],
        "compare_sites": tools_list[names.index("fleet_compare_sites")],
        "snapshots": snapshots,
        "settings": settings,
    }
    await registry.stop()


def _as(monkeypatch: pytest.MonkeyPatch, role: str, **claims: Any) -> None:
    token = AccessToken(
        token="umcp_test",  # noqa: S106
        client_id="t",
        scopes=[],
        claims={"token_id": "tok-1", "name": "t", "role": role, **claims},
    )
    monkeypatch.setattr("src.access.get_access_token", lambda: token)


def test_version_key_orders_numerically() -> None:
    assert version_key("4.0.10") > version_key("4.0.9")
    assert version_key("v8.0.1.15423") > version_key("8.0")
    assert version_key("beta") == ()


def test_version_key_ignores_trailing_zeros() -> None:
    assert version_key("8.0") == version_key("8.0.0") == version_key("8")
    assert not version_key("8.0") < version_key("8.0.0")
    assert version_key("8.0.0.1") > version_key("8")


class TestFleetHealth:
    async def test_every_enabled_controller(self, tools: dict[str, Any]) -> None:
        result = await tools["health"](settings=tools["settings"])

        by_name = {c["name"]: c for c in result["controllers"]}
        assert sorted(by_name) == ["branch", "cloud", "hq"]
        assert result["counts"] == {"down": 1, "ok": 1, "unknown": 1}
        assert by_name["hq"]["health"] == "ok"
        assert by_name["hq"]["stale"] is False
        assert by_name["hq"]["capabilities"] == {"network_version": "9.4.19"}
        assert by_name["hq"]["labels"] == {"group": "retail"}
        assert by_name["branch"]["detail"] == "ConnectError"
        assert by_name["branch"]["last_seen_seconds_ago"] is None
        assert by_name["cloud"]["health"] == "unknown"
        assert by_name["cloud"]["stale"] is True

    async def test_old_checks_are_stale(self, tools: dict[str, Any], migrated_engine: Any) -> None:
        async with migrated_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE controllers SET health_checked_at = now() - interval '181 seconds' "
                    "WHERE name = 'hq'"
                )
            )

        result = await tools["health"](health="ok", settings=tools["settings"])

        assert [c["name"] for c in result["controllers"]] == ["hq"]
        assert result["controllers"][0]["stale"] is True

    async def test_filters(self, tools: dict[str, Any]) -> None:
        result = await tools["health"](labels={"group": "retail"}, settings=tools["settings"])
        assert [c["name"] for c in result["controllers"]] == ["hq"]
        assert result["total"] == 1

        with pytest.raises(ValidationError, match="health must be"):
            await tools["health"](health="sideways", settings=tools["settings"])

    async def test_caller_scope(self, tools: dict[str, Any], monkeypatch: Any) -> None:
        _as(monkeypatch, "viewer", controller_labels={"group": "retail"})
        result = await tools["health"](settings=tools["settings"])
        assert [c["name"] for c in result["controllers"]] == ["hq"]


class TestFleetSites:
    async def test_sites(self, tools: dict[str, Any]) -> None:
        result = await tools["sites"](settings=tools["settings"])

        assert result["count"] == 2
        assert [(s["controller"], s["site_id"], s["name"]) for s in result["sites"]] == [
            ("branch", "s-br", "Branch"),
            ("hq", "s-hq", "Head office"),
        ]
        assert result["sites"][0]["synced_seconds_ago"] >= 0

    async def test_named_controllers(self, tools: dict[str, Any]) -> None:
        result = await tools["sites"](controllers=["hq"], settings=tools["settings"])
        assert [s["controller"] for s in result["sites"]] == ["hq"]

    async def test_unknown_or_disabled_controller(self, tools: dict[str, Any]) -> None:
        with pytest.raises(ValidationError, match="retired"):
            await tools["sites"](controllers=["retired"], settings=tools["settings"])

    async def test_out_of_scope_controller(self, tools: dict[str, Any], monkeypatch: Any) -> None:
        _as(monkeypatch, "viewer", controller_labels={"group": "retail"})
        with pytest.raises(ValidationError, match="branch"):
            await tools["sites"](controllers=["branch"], settings=tools["settings"])


class TestFleetInventory:
    async def test_everything(self, tools: dict[str, Any]) -> None:
        result = await tools["inventory"](settings=tools["settings"])

        assert result["total"] == 5
        assert result["by_model"] == {"U7PRO": 2, "UDM": 1, "UDM-Pro": 1, "USW_24": 1}
        first = result["devices"][0]
        assert first["controller"] == "branch"
        assert first["firmware_version"] == "4.1.0"
        assert first["synced_seconds_ago"] >= 0

    async def test_firmware_below_compares_numerically(self, tools: dict[str, Any]) -> None:
        result = await tools["inventory"](firmware_below="8.0.9", settings=tools["settings"])
        # 8.0.10 is newer than 8.0.9; the device without a version is left out.
        assert sorted(d["id"] for d in result["devices"]) == ["d-01", "d-03", "d-11"]

    async def test_model_and_state(self, tools: dict[str, Any]) -> None:
        udm = await tools["inventory"](model="udm", settings=tools["settings"])
        assert sorted(d["id"] for d in udm["devices"]) == ["d-01", "d-11"]

        offline = await tools["inventory"](state="offline", settings=tools["settings"])
        assert [d["id"] for d in offline["devices"]] == ["d-03"]

    async def test_model_wildcards_are_literal(self, tools: dict[str, Any]) -> None:
        result = await tools["inventory"](model="USW_", settings=tools["settings"])
        assert [d["id"] for d in result["devices"]] == ["d-04"]
        result = await tools["inventory"](model="%", settings=tools["settings"])
        assert result["total"] == 0

    async def test_paging(self, tools: dict[str, Any]) -> None:
        page = await tools["inventory"](limit=2, offset=2, settings=tools["settings"])
        assert page["total"] == 5
        assert page["offset"] == 2
        assert [d["id"] for d in page["devices"]] == ["d-02", "d-03"]

    async def test_labels_and_scope(self, tools: dict[str, Any], monkeypatch: Any) -> None:
        result = await tools["inventory"](labels={"group": "retail"}, settings=tools["settings"])
        assert {d["controller"] for d in result["devices"]} == {"hq"}

        _as(monkeypatch, "viewer", controller_labels={"group": "retail"})
        result = await tools["inventory"](settings=tools["settings"])
        assert {d["controller"] for d in result["devices"]} == {"hq"}

    @pytest.mark.parametrize(
        ("arguments", "message"),
        [
            ({"limit": 0}, "limit must be"),
            ({"limit": 1001}, "limit must be"),
            ({"offset": -1}, "offset must not"),
            ({"firmware_below": "latest"}, "must contain a version"),
        ],
    )
    async def test_invalid_arguments(
        self, tools: dict[str, Any], arguments: dict[str, Any], message: str
    ) -> None:
        with pytest.raises(ValidationError, match=message):
            await tools["inventory"](settings=tools["settings"], **arguments)


class TestFleetCompareVersions:
    async def test_across_controllers(self, tools: dict[str, Any]) -> None:
        result = await tools["compare_versions"](settings=tools["settings"])

        assert result["controllers_compared"] == ["branch", "cloud", "hq"]
        assert result["total_devices"] == 5
        u7pro = result["models"]["U7PRO"]
        assert u7pro["newest"] == "8.0.10"
        assert u7pro["controllers"]["hq"]["count"] == 2
        assert u7pro["controllers"]["hq"]["behind"] is False
        assert u7pro["controllers"]["hq"]["synced_seconds_ago"] >= 0
        assert u7pro["controllers"]["hq"]["stale"] is False
        assert u7pro["controllers"]["branch"]["count"] == 0
        assert u7pro["controllers"]["branch"]["behind"] is False
        assert u7pro["data_as_of_seconds_ago"] >= 0
        assert u7pro["stale"] is False

    async def test_model_filter(self, tools: dict[str, Any]) -> None:
        result = await tools["compare_versions"](model="UDM", settings=tools["settings"])

        assert sorted(result["models"]) == ["UDM", "UDM-Pro"]
        udm = result["models"]["UDM"]
        assert udm["newest"] == "4.1.0"
        assert udm["controllers"]["branch"]["behind"] is False
        assert udm["controllers"]["hq"]["behind"] is False

    async def test_behind_flag(self, tools: dict[str, Any]) -> None:
        await tools["snapshots"].replace_inventory(
            "branch",
            "s-br",
            [
                _device("d-11", "UDM", "4.1.0"),
                _device("d-12", "U7PRO", "7.6.0"),
            ],
        )
        result = await tools["compare_versions"](model="U7PRO", settings=tools["settings"])

        u7pro = result["models"]["U7PRO"]
        assert u7pro["newest"] == "8.0.10"
        assert u7pro["controllers"]["branch"]["behind"] is True
        assert u7pro["controllers"]["hq"]["behind"] is False

    async def test_unknown_version_not_behind(self, tools: dict[str, Any]) -> None:
        result = await tools["compare_versions"](model="USW_24", settings=tools["settings"])

        usw = result["models"]["USW_24"]
        assert usw["newest"] is None
        assert usw["controllers"]["hq"]["behind"] is False

    async def test_scope_and_labels(self, tools: dict[str, Any], monkeypatch: Any) -> None:
        _as(monkeypatch, "viewer", controller_labels={"group": "retail"})
        result = await tools["compare_versions"](settings=tools["settings"])
        assert result["controllers_compared"] == ["hq"]
        assert "hq" in result["models"].get("UDM-Pro", {}).get("controllers", {})


class TestFleetCompareSites:
    async def test_common_and_unique(self, tools: dict[str, Any]) -> None:
        result = await tools["compare_sites"](
            controllers=["hq", "branch"], settings=tools["settings"]
        )

        assert result["controllers_compared"] == ["branch", "hq"]
        assert result["total_sites"] == 2
        assert result["common_sites"] == ["default"]
        assert result["unique_sites"]["hq"] == []
        assert result["unique_sites"]["branch"] == []
        assert result["by_controller"]["hq"][0]["short_name"] == "default"
        assert result["by_controller"]["hq"][0]["synced_seconds_ago"] >= 0
        assert result["by_controller"]["hq"][0]["stale"] is False
        assert result["controller_sync_age"]["hq"] >= 0
        assert result["data_as_of_seconds_ago"] >= 0
        assert result["stale"] is False

    async def test_named_controllers(self, tools: dict[str, Any]) -> None:
        result = await tools["compare_sites"](controllers=["hq"], settings=tools["settings"])
        assert result["controllers_compared"] == ["hq"]
        assert result["common_sites"] == ["default"]
        assert result["unique_sites"]["hq"] == []

    async def test_scope(self, tools: dict[str, Any], monkeypatch: Any) -> None:
        _as(monkeypatch, "viewer", controller_labels={"group": "retail"})
        result = await tools["compare_sites"](settings=tools["settings"])
        assert result["controllers_compared"] == ["hq"]
        assert result["total_sites"] == 1
