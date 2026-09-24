"""Unit tests for device_migration tools.

Moving a device between sites on one controller is ``cmd/sitemgr``
``move-device`` keyed on the target site's 24-hex ``_id``; migrating a
device to another controller is ``cmd/devmgr`` ``migrate`` with the new
controller's inform URL, and ``cancel-migrate`` aborts it. Every tool
resolves the device in the source site before sending a command.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import APIType, Settings
from src.tools import device_migration as dm
from src.utils.exceptions import ResourceNotFoundError, ValidationError

DEVICE_ID = "507f191e810c19729de860ea"  # pragma: allowlist secret
MAC = "aa:bb:cc:dd:ee:01"
SITE_DEFAULT_ID = "5f0000000000000000000001"  # pragma: allowlist secret
SITE_BRANCH_ID = "5f0000000000000000000002"  # pragma: allowlist secret


def _settings(api_type: APIType = APIType.LOCAL) -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.api_type = api_type
    settings.log_level = "INFO"
    settings.get_site_api_path.side_effect = (
        lambda site, endpoint: f"/proxy/network/api/s/{site}/{endpoint}"
    )
    return settings


@pytest.fixture
def local_settings() -> MagicMock:
    return _settings()


DEVICE = {
    "_id": DEVICE_ID,
    "mac": MAC,
    "name": "Lobby AP",
    "model": "U7PG2",
    "type": "uap",
    "state": 1,
}

SITES = [
    {"_id": SITE_DEFAULT_ID, "name": "default", "desc": "Default"},
    {"_id": SITE_BRANCH_ID, "name": "ab12cd34", "desc": "Branch Office"},
]


def _mock_client(devices: list[dict[str, Any]] | None = None, sites: Any = None) -> AsyncMock:
    client = AsyncMock()
    client.authenticate = AsyncMock()

    async def fake_get(endpoint: str, *args: Any, **kwargs: Any) -> Any:
        if endpoint.endswith("/stat/device"):
            return {"data": [DEVICE] if devices is None else devices}
        if endpoint == "/proxy/network/api/self/sites":
            return {"data": SITES} if sites is None else sites
        raise AssertionError(f"unexpected GET {endpoint}")

    client.get = AsyncMock(side_effect=fake_get)
    client.post = AsyncMock(return_value={"meta": {"rc": "ok"}, "data": []})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _patch(client: AsyncMock):
    return patch("src.tools.device_migration.UniFiClient", return_value=client)


# --------------------------------------------------------------------------- #
# Shared gates                                                                #
# --------------------------------------------------------------------------- #


class TestGates:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("api_type", [APIType.CLOUD_EA, APIType.CLOUD_V1])
    async def test_cloud_rejected(self, api_type: APIType) -> None:
        with pytest.raises(NotImplementedError, match="UNIFI_API_TYPE='local'"):
            await dm.move_device_to_site("default", MAC, "Branch Office", _settings(api_type))

    @pytest.mark.asyncio
    async def test_invalid_site_rejected(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValidationError):
            await dm.cancel_device_migration("../x", MAC, local_settings, confirm=True)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "call",
        [
            lambda s: dm.move_device_to_site("default", MAC, "Branch Office", s),
            lambda s: dm.migrate_device("default", MAC, "http://10.0.0.5:8080/inform", s),
            lambda s: dm.cancel_device_migration("default", MAC, s),
        ],
    )
    async def test_confirm_required(self, local_settings: MagicMock, call: Any) -> None:
        client = _mock_client()
        with _patch(client), pytest.raises(ValidationError, match="confirm"):
            await call(local_settings)
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_device_id(self, local_settings: MagicMock) -> None:
        client = _mock_client(devices=[])
        with _patch(client), pytest.raises(ResourceNotFoundError):
            await dm.cancel_device_migration("default", DEVICE_ID, local_settings, confirm=True)
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_mac(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client), pytest.raises(ResourceNotFoundError):
            await dm.cancel_device_migration(
                "default", "aa:bb:cc:dd:ee:99", local_settings, confirm=True
            )
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_identifier_must_be_id_or_mac(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client), pytest.raises(ValidationError, match="device"):
            await dm.cancel_device_migration("default", "lobby-ap", local_settings, confirm=True)
        client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolves_by_device_id(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client):
            await dm.cancel_device_migration("default", DEVICE_ID, local_settings, confirm=True)
        assert client.post.call_args.kwargs["json_data"]["mac"] == MAC

    @pytest.mark.asyncio
    async def test_resolves_mac_in_any_format(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client):
            await dm.cancel_device_migration(
                "default", "AABB.CCDD.EE01", local_settings, confirm=True
            )
        assert client.post.call_args.kwargs["json_data"]["mac"] == MAC

    @pytest.mark.asyncio
    async def test_failure_is_audited_and_reraised(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.post.side_effect = RuntimeError("boom")
        with _patch(client), patch("src.tools.device_migration.log_audit") as audit:
            with pytest.raises(RuntimeError):
                await dm.cancel_device_migration("default", MAC, local_settings, confirm=True)
        assert audit.call_args.kwargs["result"] == "failed"


# --------------------------------------------------------------------------- #
# move_device_to_site                                                         #
# --------------------------------------------------------------------------- #


class TestMoveDeviceToSite:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("target", [SITE_BRANCH_ID, "ab12cd34", "branch office", "AB12CD34"])
    async def test_moves_by_any_site_reference(
        self, local_settings: MagicMock, target: str
    ) -> None:
        client = _mock_client()
        with _patch(client), patch("src.tools.device_migration.log_audit") as audit:
            result = await dm.move_device_to_site(
                "default", MAC, target, local_settings, confirm=True
            )

        assert client.post.call_args.args[0] == "/proxy/network/api/s/default/cmd/sitemgr"
        assert client.post.call_args.kwargs["json_data"] == {
            "cmd": "move-device",
            "site": SITE_BRANCH_ID,
            "mac": MAC,
        }
        assert result["success"] is True
        assert result["mac"] == MAC
        assert result["target_site"] == {
            "id": SITE_BRANCH_ID,
            "name": "ab12cd34",
            "description": "Branch Office",
        }
        assert audit.call_args.kwargs["result"] == "success"

    @pytest.mark.asyncio
    async def test_reads_legacy_site_list(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client):
            await dm.move_device_to_site(
                "default", MAC, "Branch Office", local_settings, dry_run=True
            )
        endpoints = [c.args[0] for c in client.get.call_args_list]
        assert "/proxy/network/api/self/sites" in endpoints

    @pytest.mark.asyncio
    async def test_dry_run_previews_without_posting(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client):
            result = await dm.move_device_to_site(
                "default", MAC, "Branch Office", local_settings, dry_run=True
            )
        assert result["dry_run"] is True
        assert result["device"]["name"] == "Lobby AP"
        assert result["target_site"]["id"] == SITE_BRANCH_ID
        assert result["would_send"] == {"cmd": "move-device", "site": SITE_BRANCH_ID, "mac": MAC}
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_target_site(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client), pytest.raises(ResourceNotFoundError, match="Nowhere"):
            await dm.move_device_to_site("default", MAC, "Nowhere", local_settings, confirm=True)
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_ambiguous_description_rejected(self, local_settings: MagicMock) -> None:
        sites = {
            "data": SITES
            + [{"_id": "5f0000000000000000000003", "name": "zz99", "desc": "Branch Office"}]
        }
        client = _mock_client(sites=sites)
        with _patch(client), pytest.raises(ValidationError, match="ambiguous"):
            await dm.move_device_to_site(
                "default", MAC, "Branch Office", local_settings, confirm=True
            )
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_same_site_rejected(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client), pytest.raises(ValidationError, match="already"):
            await dm.move_device_to_site("default", MAC, "Default", local_settings, confirm=True)
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_blank_target_rejected(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValidationError, match="target_site"):
            await dm.move_device_to_site("default", MAC, "  ", local_settings, confirm=True)


# --------------------------------------------------------------------------- #
# migrate_device                                                              #
# --------------------------------------------------------------------------- #


class TestMigrateDevice:
    @pytest.mark.asyncio
    async def test_migrates(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client), patch("src.tools.device_migration.log_audit") as audit:
            result = await dm.migrate_device(
                "default",
                MAC,
                "http://controller.example.net:8080/inform",
                local_settings,
                confirm=True,
            )
        assert client.post.call_args.args[0] == "/proxy/network/api/s/default/cmd/devmgr"
        assert client.post.call_args.kwargs["json_data"] == {
            "cmd": "migrate",
            "mac": MAC,
            "inform_url": "http://controller.example.net:8080/inform",
        }
        assert result["success"] is True
        assert result["inform_url"] == "http://controller.example.net:8080/inform"
        assert "adopt" in result["next_step"]
        assert audit.call_args.kwargs["result"] == "success"

    @pytest.mark.asyncio
    async def test_dry_run(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client):
            result = await dm.migrate_device(
                "default", MAC, "https://10.0.0.5:8443/inform", local_settings, dry_run=True
            )
        assert result["dry_run"] is True
        assert result["would_send"]["cmd"] == "migrate"
        client.post.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "url",
        [
            "",
            "10.0.0.5:8080/inform",
            "ftp://10.0.0.5/inform",
            "http:///inform",
            "http://10.0.0.5:8080/",
            "http://10.0.0.5:8080/inform?x=1",
            "http://user:pw@10.0.0.5:8080/inform",  # pragma: allowlist secret
            "http://10.0.0.5:99999/inform",
            "http://10.0.0.5:8080/inform extra",
        ],
    )
    async def test_invalid_inform_url_rejected(self, local_settings: MagicMock, url: str) -> None:
        client = _mock_client()
        with _patch(client), pytest.raises(ValidationError, match="inform_url"):
            await dm.migrate_device("default", MAC, url, local_settings, confirm=True)
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_offline_device_warns(self, local_settings: MagicMock) -> None:
        client = _mock_client(devices=[{**DEVICE, "state": 0}])
        with _patch(client):
            result = await dm.migrate_device(
                "default", MAC, "http://10.0.0.5:8080/inform", local_settings, confirm=True
            )
        assert any("offline" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_online_device_has_no_warnings(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client):
            result = await dm.migrate_device(
                "default", MAC, "http://10.0.0.5:8080/inform", local_settings, confirm=True
            )
        assert "warnings" not in result


# --------------------------------------------------------------------------- #
# cancel_device_migration                                                     #
# --------------------------------------------------------------------------- #


class TestCancelDeviceMigration:
    @pytest.mark.asyncio
    async def test_cancels(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client):
            result = await dm.cancel_device_migration("default", MAC, local_settings, confirm=True)
        assert client.post.call_args.args[0] == "/proxy/network/api/s/default/cmd/devmgr"
        assert client.post.call_args.kwargs["json_data"] == {"cmd": "cancel-migrate", "mac": MAC}
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_dry_run(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch(client):
            result = await dm.cancel_device_migration("default", MAC, local_settings, dry_run=True)
        assert result["would_send"] == {"cmd": "cancel-migrate", "mac": MAC}
        client.post.assert_not_called()


class TestRegistration:
    def test_all_tools_are_classified_mutating(self) -> None:
        from src.tool_registry import is_mutating_tool

        for fn in (dm.move_device_to_site, dm.migrate_device, dm.cancel_device_migration):
            assert is_mutating_tool(fn)
