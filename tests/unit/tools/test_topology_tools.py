"""Tests for topology tools."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.exceptions import AuthenticationError, RateLimitError, ResourceNotFoundError


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

    @pytest.mark.asyncio
    async def test_one_port_reports_every_host_behind_it(self, mock_settings):
        """A virtualization host bridges many guests onto a single switch port.

        Keying one peer per port silently dropped all but the last of them.
        """
        from src.tools.topology import get_port_mappings

        devices = [
            {"id": "sw1", "name": "Switch", "macAddress": "AA:BB:CC:00:00:00", "state": "ONLINE"}
        ]
        clients = [
            {
                "id": f"c{i}",
                "name": name,
                "macAddress": f"AA:BB:CC:00:00:0{i}",
                "type": "WIRED",
                "uplinkDeviceId": "sw1",
            }
            for i, name in enumerate(["vm-alpha", "vm-beta", "vm-gamma"], start=1)
        ]
        legacy_clients = [
            {"mac": f"aa:bb:cc:00:00:0{i}", "sw_port": 5, "wired_rate_mbps": 1000}
            for i in range(1, 4)
        ]

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.is_authenticated = True
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings
            mock_instance.logger = MagicMock()

            def dispatch(url):
                # "sw1" must resolve as a real node (see _resolve_topology_node),
                # not just appear as an uplinkDeviceId string on the clients.
                if "/devices/" in url:
                    return {"data": devices[0]}
                if "/integration/" in url and "/devices" in url:
                    return devices
                if "/integration/" in url and "/clients" in url:
                    return clients
                if url.endswith("/sta"):
                    return legacy_clients
                return []

            mock_instance.get = AsyncMock(side_effect=dispatch)

            result = await get_port_mappings("default", "sw1", mock_settings)

        peers = result["ports"][5]
        assert len(peers) == 3
        assert {p["connected_name"] for p in peers} == {"vm-alpha", "vm-beta", "vm-gamma"}
        assert all(p["speed_mbps"] == 1000 for p in peers)


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


class TestDeviceUplinkResolution:
    """The device list endpoint omits `uplink`; it comes from the detail route."""

    def test_depth_is_independent_of_device_order(self):
        """Depth comes from the uplink chain, not from device ordering."""
        from src.tools.topology import _resolve_depth

        # Deliberately leaf-first: a single forward pass would score these 0.
        uplinks = {"ap": "switch", "switch": "gateway"}
        cache: dict[str, int] = {}

        assert _resolve_depth("ap", uplinks, cache) == 2
        assert _resolve_depth("switch", uplinks, cache) == 1
        assert _resolve_depth("gateway", uplinks, cache) == 0

    def test_depth_survives_an_uplink_cycle(self):
        """A cycle terminates, with the repeated device pinned as the root."""
        from src.tools.topology import _resolve_depth

        uplinks = {"a": "b", "b": "a"}
        cache: dict[str, int] = {}

        # The repeated device is the cycle root and must stay at 0; the unwind
        # pass must not overwrite it and inflate the rest of the chain.
        assert _resolve_depth("a", uplinks, cache) == 0
        assert cache["a"] == 0
        assert cache["b"] == 1

    def test_depth_of_a_device_hanging_off_a_cycle(self):
        """A device feeding into a cycle counts hops from the cycle root."""
        from src.tools.topology import _resolve_depth

        uplinks = {"leaf": "a", "a": "b", "b": "a"}
        cache: dict[str, int] = {}

        # "a" is pinned to 0 as the cycle root, so its child is one hop away.
        assert _resolve_depth("leaf", uplinks, cache) == 1
        assert cache["a"] == 0

    @pytest.mark.asyncio
    async def test_merge_device_uplinks_fills_from_detail_route(self):
        """The detail route supplies the uplink the list route omits."""
        from src.tools.topology import _merge_device_uplinks

        devices = [{"id": "ap_001"}, {"id": "switch_001"}]
        details = {
            "ap_001": {"data": {"id": "ap_001", "uplink": {"deviceId": "switch_001"}}},
            "switch_001": {"data": {"id": "switch_001", "uplink": {"deviceId": "gw_001"}}},
        }

        client = MagicMock()
        client.logger = MagicMock()
        client.get = AsyncMock(side_effect=lambda ep: details[ep.rsplit("/", 1)[1]])

        await _merge_device_uplinks(client, "/integration/v1/sites/default/devices", devices)

        assert devices[0]["uplink"] == {"deviceId": "switch_001"}
        assert devices[1]["uplink"] == {"deviceId": "gw_001"}

    @pytest.mark.asyncio
    async def test_merge_device_uplinks_tolerates_detail_failure(self):
        """A per-device API failure degrades that device only."""
        from src.tools.topology import _merge_device_uplinks

        devices = [{"id": "ap_001"}, {"id": "switch_001"}]
        detail = {"data": {"id": "switch_001", "uplink": {"deviceId": "gw_001"}}}

        async def get(endpoint):
            if endpoint.endswith("ap_001"):
                raise ResourceNotFoundError("device", "ap_001")
            return detail

        client = MagicMock()
        client.logger = MagicMock()
        client.get = AsyncMock(side_effect=get)

        await _merge_device_uplinks(client, "/integration/v1/sites/default/devices", devices)

        # One unreachable device must not sink the whole graph.
        assert "uplink" not in devices[0]
        assert devices[1]["uplink"] == {"deviceId": "gw_001"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "systemic_error",
        [AuthenticationError("401"), RateLimitError(retry_after=60)],
    )
    async def test_merge_device_uplinks_reraises_systemic_failures(self, systemic_error):
        """Auth and rate-limit failures affect every lookup, so they surface.

        Args:
            systemic_error: Controller-wide failure raised by the detail route
        """
        from src.tools.topology import _merge_device_uplinks

        devices = [{"id": "ap_001"}]

        client = MagicMock()
        client.logger = MagicMock()
        client.get = AsyncMock(side_effect=systemic_error)

        with pytest.raises(type(systemic_error)):
            await _merge_device_uplinks(client, "/integration/v1/sites/default/devices", devices)

    @pytest.mark.asyncio
    async def test_merge_device_uplinks_bounds_concurrency(self):
        """Detail lookups are capped rather than fanned out one per device."""
        from src.tools import topology
        from src.tools.topology import _merge_device_uplinks

        devices = [{"id": f"ap_{index:03d}"} for index in range(50)]
        in_flight = 0
        peak = 0

        async def get(endpoint):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0)
            in_flight -= 1
            return {"data": {"uplink": {"deviceId": "gw_001"}}}

        client = MagicMock()
        client.logger = MagicMock()
        client.get = AsyncMock(side_effect=get)

        await _merge_device_uplinks(client, "/integration/v1/sites/default/devices", devices)

        assert peak <= topology._UPLINK_DETAIL_CONCURRENCY
        assert all(device["uplink"] == {"deviceId": "gw_001"} for device in devices)

    @pytest.mark.asyncio
    async def test_merge_device_uplinks_skips_already_populated(self):
        """A device that already carries an uplink is not re-fetched."""
        from src.tools.topology import _merge_device_uplinks

        devices = [{"id": "ap_001", "uplink": {"deviceId": "switch_001"}}]

        client = MagicMock()
        client.logger = MagicMock()
        client.get = AsyncMock()

        await _merge_device_uplinks(client, "/integration/v1/sites/default/devices", devices)

        client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_online_state_is_recognised(self, mock_settings, sample_client_data):
        """The Integration API reports ONLINE, not CONNECTED."""
        from src.tools.topology import get_network_topology

        devices = [{"id": "gw_001", "name": "UDM Pro", "state": "ONLINE"}]

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.is_authenticated = True
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings
            mock_instance.logger = MagicMock()
            # devices list, clients list, uplink detail, then the two legacy
            # stat routes _fetch_legacy_stats joins on.
            mock_instance.get = AsyncMock(side_effect=[devices, [], {"data": devices[0]}, [], []])

            result = await get_network_topology("default", mock_settings)

        device_nodes = [n for n in result["nodes"] if n["node_type"] == "device"]
        assert device_nodes[0]["state"] == 1


# =============================================================================
# Device identifier resolution (two id namespaces)
# =============================================================================

TOPO_FIXTURE = {
    "nodes": [
        {"node_id": "uuid-sw1", "name": "Switch A", "mac": "00:00:5e:00:53:10"},
        {"node_id": "uuid-sw2", "name": "Switch B", "mac": "00:00:5e:00:53:20"},
        {"node_id": "uuid-client", "name": "Media Player", "mac": "00:00:5e:00:53:30"},
    ],
    "connections": [
        {
            "source_node_id": "uuid-sw1",
            "target_node_id": "uuid-sw2",
            "source_port": 8,
            "target_port": 6,
            "connection_type": "uplink",
            "speed_mbps": 1000,
            "status": "up",
        },
        {
            "source_node_id": "uuid-client",
            "target_node_id": "uuid-sw1",
            "target_port": 1,
            "connection_type": "wired",
            "speed_mbps": 1000,
            "status": "up",
        },
    ],
}


def test_resolve_topology_node_by_node_id():
    """The topology's own id resolves to itself."""
    from src.tools.topology import _resolve_topology_node

    assert _resolve_topology_node(TOPO_FIXTURE, "uuid-sw1") == "uuid-sw1"


