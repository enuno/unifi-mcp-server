"""Unit tests for traffic flows tools.

TDD: Tests for src/tools/traffic_flows.py
Based on traffic flow monitoring functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.api_key = "test-api-key"
    settings.api_type = "local"
    settings.local_host = "192.168.2.1"
    settings.local_port = 443
    settings.local_verify_ssl = False
    settings.log_level = "INFO"
    settings.get_integration_path = MagicMock(
        side_effect=lambda endpoint: f"/proxy/network/integration/v1/{endpoint}"
    )
    return settings


@pytest.fixture
def sample_traffic_flows():
    """Sample traffic flow data from API."""
    return [
        {
            "flow_id": "flow-001",
            "site_id": "default",
            "source_ip": "192.168.2.100",
            "source_port": 54321,
            "destination_ip": "8.8.8.8",
            "destination_port": 443,
            "protocol": "tcp",
            "application_id": "app-001",
            "application_name": "HTTPS",
            "bytes_sent": 1024000,
            "bytes_received": 5120000,
            "packets_sent": 1000,
            "packets_received": 5000,
            "start_time": "2026-01-05T00:00:00Z",
            "end_time": None,
            "duration": 300,
            "client_mac": "aa:bb:cc:dd:ee:ff",
            "device_id": "device-001",
        },
        {
            "flow_id": "flow-002",
            "site_id": "default",
            "source_ip": "192.168.2.101",
            "source_port": 54322,
            "destination_ip": "1.1.1.1",
            "destination_port": 53,
            "protocol": "udp",
            "application_id": "app-002",
            "application_name": "DNS",
            "bytes_sent": 512,
            "bytes_received": 1024,
            "packets_sent": 10,
            "packets_received": 10,
            "start_time": "2026-01-05T00:01:00Z",
            "end_time": "2026-01-05T00:01:01Z",
            "duration": 1,
            "client_mac": "11:22:33:44:55:66",
            "device_id": "device-001",
        },
    ]


@pytest.fixture
def sample_flow_statistics():
    """Sample flow statistics data."""
    return {
        "site_id": "default",
        "time_range": "24h",
        "total_flows": 1000,
        "total_bytes_sent": 10240000,
        "total_bytes_received": 51200000,
        "total_bytes": 61440000,
        "total_packets_sent": 10000,
        "total_packets_received": 50000,
        "unique_sources": 50,
        "unique_destinations": 200,
        "top_applications": [
            {"application": "HTTPS", "bytes": 30000000},
            {"application": "YouTube", "bytes": 20000000},
        ],
    }


@pytest.fixture
def sample_flow_risks():
    """Sample flow risk data."""
    return [
        {
            "flow_id": "flow-001",
            "risk_score": 75.0,
            "risk_level": "high",
            "indicators": ["unusual_port", "high_volume"],
            "threat_type": "data_exfiltration",
            "description": "Potential data exfiltration detected",
        },
        {
            "flow_id": "flow-003",
            "risk_score": 30.0,
            "risk_level": "low",
            "indicators": ["new_destination"],
            "threat_type": None,
            "description": "New destination observed",
        },
    ]


class TestGetTrafficFlowsBasic:
    """Tests for get_traffic_flows basic functionality."""

    @pytest.mark.asyncio
    async def test_get_traffic_flows_success(self, mock_settings, sample_traffic_flows):
        """Successfully retrieve traffic flows."""
        from src.tools.traffic_flows import get_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await get_traffic_flows("default", mock_settings)

            assert len(result) == 2
            assert result[0]["flow_id"] == "flow-001"
            assert result[0]["source_ip"] == "192.168.2.100"
            assert result[0]["protocol"] == "tcp"

    @pytest.mark.asyncio
    async def test_get_traffic_flows_empty_response(self, mock_settings):
        """Handle sites with no traffic flows."""
        from src.tools.traffic_flows import get_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": []})

            result = await get_traffic_flows("default", mock_settings)

            assert len(result) == 0
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_traffic_flows_with_source_ip_filter(
        self, mock_settings, sample_traffic_flows
    ):
        """Filter traffic flows by source IP."""
        from src.tools.traffic_flows import get_traffic_flows

        filtered_flows = [f for f in sample_traffic_flows if f["source_ip"] == "192.168.2.100"]

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": filtered_flows})

            result = await get_traffic_flows("default", mock_settings, source_ip="192.168.2.100")

            assert len(result) == 1
            assert result[0]["source_ip"] == "192.168.2.100"
            # Verify source_ip was passed in params
            call_args = mock_instance.get.call_args
            assert "source_ip" in call_args[1].get("params", {})


class TestGetTrafficFlowsFilters:
    """Tests for get_traffic_flows filter parameters."""

    @pytest.mark.asyncio
    async def test_get_traffic_flows_with_dest_ip_filter(self, mock_settings, sample_traffic_flows):
        """Filter traffic flows by destination IP."""
        from src.tools.traffic_flows import get_traffic_flows

        filtered_flows = [f for f in sample_traffic_flows if f["destination_ip"] == "8.8.8.8"]

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": filtered_flows})

            result = await get_traffic_flows("default", mock_settings, destination_ip="8.8.8.8")

            assert len(result) == 1
            assert result[0]["destination_ip"] == "8.8.8.8"
            call_args = mock_instance.get.call_args
            assert "destination_ip" in call_args[1].get("params", {})

    @pytest.mark.asyncio
    async def test_get_traffic_flows_with_protocol_filter(
        self, mock_settings, sample_traffic_flows
    ):
        """Filter traffic flows by protocol."""
        from src.tools.traffic_flows import get_traffic_flows

        filtered_flows = [f for f in sample_traffic_flows if f["protocol"] == "udp"]

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": filtered_flows})

            result = await get_traffic_flows("default", mock_settings, protocol="udp")

            assert len(result) == 1
            assert result[0]["protocol"] == "udp"
            call_args = mock_instance.get.call_args
            assert "protocol" in call_args[1].get("params", {})

    @pytest.mark.asyncio
    async def test_get_traffic_flows_with_time_range(self, mock_settings, sample_traffic_flows):
        """Filter traffic flows by time range."""
        from src.tools.traffic_flows import get_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await get_traffic_flows("default", mock_settings, time_range="7d")

            assert len(result) == 2
            call_args = mock_instance.get.call_args
            assert call_args[1].get("params", {}).get("time_range") == "7d"


class TestGetFlowStatistics:
    """Tests for get_flow_statistics tool."""

    @pytest.mark.asyncio
    async def test_get_flow_statistics_success(self, mock_settings, sample_flow_statistics):
        """Successfully retrieve flow statistics."""
        from src.tools.traffic_flows import get_flow_statistics

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_flow_statistics})

            result = await get_flow_statistics("default", mock_settings)

            assert result["site_id"] == "default"
            assert result["total_flows"] == 1000
            assert result["total_bytes"] == 61440000

    @pytest.mark.asyncio
    async def test_get_flow_statistics_empty(self, mock_settings):
        """Handle endpoint not available gracefully."""
        from src.tools.traffic_flows import get_flow_statistics

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=Exception("Endpoint not available"))

            result = await get_flow_statistics("default", mock_settings)

            # Should return empty statistics
            assert result["site_id"] == "default"
            assert result["total_flows"] == 0
            assert result["total_bytes"] == 0

    @pytest.mark.asyncio
    async def test_get_flow_statistics_time_ranges(self, mock_settings, sample_flow_statistics):
        """Verify time_range parameter is passed correctly."""
        from src.tools.traffic_flows import get_flow_statistics

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_flow_statistics})

            await get_flow_statistics("default", mock_settings, time_range="7d")

            call_args = mock_instance.get.call_args
            assert call_args[1].get("params", {}).get("time_range") == "7d"


class TestGetTrafficFlowDetails:
    """Tests for get_traffic_flow_details tool."""

    @pytest.mark.asyncio
    async def test_get_traffic_flow_details_success(self, mock_settings, sample_traffic_flows):
        """Successfully retrieve flow details."""
        from src.tools.traffic_flows import get_traffic_flow_details

        flow = sample_traffic_flows[0]

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow})

            result = await get_traffic_flow_details("default", "flow-001", mock_settings)

            assert result["flow_id"] == "flow-001"
            assert result["source_ip"] == "192.168.2.100"
            assert result["application_name"] == "HTTPS"


class TestGetTopFlows:
    """Tests for get_top_flows tool."""

    @pytest.mark.asyncio
    async def test_get_top_flows_by_bytes(self, mock_settings, sample_traffic_flows):
        """Get top flows sorted by bytes."""
        from src.tools.traffic_flows import get_top_flows

        # Sort by total bytes (sent + received)
        sorted_flows = sorted(
            sample_traffic_flows,
            key=lambda x: x.get("bytes_sent", 0) + x.get("bytes_received", 0),
            reverse=True,
        )

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sorted_flows})

            result = await get_top_flows("default", mock_settings, limit=10, sort_by="bytes")

            assert len(result) == 2
            # First flow should have more bytes
            first_bytes = result[0]["bytes_sent"] + result[0]["bytes_received"]
            second_bytes = result[1]["bytes_sent"] + result[1]["bytes_received"]
            assert first_bytes >= second_bytes

    @pytest.mark.asyncio
    async def test_get_top_flows_by_packets(self, mock_settings, sample_traffic_flows):
        """Get top flows sorted by packets."""
        from src.tools.traffic_flows import get_top_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await get_top_flows("default", mock_settings, limit=5, sort_by="packets")

            assert len(result) == 2
            call_args = mock_instance.get.call_args
            assert call_args[1].get("params", {}).get("sort_by") == "packets"


class TestGetFlowRisks:
    """Tests for get_flow_risks tool."""

    @pytest.mark.asyncio
    async def test_get_flow_risks_success(self, mock_settings, sample_flow_risks):
        """Successfully retrieve flow risks."""
        from src.tools.traffic_flows import get_flow_risks

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_flow_risks})

            result = await get_flow_risks("default", mock_settings)

            assert len(result) == 2
            assert result[0]["risk_level"] == "high"
            assert result[0]["risk_score"] == 75.0

    @pytest.mark.asyncio
    async def test_get_flow_risks_with_min_level(self, mock_settings, sample_flow_risks):
        """Filter flow risks by minimum level."""
        from src.tools.traffic_flows import get_flow_risks

        high_risks = [r for r in sample_flow_risks if r["risk_level"] == "high"]

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": high_risks})

            result = await get_flow_risks("default", mock_settings, min_risk_level="high")

            assert len(result) == 1
            assert result[0]["risk_level"] == "high"
            call_args = mock_instance.get.call_args
            assert "min_risk_level" in call_args[1].get("params", {})


class TestGetFlowTrends:
    """Tests for get_flow_trends tool."""

    @pytest.mark.asyncio
    async def test_get_flow_trends_success(self, mock_settings):
        """Successfully retrieve flow trends."""
        from src.tools.traffic_flows import get_flow_trends

        trend_data = [
            {"timestamp": "2026-01-05T00:00:00Z", "flows": 100, "bytes": 1000000},
            {"timestamp": "2026-01-05T01:00:00Z", "flows": 150, "bytes": 1500000},
            {"timestamp": "2026-01-05T02:00:00Z", "flows": 120, "bytes": 1200000},
        ]

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": trend_data})

            result = await get_flow_trends("default", mock_settings)

            assert len(result) == 3
            assert "timestamp" in result[0]


class TestFilterTrafficFlows:
    """Tests for filter_traffic_flows tool."""

    @pytest.mark.asyncio
    async def test_filter_traffic_flows_success(self, mock_settings, sample_traffic_flows):
        """Successfully filter traffic flows."""
        from src.tools.traffic_flows import filter_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await filter_traffic_flows(
                "default", mock_settings, filter_expression="protocol = 'tcp'"
            )

            assert isinstance(result, list)
            call_args = mock_instance.get.call_args
            assert "filter" in call_args[1].get("params", {})

    @pytest.mark.asyncio
    async def test_filter_traffic_flows_with_limit(self, mock_settings, sample_traffic_flows):
        """Filter traffic flows with result limit."""
        from src.tools.traffic_flows import filter_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows[:1]})

            result = await filter_traffic_flows(
                "default",
                mock_settings,
                filter_expression="bytes > 1000",
                limit=1,
            )

            assert len(result) == 1
            call_args = mock_instance.get.call_args
            assert call_args[1].get("params", {}).get("limit") == 1

    @pytest.mark.asyncio
    async def test_filter_traffic_flows_complex_expression(
        self, mock_settings, sample_traffic_flows
    ):
        """Filter traffic flows with complex expression."""
        from src.tools.traffic_flows import filter_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await filter_traffic_flows(
                "default",
                mock_settings,
                filter_expression="bytes > 1000 AND protocol = 'tcp'",
            )

            assert isinstance(result, list)
            call_args = mock_instance.get.call_args
            params = call_args[1].get("params", {})
            assert "bytes > 1000 AND protocol = 'tcp'" in params.get("filter", "")


class TestApiErrorHandling:
    """Tests for error handling in traffic flow tools."""

    @pytest.mark.asyncio
    async def test_get_traffic_flows_api_error(self, mock_settings):
        """Handle API errors gracefully."""
        from src.tools.traffic_flows import get_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=Exception("API Error"))

            result = await get_traffic_flows("default", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_get_flow_risks_api_error(self, mock_settings):
        """Handle API errors in get_flow_risks."""
        from src.tools.traffic_flows import get_flow_risks

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=Exception("API Error"))

            result = await get_flow_risks("default", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_get_flow_trends_api_error(self, mock_settings):
        """Handle API errors in get_flow_trends."""
        from src.tools.traffic_flows import get_flow_trends

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=Exception("API Error"))

            result = await get_flow_trends("default", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_authentication_called(self, mock_settings, sample_traffic_flows):
        """Verify authentication is called when not authenticated."""
        from src.tools.traffic_flows import get_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            await get_traffic_flows("default", mock_settings)

            mock_instance.authenticate.assert_called_once()


class TestApiEndpoints:
    """Tests for API endpoint construction."""

    @pytest.mark.asyncio
    async def test_traffic_flows_endpoint(self, mock_settings, sample_traffic_flows):
        """Verify correct API endpoint for traffic flows."""
        from src.tools.traffic_flows import get_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(side_effect=lambda s: s)
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            await get_traffic_flows("test-site", mock_settings)

            call_args = mock_instance.get.call_args
            endpoint = call_args[0][0]
            assert "traffic/flows" in endpoint
            assert "test-site" in endpoint

    @pytest.mark.asyncio
    async def test_flow_statistics_endpoint(self, mock_settings, sample_flow_statistics):
        """Verify correct API endpoint for flow statistics."""
        from src.tools.traffic_flows import get_flow_statistics

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(side_effect=lambda s: s)
            mock_instance.get = AsyncMock(return_value={"data": sample_flow_statistics})

            await get_flow_statistics("test-site", mock_settings)

            call_args = mock_instance.get.call_args
            endpoint = call_args[0][0]
            assert "traffic/flows/statistics" in endpoint
            assert "test-site" in endpoint

    @pytest.mark.asyncio
    async def test_flow_risks_endpoint(self, mock_settings, sample_flow_risks):
        """Verify correct API endpoint for flow risks."""
        from src.tools.traffic_flows import get_flow_risks

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(side_effect=lambda s: s)
            mock_instance.get = AsyncMock(return_value={"data": sample_flow_risks})

            await get_flow_risks("test-site", mock_settings)

            call_args = mock_instance.get.call_args
            endpoint = call_args[0][0]
            assert "traffic/flows/risks" in endpoint
            assert "test-site" in endpoint


class TestGetConnectionStates:
    """Tests for get_connection_states tool."""

    @pytest.mark.asyncio
    async def test_get_connection_states_success(self, mock_settings, sample_traffic_flows):
        """Successfully retrieve connection states."""
        from src.tools.traffic_flows import get_connection_states

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await get_connection_states("default", mock_settings)

            assert isinstance(result, list)
            assert len(result) == 2
            assert "flow_id" in result[0]
            assert "state" in result[0]

    @pytest.mark.asyncio
    async def test_get_connection_states_active_flow(self, mock_settings):
        """Detect active connection state."""
        from src.tools.traffic_flows import get_connection_states

        active_flow = {
            "flow_id": "flow-active",
            "site_id": "default",
            "source_ip": "192.168.2.100",
            "destination_ip": "8.8.8.8",
            "protocol": "tcp",
            "bytes_sent": 1000,
            "bytes_received": 2000,
            "packets_sent": 10,
            "packets_received": 20,
            "start_time": "2026-01-05T00:12:00Z",
            "end_time": None,
            "duration": None,
        }

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": [active_flow]})

            result = await get_connection_states("default", mock_settings, time_range="1h")

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_connection_states_closed_flow(self, mock_settings):
        """Detect closed connection state."""
        from src.tools.traffic_flows import get_connection_states

        closed_flow = {
            "flow_id": "flow-closed",
            "site_id": "default",
            "source_ip": "192.168.2.100",
            "destination_ip": "8.8.8.8",
            "protocol": "tcp",
            "bytes_sent": 1000,
            "bytes_received": 2000,
            "packets_sent": 10,
            "packets_received": 20,
            "start_time": "2026-01-05T00:00:00Z",
            "end_time": "2026-01-05T00:01:00Z",
            "duration": 60,
        }

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": [closed_flow]})

            result = await get_connection_states("default", mock_settings)

            assert len(result) == 1
            assert result[0]["state"] == "closed"


class TestGetClientFlowAggregation:
    """Tests for get_client_flow_aggregation tool."""

    @pytest.mark.asyncio
    async def test_get_client_flow_aggregation_success(self, mock_settings, sample_traffic_flows):
        """Successfully retrieve client flow aggregation."""
        from src.tools.traffic_flows import get_client_flow_aggregation

        client_mac = "aa:bb:cc:dd:ee:ff"

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await get_client_flow_aggregation("default", client_mac, mock_settings)

            assert "client_mac" in result
            assert "total_bytes" in result
            assert "total_flows" in result

    @pytest.mark.asyncio
    async def test_get_client_flow_aggregation_with_time_range(
        self, mock_settings, sample_traffic_flows
    ):
        """Retrieve client aggregation with time range."""
        from src.tools.traffic_flows import get_client_flow_aggregation

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await get_client_flow_aggregation(
                "default", "aa:bb:cc:dd:ee:ff", mock_settings, time_range="7d"
            )

            assert isinstance(result, dict)
            assert "top_applications" in result


class TestBlockFlowSourceIP:
    """Tests for block_flow_source_ip tool."""

    @pytest.mark.asyncio
    async def test_block_flow_source_ip_dry_run(self, mock_settings, sample_traffic_flows):
        """Dry run block flow source IP."""
        from src.tools.traffic_flows import block_flow_source_ip

        flow = sample_traffic_flows[0]

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow})

            result = await block_flow_source_ip(
                "default",
                "flow-001",
                mock_settings,
                confirm=True,
                dry_run=True,
            )

            assert result["block_type"] == "source_ip"
            assert result["blocked_target"] == "192.168.2.100"
            assert result["rule_id"] is None

    @pytest.mark.asyncio
    async def test_block_flow_source_ip_no_confirm_error(self, mock_settings):
        """Block source IP requires confirmation."""
        from src.tools.traffic_flows import block_flow_source_ip
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await block_flow_source_ip("default", "flow-001", mock_settings, confirm=False)


class TestBlockFlowDestinationIP:
    """Tests for block_flow_destination_ip tool."""

    @pytest.mark.asyncio
    async def test_block_flow_destination_ip_dry_run(self, mock_settings, sample_traffic_flows):
        """Dry run block flow destination IP."""
        from src.tools.traffic_flows import block_flow_destination_ip

        flow = sample_traffic_flows[0]

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow})

            result = await block_flow_destination_ip(
                "default",
                "flow-001",
                mock_settings,
                confirm=True,
                dry_run=True,
            )

            assert result["block_type"] == "destination_ip"
            assert result["blocked_target"] == "8.8.8.8"

    @pytest.mark.asyncio
    async def test_block_flow_destination_ip_no_confirm_error(self, mock_settings):
        """Block destination IP requires confirmation."""
        from src.tools.traffic_flows import block_flow_destination_ip
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await block_flow_destination_ip("default", "flow-001", mock_settings, confirm=False)


class TestBlockFlowApplication:
    """Tests for block_flow_application tool."""

    @pytest.mark.asyncio
    async def test_block_flow_application_dry_run(self, mock_settings, sample_traffic_flows):
        """Dry run block flow application."""
        from src.tools.traffic_flows import block_flow_application

        flow = sample_traffic_flows[0]

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow})

            result = await block_flow_application(
                "default",
                "flow-001",
                mock_settings,
                confirm=True,
                dry_run=True,
            )

            assert result["block_type"] == "application"
            assert result["blocked_target"] == "app-001"

    @pytest.mark.asyncio
    async def test_block_flow_application_no_confirm_error(self, mock_settings):
        """Block application requires confirmation."""
        from src.tools.traffic_flows import block_flow_application
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await block_flow_application("default", "flow-001", mock_settings, confirm=False)


class TestExportTrafficFlows:
    """Tests for export_traffic_flows tool."""

    @pytest.mark.asyncio
    async def test_export_traffic_flows_json(self, mock_settings, sample_traffic_flows):
        """Export traffic flows as JSON."""
        from src.tools.traffic_flows import export_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await export_traffic_flows("default", mock_settings, export_format="json")

            assert isinstance(result, str)
            import json

            parsed = json.loads(result)
            assert len(parsed) == 2

    @pytest.mark.asyncio
    async def test_export_traffic_flows_csv(self, mock_settings, sample_traffic_flows):
        """Export traffic flows as CSV."""
        from src.tools.traffic_flows import export_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await export_traffic_flows("default", mock_settings, export_format="csv")

            assert isinstance(result, str)
            assert "flow_id" in result

    @pytest.mark.asyncio
    async def test_export_traffic_flows_with_limit(self, mock_settings, sample_traffic_flows):
        """Export traffic flows with max records limit."""
        from src.tools.traffic_flows import export_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await export_traffic_flows(
                "default", mock_settings, export_format="json", max_records=1
            )

            import json

            parsed = json.loads(result)
            assert len(parsed) == 1

    @pytest.mark.asyncio
    async def test_export_traffic_flows_unsupported_format(self, mock_settings):
        """Raise error for unsupported export format."""
        from src.tools.traffic_flows import export_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": []})

            with pytest.raises(ValueError, match="Unsupported export format"):
                await export_traffic_flows("default", mock_settings, export_format="xml")


class TestGetFlowAnalytics:
    """Tests for get_flow_analytics tool."""

    @pytest.mark.asyncio
    async def test_get_flow_analytics_success(self, mock_settings, sample_traffic_flows):
        """Successfully retrieve flow analytics."""
        from src.tools.traffic_flows import get_flow_analytics

        stats = {
            "site_id": "default",
            "time_range": "24h",
            "total_flows": 2,
            "total_bytes_sent": 1024512,
            "total_bytes_received": 5121024,
            "total_bytes": 6145536,
            "total_packets_sent": 1010,
            "total_packets_received": 5010,
            "unique_sources": 2,
            "unique_destinations": 2,
        }

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()

            def get_side_effect(endpoint, **kwargs):
                if "statistics" in endpoint:
                    return {"data": stats}
                return {"data": sample_traffic_flows}

            mock_instance.get = AsyncMock(side_effect=get_side_effect)

            result = await get_flow_analytics("default", mock_settings)

            assert "site_id" in result
            assert "statistics" in result
            assert "protocol_distribution" in result
            assert "application_distribution" in result

    @pytest.mark.asyncio
    async def test_get_flow_analytics_with_time_range(self, mock_settings, sample_traffic_flows):
        """Retrieve analytics with custom time range."""
        from src.tools.traffic_flows import get_flow_analytics

        stats = {
            "site_id": "default",
            "time_range": "7d",
            "total_flows": 2,
            "total_bytes_sent": 0,
            "total_bytes_received": 0,
            "total_bytes": 0,
            "total_packets_sent": 0,
            "total_packets_received": 0,
            "unique_sources": 0,
            "unique_destinations": 0,
        }

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()

            def get_side_effect(endpoint, **kwargs):
                if "statistics" in endpoint:
                    return {"data": stats}
                return {"data": sample_traffic_flows}

            mock_instance.get = AsyncMock(side_effect=get_side_effect)

            result = await get_flow_analytics("default", mock_settings, time_range="7d")

            assert result["time_range"] == "7d"


class TestGetTopFlowsFallback:
    """Tests for get_top_flows fallback behavior."""

    @pytest.mark.asyncio
    async def test_get_top_flows_fallback_to_manual_sort(self, mock_settings, sample_traffic_flows):
        """Test fallback when top endpoint unavailable."""
        from src.tools.traffic_flows import get_top_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()

            call_count = 0

            async def get_side_effect(endpoint, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Top endpoint not available")
                return {"data": sample_traffic_flows}

            mock_instance.get = AsyncMock(side_effect=get_side_effect)

            result = await get_top_flows("default", mock_settings, limit=1)

            assert len(result) == 1


class TestFilterTrafficFlowsFallback:
    """Tests for filter_traffic_flows fallback behavior."""

    @pytest.mark.asyncio
    async def test_filter_traffic_flows_fallback(self, mock_settings, sample_traffic_flows):
        """Test fallback when filter endpoint not available."""
        from src.tools.traffic_flows import filter_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()

            call_count = 0

            async def get_side_effect(endpoint, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Filter endpoint not available")
                return {"data": sample_traffic_flows}

            mock_instance.get = AsyncMock(side_effect=get_side_effect)

            result = await filter_traffic_flows(
                "default", mock_settings, filter_expression="protocol = 'tcp'", limit=1
            )

            assert len(result) == 1


class TestBlockFlowSourceIPExecution:
    """Tests for block_flow_source_ip actual execution."""

    @pytest.mark.asyncio
    async def test_block_flow_source_ip_execution(self, mock_settings, sample_traffic_flows):
        """Execute block flow source IP with firewall rule creation."""
        from src.tools.traffic_flows import block_flow_source_ip

        flow = sample_traffic_flows[0]

        with (
            patch("src.tools.traffic_flows.UniFiClient") as mock_client,
            patch(
                "src.tools.firewall.create_firewall_rule", new_callable=AsyncMock
            ) as mock_firewall,
            patch("src.tools.traffic_flows.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow})

            mock_firewall.return_value = {"_id": "rule-123", "name": "Block_192.168.2.100"}

            result = await block_flow_source_ip(
                "default",
                "flow-001",
                mock_settings,
                confirm=True,
                dry_run=False,
            )

            assert result["block_type"] == "source_ip"
            assert result["blocked_target"] == "192.168.2.100"
            assert result["rule_id"] == "rule-123"
            mock_firewall.assert_called_once()

    @pytest.mark.asyncio
    async def test_block_flow_source_ip_temporary(self, mock_settings, sample_traffic_flows):
        """Block source IP with temporary duration."""
        from src.tools.traffic_flows import block_flow_source_ip

        flow = sample_traffic_flows[0]

        with (
            patch("src.tools.traffic_flows.UniFiClient") as mock_client,
            patch(
                "src.tools.firewall.create_firewall_rule", new_callable=AsyncMock
            ) as mock_firewall,
            patch("src.tools.traffic_flows.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow})

            mock_firewall.return_value = {"_id": "rule-124", "name": "Block_temp"}

            result = await block_flow_source_ip(
                "default",
                "flow-001",
                mock_settings,
                duration="temporary",
                expires_in_hours=24,
                confirm=True,
                dry_run=False,
            )

            assert result["duration"] == "temporary"
            assert result["expires_at"] is not None


class TestBlockFlowDestinationIPExecution:
    """Tests for block_flow_destination_ip actual execution."""

    @pytest.mark.asyncio
    async def test_block_flow_destination_ip_execution(self, mock_settings, sample_traffic_flows):
        """Execute block flow destination IP with firewall rule creation."""
        from src.tools.traffic_flows import block_flow_destination_ip

        flow = sample_traffic_flows[0]

        with (
            patch("src.tools.traffic_flows.UniFiClient") as mock_client,
            patch(
                "src.tools.firewall.create_firewall_rule", new_callable=AsyncMock
            ) as mock_firewall,
            patch("src.tools.traffic_flows.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow})

            mock_firewall.return_value = {"_id": "rule-125", "name": "Block_8.8.8.8"}

            result = await block_flow_destination_ip(
                "default",
                "flow-001",
                mock_settings,
                confirm=True,
                dry_run=False,
            )

            assert result["block_type"] == "destination_ip"
            assert result["blocked_target"] == "8.8.8.8"
            assert result["rule_id"] == "rule-125"


class TestBlockFlowApplicationExecution:
    """Tests for block_flow_application actual execution."""

    @pytest.mark.asyncio
    async def test_block_flow_application_without_zbf(self, mock_settings, sample_traffic_flows):
        """Block application using traditional firewall (no ZBF)."""
        from src.tools.traffic_flows import block_flow_application

        flow = sample_traffic_flows[0]

        with (
            patch("src.tools.traffic_flows.UniFiClient") as mock_client,
            patch(
                "src.tools.firewall.create_firewall_rule", new_callable=AsyncMock
            ) as mock_firewall,
            patch("src.tools.traffic_flows.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow})

            mock_firewall.return_value = {"_id": "rule-126", "name": "Block_App_HTTPS"}

            result = await block_flow_application(
                "default",
                "flow-001",
                mock_settings,
                use_zbf=False,
                confirm=True,
                dry_run=False,
            )

            assert result["block_type"] == "application"
            assert result["blocked_target"] == "app-001"
            assert result["rule_id"] == "rule-126"


class TestBlockFlowErrors:
    """Tests for block flow error handling."""

    @pytest.mark.asyncio
    async def test_block_flow_source_ip_no_source_ip(self, mock_settings):
        """Handle flow with no source IP - Pydantic validation catches missing required field."""
        from pydantic import ValidationError

        from src.tools.traffic_flows import block_flow_source_ip

        flow_without_source = {
            "flow_id": "flow-bad",
            "site_id": "default",
            "destination_ip": "8.8.8.8",
            "protocol": "tcp",
            "bytes_sent": 0,
            "bytes_received": 0,
            "packets_sent": 0,
            "packets_received": 0,
            "start_time": "2026-01-05T00:00:00Z",
        }

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow_without_source})

            # Pydantic validation fails because source_ip is required in TrafficFlow model
            with pytest.raises(ValidationError, match="source_ip"):
                await block_flow_source_ip(
                    "default", "flow-bad", mock_settings, confirm=True, dry_run=False
                )

    @pytest.mark.asyncio
    async def test_block_flow_application_no_app_id(self, mock_settings):
        """Handle flow with no application ID."""
        from src.tools.traffic_flows import block_flow_application

        flow_without_app = {
            "flow_id": "flow-noapp",
            "site_id": "default",
            "source_ip": "192.168.2.100",
            "destination_ip": "8.8.8.8",
            "protocol": "tcp",
            "bytes_sent": 0,
            "bytes_received": 0,
            "packets_sent": 0,
            "packets_received": 0,
            "start_time": "2026-01-05T00:00:00Z",
            "application_id": None,
        }

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow_without_app})

            with pytest.raises(ValueError, match="No application ID found"):
                await block_flow_application(
                    "default", "flow-noapp", mock_settings, confirm=True, dry_run=False
                )


class TestExportEmptyFlows:
    """Tests for export_traffic_flows with empty data."""

    @pytest.mark.asyncio
    async def test_export_csv_empty_flows(self, mock_settings):
        """Export empty flows as CSV returns empty string."""
        from src.tools.traffic_flows import export_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": []})

            result = await export_traffic_flows("default", mock_settings, export_format="csv")

            assert result == ""

    @pytest.mark.asyncio
    async def test_export_with_include_fields(self, mock_settings, sample_traffic_flows):
        """Export with specific fields only."""
        from src.tools.traffic_flows import export_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_flows})

            result = await export_traffic_flows(
                "default",
                mock_settings,
                export_format="json",
                include_fields=["flow_id", "source_ip"],
            )

            import json

            parsed = json.loads(result)
            assert "flow_id" in parsed[0]
            assert "source_ip" in parsed[0]
            assert "destination_ip" not in parsed[0]


class TestStreamTrafficFlows:
    """Tests for stream_traffic_flows async generator."""

    @pytest.mark.asyncio
    async def test_stream_traffic_flows_single_iteration(self, mock_settings, sample_traffic_flows):
        """Stream traffic flows yields updates correctly."""
        from src.tools.traffic_flows import stream_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()

            call_count = 0

            async def get_side_effect(endpoint, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {"data": sample_traffic_flows}
                raise StopAsyncIteration()

            mock_instance.get = AsyncMock(side_effect=get_side_effect)

            with patch(
                "src.tools.traffic_flows.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep:
                mock_sleep.side_effect = StopAsyncIteration()

                updates = []
                try:
                    async for update in stream_traffic_flows("default", mock_settings):
                        updates.append(update)
                        if len(updates) >= 2:
                            break
                except StopAsyncIteration:
                    pass

                assert len(updates) == 2
                assert updates[0]["update_type"] == "new"


class TestBlockFlowApplicationWithZBF:
    """Tests for block_flow_application with ZBF enabled."""

    @pytest.mark.asyncio
    async def test_block_flow_application_zbf_fallback(self, mock_settings, sample_traffic_flows):
        """Block application falls back to firewall when ZBF fails."""
        from src.tools.traffic_flows import block_flow_application

        flow = sample_traffic_flows[0]

        with (
            patch("src.tools.traffic_flows.UniFiClient") as mock_client,
            patch(
                "src.tools.firewall.create_firewall_rule", new_callable=AsyncMock
            ) as mock_firewall,
            patch("src.tools.traffic_flows.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow})

            mock_firewall.return_value = {"_id": "rule-zbf-fallback", "name": "Block_App"}

            result = await block_flow_application(
                "default",
                "flow-001",
                mock_settings,
                use_zbf=True,
                zone_id=None,
                confirm=True,
                dry_run=False,
            )

            assert result["block_type"] == "application"
            assert result["rule_id"] == "rule-zbf-fallback"
            mock_firewall.assert_called_once()


class TestGetFlowRisksEdgeCases:
    """Tests for get_flow_risks edge cases."""

    @pytest.mark.asyncio
    async def test_get_flow_risks_with_min_level(self, mock_settings):
        """Get flow risks with minimum risk level filter."""
        from src.tools.traffic_flows import get_flow_risks

        risks = [
            {"flow_id": "flow-1", "risk_level": "high", "risk_score": 90},
            {"flow_id": "flow-2", "risk_level": "medium", "risk_score": 50},
        ]

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": risks})

            result = await get_flow_risks("default", mock_settings, min_risk_level="high")

            assert isinstance(result, list)


class TestBlockFlowDestinationIPEdgeCases:
    """Tests for block_flow_destination_ip edge cases."""

    @pytest.mark.asyncio
    async def test_block_flow_destination_ip_temporary(self, mock_settings, sample_traffic_flows):
        """Block destination IP with temporary duration."""
        from src.tools.traffic_flows import block_flow_destination_ip

        flow = sample_traffic_flows[0]

        with (
            patch("src.tools.traffic_flows.UniFiClient") as mock_client,
            patch(
                "src.tools.firewall.create_firewall_rule", new_callable=AsyncMock
            ) as mock_firewall,
            patch("src.tools.traffic_flows.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": flow})

            mock_firewall.return_value = {"_id": "rule-temp-dest", "name": "Block_8.8.8.8"}

            result = await block_flow_destination_ip(
                "default",
                "flow-001",
                mock_settings,
                duration="temporary",
                expires_in_hours=12,
                confirm=True,
                dry_run=False,
            )

            assert result["duration"] == "temporary"
            assert result["expires_at"] is not None


class TestGetTrafficFlowsEdgeCases:
    """Tests for get_traffic_flows edge cases."""

    @pytest.mark.asyncio
    async def test_get_traffic_flows_empty_response(self, mock_settings):
        """Handle empty response from API."""
        from src.tools.traffic_flows import get_traffic_flows

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.get = AsyncMock(return_value={"data": []})

            result = await get_traffic_flows("default", mock_settings)

            assert result == []
