"""Unit tests for device control tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.device_control import (
    locate_device,
    restart_device,
    upgrade_device,
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
            "mac": "00:11:22:33:44:55",
            "name": "AP-Office",
            "type": "uap",
            "model": "U6-Pro",
            "version": "6.5.55.14777",
            "state": 1,
            "adopted": True,
        },
        {
            "mac": "aa:bb:cc:dd:ee:ff",
            "name": "Switch-Main",
            "type": "usw",
            "model": "USW-Pro-24",
            "version": "6.5.59.14783",
            "state": 1,
            "adopted": True,
        },
    ]


@pytest.fixture
def sample_success_response():
    """Sample success response."""
    return {"success": True}


# ============================================================================
# Test: restart_device - Device Restart
# ============================================================================


@pytest.mark.asyncio
async def test_restart_device_success(
    settings: Settings, sample_devices_data: list, sample_success_response: dict
) -> None:
    """Test restarting a device successfully."""
    with patch("src.tools.device_control.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.post.return_value = sample_success_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await restart_device("site-123", "00:11:22:33:44:55", settings, confirm=True)

        assert result["success"] is True
        assert result["device_mac"] == "00:11:22:33:44:55"
        assert "restart initiated" in result["message"].lower()
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_restart_device_without_confirmation(settings: Settings) -> None:
    """Test that device restart requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await restart_device("site-123", "00:11:22:33:44:55", settings, confirm=False)


@pytest.mark.asyncio
async def test_restart_device_dry_run(settings: Settings) -> None:
    """Test restarting device in dry-run mode."""
    result = await restart_device("site-123", "00:11:22:33:44:55", settings, confirm=True, dry_run=True)

    assert result["dry_run"] is True
    assert result["would_restart"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_restart_device_not_found(settings: Settings) -> None:
    """Test restarting non-existent device."""
    with patch("src.tools.device_control.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = []
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await restart_device("site-123", "99:99:99:99:99:99", settings, confirm=True)


@pytest.mark.asyncio
async def test_restart_device_invalid_mac(settings: Settings) -> None:
    """Test restarting with invalid MAC address."""
    with pytest.raises(ValidationError, match="Invalid MAC address"):
        await restart_device("site-123", "invalid-mac", settings, confirm=True)


# ============================================================================
# Test: locate_device - LED Locate Mode Control
# ============================================================================


@pytest.mark.asyncio
async def test_locate_device_enable_success(
    settings: Settings, sample_devices_data: list, sample_success_response: dict
) -> None:
    """Test enabling locate mode successfully."""
    with patch("src.tools.device_control.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.post.return_value = sample_success_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await locate_device("site-123", "00:11:22:33:44:55", settings, enabled=True, confirm=True)

        assert result["success"] is True
        assert result["device_mac"] == "00:11:22:33:44:55"
        assert result["locate_enabled"] is True
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_locate_device_disable_success(
    settings: Settings, sample_devices_data: list, sample_success_response: dict
) -> None:
    """Test disabling locate mode successfully."""
    with patch("src.tools.device_control.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.post.return_value = sample_success_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await locate_device("site-123", "00:11:22:33:44:55", settings, enabled=False, confirm=True)

        assert result["success"] is True
        assert result["locate_enabled"] is False


@pytest.mark.asyncio
async def test_locate_device_without_confirmation(settings: Settings) -> None:
    """Test that locate mode requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await locate_device("site-123", "00:11:22:33:44:55", settings, confirm=False)


@pytest.mark.asyncio
async def test_locate_device_dry_run(settings: Settings) -> None:
    """Test locate mode in dry-run mode."""
    result = await locate_device("site-123", "00:11:22:33:44:55", settings, enabled=True, confirm=True, dry_run=True)

    assert result["dry_run"] is True
    assert result["would_enable"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_locate_device_not_found(settings: Settings) -> None:
    """Test locate mode for non-existent device."""
    with patch("src.tools.device_control.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = []
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await locate_device("site-123", "99:99:99:99:99:99", settings, confirm=True)


# ============================================================================
# Test: upgrade_device - Firmware Upgrade
# ============================================================================


@pytest.mark.asyncio
async def test_upgrade_device_success(
    settings: Settings, sample_devices_data: list, sample_success_response: dict
) -> None:
    """Test upgrading device firmware successfully."""
    with patch("src.tools.device_control.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.post.return_value = sample_success_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await upgrade_device("site-123", "00:11:22:33:44:55", settings, confirm=True)

        assert result["success"] is True
        assert result["device_mac"] == "00:11:22:33:44:55"
        assert "upgrade initiated" in result["message"].lower()
        assert result["current_version"] == "6.5.55.14777"
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_upgrade_device_with_custom_firmware(
    settings: Settings, sample_devices_data: list, sample_success_response: dict
) -> None:
    """Test upgrading device with custom firmware URL."""
    with patch("src.tools.device_control.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = sample_devices_data
        mock_client.post.return_value = sample_success_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        firmware_url = "https://fw-download.ubnt.com/data/uap/custom.bin"
        result = await upgrade_device(
            "site-123",
            "00:11:22:33:44:55",
            settings,
            firmware_url=firmware_url,
            confirm=True,
        )

        assert result["success"] is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        json_data = call_args[1]["json_data"]
        assert json_data["url"] == firmware_url


@pytest.mark.asyncio
async def test_upgrade_device_without_confirmation(settings: Settings) -> None:
    """Test that device upgrade requires confirmation."""
    with pytest.raises(ValidationError, match="confirmation"):
        await upgrade_device("site-123", "00:11:22:33:44:55", settings, confirm=False)


@pytest.mark.asyncio
async def test_upgrade_device_dry_run(settings: Settings) -> None:
    """Test device upgrade in dry-run mode."""
    result = await upgrade_device("site-123", "00:11:22:33:44:55", settings, confirm=True, dry_run=True)

    assert result["dry_run"] is True
    assert result["would_upgrade"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_upgrade_device_not_found(settings: Settings) -> None:
    """Test upgrading non-existent device."""
    with patch("src.tools.device_control.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = []
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        with pytest.raises(ResourceNotFoundError):
            await upgrade_device("site-123", "99:99:99:99:99:99", settings, confirm=True)