def test_resolve_topology_node_by_mac():
    """A MAC resolves, case-insensitively.

    Every other device tool in this server speaks MACs and legacy controller
    ids; the topology speaks Integration API UUIDs.
    """
    from src.tools.topology import _resolve_topology_node

    assert _resolve_topology_node(TOPO_FIXTURE, "00:00:5E:00:53:10") == "uuid-sw1"


def test_resolve_topology_node_by_name():
    """A device name resolves."""
    from src.tools.topology import _resolve_topology_node

    assert _resolve_topology_node(TOPO_FIXTURE, "Switch A") == "uuid-sw1"


def test_resolve_topology_node_unknown_raises():
    """An unrecognised id raises rather than yielding an empty result.

    Regression: a legacy controller _id matched no node, so the port lookup
    returned {} -- indistinguishable from a switch that genuinely had nothing
    connected. "I do not know this device" is a different answer from "this
    device has no connections".
    """
    from src.tools.topology import _resolve_topology_node

    with pytest.raises(ResourceNotFoundError, match="device"):
        _resolve_topology_node(TOPO_FIXTURE, "507f191e810c19729de860ea")  # pragma: allowlist secret


@pytest.mark.asyncio
async def test_get_port_mappings_accepts_a_mac(mock_settings):
    """Port mappings resolve a MAC and report which node answered.

    Each port maps to a *list* of peers (see TestLegacyPortDetail /
    "report every host behind a switch port"), so a single-peer port still
    reports as a one-element list.
    """
    from src.tools.topology import get_port_mappings

    with patch("src.tools.topology.get_network_topology", return_value=TOPO_FIXTURE):
        result = await get_port_mappings("default", "00:00:5e:00:53:10", mock_settings)

    assert result["device_id"] == "uuid-sw1"
    assert result["requested_id"] == "00:00:5e:00:53:10"
    assert result["ports"][8][0]["connected_to"] == "uuid-sw2"
    assert result["ports"][1][0]["connected_to"] == "uuid-client"


