"""Tests for traffic route and Smart Queue tools.

Note: Tests for QoS Profile (5 tools), ProAV Profile (3 tools), and Smart
Queue (3 tools) were removed along with the tools themselves. Those tools
used non-existent API endpoints (rest/qosprofile, rest/wanconf). The
create/update/delete traffic route tools were removed for the same reason
(issue #171). See src/tools/qos.py docstring for details.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils import APIError


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
    settings.get_v2_api_path = lambda site_id: f"/proxy/network/v2/api/site/{site_id}"
    return settings


@pytest.fixture
def sample_traffic_routes():
    """Traffic Routes as the v2 endpoint returns them (keys verbatim from issue #171)."""
    return [
        {
            "_id": "route-001",
            "description": "Streaming via VPN",
            "domains": [{"domain": "example.com", "port_ranges": [], "ports": []}],
            "enabled": True,
            "ip_addresses": [],
            "ip_ranges": [],
            "kill_switch_enabled": True,
            "matching_target": "DOMAIN",
            "network_id": "vpn-net-1",
            "next_hop": "",
            "regions": [],
            "target_devices": [{"network_id": "lan-net-1", "type": "NETWORK"}],
        },
        {
            "_id": "route-002",
            "description": "Laptop all traffic via VPN",
            "domains": [],
            "enabled": False,
            "ip_addresses": [],
            "ip_ranges": [],
            "kill_switch_enabled": False,
            "matching_target": "INTERNET",
            "network_id": "vpn-net-1",
            "next_hop": "",
            "regions": [],
            "target_devices": [{"client_mac": "aa:bb:cc:dd:ee:ff", "type": "CLIENT"}],
        },
    ]


def _route_client(response):
    """Patch UniFiClient so GET returns ``response``; return (patcher, instance)."""
    patcher = patch("src.tools.qos.UniFiClient")
    mock_client = patcher.start()
    instance = AsyncMock()
    mock_client.return_value.__aenter__.return_value = instance
    instance.is_authenticated = True
    instance._site_uuid_to_name = {}
    instance.get = AsyncMock(return_value=response)
    return patcher, instance


class TestListTrafficRoutes:
    @pytest.mark.asyncio
    async def test_reads_v2_trafficroutes_endpoint(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import list_traffic_routes

        patcher, instance = _route_client(sample_traffic_routes)
        try:
            result = await list_traffic_routes("default", mock_settings)
        finally:
            patcher.stop()

        instance.get.assert_awaited_once_with("/proxy/network/v2/api/site/default/trafficroutes")
        assert [r["id"] for r in result] == ["route-001", "route-002"]
        assert result[0]["matching_target"] == "DOMAIN"
        assert result[0]["network_id"] == "vpn-net-1"
        assert result[0]["kill_switch_enabled"] is True
        assert result[0]["domains"][0]["domain"] == "example.com"
        assert result[1]["target_devices"][0]["client_mac"] == "aa:bb:cc:dd:ee:ff"
        assert result[1]["target_devices"][0]["type"] == "CLIENT"

    @pytest.mark.asyncio
    async def test_site_uuid_resolved_to_internal_name(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import list_traffic_routes

        patcher, instance = _route_client(sample_traffic_routes)
        instance._site_uuid_to_name = {"88f7af54-98f8-306a-a1c7-c9349722b1f6": "default"}
        try:
            await list_traffic_routes("88f7af54-98f8-306a-a1c7-c9349722b1f6", mock_settings)
        finally:
            patcher.stop()

        instance.get.assert_awaited_once_with("/proxy/network/v2/api/site/default/trafficroutes")

    @pytest.mark.asyncio
    async def test_unknown_fields_are_preserved(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import list_traffic_routes

        route = dict(sample_traffic_routes[0], future_field="kept")
        patcher, _ = _route_client([route])
        try:
            result = await list_traffic_routes("default", mock_settings)
        finally:
            patcher.stop()

        assert result[0]["future_field"] == "kept"

    @pytest.mark.asyncio
    async def test_accepts_data_envelope(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import list_traffic_routes

        patcher, _ = _route_client({"data": sample_traffic_routes})
        try:
            result = await list_traffic_routes("default", mock_settings)
        finally:
            patcher.stop()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_list_means_no_routes(self, mock_settings):
        from src.tools.qos import list_traffic_routes

        patcher, _ = _route_client([])
        try:
            result = await list_traffic_routes("default", mock_settings)
        finally:
            patcher.stop()

        assert result == []

    @pytest.mark.asyncio
    async def test_pagination(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import list_traffic_routes

        routes = [dict(sample_traffic_routes[0], _id=f"route-{i}") for i in range(6)]
        patcher, _ = _route_client(routes)
        try:
            result = await list_traffic_routes("default", mock_settings, limit=2, offset=2)
        finally:
            patcher.stop()

        assert [r["id"] for r in result] == ["route-2", "route-3"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response",
        [{"count": 0}, {"data": "nope"}, "unexpected", None, [1, 2]],
        ids=["count-only", "data-not-list", "string", "none", "non-dict-items"],
    )
    async def test_unexpected_shape_raises_instead_of_empty(self, mock_settings, response):
        """A payload that is not a route list must not be reported as 'no routes' (#171)."""
        from src.tools.qos import list_traffic_routes

        patcher, _ = _route_client(response)
        try:
            with pytest.raises(APIError, match="Unexpected response"):
                await list_traffic_routes("default", mock_settings)
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_requires_local_api(self, mock_settings):
        from src.config import APIType
        from src.tools.qos import list_traffic_routes

        mock_settings.api_type = APIType.CLOUD_V1
        with pytest.raises(NotImplementedError, match="UNIFI_API_TYPE='local'"):
            await list_traffic_routes("default", mock_settings)

    @pytest.mark.asyncio
    async def test_invalid_pagination_rejected(self, mock_settings):
        from src.tools.qos import list_traffic_routes
        from src.utils import ValidationError

        with pytest.raises(ValidationError):
            await list_traffic_routes("default", mock_settings, limit=0)

    def test_write_tools_removed(self):
        """create/update/delete targeted a resource that does not exist (#171)."""
        import src.tools.qos as qos

        for name in ("create_traffic_route", "update_traffic_route", "delete_traffic_route"):
            assert not hasattr(qos, name)


# ============================================================================
# WAN Smart Queues
# ============================================================================

WAN_NET = {
    "_id": "wan-net-1",
    "name": "Internet 1",
    "purpose": "wan",
    "wan_networkgroup": "WAN",
}
LAN_NET = {"_id": "lan-net-1", "name": "Default", "purpose": "corporate"}


def _sq_client(networks, put_return=None, refetch=None):
    client = MagicMock()
    client.is_authenticated = True
    client.authenticate = AsyncMock()
    responses = [{"data": networks}]
    if refetch is not None:
        responses.append({"data": refetch})
    client.get = AsyncMock(side_effect=responses)
    client.put = AsyncMock(return_value=put_return if put_return is not None else {"data": []})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestSmartQueues:
    """Smart Queues live on the WAN networkconf's wan_smartq_* fields."""

    @pytest.mark.asyncio
    async def test_status_reads_primary_wan(self, mock_settings):
        from src.tools.qos import get_smart_queue_status

        # The controller stores kbps; the tool reports Mbps.
        wan = {**WAN_NET, "wan_smartq_enabled": True, "wan_smartq_down_rate": 500_000}
        client = _sq_client([LAN_NET, wan])

        with patch("src.tools.qos.UniFiClient", return_value=client):
            result = await get_smart_queue_status("default", mock_settings)

        assert result["wan_network_id"] == "wan-net-1"
        assert result["enabled"] is True
        assert result["download_mbps"] == 500
        assert result["upload_mbps"] is None

    @pytest.mark.asyncio
    async def test_enable_writes_partial_payload(self, mock_settings):
        from src.tools.qos import configure_smart_queue

        stored = {
            **WAN_NET,
            "wan_smartq_enabled": True,
            "wan_smartq_down_rate": 840_000,
            "wan_smartq_up_rate": 805_000,
        }
        client = _sq_client([WAN_NET], put_return={"data": [stored]})

        with patch("src.tools.qos.UniFiClient", return_value=client):
            result = await configure_smart_queue(
                "default",
                mock_settings,
                enabled=True,
                download_mbps=840,
                upload_mbps=805,
                confirm=True,
            )

        url = client.put.call_args[0][0]
        assert url == "/ea/sites/default/rest/networkconf/wan-net-1"
        # Regression: these fields are kbps on the wire. Writing the Mbps
        # numbers raw shaped a ~900 Mbps line to 0.84 Mbps (observed live).
        assert client.put.call_args[1]["json_data"] == {
            "wan_smartq_enabled": True,
            "wan_smartq_down_rate": 840_000,
            "wan_smartq_up_rate": 805_000,
        }
        assert result["enabled"] is True
        assert result["download_mbps"] == 840
        assert result["upload_mbps"] == 805

    @pytest.mark.asyncio
    async def test_unechoed_write_rereads_the_stored_state(self, mock_settings):
        from src.tools.qos import configure_smart_queue

        stored = {
            **WAN_NET,
            "wan_smartq_enabled": True,
            "wan_smartq_down_rate": 840_000,
            "wan_smartq_up_rate": 805_000,
        }
        client = _sq_client([WAN_NET], put_return={"data": []}, refetch=[stored])

        with patch("src.tools.qos.UniFiClient", return_value=client):
            result = await configure_smart_queue(
                "default",
                mock_settings,
                download_mbps=840,
                upload_mbps=805,
                confirm=True,
            )

        assert result["download_mbps"] == 840
        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_enable_requires_both_rates(self, mock_settings):
        from src.tools.qos import configure_smart_queue
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="upload_mbps"):
            await configure_smart_queue("default", mock_settings, download_mbps=840, confirm=True)

    @pytest.mark.asyncio
    async def test_disable_needs_no_rates(self, mock_settings):
        from src.tools.qos import configure_smart_queue

        stored = {**WAN_NET, "wan_smartq_enabled": False}
        client = _sq_client([WAN_NET], put_return={"data": [stored]})

        with patch("src.tools.qos.UniFiClient", return_value=client):
            result = await configure_smart_queue(
                "default", mock_settings, enabled=False, confirm=True
            )

        assert client.put.call_args[1]["json_data"] == {"wan_smartq_enabled": False}
        assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_explicit_wan_id_must_match(self, mock_settings):
        from src.tools.qos import configure_smart_queue
        from src.utils.exceptions import APIError

        client = _sq_client([WAN_NET])

        with patch("src.tools.qos.UniFiClient", return_value=client):
            with pytest.raises(APIError, match="wan-net-9"):
                await configure_smart_queue(
                    "default",
                    mock_settings,
                    download_mbps=840,
                    upload_mbps=805,
                    wan_network_id="wan-net-9",
                    confirm=True,
                )

    @pytest.mark.asyncio
    async def test_dry_run_previews_without_writing(self, mock_settings):
        from src.tools.qos import configure_smart_queue

        client = _sq_client([WAN_NET])

        with patch("src.tools.qos.UniFiClient", return_value=client):
            result = await configure_smart_queue(
                "default",
                mock_settings,
                download_mbps=840,
                upload_mbps=805,
                confirm=True,
                dry_run=True,
            )

        client.put.assert_not_called()
        assert result["dry_run"] is True
        assert result["payload"]["wan_smartq_down_rate"] == 840_000

    @pytest.mark.asyncio
    async def test_confirmation_required(self, mock_settings):
        from src.tools.qos import configure_smart_queue
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="confirm"):
            await configure_smart_queue(
                "default", mock_settings, download_mbps=840, upload_mbps=805
            )

    @pytest.mark.asyncio
    async def test_string_false_dry_run_still_writes(self, mock_settings):
        """JSON-RPC serializes booleans as strings; "false" must not
        be treated as truthy and silently skip the PUT."""
        from src.tools.qos import configure_smart_queue

        stored = {**WAN_NET, "wan_smartq_enabled": True}
        client = _sq_client([WAN_NET], put_return={"data": [stored]})

        with patch("src.tools.qos.UniFiClient", return_value=client):
            result = await configure_smart_queue(
                site_id="default",
                enabled=True,
                download_mbps=840,
                upload_mbps=805,
                settings=mock_settings,
                confirm=True,
                dry_run="false",
            )

        client.put.assert_called_once()
        assert "dry_run" not in result
