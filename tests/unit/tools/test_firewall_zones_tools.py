"""Tests for firewall_zones tools."""

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
def mock_settings_cloud():
    from src.config import APIType

    settings = MagicMock(spec="Settings")
    settings.log_level = "INFO"
    settings.api_type = APIType.CLOUD_EA
    return settings


@pytest.fixture
def sample_firewall_zones():
    return [
        {
            "_id": "zone-001",
            "site_id": "default",
            "name": "LAN",
            "description": "Local network zone",
            "networks": ["net-001", "net-002"],
            "networkIds": ["net-001", "net-002"],
        },
        {
            "_id": "zone-002",
            "site_id": "default",
            "name": "IoT",
            "description": "IoT devices zone",
            "networks": ["net-003"],
            "networkIds": ["net-003"],
        },
    ]


class TestListFirewallZones:
    @pytest.mark.asyncio
    async def test_list_firewall_zones_success(self, mock_settings, sample_firewall_zones):
        from src.tools.firewall_zones import list_firewall_zones

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": sample_firewall_zones})

            result = await list_firewall_zones("default", mock_settings)

            assert len(result) == 2
            assert result[0]["name"] == "LAN"
            assert result[1]["name"] == "IoT"

    @pytest.mark.asyncio
    async def test_list_firewall_zones_empty(self, mock_settings):
        from src.tools.firewall_zones import list_firewall_zones

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": []})

            result = await list_firewall_zones("default", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_firewall_zones_requires_local_api(self, mock_settings_cloud):
        from src.tools.firewall_zones import list_firewall_zones
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="local"):
            await list_firewall_zones("default", mock_settings_cloud)


