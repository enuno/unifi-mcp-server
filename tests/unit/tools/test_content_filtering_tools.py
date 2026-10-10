"""Unit tests for content_filtering tools.

Profiles live at the local v2 endpoint
``/proxy/network/v2/api/site/{site}/content-filtering``. The endpoint has no
single-item GET and no POST, so update is list -> merge -> PUT, and every tool
is gated on ``UNIFI_API_TYPE=local``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import APIType, Settings
from src.tools import content_filtering as cf
from src.utils.exceptions import APIError, ResourceNotFoundError

FILTER_ID = "65a1b2c3d4e5f60718293a4b"
SITE_UUID = "88f7af54-98f8-306a-a1c7-c9349722b1f6"
V2 = "/proxy/network/v2/api/site"


@pytest.fixture
def local_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.api_type = APIType.LOCAL
    settings.api_key = "test-api-key"  # pragma: allowlist secret
    settings.local_host = "192.0.2.1"
    settings.log_level = "INFO"
    settings.get_v2_api_path.side_effect = lambda site: f"{V2}/{site}"
    return settings


@pytest.fixture
def cloud_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.api_type = APIType.CLOUD_V1
    settings.api_key = "test-api-key"  # pragma: allowlist secret
    settings.log_level = "INFO"
    return settings


def _mock_client(get_response: Any = None, put_response: Any = None) -> AsyncMock:
    client = AsyncMock()
    client.is_authenticated = True
    client.authenticate = AsyncMock()
    client._site_uuid_to_name = {}
    client.get = AsyncMock(return_value=get_response)
    client.put = AsyncMock(return_value=put_response)
    client.delete = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _patch_client(client: AsyncMock):
    return patch("src.tools.content_filtering.UniFiClient", return_value=client)


def _profile(**overrides: Any) -> dict[str, Any]:
    return {
        "_id": FILTER_ID,
        "name": "Kids",
        "enabled": True,
        "categories": ["GAMBLING"],
        "network_ids": ["net-1"],
        "client_macs": [],
        "allow_list": [],
        "block_list": ["bad.example"],
        "safe_search": ["GOOGLE"],
        "schedule": {"mode": "ALWAYS"},
        **overrides,
    }


class TestLocalApiGate:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "call",
        [
            lambda s: cf.list_content_filters("default", s),
            lambda s: cf.list_content_filter_categories("default", s),
            lambda s: cf.update_content_filter(FILTER_ID, "default", s, enabled=True, confirm=True),
            lambda s: cf.delete_content_filter(FILTER_ID, "default", s, confirm=True),
        ],
    )
    async def test_rejects_cloud(self, cloud_settings: MagicMock, call: Any) -> None:
        with pytest.raises(NotImplementedError, match="UNIFI_API_TYPE='local'"):
            await call(cloud_settings)


class TestNormalize:
    def test_defaults(self) -> None:
        assert cf._normalize({}) == {
            "id": None,
            "name": None,
            "enabled": False,
            "categories": [],
            "network_ids": [],
            "client_macs": [],
            "allow_list": [],
            "block_list": [],
            "safe_search": [],
            "schedule": None,
        }


class TestListContentFilters:
    @pytest.mark.asyncio
    async def test_list_response(self, local_settings: MagicMock) -> None:
        client = _mock_client([_profile(), "junk"])
        with _patch_client(client):
            result = await cf.list_content_filters("default", local_settings)

        client.get.assert_awaited_once_with(f"{V2}/default/content-filtering")
        assert len(result) == 1
        assert result[0]["id"] == FILTER_ID
        assert result[0]["categories"] == ["GAMBLING"]

    @pytest.mark.asyncio
    async def test_data_envelope_and_uuid_mapping(self, local_settings: MagicMock) -> None:
        client = _mock_client({"data": [_profile()]})
        client._site_uuid_to_name = {SITE_UUID: "default"}
        client.is_authenticated = False
        with _patch_client(client):
            result = await cf.list_content_filters(SITE_UUID, local_settings)

        client.authenticate.assert_awaited_once()
        client.get.assert_awaited_once_with(f"{V2}/default/content-filtering")
        assert result[0]["name"] == "Kids"

    @pytest.mark.asyncio
    async def test_api_error_propagates(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.get.side_effect = APIError("boom")
        with _patch_client(client), pytest.raises(APIError):
            await cf.list_content_filters("default", local_settings)


class TestListCategories:
    @pytest.mark.asyncio
    async def test_returns_strings_only(self, local_settings: MagicMock) -> None:
        client = _mock_client(["ADULT", "GAMBLING", 3])
        with _patch_client(client):
            result = await cf.list_content_filter_categories("default", local_settings)

        client.get.assert_awaited_once_with(f"{V2}/default/content-filtering/categories")
        assert result == ["ADULT", "GAMBLING"]

    @pytest.mark.asyncio
    async def test_non_list_response(self, local_settings: MagicMock) -> None:
        client = _mock_client({"data": []})
        with _patch_client(client):
            assert await cf.list_content_filter_categories("default", local_settings) == []

    @pytest.mark.asyncio
    async def test_api_error_propagates(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.get.side_effect = APIError("boom")
        with _patch_client(client), pytest.raises(APIError):
            await cf.list_content_filter_categories("default", local_settings)


class TestUpdateContentFilter:
    @pytest.mark.asyncio
    async def test_requires_confirm(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValueError, match="confirm=True"):
            await cf.update_content_filter(FILTER_ID, "default", local_settings, enabled=False)

    @pytest.mark.asyncio
    async def test_not_found(self, local_settings: MagicMock) -> None:
        client = _mock_client([_profile(_id="other")])
        with _patch_client(client), pytest.raises(ResourceNotFoundError):
            await cf.update_content_filter(
                FILTER_ID, "default", local_settings, enabled=False, confirm=True
            )

    @pytest.mark.asyncio
    async def test_fetch_error_propagates(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.get.side_effect = APIError("boom")
        with _patch_client(client), pytest.raises(APIError):
            await cf.update_content_filter(
                FILTER_ID, "default", local_settings, enabled=False, confirm=True
            )

    @pytest.mark.asyncio
    async def test_dry_run_merges_all_fields(self, local_settings: MagicMock) -> None:
        client = _mock_client({"data": [_profile()]})
        with _patch_client(client):
            result = await cf.update_content_filter(
                FILTER_ID,
                "default",
                local_settings,
                name="Teens",
                enabled=False,
                categories=("ADULT",),
                network_ids=[],
                client_macs=["aa:bb:cc:dd:ee:ff"],
                allow_list=["ok.example"],
                block_list=[],
                safe_search=["BING"],
                dry_run=True,
            )

        assert result["status"] == "dry_run"
        assert result["changes"] == {
            "name": "Teens",
            "enabled": False,
            "categories": ["ADULT"],
            "network_ids": [],
            "client_macs": ["aa:bb:cc:dd:ee:ff"],
            "allow_list": ["ok.example"],
            "block_list": [],
            "safe_search": ["BING"],
        }
        merged = result["merged_payload"]
        assert "_id" not in merged
        assert merged["schedule"] == {"mode": "ALWAYS"}
        assert merged["name"] == "Teens"
        client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_applies_full_object_and_audits(self, local_settings: MagicMock) -> None:
        client = _mock_client([_profile()], put_response=_profile(enabled=False))
        with _patch_client(client), patch("src.tools.content_filtering.log_audit") as audit:
            result = await cf.update_content_filter(
                FILTER_ID, "default", local_settings, enabled=False, confirm=True
            )

        url, kwargs = client.put.await_args.args[0], client.put.await_args.kwargs
        assert url == f"{V2}/default/content-filtering/{FILTER_ID}"
        expected = _profile(enabled=False)
        del expected["_id"]
        assert kwargs["json_data"] == expected
        assert result["enabled"] is False
        audit.assert_called_once()
        assert audit.call_args.kwargs["operation"] == "update_content_filter"

    @pytest.mark.asyncio
    async def test_non_dict_put_response(self, local_settings: MagicMock) -> None:
        client = _mock_client([_profile()], put_response=[])
        with _patch_client(client), patch("src.tools.content_filtering.log_audit"):
            result = await cf.update_content_filter(
                FILTER_ID, "default", local_settings, enabled=True, confirm=True
            )

        assert result["id"] is None

    @pytest.mark.asyncio
    async def test_put_not_found_is_rewrapped(self, local_settings: MagicMock) -> None:
        client = _mock_client([_profile()])
        client.put.side_effect = ResourceNotFoundError("resource", "x")
        with (
            _patch_client(client),
            patch("src.tools.content_filtering.log_audit") as audit,
            pytest.raises(ResourceNotFoundError, match=FILTER_ID),
        ):
            await cf.update_content_filter(
                FILTER_ID, "default", local_settings, enabled=True, confirm=True
            )

        audit.assert_not_called()


class TestDeleteContentFilter:
    @pytest.mark.asyncio
    async def test_requires_confirm(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValueError, match="confirm=True"):
            await cf.delete_content_filter(FILTER_ID, "default", local_settings)

    @pytest.mark.asyncio
    async def test_dry_run_skips_api(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch_client(client):
            result = await cf.delete_content_filter(
                FILTER_ID, "default", local_settings, dry_run=True
            )

        assert result == {"status": "dry_run", "filter_id": FILTER_ID, "action": "would_delete"}
        client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes_and_audits(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.is_authenticated = False
        with _patch_client(client), patch("src.tools.content_filtering.log_audit") as audit:
            result = await cf.delete_content_filter(
                FILTER_ID, "default", local_settings, confirm=True
            )

        client.authenticate.assert_awaited_once()
        client.delete.assert_awaited_once_with(f"{V2}/default/content-filtering/{FILTER_ID}")
        assert result == {"status": "success", "filter_id": FILTER_ID, "action": "deleted"}
        audit.assert_called_once()
        assert audit.call_args.kwargs["operation"] == "delete_content_filter"

    @pytest.mark.asyncio
    async def test_api_error_propagates_without_audit(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.delete.side_effect = APIError("boom")
        with (
            _patch_client(client),
            patch("src.tools.content_filtering.log_audit") as audit,
            pytest.raises(APIError),
        ):
            await cf.delete_content_filter(FILTER_ID, "default", local_settings, confirm=True)

        audit.assert_not_called()
