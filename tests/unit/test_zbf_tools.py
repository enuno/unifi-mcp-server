"""Unit tests for Zone-Based Firewall (ZBF) tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools import firewall_zones, zbf_matrix
from src.utils import ValidationError


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings for testing."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud")
    return Settings()


@pytest.fixture
def sample_zone_data() -> dict:
    """Sample firewall zone data."""
    return {
        "data": [
            {
                "_id": "zone-lan",
                "site_id": "default",
                "name": "LAN Zone",
                "description": "Local Area Network",
                "networks": ["net-001", "net-002"],
            },
            {
                "_id": "zone-wan",
                "site_id": "default",
                "name": "WAN Zone",
                "description": "Wide Area Network",
                "networks": ["net-wan-001"],
            },
        ]
    }


@pytest.fixture
def sample_zbf_matrix_data() -> dict:
    """Sample ZBF matrix data."""
    return {
        "data": {
            "site_id": "default",
            "zones": ["zone-lan", "zone-wan", "zone-guest"],
            "policies": [
                {
                    "source_zone_id": "zone-lan",
                    "destination_zone_id": "zone-wan",
                    "action": "allow",
                    "enabled": True,
                },
                {
                    "source_zone_id": "zone-guest",
                    "destination_zone_id": "zone-lan",
                    "action": "deny",
                    "enabled": True,
                },
            ],
            "default_policy": "allow",
        }
    }


@pytest.fixture
def sample_zone_policies_data() -> dict:
    """Sample zone policies data."""
    return {
        "data": [
            {
                "source_zone_id": "zone-lan",
                "destination_zone_id": "zone-wan",
                "action": "allow",
                "description": "Allow LAN to WAN",
                "enabled": True,
            },
            {
                "source_zone_id": "zone-lan",
                "destination_zone_id": "zone-dmz",
                "action": "deny",
                "description": "Block LAN to DMZ",
                "enabled": True,
            },
        ]
    }


# ============================================================================
# Firewall Zone Tools Tests
# ============================================================================


class TestFirewallZoneTools:
    """Test suite for firewall zone management tools."""

    @pytest.mark.asyncio
    async def test_list_firewall_zones(
        self, mock_settings: Settings, sample_zone_data: dict
    ) -> None:
        """Test listing firewall zones."""
        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=sample_zone_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await firewall_zones.list_firewall_zones("default", mock_settings)

            assert len(result) == 2
            assert result[0]["id"] == "zone-lan"
            assert result[0]["name"] == "LAN Zone"
            assert result[1]["id"] == "zone-wan"
            mock_instance.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_firewall_zone_minimal(self, mock_settings: Settings) -> None:
        """Test creating a firewall zone with minimal parameters."""
        zone_response = {
            "data": {
                "_id": "zone-new",
                "site_id": "default",
                "name": "New Zone",
                "description": None,
                "networks": [],
            }
        }

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.post = AsyncMock(return_value=zone_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            with patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock):
                result = await firewall_zones.create_firewall_zone(
                    "default",
                    "New Zone",
                    mock_settings,
                    confirm=True,
                )

            assert result["id"] == "zone-new"
            assert result["name"] == "New Zone"
            mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_firewall_zone_full(self, mock_settings: Settings) -> None:
        """Test creating a firewall zone with all parameters."""
        zone_response = {
            "data": {
                "_id": "zone-dmz",
                "site_id": "default",
                "name": "DMZ Zone",
                "description": "Demilitarized Zone",
                "networks": ["net-dmz-001"],
            }
        }

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.post = AsyncMock(return_value=zone_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            with patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock):
                result = await firewall_zones.create_firewall_zone(
                    "default",
                    "DMZ Zone",
                    mock_settings,
                    description="Demilitarized Zone",
                    network_ids=["net-dmz-001"],
                    confirm=True,
                )

            assert result["id"] == "zone-dmz"
            assert result["description"] == "Demilitarized Zone"
            assert "net-dmz-001" in result["network_ids"]

    @pytest.mark.asyncio
    async def test_create_firewall_zone_dry_run(self, mock_settings: Settings) -> None:
        """Test creating a firewall zone with dry run."""
        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await firewall_zones.create_firewall_zone(
                "default",
                "Test Zone",
                mock_settings,
                description="Test description",
                confirm=True,
                dry_run=True,
            )

        assert result["dry_run"] is True
        assert result["payload"]["name"] == "Test Zone"
        assert result["payload"]["description"] == "Test description"

    @pytest.mark.asyncio
    async def test_create_firewall_zone_without_confirmation(self, mock_settings: Settings) -> None:
        """Test creating a firewall zone without confirmation raises error."""
        with pytest.raises(ValidationError, match="confirmation"):
            await firewall_zones.create_firewall_zone(
                "default",
                "Test Zone",
                mock_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_update_firewall_zone(self, mock_settings: Settings) -> None:
        """Test updating a firewall zone."""
        zone_response = {
            "data": {
                "_id": "zone-lan",
                "site_id": "default",
                "name": "Updated LAN Zone",
                "description": "Updated description",
                "networks": ["net-001"],
            }
        }

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.put = AsyncMock(return_value=zone_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            with patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock):
                result = await firewall_zones.update_firewall_zone(
                    "default",
                    "zone-lan",
                    mock_settings,
                    name="Updated LAN Zone",
                    description="Updated description",
                    confirm=True,
                )

            assert result["id"] == "zone-lan"
            assert result["name"] == "Updated LAN Zone"
            assert result["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_assign_network_to_zone(self, mock_settings: Settings) -> None:
        """Test assigning a network to a zone."""
        zone_response = {
            "data": {
                "_id": "zone-lan",
                "name": "LAN Zone",
                "networks": ["net-001"],
            }
        }

        network_response = {
            "data": {
                "_id": "net-002",
                "name": "Office Network",
            }
        }

        updated_zone_response = {
            "data": {
                "_id": "zone-lan",
                "name": "LAN Zone",
                "networks": ["net-001", "net-002"],
            }
        }

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False

            # Mock multiple get/put calls
            mock_instance.get = AsyncMock(side_effect=[network_response, zone_response])
            mock_instance.put = AsyncMock(return_value=updated_zone_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            with patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock):
                result = await firewall_zones.assign_network_to_zone(
                    "default",
                    "zone-lan",
                    "net-002",
                    mock_settings,
                    confirm=True,
                )

            assert result["zone_id"] == "zone-lan"
            assert result["network_id"] == "net-002"
            assert result["network_name"] == "Office Network"

    @pytest.mark.asyncio
    async def test_assign_network_already_assigned(self, mock_settings: Settings) -> None:
        """Test assigning a network that's already assigned."""
        zone_response = {
            "data": {
                "_id": "zone-lan",
                "name": "LAN Zone",
                "networks": ["net-001", "net-002"],  # net-002 already assigned
            }
        }

        network_response = {
            "data": {
                "_id": "net-002",
                "name": "Office Network",
            }
        }

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(side_effect=[network_response, zone_response])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await firewall_zones.assign_network_to_zone(
                "default",
                "zone-lan",
                "net-002",
                mock_settings,
                confirm=True,
            )

            assert result["zone_id"] == "zone-lan"
            assert result["network_id"] == "net-002"
            # Should not call put if already assigned
            assert not mock_instance.put.called

    @pytest.mark.asyncio
    async def test_get_zone_networks(self, mock_settings: Settings) -> None:
        """Test getting networks in a zone."""
        zone_response = {
            "data": {
                "_id": "zone-lan",
                "networks": ["net-001", "net-002"],
            }
        }

        network_1_response = {
            "data": {
                "_id": "net-001",
                "name": "Main Network",
            }
        }

        network_2_response = {
            "data": {
                "_id": "net-002",
                "name": "Guest Network",
            }
        }

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(
                side_effect=[zone_response, network_1_response, network_2_response]
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await firewall_zones.get_zone_networks("default", "zone-lan", mock_settings)

            assert len(result) == 2
            assert result[0]["network_id"] == "net-001"
            assert result[0]["network_name"] == "Main Network"
            assert result[1]["network_id"] == "net-002"
            assert result[1]["network_name"] == "Guest Network"

    @pytest.mark.asyncio
    async def test_delete_firewall_zone(self, mock_settings: Settings) -> None:
        """Test deleting a firewall zone."""
        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.delete = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            with patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock):
                result = await firewall_zones.delete_firewall_zone(
                    "default",
                    "zone-old",
                    mock_settings,
                    confirm=True,
                )

            assert result["status"] == "success"
            assert result["zone_id"] == "zone-old"
            assert result["action"] == "deleted"
            mock_instance.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_firewall_zone_without_confirmation(
        self, mock_settings: Settings
    ) -> None:
        """Test deleting a firewall zone without confirmation raises error."""
        with pytest.raises(ValidationError, match="confirmation"):
            await firewall_zones.delete_firewall_zone(
                "default",
                "zone-old",
                mock_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_delete_firewall_zone_dry_run(self, mock_settings: Settings) -> None:
        """Test deleting a firewall zone with dry run."""
        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await firewall_zones.delete_firewall_zone(
                "default",
                "zone-test",
                mock_settings,
                confirm=True,
                dry_run=True,
            )

        assert result["dry_run"] is True
        assert result["zone_id"] == "zone-test"
        assert result["action"] == "would_delete"
        assert not mock_instance.delete.called

    @pytest.mark.asyncio
    async def test_unassign_network_from_zone(self, mock_settings: Settings) -> None:
        """Test unassigning a network from a zone."""
        zone_response = {
            "data": {
                "_id": "zone-lan",
                "networks": ["net-001", "net-002", "net-003"],
            }
        }

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(return_value=zone_response)
            mock_instance.put = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            with patch("src.tools.firewall_zones.audit_action", new_callable=AsyncMock):
                result = await firewall_zones.unassign_network_from_zone(
                    "default",
                    "zone-lan",
                    "net-002",
                    mock_settings,
                    confirm=True,
                )

            assert result["status"] == "success"
            assert result["zone_id"] == "zone-lan"
            assert result["network_id"] == "net-002"
            assert result["action"] == "unassigned"

            # Verify PUT was called with correct payload
            mock_instance.put.assert_called_once()
            call_args = mock_instance.put.call_args
            assert call_args[1]["json_data"]["networks"] == ["net-001", "net-003"]

    @pytest.mark.asyncio
    async def test_unassign_network_dry_run(self, mock_settings: Settings) -> None:
        """Test unassigning a network with dry run."""
        zone_response = {
            "data": {
                "_id": "zone-lan",
                "networks": ["net-001", "net-002"],
            }
        }

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.get = AsyncMock(return_value=zone_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await firewall_zones.unassign_network_from_zone(
                "default",
                "zone-lan",
                "net-002",
                mock_settings,
                confirm=True,
                dry_run=True,
            )

        assert result["dry_run"] is True
        assert result["payload"]["networks"] == ["net-001"]
        assert not mock_instance.put.called

    @pytest.mark.asyncio
    async def test_get_zone_statistics(self, mock_settings: Settings) -> None:
        """Test getting zone traffic statistics."""
        stats_response = {
            "data": {
                "zone_id": "zone-lan",
                "bytes_in": 1024000,
                "bytes_out": 2048000,
                "packets_in": 5000,
                "packets_out": 6000,
                "connections": 150,
            }
        }

        with patch("src.tools.firewall_zones.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(return_value=stats_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await firewall_zones.get_zone_statistics(
                "default",
                "zone-lan",
                mock_settings,
            )

            assert result["zone_id"] == "zone-lan"
            assert result["bytes_in"] == 1024000
            assert result["bytes_out"] == 2048000
            assert result["connections"] == 150
            mock_instance.get.assert_called_once_with(
                "/integration/v1/sites/default/firewall/zones/zone-lan/statistics"
            )


# ============================================================================
# ZBF Matrix Tools Tests
# ============================================================================


class TestZBFMatrixTools:
    """Test suite for ZBF matrix management tools."""

    @pytest.mark.asyncio
    async def test_get_zbf_matrix(
        self, mock_settings: Settings, sample_zbf_matrix_data: dict
    ) -> None:
        """Test getting ZBF matrix."""
        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(return_value=sample_zbf_matrix_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await zbf_matrix.get_zbf_matrix("default", mock_settings)

            assert result["site_id"] == "default"
            assert len(result["zones"]) == 3
            assert len(result["policies"]) == 2
            assert result["default_policy"] == "allow"

    @pytest.mark.asyncio
    async def test_get_zbf_matrix_fallback_to_zones(self, mock_settings: Settings) -> None:
        """Test getting ZBF matrix when matrix endpoint doesn't exist."""
        zones_response = {
            "data": [
                {"_id": "zone-lan", "name": "LAN"},
                {"_id": "zone-wan", "name": "WAN"},
            ]
        }

        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False

            # First call (matrix) raises exception, second call (zones) succeeds
            mock_instance.get = AsyncMock(side_effect=[Exception("404 not found"), zones_response])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await zbf_matrix.get_zbf_matrix("default", mock_settings)

            assert result["site_id"] == "default"
            assert len(result["zones"]) == 2
            assert result["zones"] == ["zone-lan", "zone-wan"]
            assert result["policies"] == []
            assert result["default_policy"] == "allow"

    @pytest.mark.asyncio
    async def test_get_zone_policies(
        self, mock_settings: Settings, sample_zone_policies_data: dict
    ) -> None:
        """Test getting zone policies."""
        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(return_value=sample_zone_policies_data)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await zbf_matrix.get_zone_policies("default", "zone-lan", mock_settings)

            assert len(result) == 2
            assert result[0]["source_zone_id"] == "zone-lan"
            assert result[0]["destination_zone_id"] == "zone-wan"
            assert result[0]["action"] == "allow"
            assert result[1]["action"] == "deny"

    @pytest.mark.asyncio
    async def test_get_zone_policies_endpoint_not_found(self, mock_settings: Settings) -> None:
        """Test getting zone policies when endpoint doesn't exist."""
        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(side_effect=Exception("404 not found"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await zbf_matrix.get_zone_policies("default", "zone-lan", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_update_zbf_policy(self, mock_settings: Settings) -> None:
        """Test updating ZBF policy."""
        policy_response = {
            "data": {
                "source_zone_id": "zone-guest",
                "destination_zone_id": "zone-lan",
                "action": "deny",
                "description": "Block guest to LAN",
                "priority": 100,
                "enabled": True,
            }
        }

        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.put = AsyncMock(return_value=policy_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            with patch("src.tools.zbf_matrix.audit_action", new_callable=AsyncMock):
                result = await zbf_matrix.update_zbf_policy(
                    "default",
                    "zone-guest",
                    "zone-lan",
                    "deny",
                    mock_settings,
                    description="Block guest to LAN",
                    priority=100,
                    confirm=True,
                )

            assert result["source_zone_id"] == "zone-guest"
            assert result["destination_zone_id"] == "zone-lan"
            assert result["action"] == "deny"
            assert result["description"] == "Block guest to LAN"
            assert result["priority"] == 100

    @pytest.mark.asyncio
    async def test_update_zbf_policy_invalid_action(self, mock_settings: Settings) -> None:
        """Test updating ZBF policy with invalid action."""
        with pytest.raises(ValueError, match="allow.*deny"):
            await zbf_matrix.update_zbf_policy(
                "default",
                "zone-lan",
                "zone-wan",
                "reject",  # Invalid action
                mock_settings,
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_update_zbf_policy_without_confirmation(self, mock_settings: Settings) -> None:
        """Test updating ZBF policy without confirmation."""
        with pytest.raises(ValidationError, match="confirmation"):
            await zbf_matrix.update_zbf_policy(
                "default",
                "zone-lan",
                "zone-wan",
                "allow",
                mock_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_update_zbf_policy_dry_run(self, mock_settings: Settings) -> None:
        """Test updating ZBF policy with dry run."""
        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await zbf_matrix.update_zbf_policy(
                "default",
                "zone-lan",
                "zone-wan",
                "allow",
                mock_settings,
                description="Test policy",
                confirm=True,
                dry_run=True,
            )

        assert result["dry_run"] is True
        assert result["payload"]["source_zone_id"] == "zone-lan"
        assert result["payload"]["destination_zone_id"] == "zone-wan"
        assert result["payload"]["action"] == "allow"

    @pytest.mark.asyncio
    async def test_block_application_by_zone(self, mock_settings: Settings) -> None:
        """Test blocking an application by zone."""
        dpi_response = {
            "data": [
                {"_id": "app-facebook", "name": "Facebook"},
                {"_id": "app-twitter", "name": "Twitter"},
            ]
        }

        rule_response = {
            "data": {
                "zone_id": "zone-guest",
                "application_id": "app-facebook",
                "application_name": "Facebook",
                "action": "block",
                "enabled": True,
            }
        }

        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(return_value=dpi_response)
            mock_instance.post = AsyncMock(return_value=rule_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            with patch("src.tools.zbf_matrix.audit_action", new_callable=AsyncMock):
                result = await zbf_matrix.block_application_by_zone(
                    "default",
                    "zone-guest",
                    "app-facebook",
                    mock_settings,
                    confirm=True,
                )

            assert result["zone_id"] == "zone-guest"
            assert result["application_id"] == "app-facebook"
            assert result["application_name"] == "Facebook"
            assert result["action"] == "block"
            assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_block_application_invalid_action(self, mock_settings: Settings) -> None:
        """Test blocking application with invalid action."""
        with pytest.raises(ValueError, match="block.*allow"):
            await zbf_matrix.block_application_by_zone(
                "default",
                "zone-guest",
                "app-001",
                mock_settings,
                action="deny",  # Invalid action
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_list_blocked_applications(self, mock_settings: Settings) -> None:
        """Test listing blocked applications."""
        blocked_apps_response = {
            "data": [
                {
                    "zone_id": "zone-guest",
                    "application_id": "app-facebook",
                    "application_name": "Facebook",
                    "action": "block",
                    "enabled": True,
                },
                {
                    "zone_id": "zone-guest",
                    "application_id": "app-twitter",
                    "application_name": "Twitter",
                    "action": "block",
                    "enabled": True,
                },
            ]
        }

        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(return_value=blocked_apps_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await zbf_matrix.list_blocked_applications(
                "default", "zone-guest", mock_settings
            )

            assert len(result) == 2
            assert result[0]["application_id"] == "app-facebook"
            assert result[1]["application_id"] == "app-twitter"

    @pytest.mark.asyncio
    async def test_list_blocked_applications_endpoint_not_found(
        self, mock_settings: Settings
    ) -> None:
        """Test listing blocked applications when endpoint doesn't exist."""
        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(side_effect=Exception("404 not found"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await zbf_matrix.list_blocked_applications("default", None, mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_blocked_applications_no_settings(self) -> None:
        """Test listing blocked applications without settings."""
        with pytest.raises(ValueError, match="Settings is required"):
            await zbf_matrix.list_blocked_applications("default", None, None)

    @pytest.mark.asyncio
    async def test_get_zone_matrix_policy(self, mock_settings: Settings) -> None:
        """Test getting a specific zone-to-zone policy."""
        policy_response = {
            "data": {
                "source_zone_id": "zone-lan",
                "destination_zone_id": "zone-wan",
                "action": "allow",
                "description": "Allow LAN to WAN",
                "priority": 100,
                "enabled": True,
            }
        }

        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.get = AsyncMock(return_value=policy_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await zbf_matrix.get_zone_matrix_policy(
                "default",
                "zone-lan",
                "zone-wan",
                mock_settings,
            )

            assert result["source_zone_id"] == "zone-lan"
            assert result["destination_zone_id"] == "zone-wan"
            assert result["action"] == "allow"
            assert result["description"] == "Allow LAN to WAN"
            assert result["priority"] == 100

    @pytest.mark.asyncio
    async def test_get_zone_matrix_policy_fallback(self, mock_settings: Settings) -> None:
        """Test getting a specific policy with fallback to all policies."""
        policies_response = {
            "data": [
                {
                    "source_zone_id": "zone-lan",
                    "destination_zone_id": "zone-wan",
                    "action": "allow",
                    "enabled": True,
                },
                {
                    "source_zone_id": "zone-lan",
                    "destination_zone_id": "zone-dmz",
                    "action": "deny",
                    "enabled": True,
                },
            ]
        }

        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            # First call fails (specific policy), second call succeeds (all policies)
            mock_instance.get = AsyncMock(
                side_effect=[Exception("404 not found"), policies_response]
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            with patch("src.tools.zbf_matrix.get_zone_policies", new_callable=AsyncMock) as mock_get_policies:
                mock_get_policies.return_value = [
                    {
                        "source_zone_id": "zone-lan",
                        "destination_zone_id": "zone-wan",
                        "action": "allow",
                        "enabled": True,
                    },
                    {
                        "source_zone_id": "zone-lan",
                        "destination_zone_id": "zone-dmz",
                        "action": "deny",
                        "enabled": True,
                    },
                ]

                result = await zbf_matrix.get_zone_matrix_policy(
                    "default",
                    "zone-lan",
                    "zone-wan",
                    mock_settings,
                )

                assert result["source_zone_id"] == "zone-lan"
                assert result["destination_zone_id"] == "zone-wan"
                assert result["action"] == "allow"

    @pytest.mark.asyncio
    async def test_delete_zbf_policy(self, mock_settings: Settings) -> None:
        """Test deleting a zone-to-zone policy."""
        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.delete = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            with patch("src.tools.zbf_matrix.audit_action", new_callable=AsyncMock):
                result = await zbf_matrix.delete_zbf_policy(
                    "default",
                    "zone-guest",
                    "zone-lan",
                    mock_settings,
                    confirm=True,
                )

            assert result["status"] == "success"
            assert result["source_zone_id"] == "zone-guest"
            assert result["destination_zone_id"] == "zone-lan"
            assert result["action"] == "deleted"
            mock_instance.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_zbf_policy_without_confirmation(self, mock_settings: Settings) -> None:
        """Test deleting a ZBF policy without confirmation raises error."""
        with pytest.raises(ValidationError, match="confirmation"):
            await zbf_matrix.delete_zbf_policy(
                "default",
                "zone-guest",
                "zone-lan",
                mock_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_delete_zbf_policy_dry_run(self, mock_settings: Settings) -> None:
        """Test deleting a ZBF policy with dry run."""
        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = True
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await zbf_matrix.delete_zbf_policy(
                "default",
                "zone-test1",
                "zone-test2",
                mock_settings,
                confirm=True,
                dry_run=True,
            )

        assert result["dry_run"] is True
        assert result["source_zone_id"] == "zone-test1"
        assert result["destination_zone_id"] == "zone-test2"
        assert result["action"] == "would_delete"
        assert not mock_instance.delete.called

    @pytest.mark.asyncio
    async def test_delete_zbf_policy_endpoint_not_found(self, mock_settings: Settings) -> None:
        """Test deleting a ZBF policy when endpoint doesn't exist."""
        with patch("src.tools.zbf_matrix.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.authenticate = AsyncMock()
            mock_instance.is_authenticated = False
            mock_instance.delete = AsyncMock(side_effect=Exception("404 not found"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance

            result = await zbf_matrix.delete_zbf_policy(
                "default",
                "zone-test1",
                "zone-test2",
                mock_settings,
                confirm=True,
            )

            assert result["dry_run"] is True
            assert result["source_zone_id"] == "zone-test1"
            assert result["destination_zone_id"] == "zone-test2"
            assert "note" in result
