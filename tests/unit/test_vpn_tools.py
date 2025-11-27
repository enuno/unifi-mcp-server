"""Unit tests for VPN tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.vpn import list_vpn_servers, list_vpn_tunnels


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
    return Settings(_env_file=None)


class TestListVPNTunnels:
    """Test suite for list_vpn_tunnels function."""

    @pytest.mark.asyncio
    async def test_list_tunnels_success(self, mock_settings: Settings) -> None:
        """Test listing VPN tunnels successfully."""
        mock_data = {
            "data": [
                {
                    "_id": "tunnel1",
                    "name": "Office-to-DC",
                    "enabled": True,
                    "peer_address": "203.0.113.10",
                    "local_network": "192.168.1.0/24",
                    "remote_network": "10.0.0.0/24",
                    "status": "connected",
                },
                {
                    "_id": "tunnel2",
                    "name": "Branch-VPN",
                    "enabled": True,
                    "peer_address": "203.0.113.20",
                    "local_network": "192.168.2.0/24",
                    "remote_network": "10.1.0.0/24",
                    "status": "disconnected",
                },
            ]
        }

        with patch("src.tools.vpn.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_vpn_tunnels("site-123", mock_settings)

            assert len(result) == 2
            assert result[0]["name"] == "Office-to-DC"
            assert result[0]["status"] == "connected"
            assert result[1]["name"] == "Branch-VPN"
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_tunnels_empty(self, mock_settings: Settings) -> None:
        """Test listing VPN tunnels when none exist."""
        mock_data = {"data": []}

        with patch("src.tools.vpn.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_vpn_tunnels("site-123", mock_settings)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_tunnels_pagination(self, mock_settings: Settings) -> None:
        """Test listing VPN tunnels with pagination."""
        mock_data = {
            "data": [
                {
                    "_id": f"tunnel{i}",
                    "name": f"VPN Tunnel {i}",
                    "enabled": True,
                    "status": "connected",
                }
                for i in range(10)
            ]
        }

        with patch("src.tools.vpn.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_vpn_tunnels("site-123", mock_settings, limit=5, offset=2)

            assert len(result) == 5
            assert result[0]["name"] == "VPN Tunnel 2"


class TestListVPNServers:
    """Test suite for list_vpn_servers function."""

    @pytest.mark.asyncio
    async def test_list_servers_success(self, mock_settings: Settings) -> None:
        """Test listing VPN servers successfully."""
        mock_data = {
            "data": [
                {
                    "_id": "server1",
                    "name": "Remote Access VPN",
                    "enabled": True,
                    "server_type": "L2TP",
                    "network": "192.168.250.0/24",
                    "max_connections": 50,
                },
                {
                    "_id": "server2",
                    "name": "PPTP VPN",
                    "enabled": False,
                    "server_type": "PPTP",
                    "network": "192.168.251.0/24",
                    "max_connections": 25,
                },
            ]
        }

        with patch("src.tools.vpn.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_vpn_servers("site-123", mock_settings)

            assert len(result) == 2
            assert result[0]["name"] == "Remote Access VPN"
            assert result[0]["server_type"] == "L2TP"
            assert result[1]["enabled"] is False
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_servers_empty(self, mock_settings: Settings) -> None:
        """Test listing VPN servers when none exist."""
        mock_data = {"data": []}

        with patch("src.tools.vpn.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_vpn_servers("site-123", mock_settings)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_servers_pagination(self, mock_settings: Settings) -> None:
        """Test listing VPN servers with pagination."""
        mock_data = {
            "data": [
                {
                    "_id": f"server{i}",
                    "name": f"VPN Server {i}",
                    "enabled": True,
                    "server_type": "L2TP",
                }
                for i in range(10)
            ]
        }

        with patch("src.tools.vpn.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_vpn_servers("site-123", mock_settings, limit=3, offset=1)

            assert len(result) == 3
            assert result[0]["name"] == "VPN Server 1"
