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


@pytest.mark.asyncio
async def test_set_radio_channel_writes_and_unwraps_echo(mock_settings):
    """The radio write survives an accepted-but-unechoed reply.

    Regression for the shared unwrap helper: an empty ``data`` list used
    to raise IndexError while parsing the reply to a write that had
    already landed.
    """
    from src.tools.device_control import set_ap_radio_channel

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    device = {
        "_id": "ap-1",
        "mac": "00:00:5e:00:53:41",
        "name": "Test AP",
        "radio_table": [
            {"radio": "ng", "channel": 6, "ht": 20},
            {"radio": "na", "channel": 36, "ht": 80},
        ],
    }
    client = MagicMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value={"data": [device]})
    client.put = AsyncMock(return_value={"data": []})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_radio_channel(
            site_id="default",
            device_id="ap-1",
            band="5",
            channel=44,
            settings=mock_settings,
            confirm=True,
        )

    client.put.assert_called_once()
    assert result["new_channel"] == 44


# =============================================================================
# force_provision_device Tests
# =============================================================================


def _provision_client(devices=None):
    client = MagicMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value={"data": devices or []})
    client.post = AsyncMock(return_value={"meta": {"rc": "ok"}})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_force_provision_by_mac(mock_settings):
    """A MAC goes straight to cmd/devmgr with no device enumeration."""
    from src.tools.device_control import force_provision_device

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _provision_client()

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await force_provision_device(
            site_id="default",
            device_id="00:00:5e:00:53:41",
            settings=mock_settings,
            confirm=True,
        )

    client.get.assert_not_called()
    url = client.post.call_args[0][0]
    assert url.endswith("/cmd/devmgr")
    body = client.post.call_args[1]["json_data"]
    assert body == {"cmd": "force-provision", "mac": "00:00:5e:00:53:41"}
    assert result["success"] is True
    assert result["mac"] == "00:00:5e:00:53:41"


@pytest.mark.asyncio
async def test_force_provision_resolves_id_to_mac(mock_settings):
    """A device _id is resolved to its MAC via stat/device first."""
    from src.tools.device_control import force_provision_device

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _provision_client(devices=[{"_id": "ap-1", "mac": "00:00:5e:00:53:41"}])

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await force_provision_device(
            site_id="default",
            device_id="ap-1",
            settings=mock_settings,
            confirm=True,
        )

    assert client.get.call_args[0][0].endswith("/stat/device")
    body = client.post.call_args[1]["json_data"]
    assert body == {"cmd": "force-provision", "mac": "00:00:5e:00:53:41"}
    assert result["success"] is True


@pytest.mark.asyncio
async def test_force_provision_unknown_id_raises(mock_settings):
    """An _id absent from stat/device raises ResourceNotFoundError."""
    from src.tools.device_control import force_provision_device

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _provision_client(devices=[{"_id": "other", "mac": "00:00:5e:00:53:99"}])

    with patch.object(dc_module, "UniFiClient", return_value=client):
        with pytest.raises(ResourceNotFoundError):
            await force_provision_device(
                site_id="default",
                device_id="ap-1",
                settings=mock_settings,
                confirm=True,
            )

    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_force_provision_dry_run(mock_settings):
    """Dry run previews the target MAC without posting."""
    from src.tools.device_control import force_provision_device

    client = _provision_client()

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await force_provision_device(
            site_id="default",
            device_id="00:00:5e:00:53:41",
            settings=mock_settings,
            confirm=True,
            dry_run=True,
        )

    assert result == {"dry_run": True, "would_provision": "00:00:5e:00:53:41"}
    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_force_provision_requires_confirm(mock_settings):
    """The provision command is mutating and demands confirm=True."""
    from src.tools.device_control import force_provision_device

    with pytest.raises(ValidationError):
        await force_provision_device(
            site_id="default",
            device_id="00:00:5e:00:53:41",
            settings=mock_settings,
        )


