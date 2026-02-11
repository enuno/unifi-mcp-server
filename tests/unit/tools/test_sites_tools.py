"""Unit tests for src/tools/sites.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.sites import get_site_details, get_site_statistics, list_sites
from src.utils.exceptions import ResourceNotFoundError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "cloud-ea"
    settings.base_url = "https://api.ui.com"
    settings.api_key = "test-key"
    settings.get_integration_path = MagicMock(return_value="/integration/v1/sites")
    return settings


@pytest.fixture
def mock_local_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "local"
    settings.base_url = "https://192.168.2.1:443"
    settings.api_key = "test-key"
    settings.get_integration_path = MagicMock(return_value="/proxy/network/integration/v1/sites")
    return settings


def create_mock_client(mock_response):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.authenticate = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    # IMPORTANT: return_value=False ensures exceptions are NOT suppressed
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestGetSiteDetails:
    @pytest.mark.asyncio
    async def test_get_site_details_success_by_id(self, mock_settings):
        mock_response = [
            {"_id": "site-123", "name": "Default", "desc": "Main site"},
            {"_id": "site-456", "name": "Branch", "desc": "Branch Office"},
        ]

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await get_site_details("site-123", mock_settings)

            assert result["id"] == "site-123"
            assert result["name"] == "Default"

    @pytest.mark.asyncio
    async def test_get_site_details_success_by_name(self, mock_settings):
        mock_response = [
            {"_id": "site-123", "name": "Default", "desc": "Main site"},
        ]

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await get_site_details("Default", mock_settings)

            assert result["id"] == "site-123"
            assert result["name"] == "Default"

    @pytest.mark.asyncio
    async def test_get_site_details_dict_response(self, mock_settings):
        mock_response = {
            "data": [
                {"_id": "site-123", "name": "Default", "desc": "Main site"},
            ]
        }

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await get_site_details("site-123", mock_settings)

            assert result["id"] == "site-123"

    @pytest.mark.asyncio
    async def test_get_site_details_not_found(self, mock_settings):
        mock_response = [
            {"_id": "site-abc", "name": "OtherSite", "desc": "Another site"},
        ]

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            with pytest.raises(ResourceNotFoundError):
                await get_site_details("nonexistent-site", mock_settings)


class TestListSites:
    @pytest.mark.asyncio
    async def test_list_sites_success(self, mock_settings):
        mock_response = [
            {"_id": "site-1", "name": "Site1", "desc": "First"},
            {"_id": "site-2", "name": "Site2", "desc": "Second"},
        ]

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_sites(mock_settings)

            assert len(result) == 2
            assert result[0]["name"] == "Site1"
            assert result[1]["name"] == "Site2"

    @pytest.mark.asyncio
    async def test_list_sites_with_dict_response(self, mock_settings):
        mock_response = {
            "data": [
                {"_id": "site-1", "name": "Site1", "desc": "First"},
            ]
        }

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_sites(mock_settings)

            assert len(result) == 1
            assert result[0]["id"] == "site-1"

    @pytest.mark.asyncio
    async def test_list_sites_with_limit(self, mock_settings):
        mock_response = [
            {"_id": f"site-{i}", "name": f"Site{i}", "desc": f"Site {i}"} for i in range(10)
        ]

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_sites(mock_settings, limit=3)

            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_sites_with_offset(self, mock_settings):
        mock_response = [
            {"_id": "site-0", "name": "Site0", "desc": "First"},
            {"_id": "site-1", "name": "Site1", "desc": "Second"},
            {"_id": "site-2", "name": "Site2", "desc": "Third"},
        ]

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_sites(mock_settings, offset=1, limit=2)

            assert len(result) == 2
            assert result[0]["id"] == "site-1"

    @pytest.mark.asyncio
    async def test_list_sites_local_api(self, mock_local_settings):
        mock_response = [
            {"_id": "local-site", "name": "LocalSite", "desc": "Local gateway site"},
        ]

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_sites(mock_local_settings)

            assert len(result) == 1
            mock_local_settings.get_integration_path.assert_called_with("sites")

    @pytest.mark.asyncio
    async def test_list_sites_empty(self, mock_settings):
        mock_response = []

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            result = await list_sites(mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_sites_context_enter_error(self, mock_settings):
        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(side_effect=Exception("Connection Error"))
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await list_sites(mock_settings)

            assert "Connection Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_sites_parse_error(self, mock_settings):
        mock_response = [
            {"invalid_field_only": "no _id or name"},
        ]

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(mock_response)

            with pytest.raises((Exception, ValueError, KeyError)):  # noqa: B017
                await list_sites(mock_settings)


class TestGetSiteStatistics:
    @pytest.mark.asyncio
    async def test_get_site_statistics_success(self, mock_settings):
        devices_response = [
            {"_id": "ap1", "type": "uap", "state": 1},
            {"_id": "sw1", "type": "usw", "state": 1},
            {"_id": "gw1", "type": "ugw", "state": 1},
            {"_id": "ap2", "type": "uap", "state": 0},
        ]
        clients_response = [
            {"mac": "aa:bb:cc:dd:ee:ff", "is_wired": True, "tx_bytes": 1000, "rx_bytes": 2000},
            {"mac": "11:22:33:44:55:66", "is_wired": False, "tx_bytes": 500, "rx_bytes": 1500},
        ]
        networks_response = [
            {"_id": "net1", "name": "LAN"},
            {"_id": "net2", "name": "Guest"},
        ]

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=[devices_response, clients_response, networks_response]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await get_site_statistics("default", mock_settings)

            assert result["site_id"] == "default"
            assert result["devices"]["total"] == 4
            assert result["devices"]["online"] == 3
            assert result["devices"]["offline"] == 1
            assert result["devices"]["access_points"] == 2
            assert result["devices"]["switches"] == 1
            assert result["devices"]["gateways"] == 1
            assert result["clients"]["total"] == 2
            assert result["clients"]["wired"] == 1
            assert result["clients"]["wireless"] == 1
            assert result["networks"]["total"] == 2
            assert result["bandwidth"]["total_tx_bytes"] == 1500
            assert result["bandwidth"]["total_rx_bytes"] == 3500
            assert result["bandwidth"]["total_bytes"] == 5000

    @pytest.mark.asyncio
    async def test_get_site_statistics_with_dict_responses(self, mock_settings):
        devices_response = {"data": [{"_id": "ap1", "type": "uap", "state": 1}]}
        clients_response = {
            "data": [
                {"mac": "aa:bb:cc:dd:ee:ff", "is_wired": False, "tx_bytes": 100, "rx_bytes": 200}
            ]
        }
        networks_response = {"data": [{"_id": "net1", "name": "LAN"}]}

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=[devices_response, clients_response, networks_response]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await get_site_statistics("default", mock_settings)

            assert result["devices"]["total"] == 1
            assert result["clients"]["total"] == 1
            assert result["networks"]["total"] == 1

    @pytest.mark.asyncio
    async def test_get_site_statistics_udm_gateway(self, mock_settings):
        devices_response = [
            {"_id": "udm1", "type": "udm", "state": 1},
        ]
        clients_response = []
        networks_response = []

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=[devices_response, clients_response, networks_response]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await get_site_statistics("default", mock_settings)

            assert result["devices"]["gateways"] == 1

    @pytest.mark.asyncio
    async def test_get_site_statistics_uxg_gateway(self, mock_settings):
        devices_response = [
            {"_id": "uxg1", "type": "uxg", "state": 1},
        ]
        clients_response = []
        networks_response = []

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=[devices_response, clients_response, networks_response]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await get_site_statistics("default", mock_settings)

            assert result["devices"]["gateways"] == 1

    @pytest.mark.asyncio
    async def test_get_site_statistics_empty(self, mock_settings):
        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[[], [], []])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await get_site_statistics("default", mock_settings)

            assert result["devices"]["total"] == 0
            assert result["clients"]["total"] == 0
            assert result["networks"]["total"] == 0
            assert result["bandwidth"]["total_bytes"] == 0

    @pytest.mark.asyncio
    async def test_get_site_statistics_missing_bytes(self, mock_settings):
        devices_response = []
        clients_response = [
            {"mac": "aa:bb:cc:dd:ee:ff", "is_wired": True},
        ]
        networks_response = []

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=[devices_response, clients_response, networks_response]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await get_site_statistics("default", mock_settings)

            assert result["bandwidth"]["total_tx_bytes"] == 0
            assert result["bandwidth"]["total_rx_bytes"] == 0
