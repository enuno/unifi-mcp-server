"""Unit tests for mac_tags tools.

Tags live at the legacy V1 internal endpoint
``/proxy/network/api/s/{site}/rest/tag`` (auto-translated by the client from
the ``/ea/sites/{site}/rest/tag`` shape used here). A tag is a name plus a
``member_table`` of device MAC addresses. The endpoint is local-gateway only,
so every tool in the module is gated on ``UNIFI_API_TYPE=local``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import APIType, Settings
from src.tools import mac_tags as mt
from src.utils.exceptions import DuplicateResourceError, ResourceNotFoundError, ValidationError

TAG_ID = "5f1e2d3c4b5a697886950413"
OTHER_TAG_ID = "5f1e2d3c4b5a697886950414"
MAC_A = "aa:bb:cc:dd:ee:01"
MAC_B = "aa:bb:cc:dd:ee:02"
MAC_C = "aa:bb:cc:dd:ee:03"


@pytest.fixture
def local_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.api_type = APIType.LOCAL
    settings.api_key = "test-api-key"  # pragma: allowlist secret
    settings.local_host = "192.0.2.1"
    settings.log_level = "INFO"
    return settings


@pytest.fixture
def cloud_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.api_type = APIType.CLOUD_EA
    settings.api_key = "test-api-key"  # pragma: allowlist secret
    settings.log_level = "INFO"
    return settings


def _tag(tag_id: str = TAG_ID, name: str = "Lobby APs", members: list[str] | None = None) -> dict:
    return {
        "_id": tag_id,
        "name": name,
        "member_table": [MAC_A, MAC_B] if members is None else members,
        "site_id": "site-internal-1",
    }


def _mock_client(get_response: Any = None) -> AsyncMock:
    client = AsyncMock()
    client.is_authenticated = True
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value=get_response)
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _patch_client(client: AsyncMock):
    return patch("src.tools.mac_tags.UniFiClient", return_value=client)


# --------------------------------------------------------------------------- #
# Gates and validation                                                        #
# --------------------------------------------------------------------------- #


class TestLocalApiGate:
    @pytest.mark.asyncio
    async def test_list_rejects_cloud(self, cloud_settings: MagicMock) -> None:
        with pytest.raises(NotImplementedError, match="UNIFI_API_TYPE='local'"):
            await mt.list_mac_tags("default", cloud_settings)

    @pytest.mark.asyncio
    async def test_create_rejects_cloud(self, cloud_settings: MagicMock) -> None:
        with pytest.raises(NotImplementedError, match="UNIFI_API_TYPE='local'"):
            await mt.create_mac_tag("x", [MAC_A], "default", cloud_settings, confirm=True)


class TestInputValidation:
    @pytest.mark.asyncio
    async def test_invalid_site_id_rejected(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValidationError):
            await mt.list_mac_tags("../default", local_settings)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_id", ["", "not-an-id", "../5f1e2d3c4b5a697886950413", "x" * 24])
    async def test_invalid_tag_id_rejected(self, local_settings: MagicMock, bad_id: str) -> None:
        client = _mock_client()
        with _patch_client(client), pytest.raises(ValidationError, match="tag ID"):
            await mt.get_mac_tag(bad_id, "default", local_settings)
        client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_mac_rejected_before_any_request(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": []})
        with _patch_client(client), pytest.raises(ValidationError, match="Invalid MAC"):
            await mt.create_mac_tag("x", ["not-a-mac"], "default", local_settings, confirm=True)
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_blank_name_rejected(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValidationError, match="name"):
            await mt.create_mac_tag("   ", [MAC_A], "default", local_settings, confirm=True)

    @pytest.mark.asyncio
    async def test_macs_must_be_a_list(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValidationError, match="list"):
            await mt.create_mac_tag(
                "x", MAC_A, "default", local_settings, confirm=True  # type: ignore[arg-type]
            )


# --------------------------------------------------------------------------- #
# Read                                                                        #
# --------------------------------------------------------------------------- #


class TestListMacTags:
    @pytest.mark.asyncio
    async def test_lists_tags(self, local_settings: MagicMock) -> None:
        client = _mock_client(
            get_response={"meta": {"rc": "ok"}, "data": [_tag(), _tag(OTHER_TAG_ID, "Warehouse")]}
        )
        with _patch_client(client):
            result = await mt.list_mac_tags("default", local_settings)

        assert [t["name"] for t in result] == ["Lobby APs", "Warehouse"]
        assert result[0]["id"] == TAG_ID
        assert result[0]["member_table"] == [MAC_A, MAC_B]
        assert result[0]["member_count"] == 2
        assert client.get.call_args.args[0] == "/ea/sites/default/rest/tag"

    @pytest.mark.asyncio
    async def test_empty_site(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": []})
        with _patch_client(client):
            assert await mt.list_mac_tags("default", local_settings) == []

    @pytest.mark.asyncio
    async def test_tag_without_member_table(self, local_settings: MagicMock) -> None:
        raw = {"_id": TAG_ID, "name": "Empty"}
        client = _mock_client(get_response={"data": [raw]})
        with _patch_client(client):
            result = await mt.list_mac_tags("default", local_settings)
        assert result[0]["member_table"] == []
        assert result[0]["member_count"] == 0

    @pytest.mark.asyncio
    async def test_authenticates_when_needed(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": []})
        client.is_authenticated = False
        with _patch_client(client):
            await mt.list_mac_tags("default", local_settings)
        client.authenticate.assert_awaited_once()


class TestGetMacTag:
    @pytest.mark.asyncio
    async def test_gets_tag(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": [_tag()]})
        with _patch_client(client):
            result = await mt.get_mac_tag(TAG_ID.upper(), "default", local_settings)
        assert result["id"] == TAG_ID
        assert client.get.call_args.args[0] == f"/ea/sites/default/rest/tag/{TAG_ID}"

    @pytest.mark.asyncio
    async def test_empty_response_is_not_found(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": []})
        with _patch_client(client), pytest.raises(ResourceNotFoundError):
            await mt.get_mac_tag(TAG_ID, "default", local_settings)

    @pytest.mark.asyncio
    async def test_api_not_found_is_reraised_with_tag_context(
        self, local_settings: MagicMock
    ) -> None:
        client = _mock_client()
        client.get.side_effect = ResourceNotFoundError("endpoint", "x")
        with _patch_client(client), pytest.raises(ResourceNotFoundError, match=TAG_ID):
            await mt.get_mac_tag(TAG_ID, "default", local_settings)


# --------------------------------------------------------------------------- #
# Create                                                                      #
# --------------------------------------------------------------------------- #


class TestCreateMacTag:
    @pytest.mark.asyncio
    async def test_requires_confirm(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch_client(client), pytest.raises(ValueError, match="confirm=True"):
            await mt.create_mac_tag("Lobby APs", [MAC_A], "default", local_settings)
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_normalises_and_sends_nothing(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": []})
        with _patch_client(client):
            result = await mt.create_mac_tag(
                " Lobby APs ",
                ["AA-BB-CC-DD-EE-01", "aabb.ccdd.ee02", "aa:bb:cc:dd:ee:01"],
                "default",
                local_settings,
                dry_run=True,
            )
        assert result["status"] == "dry_run"
        assert result["payload"] == {"name": "Lobby APs", "member_table": [MAC_A, MAC_B]}
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_tag(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": []})
        client.post.return_value = {"data": [_tag()]}
        with _patch_client(client), patch("src.tools.mac_tags.log_audit") as audit:
            result = await mt.create_mac_tag(
                "Lobby APs", [MAC_A, MAC_B], "default", local_settings, confirm="true"
            )

        assert result["id"] == TAG_ID
        assert "warnings" not in result
        endpoint = client.post.call_args.args[0]
        assert endpoint == "/ea/sites/default/rest/tag"
        assert client.post.call_args.kwargs["json_data"] == {
            "name": "Lobby APs",
            "member_table": [MAC_A, MAC_B],
        }
        audit.assert_called_once()
        assert audit.call_args.kwargs["operation"] == "create_mac_tag"

    @pytest.mark.asyncio
    async def test_empty_member_list_allowed(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": []})
        client.post.return_value = {"data": [_tag(members=[])]}
        with _patch_client(client):
            result = await mt.create_mac_tag(
                "Lobby APs", [], "default", local_settings, confirm=True
            )
        assert result["member_table"] == []

    @pytest.mark.asyncio
    async def test_duplicate_name_rejected(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": [_tag(name="Lobby APs")]})
        with _patch_client(client), pytest.raises(DuplicateResourceError):
            await mt.create_mac_tag("lobby aps", [MAC_A], "default", local_settings, confirm=True)
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_name_reported_in_dry_run(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": [_tag(name="Lobby APs")]})
        with _patch_client(client), pytest.raises(DuplicateResourceError):
            await mt.create_mac_tag("Lobby APs", [MAC_A], "default", local_settings, dry_run=True)

    @pytest.mark.asyncio
    async def test_unechoed_create_is_resolved_by_rereading(
        self, local_settings: MagicMock
    ) -> None:
        client = _mock_client()
        client.get.side_effect = [{"data": []}, {"data": [_tag()]}]
        client.post.return_value = {"data": []}
        with _patch_client(client):
            result = await mt.create_mac_tag(
                "Lobby APs", [MAC_A, MAC_B], "default", local_settings, confirm=True
            )
        assert result["id"] == TAG_ID
        assert client.get.await_count == 2

    @pytest.mark.asyncio
    async def test_unechoed_create_not_found_on_reread_warns(
        self, local_settings: MagicMock
    ) -> None:
        client = _mock_client()
        client.get.side_effect = [{"data": []}, {"data": []}]
        client.post.return_value = {"data": []}
        with _patch_client(client):
            result = await mt.create_mac_tag(
                "Lobby APs", [MAC_A], "default", local_settings, confirm=True
            )
        assert result["status"] == "unconfirmed"
        assert result["warnings"]

    @pytest.mark.asyncio
    async def test_stored_members_differing_from_request_warns(
        self, local_settings: MagicMock
    ) -> None:
        client = _mock_client(get_response={"data": []})
        client.post.return_value = {"data": [_tag(members=[MAC_A])]}
        with _patch_client(client):
            result = await mt.create_mac_tag(
                "Lobby APs", [MAC_A, MAC_B], "default", local_settings, confirm=True
            )
        assert any(MAC_B in w for w in result["warnings"])


# --------------------------------------------------------------------------- #
# Update                                                                      #
# --------------------------------------------------------------------------- #


class TestUpdateMacTag:
    @pytest.mark.asyncio
    async def test_requires_confirm(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": [_tag()]})
        with _patch_client(client), pytest.raises(ValueError, match="confirm=True"):
            await mt.update_mac_tag(TAG_ID, "default", local_settings, name="New")
        client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_requires_a_change(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValidationError, match="Nothing to update"):
            await mt.update_mac_tag(TAG_ID, "default", local_settings, confirm=True)

    @pytest.mark.asyncio
    async def test_replace_excludes_add_remove(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValidationError, match="macs"):
            await mt.update_mac_tag(
                TAG_ID, "default", local_settings, macs=[MAC_A], add_macs=[MAC_B], confirm=True
            )

    @pytest.mark.asyncio
    async def test_same_mac_in_add_and_remove_rejected(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValidationError, match="both"):
            await mt.update_mac_tag(
                TAG_ID,
                "default",
                local_settings,
                add_macs=[MAC_C],
                remove_macs=["AA-BB-CC-DD-EE-03"],
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_add_and_remove_members(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": [_tag()]})
        client.put.return_value = {"data": [_tag(members=[MAC_B, MAC_C])]}
        with _patch_client(client), patch("src.tools.mac_tags.log_audit") as audit:
            result = await mt.update_mac_tag(
                TAG_ID,
                "default",
                local_settings,
                add_macs=[MAC_C, MAC_B],
                remove_macs=[MAC_A],
                confirm=True,
            )

        payload = client.put.call_args.kwargs["json_data"]
        assert payload["member_table"] == [MAC_B, MAC_C]
        assert payload["name"] == "Lobby APs"
        assert "_id" not in payload and "site_id" not in payload
        assert client.put.call_args.args[0] == f"/ea/sites/default/rest/tag/{TAG_ID}"
        assert result["member_table"] == [MAC_B, MAC_C]
        assert "warnings" not in result
        audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_replace_members_and_rename(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": [_tag()]})
        client.put.return_value = {"data": [_tag(name="Renamed", members=[MAC_C])]}
        with _patch_client(client):
            await mt.update_mac_tag(
                TAG_ID, "default", local_settings, name="Renamed", macs=[MAC_C], confirm=True
            )
        payload = client.put.call_args.kwargs["json_data"]
        assert payload == {"name": "Renamed", "member_table": [MAC_C]}

    @pytest.mark.asyncio
    async def test_replace_with_empty_list_clears_members(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": [_tag()]})
        client.put.return_value = {"data": [_tag(members=[])]}
        with _patch_client(client):
            await mt.update_mac_tag(TAG_ID, "default", local_settings, macs=[], confirm=True)
        assert client.put.call_args.kwargs["json_data"]["member_table"] == []

    @pytest.mark.asyncio
    async def test_dry_run_shows_diff_and_sends_nothing(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": [_tag()]})
        with _patch_client(client):
            result = await mt.update_mac_tag(
                TAG_ID,
                "default",
                local_settings,
                add_macs=[MAC_C],
                remove_macs=[MAC_A],
                dry_run=True,
            )
        assert result["status"] == "dry_run"
        assert result["changes"]["added_macs"] == [MAC_C]
        assert result["changes"]["removed_macs"] == [MAC_A]
        assert result["merged_payload"]["member_table"] == [MAC_B, MAC_C]
        client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_removing_non_member_warns(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": [_tag()]})
        with _patch_client(client):
            result = await mt.update_mac_tag(
                TAG_ID, "default", local_settings, remove_macs=[MAC_C], dry_run=True
            )
        assert any(MAC_C in w and "not a member" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_rename_to_existing_name_rejected(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.get.side_effect = [
            {"data": [_tag()]},
            {"data": [_tag(), _tag(OTHER_TAG_ID, "Warehouse")]},
        ]
        with _patch_client(client), pytest.raises(DuplicateResourceError):
            await mt.update_mac_tag(
                TAG_ID, "default", local_settings, name="warehouse", confirm=True
            )
        client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_unechoed_update_rereads_tag(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.get.side_effect = [
            {"data": [_tag()]},
            {"data": [_tag(members=[MAC_A, MAC_B, MAC_C])]},
        ]
        client.put.return_value = {"data": []}
        with _patch_client(client):
            result = await mt.update_mac_tag(
                TAG_ID, "default", local_settings, add_macs=[MAC_C], confirm=True
            )
        assert result["member_table"] == [MAC_A, MAC_B, MAC_C]
        assert "warnings" not in result

    @pytest.mark.asyncio
    async def test_stored_members_differing_from_request_warns(
        self, local_settings: MagicMock
    ) -> None:
        client = _mock_client(get_response={"data": [_tag()]})
        client.put.return_value = {"data": [_tag()]}  # controller ignored the add
        with _patch_client(client):
            result = await mt.update_mac_tag(
                TAG_ID, "default", local_settings, add_macs=[MAC_C], confirm=True
            )
        assert any(MAC_C in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_missing_tag_is_not_found(self, local_settings: MagicMock) -> None:
        client = _mock_client(get_response={"data": []})
        with _patch_client(client), pytest.raises(ResourceNotFoundError):
            await mt.update_mac_tag(TAG_ID, "default", local_settings, name="x", confirm=True)
        client.put.assert_not_called()


# --------------------------------------------------------------------------- #
# Delete                                                                      #
# --------------------------------------------------------------------------- #


class TestDeleteMacTag:
    @pytest.mark.asyncio
    async def test_requires_confirm(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch_client(client), pytest.raises(ValueError, match="confirm=True"):
            await mt.delete_mac_tag(TAG_ID, "default", local_settings)
        client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch_client(client):
            result = await mt.delete_mac_tag(TAG_ID, "default", local_settings, dry_run=True)
        assert result == {"status": "dry_run", "tag_id": TAG_ID, "action": "would_delete"}
        client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch_client(client), patch("src.tools.mac_tags.log_audit") as audit:
            result = await mt.delete_mac_tag(TAG_ID, "default", local_settings, confirm=True)
        assert result == {"status": "success", "tag_id": TAG_ID, "action": "deleted"}
        assert client.delete.call_args.args[0] == f"/ea/sites/default/rest/tag/{TAG_ID}"
        audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_tag_is_not_found(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.delete.side_effect = ResourceNotFoundError("endpoint", "x")
        with _patch_client(client), pytest.raises(ResourceNotFoundError, match=TAG_ID):
            await mt.delete_mac_tag(TAG_ID, "default", local_settings, confirm=True)


class TestRegistration:
    def test_write_tools_are_classified_mutating(self) -> None:
        from src.tool_registry import is_mutating_tool

        assert not is_mutating_tool(mt.list_mac_tags)
        assert not is_mutating_tool(mt.get_mac_tag)
        for fn in (mt.create_mac_tag, mt.update_mac_tag, mt.delete_mac_tag):
            assert is_mutating_tool(fn)
