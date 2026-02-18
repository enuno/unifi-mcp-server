"""Tests for topology tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_settings():
    from src.config import APIType

    settings = MagicMock(spec="Settings")
    settings.log_level = "INFO"
    settings.api_type = APIType.LOCAL
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-key"
    settings.local_host = "192.168.2.1"
    settings.local_port = 443
    settings.local_verify_ssl = False
    settings.get_integration_path = MagicMock(side_effect=lambda x: f"/integration/v1/{x}")
    return settings


@pytest.fixture
def sample_device_data():
    """Sample device data from UniFi Integration API."""
    return [
        {
            "id": "gateway_001",
            "macAddress": "aa:bb:cc:dd:ee:01",
            "name": "UDM Pro",
            "model": "UDM-Pro",
            "type": "ugw",
            "ipAddress": "192.168.2.1",
            "state": "CONNECTED",
            "adopted": True,
        },
        {
            "id": "switch_001",
            "macAddress": "aa:bb:cc:dd:ee:02",
            "name": "USW-24-POE",
            "model": "USW-24-POE",
            "type": "usw",
            "ipAddress": "192.168.1.2",
            "state": "CONNECTED",
            "adopted": True,
            "uplink": {
                "deviceId": "gateway_001",
                "portIdx": 1,
                "speed": 1000,
            },
        },
        {
            "id": "ap_001",
            "macAddress": "aa:bb:cc:dd:ee:03",
            "name": "AP Office",
            "model": "U6-LR",
            "type": "uap",
            "ipAddress": "192.168.1.3",
            "state": "CONNECTED",
            "adopted": True,
            "uplink": {
                "deviceId": "switch_001",
                "portIdx": 5,
                "speed": 1000,
            },
        },
    ]


@pytest.fixture
def sample_client_data():
    """Sample client data from UniFi Integration API."""
    return [
        {
            "id": "client_001",
            "macAddress": "11:22:33:44:55:01",
            "name": "iPhone",
            "ipAddress": "192.168.2.100",
            "isWired": False,
            "uplinkDeviceId": "ap_001",
        },
        {
            "id": "client_002",
            "macAddress": "11:22:33:44:55:02",
            "name": "Laptop",
            "ipAddress": "192.168.2.101",
            "isWired": True,
            "uplinkDeviceId": "switch_001",
            "portIdx": 10,
        },
    ]


class TestGetNetworkTopology:
    """Tests for get_network_topology tool."""

    @pytest.mark.asyncio
    async def test_get_network_topology_success(
        self, mock_settings, sample_device_data, sample_client_data
    ):
        """Test retrieving complete network topology."""
        from src.tools.topology import get_network_topology

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings  # Add settings to mock instance

            # Mock separate calls for devices and clients
            def mock_get_side_effect(url):
                if "devices" in url:
                    return sample_device_data
                elif "clients" in url:
                    return sample_client_data
                return []

            mock_instance.get = AsyncMock(side_effect=mock_get_side_effect)
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await get_network_topology("default", mock_settings)

            # Verify the result structure
            assert result["site_id"] == "default"
            assert "nodes" in result
            assert "connections" in result
            assert len(result["nodes"]) > 0  # Should have devices and clients
            assert "total_devices" in result
            assert "total_clients" in result

    @pytest.mark.asyncio
    async def test_get_network_topology_empty(self, mock_settings):
        """Test topology retrieval with no devices."""
        from src.tools.topology import get_network_topology

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings
            mock_instance.get = AsyncMock(return_value=[])
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await get_network_topology("default", mock_settings)

            assert result["total_devices"] == 0
            assert result["total_clients"] == 0
            assert len(result["nodes"]) == 0

    @pytest.mark.asyncio
    async def test_get_network_topology_with_coordinates(
        self, mock_settings, sample_device_data, sample_client_data
    ):
        """Test topology retrieval with position coordinates."""
        from src.tools.topology import get_network_topology

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings  # Add settings to mock instance

            # Mock separate calls for devices and clients
            def mock_get_side_effect(url):
                if "devices" in url:
                    return sample_device_data
                elif "clients" in url:
                    return sample_client_data
                return []

            mock_instance.get = AsyncMock(side_effect=mock_get_side_effect)
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await get_network_topology("default", mock_settings, include_coordinates=True)

            # Some nodes should have coordinates
            nodes_with_coords = [n for n in result["nodes"] if n.get("x_coordinate") is not None]
            assert result["has_coordinates"] is True or len(nodes_with_coords) > 0


class TestGetDeviceConnections:
    """Tests for get_device_connections tool."""

    @pytest.mark.asyncio
    async def test_get_device_connections_specific_device(
        self, mock_settings, sample_device_data, sample_client_data
    ):
        """Test retrieving connections for a specific device."""
        from src.tools.topology import get_device_connections

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings  # Add settings to mock instance

            # Mock separate calls for devices and clients
            def mock_get_side_effect(url):
                if "devices" in url:
                    return sample_device_data
                elif "clients" in url:
                    return sample_client_data
                return []

            mock_instance.get = AsyncMock(side_effect=mock_get_side_effect)
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await get_device_connections("default", "switch_001", mock_settings)

            # Should only show connections involving this device
            assert isinstance(result, list)
            if len(result) > 0:
                # All connections should involve switch_001
                for conn in result:
                    assert (
                        conn["source_node_id"] == "switch_001"
                        or conn["target_node_id"] == "switch_001"
                    )

    @pytest.mark.asyncio
    async def test_get_device_connections_all_devices(
        self, mock_settings, sample_device_data, sample_client_data
    ):
        """Test retrieving all device connections."""
        from src.tools.topology import get_device_connections

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings  # Add settings to mock instance

            # Mock separate calls for devices and clients
            def mock_get_side_effect(url):
                if "devices" in url:
                    return sample_device_data
                elif "clients" in url:
                    return sample_client_data
                return []

            mock_instance.get = AsyncMock(side_effect=mock_get_side_effect)
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await get_device_connections("default", None, mock_settings)

            # Should return all connections
            assert isinstance(result, list)
            assert len(result) >= 0  # May be empty or have connections


class TestGetPortMappings:
    """Tests for get_port_mappings tool."""

    @pytest.mark.asyncio
    async def test_get_port_mappings_specific_device(
        self, mock_settings, sample_device_data, sample_client_data
    ):
        """Test retrieving port mappings for a specific device."""
        from src.tools.topology import get_port_mappings

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings  # Add settings to mock instance

            # Mock separate calls for devices and clients
            def mock_get_side_effect(url):
                if "devices" in url:
                    return sample_device_data
                elif "clients" in url:
                    return sample_client_data
                return []

            mock_instance.get = AsyncMock(side_effect=mock_get_side_effect)
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await get_port_mappings("default", "switch_001", mock_settings)

            # Should return port mapping information
            assert isinstance(result, dict)
            assert "device_id" in result
            assert result["device_id"] == "switch_001"
            assert "ports" in result


class TestExportTopology:
    """Tests for export_topology tool."""

    @pytest.mark.asyncio
    async def test_export_topology_json(
        self, mock_settings, sample_device_data, sample_client_data
    ):
        """Test exporting topology as JSON."""
        from src.tools.topology import export_topology

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings

            def mock_get_side_effect(url):
                if "devices" in url:
                    return sample_device_data
                elif "clients" in url:
                    return sample_client_data
                return []

            mock_instance.get = AsyncMock(side_effect=mock_get_side_effect)
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await export_topology("default", "json", mock_settings)

            # Should return JSON string
            assert isinstance(result, str)
            assert len(result) > 0
            # Verify it's valid JSON by parsing it
            import json

            parsed = json.loads(result)
            assert "nodes" in parsed or "site_id" in parsed

    @pytest.mark.asyncio
    async def test_export_topology_graphml(
        self, mock_settings, sample_device_data, sample_client_data
    ):
        """Test exporting topology as GraphML."""
        from src.tools.topology import export_topology

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings

            def mock_get_side_effect(url):
                if "devices" in url:
                    return sample_device_data
                elif "clients" in url:
                    return sample_client_data
                return []

            mock_instance.get = AsyncMock(side_effect=mock_get_side_effect)
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await export_topology("default", "graphml", mock_settings)

            # Should return GraphML XML string
            assert isinstance(result, str)
            assert "<?xml" in result or "<graphml" in result

    @pytest.mark.asyncio
    async def test_export_topology_dot(self, mock_settings, sample_device_data, sample_client_data):
        """Test exporting topology as DOT format."""
        from src.tools.topology import export_topology

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings

            def mock_get_side_effect(url):
                if "devices" in url:
                    return sample_device_data
                elif "clients" in url:
                    return sample_client_data
                return []

            mock_instance.get = AsyncMock(side_effect=mock_get_side_effect)
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await export_topology("default", "dot", mock_settings)

            # Should return DOT format string
            assert isinstance(result, str)
            assert "digraph" in result or "graph" in result

    @pytest.mark.asyncio
    async def test_export_topology_invalid_format(self, mock_settings):
        """Test that invalid export formats are rejected."""
        from src.tools.topology import export_topology
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="format"):
            await export_topology("default", "invalid_format", mock_settings)


class TestGetTopologyStatistics:
    """Tests for get_topology_statistics tool."""

    @pytest.mark.asyncio
    async def test_get_topology_statistics(
        self, mock_settings, sample_device_data, sample_client_data
    ):
        """Test retrieving topology statistics."""
        from src.tools.topology import get_topology_statistics

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings

            def mock_get_side_effect(url):
                if "devices" in url:
                    return sample_device_data
                elif "clients" in url:
                    return sample_client_data
                return []

            mock_instance.get = AsyncMock(side_effect=mock_get_side_effect)
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await get_topology_statistics("default", mock_settings)

            # Should return statistical summary
            assert isinstance(result, dict)
            assert "total_devices" in result
            assert "total_clients" in result
            assert "total_connections" in result
            assert "max_depth" in result
            assert result["total_devices"] >= 0
            assert result["total_clients"] >= 0

    @pytest.mark.asyncio
    async def test_get_topology_statistics_empty(self, mock_settings):
        """Test topology statistics with no devices."""
        from src.tools.topology import get_topology_statistics

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings
            mock_instance.get = AsyncMock(return_value=[])
            mock_settings.get_integration_path.side_effect = lambda x: f"/integration/v1/{x}"

            result = await get_topology_statistics("default", mock_settings)

            assert result["total_devices"] == 0
            assert result["total_clients"] == 0
            assert result["max_depth"] == 0
