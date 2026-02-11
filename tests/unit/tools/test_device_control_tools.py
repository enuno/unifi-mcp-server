"""Unit tests for device control tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.device_control as dc_module
from src.tools.device_control import locate_device, restart_device, upgrade_device
from src.utils.exceptions import ResourceNotFoundError, ValidationError


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "local"
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-key"
    settings.local_host = "192.168.2.1"
    settings.local_port = 443
    settings.local_verify_ssl = False
    return settings


# =============================================================================
# restart_device Tests
# =============================================================================


@pytest.mark.asyncio
async def test_restart_device_success(mock_settings):
    """Test successful device restart."""
    mock_devices_response = {
        "data": [
            {
                "_id": "device1",
                "mac": "00:11:22:33:44:55",
                "name": "Test AP",
                "model": "UAP-AC-PRO",
            }
        ]
    }
    mock_restart_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.post = AsyncMock(return_value=mock_restart_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        result = await restart_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    assert result["device_mac"] == "00:11:22:33:44:55"
    assert result["message"] == "Device restart initiated"
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_restart_device_dry_run(mock_settings):
    """Test device restart dry run."""
    result = await restart_device(
        site_id="default",
        device_mac="00:11:22:33:44:55",
        settings=mock_settings,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_restart"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_restart_device_no_confirm(mock_settings):
    """Test device restart fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await restart_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_restart_device_not_found(mock_settings):
    """Test restart of non-existent device."""
    mock_devices_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        with pytest.raises(ResourceNotFoundError):
            await restart_device(
                site_id="default",
                device_mac="aa:bb:cc:dd:ee:ff",
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_restart_device_invalid_mac(mock_settings):
    """Test device restart with invalid MAC address."""
    with pytest.raises(ValidationError) as excinfo:
        await restart_device(
            site_id="default",
            device_mac="invalid-mac",
            settings=mock_settings,
            confirm=True,
        )

    assert "mac" in str(excinfo.value).lower() or "invalid" in str(excinfo.value).lower()


# =============================================================================
# locate_device Tests
# =============================================================================


@pytest.mark.asyncio
async def test_locate_device_enable(mock_settings):
    """Test enabling device locate mode."""
    mock_devices_response = {
        "data": [
            {
                "_id": "device1",
                "mac": "00:11:22:33:44:55",
                "name": "Test AP",
            }
        ]
    }
    mock_locate_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.post = AsyncMock(return_value=mock_locate_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        result = await locate_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            enabled=True,
            confirm=True,
        )

    assert result["success"] is True
    assert result["device_mac"] == "00:11:22:33:44:55"
    assert result["locate_enabled"] is True
    assert result["message"] == "Locate mode enabled"

    # Verify the correct command was sent
    call_args = mock_client.post.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["cmd"] == "set-locate"


@pytest.mark.asyncio
async def test_locate_device_disable(mock_settings):
    """Test disabling device locate mode."""
    mock_devices_response = {
        "data": [
            {
                "_id": "device1",
                "mac": "00:11:22:33:44:55",
                "name": "Test AP",
            }
        ]
    }
    mock_locate_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.post = AsyncMock(return_value=mock_locate_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        result = await locate_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            enabled=False,
            confirm=True,
        )

    assert result["success"] is True
    assert result["locate_enabled"] is False
    assert result["message"] == "Locate mode disabled"

    # Verify the correct command was sent
    call_args = mock_client.post.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["cmd"] == "unset-locate"


@pytest.mark.asyncio
async def test_locate_device_dry_run(mock_settings):
    """Test device locate mode dry run."""
    result = await locate_device(
        site_id="default",
        device_mac="00:11:22:33:44:55",
        settings=mock_settings,
        enabled=True,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_enable"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_locate_device_disable_dry_run(mock_settings):
    """Test device locate mode disable dry run."""
    result = await locate_device(
        site_id="default",
        device_mac="00:11:22:33:44:55",
        settings=mock_settings,
        enabled=False,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_disable"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_locate_device_no_confirm(mock_settings):
    """Test device locate fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await locate_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            enabled=True,
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_locate_device_not_found(mock_settings):
    """Test locate of non-existent device."""
    mock_devices_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        with pytest.raises(ResourceNotFoundError):
            await locate_device(
                site_id="default",
                device_mac="aa:bb:cc:dd:ee:ff",
                settings=mock_settings,
                enabled=True,
                confirm=True,
            )


# =============================================================================
# upgrade_device Tests
# =============================================================================


@pytest.mark.asyncio
async def test_upgrade_device_latest(mock_settings):
    """Test triggering firmware upgrade to latest version."""
    mock_devices_response = {
        "data": [
            {
                "_id": "device1",
                "mac": "00:11:22:33:44:55",
                "name": "Test AP",
                "version": "6.5.28",
                "model": "UAP-AC-PRO",
            }
        ]
    }
    mock_upgrade_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.post = AsyncMock(return_value=mock_upgrade_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        result = await upgrade_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    assert result["device_mac"] == "00:11:22:33:44:55"
    assert result["message"] == "Firmware upgrade initiated"
    assert result["current_version"] == "6.5.28"

    # Verify no firmware_url in command (uses latest)
    call_args = mock_client.post.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["cmd"] == "upgrade"
    assert "url" not in json_data


@pytest.mark.asyncio
async def test_upgrade_device_specific_firmware(mock_settings):
    """Test triggering firmware upgrade with specific firmware URL."""
    mock_devices_response = {
        "data": [
            {
                "_id": "device1",
                "mac": "00:11:22:33:44:55",
                "name": "Test AP",
                "version": "6.5.28",
            }
        ]
    }
    mock_upgrade_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.post = AsyncMock(return_value=mock_upgrade_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    firmware_url = "https://fw-update.ubnt.com/firmware/UAP-AC-PRO/6.6.55.unf"

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        result = await upgrade_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            firmware_url=firmware_url,
            confirm=True,
        )

    assert result["success"] is True
    assert result["device_mac"] == "00:11:22:33:44:55"

    # Verify firmware_url was included in command
    call_args = mock_client.post.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["cmd"] == "upgrade"
    assert json_data["url"] == firmware_url


@pytest.mark.asyncio
async def test_upgrade_device_dry_run(mock_settings):
    """Test device upgrade dry run."""
    result = await upgrade_device(
        site_id="default",
        device_mac="00:11:22:33:44:55",
        settings=mock_settings,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_upgrade"] == "00:11:22:33:44:55"


@pytest.mark.asyncio
async def test_upgrade_device_no_confirm(mock_settings):
    """Test device upgrade fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await upgrade_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_upgrade_device_not_found(mock_settings):
    """Test upgrade of non-existent device."""
    mock_devices_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        with pytest.raises(ResourceNotFoundError):
            await upgrade_device(
                site_id="default",
                device_mac="aa:bb:cc:dd:ee:ff",
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_upgrade_device_invalid_mac(mock_settings):
    """Test device upgrade with invalid MAC address."""
    with pytest.raises(ValidationError) as excinfo:
        await upgrade_device(
            site_id="default",
            device_mac="invalid-mac",
            settings=mock_settings,
            confirm=True,
        )

    assert "mac" in str(excinfo.value).lower() or "invalid" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_upgrade_device_with_version_info(mock_settings):
    """Test upgrade returns current version info."""
    mock_devices_response = {
        "data": [
            {
                "_id": "device1",
                "mac": "00:11:22:33:44:55",
                "name": "Test Switch",
                "version": "6.2.14",
                "model": "USW-24-POE",
            }
        ]
    }
    mock_upgrade_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.post = AsyncMock(return_value=mock_upgrade_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        result = await upgrade_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["current_version"] == "6.2.14"


# =============================================================================
# Edge Cases and Additional Tests
# =============================================================================


@pytest.mark.asyncio
async def test_restart_device_multiple_devices(mock_settings):
    """Test restart finds correct device among multiple."""
    mock_devices_response = {
        "data": [
            {"_id": "device1", "mac": "00:11:22:33:44:55", "name": "AP 1"},
            {"_id": "device2", "mac": "aa:bb:cc:dd:ee:ff", "name": "AP 2"},
            {"_id": "device3", "mac": "11:22:33:44:55:66", "name": "Switch 1"},
        ]
    }
    mock_restart_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.post = AsyncMock(return_value=mock_restart_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        result = await restart_device(
            site_id="default",
            device_mac="aa:bb:cc:dd:ee:ff",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    assert result["device_mac"] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.asyncio
async def test_locate_device_default_enabled(mock_settings):
    """Test locate device defaults to enabled."""
    mock_devices_response = {
        "data": [{"_id": "device1", "mac": "00:11:22:33:44:55", "name": "Test AP"}]
    }
    mock_locate_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.post = AsyncMock(return_value=mock_locate_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        # Don't pass enabled param - should default to True
        result = await locate_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["locate_enabled"] is True


@pytest.mark.asyncio
async def test_restart_device_mac_normalization(mock_settings):
    """Test that MAC address is normalized during comparison."""
    # Device in API uses colons, input uses colons
    mock_devices_response = {
        "data": [{"_id": "device1", "mac": "00:11:22:33:44:55", "name": "Test AP"}]
    }
    mock_restart_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.post = AsyncMock(return_value=mock_restart_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        # Input MAC with different format (uppercase)
        result = await restart_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_devices_response_list_format(mock_settings):
    """Test handling when devices response is a list (auto-unwrapped)."""
    # Client auto-unwraps data, so response might be a list directly
    mock_devices_response = [{"_id": "device1", "mac": "00:11:22:33:44:55", "name": "Test AP"}]
    mock_restart_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_devices_response)
    mock_client.post = AsyncMock(return_value=mock_restart_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dc_module, "UniFiClient", return_value=mock_client):
        result = await restart_device(
            site_id="default",
            device_mac="00:11:22:33:44:55",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
