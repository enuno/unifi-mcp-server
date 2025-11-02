"""Unit tests for new v0.2.0 models (ZBF, Traffic Flows, Site Manager)."""

import pytest
from pydantic import ValidationError

from src.models.site_manager import (
    CrossSiteStatistics,
    InternetHealthMetrics,
    SiteHealthSummary,
    VantagePoint,
)
from src.models.traffic_flow import FlowRisk, FlowStatistics, FlowView, TrafficFlow
from src.models.zbf_matrix import (
    ApplicationBlockRule,
    ZoneNetworkAssignment,
    ZonePolicy,
    ZonePolicyMatrix,
)

# ============================================================================
# Zone-Based Firewall Models Tests
# ============================================================================


class TestZonePolicy:
    """Test suite for ZonePolicy model."""

    def test_zone_policy_creation_minimal(self) -> None:
        """Test zone policy creation with minimal required fields."""
        policy = ZonePolicy(
            source_zone_id="zone-lan",
            destination_zone_id="zone-wan",
            action="allow",
        )
        assert policy.source_zone_id == "zone-lan"
        assert policy.destination_zone_id == "zone-wan"
        assert policy.action == "allow"
        assert policy.description is None
        assert policy.priority is None
        assert policy.enabled is True

    def test_zone_policy_creation_full(self) -> None:
        """Test zone policy creation with all fields."""
        policy = ZonePolicy(
            source_zone_id="zone-lan",
            destination_zone_id="zone-dmz",
            action="deny",
            description="Block LAN to DMZ traffic",
            priority=100,
            enabled=False,
        )
        assert policy.source_zone_id == "zone-lan"
        assert policy.destination_zone_id == "zone-dmz"
        assert policy.action == "deny"
        assert policy.description == "Block LAN to DMZ traffic"
        assert policy.priority == 100
        assert policy.enabled is False

    def test_zone_policy_invalid_action(self) -> None:
        """Test zone policy with invalid action."""
        with pytest.raises(ValidationError):
            ZonePolicy(
                source_zone_id="zone-lan",
                destination_zone_id="zone-wan",
                action="reject",  # Invalid action
            )

    def test_zone_policy_missing_required_fields(self) -> None:
        """Test zone policy missing required fields."""
        with pytest.raises(ValidationError):
            ZonePolicy(source_zone_id="zone-lan")  # Missing required fields


class TestApplicationBlockRule:
    """Test suite for ApplicationBlockRule model."""

    def test_application_block_rule_minimal(self) -> None:
        """Test application block rule with minimal fields."""
        rule = ApplicationBlockRule(
            zone_id="zone-guest",
            application_id="app-001",
            action="block",
        )
        assert rule.zone_id == "zone-guest"
        assert rule.application_id == "app-001"
        assert rule.action == "block"
        assert rule.application_name is None
        assert rule.enabled is True
        assert rule.description is None

    def test_application_block_rule_full(self) -> None:
        """Test application block rule with all fields."""
        rule = ApplicationBlockRule(
            zone_id="zone-iot",
            application_id="app-social-media",
            application_name="Facebook",
            action="block",
            enabled=True,
            description="Block social media on IoT devices",
        )
        assert rule.zone_id == "zone-iot"
        assert rule.application_id == "app-social-media"
        assert rule.application_name == "Facebook"
        assert rule.action == "block"
        assert rule.enabled is True
        assert rule.description == "Block social media on IoT devices"

    def test_application_block_rule_allow_action(self) -> None:
        """Test application block rule with allow action."""
        rule = ApplicationBlockRule(
            zone_id="zone-lan",
            application_id="app-business",
            action="allow",
        )
        assert rule.action == "allow"

    def test_application_block_rule_invalid_action(self) -> None:
        """Test application block rule with invalid action."""
        with pytest.raises(ValidationError):
            ApplicationBlockRule(
                zone_id="zone-lan",
                application_id="app-001",
                action="drop",  # Invalid action
            )


