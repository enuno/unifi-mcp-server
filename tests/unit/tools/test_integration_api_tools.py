"""Unit tests for integration API tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.integration_api import (
    get_integration_client,
    get_integration_device,
    get_integration_dns_policy,
    get_integration_wifi_broadcast,
    list_dpi_application_categories,
    list_integration_clients,
    list_integration_device_tags,
    list_integration_devices,
    list_integration_dns_policies,
    list_integration_networks,
    list_integration_sites,
    list_integration_vpn_servers,
    list_integration_wans,
    list_integration_wifi_broadcasts,
)


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.get_integration_path = lambda endpoint: f"/integration/v1/{endpoint}"
    return settings


@pytest.fixture
def mock_client():
    """Create a mock UniFiClient."""
    client = AsyncMock()
    client.resolve_site_id = AsyncMock(return_value="default")
    return client


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_integration_sites_success(mock_settings, mock_client):
    """Test listing integration API sites."""
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 2,
        "totalCount": 2,
        "data": [
            {"id": "site-uuid-1", "internalReference": "default", "name": "Default"},
            {"id": "site-uuid-2", "internalReference": "home", "name": "Home"},
        ],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await list_integration_sites(mock_settings)

    assert result["count"] == 2
    assert len(result["data"]) == 2
    assert result["data"][0]["id"] == "site-uuid-1"


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_integration_devices_success(mock_settings, mock_client):
    """Test listing integration API devices."""
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 1,
        "totalCount": 1,
        "data": [
            {
                "id": "dev-uuid-1",
                "macAddress": "aa:bb:cc:dd:ee:ff",
                "ipAddress": "192.168.1.1",
                "name": "USG",
                "model": "USG",
                "state": "ONLINE",
                "supported": True,
                "firmwareVersion": "4.4.50",
                "firmwareUpdatable": False,
                "features": {"switching": {}},
                "interfaces": {"ports": [{"idx": 1, "state": "UP"}], "radios": []},
            }
        ],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await list_integration_devices("default", mock_settings)

    assert result["count"] == 1
    assert result["data"][0]["id"] == "dev-uuid-1"
    assert result["data"][0]["macAddress"] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.asyncio
async def test_get_integration_device_success(mock_settings, mock_client):
    """Test getting a single integration API device."""
    mock_response = {
        "id": "dev-uuid-1",
        "macAddress": "aa:bb:cc:dd:ee:ff",
        "name": "USG",
        "model": "USG",
        "state": "ONLINE",
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await get_integration_device("default", "dev-uuid-1", mock_settings)

    assert result["id"] == "dev-uuid-1"
    assert result["name"] == "USG"


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_integration_clients_success(mock_settings, mock_client):
    """Test listing integration API clients."""
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 1,
        "totalCount": 1,
        "data": [
            {
                "type": "WIRED",
                "id": "client-uuid-1",
                "name": "Workstation",
                "connectedAt": "2024-01-01T00:00:00Z",
                "ipAddress": "192.168.1.100",
                "access": None,
            }
        ],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await list_integration_clients("default", mock_settings)

    assert result["count"] == 1
    assert result["data"][0]["id"] == "client-uuid-1"


@pytest.mark.asyncio
async def test_get_integration_client_success(mock_settings, mock_client):
    """Test getting a single integration API client."""
    mock_response = {
        "type": "WIRELESS",
        "id": "client-uuid-2",
        "name": "Phone",
        "connectedAt": "2024-01-01T00:00:00Z",
        "ipAddress": "192.168.1.101",
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await get_integration_client("default", "client-uuid-2", mock_settings)

    assert result["id"] == "client-uuid-2"
    assert result["name"] == "Phone"


# ---------------------------------------------------------------------------
# Networks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_integration_networks_success(mock_settings, mock_client):
    """Test listing integration API networks."""
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 1,
        "totalCount": 1,
        "data": [
            {
                "management": "lan",
                "id": "net-uuid-1",
                "name": "LAN",
                "enabled": True,
                "vlanId": 1,
                "metadata": {"origin": "user"},
                "default": True,
            }
        ],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await list_integration_networks("default", mock_settings)

    assert result["count"] == 1
    assert result["data"][0]["id"] == "net-uuid-1"
    assert result["data"][0]["vlanId"] == 1


# ---------------------------------------------------------------------------
# WiFi Broadcasts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_integration_wifi_broadcasts_success(mock_settings, mock_client):
    """Test listing WiFi broadcasts."""
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 1,
        "totalCount": 1,
        "data": [
            {
                "type": "ssid",
                "id": "wifi-uuid-1",
                "name": "HomeWiFi",
                "enabled": True,
                "metadata": {"origin": "user"},
                "network": {"type": "corporate"},
                "securityConfiguration": {"type": "WPA2"},
                "broadcastingDeviceFilter": {"type": "all"},
            }
        ],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await list_integration_wifi_broadcasts("default", mock_settings)

    assert result["count"] == 1
    assert result["data"][0]["id"] == "wifi-uuid-1"
    assert result["data"][0]["name"] == "HomeWiFi"


@pytest.mark.asyncio
async def test_get_integration_wifi_broadcast_success(mock_settings, mock_client):
    """Test getting a single WiFi broadcast."""
    mock_response = {
        "type": "ssid",
        "id": "wifi-uuid-1",
        "name": "HomeWiFi",
        "enabled": True,
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await get_integration_wifi_broadcast("default", "wifi-uuid-1", mock_settings)

    assert result["id"] == "wifi-uuid-1"


# ---------------------------------------------------------------------------
# DNS Policies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_integration_dns_policies_success(mock_settings, mock_client):
    """Test listing DNS policies."""
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 1,
        "totalCount": 1,
        "data": [
            {
                "type": "block",
                "id": "dns-uuid-1",
                "enabled": True,
                "metadata": {"origin": "user"},
                "domain": "example.com",
            }
        ],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await list_integration_dns_policies("default", mock_settings)

    assert result["count"] == 1
    assert result["data"][0]["domain"] == "example.com"


@pytest.mark.asyncio
async def test_get_integration_dns_policy_success(mock_settings, mock_client):
    """Test getting a single DNS policy."""
    mock_response = {
        "type": "block",
        "id": "dns-uuid-1",
        "enabled": True,
        "domain": "example.com",
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await get_integration_dns_policy("default", "dns-uuid-1", mock_settings)

    assert result["id"] == "dns-uuid-1"


# ---------------------------------------------------------------------------
# WANs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_integration_wans_success(mock_settings, mock_client):
    """Test listing WAN connections."""
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 1,
        "totalCount": 1,
        "data": [{"id": "wan-uuid-1", "name": "WAN1"}],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await list_integration_wans("default", mock_settings)

    assert result["count"] == 1
    assert result["data"][0]["name"] == "WAN1"


# ---------------------------------------------------------------------------
# VPN Servers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_integration_vpn_servers_success(mock_settings, mock_client):
    """Test listing VPN servers."""
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 1,
        "totalCount": 1,
        "data": [
            {
                "type": "l2tp",
                "id": "vpn-uuid-1",
                "name": "Remote Access",
                "enabled": True,
                "metadata": {"origin": "user"},
            }
        ],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await list_integration_vpn_servers("default", mock_settings)

    assert result["count"] == 1
    assert result["data"][0]["name"] == "Remote Access"


# ---------------------------------------------------------------------------
# Device Tags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_integration_device_tags_success(mock_settings, mock_client):
    """Test listing device tags."""
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 1,
        "totalCount": 1,
        "data": [
            {
                "id": "tag-uuid-1",
                "name": "Production",
                "deviceIds": ["dev-uuid-1"],
                "metadata": {"origin": "user"},
            }
        ],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await list_integration_device_tags("default", mock_settings)

    assert result["count"] == 1
    assert result["data"][0]["name"] == "Production"


# ---------------------------------------------------------------------------
# DPI Categories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_dpi_application_categories_success(mock_settings, mock_client):
    """Test listing DPI application categories."""
    mock_response = {
        "offset": 0,
        "limit": 10,
        "count": 2,
        "totalCount": 2,
        "data": [
            {"id": 1, "name": "Streaming"},
            {"id": 2, "name": "Gaming"},
        ],
    }
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.tools.integration_api.UniFiClient", return_value=mock_client):
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        result = await list_dpi_application_categories(mock_settings)

    assert result["count"] == 2
    assert result["data"][0]["id"] == 1
    assert result["data"][1]["name"] == "Gaming"