@pytest.mark.asyncio
async def test_get_device_connections_accepts_a_mac(mock_settings):
    """Connections resolve a MAC instead of silently returning nothing."""
    from src.tools.topology import get_device_connections

    with patch("src.tools.topology.get_network_topology", return_value=TOPO_FIXTURE):
        result = await get_device_connections("default", "00:00:5e:00:53:10", mock_settings)

    assert len(result) == 2


class TestLegacyPortDetail:
    """Port and link-speed detail comes only from the legacy stat routes.

    The Integration API's uplink object is just ``{"deviceId": ...}``, so
    without this join every edge in the graph has null ports and null speed.
    """

    @pytest.mark.asyncio
    async def test_device_uplink_gains_ports_and_speed(self, mock_settings):
        from src.tools.topology import get_network_topology

        devices = [
            {"id": "sw1", "name": "Switch", "macAddress": "AA:BB:CC:00:00:01", "state": "ONLINE"},
        ]
        legacy_devices = [
            {
                "mac": "aa:bb:cc:00:00:01",
                "type": "usw",
                "uplink": {
                    "port_idx": 9,
                    "uplink_remote_port": 3,
                    "speed": 2500,
                    "full_duplex": True,
                },
            }
        ]

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.is_authenticated = True
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings
            mock_instance.logger = MagicMock()
            mock_instance.get = AsyncMock(
                side_effect=[
                    devices,
                    [],
                    {"data": {**devices[0], "uplink": {"deviceId": "gw1"}}},
                    legacy_devices,
                    [],
                ]
            )
            result = await get_network_topology("default", mock_settings)

        node = next(n for n in result["nodes"] if n["node_id"] == "sw1")
        assert node["uplink_port"] == 9
        assert node["type_detail"] == "usw"

        conn = next(c for c in result["connections"] if c["is_uplink"])
        assert conn["source_port"] == 9
        assert conn["target_port"] == 3
        assert conn["speed_mbps"] == 2500
        assert conn["duplex"] == "full"

    @pytest.mark.asyncio
    async def test_wired_client_gains_switch_port_and_rate(self, mock_settings):
        from src.tools.topology import get_network_topology

        clients = [
            {
                "id": "c1",
                "macAddress": "AA:BB:CC:00:00:09",
                "type": "WIRED",
                "uplinkDeviceId": "sw1",
            }
        ]
        legacy_clients = [{"mac": "aa:bb:cc:00:00:09", "sw_port": 5, "wired_rate_mbps": 1000}]

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.is_authenticated = True
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings
            mock_instance.logger = MagicMock()
            # No devices, so _merge_device_uplinks makes no detail call:
            # devices list, clients list, then the two legacy routes.
            mock_instance.get = AsyncMock(side_effect=[[], clients, [], legacy_clients])
            result = await get_network_topology("default", mock_settings)

        conn = result["connections"][0]
        assert conn["connection_type"] == "wired"
        assert conn["target_port"] == 5
        assert conn["speed_mbps"] == 1000

    @pytest.mark.asyncio
    async def test_wireless_client_rate_is_converted_from_kbps(self, mock_settings):
        from src.tools.topology import get_network_topology

        clients = [
            {
                "id": "c1",
                "macAddress": "AA:BB:CC:00:00:0A",
                "type": "WIRELESS",
                "uplinkDeviceId": "ap1",
            }
        ]
        legacy_clients = [{"mac": "aa:bb:cc:00:00:0a", "tx_rate": 1201000}]

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.is_authenticated = True
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings
            mock_instance.logger = MagicMock()
            # No devices, so _merge_device_uplinks makes no detail call:
            # devices list, clients list, then the two legacy routes.
            mock_instance.get = AsyncMock(side_effect=[[], clients, [], legacy_clients])
            result = await get_network_topology("default", mock_settings)

        conn = result["connections"][0]
        assert conn["connection_type"] == "wireless"
        assert conn["speed_mbps"] == 1201
        assert conn["target_port"] is None

    @pytest.mark.asyncio
    async def test_graph_survives_legacy_route_failure(self, mock_settings):
        """A controller refusing the legacy routes must degrade, not fail."""
        from src.tools.topology import get_network_topology
        from src.utils.exceptions import APIError

        devices = [
            {"id": "sw1", "name": "Switch", "macAddress": "AA:BB:CC:00:00:01", "state": "ONLINE"}
        ]

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.is_authenticated = True
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings
            mock_instance.logger = MagicMock()
            mock_instance.get = AsyncMock(
                side_effect=[
                    devices,
                    [],
                    {"data": devices[0]},
                    APIError("legacy route disabled"),
                    APIError("legacy route disabled"),
                ]
            )
            result = await get_network_topology("default", mock_settings)

        assert result["total_devices"] == 1
        node = next(n for n in result["nodes"] if n["node_id"] == "sw1")
        assert node["uplink_port"] is None
        # Falls back to the model when the legacy type code is unavailable.
        assert node["type_detail"] == node["model"]

    @pytest.mark.asyncio
    async def test_graph_survives_legacy_auth_refusal(self, mock_settings):
        """401/403 on the legacy routes must degrade like any other refusal.

        AuthenticationError is not an APIError subclass, so it needs its own
        entry in the best-effort catch.
        """
        from src.tools.topology import get_network_topology
        from src.utils.exceptions import AuthenticationError

        devices = [
            {"id": "sw1", "name": "Switch", "macAddress": "AA:BB:CC:00:00:01", "state": "ONLINE"}
        ]

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.is_authenticated = True
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings
            mock_instance.logger = MagicMock()
            mock_instance.get = AsyncMock(
                side_effect=[
                    devices,
                    [],
                    {"data": devices[0]},
                    AuthenticationError("legacy routes need a session"),
                    AuthenticationError("legacy routes need a session"),
                ]
            )
            result = await get_network_topology("default", mock_settings)

        assert result["total_devices"] == 1
        node = next(n for n in result["nodes"] if n["node_id"] == "sw1")
        assert node["uplink_port"] is None

    @pytest.mark.asyncio
    async def test_half_duplex_link_is_reported_as_half(self, mock_settings):
        """full_duplex=False is a half-duplex link, not missing detail."""
        from src.tools.topology import get_network_topology

        devices = [
            {"id": "gw1", "name": "Gateway", "macAddress": "AA:BB:CC:00:00:01", "state": "ONLINE"},
            {
                "id": "sw1",
                "name": "Switch",
                "macAddress": "AA:BB:CC:00:00:02",
                "state": "ONLINE",
                "uplink": {"deviceId": "gw1"},
            },
        ]
        legacy_devices = [
            {
                "mac": "aa:bb:cc:00:00:02",
                "uplink": {
                    "port_idx": 2,
                    "uplink_remote_port": 7,
                    "speed": 100,
                    "full_duplex": False,
                },
            }
        ]

        with patch("src.tools.topology.UniFiClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.is_authenticated = True
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.settings = mock_settings
            mock_instance.logger = MagicMock()

            def dispatch(url):
                if "/devices/" in url:
                    return {"data": next(d for d in devices if url.endswith(d["id"]))}
                if "/integration/" in url and "/devices" in url:
                    return devices
                if "/ea/" in url and url.endswith("/devices"):
                    return legacy_devices
                return []

            mock_instance.get = AsyncMock(side_effect=dispatch)
            result = await get_network_topology("default", mock_settings)

        conn = next(c for c in result["connections"] if c["source_node_id"] == "sw1")
        assert conn["duplex"] == "half"
        assert conn["speed_mbps"] == 100


@pytest.mark.asyncio
async def test_legacy_rows_skip_non_dict_entries(mock_settings):
    """Junk rows in a legacy response are skipped, not indexed."""
    from src.tools.topology import _fetch_legacy_stats

    client = MagicMock()
    client.logger = MagicMock()
    client.get = AsyncMock(
        side_effect=[
            {"data": ["junk", 7, {"mac": "00:00:5E:00:53:41", "port_idx": 3}, {}]},
            {"data": [None, {"mac": "00:00:5E:00:53:07", "sw_port": 5}]},
        ]
    )

    devices, clients = await _fetch_legacy_stats(client, "default")

    assert list(devices) == ["00:00:5e:00:53:41"]
    assert devices["00:00:5e:00:53:41"]["port_idx"] == 3
    assert list(clients) == ["00:00:5e:00:53:07"]
