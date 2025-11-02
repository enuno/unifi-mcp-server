"""Unit tests for Traffic Flow monitoring tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools import traffic_flows


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings for testing."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud")
    return Settings()


@pytest.fixture
def sample_traffic_flow_data() -> dict:
    """Sample traffic flow data."""
    return {
        "data": [
            {
                "flow_id": "flow-001",
                "site_id": "default",
                "source_ip": "192.168.1.100",
                "source_port": 54321,
                "destination_ip": "8.8.8.8",
                "destination_port": 443,
                "protocol": "tcp",
                "application_id": "app-https",
                "application_name": "HTTPS",
                "bytes_sent": 1024000,
                "bytes_received": 2048000,
                "packets_sent": 1500,
                "packets_received": 2000,
                "start_time": "2025-01-01T10:00:00Z",
                "end_time": "2025-01-01T10:05:00Z",
                "duration": 300,
            },
            {
                "flow_id": "flow-002",
                "site_id": "default",
                "source_ip": "192.168.1.50",
                "destination_ip": "1.1.1.1",
                "destination_port": 53,
                "protocol": "udp",
                "bytes_sent": 512,
                "bytes_received": 1024,
                "packets_sent": 10,
                "packets_received": 10,
                "start_time": "2025-01-01T10:00:00Z",
            },
        ]
    }


@pytest.fixture
def sample_flow_statistics_data() -> dict:
    """Sample flow statistics data."""
    return {
        "data": {
            "site_id": "default",
            "time_range": "24h",
            "total_flows": 10000,
            "total_bytes_sent": 50000000,
            "total_bytes_received": 100000000,
            "total_bytes": 150000000,
            "total_packets_sent": 75000,
            "total_packets_received": 125000,
            "unique_sources": 250,
            "unique_destinations": 5000,
            "top_applications": [
                {"application": "HTTPS", "bytes": 5000000},
                {"application": "DNS", "bytes": 100000},
            ],
        }
    }


@pytest.fixture
def sample_flow_risk_data() -> dict:
    """Sample flow risk data."""
    return {
        "data": [
            {
                "flow_id": "flow-001",
                "risk_score": 85.0,
                "risk_level": "critical",
                "indicators": ["suspicious_port", "unusual_traffic_pattern"],
                "threat_type": "malware",
                "description": "Detected C2 communication pattern",
            },
            {
                "flow_id": "flow-002",
                "risk_score": 25.5,
                "risk_level": "low",
                "indicators": [],
            },
        ]
    }


class TestTrafficFlowTools:
    """Test suite for traffic flow monitoring tools."""

    @pytest.mark.asyncio
    async def test_get_traffic_flows_minimal(
        self, mock_settings: Settings, sample_traffic_flow_data: dict
    ) -> None:
        """Test getting traffic flows with minimal parameters."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=sample_traffic_flow_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_traffic_flows("default", mock_settings)

            assert len(result) == 2
            assert result[0]["flow_id"] == "flow-001"
            assert result[0]["source_ip"] == "192.168.1.100"
            assert result[1]["flow_id"] == "flow-002"
            mock_instance.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_traffic_flows_with_filters(
        self, mock_settings: Settings, sample_traffic_flow_data: dict
    ) -> None:
        """Test getting traffic flows with filters."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=sample_traffic_flow_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_traffic_flows(
                "default",
                mock_settings,
                source_ip="192.168.1.100",
                destination_ip="8.8.8.8",
                protocol="tcp",
                application_id="app-https",
                time_range="12h",
                limit=10,
                offset=0,
            )

            assert len(result) == 2
            # Verify params were passed to API call
            call_args = mock_instance.get.call_args
            assert call_args[1]["params"]["source_ip"] == "192.168.1.100"
            assert call_args[1]["params"]["protocol"] == "tcp"
            assert call_args[1]["params"]["time_range"] == "12h"

    @pytest.mark.asyncio
    async def test_get_traffic_flows_endpoint_not_available(
        self, mock_settings: Settings
    ) -> None:
        """Test getting traffic flows when endpoint is not available."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(side_effect=Exception("404 not found"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_traffic_flows("default", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_get_flow_statistics(
        self, mock_settings: Settings, sample_flow_statistics_data: dict
    ) -> None:
        """Test getting flow statistics."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=sample_flow_statistics_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_flow_statistics(
                "default", mock_settings, time_range="7d"
            )

            assert result["site_id"] == "default"
            assert result["total_flows"] == 10000
            assert result["total_bytes"] == 150000000
            assert len(result["top_applications"]) == 2

    @pytest.mark.asyncio
    async def test_get_flow_statistics_endpoint_not_available(
        self, mock_settings: Settings
    ) -> None:
        """Test getting flow statistics when endpoint is not available."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(side_effect=Exception("404 not found"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_flow_statistics("default", mock_settings)

            # Should return empty statistics instead of raising error
            assert result["site_id"] == "default"
            assert result["time_range"] == "24h"
            assert result["total_flows"] == 0

    @pytest.mark.asyncio
    async def test_get_traffic_flow_details(
        self, mock_settings: Settings
    ) -> None:
        """Test getting details for a specific traffic flow."""
        flow_data = {
            "data": {
                "flow_id": "flow-123",
                "site_id": "default",
                "source_ip": "192.168.1.100",
                "destination_ip": "8.8.8.8",
                "protocol": "tcp",
                "bytes_sent": 1024000,
                "bytes_received": 2048000,
                "packets_sent": 1500,
                "packets_received": 2000,
                "start_time": "2025-01-01T10:00:00Z",
            }
        }

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=flow_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_traffic_flow_details(
                "default", "flow-123", mock_settings
            )

            assert result["flow_id"] == "flow-123"
            assert result["source_ip"] == "192.168.1.100"
            assert result["bytes_sent"] == 1024000

    @pytest.mark.asyncio
    async def test_get_top_flows(
        self, mock_settings: Settings, sample_traffic_flow_data: dict
    ) -> None:
        """Test getting top bandwidth-consuming flows."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=sample_traffic_flow_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_top_flows(
                "default",
                mock_settings,
                limit=5,
                time_range="12h",
                sort_by="bytes",
            )

            assert len(result) == 2
            assert result[0]["flow_id"] == "flow-001"

    @pytest.mark.asyncio
    async def test_get_top_flows_with_fallback(
        self, mock_settings: Settings, sample_traffic_flow_data: dict
    ) -> None:
        """Test getting top flows with fallback when endpoint not available."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            # First call fails, second call (fallback) succeeds
            mock_instance.get = AsyncMock(
                side_effect=[Exception("404"), sample_traffic_flow_data]
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_top_flows(
                "default", mock_settings, limit=2
            )

            # Should return flows sorted by bytes (flow-001 has more bytes)
            assert len(result) == 2
            assert result[0]["flow_id"] == "flow-001"
            assert result[0]["bytes_sent"] + result[0]["bytes_received"] > \
                   result[1]["bytes_sent"] + result[1]["bytes_received"]

    @pytest.mark.asyncio
    async def test_get_flow_risks(
        self, mock_settings: Settings, sample_flow_risk_data: dict
    ) -> None:
        """Test getting flow risk assessments."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=sample_flow_risk_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_flow_risks(
                "default", mock_settings, time_range="24h"
            )

            assert len(result) == 2
            assert result[0]["flow_id"] == "flow-001"
            assert result[0]["risk_level"] == "critical"
            assert result[0]["risk_score"] == 85.0

    @pytest.mark.asyncio
    async def test_get_flow_risks_with_min_level(
        self, mock_settings: Settings, sample_flow_risk_data: dict
    ) -> None:
        """Test getting flow risks with minimum risk level filter."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=sample_flow_risk_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_flow_risks(
                "default", mock_settings, min_risk_level="high"
            )

            # Verify params were passed
            call_args = mock_instance.get.call_args
            assert call_args[1]["params"]["min_risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_get_flow_risks_endpoint_not_available(
        self, mock_settings: Settings
    ) -> None:
        """Test getting flow risks when endpoint not available."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(side_effect=Exception("404 not found"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_flow_risks("default", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_get_flow_trends(self, mock_settings: Settings) -> None:
        """Test getting historical flow trends."""
        trend_data = {
            "data": [
                {"timestamp": "2025-01-01T00:00:00Z", "total_bytes": 1000000},
                {"timestamp": "2025-01-01T01:00:00Z", "total_bytes": 1500000},
                {"timestamp": "2025-01-01T02:00:00Z", "total_bytes": 2000000},
            ]
        }

        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=trend_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_flow_trends(
                "default", mock_settings, time_range="7d", interval="1h"
            )

            assert len(result) == 3
            assert result[0]["timestamp"] == "2025-01-01T00:00:00Z"
            assert result[0]["total_bytes"] == 1000000

    @pytest.mark.asyncio
    async def test_get_flow_trends_endpoint_not_available(
        self, mock_settings: Settings
    ) -> None:
        """Test getting flow trends when endpoint not available."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(side_effect=Exception("404 not found"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.get_flow_trends("default", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_filter_traffic_flows(
        self, mock_settings: Settings, sample_traffic_flow_data: dict
    ) -> None:
        """Test filtering traffic flows with complex expression."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=sample_traffic_flow_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.filter_traffic_flows(
                "default",
                mock_settings,
                filter_expression="bytes > 1000000 AND protocol = 'tcp'",
                time_range="12h",
                limit=10,
            )

            assert len(result) == 2
            # Verify filter expression was passed
            call_args = mock_instance.get.call_args
            assert call_args[1]["params"]["filter"] == "bytes > 1000000 AND protocol = 'tcp'"

    @pytest.mark.asyncio
    async def test_filter_traffic_flows_with_fallback(
        self, mock_settings: Settings, sample_traffic_flow_data: dict
    ) -> None:
        """Test filtering traffic flows with fallback when endpoint not available."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            # First call fails, second call (fallback) succeeds
            mock_instance.get = AsyncMock(
                side_effect=[Exception("404"), sample_traffic_flow_data]
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.filter_traffic_flows(
                "default",
                mock_settings,
                filter_expression="bytes > 1000000",
                limit=1,
            )

            # Should return limited results from fallback
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_filter_traffic_flows_no_limit_fallback(
        self, mock_settings: Settings, sample_traffic_flow_data: dict
    ) -> None:
        """Test filtering traffic flows without limit in fallback."""
        with patch("src.tools.traffic_flows.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(
                side_effect=[Exception("404"), sample_traffic_flow_data]
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await traffic_flows.filter_traffic_flows(
                "default",
                mock_settings,
                filter_expression="protocol = 'tcp'",
            )

            # Should return all results when no limit specified
            assert len(result) == 2
