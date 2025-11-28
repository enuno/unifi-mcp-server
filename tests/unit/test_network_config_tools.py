"""Unit tests for network configuration tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.network_config import create_network, delete_network, update_network
from src.utils.exceptions import ResourceNotFoundError, ValidationError

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_network_data():
    """Sample network data for testing."""
    return {
        "_id": "507f1f77bcf86cd799439011",
        "name": "Corporate LAN",
        "vlan": 10,
        "ip_subnet": "192.168.10.0/24",
        "purpose": "corporate",
        "dhcpd_enabled": True,
        "dhcpd_start": "192.168.10.10",
        "dhcpd_stop": "192.168.10.254",
        "dhcpd_dns_1": "8.8.8.8",
        "dhcpd_dns_2": "8.8.4.4",
        "domain_name": "corporate.local",
    }


@pytest.fixture
def sample_networks_list(sample_network_data):
    """Sample networks list for testing."""
    return [
        sample_network_data,
        {
            "_id": "507f1f77bcf86cd799439012",
            "name": "Guest WiFi",
            "vlan": 20,
            "ip_subnet": "192.168.20.0/24",
            "purpose": "guest",
            "dhcpd_enabled": True,
        },
    ]


# ============================================================================
# Test: create_network - Network Creation
# ============================================================================


@pytest.mark.asyncio
async def test_create_network_success(
    settings: Settings, sample_network_data: dict
) -> None:
    """Test creating a network successfully with all parameters."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = {"data": [sample_network_data]}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_network(
            "site-123",
            "Corporate LAN",
            10,
            "192.168.10.0/24",
            settings,
            purpose="corporate",
            dhcp_enabled=True,
            dhcp_start="192.168.10.10",
            dhcp_stop="192.168.10.254",
            dhcp_dns_1="8.8.8.8",
            dhcp_dns_2="8.8.4.4",
            domain_name="corporate.local",
            confirm=True,
        )

        assert result["_id"] == "507f1f77bcf86cd799439011"
        assert result["name"] == "Corporate LAN"
        assert result["vlan"] == 10
        assert result["purpose"] == "corporate"
        mock_client.post.assert_called_once()

        # Verify the payload structure
        call_args = mock_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "Corporate LAN"
        assert json_data["vlan"] == 10
        assert json_data["ip_subnet"] == "192.168.10.0/24"
        assert json_data["purpose"] == "corporate"
        assert json_data["dhcpd_enabled"] is True
        assert json_data["dhcpd_start"] == "192.168.10.10"
        assert json_data["dhcpd_stop"] == "192.168.10.254"


@pytest.mark.asyncio
async def test_create_network_minimal(settings: Settings) -> None:
    """Test creating a network with minimal parameters (DHCP disabled)."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = {
            "data": [
                {
                    "_id": "507f1f77bcf86cd799439013",
                    "name": "VLAN Only",
                    "vlan": 30,
                    "ip_subnet": "10.0.30.0/24",
                    "purpose": "vlan-only",
                    "dhcpd_enabled": False,
                }
            ]
        }
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_network(
            "site-123",
            "VLAN Only",
            30,
            "10.0.30.0/24",
            settings,
            purpose="vlan-only",
            dhcp_enabled=False,
            confirm=True,
        )

        assert result["name"] == "VLAN Only"
        assert result["dhcpd_enabled"] is False

        # Verify DHCP fields are not in payload when disabled
        call_args = mock_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert "dhcpd_start" not in json_data
        assert "dhcpd_stop" not in json_data


@pytest.mark.asyncio
async def test_create_network_invalid_vlan_id_zero(settings: Settings) -> None:
    """Test creating network with VLAN ID of 0 (invalid)."""
    with pytest.raises(ValidationError, match="Invalid VLAN ID 0"):
        await create_network(
            "site-123",
            "Test Network",
            0,  # Invalid: must be 1-4094
            "192.168.1.0/24",
            settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_network_invalid_vlan_id_too_high(settings: Settings) -> None:
    """Test creating network with VLAN ID of 4095 (invalid)."""
    with pytest.raises(ValidationError, match="Invalid VLAN ID 4095"):
        await create_network(
            "site-123",
            "Test Network",
            4095,  # Invalid: must be 1-4094
            "192.168.1.0/24",
            settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_network_invalid_vlan_id_negative(settings: Settings) -> None:
    """Test creating network with negative VLAN ID."""
    with pytest.raises(ValidationError, match="Invalid VLAN ID -10"):
        await create_network(
            "site-123",
            "Test Network",
            -10,  # Invalid: must be positive
            "192.168.1.0/24",
            settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_network_invalid_purpose(settings: Settings) -> None:
    """Test creating network with invalid purpose enum."""
    with pytest.raises(ValidationError, match="Invalid purpose 'invalid-purpose'"):
        await create_network(
            "site-123",
            "Test Network",
            10,
            "192.168.1.0/24",
            settings,
            purpose="invalid-purpose",  # Must be: corporate, guest, vlan-only, wan
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_network_invalid_subnet_no_cidr(settings: Settings) -> None:
    """Test creating network with subnet missing CIDR notation."""
    with pytest.raises(ValidationError, match="Invalid subnet.*CIDR"):
        await create_network(
            "site-123",
            "Test Network",
            10,
            "192.168.1.0",  # Missing /24 CIDR notation
            settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_network_dry_run(settings: Settings) -> None:
    """Test creating network in dry-run mode."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await create_network(
            "site-123",
            "Test Network",
            10,
            "192.168.1.0/24",
            settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert "would_create" in result
        assert result["would_create"]["name"] == "Test Network"
        assert result["would_create"]["vlan"] == 10

        # Verify no API call was made
        mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_network_without_confirmation(settings: Settings) -> None:
    """Test that network creation requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await create_network(
            "site-123",
            "Test Network",
            10,
            "192.168.1.0/24",
            settings,
            confirm=False,  # Must be True
        )


# ============================================================================
# Test: update_network - Network Modification
# ============================================================================


@pytest.mark.asyncio
async def test_update_network_success(
    settings: Settings, sample_networks_list: list
) -> None:
    """Test updating network with single parameter."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None

        # First GET call returns existing networks
        updated_network = sample_networks_list[0].copy()
        updated_network["name"] = "Updated Corporate LAN"

        mock_client.get.return_value = {"data": sample_networks_list}
        mock_client.put.return_value = {"data": [updated_network]}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await update_network(
            "site-123",
            "507f1f77bcf86cd799439011",
            settings,
            name="Updated Corporate LAN",
            confirm=True,
        )

        assert result["name"] == "Updated Corporate LAN"
        mock_client.get.assert_called_once()
        mock_client.put.assert_called_once()


