"""Unit tests for MCP resources."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import Settings
from src.resources import ClientsResource, DevicesResource, NetworksResource, SitesResource


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings for testing."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    return Settings()


class TestSitesResource:
    """Test suite for SitesResource."""

    @pytest.mark.asyncio
    async def test_list_sites(
        self, mock_settings: Settings, sample_site_data: dict
    ) -> None:
        """Test listing all sites."""
        with patch("src.resources.sites.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_site_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = SitesResource(mock_settings)
            sites = await resource.list_sites()

            assert len(sites) == 2
            assert sites[0].id == "default"
            assert sites[0].name == "Default Site"
            assert sites[1].id == "site-123"

    @pytest.mark.asyncio
    async def test_list_sites_with_pagination(
        self, mock_settings: Settings, sample_site_data: dict
    ) -> None:
        """Test listing sites with pagination."""
        with patch("src.resources.sites.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_site_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = SitesResource(mock_settings)
            sites = await resource.list_sites(limit=1, offset=0)

            assert len(sites) == 1
            assert sites[0].id == "default"

    @pytest.mark.asyncio
    async def test_get_site(
        self, mock_settings: Settings, sample_site_data: dict
    ) -> None:
        """Test getting a specific site."""
        with patch("src.resources.sites.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_site_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = SitesResource(mock_settings)
            site = await resource.get_site("default")

            assert site is not None
            assert site.id == "default"
            assert site.name == "Default Site"

    @pytest.mark.asyncio
    async def test_get_site_not_found(
        self, mock_settings: Settings, sample_site_data: dict
    ) -> None:
        """Test getting a site that doesn't exist."""
        with patch("src.resources.sites.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_site_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = SitesResource(mock_settings)
            site = await resource.get_site("nonexistent")

            assert site is None


class TestDevicesResource:
    """Test suite for DevicesResource."""

    @pytest.mark.asyncio
    async def test_list_devices(
        self, mock_settings: Settings, sample_device_data: dict
    ) -> None:
        """Test listing all devices."""
        with patch("src.resources.devices.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_device_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = DevicesResource(mock_settings)
            devices = await resource.list_devices("default")

            assert len(devices) == 2
            assert devices[0].name == "AP-Office"
            assert devices[1].name == "Switch-Main"

    @pytest.mark.asyncio
    async def test_list_devices_with_pagination(
        self, mock_settings: Settings, sample_device_data: dict
    ) -> None:
        """Test listing devices with pagination."""
        with patch("src.resources.devices.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_device_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = DevicesResource(mock_settings)
            devices = await resource.list_devices("default", limit=1, offset=1)

            assert len(devices) == 1
            assert devices[0].name == "Switch-Main"

    @pytest.mark.asyncio
    async def test_filter_by_type(
        self, mock_settings: Settings, sample_device_data: dict
    ) -> None:
        """Test filtering devices by type."""
        with patch("src.resources.devices.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_device_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = DevicesResource(mock_settings)
            devices = await resource.filter_by_type("default", "uap")

            assert len(devices) == 1
            assert devices[0].type == "uap"


class TestClientsResource:
    """Test suite for ClientsResource."""

    @pytest.mark.asyncio
    async def test_list_clients(
        self, mock_settings: Settings, sample_client_data: dict
    ) -> None:
        """Test listing all clients."""
        with patch("src.resources.clients.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_client_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = ClientsResource(mock_settings)
            clients = await resource.list_clients("default")

            assert len(clients) == 2
            assert clients[0].hostname == "laptop-001"
            assert clients[1].hostname == "desktop-001"

    @pytest.mark.asyncio
    async def test_list_clients_active_only(
        self, mock_settings: Settings, sample_client_data: dict
    ) -> None:
        """Test listing only active clients."""
        with patch("src.resources.clients.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_client_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = ClientsResource(mock_settings)
            clients = await resource.list_clients("default", active_only=True)

            # Should call the correct endpoint
            mock_instance.get.assert_called_with("/ea/sites/default/sta")

    @pytest.mark.asyncio
    async def test_filter_by_connection(
        self, mock_settings: Settings, sample_client_data: dict
    ) -> None:
        """Test filtering clients by connection type."""
        with patch("src.resources.clients.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_client_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = ClientsResource(mock_settings)
            clients = await resource.filter_by_connection("default", is_wired=True)

            assert len(clients) == 1
            assert clients[0].is_wired is True


class TestNetworksResource:
    """Test suite for NetworksResource."""

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
    async def test_list_networks(
        self, mock_settings: Settings, sample_network_data: dict
    ) -> None:
        """Test listing all networks."""
        with patch("src.resources.networks.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_network_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = NetworksResource(mock_settings)
            networks = await resource.list_networks("default")

            assert len(networks) == 2
            assert networks[0].name == "LAN"
            assert networks[1].name == "Guest"

    @pytest.mark.asyncio
    async def test_list_vlans(
        self, mock_settings: Settings, sample_network_data: dict
    ) -> None:
        """Test listing VLANs."""
        with patch("src.resources.networks.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value=sample_network_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            resource = NetworksResource(mock_settings)
            vlans = await resource.list_vlans("default")

            assert len(vlans) == 2
            assert all(v.vlan_id is not None for v in vlans)
