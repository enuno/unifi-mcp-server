"""Unit tests for application tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.application as app_module
from src.tools.application import get_application_info


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
# get_application_info Tests - Task 18.1
# =============================================================================


@pytest.mark.asyncio
async def test_get_application_info_success(mock_settings):
    """Test successful retrieval of application info."""
    mock_response = {
        "data": {
            "version": "8.4.59",
            "build": "atag_8.4.59_12345",
            "deploymentType": "standalone",
            "capabilities": ["network", "protect", "access"],
            "systemInfo": {
                "hostname": "unifi-controller",
                "uptime": 123456,
                "platform": "linux",
            },
        }
    }

    mock_client = MagicMock()
    mock_client.is_authenticated = True
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(app_module, "UniFiClient", return_value=mock_client):
        result = await get_application_info(settings=mock_settings)

    assert result["version"] == "8.4.59"
    assert result["build"] == "atag_8.4.59_12345"
    assert result["deployment_type"] == "standalone"
    assert "network" in result["capabilities"]
    assert result["system_info"]["hostname"] == "unifi-controller"
    mock_client.get.assert_called_once_with("/integration/v1/application/info")


@pytest.mark.asyncio
async def test_get_application_info_response_format(mock_settings):
    """Test application info returns correct response format."""
    mock_response = {
        "data": {
            "version": "9.0.0",
            "build": "build_9.0.0",
            "deploymentType": "cloud",
            "capabilities": ["zbf", "traffic-flows"],
            "systemInfo": {"memory": "8GB", "cpu": "4 cores"},
        }
    }

    mock_client = MagicMock()
    mock_client.is_authenticated = True
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(app_module, "UniFiClient", return_value=mock_client):
        result = await get_application_info(settings=mock_settings)

    assert "version" in result
    assert "build" in result
    assert "deployment_type" in result
    assert "capabilities" in result
    assert "system_info" in result
    assert isinstance(result["capabilities"], list)
    assert isinstance(result["system_info"], dict)


@pytest.mark.asyncio
async def test_get_application_info_unauthenticated(mock_settings):
    """Test application info with unauthenticated client triggers auth."""
    mock_response = {
        "data": {
            "version": "8.5.0",
            "build": "build_8.5.0",
        }
    }

    mock_client = MagicMock()
    mock_client.is_authenticated = False
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(app_module, "UniFiClient", return_value=mock_client):
        result = await get_application_info(settings=mock_settings)

    mock_client.authenticate.assert_called_once()
    assert result["version"] == "8.5.0"


@pytest.mark.asyncio
async def test_get_application_info_minimal_response(mock_settings):
    """Test application info with minimal response data."""
    mock_response = {
        "version": "8.0.0",
        "build": None,
    }

    mock_client = MagicMock()
    mock_client.is_authenticated = True
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(app_module, "UniFiClient", return_value=mock_client):
        result = await get_application_info(settings=mock_settings)

    assert result["version"] == "8.0.0"
    assert result["build"] is None
    assert result["capabilities"] == []
    assert result["system_info"] == {}


@pytest.mark.asyncio
async def test_get_application_info_empty_capabilities(mock_settings):
    """Test application info with empty capabilities."""
    mock_response = {
        "data": {
            "version": "7.5.0",
            "deploymentType": "udm",
            "capabilities": [],
            "systemInfo": {},
        }
    }

    mock_client = MagicMock()
    mock_client.is_authenticated = True
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(app_module, "UniFiClient", return_value=mock_client):
        result = await get_application_info(settings=mock_settings)

    assert result["capabilities"] == []
    assert result["system_info"] == {}
    assert result["deployment_type"] == "udm"
