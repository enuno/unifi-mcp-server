"""Unit tests for FirewallPolicy models.

TDD: Write these tests FIRST, then implement src/models/firewall_policy.py
Based on API discovery in docs/research/TRAFFIC_RULES_API_DISCOVERY.md
"""

import pytest
from pydantic import ValidationError


class TestPolicyAction:
    """Tests for PolicyAction enum."""

    def test_allow_value(self):
        """ALLOW should have value 'ALLOW'."""
        from src.models.firewall_policy import PolicyAction

        assert PolicyAction.ALLOW.value == "ALLOW"

    def test_block_value(self):
        """BLOCK should have value 'BLOCK'."""
        from src.models.firewall_policy import PolicyAction

        assert PolicyAction.BLOCK.value == "BLOCK"

    def test_invalid_action_raises(self):
        """Invalid action string should not be convertible."""
        from src.models.firewall_policy import PolicyAction

        with pytest.raises(ValueError):
            PolicyAction("invalid")


class TestMatchingTarget:
    """Tests for MatchingTarget enum."""

    def test_any_value(self):
        """ANY should be a valid matching target."""
        from src.models.firewall_policy import MatchingTarget

        assert MatchingTarget.ANY.value == "ANY"

    def test_ip_value(self):
        """IP should be a valid matching target."""
        from src.models.firewall_policy import MatchingTarget

        assert MatchingTarget.IP.value == "IP"

    def test_network_value(self):
        """NETWORK should be a valid matching target."""
        from src.models.firewall_policy import MatchingTarget

        assert MatchingTarget.NETWORK.value == "NETWORK"

    def test_region_value(self):
        """REGION should be a valid matching target."""
        from src.models.firewall_policy import MatchingTarget

        assert MatchingTarget.REGION.value == "REGION"

    def test_client_value(self):
        """CLIENT should be a valid matching target."""
        from src.models.firewall_policy import MatchingTarget

        assert MatchingTarget.CLIENT.value == "CLIENT"


class TestConnectionStateType:
    """Tests for ConnectionStateType enum."""

    def test_all_value(self):
        """ALL should be a valid connection state type."""
        from src.models.firewall_policy import ConnectionStateType

        assert ConnectionStateType.ALL.value == "ALL"

    def test_custom_value(self):
        """CUSTOM should be a valid connection state type."""
        from src.models.firewall_policy import ConnectionStateType

        assert ConnectionStateType.CUSTOM.value == "CUSTOM"

    def test_respond_only_value(self):
        """RESPOND_ONLY should be a valid connection state type."""
        from src.models.firewall_policy import ConnectionStateType

        assert ConnectionStateType.RESPOND_ONLY.value == "RESPOND_ONLY"


class TestIPVersion:
    """Tests for IPVersion enum."""

    def test_both_value(self):
        """BOTH should be the default IP version."""
        from src.models.firewall_policy import IPVersion

        assert IPVersion.BOTH.value == "BOTH"

    def test_ipv4_value(self):
        """IPV4 should be a valid IP version."""
        from src.models.firewall_policy import IPVersion

        assert IPVersion.IPV4.value == "IPV4"

    def test_ipv6_value(self):
        """IPV6 should be a valid IP version."""
        from src.models.firewall_policy import IPVersion

        assert IPVersion.IPV6.value == "IPV6"


class TestMatchTarget:
    """Tests for MatchTarget model (source/destination)."""

    def test_any_target(self):
        """Should create target with matching_target='ANY'."""
        from src.models.firewall_policy import MatchingTarget, MatchTarget

        target = MatchTarget(zone_id="zone-123", matching_target=MatchingTarget.ANY)
        assert target.zone_id == "zone-123"
        assert target.matching_target == MatchingTarget.ANY
        assert target.ips is None
        assert target.network_ids is None

    def test_ip_target(self):
        """Should create target with IP addresses."""
        from src.models.firewall_policy import MatchingTarget, MatchTarget

        target = MatchTarget(
            zone_id="zone-123",
            matching_target=MatchingTarget.IP,
            ips=["192.168.1.90", "192.168.1.91"],
        )
        assert target.matching_target == MatchingTarget.IP
        assert target.ips == ["192.168.1.90", "192.168.1.91"]

    def test_network_target(self):
        """Should create target with network IDs."""
        from src.models.firewall_policy import MatchingTarget, MatchTarget

        target = MatchTarget(
            zone_id="zone-123",
            matching_target=MatchingTarget.NETWORK,
            network_ids=["net-001", "net-002"],
        )
        assert target.matching_target == MatchingTarget.NETWORK
        assert target.network_ids == ["net-001", "net-002"]

    def test_region_target(self):
        """Should create target with region codes."""
        from src.models.firewall_policy import MatchingTarget, MatchTarget

        target = MatchTarget(
            zone_id="zone-123",
            matching_target=MatchingTarget.REGION,
            regions=["US", "CN", "RU"],
        )
        assert target.matching_target == MatchingTarget.REGION
        assert target.regions == ["US", "CN", "RU"]

    def test_client_target(self):
        """Should create target with client MACs (source only)."""
        from src.models.firewall_policy import MatchingTarget, MatchTarget

        target = MatchTarget(
            zone_id="zone-123",
            matching_target=MatchingTarget.CLIENT,
            client_macs=["bc:24:11:7d:bf:13"],
        )
        assert target.matching_target == MatchingTarget.CLIENT
        assert target.client_macs == ["bc:24:11:7d:bf:13"]

    def test_port_matching(self):
        """Should support port matching."""
        from src.models.firewall_policy import MatchingTarget, MatchTarget

        target = MatchTarget(
            zone_id="zone-123",
            matching_target=MatchingTarget.ANY,
            port_matching_type="SPECIFIC",
            port="80,443",
        )
        assert target.port_matching_type == "SPECIFIC"
        assert target.port == "80,443"


