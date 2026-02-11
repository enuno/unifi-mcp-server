"""Unit tests for VPN tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.vpn as vpn_module
from src.tools.vpn import list_vpn_servers, list_vpn_tunnels


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
# list_vpn_tunnels Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_vpn_tunnels_success(mock_settings):
    """Test successful VPN tunnels listing."""
    mock_response = {
        "data": [
            {
                "_id": "tunnel1",
                "name": "Office-to-DC",
                "enabled": True,
                "peer_address": "203.0.113.10",
                "status": "connected",
            },
            {
                "_id": "tunnel2",
                "name": "Branch-to-HQ",
                "enabled": True,
                "peer_address": "198.51.100.5",
                "status": "connected",
            },
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vpn_module, "UniFiClient", return_value=mock_client):
        result = await list_vpn_tunnels("default", mock_settings)

    assert len(result) == 2
    assert result[0]["name"] == "Office-to-DC"
    assert result[1]["name"] == "Branch-to-HQ"


@pytest.mark.asyncio
async def test_list_vpn_tunnels_pagination(mock_settings):
    """Test VPN tunnels listing with pagination."""
    mock_response = {"data": [{"_id": f"tunnel{i}", "name": f"Tunnel {i}"} for i in range(10)]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vpn_module, "UniFiClient", return_value=mock_client):
        result = await list_vpn_tunnels("default", mock_settings, limit=3, offset=2)

    assert len(result) == 3
    assert result[0]["id"] == "tunnel2"


@pytest.mark.asyncio
async def test_list_vpn_tunnels_empty(mock_settings):
    """Test VPN tunnels listing with empty response."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vpn_module, "UniFiClient", return_value=mock_client):
        result = await list_vpn_tunnels("default", mock_settings)

    assert result == []


@pytest.mark.asyncio
async def test_list_vpn_tunnels_full_details(mock_settings):
    """Test VPN tunnels listing with full details."""
    mock_response = {
        "data": [
            {
                "_id": "tunnel1",
                "name": "Full Tunnel",
                "enabled": True,
                "peer_address": "203.0.113.10",
                "local_network": "192.168.1.0/24",
                "remote_network": "10.0.0.0/24",
                "status": "connected",
                "ipsec_profile": "default",
                "site_id": "default",
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vpn_module, "UniFiClient", return_value=mock_client):
        result = await list_vpn_tunnels("default", mock_settings)

    assert len(result) == 1
    tunnel = result[0]
    assert tunnel["name"] == "Full Tunnel"
    assert tunnel["local_network"] == "192.168.1.0/24"
    assert tunnel["remote_network"] == "10.0.0.0/24"
    assert tunnel["status"] == "connected"


# =============================================================================
# list_vpn_servers Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_vpn_servers_success(mock_settings):
    """Test successful VPN servers listing."""
    mock_response = {
        "data": [
            {
                "_id": "server1",
                "name": "Remote Access VPN",
                "enabled": True,
                "server_type": "L2TP",
                "network": "192.168.250.0/24",
            },
            {
                "_id": "server2",
                "name": "WireGuard VPN",
                "enabled": True,
                "server_type": "WireGuard",
                "network": "192.168.251.0/24",
            },
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vpn_module, "UniFiClient", return_value=mock_client):
        result = await list_vpn_servers("default", mock_settings)

    assert len(result) == 2
    assert result[0]["name"] == "Remote Access VPN"
    assert result[1]["name"] == "WireGuard VPN"


@pytest.mark.asyncio
async def test_list_vpn_servers_empty(mock_settings):
    """Test VPN servers listing with empty response."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vpn_module, "UniFiClient", return_value=mock_client):
        result = await list_vpn_servers("default", mock_settings)

    assert result == []


@pytest.mark.asyncio
async def test_list_vpn_servers_pagination(mock_settings):
    """Test VPN servers listing with pagination."""
    mock_response = {"data": [{"_id": f"server{i}", "name": f"Server {i}"} for i in range(5)]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vpn_module, "UniFiClient", return_value=mock_client):
        result = await list_vpn_servers("default", mock_settings, limit=2, offset=1)

    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_vpn_servers_full_details(mock_settings):
    """Test VPN servers listing with full details."""
    mock_response = {
        "data": [
            {
                "_id": "server1",
                "name": "Complete Server",
                "enabled": True,
                "server_type": "L2TP",
                "network": "192.168.250.0/24",
                "dns_servers": ["8.8.8.8", "8.8.4.4"],
                "max_connections": 50,
                "site_id": "default",
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vpn_module, "UniFiClient", return_value=mock_client):
        result = await list_vpn_servers("default", mock_settings)

    assert len(result) == 1
    server = result[0]
    assert server["name"] == "Complete Server"
    assert server["server_type"] == "L2TP"
    assert server["max_connections"] == 50
    assert server["dns_servers"] == ["8.8.8.8", "8.8.4.4"]
