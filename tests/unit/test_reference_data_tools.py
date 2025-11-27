"""Unit tests for Reference Data tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.reference_data import list_countries, list_device_tags, list_radius_profiles


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
    return Settings(_env_file=None)


class TestListRADIUSProfiles:
    """Test suite for list_radius_profiles function."""

    @pytest.mark.asyncio
    async def test_list_profiles_success(self, mock_settings: Settings) -> None:
        """Test listing RADIUS profiles successfully."""
        mock_data = {
            "data": [
                {
                    "_id": "profile1",
                    "name": "Corporate RADIUS",
                    "auth_server": "radius.corp.com",
                    "auth_port": 1812,
                    "acct_port": 1813,
                    "enabled": True,
                },
                {
                    "_id": "profile2",
                    "name": "Guest RADIUS",
                    "auth_server": "radius.guest.com",
                    "auth_port": 1812,
                    "enabled": False,
                },
            ]
        }

        with patch("src.tools.reference_data.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_radius_profiles("site-123", mock_settings)

            assert len(result) == 2
            assert result[0]["name"] == "Corporate RADIUS"
            assert result[0]["auth_port"] == 1812
            assert result[1]["enabled"] is False
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_profiles_empty(self, mock_settings: Settings) -> None:
        """Test listing RADIUS profiles when none exist."""
        mock_data = {"data": []}

        with patch("src.tools.reference_data.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_radius_profiles("site-123", mock_settings)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_profiles_pagination(self, mock_settings: Settings) -> None:
        """Test listing RADIUS profiles with pagination."""
        mock_data = {
            "data": [
                {
                    "_id": f"profile{i}",
                    "name": f"RADIUS Profile {i}",
                    "enabled": True,
                }
                for i in range(10)
            ]
        }

        with patch("src.tools.reference_data.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_radius_profiles("site-123", mock_settings, limit=3, offset=2)

            assert len(result) == 3
            assert result[0]["name"] == "RADIUS Profile 2"


class TestListDeviceTags:
    """Test suite for list_device_tags function."""

    @pytest.mark.asyncio
    async def test_list_tags_success(self, mock_settings: Settings) -> None:
        """Test listing device tags successfully."""
        mock_data = {
            "data": [
                {
                    "_id": "tag1",
                    "name": "Guest WiFi APs",
                    "devices": ["device-1", "device-2"],
                },
                {
                    "_id": "tag2",
                    "name": "Office APs",
                    "devices": ["device-3", "device-4", "device-5"],
                },
            ]
        }

        with patch("src.tools.reference_data.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_device_tags("site-123", mock_settings)

            assert len(result) == 2
            assert result[0]["name"] == "Guest WiFi APs"
            assert len(result[0]["devices"]) == 2
            assert len(result[1]["devices"]) == 3
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_tags_empty(self, mock_settings: Settings) -> None:
        """Test listing device tags when none exist."""
        mock_data = {"data": []}

        with patch("src.tools.reference_data.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_device_tags("site-123", mock_settings)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_tags_pagination(self, mock_settings: Settings) -> None:
        """Test listing device tags with pagination."""
        mock_data = {
            "data": [
                {
                    "_id": f"tag{i}",
                    "name": f"Tag {i}",
                    "devices": [],
                }
                for i in range(10)
            ]
        }

        with patch("src.tools.reference_data.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_device_tags("site-123", mock_settings, limit=4, offset=1)

            assert len(result) == 4
            assert result[0]["name"] == "Tag 1"


class TestListCountries:
    """Test suite for list_countries function."""

    @pytest.mark.asyncio
    async def test_list_countries_success(self, mock_settings: Settings) -> None:
        """Test listing countries successfully."""
        mock_data = {
            "data": [
                {"code": "US", "name": "United States"},
                {"code": "CA", "name": "Canada"},
                {"code": "MX", "name": "Mexico"},
            ]
        }

        with patch("src.tools.reference_data.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_countries(mock_settings)

            assert len(result) == 3
            assert result[0]["code"] == "US"
            assert result[0]["name"] == "United States"
            assert result[1]["code"] == "CA"
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_countries_empty(self, mock_settings: Settings) -> None:
        """Test listing countries when none exist."""
        mock_data = {"data": []}

        with patch("src.tools.reference_data.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_countries(mock_settings)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_countries_large_dataset(self, mock_settings: Settings) -> None:
        """Test listing countries with large dataset and pagination."""
        # Create a large dataset of countries
        mock_data = {
            "data": [
                {"code": f"C{i:02d}", "name": f"Country {i}"}
                for i in range(250)  # ISO 3166-1 has 249 countries
            ]
        }

        with patch("src.tools.reference_data.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_countries(mock_settings, limit=50, offset=100)

            assert len(result) == 50
            assert result[0]["code"] == "C100"
            assert result[49]["code"] == "C149"