class TestSchedule:
    """Tests for Schedule model."""

    def test_always_schedule(self):
        """Should create always-active schedule."""
        from src.models.firewall_policy import Schedule

        schedule = Schedule(mode="ALWAYS")
        assert schedule.mode == "ALWAYS"
        assert schedule.time_all_day is None

    def test_time_based_schedule(self):
        """Should create time-based schedule."""
        from src.models.firewall_policy import Schedule

        schedule = Schedule(
            mode="CUSTOM",
            date_start="2024-04-21",
            date_end="2024-04-28",
            time_all_day=False,
            time_range_start="09:00",
            time_range_end="17:00",
        )
        assert schedule.mode == "CUSTOM"
        assert schedule.date_start == "2024-04-21"
        assert schedule.time_range_start == "09:00"


class TestFirewallPolicy:
    """Tests for FirewallPolicy model."""

    @pytest.fixture
    def sample_api_response(self):
        """Sample API response from UniFi controller."""
        return {
            "_id": "682a0e42220317278bb0b2cb",
            "name": "Block IOT to Internal",
            "enabled": True,
            "action": "BLOCK",
            "predefined": False,
            "index": 10000,
            "protocol": "all",
            "ip_version": "BOTH",
            "connection_state_type": "CUSTOM",
            "connection_states": ["NEW"],
            "source": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "NETWORK",
                "network_ids": ["6643a914785061509e45c60f"],
            },
            "destination": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "NETWORK",
                "network_ids": ["6507f744e35fa70a9663d80e"],
            },
        }

    @pytest.fixture
    def predefined_rule_response(self):
        """Sample predefined rule from API."""
        return {
            "_id": "682a0e42220317278bb0b2c5682a0e42220317278bb0b2c52147483647",
            "name": "Allow All Traffic",
            "enabled": True,
            "action": "ALLOW",
            "predefined": True,
            "index": 2147483647,
            "protocol": "all",
            "ip_version": "BOTH",
            "connection_state_type": "ALL",
            "source": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "ANY",
            },
            "destination": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "ANY",
            },
        }

    def test_parses_api_response(self, sample_api_response):
        """Model should parse actual API response JSON."""
        from src.models.firewall_policy import FirewallPolicy

        policy = FirewallPolicy(**sample_api_response)
        assert policy.name == "Block IOT to Internal"
        assert policy.action.value == "BLOCK"
        assert policy.enabled is True
        assert policy.predefined is False

    def test_id_alias(self, sample_api_response):
        """Model should accept _id and expose as id."""
        from src.models.firewall_policy import FirewallPolicy

        policy = FirewallPolicy(**sample_api_response)
        assert policy.id == "682a0e42220317278bb0b2cb"

    def test_action_enum_conversion(self, sample_api_response):
        """Action string should convert to enum."""
        from src.models.firewall_policy import FirewallPolicy, PolicyAction

        policy = FirewallPolicy(**sample_api_response)
        assert policy.action == PolicyAction.BLOCK
        assert isinstance(policy.action, PolicyAction)

    def test_invalid_action_raises(self, sample_api_response):
        """Invalid action should raise ValidationError."""
        from src.models.firewall_policy import FirewallPolicy

        sample_api_response["action"] = "INVALID"
        with pytest.raises(ValidationError):
            FirewallPolicy(**sample_api_response)

    def test_source_destination_parsing(self, sample_api_response):
        """Source and destination should be parsed as MatchTarget."""
        from src.models.firewall_policy import FirewallPolicy, MatchingTarget, MatchTarget

        policy = FirewallPolicy(**sample_api_response)
        assert isinstance(policy.source, MatchTarget)
        assert isinstance(policy.destination, MatchTarget)
        assert policy.source.matching_target == MatchingTarget.NETWORK
        assert policy.source.network_ids == ["6643a914785061509e45c60f"]

    def test_connection_states(self, sample_api_response):
        """Connection states should be parsed correctly."""
        from src.models.firewall_policy import ConnectionStateType, FirewallPolicy

        policy = FirewallPolicy(**sample_api_response)
        assert policy.connection_state_type == ConnectionStateType.CUSTOM
        assert policy.connection_states == ["NEW"]

    def test_predefined_rule(self, predefined_rule_response):
        """Should correctly parse predefined rules."""
        from src.models.firewall_policy import FirewallPolicy

        policy = FirewallPolicy(**predefined_rule_response)
        assert policy.predefined is True
        assert policy.index == 2147483647

    def test_serialization_roundtrip(self, sample_api_response):
        """model_dump() output should be re-parseable."""
        from src.models.firewall_policy import FirewallPolicy

        policy = FirewallPolicy(**sample_api_response)
        dumped = policy.model_dump(by_alias=True)
        policy2 = FirewallPolicy(**dumped)
        assert policy.id == policy2.id
        assert policy.name == policy2.name
        assert policy.action == policy2.action

    def test_optional_fields_default(self):
        """Optional fields should have sensible defaults."""
        from src.models.firewall_policy import FirewallPolicy

        minimal = {
            "_id": "123",
            "name": "Test Rule",
            "action": "ALLOW",
            "source": {"zone_id": "zone-1", "matching_target": "ANY"},
            "destination": {"zone_id": "zone-2", "matching_target": "ANY"},
        }
        policy = FirewallPolicy(**minimal)
        assert policy.enabled is True
        assert policy.predefined is False
        assert policy.protocol == "all"
        assert policy.index == 10000

    def test_ip_version_default(self, sample_api_response):
        """IP version should default to BOTH."""
        from src.models.firewall_policy import FirewallPolicy, IPVersion

        policy = FirewallPolicy(**sample_api_response)
        assert policy.ip_version == IPVersion.BOTH

    def test_region_block_rule(self):
        """Should parse region-based blocking rule."""
        from src.models.firewall_policy import FirewallPolicy, MatchingTarget

        region_rule = {
            "_id": "region-001",
            "name": "Region Block",
            "action": "BLOCK",
            "source": {"zone_id": "zone-internal", "matching_target": "ANY"},
            "destination": {
                "zone_id": "zone-external",
                "matching_target": "REGION",
                "regions": ["KP", "IR", "CN", "RU"],
            },
        }
        policy = FirewallPolicy(**region_rule)
        assert policy.destination.matching_target == MatchingTarget.REGION
        assert "CN" in policy.destination.regions

    def test_port_forward_origin(self):
        """Should parse rules created from port forwards."""
        from src.models.firewall_policy import FirewallPolicy

        port_forward_rule = {
            "_id": "pf-001",
            "name": "Port Forward - SSH",
            "action": "ALLOW",
            "origin_type": "port_forward",
            "origin_id": "pf-origin-123",
            "source": {"zone_id": "zone-ext", "matching_target": "ANY"},
            "destination": {
                "zone_id": "zone-int",
                "matching_target": "IP",
                "ips": ["192.168.2.100"],
                "port_matching_type": "SPECIFIC",
                "port": "22",
            },
        }
        policy = FirewallPolicy(**port_forward_rule)
        assert policy.origin_type == "port_forward"
        assert policy.origin_id == "pf-origin-123"