class TestZonePolicyMatrix:
    """Test suite for ZonePolicyMatrix model."""

    def test_zone_policy_matrix_minimal(self) -> None:
        """Test zone policy matrix with minimal fields."""
        matrix = ZonePolicyMatrix(site_id="default", zones=["zone-lan", "zone-wan"])
        assert matrix.site_id == "default"
        assert matrix.zones == ["zone-lan", "zone-wan"]
        assert matrix.policies == []
        assert matrix.default_policy == "allow"

    def test_zone_policy_matrix_with_policies(self) -> None:
        """Test zone policy matrix with policies."""
        policies = [
            ZonePolicy(
                source_zone_id="zone-lan",
                destination_zone_id="zone-wan",
                action="allow",
            ),
            ZonePolicy(
                source_zone_id="zone-guest",
                destination_zone_id="zone-lan",
                action="deny",
            ),
        ]
        matrix = ZonePolicyMatrix(
            site_id="site-123",
            zones=["zone-lan", "zone-wan", "zone-guest"],
            policies=policies,
            default_policy="deny",
        )
        assert matrix.site_id == "site-123"
        assert len(matrix.zones) == 3
        assert len(matrix.policies) == 2
        assert matrix.default_policy == "deny"
        assert matrix.policies[0].action == "allow"
        assert matrix.policies[1].action == "deny"

    def test_zone_policy_matrix_default_policy(self) -> None:
        """Test zone policy matrix default policy values."""
        matrix = ZonePolicyMatrix(site_id="default", zones=[], default_policy="deny")
        assert matrix.default_policy == "deny"


class TestZoneNetworkAssignment:
    """Test suite for ZoneNetworkAssignment model."""

    def test_zone_network_assignment_minimal(self) -> None:
        """Test zone network assignment with minimal fields."""
        assignment = ZoneNetworkAssignment(zone_id="zone-lan", network_id="net-001")
        assert assignment.zone_id == "zone-lan"
        assert assignment.network_id == "net-001"
        assert assignment.network_name is None
        assert assignment.assigned_at is None

    def test_zone_network_assignment_full(self) -> None:
        """Test zone network assignment with all fields."""
        assignment = ZoneNetworkAssignment(
            zone_id="zone-dmz",
            network_id="net-dmz-001",
            network_name="DMZ Network",
            assigned_at="2025-01-01T12:00:00Z",
        )
        assert assignment.zone_id == "zone-dmz"
        assert assignment.network_id == "net-dmz-001"
        assert assignment.network_name == "DMZ Network"
        assert assignment.assigned_at == "2025-01-01T12:00:00Z"


# ============================================================================
# Traffic Flow Models Tests
# ============================================================================


class TestTrafficFlow:
    """Test suite for TrafficFlow model."""

    def test_traffic_flow_minimal(self) -> None:
        """Test traffic flow creation with minimal fields."""
        flow = TrafficFlow(
            flow_id="flow-001",
            site_id="default",
            source_ip="192.168.1.100",
            destination_ip="8.8.8.8",
            protocol="tcp",
            start_time="2025-01-01T10:00:00Z",
        )
        assert flow.flow_id == "flow-001"
        assert flow.site_id == "default"
        assert flow.source_ip == "192.168.1.100"
        assert flow.destination_ip == "8.8.8.8"
        assert flow.protocol == "tcp"
        assert flow.source_port is None
        assert flow.destination_port is None
        assert flow.bytes_sent == 0
        assert flow.bytes_received == 0
        assert flow.packets_sent == 0
        assert flow.packets_received == 0

    def test_traffic_flow_full(self) -> None:
        """Test traffic flow creation with all fields."""
        flow = TrafficFlow(
            flow_id="flow-002",
            site_id="site-123",
            source_ip="192.168.1.50",
            source_port=54321,
            destination_ip="1.1.1.1",
            destination_port=443,
            protocol="tcp",
            application_id="app-https",
            application_name="HTTPS",
            bytes_sent=1024000,
            bytes_received=2048000,
            packets_sent=1500,
            packets_received=2000,
            start_time="2025-01-01T10:00:00Z",
            end_time="2025-01-01T10:05:00Z",
            duration=300,
            client_mac="aa:bb:cc:dd:ee:ff",
            device_id="device-ap-001",
        )
        assert flow.flow_id == "flow-002"
        assert flow.source_port == 54321
        assert flow.destination_port == 443
        assert flow.application_id == "app-https"
        assert flow.application_name == "HTTPS"
        assert flow.bytes_sent == 1024000
        assert flow.bytes_received == 2048000
        assert flow.packets_sent == 1500
        assert flow.packets_received == 2000
        assert flow.duration == 300
        assert flow.client_mac == "aa:bb:cc:dd:ee:ff"

    def test_traffic_flow_udp_protocol(self) -> None:
        """Test traffic flow with UDP protocol."""
        flow = TrafficFlow(
            flow_id="flow-003",
            site_id="default",
            source_ip="192.168.1.100",
            destination_ip="8.8.4.4",
            protocol="udp",
            destination_port=53,
            start_time="2025-01-01T10:00:00Z",
        )
        assert flow.protocol == "udp"
        assert flow.destination_port == 53


