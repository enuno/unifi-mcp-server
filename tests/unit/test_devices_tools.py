"""Unit tests for device management tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.devices import (
    adopt_device,
    execute_port_action,
    get_device_details,
    get_device_statistics,
    list_devices_by_type,
    list_pending_devices,
    search_devices,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_devices_data():
    """Sample devices for testing."""
    return [
        {
            "_id": "507f1f77bcf86cd799439011",  # Valid 24-char hex MongoDB ObjectId
            "mac": "00:11:22:33:44:55",
            "name": "AP-Office",
            "type": "uap",
            "model": "U6-Pro",
            "version": "6.5.55.14777",
            "ip": "192.168.1.10",
            "state": 1,
            "adopted": True,
            "uptime": 86400,
            "cpu": 25,
            "mem": 45,
            "tx_bytes": 1000000,
            "rx_bytes": 2000000,
            "bytes": 3000000,
            "uplink_depth": 1,
        },
        {
            "_id": "507f1f77bcf86cd799439022",  # Valid 24-char hex MongoDB ObjectId
            "mac": "aa:bb:cc:dd:ee:ff",
            "name": "Switch-Main",
            "type": "usw",
            "model": "USW-Pro-24",
            "version": "6.5.59.14783",
            "ip": "192.168.1.20",
            "state": 1,
            "adopted": True,
            "uptime": 172800,
            "cpu": 15,
            "mem": 30,
            "tx_bytes": 5000000,
            "rx_bytes": 10000000,
            "bytes": 15000000,
            "uplink_depth": 0,
        },
    ]


@pytest.fixture
def sample_pending_devices():
    """Sample pending devices."""
    return [
        {
            "_id": "507f1f77bcf86cd799439033",  # Valid 24-char hex MongoDB ObjectId
            "mac": "11:22:33:44:55:66",
            "name": "Unknown Device",
            "type": "uap",
            "model": "U6-Lite",
            "version": "6.5.55.14777",
            "state": 0,
            "adopted": False,
        }
    ]


# ============================================================================
# Test: get_device_details - Device Details Retrieval
# ============================================================================


@pytest.mark.asyncio
async def test_get_device_details_success(settings: Settings, sample_devices_data: list) -> None:
    """Test getting device details successfully."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await get_device_details("site-123", "507f1f77bcf86cd799439011", settings)

        assert result["id"] == "507f1f77bcf86cd799439011"  # Device model uses 'id' not '_id'
        assert result["name"] == "AP-Office"
        assert result["type"] == "uap"


@pytest.mark.asyncio
async def test_get_device_details_not_found(settings: Settings, sample_devices_data: list) -> None:
    """Test getting details for non-existent device."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await get_device_details("site-123", "507f1f77bcf86cd799439099", settings)  # Valid but nonexistent ID


# ============================================================================
# Test: get_device_statistics - Device Statistics Retrieval
# ============================================================================


@pytest.mark.asyncio
async def test_get_device_statistics_success(settings: Settings, sample_devices_data: list) -> None:
    """Test getting device statistics successfully."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await get_device_statistics("site-123", "507f1f77bcf86cd799439011", settings)

        assert result["device_id"] == "507f1f77bcf86cd799439011"
        assert result["uptime"] == 86400
        assert result["cpu"] == 25
        assert result["mem"] == 45
        assert result["tx_bytes"] == 1000000
        assert result["rx_bytes"] == 2000000


@pytest.mark.asyncio
async def test_get_device_statistics_not_found(settings: Settings, sample_devices_data: list) -> None:
    """Test getting statistics for non-existent device."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await get_device_statistics("site-123", "507f1f77bcf86cd799439099", settings)


# ============================================================================
# Test: list_devices_by_type - Device Type Filtering
# ============================================================================


@pytest.mark.asyncio
async def test_list_devices_by_type_success(settings: Settings, sample_devices_data: list) -> None:
    """Test listing devices by type successfully."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_devices_by_type("site-123", "uap", settings)

        assert len(result) == 1
        assert result[0]["type"] == "uap"
        assert result[0]["name"] == "AP-Office"


@pytest.mark.asyncio
async def test_list_devices_by_type_with_pagination(settings: Settings, sample_devices_data: list) -> None:
    """Test listing devices by type with pagination."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_devices_by_type("site-123", "usw", settings, limit=1, offset=0)

        assert len(result) == 1
        assert result[0]["type"] == "usw"


# ============================================================================
# Test: search_devices - Device Search
# ============================================================================


@pytest.mark.asyncio
async def test_search_devices_by_name(settings: Settings, sample_devices_data: list) -> None:
    """Test searching devices by name."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await search_devices("site-123", "Office", settings)

        assert len(result) == 1
        assert result[0]["name"] == "AP-Office"