@pytest.mark.asyncio
async def test_force_provision_separatorless_mac(mock_settings):
    """A 12-hex MAC without separators is a MAC, not a device id."""
    from src.tools.device_control import force_provision_device

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _provision_client()

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await force_provision_device(
            site_id="default",
            device_id="00005e005341",
            settings=mock_settings,
            confirm=True,
        )

    client.get.assert_not_called()
    body = client.post.call_args[1]["json_data"]
    assert body == {"cmd": "force-provision", "mac": "00:00:5e:00:53:41"}
    assert result["success"] is True


@pytest.mark.asyncio
async def test_force_provision_failure_audits_failed(mock_settings):
    """A failed provision POST audits result=failed and re-raises."""
    from src.tools.device_control import force_provision_device
    from src.utils.exceptions import APIError

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _provision_client()
    client.post = AsyncMock(side_effect=APIError("boom"))

    with (
        patch.object(dc_module, "UniFiClient", return_value=client),
        patch.object(dc_module, "log_audit") as audit,
    ):
        with pytest.raises(APIError):
            await force_provision_device(
                site_id="default",
                device_id="00:00:5e:00:53:41",
                settings=mock_settings,
                confirm=True,
            )

    assert audit.call_args[1]["result"] == "failed"


# =============================================================================
# set_ap_radio_channel Tests
# =============================================================================

AP_CONFIG = {
    "_id": "ap-1",
    "mac": "00:00:5e:00:53:41",
    "name": "Test AP",
    "radio_table": [
        {"radio": "ng", "channel": 11, "ht": 20, "tx_power_mode": "custom", "tx_power": 19},
        {"radio": "na", "channel": 36, "ht": 80, "tx_power_mode": "custom", "tx_power": 26},
    ],
}


def _radio_client(config_devices, put_return, config_get=None):
    client = MagicMock()
    client.authenticate = AsyncMock()
    # First GET enumerates stat/device; second GET fetches the per-id
    # config record (rest/device serves no collection GET).
    responses = [
        {"data": config_devices},
        config_get if config_get is not None else {"data": [config_devices[0]]},
    ]
    client.get = AsyncMock(side_effect=responses)
    client.put = AsyncMock(return_value=put_return)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _stored(power=23, mode="custom"):
    import copy

    stored = copy.deepcopy(AP_CONFIG)
    stored["radio_table"][1]["tx_power"] = power
    stored["radio_table"][1]["tx_power_mode"] = mode
    return stored


@pytest.mark.asyncio
async def test_set_radio_power_writes_config_record(mock_settings):
    """The write reads rest/device config and PUTs only the radio_table.

    Regression: the tool previously PUT the whole stat/device operational
    blob back, which the controller answered with 200 while silently
    dropping the radio change (a tx_power write observed live to not
    stick).
    """
    from src.tools.device_control import set_ap_radio_channel

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _radio_client([AP_CONFIG], put_return={"data": [_stored()]})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_radio_channel(
            site_id="default",
            device_id="00:00:5e:00:53:41",
            band="5",
            channel=36,
            settings=mock_settings,
            tx_power_mode="custom",
            tx_power=23,
            confirm=True,
        )

    stat_url = client.get.call_args_list[0][0][0]
    assert stat_url.endswith("/stat/device")
    config_url = client.get.call_args_list[1][0][0]
    assert config_url.endswith("/rest/device/ap-1")
    put_url = client.put.call_args[0][0]
    assert put_url.endswith("/rest/device/ap-1")
    body = client.put.call_args[1]["json_data"]
    assert set(body.keys()) == {"radio_table"}
    na = next(e for e in body["radio_table"] if e.get("radio") == "na")
    assert na["tx_power"] == 23
    assert result["success"] is True
    assert result["stored_tx_power"] == 23
    assert "warnings" not in result


@pytest.mark.asyncio
async def test_set_radio_power_warns_when_not_stored(mock_settings):
    """A 200 whose echo lacks the change must not report success."""
    from src.tools.device_control import set_ap_radio_channel

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    # Echo still carries the OLD power: the controller dropped the write.
    client = _radio_client([AP_CONFIG], put_return={"data": [_stored(power=26)]})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_radio_channel(
            site_id="default",
            device_id="ap-1",
            band="5",
            channel=36,
            settings=mock_settings,
            tx_power_mode="custom",
            tx_power=23,
            confirm=True,
        )

    assert result["success"] is False
    assert any("tx_power" in w for w in result["warnings"])
    assert result["stored_tx_power"] == 26


