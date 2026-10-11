"""Unit tests for dns_management tools.

WAN DNS lives on ``/ea/sites/{site}/rest/networkconf`` and DNS filtering on
the ``[ips]`` settings endpoint; both are legacy V1 internal endpoints, so
every tool is gated on ``UNIFI_API_TYPE=local``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import APIType, Settings
from src.tools import dns_management as dm
from src.utils.exceptions import APIError

WAN_ID = "5f1e2d3c4b5a697886950401"
LAN_ID = "5f1e2d3c4b5a697886950402"
IPS_ID = "5f1e2d3c4b5a697886950403"


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


def _mock_client(get_response: Any = None, put_response: Any = None) -> AsyncMock:
    client = AsyncMock()
    client.is_authenticated = True
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value=get_response)
    client.put = AsyncMock(return_value=put_response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _patch_client(client: AsyncMock):
    return patch("src.tools.dns_management.UniFiClient", return_value=client)


def _wan(**overrides: Any) -> dict[str, Any]:
    return {
        "_id": WAN_ID,
        "name": "Internet 1",
        "purpose": "wan",
        "wan_dns1": "1.1.1.1",
        "wan_dns2": "1.0.0.1",
        "wan_dns_preference": "manual",
        "wan_type": "dhcp",
        "wan_networkgroup": "WAN",
        **overrides,
    }


def _ips(dns_filters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"_id": IPS_ID, "dns_filtering": True, "dns_filters": dns_filters or []}


class TestUnwrap:
    def test_list_drops_non_dicts(self) -> None:
        assert dm._unwrap([{"a": 1}, "x", None]) == [{"a": 1}]

    def test_data_list(self) -> None:
        assert dm._unwrap({"data": [{"a": 1}, 2]}) == [{"a": 1}]

    def test_data_dict(self) -> None:
        assert dm._unwrap({"data": {"a": 1}}) == [{"a": 1}]

    @pytest.mark.parametrize("response", [None, "x", {"data": "x"}, {}])
    def test_unrecognised_shapes(self, response: Any) -> None:
        assert dm._unwrap(response) == []


class TestLocalApiGate:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "call",
        [
            lambda s: dm.list_wan_dns("default", s),
            lambda s: dm.update_wan_dns(WAN_ID, "default", s, dns1="1.1.1.1", confirm=True),
            lambda s: dm.get_dns_filter_settings("default", s),
            lambda s: dm.update_dns_filter("default", s, dns_filtering=True, confirm=True),
        ],
    )
    async def test_rejects_cloud(self, cloud_settings: MagicMock, call: Any) -> None:
        with pytest.raises(NotImplementedError, match="UNIFI_API_TYPE='local'"):
            await call(cloud_settings)


class TestListWanDns:
    @pytest.mark.asyncio
    async def test_returns_only_wans(self, local_settings: MagicMock) -> None:
        client = _mock_client({"data": [_wan(), {"_id": LAN_ID, "purpose": "corporate"}]})
        with _patch_client(client):
            result = await dm.list_wan_dns("default", local_settings)

        client.get.assert_awaited_once_with("/ea/sites/default/rest/networkconf")
        assert result == [
            {
                "id": WAN_ID,
                "name": "Internet 1",
                "wan_dns1": "1.1.1.1",
                "wan_dns2": "1.0.0.1",
                "wan_dns_preference": "manual",
                "wan_type": "dhcp",
                "wan_networkgroup": "WAN",
            }
        ]

    @pytest.mark.asyncio
    async def test_preference_defaults_to_auto(self, local_settings: MagicMock) -> None:
        wan = _wan()
        del wan["wan_dns_preference"]
        client = _mock_client([wan])
        with _patch_client(client):
            result = await dm.list_wan_dns("default", local_settings)

        assert result[0]["wan_dns_preference"] == "auto"

    @pytest.mark.asyncio
    async def test_authenticates_when_needed(self, local_settings: MagicMock) -> None:
        client = _mock_client([])
        client.is_authenticated = False
        with _patch_client(client):
            assert await dm.list_wan_dns("default", local_settings) == []

        client.authenticate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_api_error_propagates(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.get.side_effect = APIError("boom")
        with _patch_client(client), pytest.raises(APIError):
            await dm.list_wan_dns("default", local_settings)


class TestUpdateWanDns:
    @pytest.mark.asyncio
    async def test_requires_confirm(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValueError, match="confirm=True"):
            await dm.update_wan_dns(WAN_ID, "default", local_settings, dns1="1.1.1.1")

    @pytest.mark.asyncio
    async def test_rejects_bad_preference(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValueError, match="'auto' or 'manual'"):
            await dm.update_wan_dns(
                WAN_ID, "default", local_settings, dns_preference="static", confirm=True
            )

    @pytest.mark.asyncio
    async def test_dry_run_infers_manual_and_skips_api(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        with _patch_client(client):
            result = await dm.update_wan_dns(
                WAN_ID,
                "default",
                local_settings,
                dns1="9.9.9.9",
                dns2="149.112.112.112",
                dry_run="true",
            )

        assert result == {
            "status": "dry_run",
            "wan_network_id": WAN_ID,
            "changes": {
                "wan_dns1": "9.9.9.9",
                "wan_dns2": "149.112.112.112",
                "wan_dns_preference": "manual",
            },
        }
        client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_explicit_preference_wins(self, local_settings: MagicMock) -> None:
        result = await dm.update_wan_dns(
            WAN_ID, "default", local_settings, dns1="9.9.9.9", dns_preference="auto", dry_run=True
        )

        assert result["changes"]["wan_dns_preference"] == "auto"

    @pytest.mark.asyncio
    async def test_applies_and_audits(self, local_settings: MagicMock) -> None:
        client = _mock_client(put_response={"data": [_wan(wan_dns1="9.9.9.9")]})
        with _patch_client(client), patch("src.tools.dns_management.log_audit") as audit:
            result = await dm.update_wan_dns(
                WAN_ID, "default", local_settings, dns1="9.9.9.9", confirm=True
            )

        client.put.assert_awaited_once_with(
            f"/ea/sites/default/rest/networkconf/{WAN_ID}",
            json_data={"wan_dns1": "9.9.9.9", "wan_dns_preference": "manual"},
        )
        assert result["wan_dns1"] == "9.9.9.9"
        assert result["id"] == WAN_ID
        audit.assert_called_once()
        assert audit.call_args.kwargs["operation"] == "update_wan_dns"

    @pytest.mark.asyncio
    async def test_empty_response(self, local_settings: MagicMock) -> None:
        client = _mock_client(put_response={})
        with _patch_client(client), patch("src.tools.dns_management.log_audit"):
            result = await dm.update_wan_dns(
                WAN_ID, "default", local_settings, dns_preference="auto", confirm=True
            )

        assert result["id"] is None

    @pytest.mark.asyncio
    async def test_api_error_propagates_without_audit(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.put.side_effect = APIError("boom")
        with (
            _patch_client(client),
            patch("src.tools.dns_management.log_audit") as audit,
            pytest.raises(APIError),
        ):
            await dm.update_wan_dns(WAN_ID, "default", local_settings, dns1="9.9.9.9", confirm=True)

        audit.assert_not_called()


class TestGetDnsFilterSettings:
    @pytest.mark.asyncio
    async def test_returns_settings(self, local_settings: MagicMock) -> None:
        filters = [{"network_id": LAN_ID, "filter": "family"}]
        client = _mock_client({"data": [_ips(filters)]})
        with _patch_client(client):
            result = await dm.get_dns_filter_settings("default", local_settings)

        client.get.assert_awaited_once_with("/ea/sites/default/get/setting/ips")
        assert result == {"id": IPS_ID, "dns_filtering": True, "dns_filters": filters}

    @pytest.mark.asyncio
    async def test_missing_settings_default_off(self, local_settings: MagicMock) -> None:
        client = _mock_client({"data": []})
        with _patch_client(client):
            result = await dm.get_dns_filter_settings("default", local_settings)

        assert result == {"dns_filtering": False, "dns_filters": []}

    @pytest.mark.asyncio
    async def test_api_error_propagates(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.get.side_effect = APIError("boom")
        with _patch_client(client), pytest.raises(APIError):
            await dm.get_dns_filter_settings("default", local_settings)


class TestUpdateDnsFilter:
    @pytest.mark.asyncio
    async def test_requires_confirm(self, local_settings: MagicMock) -> None:
        with pytest.raises(ValueError, match="confirm=True"):
            await dm.update_dns_filter("default", local_settings, dns_filtering=True)

    @pytest.mark.asyncio
    async def test_missing_settings_raises(self, local_settings: MagicMock) -> None:
        client = _mock_client({"data": []})
        with _patch_client(client), pytest.raises(APIError, match="IPS settings not found"):
            await dm.update_dns_filter("default", local_settings, dns_filtering=True, confirm=True)

    @pytest.mark.asyncio
    async def test_get_error_propagates(self, local_settings: MagicMock) -> None:
        client = _mock_client()
        client.get.side_effect = APIError("boom")
        with _patch_client(client), pytest.raises(APIError):
            await dm.update_dns_filter("default", local_settings, dns_filtering=True, confirm=True)

    @pytest.mark.asyncio
    async def test_dry_run_updates_existing_entry(self, local_settings: MagicMock) -> None:
        existing = {"network_id": LAN_ID, "filter": "none", "blocked_sites": ["a.example"]}
        client = _mock_client({"data": [_ips([existing])]})
        with _patch_client(client):
            result = await dm.update_dns_filter(
                "default",
                local_settings,
                network_id=LAN_ID,
                filter_level="family",
                blocked_sites=["b.example"],
                allowed_sites=["c.example"],
                blocked_tld=["zip"],
                dry_run=True,
            )

        assert result["status"] == "dry_run"
        assert result["settings_id"] == IPS_ID
        assert result["changes"] == {
            "dns_filters": [
                {
                    "network_id": LAN_ID,
                    "filter": "family",
                    "blocked_sites": ["b.example"],
                    "allowed_sites": ["c.example"],
                    "blocked_tld": ["zip"],
                }
            ]
        }
        client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_entry_for_new_network(self, local_settings: MagicMock) -> None:
        other = {"network_id": "other", "filter": "work"}
        client = _mock_client({"data": [_ips([other])]})
        with _patch_client(client):
            result = await dm.update_dns_filter(
                "default", local_settings, network_id=LAN_ID, filter_level="work", dry_run=True
            )

        filters = result["changes"]["dns_filters"]
        assert filters[0] == other
        assert filters[1]["network_id"] == LAN_ID
        assert filters[1]["filter"] == "work"
        assert filters[1]["blocked_sites"] == []
        assert filters[1]["version"] == "v4"

    @pytest.mark.asyncio
    async def test_network_without_filter_fields_is_ignored(
        self, local_settings: MagicMock
    ) -> None:
        client = _mock_client({"data": [_ips()]})
        with _patch_client(client):
            result = await dm.update_dns_filter(
                "default", local_settings, network_id=LAN_ID, dns_filtering=False, dry_run=True
            )

        assert result["changes"] == {"dns_filtering": False}

    @pytest.mark.asyncio
    async def test_applies_and_audits(self, local_settings: MagicMock) -> None:
        updated = _ips()
        updated["dns_filtering"] = False
        client = _mock_client({"data": [_ips()]}, put_response={"data": [updated]})
        with _patch_client(client), patch("src.tools.dns_management.log_audit") as audit:
            result = await dm.update_dns_filter(
                "default", local_settings, dns_filtering=False, confirm=True
            )

        client.put.assert_awaited_once_with(
            f"/ea/sites/default/set/setting/ips/{IPS_ID}",
            json_data={"dns_filtering": False},
        )
        assert result == {"id": IPS_ID, "dns_filtering": False, "dns_filters": []}
        audit.assert_called_once()
        assert audit.call_args.kwargs["operation"] == "update_dns_filter"

    @pytest.mark.asyncio
    async def test_put_error_propagates_without_audit(self, local_settings: MagicMock) -> None:
        client = _mock_client({"data": [_ips()]})
        client.put.side_effect = APIError("boom")
        with (
            _patch_client(client),
            patch("src.tools.dns_management.log_audit") as audit,
            pytest.raises(APIError),
        ):
            await dm.update_dns_filter("default", local_settings, dns_filtering=True, confirm=True)

        audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_put_response(self, local_settings: MagicMock) -> None:
        client = _mock_client({"data": [_ips()]}, put_response=None)
        with _patch_client(client), patch("src.tools.dns_management.log_audit"):
            result = await dm.update_dns_filter(
                "default", local_settings, dns_filtering=True, confirm=True
            )

        assert result == {"id": None, "dns_filtering": None, "dns_filters": []}