@pytest.mark.asyncio
async def test_search_devices_by_mac(settings: Settings, sample_devices_data: list) -> None:
    """Test searching devices by MAC address."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await search_devices("site-123", "aa:bb:cc", settings)

        assert len(result) == 1
        assert result[0]["mac"] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.asyncio
async def test_search_devices_by_ip(settings: Settings, sample_devices_data: list) -> None:
    """Test searching devices by IP address."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await search_devices("site-123", "192.168.1.20", settings)

        assert len(result) == 1
        assert result[0]["ip"] == "192.168.1.20"


@pytest.mark.asyncio
async def test_search_devices_with_pagination(settings: Settings, sample_devices_data: list) -> None:
    """Test searching devices with pagination."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await search_devices("site-123", "192.168", settings, limit=1, offset=1)

        assert len(result) == 1


# ============================================================================
# Test: list_pending_devices - Pending Devices Listing
# ============================================================================


@pytest.mark.asyncio
async def test_list_pending_devices_success(settings: Settings, sample_pending_devices: list) -> None:
    """Test listing pending devices successfully."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_pending_devices}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_pending_devices("site-123", settings)

        assert len(result) == 1
        assert result[0]["id"] == "507f1f77bcf86cd799439033"  # Device model uses 'id' not '_id'
        assert result[0]["adopted"] is False


@pytest.mark.asyncio
async def test_list_pending_devices_with_pagination(settings: Settings, sample_pending_devices: list) -> None:
    """Test listing pending devices with pagination."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_pending_devices}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_pending_devices("site-123", settings, limit=10, offset=0)

        assert len(result) == 1
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["limit"] == 10
        assert call_args[1]["params"]["offset"] == 0


# ============================================================================
# Test: adopt_device - Device Adoption
# ============================================================================


@pytest.mark.asyncio
async def test_adopt_device_success(settings: Settings, sample_pending_devices: list) -> None:
    """Test adopting a device successfully."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        adopted_device = sample_pending_devices[0].copy()
        adopted_device["adopted"] = True
        mock_client.post.return_value = {"data": adopted_device}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with patch("src.tools.devices.audit_action", new=AsyncMock()):
            result = await adopt_device("site-123", "507f1f77bcf86cd799439033", settings, name="New AP", confirm=True)

        assert result["id"] == "507f1f77bcf86cd799439033"  # Device model uses 'id' not '_id'
        assert result["adopted"] is True
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_adopt_device_without_confirmation(settings: Settings) -> None:
    """Test that device adoption requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await adopt_device("site-123", "507f1f77bcf86cd799439033", settings, confirm=False)


@pytest.mark.asyncio
async def test_adopt_device_dry_run(settings: Settings) -> None:
    """Test adopting device in dry-run mode."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await adopt_device("site-123", "507f1f77bcf86cd799439033", settings, name="Test AP", confirm=True, dry_run=True)

        assert result["dry_run"] is True
        assert result["device_id"] == "507f1f77bcf86cd799439033"
        assert result["payload"]["name"] == "Test AP"


# ============================================================================
# Test: execute_port_action - Port Action Execution
# ============================================================================


@pytest.mark.asyncio
async def test_execute_port_action_success(settings: Settings) -> None:
    """Test executing port action successfully."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = {"data": {"status": "success"}}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with patch("src.tools.devices.audit_action", new=AsyncMock()):
            result = await execute_port_action(
                "site-123",
                "507f1f77bcf86cd799439011",
                1,
                "power-cycle",
                settings,
                confirm=True,
            )

        assert result["success"] is True
        assert result["action"] == "power-cycle"
        assert result["port_idx"] == 1
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_execute_port_action_with_params(settings: Settings) -> None:
    """Test executing port action with parameters."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.post.return_value = {"data": {"status": "success"}}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with patch("src.tools.devices.audit_action", new=AsyncMock()):
            result = await execute_port_action(
                "site-123",
                "507f1f77bcf86cd799439011",
                5,
                "enable",
                settings,
                params={"poe_mode": "auto"},
                confirm=True,
            )

        assert result["success"] is True
        assert result["action"] == "enable"
        assert result["port_idx"] == 5
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["action"] == "enable"
        assert json_data["params"]["poe_mode"] == "auto"


@pytest.mark.asyncio
async def test_execute_port_action_without_confirmation(settings: Settings) -> None:
    """Test that port action requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await execute_port_action("site-123", "507f1f77bcf86cd799439011", 1, "power-cycle", settings, confirm=False)


@pytest.mark.asyncio
async def test_execute_port_action_dry_run(settings: Settings) -> None:
    """Test executing port action in dry-run mode."""
    with patch("src.tools.devices.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await execute_port_action(
            "site-123",
            "507f1f77bcf86cd799439011",
            3,
            "disable",
            settings,
            params={"reason": "maintenance"},
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["device_id"] == "507f1f77bcf86cd799439011"
        assert result["port_idx"] == 3
        assert result["payload"]["action"] == "disable"
        assert result["payload"]["params"]["reason"] == "maintenance"
