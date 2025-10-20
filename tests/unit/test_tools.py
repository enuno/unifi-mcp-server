"""Unit tests for MCP tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools import clients as clients_tools
from src.tools import devices as devices_tools
from src.tools import networks as networks_tools
from src.tools import sites as sites_tools
from src.utils import ResourceNotFoundError


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings for testing."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    return Settings()


class TestDeviceTools:
    """Test suite for device management tools."""

    @pytest.mark.asyncio
    async def test_get_device_details(
        self, mock_settings: Settings, sample_device_data: dict
    ) -> None:
        """Test getting device details."""
        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_device_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await devices_tools.get_device_details(
                "default", "507f1f77bcf86cd799439011", mock_settings
            )

            assert result["name"] == "AP-Office"
            assert result["model"] == "U6-LR"

    @pytest.mark.asyncio
    async def test_get_device_details_not_found(self, mock_settings: Settings) -> None:
        """Test device not found."""
        # Return empty data to simulate device not found
        empty_data = {"meta": {"rc": "ok"}, "data": []}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=empty_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_instance

            with pytest.raises(ResourceNotFoundError):
                await devices_tools.get_device_details(
                    "default", "000000000000000000000000", mock_settings
                )

    @pytest.mark.asyncio
    async def test_list_devices_by_type(
        self, mock_settings: Settings, sample_device_data: dict
    ) -> None:
        """Test filtering devices by type."""
        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_device_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await devices_tools.list_devices_by_type("default", "uap", mock_settings)

            assert len(result) == 1
            assert result[0]["type"] == "uap"

    @pytest.mark.asyncio
    async def test_get_device_statistics(
        self, mock_settings: Settings, sample_device_data: dict
    ) -> None:
        """Test getting device statistics."""
        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_device_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await devices_tools.get_device_statistics(
                "default", "507f1f77bcf86cd799439011", mock_settings
            )

            assert result["device_id"] == "507f1f77bcf86cd799439011"
            assert result["uptime"] == 86400
            assert result["state"] == 1

    @pytest.mark.asyncio
    async def test_get_device_statistics_not_found(self, mock_settings: Settings) -> None:
        """Test device statistics not found."""
        empty_data = {"meta": {"rc": "ok"}, "data": []}

        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=empty_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_instance

            with pytest.raises(ResourceNotFoundError):
                await devices_tools.get_device_statistics(
                    "default", "000000000000000000000000", mock_settings
                )

    @pytest.mark.asyncio
    async def test_search_devices(self, mock_settings: Settings, sample_device_data: dict) -> None:
        """Test searching devices."""
        with patch("src.tools.devices.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_device_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await devices_tools.search_devices("default", "office", mock_settings)

            assert len(result) == 1
            assert "Office" in result[0]["name"]


class TestClientTools:
    """Test suite for client management tools."""

    @pytest.mark.asyncio
    async def test_get_client_details(
        self, mock_settings: Settings, sample_client_data: dict
    ) -> None:
        """Test getting client details."""
        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_client_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await clients_tools.get_client_details(
                "default", "aa:bb:cc:dd:ee:01", mock_settings
            )

            assert result["hostname"] == "laptop-001"

    @pytest.mark.asyncio
    async def test_list_active_clients(
        self, mock_settings: Settings, sample_client_data: dict
    ) -> None:
        """Test listing active clients."""
        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_client_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await clients_tools.list_active_clients("default", mock_settings)

            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_client_statistics(
        self, mock_settings: Settings, sample_client_data: dict
    ) -> None:
        """Test getting client statistics."""
        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_client_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await clients_tools.get_client_statistics(
                "default", "aa:bb:cc:dd:ee:01", mock_settings
            )

            assert result["mac"] == "aa:bb:cc:dd:ee:01"
            assert result["tx_bytes"] == 1024000
            assert result["rx_bytes"] == 2048000
            assert result["signal"] == -45

    @pytest.mark.asyncio
    async def test_get_client_statistics_not_found(self, mock_settings: Settings) -> None:
        """Test client statistics not found."""
        empty_data = {"meta": {"rc": "ok"}, "data": []}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=empty_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_instance

            with pytest.raises(ResourceNotFoundError):
                await clients_tools.get_client_statistics(
                    "default", "ff:ff:ff:ff:ff:ff", mock_settings
                )

    @pytest.mark.asyncio
    async def test_search_clients(self, mock_settings: Settings, sample_client_data: dict) -> None:
        """Test searching clients."""
        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_client_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await clients_tools.search_clients("default", "laptop", mock_settings)

            assert len(result) == 1
            assert "laptop" in result[0]["hostname"]


class TestNetworkTools:
    """Test suite for network information tools."""

    @pytest.fixture
    def sample_network_data(self) -> dict:
        """Sample network data for testing."""
        return {
            "meta": {"rc": "ok"},
            "data": [
                {
                    "_id": "507f191e810c19729de860ea",
                    "name": "LAN",
                    "purpose": "corporate",
                    "vlan_id": 1,
                    "ip_subnet": "192.168.1.0/24",
                    "dhcpd_enabled": True,
                },
                {
                    "_id": "507f191e810c19729de860eb",
                    "name": "Guest",
                    "purpose": "guest",
                    "vlan_id": 100,
                    "ip_subnet": "192.168.100.0/24",
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_get_network_details(
        self, mock_settings: Settings, sample_network_data: dict
    ) -> None:
        """Test getting network details."""
        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_network_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await networks_tools.get_network_details(
                "default", "507f191e810c19729de860ea", mock_settings
            )

            assert result["name"] == "LAN"

    @pytest.mark.asyncio
    async def test_get_subnet_info(
        self, mock_settings: Settings, sample_network_data: dict
    ) -> None:
        """Test getting subnet information."""
        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_network_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await networks_tools.get_subnet_info(
                "default", "507f191e810c19729de860ea", mock_settings
            )

            assert result["network_id"] == "507f191e810c19729de860ea"
            assert result["name"] == "LAN"
            assert result["ip_subnet"] == "192.168.1.0/24"
            assert result["dhcpd_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_subnet_info_not_found(self, mock_settings: Settings) -> None:
        """Test subnet info not found."""
        empty_data = {"meta": {"rc": "ok"}, "data": []}

        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=empty_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_instance

            with pytest.raises(ResourceNotFoundError):
                await networks_tools.get_subnet_info(
                    "default", "000000000000000000000000", mock_settings
                )

    @pytest.mark.asyncio
    async def test_get_network_statistics(
        self, mock_settings: Settings, sample_network_data: dict, sample_client_data: dict
    ) -> None:
        """Test getting network statistics."""
        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            # Mock multiple get calls for networks and clients
            mock_instance.get = AsyncMock(side_effect=[sample_network_data, sample_client_data])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await networks_tools.get_network_statistics("default", mock_settings)

            assert result["site_id"] == "default"
            assert "networks" in result
            assert len(result["networks"]) == 2

    @pytest.mark.asyncio
    async def test_list_vlans(self, mock_settings: Settings, sample_network_data: dict) -> None:
        """Test listing VLANs."""
        with patch("src.tools.networks.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_network_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await networks_tools.list_vlans("default", mock_settings)

            assert len(result) == 2
            assert all("vlan_id" in n for n in result)


class TestSiteTools:
    """Test suite for site management tools."""

    @pytest.mark.asyncio
    async def test_get_site_details(self, mock_settings: Settings, sample_site_data: dict) -> None:
        """Test getting site details."""
        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_site_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await sites_tools.get_site_details("default", mock_settings)

            assert result["name"] == "Default Site"

    @pytest.mark.asyncio
    async def test_list_sites(self, mock_settings: Settings, sample_site_data: dict) -> None:
        """Test listing sites."""
        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_site_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await sites_tools.list_sites(mock_settings)

            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_site_statistics(
        self,
        mock_settings: Settings,
        sample_device_data: dict,
        sample_client_data: dict,
    ) -> None:
        """Test getting site statistics."""
        network_data = {
            "meta": {"rc": "ok"},
            "data": [{"_id": "1", "name": "LAN", "purpose": "corporate"}],
        }

        with patch("src.tools.sites.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()

            # Mock multiple get calls
            mock_instance.get = AsyncMock(
                side_effect=[sample_device_data, sample_client_data, network_data]
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await sites_tools.get_site_statistics("default", mock_settings)

            assert "devices" in result
            assert "clients" in result
            assert "networks" in result
            assert result["devices"]["total"] == 2
            assert result["clients"]["total"] == 2
