"""Unit tests for src/tools/site_vpn.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.site_vpn import get_site_to_site_vpn, list_site_to_site_vpns, update_site_to_site_vpn
from src.utils import ResourceNotFoundError, ValidationError

VPN_ID = "5f1a2b3c4d5e6f7a8b9c0d1e"
NET_ID = "5f1a2b3c4d5e6f7a8b9c0d2f"


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    return settings


def make_vpn(vpn_id=VPN_ID, name="Office VPN"):
    return {
        "_id": vpn_id,
        "name": name,
        "purpose": "site-vpn",
        "enabled": True,
        "vpn_type": "ipsec-vpn",
    }


def create_mock_client(get_response=None, put_response=None):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=get_response if get_response is not None else [])
    mock_client.put = AsyncMock(return_value=put_response or {})
    mock_client.authenticate = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestListSiteToSiteVpns:
    async def test_returns_only_site_vpn_purpose(self, mock_settings):
        vpn = make_vpn()
        other = {**make_vpn("net-2"), "purpose": "corporate"}
        mock_client = create_mock_client([vpn, other])
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            result = await list_site_to_site_vpns("default", mock_settings)
        assert len(result) == 1
        assert result[0]["id"] == VPN_ID

    async def test_handles_dict_response(self, mock_settings):
        vpn = make_vpn()
        mock_client = create_mock_client({"data": [vpn]})
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            result = await list_site_to_site_vpns("default", mock_settings)
        assert len(result) == 1

    async def test_empty_response(self, mock_settings):
        mock_client = create_mock_client([])
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            result = await list_site_to_site_vpns("default", mock_settings)
        assert result == []


class TestGetSiteToSiteVpn:
    async def test_returns_matching_vpn(self, mock_settings):
        vpn = make_vpn("vpn-99", "HQ Link")
        mock_client = create_mock_client([vpn])
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            result = await get_site_to_site_vpn("default", "vpn-99", mock_settings)
        assert result["name"] == "HQ Link"

    async def test_raises_not_found(self, mock_settings):
        mock_client = create_mock_client([])
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            with pytest.raises(ResourceNotFoundError):
                await get_site_to_site_vpn("default", "missing", mock_settings)

    async def test_ignores_non_vpn_networks(self, mock_settings):
        corporate = {**make_vpn("net-1"), "purpose": "corporate"}
        mock_client = create_mock_client([corporate])
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            with pytest.raises(ResourceNotFoundError):
                await get_site_to_site_vpn("default", "net-1", mock_settings)


class TestUpdateSiteToSiteVpn:
    async def test_dry_run_returns_without_calling_put(self, mock_settings):
        vpn = make_vpn()
        mock_client = create_mock_client(vpn)
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            result = await update_site_to_site_vpn(
                "default", VPN_ID, mock_settings, name="New Name", dry_run=True
            )
        assert result["dry_run"] is True
        mock_client.put.assert_not_called()

    async def test_requires_confirm(self, mock_settings):
        vpn = make_vpn()
        mock_client = create_mock_client(vpn)
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            result = await update_site_to_site_vpn(
                "default", VPN_ID, mock_settings, name="New Name", confirm=False
            )
        assert "error" in result
        mock_client.put.assert_not_called()

    async def test_updates_with_confirm(self, mock_settings):
        vpn = make_vpn()
        mock_client = create_mock_client(vpn)
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            result = await update_site_to_site_vpn(
                "default", VPN_ID, mock_settings, name="New Name", confirm=True
            )
        assert result["success"] is True
        mock_client.put.assert_called_once()

    async def test_raises_not_found_when_not_site_vpn(self, mock_settings):
        corporate = {**make_vpn(NET_ID), "purpose": "corporate"}
        mock_client = create_mock_client(corporate)
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            with pytest.raises(ResourceNotFoundError):
                await update_site_to_site_vpn("default", NET_ID, mock_settings, confirm=True)

    @pytest.mark.parametrize(
        "vpn_id",
        [
            "",
            "vpn-1",
            "../../../stat/device",
            f"{VPN_ID}/../{NET_ID}",
            f"{VPN_ID}?x=1",
            f"{VPN_ID}#frag",
            "%2e%2e",
        ],
    )
    async def test_rejects_invalid_vpn_id_before_any_request(self, mock_settings, vpn_id):
        mock_client = create_mock_client(make_vpn())
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            with pytest.raises(ValidationError, match="vpn_id"):
                await update_site_to_site_vpn(
                    "default", vpn_id, mock_settings, name="New Name", confirm=True
                )
        mock_client.get.assert_not_called()
        mock_client.put.assert_not_called()

    async def test_accepts_uppercase_object_id_and_lowercases_it(self, mock_settings):
        mock_client = create_mock_client(make_vpn())
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            result = await update_site_to_site_vpn(
                "default", VPN_ID.upper(), mock_settings, name="New Name", confirm=True
            )
        assert result["vpn_id"] == VPN_ID
        mock_client.get.assert_awaited_once_with(f"/ea/sites/default/rest/networkconf/{VPN_ID}")


class TestSiteIdTranslation:
    """site_vpn sends /ea/sites/{site_id}/... so the client maps a site UUID to its name."""

    SITE_UUID = "88f7af54-98f8-306a-a1c7-c9349722b1f6"

    async def test_list_uses_translatable_path(self, mock_settings):
        mock_client = create_mock_client([make_vpn()])
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            await list_site_to_site_vpns(self.SITE_UUID, mock_settings)
        mock_client.get.assert_awaited_once_with(f"/ea/sites/{self.SITE_UUID}/rest/networkconf")

    async def test_get_uses_translatable_path(self, mock_settings):
        mock_client = create_mock_client([make_vpn()])
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            await get_site_to_site_vpn(self.SITE_UUID, VPN_ID, mock_settings)
        mock_client.get.assert_awaited_once_with(f"/ea/sites/{self.SITE_UUID}/rest/networkconf")

    async def test_update_uses_translatable_paths(self, mock_settings):
        mock_client = create_mock_client(make_vpn())
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            await update_site_to_site_vpn(
                self.SITE_UUID, VPN_ID, mock_settings, name="New Name", confirm=True
            )
        path = f"/ea/sites/{self.SITE_UUID}/rest/networkconf/{VPN_ID}"
        mock_client.get.assert_awaited_once_with(path)
        assert mock_client.put.await_args.args[0] == path