class TestCreateFirewallZone:
    @pytest.mark.asyncio
    async def test_create_firewall_zone_success(self, mock_settings):
        from src.tools.firewall_zones import create_firewall_zone

        created_zone = {
            "_id": "zone-new",
            "site_id": "default",
            "name": "Guest",
            "description": "Guest network zone",
            "networks": [],
            "networkIds": [],
        }

        with (
            patch("src.tools.firewall_zones.UniFiClient") as mock_client,
            patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock) as mock_audit,
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.post = AsyncMock(return_value={"data": created_zone})

            result = await create_firewall_zone(
                "default",
                "Guest",
                mock_settings,
                description="Guest network zone",
                confirm=True,
            )

            assert result["name"] == "Guest"
            mock_instance.post.assert_called_once()
            mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_firewall_zone_dry_run(self, mock_settings):
        from src.tools.firewall_zones import create_firewall_zone

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()

            result = await create_firewall_zone(
                "default",
                "TestZone",
                mock_settings,
                confirm=True,
                dry_run=True,
            )

            assert result["dry_run"] is True
            assert result["payload"]["name"] == "TestZone"
            mock_instance.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_firewall_zone_no_confirm_error(self, mock_settings):
        from src.tools.firewall_zones import create_firewall_zone
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await create_firewall_zone("default", "TestZone", mock_settings, confirm=False)

    @pytest.mark.asyncio
    async def test_create_firewall_zone_with_networks(self, mock_settings):
        from src.tools.firewall_zones import create_firewall_zone

        created_zone = {
            "_id": "zone-with-nets",
            "site_id": "default",
            "name": "Internal",
            "networks": ["net-001", "net-002"],
        }

        with (
            patch("src.tools.firewall_zones.UniFiClient") as mock_client,
            patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.post = AsyncMock(return_value={"data": created_zone})

            result = await create_firewall_zone(
                "default",
                "Internal",
                mock_settings,
                network_ids=["net-001", "net-002"],
                confirm=True,
            )

            assert "net-001" in result["networks"]


class TestUpdateFirewallZone:
    @pytest.mark.asyncio
    async def test_update_firewall_zone_success(self, mock_settings, sample_firewall_zones):
        from src.tools.firewall_zones import update_firewall_zone

        updated_zone = {
            "_id": "zone-001",
            "site_id": "default",
            "name": "LAN-Updated",
            "description": "Updated description",
            "networks": ["net-001", "net-002"],
        }

        with (
            patch("src.tools.firewall_zones.UniFiClient") as mock_client,
            patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": sample_firewall_zones[0]})
            mock_instance.put = AsyncMock(return_value={"data": updated_zone})

            result = await update_firewall_zone(
                "default",
                "zone-001",
                mock_settings,
                name="LAN-Updated",
                description="Updated description",
                confirm=True,
            )

            assert result["name"] == "LAN-Updated"
            mock_instance.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_firewall_zone_dry_run(self, mock_settings, sample_firewall_zones):
        from src.tools.firewall_zones import update_firewall_zone

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": sample_firewall_zones[0]})

            result = await update_firewall_zone(
                "default",
                "zone-001",
                mock_settings,
                name="NewName",
                confirm=True,
                dry_run=True,
            )

            assert result["dry_run"] is True
            assert result["payload"]["name"] == "NewName"
            mock_instance.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_firewall_zone_partial_fields(self, mock_settings, sample_firewall_zones):
        from src.tools.firewall_zones import update_firewall_zone

        updated_zone = {
            "_id": "zone-001",
            "site_id": "default",
            "name": "LAN",
            "description": "Only description updated",
            "networks": ["net-001", "net-002"],
            "networkIds": ["net-001", "net-002"],
        }

        with (
            patch("src.tools.firewall_zones.UniFiClient") as mock_client,
            patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value={"data": sample_firewall_zones[0]})
            mock_instance.put = AsyncMock(return_value={"data": updated_zone})

            result = await update_firewall_zone(
                "default",
                "zone-001",
                mock_settings,
                description="Only description updated",
                confirm=True,
            )

            assert result["description"] == "Only description updated"

    @pytest.mark.asyncio
    async def test_update_firewall_zone_no_confirm_error(self, mock_settings):
        from src.tools.firewall_zones import update_firewall_zone
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await update_firewall_zone("default", "zone-001", mock_settings, confirm=False)


class TestDeleteFirewallZone:
    @pytest.mark.asyncio
    async def test_delete_firewall_zone_success(self, mock_settings):
        from src.tools.firewall_zones import delete_firewall_zone

        with (
            patch("src.tools.firewall_zones.UniFiClient") as mock_client,
            patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.delete = AsyncMock(return_value={})

            result = await delete_firewall_zone(
                "default",
                "zone-001",
                mock_settings,
                confirm=True,
            )

            assert result["status"] == "success"
            assert result["action"] == "deleted"
            mock_instance.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_firewall_zone_dry_run(self, mock_settings):
        from src.tools.firewall_zones import delete_firewall_zone

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()

            result = await delete_firewall_zone(
                "default",
                "zone-001",
                mock_settings,
                confirm=True,
                dry_run=True,
            )

            assert result["dry_run"] is True
            assert result["action"] == "would_delete"
            mock_instance.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_firewall_zone_no_confirm_error(self, mock_settings):
        from src.tools.firewall_zones import delete_firewall_zone
        from src.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires confirmation"):
            await delete_firewall_zone("default", "zone-001", mock_settings, confirm=False)


class TestAssignNetworkToZone:
    @pytest.mark.asyncio
    async def test_assign_network_to_zone_success(self, mock_settings, sample_firewall_zones):
        from src.tools.firewall_zones import assign_network_to_zone

        zone_data = {"data": {"networkIds": ["net-001"]}}
        network_data = {"data": {"name": "NewNetwork"}}

        with (
            patch("src.tools.firewall_zones.UniFiClient") as mock_client,
            patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")

            def get_side_effect(endpoint):
                if "networks/net-new" in endpoint:
                    return network_data
                return zone_data

            mock_instance.get = AsyncMock(side_effect=get_side_effect)
            mock_instance.put = AsyncMock(return_value={})

            result = await assign_network_to_zone(
                "default",
                "zone-001",
                "net-new",
                mock_settings,
                confirm=True,
            )

            assert result["zone_id"] == "zone-001"
            assert result["network_id"] == "net-new"
            _, kwargs = mock_instance.put.call_args
            assert "networkIds" in kwargs["json_data"]
            assert "net-new" in kwargs["json_data"]["networkIds"]

    @pytest.mark.asyncio
    async def test_assign_network_to_zone_already_assigned(self, mock_settings):
        from src.tools.firewall_zones import assign_network_to_zone

        zone_data = {"data": {"networkIds": ["net-001", "net-002"]}}

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value=zone_data)

            result = await assign_network_to_zone(
                "default",
                "zone-001",
                "net-001",
                mock_settings,
                confirm=True,
            )

            assert result["network_id"] == "net-001"
            mock_instance.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_assign_network_to_zone_dry_run(self, mock_settings):
        from src.tools.firewall_zones import assign_network_to_zone

        zone_data = {"data": {"networkIds": []}}

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value=zone_data)

            result = await assign_network_to_zone(
                "default",
                "zone-001",
                "net-new",
                mock_settings,
                confirm=True,
                dry_run=True,
            )

            assert result["dry_run"] is True
            assert "networkIds" in result["payload"]
            mock_instance.put.assert_not_called()


class TestUnassignNetworkFromZone:
    @pytest.mark.asyncio
    async def test_unassign_network_from_zone_success(self, mock_settings):
        from src.tools.firewall_zones import unassign_network_from_zone

        zone_data = {"data": {"networkIds": ["net-001", "net-002"]}}

        with (
            patch("src.tools.firewall_zones.UniFiClient") as mock_client,
            patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock),
        ):
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value=zone_data)
            mock_instance.put = AsyncMock(return_value={})

            result = await unassign_network_from_zone(
                "default",
                "zone-001",
                "net-001",
                mock_settings,
                confirm=True,
            )

            assert result["status"] == "success"
            assert result["action"] == "unassigned"
            _, kwargs = mock_instance.put.call_args
            assert "networkIds" in kwargs["json_data"]
            assert "net-001" not in kwargs["json_data"]["networkIds"]

    @pytest.mark.asyncio
    async def test_unassign_network_not_in_zone_error(self, mock_settings):
        from src.tools.firewall_zones import unassign_network_from_zone

        zone_data = {"data": {"networkIds": ["net-001"]}}

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value=zone_data)

            with pytest.raises(ValueError, match="not assigned"):
                await unassign_network_from_zone(
                    "default",
                    "zone-001",
                    "net-999",
                    mock_settings,
                    confirm=True,
                )

    @pytest.mark.asyncio
    async def test_unassign_network_from_zone_dry_run(self, mock_settings):
        from src.tools.firewall_zones import unassign_network_from_zone

        zone_data = {"data": {"networkIds": ["net-001", "net-002"]}}

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value=zone_data)

            result = await unassign_network_from_zone(
                "default",
                "zone-001",
                "net-001",
                mock_settings,
                confirm=True,
                dry_run=True,
            )

            assert result["dry_run"] is True
            assert "networkIds" in result["payload"]
            mock_instance.put.assert_not_called()