class TestFlowStatistics:
    """Test suite for FlowStatistics model."""

    def test_flow_statistics_minimal(self) -> None:
        """Test flow statistics with minimal fields."""
        stats = FlowStatistics(site_id="default", time_range="24h")
        assert stats.site_id == "default"
        assert stats.time_range == "24h"
        assert stats.total_flows == 0
        assert stats.total_bytes_sent == 0
        assert stats.total_bytes_received == 0
        assert stats.total_bytes == 0
        assert stats.total_packets_sent == 0
        assert stats.total_packets_received == 0
        assert stats.unique_sources == 0
        assert stats.unique_destinations == 0
        assert stats.top_applications == []

    def test_flow_statistics_full(self) -> None:
        """Test flow statistics with all fields."""
        top_apps = [
            {"application": "HTTPS", "bytes": 5000000},
            {"application": "DNS", "bytes": 100000},
        ]
        stats = FlowStatistics(
            site_id="site-123",
            time_range="7d",
            total_flows=10000,
            total_bytes_sent=50000000,
            total_bytes_received=100000000,
            total_bytes=150000000,
            total_packets_sent=75000,
            total_packets_received=125000,
            unique_sources=250,
            unique_destinations=5000,
            top_applications=top_apps,
        )
        assert stats.total_flows == 10000
        assert stats.total_bytes_sent == 50000000
        assert stats.total_bytes == 150000000
        assert stats.unique_sources == 250
        assert len(stats.top_applications) == 2
        assert stats.top_applications[0]["application"] == "HTTPS"


class TestFlowRisk:
    """Test suite for FlowRisk model."""

    def test_flow_risk_minimal(self) -> None:
        """Test flow risk with minimal fields."""
        risk = FlowRisk(flow_id="flow-001", risk_score=25.5, risk_level="low")
        assert risk.flow_id == "flow-001"
        assert risk.risk_score == 25.5
        assert risk.risk_level == "low"
        assert risk.indicators == []
        assert risk.threat_type is None
        assert risk.description is None

    def test_flow_risk_full(self) -> None:
        """Test flow risk with all fields."""
        indicators = ["suspicious_port", "unusual_traffic_pattern", "known_c2_domain"]
        risk = FlowRisk(
            flow_id="flow-002",
            risk_score=85.0,
            risk_level="critical",
            indicators=indicators,
            threat_type="malware",
            description="Detected C2 communication pattern",
        )
        assert risk.flow_id == "flow-002"
        assert risk.risk_score == 85.0
        assert risk.risk_level == "critical"
        assert len(risk.indicators) == 3
        assert risk.threat_type == "malware"
        assert risk.description == "Detected C2 communication pattern"

    def test_flow_risk_levels(self) -> None:
        """Test all valid flow risk levels."""
        for level in ["low", "medium", "high", "critical"]:
            risk = FlowRisk(flow_id="flow-test", risk_score=50.0, risk_level=level)
            assert risk.risk_level == level

    def test_flow_risk_invalid_level(self) -> None:
        """Test flow risk with invalid level."""
        with pytest.raises(ValidationError):
            FlowRisk(flow_id="flow-001", risk_score=50.0, risk_level="extreme")


