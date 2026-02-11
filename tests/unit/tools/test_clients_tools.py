"""Unit tests for src/tools/clients.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.clients import (
    get_client_details,
    get_client_statistics,
    list_active_clients,
    search_clients,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "cloud-ea"
    settings.base_url = "https://api.ui.com"
    settings.api_key = "test-key"
    return settings


def create_mock_client(get_responses=None):
    mock_client = AsyncMock()
    if get_responses:
        mock_client.get = AsyncMock(side_effect=get_responses)
    else:
        mock_client.get = AsyncMock(return_value={"data": []})
    mock_client.authenticate = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def make_client(
    mac="00:11:22:33:44:55",
    ip="192.168.2.100",
    hostname="test-client",
    name=None,
    is_wired=False,
):
    return {
        "mac": mac,
        "ip": ip,
        "hostname": hostname,
        "name": name or hostname,
        "is_wired": is_wired,
        "tx_bytes": 1000000,
        "rx_bytes": 2000000,
        "tx_packets": 1000,
        "rx_packets": 2000,
        "tx_rate": 100000,
        "rx_rate": 200000,
        "signal": -65,
        "rssi": 35,
        "noise": -95,
        "uptime": 3600,
    }


class TestGetClientDetails:
    @pytest.mark.asyncio
    async def test_get_client_details_found_in_active(self, mock_settings):
        mac = "00:11:22:33:44:55"
        active_response = {"data": [make_client(mac=mac)]}
        alluser_response = {"data": []}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await get_client_details("site-1", mac, mock_settings)

            assert result["mac"] == mac

    @pytest.mark.asyncio
    async def test_get_client_details_found_in_alluser(self, mock_settings):
        mac = "aa:bb:cc:dd:ee:ff"
        active_response = {"data": []}
        alluser_response = {"data": [make_client(mac=mac)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await get_client_details("site-1", mac, mock_settings)

            assert result["mac"] == mac

    @pytest.mark.asyncio
    async def test_get_client_details_list_response(self, mock_settings):
        mac = "00:11:22:33:44:55"
        active_response = [make_client(mac=mac)]

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response])

            result = await get_client_details("site-1", mac, mock_settings)

            assert result["mac"] == mac

    @pytest.mark.asyncio
    async def test_get_client_details_not_found(self, mock_settings):
        active_response = {"data": [make_client(mac="00:00:00:00:00:00")]}
        alluser_response = {"data": []}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            with pytest.raises(ResourceNotFoundError):
                await get_client_details("site-1", "ff:ff:ff:ff:ff:ff", mock_settings)

    @pytest.mark.asyncio
    async def test_get_client_details_invalid_site_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await get_client_details("", "00:11:22:33:44:55", mock_settings)

    @pytest.mark.asyncio
    async def test_get_client_details_invalid_mac(self, mock_settings):
        with pytest.raises(ValidationError):
            await get_client_details("site-1", "invalid-mac", mock_settings)

    @pytest.mark.asyncio
    async def test_get_client_details_mac_normalization(self, mock_settings):
        mac = "00:11:22:33:44:55"
        active_response = {"data": [make_client(mac=mac)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response])

            result = await get_client_details("site-1", "00-11-22-33-44-55", mock_settings)

            assert result["mac"] == mac


class TestGetClientStatistics:
    @pytest.mark.asyncio
    async def test_get_client_statistics_success(self, mock_settings):
        mac = "00:11:22:33:44:55"
        response = {"data": [make_client(mac=mac)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_client_statistics("site-1", mac, mock_settings)

            assert result["mac"] == mac
            assert result["tx_bytes"] == 1000000
            assert result["rx_bytes"] == 2000000
            assert result["tx_packets"] == 1000
            assert result["rx_packets"] == 2000
            assert result["signal"] == -65
            assert result["is_wired"] is False

    @pytest.mark.asyncio
    async def test_get_client_statistics_list_response(self, mock_settings):
        mac = "aa:bb:cc:dd:ee:ff"
        response = [make_client(mac=mac)]

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_client_statistics("site-1", mac, mock_settings)

            assert result["mac"] == mac

    @pytest.mark.asyncio
    async def test_get_client_statistics_not_found(self, mock_settings):
        response = {"data": [make_client(mac="00:00:00:00:00:00")]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            with pytest.raises(ResourceNotFoundError):
                await get_client_statistics("site-1", "ff:ff:ff:ff:ff:ff", mock_settings)

    @pytest.mark.asyncio
    async def test_get_client_statistics_minimal_data(self, mock_settings):
        mac = "00:11:22:33:44:55"
        minimal_client = {"mac": mac}
        response = {"data": [minimal_client]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_client_statistics("site-1", mac, mock_settings)

            assert result["mac"] == mac
            assert result["tx_bytes"] == 0
            assert result["rx_bytes"] == 0
            assert result["uptime"] == 0
            assert result["is_wired"] is False


class TestListActiveClients:
    @pytest.mark.asyncio
    async def test_list_active_clients_success(self, mock_settings):
        response = {
            "data": [
                make_client(mac="00:11:22:33:44:55"),
                make_client(mac="aa:bb:cc:dd:ee:ff"),
            ]
        }

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings)

            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_active_clients_list_response(self, mock_settings):
        response = [make_client(mac="00:11:22:33:44:55")]

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_active_clients_with_limit(self, mock_settings):
        response = {"data": [make_client(mac=f"00:00:00:00:00:{i:02x}") for i in range(10)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings, limit=5)

            assert len(result) == 5

    @pytest.mark.asyncio
    async def test_list_active_clients_with_offset(self, mock_settings):
        response = {"data": [make_client(mac=f"00:00:00:00:00:{i:02x}") for i in range(10)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings, offset=5, limit=3)

            assert len(result) == 3
            assert result[0]["mac"] == "00:00:00:00:00:05"

    @pytest.mark.asyncio
    async def test_list_active_clients_empty(self, mock_settings):
        response = {"data": []}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_active_clients_invalid_site_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await list_active_clients("", mock_settings)


class TestSearchClients:
    @pytest.mark.asyncio
    async def test_search_clients_by_mac(self, mock_settings):
        response = {
            "data": [
                make_client(mac="00:11:22:33:44:55"),
                make_client(mac="aa:bb:cc:dd:ee:ff"),
            ]
        }

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await search_clients("site-1", "00:11", mock_settings)

            assert len(result) == 1
            assert result[0]["mac"] == "00:11:22:33:44:55"

    @pytest.mark.asyncio
    async def test_search_clients_by_ip(self, mock_settings):
        response = {
            "data": [
                make_client(ip="192.168.2.100"),
                make_client(ip="192.168.2.200"),
            ]
        }

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await search_clients("site-1", "192.168.1", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_clients_by_hostname(self, mock_settings):
        response = {
            "data": [
                make_client(hostname="office-laptop"),
                make_client(hostname="home-phone"),
            ]
        }

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await search_clients("site-1", "office", mock_settings)

            assert len(result) == 1
            assert result[0]["hostname"] == "office-laptop"

    @pytest.mark.asyncio
    async def test_search_clients_by_name(self, mock_settings):
        response = {"data": [make_client(name="John's iPhone")]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await search_clients("site-1", "john", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_clients_case_insensitive(self, mock_settings):
        response = {"data": [make_client(hostname="Office-PC")]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await search_clients("site-1", "OFFICE", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_clients_with_pagination(self, mock_settings):
        response = {"data": [make_client(hostname=f"client-{i}") for i in range(10)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await search_clients("site-1", "client", mock_settings, limit=3, offset=2)

            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_search_clients_no_match(self, mock_settings):
        response = {"data": [make_client(hostname="office-pc")]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await search_clients("site-1", "nonexistent", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_search_clients_list_response(self, mock_settings):
        response = [make_client(hostname="test-client")]

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await search_clients("site-1", "test", mock_settings)

            assert len(result) == 1
