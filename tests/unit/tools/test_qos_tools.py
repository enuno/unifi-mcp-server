"""Tests for traffic route tools.

Note: Tests for QoS Profile (5 tools), ProAV Profile (3 tools), and Smart
Queue (3 tools) were removed along with the tools themselves. Those tools
used non-existent API endpoints (rest/qosprofile, rest/wanconf).
See src/tools/qos.py docstring for details.
"""

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
    return settings


@pytest.fixture
def sample_traffic_routes():
    return [
        {
            "_id": "route-001",
            "name": "Block External DNS",
            "description": "Block external DNS queries",
            "action": "deny",
            "enabled": True,
            "match_criteria": {
                "destination_port": 53,
                "protocol": "udp",
            },
            "priority": 100,
            "site_id": "default",
        },
        {
            "_id": "route-002",
            "name": "Prioritize VoIP",
            "description": "Mark VoIP with EF",
            "action": "mark",
            "enabled": True,
            "match_criteria": {
                "destination_port": 5060,
                "protocol": "udp",
            },
            "dscp_marking": 46,
            "priority": 50,
            "site_id": "default",
        },
    ]


class TestListTrafficRoutes:
    @pytest.mark.asyncio
    async def test_list_traffic_routes_success(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import list_traffic_routes

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": sample_traffic_routes})

            result = await list_traffic_routes("default", mock_settings)

            assert len(result) == 2
            assert result[0]["name"] == "Block External DNS"
            assert result[1]["name"] == "Prioritize VoIP"

    @pytest.mark.asyncio
    async def test_list_traffic_routes_pagination(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import list_traffic_routes

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(
                return_value={"data": sample_traffic_routes * 3}  # 6 routes
            )

            result = await list_traffic_routes("default", mock_settings, limit=2, offset=2)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_traffic_routes_filters_static_routes_before_pagination(self, mock_settings):
        from src.tools.qos import list_traffic_routes

        mixed_routes = [
            {
                "_id": "policy-001",
                "name": "Policy 1",
                "action": "deny",
                "enabled": True,
                "match_criteria": {"destination_port": 53, "protocol": "udp"},
                "priority": 100,
                "site_id": "default",
            },
            {
                "_id": "static-001",
                "name": "Static Route 1",
                "static-route_nexthop": "192.168.1.1",
                "enabled": True,
                "priority": 10,
                "site_id": "default",
            },
            {
                "_id": "policy-002",
                "name": "Policy 2",
                "action": "mark",
                "enabled": True,
                "match_criteria": {"destination_port": 5060, "protocol": "udp"},
                "dscp_marking": 46,
                "priority": 50,
                "site_id": "default",
            },
            {
                "_id": "static-002",
                "name": "Static Route 2",
                "static-route_nexthop": "192.168.1.2",
                "enabled": True,
                "priority": 20,
                "site_id": "default",
            },
            {
                "_id": "policy-003",
                "name": "Policy 3",
                "action": "allow",
                "enabled": True,
                "match_criteria": {"destination_port": 443, "protocol": "tcp"},
                "priority": 25,
                "site_id": "default",
            },
        ]

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value={"data": mixed_routes})

            result = await list_traffic_routes("default", mock_settings, limit=2, offset=1)

        assert [route["name"] for route in result] == ["Policy 2", "Policy 3"]


class TestCreateTrafficRoute:
    @pytest.mark.asyncio
    async def test_create_traffic_route_success(self, mock_settings):
        from src.tools.qos import create_traffic_route

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.post = AsyncMock(
                return_value={
                    "data": [
                        {
                            "_id": "route-new",
                            "name": "Test Route",
                            "action": "allow",
                            "enabled": True,
                            "match_criteria": {
                                "destination_port": 443,
                                "protocol": "tcp",
                            },
                            "priority": 100,
                            "site_id": "default",
                        }
                    ]
                }
            )

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await create_traffic_route(
                    site_id="default",
                    name="Test Route",
                    action="allow",
                    settings=mock_settings,
                    destination_port=443,
                    protocol="tcp",
                    confirm=True,
                )

            assert result["name"] == "Test Route"
            assert result["action"] == "allow"

    @pytest.mark.asyncio
    async def test_create_traffic_route_requires_confirmation(self, mock_settings):
        from src.tools.qos import create_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await create_traffic_route(
                site_id="default",
                name="Test",
                action="allow",
                settings=mock_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_create_traffic_route_invalid_action(self, mock_settings):
        from src.tools.qos import create_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Invalid action"):
            await create_traffic_route(
                site_id="default",
                name="Test",
                action="invalid",
                settings=mock_settings,
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_create_traffic_route_invalid_dscp(self, mock_settings):
        from src.tools.qos import create_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="DSCP marking must be 0-63"):
            await create_traffic_route(
                site_id="default",
                name="Test",
                action="mark",
                settings=mock_settings,
                dscp_marking=100,  # Invalid
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_create_traffic_route_invalid_priority(self, mock_settings):
        from src.tools.qos import create_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Priority must be 1-1000"):
            await create_traffic_route(
                site_id="default",
                name="Test",
                action="allow",
                settings=mock_settings,
                priority=2000,  # Invalid
                confirm=True,
            )


class TestUpdateTrafficRoute:
    @pytest.mark.asyncio
    async def test_update_traffic_route_success(self, mock_settings, sample_traffic_routes):
        from src.tools.qos import update_traffic_route

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            updated_route = sample_traffic_routes[0].copy()
            updated_route["enabled"] = False
            mock_instance.put = AsyncMock(return_value={"data": [updated_route]})

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await update_traffic_route(
                    site_id="default",
                    route_id="route-001",
                    settings=mock_settings,
                    enabled=False,
                    confirm=True,
                )

            assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_update_traffic_route_requires_confirmation(self, mock_settings):
        from src.tools.qos import update_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await update_traffic_route(
                site_id="default",
                route_id="route-001",
                settings=mock_settings,
                enabled=False,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_update_traffic_route_no_fields(self, mock_settings):
        from src.tools.qos import update_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="No update fields provided"):
            await update_traffic_route(
                site_id="default",
                route_id="route-001",
                settings=mock_settings,
                confirm=True,
            )


class TestDeleteTrafficRoute:
    @pytest.mark.asyncio
    async def test_delete_traffic_route_success(self, mock_settings):
        from src.tools.qos import delete_traffic_route

        with patch("src.tools.qos.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.delete = AsyncMock(return_value={})

            with patch("src.tools.qos.audit_action", new_callable=AsyncMock):
                result = await delete_traffic_route(
                    site_id="default",
                    route_id="route-001",
                    settings=mock_settings,
                    confirm=True,
                )

            assert result["success"] is True
            assert result["route_id"] == "route-001"

    @pytest.mark.asyncio
    async def test_delete_traffic_route_requires_confirmation(self, mock_settings):
        from src.tools.qos import delete_traffic_route
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await delete_traffic_route(
                site_id="default",
                route_id="route-001",
                settings=mock_settings,
                confirm=False,
            )


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