class TestFlowView:
    """Test suite for FlowView model."""

    def test_flow_view_minimal(self) -> None:
        """Test flow view with minimal fields."""
        view = FlowView(
            view_id="view-001",
            site_id="default",
            name="Default View",
            created_at="2025-01-01T12:00:00Z",
        )
        assert view.view_id == "view-001"
        assert view.site_id == "default"
        assert view.name == "Default View"
        assert view.description is None
        assert view.filter_expression is None
        assert view.time_range == "24h"
        assert view.created_at == "2025-01-01T12:00:00Z"

    def test_flow_view_full(self) -> None:
        """Test flow view with all fields."""
        view = FlowView(
            view_id="view-002",
            site_id="site-123",
            name="High Risk Flows",
            description="Flows with high risk scores",
            filter_expression="risk_score > 75",
            time_range="7d",
            created_at="2025-01-01T12:00:00Z",
        )
        assert view.view_id == "view-002"
        assert view.site_id == "site-123"
        assert view.name == "High Risk Flows"
        assert view.description == "Flows with high risk scores"
        assert view.filter_expression == "risk_score > 75"
        assert view.time_range == "7d"


# ============================================================================
# Site Manager Models Tests
# ============================================================================


class TestSiteHealthSummary:
    """Test suite for SiteHealthSummary model."""

    def test_site_health_summary_minimal(self) -> None:
        """Test site health summary with minimal fields."""
        summary = SiteHealthSummary(
            site_id="site-001",
            site_name="Main Office",
            status="healthy",
            last_updated="2025-01-01T12:00:00Z",
        )
        assert summary.site_id == "site-001"
        assert summary.site_name == "Main Office"
        assert summary.status == "healthy"
        assert summary.devices_online == 0
        assert summary.devices_total == 0
        assert summary.clients_active == 0
        assert summary.uptime_percentage == 0.0

    def test_site_health_summary_full(self) -> None:
        """Test site health summary with all fields."""
        summary = SiteHealthSummary(
            site_id="site-002",
            site_name="Branch Office",
            status="degraded",
            devices_online=15,
            devices_total=20,
            clients_active=50,
            uptime_percentage=98.5,
            last_updated="2025-01-01T12:00:00Z",
        )
        assert summary.site_id == "site-002"
        assert summary.status == "degraded"
        assert summary.devices_online == 15
        assert summary.devices_total == 20
        assert summary.clients_active == 50
        assert summary.uptime_percentage == 98.5

    def test_site_health_summary_all_statuses(self) -> None:
        """Test all valid health statuses."""
        for status in ["healthy", "degraded", "down"]:
            summary = SiteHealthSummary(
                site_id="test",
                site_name="Test",
                status=status,
                last_updated="2025-01-01T12:00:00Z",
            )
            assert summary.status == status


class TestInternetHealthMetrics:
    """Test suite for InternetHealthMetrics model."""

    def test_internet_health_metrics_minimal(self) -> None:
        """Test internet health metrics with minimal fields."""
        metrics = InternetHealthMetrics(
            status="healthy",
            last_tested="2025-01-01T12:00:00Z",
        )
        assert metrics.site_id is None
        assert metrics.latency_ms is None
        assert metrics.packet_loss_percent == 0.0
        assert metrics.jitter_ms is None
        assert metrics.bandwidth_up_mbps is None
        assert metrics.bandwidth_down_mbps is None
        assert metrics.status == "healthy"

    def test_internet_health_metrics_full(self) -> None:
        """Test internet health metrics with all fields."""
        metrics = InternetHealthMetrics(
            site_id="site-001",
            latency_ms=15.5,
            packet_loss_percent=0.5,
            jitter_ms=2.0,
            bandwidth_up_mbps=100.0,
            bandwidth_down_mbps=500.0,
            status="healthy",
            last_tested="2025-01-01T12:00:00Z",
        )
        assert metrics.site_id == "site-001"
        assert metrics.latency_ms == 15.5
        assert metrics.packet_loss_percent == 0.5
        assert metrics.jitter_ms == 2.0
        assert metrics.bandwidth_up_mbps == 100.0
        assert metrics.bandwidth_down_mbps == 500.0
        assert metrics.status == "healthy"

    def test_internet_health_metrics_degraded(self) -> None:
        """Test degraded internet health metrics."""
        metrics = InternetHealthMetrics(
            site_id="site-002",
            latency_ms=150.0,
            packet_loss_percent=5.0,
            status="degraded",
            last_tested="2025-01-01T12:00:00Z",
        )
        assert metrics.status == "degraded"
        assert metrics.packet_loss_percent == 5.0