class TestGetZoneNetworks:
    @pytest.mark.asyncio
    async def test_get_zone_networks_success(self, mock_settings):
        from src.tools.firewall_zones import get_zone_networks

        zone_data = {"data": {"networkIds": ["net-001", "net-002"]}}
        network1_data = {"data": {"name": "Network1"}}
        network2_data = {"data": {"name": "Network2"}}

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")

            call_count = 0

            async def get_side_effect(endpoint):
                nonlocal call_count
                call_count += 1
                if "zones/zone-001" in endpoint:
                    return zone_data
                elif "networks/net-001" in endpoint:
                    return network1_data
                elif "networks/net-002" in endpoint:
                    return network2_data
                return {}

            mock_instance.get = AsyncMock(side_effect=get_side_effect)

            result = await get_zone_networks("default", "zone-001", mock_settings)

            assert len(result) == 2
            assert result[0]["network_name"] == "Network1"
            assert result[1]["network_name"] == "Network2"

    @pytest.mark.asyncio
    async def test_get_zone_networks_empty(self, mock_settings):
        from src.tools.firewall_zones import get_zone_networks

        zone_data = {"data": {"networkIds": []}}

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")
            mock_instance.get = AsyncMock(return_value=zone_data)

            result = await get_zone_networks("default", "zone-001", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_get_zone_networks_fetch_error_handled(self, mock_settings):
        from src.tools.firewall_zones import get_zone_networks

        zone_data = {"data": {"networkIds": ["net-001"]}}

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.is_authenticated = False
            mock_instance.authenticate = AsyncMock()
            mock_instance.resolve_site_id = AsyncMock(return_value="default")

            call_count = 0

            async def get_side_effect(endpoint):
                nonlocal call_count
                call_count += 1
                if "zones/zone-001" in endpoint:
                    return zone_data
                raise Exception("Network fetch failed")

            mock_instance.get = AsyncMock(side_effect=get_side_effect)

            result = await get_zone_networks("default", "zone-001", mock_settings)

            assert len(result) == 1
            assert result[0]["network_id"] == "net-001"
            assert result[0]["network_name"] is None


class TestGetZoneStatistics:
    @pytest.mark.asyncio
    async def test_get_zone_statistics_not_implemented(self, mock_settings):
        from src.tools.firewall_zones import get_zone_statistics

        with pytest.raises(NotImplementedError, match="does not exist"):
            await get_zone_statistics("default", "zone-001", mock_settings)
