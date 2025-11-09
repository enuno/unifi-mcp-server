"""Integration tests for traffic flow features."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.models.traffic_flow import (
    BlockFlowAction,
    ClientFlowAggregation,
    ConnectionState,
    FlowStreamUpdate,
    TrafficFlow,
)
from src.tools.traffic_flows import (
    block_flow_application,
    block_flow_destination_ip,
    block_flow_source_ip,
    export_traffic_flows,
    get_client_flow_aggregation,
    get_connection_states,
    get_flow_analytics,
    stream_traffic_flows,
)


@pytest.fixture
def settings():
    """Create test settings."""
    return Settings(
        api_key="test-api-key",
        api_type="cloud",
        host="api.ui.com",
        verify_ssl=True,
    )


@pytest.fixture
def sample_flow():
    """Create sample traffic flow."""
    return {
        "flow_id": "flow123",
        "site_id": "default",
        "source_ip": "192.168.1.100",
        "source_port": 50000,
        "destination_ip": "8.8.8.8",
        "destination_port": 443,
        "protocol": "tcp",
        "application_id": "app001",
        "application_name": "HTTPS",
        "bytes_sent": 1024000,
        "bytes_received": 2048000,
        "packets_sent": 1000,
        "packets_received": 2000,
        "start_time": datetime.utcnow().isoformat(),
        "end_time": None,
        "duration": None,
        "client_mac": "aa:bb:cc:dd:ee:ff",
        "device_id": "device123",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_traffic_flows(settings, sample_flow):
    """Test real-time traffic flow streaming."""
    with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
        # Setup mock
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.get.return_value = {"data": [sample_flow]}
        mock_client.return_value = mock_instance

        # Stream flows (get first update)
        stream = stream_traffic_flows("default", settings, interval_seconds=1)

        # Get first update
        update = await stream.__anext__()

        # Verify update
        assert update is not None
        assert update["update_type"] in ["new", "update", "closed"]
        assert "flow" in update
        assert update["timestamp"] is not None

        # Close stream
        await stream.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_connection_states(settings, sample_flow):
    """Test connection state tracking."""
    with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
        with patch("src.tools.traffic_flows.get_traffic_flows") as mock_get_flows:
            # Setup mocks
            mock_get_flows.return_value = [sample_flow]
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = True
            mock_client.return_value = mock_instance

            # Get connection states
            states = await get_connection_states("default", settings)

            # Verify states
            assert len(states) == 1
            assert states[0]["flow_id"] == "flow123"
            assert states[0]["state"] in ["active", "closed", "timed_out"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_client_flow_aggregation(settings, sample_flow):
    """Test client traffic aggregation."""
    with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
        with patch("src.tools.traffic_flows.get_traffic_flows") as mock_get_flows:
            with patch("src.tools.traffic_flows.get_connection_states") as mock_get_states:
                # Setup mocks
                mock_get_flows.return_value = [sample_flow]
                mock_get_states.return_value = [
                    {
                        "flow_id": "flow123",
                        "state": "active",
                        "last_seen": datetime.utcnow().isoformat(),
                        "total_duration": None,
                        "termination_reason": None,
                    }
                ]
                mock_instance = AsyncMock()
                mock_instance.__aenter__.return_value = mock_instance
                mock_instance.is_authenticated = True
                mock_client.return_value = mock_instance

                # Get aggregation
                agg = await get_client_flow_aggregation(
                    "default", "aa:bb:cc:dd:ee:ff", settings
                )

                # Verify aggregation
                assert agg["client_mac"] == "aa:bb:cc:dd:ee:ff"
                assert agg["total_flows"] == 1
                assert agg["total_bytes"] == 3072000  # 1024000 + 2048000
                assert agg["active_flows"] == 1
                assert "top_applications" in agg
                assert "top_destinations" in agg


@pytest.mark.integration
@pytest.mark.asyncio
async def test_block_flow_source_ip(settings, sample_flow):
    """Test blocking source IP from flow."""
    with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
        with patch("src.tools.traffic_flows.get_traffic_flow_details") as mock_get_details:
            with patch("src.tools.traffic_flows.create_firewall_rule") as mock_create_rule:
                with patch("src.tools.traffic_flows.audit_action") as mock_audit:
                    # Setup mocks
                    mock_get_details.return_value = sample_flow
                    mock_create_rule.return_value = {"_id": "rule123"}
                    mock_audit.return_value = None

                    mock_instance = AsyncMock()
                    mock_instance.__aenter__.return_value = mock_instance
                    mock_instance.is_authenticated = True
                    mock_client.return_value = mock_instance

                    # Block source IP
                    result = await block_flow_source_ip(
                        "default", "flow123", settings, confirm=True
                    )

                    # Verify result
                    assert result["block_type"] == "source_ip"
                    assert result["blocked_target"] == "192.168.1.100"
                    assert result["rule_id"] == "rule123"
                    assert result["duration"] == "permanent"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_block_flow_destination_ip(settings, sample_flow):
    """Test blocking destination IP from flow."""
    with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
        with patch("src.tools.traffic_flows.get_traffic_flow_details") as mock_get_details:
            with patch("src.tools.traffic_flows.create_firewall_rule") as mock_create_rule:
                with patch("src.tools.traffic_flows.audit_action") as mock_audit:
                    # Setup mocks
                    mock_get_details.return_value = sample_flow
                    mock_create_rule.return_value = {"_id": "rule124"}
                    mock_audit.return_value = None

                    mock_instance = AsyncMock()
                    mock_instance.__aenter__.return_value = mock_instance
                    mock_instance.is_authenticated = True
                    mock_client.return_value = mock_instance

                    # Block destination IP
                    result = await block_flow_destination_ip(
                        "default", "flow123", settings, confirm=True
                    )

                    # Verify result
                    assert result["block_type"] == "destination_ip"
                    assert result["blocked_target"] == "8.8.8.8"
                    assert result["rule_id"] == "rule124"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_block_flow_application(settings, sample_flow):
    """Test blocking application from flow."""
    with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
        with patch("src.tools.traffic_flows.get_traffic_flow_details") as mock_get_details:
            with patch("src.tools.traffic_flows.create_firewall_rule") as mock_create_rule:
                with patch("src.tools.traffic_flows.audit_action") as mock_audit:
                    # Setup mocks
                    mock_get_details.return_value = sample_flow
                    mock_create_rule.return_value = {"_id": "rule125"}
                    mock_audit.return_value = None

                    mock_instance = AsyncMock()
                    mock_instance.__aenter__.return_value = mock_instance
                    mock_instance.is_authenticated = True
                    mock_client.return_value = mock_instance

                    # Block application (without ZBF)
                    result = await block_flow_application(
                        "default", "flow123", settings, use_zbf=False, confirm=True
                    )

                    # Verify result
                    assert result["block_type"] == "application"
                    assert result["blocked_target"] == "app001"
                    assert result["rule_id"] == "rule125"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_traffic_flows_json(settings, sample_flow):
    """Test exporting flows to JSON."""
    with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
        with patch("src.tools.traffic_flows.get_traffic_flows") as mock_get_flows:
            # Setup mocks
            mock_get_flows.return_value = [sample_flow]
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = True
            mock_client.return_value = mock_instance

            # Export to JSON
            result = await export_traffic_flows(
                "default", settings, export_format="json"
            )

            # Verify export
            assert result is not None
            assert isinstance(result, str)
            assert "flow123" in result
            assert "192.168.1.100" in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_traffic_flows_csv(settings, sample_flow):
    """Test exporting flows to CSV."""
    with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
        with patch("src.tools.traffic_flows.get_traffic_flows") as mock_get_flows:
            # Setup mocks
            mock_get_flows.return_value = [sample_flow]
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = True
            mock_client.return_value = mock_instance

            # Export to CSV
            result = await export_traffic_flows("default", settings, export_format="csv")

            # Verify export
            assert result is not None
            assert isinstance(result, str)
            assert "flow_id" in result  # CSV header
            assert "flow123" in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_flow_analytics(settings, sample_flow):
    """Test comprehensive flow analytics."""
    with patch("src.tools.traffic_flows.UniFiClient") as mock_client:
        with patch("src.tools.traffic_flows.get_traffic_flows") as mock_get_flows:
            with patch("src.tools.traffic_flows.get_flow_statistics") as mock_get_stats:
                with patch("src.tools.traffic_flows.get_connection_states") as mock_get_states:
                    # Setup mocks
                    mock_get_flows.return_value = [sample_flow]
                    mock_get_stats.return_value = {
                        "site_id": "default",
                        "time_range": "24h",
                        "total_flows": 1,
                        "total_bytes": 3072000,
                    }
                    mock_get_states.return_value = [
                        {"flow_id": "flow123", "state": "active"}
                    ]

                    mock_instance = AsyncMock()
                    mock_instance.__aenter__.return_value = mock_instance
                    mock_instance.is_authenticated = True
                    mock_client.return_value = mock_instance

                    # Get analytics
                    analytics = await get_flow_analytics("default", settings)

                    # Verify analytics
                    assert analytics["site_id"] == "default"
                    assert analytics["total_flows"] == 1
                    assert "protocol_distribution" in analytics
                    assert "application_distribution" in analytics
                    assert "state_distribution" in analytics
                    assert analytics["protocol_distribution"]["tcp"] == 1