class TestCrossSiteStatistics:
    """Test suite for CrossSiteStatistics model."""

    def test_cross_site_statistics_minimal(self) -> None:
        """Test cross-site statistics with minimal fields."""
        stats = CrossSiteStatistics()
        assert stats.total_sites == 0
        assert stats.sites_healthy == 0
        assert stats.sites_degraded == 0
        assert stats.sites_down == 0
        assert stats.total_devices == 0
        assert stats.devices_online == 0
        assert stats.total_clients == 0
        assert stats.total_bandwidth_up_mbps == 0.0
        assert stats.total_bandwidth_down_mbps == 0.0
        assert stats.site_summaries == []

    def test_cross_site_statistics_full(self) -> None:
        """Test cross-site statistics with all fields."""
        site_summaries = [
            SiteHealthSummary(
                site_id="site-001",
                site_name="Site 1",
                status="healthy",
                devices_online=10,
                devices_total=10,
                clients_active=25,
                uptime_percentage=99.9,
                last_updated="2025-01-01T12:00:00Z",
            ),
            SiteHealthSummary(
                site_id="site-002",
                site_name="Site 2",
                status="degraded",
                devices_online=8,
                devices_total=10,
                clients_active=15,
                uptime_percentage=95.0,
                last_updated="2025-01-01T12:00:00Z",
            ),
        ]
        stats = CrossSiteStatistics(
            total_sites=2,
            sites_healthy=1,
            sites_degraded=1,
            sites_down=0,
            total_devices=20,
            devices_online=18,
            total_clients=40,
            total_bandwidth_up_mbps=200.0,
            total_bandwidth_down_mbps=1000.0,
            site_summaries=site_summaries,
        )
        assert stats.total_sites == 2
        assert stats.sites_healthy == 1
        assert stats.sites_degraded == 1
        assert stats.total_devices == 20
        assert stats.devices_online == 18
        assert len(stats.site_summaries) == 2
        assert stats.site_summaries[0].status == "healthy"
        assert stats.site_summaries[1].status == "degraded"


class TestVantagePoint:
    """Test suite for VantagePoint model."""

    def test_vantage_point_minimal(self) -> None:
        """Test vantage point with minimal fields."""
        vp = VantagePoint(
            vantage_point_id="vp-001",
            name="US East",
            status="active",
        )
        assert vp.vantage_point_id == "vp-001"
        assert vp.name == "US East"
        assert vp.location is None
        assert vp.latitude is None
        assert vp.longitude is None
        assert vp.status == "active"
        assert vp.site_ids == []

    def test_vantage_point_full(self) -> None:
        """Test vantage point with all fields."""
        vp = VantagePoint(
            vantage_point_id="vp-002",
            name="EU West",
            location="Dublin, Ireland",
            latitude=53.3498,
            longitude=-6.2603,
            status="active",
            site_ids=["site-001", "site-002", "site-003"],
        )
        assert vp.vantage_point_id == "vp-002"
        assert vp.name == "EU West"
        assert vp.location == "Dublin, Ireland"
        assert vp.latitude == 53.3498
        assert vp.longitude == -6.2603
        assert vp.status == "active"
        assert len(vp.site_ids) == 3

    def test_vantage_point_inactive(self) -> None:
        """Test inactive vantage point."""
        vp = VantagePoint(
            vantage_point_id="vp-003",
            name="Asia Pacific",
            status="inactive",
        )
        assert vp.status == "inactive"

    def test_vantage_point_invalid_status(self) -> None:
        """Test vantage point with invalid status."""
        with pytest.raises(ValidationError):
            VantagePoint(
                vantage_point_id="vp-004",
                name="Test",
                status="disabled",  # Invalid status
            )