class TestFirewallPolicyCreate:
    """Tests for FirewallPolicyCreate model (for API requests)."""

    def test_create_minimal_policy(self):
        """Should create policy with minimal required fields."""
        from src.models.firewall_policy import FirewallPolicyCreate

        create_data = FirewallPolicyCreate(
            name="Test Rule",
            action="ALLOW",
            source={"zone_id": "zone-1", "matching_target": "ANY"},
            destination={"zone_id": "zone-2", "matching_target": "ANY"},
        )
        assert create_data.name == "Test Rule"
        assert create_data.action == "ALLOW"

    def test_create_excludes_id(self):
        """Create model should not include _id field."""
        from src.models.firewall_policy import FirewallPolicyCreate

        create_data = FirewallPolicyCreate(
            name="Test",
            action="BLOCK",
            source={"zone_id": "z1", "matching_target": "ANY"},
            destination={"zone_id": "z2", "matching_target": "ANY"},
        )
        dumped = create_data.model_dump(exclude_none=True)
        assert "_id" not in dumped
        assert "id" not in dumped


class TestFirewallPolicyUpdate:
    """Tests for FirewallPolicyUpdate model (for partial updates)."""

    def test_update_name_only(self):
        """Should allow updating just the name."""
        from src.models.firewall_policy import FirewallPolicyUpdate

        update_data = FirewallPolicyUpdate(name="New Name")
        dumped = update_data.model_dump(exclude_none=True)
        assert dumped == {"name": "New Name"}

    def test_update_enabled(self):
        """Should allow toggling enabled state."""
        from src.models.firewall_policy import FirewallPolicyUpdate

        update_data = FirewallPolicyUpdate(enabled=False)
        dumped = update_data.model_dump(exclude_none=True)
        assert dumped == {"enabled": False}

    def test_update_action(self):
        """Should allow changing action."""
        from src.models.firewall_policy import FirewallPolicyUpdate

        update_data = FirewallPolicyUpdate(action="BLOCK")
        dumped = update_data.model_dump(exclude_none=True)
        assert dumped == {"action": "BLOCK"}
