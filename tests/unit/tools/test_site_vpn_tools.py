"""Unit tests for src/tools/site_vpn.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.site_vpn import get_site_to_site_vpn, list_site_to_site_vpns, update_site_to_site_vpn
from src.utils import ResourceNotFoundError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    return settings


def make_vpn(vpn_id="vpn-1", name="Office VPN"):
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
        assert result[0]["id"] == "vpn-1"

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
                "default", "vpn-1", mock_settings, name="New Name", dry_run=True
            )
        assert result["dry_run"] is True
        mock_client.put.assert_not_called()

    async def test_requires_confirm(self, mock_settings):
        vpn = make_vpn()
        mock_client = create_mock_client(vpn)
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            result = await update_site_to_site_vpn(
                "default", "vpn-1", mock_settings, name="New Name", confirm=False
            )
        assert "error" in result
        mock_client.put.assert_not_called()

    async def test_updates_with_confirm(self, mock_settings):
        vpn = make_vpn()
        mock_client = create_mock_client(vpn)
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            result = await update_site_to_site_vpn(
                "default", "vpn-1", mock_settings, name="New Name", confirm=True
            )
        assert result["success"] is True
        mock_client.put.assert_called_once()

    async def test_raises_not_found_when_not_site_vpn(self, mock_settings):
        corporate = {**make_vpn("net-1"), "purpose": "corporate"}
        mock_client = create_mock_client(corporate)
        with patch("src.tools.site_vpn.UniFiClient", return_value=mock_client):
            with pytest.raises(ResourceNotFoundError):
                await update_site_to_site_vpn("default", "net-1", mock_settings, confirm=True)