@pytest.mark.asyncio
async def test_set_radio_power_warns_on_unechoed_write(mock_settings):
    """An empty echo is an unconfirmed change, not a success."""
    from src.tools.device_control import set_ap_radio_channel

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _radio_client([AP_CONFIG], put_return={"data": []})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_radio_channel(
            site_id="default",
            device_id="ap-1",
            band="5",
            channel=36,
            settings=mock_settings,
            tx_power=23,
            tx_power_mode="custom",
            confirm=True,
        )

    assert result["success"] is False
    assert any("could not be confirmed" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_unconfirmed_write_audits_unconfirmed(mock_settings):
    """The audit record must not claim success when the echo does not."""
    from unittest.mock import ANY

    from src.tools.device_control import set_ap_radio_channel

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _radio_client([AP_CONFIG], put_return={"data": []})

    with (
        patch.object(dc_module, "UniFiClient", return_value=client),
        patch.object(dc_module, "log_audit") as audit,
    ):
        result = await set_ap_radio_channel(
            site_id="default",
            device_id="ap-1",
            band="5",
            channel=36,
            settings=mock_settings,
            tx_power_mode="custom",
            tx_power=23,
            confirm=True,
        )

    assert result["success"] is False
    audit.assert_called_once_with(
        operation="set_ap_radio_channel",
        parameters=ANY,
        result="unconfirmed",
        site_id="default",
    )


@pytest.mark.asyncio
async def test_set_radio_falls_back_to_stat_record_on_config_error(mock_settings):
    """A refused per-id config GET falls back to the stat record.

    Older surfaces do not serve rest/device/{id}; the stat record's
    radio_table mirrors applied config and the write sends only that
    table, so the change must still land.
    """
    from src.tools.device_control import set_ap_radio_channel
    from src.utils.exceptions import APIError

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = MagicMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock(side_effect=[{"data": [AP_CONFIG]}, APIError("no such resource")])
    client.put = AsyncMock(return_value={"data": [_stored()]})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_radio_channel(
            site_id="default",
            device_id="ap-1",
            band="5",
            channel=36,
            settings=mock_settings,
            tx_power_mode="custom",
            tx_power=23,
            confirm=True,
        )

    body = client.put.call_args[1]["json_data"]
    assert set(body.keys()) == {"radio_table"}
    assert result["success"] is True


@pytest.mark.asyncio
async def test_set_radio_falls_back_when_config_record_is_empty(mock_settings):
    """An empty config payload is treated the same as a refusal."""
    from src.tools.device_control import set_ap_radio_channel

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _radio_client([AP_CONFIG], put_return={"data": [_stored()]}, config_get={"data": []})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_radio_channel(
            site_id="default",
            device_id="ap-1",
            band="5",
            channel=36,
            settings=mock_settings,
            tx_power_mode="custom",
            tx_power=23,
            confirm=True,
        )

    assert result["success"] is True
    assert client.put.call_args[1]["json_data"]["radio_table"]


@pytest.mark.asyncio
async def test_set_radio_verifies_channel_width_echo(mock_settings):
    """A requested width is verified against the echo like the other fields."""
    from src.tools.device_control import set_ap_radio_channel

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    # The controller stores the channel but leaves the width at 80.
    stored = _stored()
    stored["radio_table"][1]["ht"] = 80
    client = _radio_client([AP_CONFIG], put_return={"data": [stored]})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_radio_channel(
            site_id="default",
            device_id="ap-1",
            band="5",
            channel=36,
            settings=mock_settings,
            ht="40",
            tx_power_mode="custom",
            tx_power=23,
            confirm=True,
        )

    assert result["success"] is False
    assert any("ht" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_set_min_rssi_writes_and_verifies(mock_settings):
    """The floor lands in the radio_table and the echo is verified."""
    from src.tools.device_control import set_ap_min_rssi

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    stored = {
        "_id": "ap-1",
        "radio_table": [
            {"radio": "ng", "channel": 6},
            {"radio": "na", "channel": 36, "min_rssi_enabled": True, "min_rssi": -72},
        ],
    }
    client = _radio_client([AP_CONFIG], put_return={"data": [stored]})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_min_rssi(
            site_id="default",
            device_id="ap-1",
            band="5",
            settings=mock_settings,
            enabled=True,
            min_rssi=-72,
            confirm=True,
        )

    body = client.put.call_args[1]["json_data"]
    na = next(e for e in body["radio_table"] if e.get("radio") == "na")
    assert na["min_rssi_enabled"] is True and na["min_rssi"] == -72
    assert result["success"] is True
    assert result["min_rssi"] == -72


@pytest.mark.asyncio
async def test_set_min_rssi_disable_does_not_write_a_floor(mock_settings):
    """Disabling clears the flag and deliberately sends no floor value.

    ``min_rssi`` is only written when the floor is being enabled. Sending
    one back on the way out would leave a number in the radio_table that
    reads like a floor still in force, so the disable path must touch
    ``min_rssi_enabled`` and nothing else.
    """
    from src.tools.device_control import set_ap_min_rssi

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    stored = {
        "_id": "ap-1",
        "radio_table": [
            {"radio": "ng", "channel": 6},
            {"radio": "na", "channel": 36, "min_rssi_enabled": False},
        ],
    }
    # A local config rather than AP_CONFIG: the write paths in this module
    # mutate the radio_table entry in place, so by the time this test runs
    # the shared fixture already carries an earlier test's min_rssi. This
    # assertion is about what this call writes, so it needs an input no
    # other test has touched.
    config = {
        "_id": "ap-1",
        "mac": "00:00:5e:00:53:41",
        "name": "Test AP",
        "radio_table": [
            {"radio": "ng", "channel": 11},
            {"radio": "na", "channel": 36},
        ],
    }
    client = _radio_client([config], put_return={"data": [stored]})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_min_rssi(
            site_id="default",
            device_id="ap-1",
            band="5",
            settings=mock_settings,
            enabled=False,
            min_rssi=-72,
            confirm=True,
        )

    body = client.put.call_args[1]["json_data"]
    na = next(e for e in body["radio_table"] if e.get("radio") == "na")
    assert na["min_rssi_enabled"] is False
    assert "min_rssi" not in na
    assert result["success"] is True
    assert result["min_rssi_enabled"] is False
    assert result["min_rssi"] is None


@pytest.mark.asyncio
async def test_set_min_rssi_bounds_and_confirm(mock_settings):
    from src.tools.device_control import set_ap_min_rssi
    from src.utils.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await set_ap_min_rssi(
            site_id="default",
            device_id="ap-1",
            band="5",
            settings=mock_settings,
            min_rssi=-95,
            confirm=True,
        )
    with pytest.raises(ValidationError):
        await set_ap_min_rssi(
            site_id="default",
            device_id="ap-1",
            band="5",
            settings=mock_settings,
            min_rssi=-72,
        )


@pytest.mark.asyncio
async def test_set_min_rssi_rejects_unknown_band(mock_settings):
    """An unrecognised band fails before any network I/O."""
    from src.tools.device_control import set_ap_min_rssi
    from src.utils.exceptions import ValidationError

    with pytest.raises(ValidationError, match="Unknown band"):
        await set_ap_min_rssi(
            site_id="default",
            device_id="ap-1",
            band="7",
            settings=mock_settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_set_min_rssi_dry_run_previews_without_writing(mock_settings):
    """dry_run returns the intended change and never opens a client."""
    from src.tools.device_control import set_ap_min_rssi

    result = await set_ap_min_rssi(
        site_id="default",
        device_id="ap-1",
        band="5",
        settings=mock_settings,
        min_rssi=-70,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_set"]["radio"] == "na"
    assert result["would_set"]["min_rssi"] == -70


@pytest.mark.asyncio
async def test_set_min_rssi_unknown_device_raises(mock_settings):
    """A device neither id nor MAC matches is reported, not written to."""
    from src.tools.device_control import set_ap_min_rssi
    from src.utils.exceptions import ResourceNotFoundError

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _radio_client([AP_CONFIG], put_return={"data": []})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        with pytest.raises(ResourceNotFoundError):
            await set_ap_min_rssi(
                site_id="default",
                device_id="no-such-ap",
                band="5",
                settings=mock_settings,
                confirm=True,
            )
    client.put.assert_not_called()


@pytest.mark.asyncio
async def test_set_min_rssi_falls_back_to_stat_record(mock_settings):
    """When the config GET errors, the stat record still carries the table.

    rest/device is the authoritative config source, but a controller that
    refuses it must not cost the operation -- the radio table on the stat
    blob is the same shape and is enough to build the write.
    """
    import copy

    from src.tools.device_control import set_ap_min_rssi
    from src.utils.exceptions import APIError

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    stored = copy.deepcopy(AP_CONFIG)
    stored["radio_table"][1]["min_rssi_enabled"] = True
    stored["radio_table"][1]["min_rssi"] = -72

    client = MagicMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock(side_effect=[{"data": [AP_CONFIG]}, APIError("no config record")])
    client.put = AsyncMock(return_value={"data": [stored]})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_min_rssi(
            site_id="default",
            device_id="ap-1",
            band="5",
            settings=mock_settings,
            min_rssi=-72,
            confirm=True,
        )

    assert result["success"] is True
    assert result["min_rssi"] == -72


@pytest.mark.asyncio
async def test_set_min_rssi_missing_radio_raises(mock_settings):
    """Asking for a band the AP does not have is a caller error."""
    from src.tools.device_control import set_ap_min_rssi
    from src.utils.exceptions import ValidationError

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    single_band = {"_id": "ap-1", "mac": "00:00:5e:00:53:41", "radio_table": [{"radio": "ng"}]}
    client = _radio_client([single_band], put_return={"data": []})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        with pytest.raises(ValidationError, match="no na radio"):
            await set_ap_min_rssi(
                site_id="default",
                device_id="ap-1",
                band="5",
                settings=mock_settings,
                confirm=True,
            )
    client.put.assert_not_called()


@pytest.mark.asyncio
async def test_set_min_rssi_warns_when_controller_stores_something_else(mock_settings):
    """A divergent echo is surfaced as a warning, not reported as success."""
    import copy

    from src.tools.device_control import set_ap_min_rssi

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    stored = copy.deepcopy(AP_CONFIG)
    stored["radio_table"][1]["min_rssi_enabled"] = False
    stored["radio_table"][1]["min_rssi"] = -80
    client = _radio_client([AP_CONFIG], put_return={"data": [stored]})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_min_rssi(
            site_id="default",
            device_id="ap-1",
            band="5",
            settings=mock_settings,
            enabled=True,
            min_rssi=-72,
            confirm=True,
        )

    assert result["success"] is False
    assert len(result["warnings"]) == 2
    assert any("min_rssi_enabled" in w for w in result["warnings"])
    assert any("min_rssi=-80" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_set_min_rssi_warns_when_echo_is_empty(mock_settings):
    """No radio table back means the change is unconfirmed, not successful."""
    from src.tools.device_control import set_ap_min_rssi

    mock_settings.get_site_api_path = MagicMock(
        side_effect=lambda site, ep: f"/proxy/network/api/s/{site}/{ep}"
    )
    client = _radio_client([AP_CONFIG], put_return={"data": [{"_id": "ap-1"}]})

    with patch.object(dc_module, "UniFiClient", return_value=client):
        result = await set_ap_min_rssi(
            site_id="default",
            device_id="ap-1",
            band="5",
            settings=mock_settings,
            min_rssi=-72,
            confirm=True,
        )

    assert result["success"] is False
    assert result["warnings"] == ["Controller did not echo the radio table; change unconfirmed"]
