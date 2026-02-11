"""Unit tests for src/tools/networks.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.networks import (
    get_network_details,
    get_network_statistics,
    get_subnet_info,
    list_vlans,
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


def make_network(
    network_id="net-123",
    name="Default",
    vlan_id=1,
    subnet="192.168.1.0/24",
    dhcp_enabled=True,
):
    return {
        "_id": network_id,
        "name": name,
        "vlan_id": vlan_id,
        "ip_subnet": subnet,
        "dhcpd_enabled": dhcp_enabled,
        "dhcpd_start": "192.168.2.100",
        "dhcpd_stop": "192.168.1.200",
        "dhcpd_leasetime": 86400,
        "dhcpd_dns_1": "8.8.8.8",
        "dhcpd_dns_2": "8.8.4.4",
        "dhcpd_gateway": "192.168.2.1",
        "domain_name": "local",
        "purpose": "corporate",
    }


def make_client_on_vlan(vlan_id, tx_bytes=1000, rx_bytes=2000):
    return {
        "mac": "00:11:22:33:44:55",
        "vlan": vlan_id,
        "tx_bytes": tx_bytes,
        "rx_bytes": rx_bytes,
    }


class TestGetNetworkDetails:
    @pytest.mark.asyncio
    async def test_get_network_details_success(self, mock_settings):
        network_id = "net-123"
        response = {"data": [make_network(network_id=network_id, name="Main Network")]}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_network_details("site-1", network_id, mock_settings)

            assert result["id"] == network_id
            assert result["name"] == "Main Network"

    @pytest.mark.asyncio
    async def test_get_network_details_list_response(self, mock_settings):
        network_id = "net-456"
        response = [make_network(network_id=network_id)]

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_network_details("site-1", network_id, mock_settings)

            assert result["id"] == network_id

    @pytest.mark.asyncio
    async def test_get_network_details_not_found(self, mock_settings):
        response = {"data": [make_network(network_id="other-net")]}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            with pytest.raises(ResourceNotFoundError):
                await get_network_details("site-1", "nonexistent", mock_settings)

    @pytest.mark.asyncio
    async def test_get_network_details_invalid_site_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await get_network_details("", "net-123", mock_settings)


class TestListVlans:
    @pytest.mark.asyncio
    async def test_list_vlans_success(self, mock_settings):
        response = {
            "data": [
                make_network(network_id="net-1", name="LAN", vlan_id=1),
                make_network(network_id="net-2", name="Guest", vlan_id=100),
                make_network(network_id="net-3", name="IoT", vlan_id=200),
            ]
        }

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_vlans("site-1", mock_settings)

            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_vlans_list_response(self, mock_settings):
        response = [make_network(network_id="net-1")]

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_vlans("site-1", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_vlans_with_limit(self, mock_settings):
        response = {"data": [make_network(network_id=f"net-{i}", vlan_id=i) for i in range(10)]}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_vlans("site-1", mock_settings, limit=5)

            assert len(result) == 5

    @pytest.mark.asyncio
    async def test_list_vlans_with_offset(self, mock_settings):
        response = {"data": [make_network(network_id=f"net-{i}", vlan_id=i) for i in range(10)]}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_vlans("site-1", mock_settings, offset=3, limit=2)

            assert len(result) == 2
            assert result[0]["vlan_id"] == 3

    @pytest.mark.asyncio
    async def test_list_vlans_empty(self, mock_settings):
        response = {"data": []}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_vlans("site-1", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_vlans_invalid_site_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await list_vlans("", mock_settings)


class TestGetSubnetInfo:
    @pytest.mark.asyncio
    async def test_get_subnet_info_success(self, mock_settings):
        network_id = "net-123"
        response = {"data": [make_network(network_id=network_id)]}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_subnet_info("site-1", network_id, mock_settings)

            assert result["network_id"] == network_id
            assert result["ip_subnet"] == "192.168.1.0/24"
            assert result["dhcpd_enabled"] is True
            assert result["dhcpd_start"] == "192.168.2.100"
            assert result["dhcpd_stop"] == "192.168.1.200"
            assert result["dhcpd_dns_1"] == "8.8.8.8"

    @pytest.mark.asyncio
    async def test_get_subnet_info_list_response(self, mock_settings):
        network_id = "net-456"
        response = [make_network(network_id=network_id)]

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_subnet_info("site-1", network_id, mock_settings)

            assert result["network_id"] == network_id

    @pytest.mark.asyncio
    async def test_get_subnet_info_not_found(self, mock_settings):
        response = {"data": [make_network(network_id="other-net")]}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            with pytest.raises(ResourceNotFoundError):
                await get_subnet_info("site-1", "nonexistent", mock_settings)

    @pytest.mark.asyncio
    async def test_get_subnet_info_dhcp_disabled(self, mock_settings):
        network_id = "net-123"
        network = make_network(network_id=network_id, dhcp_enabled=False)
        del network["dhcpd_start"]
        del network["dhcpd_stop"]
        response = {"data": [network]}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_subnet_info("site-1", network_id, mock_settings)

            assert result["dhcpd_enabled"] is False
            assert result["dhcpd_start"] is None
            assert result["dhcpd_stop"] is None

    @pytest.mark.asyncio
    async def test_get_subnet_info_invalid_site_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await get_subnet_info("", "net-123", mock_settings)


class TestGetNetworkStatistics:
    @pytest.mark.asyncio
    async def test_get_network_statistics_success(self, mock_settings):
        networks_response = {
            "data": [
                make_network(network_id="net-1", name="LAN", vlan_id=1),
                make_network(network_id="net-2", name="Guest", vlan_id=100),
            ]
        }
        clients_response = {
            "data": [
                make_client_on_vlan(vlan_id=1, tx_bytes=1000, rx_bytes=2000),
                make_client_on_vlan(vlan_id=1, tx_bytes=500, rx_bytes=1000),
                make_client_on_vlan(vlan_id=100, tx_bytes=300, rx_bytes=600),
            ]
        }

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(
                [networks_response, clients_response]
            )

            result = await get_network_statistics("site-1", mock_settings)

            assert result["site_id"] == "site-1"
            assert len(result["networks"]) == 2

            lan_stats = next(n for n in result["networks"] if n["name"] == "LAN")
            assert lan_stats["client_count"] == 2
            assert lan_stats["total_tx_bytes"] == 1500
            assert lan_stats["total_rx_bytes"] == 3000
            assert lan_stats["total_bytes"] == 4500

            guest_stats = next(n for n in result["networks"] if n["name"] == "Guest")
            assert guest_stats["client_count"] == 1
            assert guest_stats["total_bytes"] == 900

    @pytest.mark.asyncio
    async def test_get_network_statistics_list_responses(self, mock_settings):
        networks_response = [make_network(network_id="net-1", vlan_id=1)]
        clients_response = [make_client_on_vlan(vlan_id=1)]

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(
                [networks_response, clients_response]
            )

            result = await get_network_statistics("site-1", mock_settings)

            assert len(result["networks"]) == 1
            assert result["networks"][0]["client_count"] == 1

    @pytest.mark.asyncio
    async def test_get_network_statistics_no_clients(self, mock_settings):
        networks_response = {"data": [make_network(network_id="net-1", vlan_id=1)]}
        clients_response = {"data": []}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(
                [networks_response, clients_response]
            )

            result = await get_network_statistics("site-1", mock_settings)

            assert result["networks"][0]["client_count"] == 0
            assert result["networks"][0]["total_bytes"] == 0

    @pytest.mark.asyncio
    async def test_get_network_statistics_no_networks(self, mock_settings):
        networks_response = {"data": []}
        clients_response = {"data": []}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(
                [networks_response, clients_response]
            )

            result = await get_network_statistics("site-1", mock_settings)

            assert result["networks"] == []

    @pytest.mark.asyncio
    async def test_get_network_statistics_invalid_site_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await get_network_statistics("", mock_settings)

    @pytest.mark.asyncio
    async def test_get_network_statistics_clients_missing_bytes(self, mock_settings):
        networks_response = {"data": [make_network(network_id="net-1", vlan_id=1)]}
        clients_response = {"data": [{"mac": "00:11:22:33:44:55", "vlan": 1}]}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client(
                [networks_response, clients_response]
            )

            result = await get_network_statistics("site-1", mock_settings)

            assert result["networks"][0]["total_tx_bytes"] == 0
            assert result["networks"][0]["total_rx_bytes"] == 0