@pytest.mark.asyncio
async def test_update_network_multiple_params(
    settings: Settings, sample_networks_list: list
) -> None:
    """Test updating network with multiple parameters."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None

        updated_network = sample_networks_list[0].copy()
        updated_network.update(
            {
                "name": "New Name",
                "vlan": 15,
                "ip_subnet": "172.16.15.0/24",
                "dhcpd_dns_1": "1.1.1.1",
            }
        )

        mock_client.get.return_value = {"data": sample_networks_list}
        mock_client.put.return_value = {"data": [updated_network]}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await update_network(
            "site-123",
            "507f1f77bcf86cd799439011",
            settings,
            name="New Name",
            vlan_id=15,
            subnet="172.16.15.0/24",
            dhcp_dns_1="1.1.1.1",
            confirm=True,
        )

        assert result["name"] == "New Name"
        assert result["vlan"] == 15
        assert result["ip_subnet"] == "172.16.15.0/24"
        assert result["dhcpd_dns_1"] == "1.1.1.1"

        # Verify PUT payload includes updates
        call_args = mock_client.put.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["name"] == "New Name"
        assert json_data["vlan"] == 15
        assert json_data["ip_subnet"] == "172.16.15.0/24"


@pytest.mark.asyncio
async def test_update_network_not_found(settings: Settings) -> None:
    """Test updating non-existent network."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": []}  # No networks
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await update_network(
                "site-123",
                "nonexistent-network-id",
                settings,
                name="New Name",
                confirm=True,
            )


@pytest.mark.asyncio
async def test_update_network_invalid_vlan_id(settings: Settings) -> None:
    """Test updating network with invalid VLAN ID."""
    with pytest.raises(ValidationError, match="Invalid VLAN ID"):
        await update_network(
            "site-123",
            "507f1f77bcf86cd799439011",
            settings,
            vlan_id=5000,  # Out of range
            confirm=True,
        )


@pytest.mark.asyncio
async def test_update_network_dry_run(
    settings: Settings, sample_networks_list: list
) -> None:
    """Test updating network in dry-run mode."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await update_network(
            "site-123",
            "507f1f77bcf86cd799439011",
            settings,
            name="New Name",
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert "would_update" in result
        assert result["would_update"]["name"] == "New Name"

        # Verify no API calls were made
        mock_client.get.assert_not_called()
        mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_update_network_preserves_fields(
    settings: Settings, sample_networks_list: list
) -> None:
    """Test that update preserves unmodified fields."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None

        original_network = sample_networks_list[0].copy()
        updated_network = original_network.copy()
        updated_network["name"] = "Updated Name"

        mock_client.get.return_value = {"data": sample_networks_list}
        mock_client.put.return_value = {"data": [updated_network]}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        await update_network(
            "site-123",
            "507f1f77bcf86cd799439011",
            settings,
            name="Updated Name",
            confirm=True,
        )

        # Verify PUT payload preserves original fields
        call_args = mock_client.put.call_args
        json_data = call_args[1]["json_data"]

        # Should preserve VLAN, subnet, purpose, etc.
        assert json_data["vlan"] == original_network["vlan"]
        assert json_data["ip_subnet"] == original_network["ip_subnet"]
        assert json_data["purpose"] == original_network["purpose"]
        assert json_data["dhcpd_enabled"] == original_network["dhcpd_enabled"]
        # Should update name
        assert json_data["name"] == "Updated Name"


# ============================================================================
# Test: delete_network - Network Deletion
# ============================================================================


@pytest.mark.asyncio
async def test_delete_network_success(
    settings: Settings, sample_networks_list: list
) -> None:
    """Test deleting a network successfully."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_networks_list}
        mock_client.delete.return_value = {"success": True}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await delete_network(
            "site-123", "507f1f77bcf86cd799439011", settings, confirm=True
        )

        assert result["success"] is True
        assert result["deleted_network_id"] == "507f1f77bcf86cd799439011"
        mock_client.get.assert_called_once()
        mock_client.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_network_not_found(settings: Settings) -> None:
    """Test deleting non-existent network."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": []}  # No networks
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await delete_network(
                "site-123", "nonexistent-network-id", settings, confirm=True
            )


@pytest.mark.asyncio
async def test_delete_network_dry_run(settings: Settings) -> None:
    """Test deleting network in dry-run mode."""
    with patch("src.tools.network_config.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await delete_network(
            "site-123",
            "507f1f77bcf86cd799439011",
            settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["would_delete"] == "507f1f77bcf86cd799439011"

        # Verify no API calls were made
        mock_client.get.assert_not_called()
        mock_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_network_without_confirmation(settings: Settings) -> None:
    """Test that network deletion requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await delete_network(
            "site-123",
            "507f1f77bcf86cd799439011",
            settings,
            confirm=False,  # Must be True
        )
