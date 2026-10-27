"""Unit tests for the v2-local traffic flow tools.

The current ``traffic_flows`` module talks to
``POST /proxy/network/v2/api/site/{site}/traffic-flows``, which is the only
endpoint on current UniFi firmware that actually exposes flow data. The
Integration API (``/integration/v1/sites/.../traffic/flows``) returns 404
on any firmware — Ubiquiti has never exposed flow data through that
surface. These tests mock the v2 POST response with a realistic sample
captured from a live UDM Pro (with IPs/MACs redacted).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.tools import traffic_flows as tf
from src.utils.exceptions import ResourceNotFoundError, ValidationError


@pytest.fixture
def mock_settings() -> MagicMock:
    """Mock Settings object configured for local API access."""
    from src.config import APIType

    settings = MagicMock(spec=Settings)
    settings.api_type = APIType.LOCAL
    settings.api_key = "test-api-key"
    settings.local_host = "192.0.2.1"
    settings.local_port = 443
    settings.local_verify_ssl = False
    settings.log_level = "INFO"
    settings.get_v2_api_path = MagicMock(
        side_effect=lambda site_id: f"/proxy/network/v2/api/site/{site_id}"
    )
    return settings


@pytest.fixture
def cloud_settings() -> MagicMock:
    """Mock Settings object configured for cloud-EA API access."""
    from src.config import APIType

    settings = MagicMock(spec=Settings)
    settings.api_type = APIType.CLOUD_EA
    settings.api_key = "test-api-key"
    settings.log_level = "INFO"
    return settings


@pytest.fixture
def sample_raw_flows() -> list[dict[str, Any]]:
    """Realistic v2 ``traffic-flows`` response shape (3 flows)."""
    return [
        {
            "id": "flow-1",
            "action": "allowed",
            "count": 1,
            "direction": "outgoing",
            "protocol": "UDP",
            "service": "OTHER",
            "risk": "low",
            "source": {
                "id": "aa:bb:cc:dd:ee:01",
                "ip": "10.0.20.10",
                "port": 14414,
                "mac": "aa:bb:cc:dd:ee:01",
                "client_name": "Camera 01",
                "client_oui": "Smart Innovation LLC",
                "network_id": "net-iot",
                "network_name": "Cameras - Data",
                "subnet": "10.0.20.0/24",
                "zone_id": "zone-dmz",
                "zone_name": "Dmz",
            },
            "destination": {
                "id": "198.51.100.5",
                "ip": "198.51.100.5",
                "port": 32100,
                "region": "US",
                "zone_id": "zone-external",
                "zone_name": "External",
                "domains": [],
            },
            "traffic_data": {
                "bytes_tx": 208,
                "bytes_rx": 336,
                "bytes_total": 544,
                "packets_tx": 5,
                "packets_rx": 5,
                "packets_total": 10,
            },
            "policies": [
                {"type": "FIREWALL", "internal_type": "CONNTRACK"},
            ],
            "duration_milliseconds": 221461,
            "flow_start_time": 1_775_932_927_744,
            "flow_end_time": 1_775_933_149_205,
            "time": 1_775_933_149_205,
            "in": {"network_id": "net-iot", "network_name": "Cameras - Data"},
            "out": {"network_id": "net-wan", "network_name": "Comcast"},
        },
        {
            "id": "flow-2",
            "action": "allowed",
            "count": 1,
            "direction": "outgoing",
            "protocol": "TCP",
            "service": "DNS",
            "risk": "medium",
            "source": {
                "id": "aa:bb:cc:dd:ee:02",
                "ip": "10.0.10.20",
                "port": 54321,
                "mac": "aa:bb:cc:dd:ee:02",
                "client_name": "Rob's Laptop",
                "network_id": "net-lan",
                "network_name": "Internal - Data",
                "zone_id": "zone-internal",
                "zone_name": "Internal",
            },
            "destination": {
                "id": "1.1.1.1",
                "ip": "1.1.1.1",
                "port": 443,
                "region": "US",
                "zone_id": "zone-external",
                "zone_name": "External",
                "domains": ["cloudflare-dns.com"],
            },
            "traffic_data": {
                "bytes_tx": 8000,
                "bytes_rx": 16000,
                "bytes_total": 24000,
                "packets_tx": 30,
                "packets_rx": 42,
                "packets_total": 72,
            },
            "policies": [{"type": "FIREWALL", "internal_type": "ESTABLISHED"}],
            "duration_milliseconds": 15200,
            "flow_start_time": 1_775_933_000_000,
            "flow_end_time": 1_775_933_015_200,
            "time": 1_775_933_015_200,
        },
        {
            "id": "flow-3",
            "action": "blocked",
            "count": 1,
            "direction": "outgoing",
            "protocol": "TCP",
            "service": "OTHER",
            "risk": "high",
            "source": {
                "id": "aa:bb:cc:dd:ee:03",
                "ip": "10.0.20.11",
                "port": 33333,
                "mac": "aa:bb:cc:dd:ee:03",
                "client_name": "Sketchy IoT",
                "network_id": "net-iot",
                "network_name": "Cameras - Data",
                "zone_id": "zone-dmz",
                "zone_name": "Dmz",
            },
            "destination": {
                "id": "203.0.113.99",
                "ip": "203.0.113.99",
                "port": 6667,
                "region": "RU",
                "zone_id": "zone-external",
                "zone_name": "External",
                "domains": [],
            },
            "traffic_data": {
                "bytes_tx": 100,
                "bytes_rx": 0,
                "bytes_total": 100,
                "packets_tx": 2,
                "packets_rx": 0,
                "packets_total": 2,
            },
            "policies": [{"type": "FIREWALL", "internal_type": "REJECT"}],
            "duration_milliseconds": 500,
            "flow_start_time": 1_775_933_200_000,
            "flow_end_time": 1_775_933_200_500,
            "time": 1_775_933_200_500,
        },
    ]


def _mock_client(raw_flows: list[dict[str, Any]] | dict[str, Any]) -> AsyncMock:
    """Build an AsyncMock UniFiClient returning the given raw flows.

    ``_site_uuid_to_name`` must be a real dict. On a bare ``AsyncMock`` the
    attribute is auto-created as a child ``AsyncMock``, so the
    ``client._site_uuid_to_name.get(site_id, site_id)`` in
    ``traffic_flows._fetch_raw_flows`` would return a **coroutine that is never
    awaited**: it would be interpolated into the endpoint as a
    ``<coroutine ...>`` repr, and the orphaned coroutine would later raise
    ``RuntimeWarning: coroutine ... was never awaited`` at garbage-collection
    time, failing whatever unrelated test happened to be running (issue #260).
    """
    client = AsyncMock()
    client.is_authenticated = True
    client._site_uuid_to_name = {}
    client.authenticate = AsyncMock()
    client.post = AsyncMock(return_value=raw_flows)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# --------------------------------------------------------------------------- #
# Local-only gate                                                             #
# --------------------------------------------------------------------------- #


class TestLocalApiGate:
    @pytest.mark.asyncio
    async def test_cloud_mode_raises(self, cloud_settings: MagicMock) -> None:
        with pytest.raises(NotImplementedError, match="UNIFI_API_TYPE='local'"):
            await tf.get_traffic_flows("default", cloud_settings)

    @pytest.mark.asyncio
    async def test_get_flow_trends_always_raises(self, mock_settings: MagicMock) -> None:
        with pytest.raises(NotImplementedError, match="historical time-series"):
            await tf.get_flow_trends("default", mock_settings)

    @pytest.mark.asyncio
    async def test_stream_traffic_flows_raises(self, mock_settings: MagicMock) -> None:
        with pytest.raises(NotImplementedError, match="50 flows with no pagination"):
            await tf.stream_traffic_flows("default", mock_settings)

    @pytest.mark.asyncio
    async def test_get_connection_states_raises(self, mock_settings: MagicMock) -> None:
        with pytest.raises(NotImplementedError, match="completed flows"):
            await tf.get_connection_states("default", mock_settings)


# --------------------------------------------------------------------------- #
# get_traffic_flows                                                           #
# --------------------------------------------------------------------------- #


class TestGetTrafficFlows:
    @pytest.mark.asyncio
    async def test_returns_all_flows_without_filters(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_traffic_flows("default", mock_settings)

        assert len(result) == 3
        assert result[0]["id"] == "flow-1"
        assert result[0]["source"]["client_name"] == "Camera 01"
        assert result[0]["destination"]["ip"] == "198.51.100.5"

    @pytest.mark.asyncio
    async def test_hits_v2_endpoint_with_empty_body(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        client = _mock_client(sample_raw_flows)
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = client
            await tf.get_traffic_flows("default", mock_settings)

        client.post.assert_called_once()
        endpoint = client.post.call_args.args[0]
        # Asserted in full, not just the suffix: an endswith() check passes even
        # when the site segment is a stray `<coroutine ...>` repr, which is how
        # the un-awaited-coroutine leak of issue #260 stayed hidden here.
        assert endpoint == "/proxy/network/v2/api/site/default/traffic-flows"
        assert client.post.call_args.kwargs["json_data"] == {}

    @pytest.mark.asyncio
    async def test_site_uuid_is_normalized_to_its_short_name(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        """A site UUID is mapped through the client's lookup before the call.

        ``_fetch_raw_flows`` resolves the site through
        ``client._site_uuid_to_name``; this pins that the resolved name reaches
        the endpoint, which the mock previously made unobservable.
        """
        site_uuid = "88f7af54-98f8-306a-a1c7-c9349722b1f6"
        client = _mock_client(sample_raw_flows)
        client._site_uuid_to_name = {site_uuid: "hq"}

        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = client
            await tf.get_traffic_flows(site_uuid, mock_settings)

        assert client.post.call_args.args[0] == "/proxy/network/v2/api/site/hq/traffic-flows"

    @pytest.mark.asyncio
    async def test_an_unmapped_site_is_passed_through_unchanged(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        client = _mock_client(sample_raw_flows)
        client._site_uuid_to_name = {"other-uuid": "elsewhere"}

        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = client
            await tf.get_traffic_flows("default", mock_settings)

        assert client.post.call_args.args[0] == "/proxy/network/v2/api/site/default/traffic-flows"

    @pytest.mark.asyncio
    async def test_filter_by_source_mac(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_traffic_flows(
                "default", mock_settings, source_mac="aa:bb:cc:dd:ee:02"
            )
        assert len(result) == 1
        assert result[0]["source"]["mac"] == "aa:bb:cc:dd:ee:02"

    @pytest.mark.asyncio
    async def test_filter_by_destination_zone(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_traffic_flows(
                "default", mock_settings, destination_zone_name="External"
            )
        assert len(result) == 3
        assert all(r["destination"]["zone_name"] == "External" for r in result)

    @pytest.mark.asyncio
    async def test_inter_vlan_filter_by_destination_network(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        """Inter-VLAN flows are labeled ``destination_zone=Gateway`` by
        UniFi, so the correct way to find them is via
        ``destination_network_name``. This test pins the behaviour: the
        zone-name filter must return 0, the network-name filter must find it.
        """
        inter_vlan = {
            "id": "flow-inter-vlan",
            "action": "allowed",
            "count": 1,
            "direction": "outgoing",
            "protocol": "TCP",
            "service": "OTHER",
            "risk": "low",
            "source": {
                "id": "aa:bb:cc:dd:ee:02",
                "ip": "10.0.10.20",
                "port": 40001,
                "mac": "aa:bb:cc:dd:ee:02",
                "client_name": "Rob's Laptop",
                "network_id": "net-lan",
                "network_name": "Internal - Data",
                "zone_id": "zone-internal",
                "zone_name": "Internal",
            },
            # The critical detail: dest zone is "Gateway", not "Servers".
            "destination": {
                "id": "10.0.30.5",
                "ip": "10.0.30.5",
                "port": 445,
                "network_id": "net-servers",
                "network_name": "Server - Data",
                "zone_id": "zone-gateway",
                "zone_name": "Gateway",
                "domains": [],
            },
            "traffic_data": {
                "bytes_tx": 4096,
                "bytes_rx": 8192,
                "bytes_total": 12288,
                "packets_tx": 12,
                "packets_rx": 18,
                "packets_total": 30,
            },
            "policies": [],
            "duration_milliseconds": 1500,
            "flow_start_time": 1_775_933_300_000,
            "flow_end_time": 1_775_933_301_500,
            "time": 1_775_933_301_500,
        }

        flows_with_inter_vlan = [*sample_raw_flows, inter_vlan]

        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(flows_with_inter_vlan)
            by_zone = await tf.get_traffic_flows(
                "default", mock_settings, destination_zone_name="Servers"
            )
        assert by_zone == [], (
            "destination_zone_name=Servers must return 0 — inter-VLAN flows "
            "are labeled as 'Gateway'. This is the bug reproducer."
        )

        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(flows_with_inter_vlan)
            by_network = await tf.get_traffic_flows(
                "default",
                mock_settings,
                destination_network_name="Server - Data",
            )
        assert len(by_network) == 1
        assert by_network[0]["id"] == "flow-inter-vlan"
        assert by_network[0]["destination"]["network_name"] == "Server - Data"
        # The "Gateway" label is preserved — we don't rewrite it.
        assert by_network[0]["destination"]["zone_name"] == "Gateway"

    @pytest.mark.asyncio
    async def test_filter_by_protocol_and_action(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_traffic_flows(
                "default", mock_settings, protocol="TCP", action="blocked"
            )
        assert len(result) == 1
        assert result[0]["id"] == "flow-3"

    @pytest.mark.asyncio
    async def test_filter_by_min_bytes(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_traffic_flows("default", mock_settings, min_bytes=1000)
        assert len(result) == 1
        assert result[0]["id"] == "flow-2"

    @pytest.mark.asyncio
    async def test_client_name_contains_is_case_insensitive(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_traffic_flows(
                "default", mock_settings, client_name_contains="laptop"
            )
        assert len(result) == 1
        assert result[0]["source"]["client_name"] == "Rob's Laptop"

    @pytest.mark.asyncio
    async def test_limit_applied_after_filter(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_traffic_flows("default", mock_settings, limit=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_handles_data_wrapped_response(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        wrapped = {"data": sample_raw_flows}

        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(wrapped)
            result = await tf.get_traffic_flows("default", mock_settings)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_handles_empty_response(self, mock_settings: MagicMock) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client([])
            result = await tf.get_traffic_flows("default", mock_settings)
        assert result == []


# --------------------------------------------------------------------------- #
# Statistics / analytics                                                      #
# --------------------------------------------------------------------------- #


class TestGetFlowStatistics:
    @pytest.mark.asyncio
    async def test_aggregates_correctly(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            stats = await tf.get_flow_statistics("default", mock_settings)

        assert stats["sample_size"] == 3
        assert stats["total_bytes"] == 544 + 24_000 + 100
        assert stats["total_bytes_tx"] == 208 + 8000 + 100
        assert stats["total_packets"] == 10 + 72 + 2
        assert stats["unique_sources"] == 3
        assert stats["unique_destinations"] == 3
        assert stats["protocol_breakdown"] == {"UDP": 1, "TCP": 2}
        assert stats["action_breakdown"] == {"allowed": 2, "blocked": 1}
        assert stats["top_destinations"][0]["ip"] == "1.1.1.1"  # biggest by bytes

    @pytest.mark.asyncio
    async def test_statistics_with_filter_narrows_sample(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            stats = await tf.get_flow_statistics("default", mock_settings, action="blocked")
        assert stats["sample_size"] == 1
        assert stats["total_bytes"] == 100


class TestGetFlowAnalytics:
    @pytest.mark.asyncio
    async def test_analytics_includes_risk_breakdown(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_flow_analytics("default", mock_settings)
        assert result["risk_breakdown"] == {"low": 1, "medium": 1, "high": 1}
        assert result["sample_size"] == 3


# --------------------------------------------------------------------------- #
# Single-flow details                                                         #
# --------------------------------------------------------------------------- #


class TestGetTrafficFlowDetails:
    @pytest.mark.asyncio
    async def test_found_in_sample(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_traffic_flow_details("default", "flow-2", mock_settings)
        assert result["id"] == "flow-2"
        assert result["source"]["client_name"] == "Rob's Laptop"

    @pytest.mark.asyncio
    async def test_not_in_sample_raises(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            with pytest.raises(ResourceNotFoundError):
                await tf.get_traffic_flow_details("default", "missing-id", mock_settings)


# --------------------------------------------------------------------------- #
# Top flows / risks / filter expression                                       #
# --------------------------------------------------------------------------- #


class TestGetTopFlows:
    @pytest.mark.asyncio
    async def test_sort_by_bytes_default(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_top_flows("default", mock_settings, limit=2)
        assert [r["id"] for r in result] == ["flow-2", "flow-1"]

    @pytest.mark.asyncio
    async def test_sort_by_packets(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_top_flows("default", mock_settings, limit=1, sort_by="packets")
        assert result[0]["id"] == "flow-2"  # 72 packets

    @pytest.mark.asyncio
    async def test_sort_by_duration(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_top_flows("default", mock_settings, limit=1, sort_by="duration")
        assert result[0]["id"] == "flow-1"  # 221461 ms


class TestGetFlowRisks:
    @pytest.mark.asyncio
    async def test_threshold_medium(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_flow_risks("default", mock_settings, min_risk_level="medium")
        assert [r["id"] for r in result] == ["flow-2", "flow-3"]

    @pytest.mark.asyncio
    async def test_threshold_high_only(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_flow_risks("default", mock_settings, min_risk_level="high")
        assert len(result) == 1
        assert result[0]["id"] == "flow-3"


class TestFilterTrafficFlows:
    @pytest.mark.asyncio
    async def test_filter_expression_parsing(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.filter_traffic_flows(
                "default",
                mock_settings,
                "protocol=TCP,action=blocked,min_bytes=50",
            )
        assert len(result) == 1
        assert result[0]["id"] == "flow-3"


# --------------------------------------------------------------------------- #
# Client aggregation                                                          #
# --------------------------------------------------------------------------- #


class TestGetClientFlowAggregation:
    @pytest.mark.asyncio
    async def test_aggregates_for_client(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_client_flow_aggregation(
                "default", "aa:bb:cc:dd:ee:02", mock_settings
            )
        assert result["sample_size"] == 1
        assert result["client_name"] == "Rob's Laptop"
        assert result["total_bytes"] == 24_000
        assert result["protocol_breakdown"] == {"TCP": 1}

    @pytest.mark.asyncio
    async def test_unknown_client_returns_empty_aggregation(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.get_client_flow_aggregation(
                "default", "00:00:00:00:00:00", mock_settings
            )
        assert result["sample_size"] == 0
        assert result["total_bytes"] == 0


# --------------------------------------------------------------------------- #
# find_flows_for_rule_reference                                               #
# --------------------------------------------------------------------------- #


class TestFindFlowsForRuleReference:
    @pytest.mark.asyncio
    async def test_match_zone_pair(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        """Simulated workflow: 'show me what a Dmz→External rule would match'."""
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            matches = await tf.find_flows_for_rule_reference(
                "default",
                mock_settings,
                source_zone_name="Dmz",
                destination_zone_name="External",
            )
        assert len(matches) == 2
        ids = {m["flow_id"] for m in matches}
        assert ids == {"flow-1", "flow-3"}
        # Match records expose the rule-reference shape, not the full flow.
        assert "source_label" in matches[0]
        assert "destination_label" in matches[0]
        assert "source_zone_name" in matches[0]

    @pytest.mark.asyncio
    async def test_match_protocol_and_port(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            matches = await tf.find_flows_for_rule_reference(
                "default",
                mock_settings,
                protocol="TCP",
                destination_port=443,
            )
        assert len(matches) == 1
        assert matches[0]["flow_id"] == "flow-2"
        assert matches[0]["destination_port"] == 443

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            matches = await tf.find_flows_for_rule_reference(
                "default",
                mock_settings,
                source_zone_name="Hotspot",
            )
        assert matches == []

    @pytest.mark.asyncio
    async def test_respects_limit(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            matches = await tf.find_flows_for_rule_reference(
                "default",
                mock_settings,
                destination_zone_name="External",
                limit=1,
            )
        assert len(matches) == 1


# --------------------------------------------------------------------------- #
# Export                                                                      #
# --------------------------------------------------------------------------- #


class TestExportTrafficFlows:
    @pytest.mark.asyncio
    async def test_json_export(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        import json

        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.export_traffic_flows("default", mock_settings, export_format="json")
        parsed = json.loads(result)
        assert len(parsed) == 3
        assert parsed[0]["id"] == "flow-1"

    @pytest.mark.asyncio
    async def test_csv_export_has_header_and_rows(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.export_traffic_flows("default", mock_settings, export_format="csv")
        lines = result.strip().split("\n")
        assert lines[0].startswith("flow_id,action,protocol")
        assert len(lines) == 4  # header + 3 rows

    @pytest.mark.asyncio
    async def test_export_invalid_format_raises(self, mock_settings: MagicMock) -> None:
        with pytest.raises(ValueError, match="export_format"):
            await tf.export_traffic_flows("default", mock_settings, export_format="xml")

    @pytest.mark.asyncio
    async def test_export_respects_max_records(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        import json

        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.export_traffic_flows(
                "default", mock_settings, export_format="json", max_records=2
            )
        parsed = json.loads(result)
        assert len(parsed) == 2


# --------------------------------------------------------------------------- #
# Block-flow actions (dry-run only; no firewall writes in unit tests)         #
# --------------------------------------------------------------------------- #


class TestBlockFlowActions:
    @pytest.mark.asyncio
    async def test_block_source_ip_dry_run(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.block_flow_source_ip(
                "default",
                "flow-1",
                mock_settings,
                confirm=True,
                dry_run=True,
            )
        assert result["block_type"] == "source_ip"
        assert result["blocked_target"] == "10.0.20.10"
        assert result["rule_id"] is None  # dry-run, no rule created

    @pytest.mark.asyncio
    async def test_block_destination_ip_dry_run(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.block_flow_destination_ip(
                "default",
                "flow-3",
                mock_settings,
                confirm=True,
                dry_run=True,
            )
        assert result["block_type"] == "destination_ip"
        assert result["blocked_target"] == "203.0.113.99"

    @pytest.mark.asyncio
    async def test_block_application_dry_run_falls_back_to_destination_ip(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        # flow-1 has service=OTHER so block_flow_application falls back to dst ip
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.block_flow_application(
                "default",
                "flow-1",
                mock_settings,
                confirm=True,
                dry_run=True,
            )
        assert result["block_type"] == "application"
        assert result["blocked_target"] == "198.51.100.5"

    @pytest.mark.asyncio
    async def test_block_without_confirm_raises(self, mock_settings: MagicMock) -> None:
        with pytest.raises(ValidationError):
            await tf.block_flow_source_ip("default", "flow-1", mock_settings, confirm=False)

    @pytest.mark.asyncio
    async def test_block_temporary_sets_expiry(
        self, mock_settings: MagicMock, sample_raw_flows: list[dict[str, Any]]
    ) -> None:
        with patch("src.tools.traffic_flows.UniFiClient") as MockClient:
            MockClient.return_value = _mock_client(sample_raw_flows)
            result = await tf.block_flow_destination_ip(
                "default",
                "flow-3",
                mock_settings,
                duration="temporary",
                expires_in_hours=6,
                confirm=True,
                dry_run=True,
            )
        assert result["duration"] == "temporary"
        assert result["expires_at"] is not None
