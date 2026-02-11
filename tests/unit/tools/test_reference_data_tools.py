"""Unit tests for reference data tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.reference_data as ref_module
from src.tools.reference_data import list_countries, list_device_tags, list_radius_profiles


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "local"
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-key"
    settings.local_host = "192.168.2.1"
    settings.local_port = 443
    settings.local_verify_ssl = False
    return settings


# =============================================================================
# list_countries Tests - Task 17.1
# =============================================================================


@pytest.mark.asyncio
async def test_list_countries_success(mock_settings):
    """Test successful listing of countries."""
    mock_response = {
        "data": [
            {"_id": "us", "code": "US", "name": "United States"},
            {"_id": "ca", "code": "CA", "name": "Canada"},
            {"_id": "gb", "code": "GB", "name": "United Kingdom"},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_countries(settings=mock_settings)

    assert len(result) == 3
    assert result[0]["code"] == "US"
    assert result[0]["name"] == "United States"
    assert result[1]["code"] == "CA"
    assert result[2]["code"] == "GB"
    mock_client.get.assert_called_once_with("/integration/v1/countries")


@pytest.mark.asyncio
async def test_list_countries_pagination(mock_settings):
    """Test listing countries with pagination."""
    mock_response = {
        "data": [
            {"_id": "us", "code": "US", "name": "United States"},
            {"_id": "ca", "code": "CA", "name": "Canada"},
            {"_id": "gb", "code": "GB", "name": "United Kingdom"},
            {"_id": "de", "code": "DE", "name": "Germany"},
            {"_id": "fr", "code": "FR", "name": "France"},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_countries(settings=mock_settings, limit=2, offset=1)

    assert len(result) == 2
    assert result[0]["code"] == "CA"
    assert result[1]["code"] == "GB"


@pytest.mark.asyncio
async def test_list_countries_empty(mock_settings):
    """Test listing countries when none exist."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_countries(settings=mock_settings)

    assert len(result) == 0
    assert result == []


@pytest.mark.asyncio
async def test_list_countries_default_pagination(mock_settings):
    """Test listing countries with default pagination values."""
    mock_response = {
        "data": [
            {"code": "MX", "name": "Mexico"},
            {"code": "BR", "name": "Brazil"},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_countries(settings=mock_settings, limit=None, offset=None)

    assert len(result) == 2
    assert result[0]["code"] == "MX"
    assert result[1]["code"] == "BR"


# =============================================================================
# list_device_tags Tests - Task 17.2
# =============================================================================


@pytest.mark.asyncio
async def test_list_device_tags_success(mock_settings):
    """Test successful listing of device tags."""
    mock_response = {
        "data": [
            {"_id": "tag1", "name": "Access Point", "color": "blue"},
            {"_id": "tag2", "name": "Switch", "color": "green"},
            {"_id": "tag3", "name": "Gateway", "color": "purple"},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_device_tags(site_id="default", settings=mock_settings)

    assert len(result) == 3
    assert result[0]["name"] == "Access Point"
    assert result[1]["name"] == "Switch"
    assert result[2]["name"] == "Gateway"
    mock_client.get.assert_called_once_with("/integration/v1/sites/default/device-tags")


@pytest.mark.asyncio
async def test_list_device_tags_empty(mock_settings):
    """Test listing device tags when none exist."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_device_tags(site_id="default", settings=mock_settings)

    assert len(result) == 0
    assert result == []


@pytest.mark.asyncio
async def test_list_device_tags_pagination(mock_settings):
    """Test listing device tags with pagination."""
    mock_response = {
        "data": [
            {"_id": "tag1", "name": "Tag 1"},
            {"_id": "tag2", "name": "Tag 2"},
            {"_id": "tag3", "name": "Tag 3"},
            {"_id": "tag4", "name": "Tag 4"},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_device_tags(
            site_id="default", settings=mock_settings, limit=2, offset=1
        )

    assert len(result) == 2
    assert result[0]["name"] == "Tag 2"
    assert result[1]["name"] == "Tag 3"


# =============================================================================
# list_radius_profiles Tests - Task 17.2
# =============================================================================


@pytest.mark.asyncio
async def test_list_radius_profiles_success(mock_settings):
    """Test successful listing of RADIUS profiles."""
    mock_response = {
        "data": [
            {
                "_id": "radius1",
                "name": "Corporate RADIUS",
                "auth_servers": [{"host": "10.0.0.1", "port": 1812}],
            },
            {
                "_id": "radius2",
                "name": "Guest RADIUS",
                "auth_servers": [{"host": "10.0.0.2", "port": 1812}],
            },
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_radius_profiles(site_id="default", settings=mock_settings)

    assert len(result) == 2
    assert result[0]["name"] == "Corporate RADIUS"
    assert result[1]["name"] == "Guest RADIUS"
    mock_client.get.assert_called_once_with("/integration/v1/sites/default/radius/profiles")


@pytest.mark.asyncio
async def test_list_radius_profiles_empty(mock_settings):
    """Test listing RADIUS profiles when none exist."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_radius_profiles(site_id="default", settings=mock_settings)

    assert len(result) == 0
    assert result == []


@pytest.mark.asyncio
async def test_list_radius_profiles_pagination(mock_settings):
    """Test listing RADIUS profiles with pagination."""
    mock_response = {
        "data": [
            {"_id": "radius1", "name": "Profile 1"},
            {"_id": "radius2", "name": "Profile 2"},
            {"_id": "radius3", "name": "Profile 3"},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_radius_profiles(
            site_id="default", settings=mock_settings, limit=2, offset=0
        )

    assert len(result) == 2
    assert result[0]["name"] == "Profile 1"
    assert result[1]["name"] == "Profile 2"


@pytest.mark.asyncio
async def test_list_radius_profiles_with_full_config(mock_settings):
    """Test listing RADIUS profiles with full configuration."""
    mock_response = {
        "data": [
            {
                "_id": "radius_full",
                "name": "Full RADIUS Config",
                "auth_server": "192.168.2.100",
                "auth_port": 1812,
                "acct_server": "192.168.2.100",
                "acct_port": 1813,
                "enabled": True,
                "vlan_enabled": False,
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ref_module, "UniFiClient", return_value=mock_client):
        result = await list_radius_profiles(site_id="default", settings=mock_settings)

    assert len(result) == 1
    assert result[0]["name"] == "Full RADIUS Config"
    assert result[0]["auth_server"] == "192.168.2.100"
    assert result[0]["auth_port"] == 1812
    assert result[0]["acct_server"] == "192.168.2.100"
    assert result[0]["acct_port"] == 1813
