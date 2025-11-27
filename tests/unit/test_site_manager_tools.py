"""Unit tests for Site Manager tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.tools.site_manager import (
    get_cross_site_statistics,
    get_internet_health,
    get_site_health_summary,
    list_all_sites_aggregated,
    list_vantage_points,
)


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings with Site Manager enabled."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
    monkeypatch.setenv("UNIFI_SITE_MANAGER_ENABLED", "true")
    return Settings(_env_file=None)


@pytest.fixture
def mock_settings_disabled(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings with Site Manager disabled."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
    monkeypatch.setenv("UNIFI_SITE_MANAGER_ENABLED", "false")
    return Settings(_env_file=None)


class TestListAllSitesAggregated:
    """Test suite for list_all_sites_aggregated function."""

    @pytest.mark.asyncio
    async def test_list_all_sites_success(self, mock_settings: Settings) -> None:
        """Test listing all sites with aggregated stats."""
        mock_sites_data = {
            "data": [
                {
                    "id": "site1",
                    "name": "Site One",
                    "description": "First site",
                },
                {
                    "id": "site2",
                    "name": "Site Two",
                    "description": "Second site",
                },
            ]
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.list_sites.return_value = mock_sites_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_all_sites_aggregated(mock_settings)

            assert len(result) == 2
            assert result[0]["id"] == "site1"
            assert result[0]["name"] == "Site One"
            assert result[1]["id"] == "site2"
            mock_client.list_sites.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_all_sites_with_sites_key(self, mock_settings: Settings) -> None:
        """Test listing all sites when response uses 'sites' key."""
        mock_sites_data = {
            "sites": [
                {"id": "site1", "name": "Site One"},
            ]
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.list_sites.return_value = mock_sites_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_all_sites_aggregated(mock_settings)

            assert len(result) == 1
            assert result[0]["id"] == "site1"

    @pytest.mark.asyncio
    async def test_list_all_sites_empty(self, mock_settings: Settings) -> None:
        """Test listing all sites with empty response."""
        mock_sites_data = {"data": []}

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.list_sites.return_value = mock_sites_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_all_sites_aggregated(mock_settings)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_all_sites_manager_disabled(
        self, mock_settings_disabled: Settings
    ) -> None:
        """Test that error is raised when Site Manager is disabled."""
        with pytest.raises(ValueError, match="Site Manager API is not enabled"):
            await list_all_sites_aggregated(mock_settings_disabled)


class TestGetInternetHealth:
    """Test suite for get_internet_health function."""

    @pytest.mark.asyncio
    async def test_get_internet_health_all_sites(self, mock_settings: Settings) -> None:
        """Test getting internet health for all sites."""
        mock_health_data = {
            "data": {
                "latency_ms": 15.5,
                "packet_loss_percent": 0.1,
                "bandwidth_down_mbps": 950.0,
                "bandwidth_up_mbps": 450.0,
                "jitter_ms": 2.3,
                "status": "healthy",
                "last_tested": "2025-11-26T12:00:00Z",
            }
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_internet_health.return_value = mock_health_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await get_internet_health(mock_settings)

            assert result["latency_ms"] == 15.5
            assert result["packet_loss_percent"] == 0.1
            assert result["bandwidth_down_mbps"] == 950.0
            assert result["status"] == "healthy"
            mock_client.get_internet_health.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_get_internet_health_specific_site(
        self, mock_settings: Settings
    ) -> None:
        """Test getting internet health for a specific site."""
        mock_health_data = {
            "latency_ms": 20.0,
            "packet_loss_percent": 0.5,
            "bandwidth_down_mbps": 500.0,
            "bandwidth_up_mbps": 250.0,
            "status": "degraded",
            "last_tested": "2025-11-26T12:00:00Z",
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_internet_health.return_value = mock_health_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await get_internet_health(mock_settings, site_id="site-123")

            assert result["latency_ms"] == 20.0
            mock_client.get_internet_health.assert_called_once_with("site-123")

    @pytest.mark.asyncio
    async def test_get_internet_health_manager_disabled(
        self, mock_settings_disabled: Settings
    ) -> None:
        """Test that error is raised when Site Manager is disabled."""
        with pytest.raises(ValueError, match="Site Manager API is not enabled"):
            await get_internet_health(mock_settings_disabled)


class TestGetSiteHealthSummary:
    """Test suite for get_site_health_summary function."""

    @pytest.mark.asyncio
    async def test_get_site_health_specific_site(self, mock_settings: Settings) -> None:
        """Test getting health summary for a specific site."""
        mock_health_data = {
            "data": {
                "site_id": "site-123",
                "site_name": "Test Site",
                "status": "healthy",
                "devices_total": 10,
                "devices_online": 9,
                "clients_active": 25,
                "last_updated": "2025-11-26T12:00:00Z",
            }
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_site_health.return_value = mock_health_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await get_site_health_summary(mock_settings, site_id="site-123")

            assert isinstance(result, dict)
            assert result["site_id"] == "site-123"
            assert result["status"] == "healthy"
            assert result["devices_total"] == 10
            mock_client.get_site_health.assert_called_once_with("site-123")

    @pytest.mark.asyncio
    async def test_get_site_health_all_sites(self, mock_settings: Settings) -> None:
        """Test getting health summary for all sites."""
        mock_health_data = {
            "data": {
                "sites": [
                    {
                        "site_id": "site-1",
                        "site_name": "Site One",
                        "status": "healthy",
                        "devices_total": 10,
                        "last_updated": "2025-11-26T12:00:00Z",
                        "devices_online": 9,
                        "clients_active": 25,
                    },
                    {
                        "site_id": "site-2",
                        "site_name": "Site Two",
                        "status": "degraded",
                        "devices_total": 5,
                        "last_updated": "2025-11-26T12:00:00Z",
                        "devices_online": 4,
                        "clients_active": 12,
                    },
                ]
            }
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_site_health.return_value = mock_health_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await get_site_health_summary(mock_settings)

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["site_id"] == "site-1"
            assert result[0]["status"] == "healthy"
            assert result[1]["site_id"] == "site-2"
            assert result[1]["status"] == "degraded"
            mock_client.get_site_health.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_get_site_health_list_response(self, mock_settings: Settings) -> None:
        """Test getting health summary when response is a list."""
        mock_health_data = [
            {
                "site_id": "site-1",
                "site_name": "Site One",
                "status": "healthy",
                "devices_total": 10,
                        "last_updated": "2025-11-26T12:00:00Z",
                "devices_online": 9,
                "clients_active": 25,
            }
        ]

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_site_health.return_value = mock_health_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await get_site_health_summary(mock_settings)

            assert isinstance(result, list)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_site_health_manager_disabled(
        self, mock_settings_disabled: Settings
    ) -> None:
        """Test that error is raised when Site Manager is disabled."""
        with pytest.raises(ValueError, match="Site Manager API is not enabled"):
            await get_site_health_summary(mock_settings_disabled)


class TestGetCrossSiteStatistics:
    """Test suite for get_cross_site_statistics function."""

    @pytest.mark.asyncio
    async def test_get_cross_site_statistics_success(
        self, mock_settings: Settings
    ) -> None:
        """Test getting cross-site statistics."""
        mock_sites_data = {
            "data": [
                {"id": "site-1", "name": "Site One"},
                {"id": "site-2", "name": "Site Two"},
            ]
        }

        mock_health_data = {
            "data": [
                {
                    "site_id": "site-1",
                    "site_name": "Site One",
                    "status": "healthy",
                    "devices_total": 10,
                        "last_updated": "2025-11-26T12:00:00Z",
                    "devices_online": 9,
                    "clients_active": 25,
                },
                {
                    "site_id": "site-2",
                    "site_name": "Site Two",
                    "status": "degraded",
                    "devices_total": 5,
                        "last_updated": "2025-11-26T12:00:00Z",
                    "devices_online": 4,
                    "clients_active": 12,
                },
            ]
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.list_sites.return_value = mock_sites_data
            mock_client.get_site_health.return_value = mock_health_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await get_cross_site_statistics(mock_settings)

            assert result["total_sites"] == 2
            assert result["sites_healthy"] == 1
            assert result["sites_degraded"] == 1
            assert result["sites_down"] == 0
            assert result["total_devices"] == 15
            assert result["devices_online"] == 13
            assert result["total_clients"] == 37
            assert len(result["site_summaries"]) == 2
            mock_client.list_sites.assert_called_once()
            mock_client.get_site_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cross_site_statistics_all_healthy(
        self, mock_settings: Settings
    ) -> None:
        """Test cross-site statistics with all sites healthy."""
        mock_sites_data = {"data": [{"id": "site-1"}]}
        mock_health_data = {
            "data": [
                {
                    "site_id": "site-1",
                    "site_name": "Site One",
                    "status": "healthy",
                    "devices_total": 10,
                        "last_updated": "2025-11-26T12:00:00Z",
                    "devices_online": 10,
                    "clients_active": 25,
                }
            ]
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.list_sites.return_value = mock_sites_data
            mock_client.get_site_health.return_value = mock_health_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await get_cross_site_statistics(mock_settings)

            assert result["sites_healthy"] == 1
            assert result["sites_degraded"] == 0
            assert result["sites_down"] == 0

    @pytest.mark.asyncio
    async def test_get_cross_site_statistics_with_down_site(
        self, mock_settings: Settings
    ) -> None:
        """Test cross-site statistics with a down site."""
        mock_sites_data = {"data": [{"id": "site-1"}]}
        mock_health_data = {
            "data": [
                {
                    "site_id": "site-1",
                    "site_name": "Site One",
                    "status": "down",
                    "devices_total": 10,
                        "last_updated": "2025-11-26T12:00:00Z",
                    "devices_online": 0,
                    "clients_active": 0,
                }
            ]
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.list_sites.return_value = mock_sites_data
            mock_client.get_site_health.return_value = mock_health_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await get_cross_site_statistics(mock_settings)

            assert result["sites_down"] == 1
            assert result["sites_healthy"] == 0

    @pytest.mark.asyncio
    async def test_get_cross_site_statistics_manager_disabled(
        self, mock_settings_disabled: Settings
    ) -> None:
        """Test that error is raised when Site Manager is disabled."""
        with pytest.raises(ValueError, match="Site Manager API is not enabled"):
            await get_cross_site_statistics(mock_settings_disabled)


class TestListVantagePoints:
    """Test suite for list_vantage_points function."""

    @pytest.mark.asyncio
    async def test_list_vantage_points_success(self, mock_settings: Settings) -> None:
        """Test listing vantage points."""
        mock_vp_data = {
            "data": [
                {
                    "id": "vp-1",
                    "name": "Vantage Point 1",
                    "location": "US-West",
                    "type": "speedtest",
                    "vantage_point_id": "vp-1",
                    "status": "active",
                },
                {
                    "id": "vp-2",
                    "name": "Vantage Point 2",
                    "location": "US-East",
                    "type": "ping",
                    "vantage_point_id": "vp-2",
                    "status": "active",
                },
            ]
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.list_vantage_points.return_value = mock_vp_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_vantage_points(mock_settings)

            assert len(result) == 2
            assert result[0]["id"] == "vp-1"
            assert result[0]["name"] == "Vantage Point 1"
            assert result[1]["id"] == "vp-2"
            mock_client.list_vantage_points.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_vantage_points_with_vp_key(
        self, mock_settings: Settings
    ) -> None:
        """Test listing vantage points when response uses 'vantage_points' key."""
        mock_vp_data = {
            "vantage_points": [
                {
                    "id": "vp-1",
                    "name": "Vantage Point 1",
                    "location": "US-West",
                    "type": "speedtest",
                    "vantage_point_id": "vp-1",
                    "status": "active",
                }
            ]
        }

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.list_vantage_points.return_value = mock_vp_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_vantage_points(mock_settings)

            assert len(result) == 1
            assert result[0]["id"] == "vp-1"

    @pytest.mark.asyncio
    async def test_list_vantage_points_empty(self, mock_settings: Settings) -> None:
        """Test listing vantage points with empty response."""
        mock_vp_data = {"data": []}

        with patch("src.tools.site_manager.SiteManagerClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.list_vantage_points.return_value = mock_vp_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_vantage_points(mock_settings)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_vantage_points_manager_disabled(
        self, mock_settings_disabled: Settings
    ) -> None:
        """Test that error is raised when Site Manager is disabled."""
        with pytest.raises(ValueError, match="Site Manager API is not enabled"):
            await list_vantage_points(mock_settings_disabled)
