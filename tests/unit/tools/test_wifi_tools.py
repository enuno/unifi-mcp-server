"""Unit tests for WiFi (WLAN) management tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.wifi as wifi_module
from src.tools.wifi import create_wlan, delete_wlan, get_wlan_statistics, list_wlans, update_wlan
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
# list_wlans Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_wlans_success(mock_settings):
    """Test successful listing of WLANs."""
    mock_response = {
        "data": [
            {"_id": "wlan1", "name": "Home WiFi", "enabled": True, "security": "wpapsk"},
            {
                "_id": "wlan2",
                "name": "Guest WiFi",
                "enabled": True,
                "security": "wpapsk",
                "is_guest": True,
            },
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await list_wlans("default", mock_settings)

    assert len(result) == 2
    assert result[0]["name"] == "Home WiFi"
    assert result[1]["name"] == "Guest WiFi"
    mock_client.get.assert_called_once_with("/ea/sites/default/rest/wlanconf")


@pytest.mark.asyncio
async def test_list_wlans_pagination(mock_settings):
    """Test WLANs listing with pagination."""
    mock_response = {
        "data": [{"_id": f"wlan{i}", "name": f"WiFi {i}", "enabled": True} for i in range(10)]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await list_wlans("default", mock_settings, limit=3, offset=2)

    assert len(result) == 3
    assert result[0]["_id"] == "wlan2"
    assert result[1]["_id"] == "wlan3"
    assert result[2]["_id"] == "wlan4"


@pytest.mark.asyncio
async def test_list_wlans_empty(mock_settings):
    """Test WLANs listing with empty response."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await list_wlans("default", mock_settings)

    assert result == []


# =============================================================================
# create_wlan Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_wlan_wpa2_success(mock_settings):
    """Test successful WPA2 WLAN creation."""
    mock_response = {
        "data": [
            {
                "_id": "new_wlan_1",
                "name": "Test WiFi",
                "security": "wpapsk",
                "wpa_mode": "wpa2",
                "enabled": True,
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await create_wlan(
            site_id="default",
            name="Test WiFi",
            security="wpapsk",
            settings=mock_settings,
            password="SecurePass123",
            wpa_mode="wpa2",
            confirm=True,
        )

    assert result["_id"] == "new_wlan_1"
    assert result["name"] == "Test WiFi"
    assert result["security"] == "wpapsk"
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_create_wlan_wpa3_success(mock_settings):
    """Test successful WPA3 WLAN creation."""
    mock_response = {
        "data": [
            {
                "_id": "new_wlan_2",
                "name": "WPA3 WiFi",
                "security": "wpapsk",
                "wpa_mode": "wpa3",
                "enabled": True,
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await create_wlan(
            site_id="default",
            name="WPA3 WiFi",
            security="wpapsk",
            settings=mock_settings,
            password="SecureWPA3Pass!",
            wpa_mode="wpa3",
            confirm=True,
        )

    assert result["_id"] == "new_wlan_2"
    assert result["wpa_mode"] == "wpa3"


@pytest.mark.asyncio
async def test_create_wlan_dry_run(mock_settings):
    """Test WLAN creation dry run."""
    result = await create_wlan(
        site_id="default",
        name="Dry Run WiFi",
        security="wpapsk",
        settings=mock_settings,
        password="TestPass123",
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert "would_create" in result
    assert result["would_create"]["name"] == "Dry Run WiFi"
    # Password should NOT be in dry-run output
    assert "x_passphrase" not in result["would_create"]


@pytest.mark.asyncio
async def test_create_wlan_guest_with_vlan(mock_settings):
    """Test creating a guest WLAN with VLAN isolation."""
    mock_response = {
        "data": [
            {
                "_id": "guest_wlan_1",
                "name": "Guest Network",
                "security": "wpapsk",
                "is_guest": True,
                "vlan": 100,
                "vlan_enabled": True,
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await create_wlan(
            site_id="default",
            name="Guest Network",
            security="wpapsk",
            settings=mock_settings,
            password="GuestPass123",
            is_guest=True,
            vlan_id=100,
            confirm=True,
        )

    assert result["is_guest"] is True
    assert result["vlan"] == 100
    # Verify the post call includes VLAN settings
    call_args = mock_client.post.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["is_guest"] is True
    assert json_data["vlan"] == 100
    assert json_data["vlan_enabled"] is True


@pytest.mark.asyncio
async def test_create_wlan_hidden_ssid(mock_settings):
    """Test creating a hidden SSID WLAN."""
    mock_response = {
        "data": [
            {
                "_id": "hidden_wlan_1",
                "name": "Hidden Network",
                "security": "wpapsk",
                "hide_ssid": True,
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await create_wlan(
            site_id="default",
            name="Hidden Network",
            security="wpapsk",
            settings=mock_settings,
            password="HiddenPass123",
            hide_ssid=True,
            confirm=True,
        )

    assert result["hide_ssid"] is True


@pytest.mark.asyncio
async def test_create_wlan_no_confirm(mock_settings):
    """Test WLAN creation fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await create_wlan(
            site_id="default",
            name="Test WiFi",
            security="wpapsk",
            settings=mock_settings,
            password="TestPass123",
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_create_wlan_invalid_security(mock_settings):
    """Test WLAN creation with invalid security type."""
    with pytest.raises(ValidationError) as excinfo:
        await create_wlan(
            site_id="default",
            name="Test WiFi",
            security="invalid",
            settings=mock_settings,
            confirm=True,
        )

    assert "Invalid security type" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_wlan_wpapsk_no_password(mock_settings):
    """Test WLAN creation with wpapsk security but no password."""
    with pytest.raises(ValidationError) as excinfo:
        await create_wlan(
            site_id="default",
            name="Test WiFi",
            security="wpapsk",
            settings=mock_settings,
            password=None,
            confirm=True,
        )

    assert "Password required" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_wlan_invalid_wpa_mode(mock_settings):
    """Test WLAN creation with invalid WPA mode."""
    with pytest.raises(ValidationError) as excinfo:
        await create_wlan(
            site_id="default",
            name="Test WiFi",
            security="wpapsk",
            settings=mock_settings,
            password="TestPass123",
            wpa_mode="invalid",
            confirm=True,
        )

    assert "Invalid WPA mode" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_wlan_invalid_wpa_enc(mock_settings):
    """Test WLAN creation with invalid WPA encryption."""
    with pytest.raises(ValidationError) as excinfo:
        await create_wlan(
            site_id="default",
            name="Test WiFi",
            security="wpapsk",
            settings=mock_settings,
            password="TestPass123",
            wpa_enc="invalid",
            confirm=True,
        )

    assert "Invalid WPA encryption" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_wlan_invalid_vlan_id(mock_settings):
    """Test WLAN creation with invalid VLAN ID."""
    with pytest.raises(ValidationError) as excinfo:
        await create_wlan(
            site_id="default",
            name="Test WiFi",
            security="wpapsk",
            settings=mock_settings,
            password="TestPass123",
            vlan_id=5000,  # Invalid: must be 1-4094
            confirm=True,
        )

    assert "Invalid VLAN ID" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_wlan_open_security(mock_settings):
    """Test creating an open (no password) WLAN."""
    mock_response = {
        "data": [
            {
                "_id": "open_wlan_1",
                "name": "Open Network",
                "security": "open",
                "enabled": True,
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await create_wlan(
            site_id="default",
            name="Open Network",
            security="open",
            settings=mock_settings,
            confirm=True,
        )

    assert result["security"] == "open"


# =============================================================================
# update_wlan Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_wlan_password(mock_settings):
    """Test updating WLAN password."""
    existing_wlan = {
        "_id": "wlan1",
        "name": "Home WiFi",
        "security": "wpapsk",
        "enabled": True,
    }
    mock_get_response = {"data": [existing_wlan]}
    mock_put_response = {
        "data": [
            {
                "_id": "wlan1",
                "name": "Home WiFi",
                "security": "wpapsk",
                "enabled": True,
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_client.put = AsyncMock(return_value=mock_put_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await update_wlan(
            site_id="default",
            wlan_id="wlan1",
            settings=mock_settings,
            password="NewPassword123",
            confirm=True,
        )

    assert result["_id"] == "wlan1"
    # Verify password was included in update
    call_args = mock_client.put.call_args
    json_data = call_args[1]["json_data"]
    assert json_data["x_passphrase"] == "NewPassword123"


@pytest.mark.asyncio
async def test_update_wlan_settings(mock_settings):
    """Test updating multiple WLAN settings."""
    existing_wlan = {
        "_id": "wlan1",
        "name": "Old Name",
        "security": "wpapsk",
        "enabled": True,
        "hide_ssid": False,
    }
    mock_get_response = {"data": [existing_wlan]}
    mock_put_response = {
        "data": [
            {
                "_id": "wlan1",
                "name": "New Name",
                "enabled": False,
                "hide_ssid": True,
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_client.put = AsyncMock(return_value=mock_put_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await update_wlan(
            site_id="default",
            wlan_id="wlan1",
            settings=mock_settings,
            name="New Name",
            enabled=False,
            hide_ssid=True,
            confirm=True,
        )

    assert result["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_wlan_dry_run(mock_settings):
    """Test WLAN update dry run."""
    result = await update_wlan(
        site_id="default",
        wlan_id="wlan1",
        settings=mock_settings,
        name="Updated Name",
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert "would_update" in result
    assert result["would_update"]["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_wlan_not_found(mock_settings):
    """Test updating non-existent WLAN."""
    mock_get_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        with pytest.raises(ResourceNotFoundError):
            await update_wlan(
                site_id="default",
                wlan_id="nonexistent",
                settings=mock_settings,
                name="New Name",
                confirm=True,
            )


@pytest.mark.asyncio
async def test_update_wlan_no_confirm(mock_settings):
    """Test WLAN update fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await update_wlan(
            site_id="default",
            wlan_id="wlan1",
            settings=mock_settings,
            name="New Name",
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_update_wlan_invalid_security(mock_settings):
    """Test WLAN update with invalid security type."""
    with pytest.raises(ValidationError) as excinfo:
        await update_wlan(
            site_id="default",
            wlan_id="wlan1",
            settings=mock_settings,
            security="invalid",
            confirm=True,
        )

    assert "Invalid security type" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_wlan_invalid_wpa_mode(mock_settings):
    """Test WLAN update with invalid WPA mode."""
    with pytest.raises(ValidationError) as excinfo:
        await update_wlan(
            site_id="default",
            wlan_id="wlan1",
            settings=mock_settings,
            wpa_mode="invalid",
            confirm=True,
        )

    assert "Invalid WPA mode" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_wlan_invalid_vlan_id(mock_settings):
    """Test WLAN update with invalid VLAN ID."""
    with pytest.raises(ValidationError) as excinfo:
        await update_wlan(
            site_id="default",
            wlan_id="wlan1",
            settings=mock_settings,
            vlan_id=0,  # Invalid: must be 1-4094
            confirm=True,
        )

    assert "Invalid VLAN ID" in str(excinfo.value)


# =============================================================================
# delete_wlan Tests
# =============================================================================


@pytest.mark.asyncio
async def test_delete_wlan_success(mock_settings):
    """Test successful WLAN deletion."""
    mock_get_response = {
        "data": [
            {"_id": "wlan1", "name": "Test WiFi"},
        ]
    }
    mock_delete_response = {"meta": {"rc": "ok"}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_client.delete = AsyncMock(return_value=mock_delete_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await delete_wlan(
            site_id="default",
            wlan_id="wlan1",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    assert result["deleted_wlan_id"] == "wlan1"
    mock_client.delete.assert_called_once_with("/ea/sites/default/rest/wlanconf/wlan1")


@pytest.mark.asyncio
async def test_delete_wlan_dry_run(mock_settings):
    """Test WLAN deletion dry run."""
    result = await delete_wlan(
        site_id="default",
        wlan_id="wlan1",
        settings=mock_settings,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_delete"] == "wlan1"


@pytest.mark.asyncio
async def test_delete_wlan_not_found(mock_settings):
    """Test deleting non-existent WLAN."""
    mock_get_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        with pytest.raises(ResourceNotFoundError):
            await delete_wlan(
                site_id="default",
                wlan_id="nonexistent",
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_delete_wlan_no_confirm(mock_settings):
    """Test WLAN deletion fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await delete_wlan(
            site_id="default",
            wlan_id="wlan1",
            settings=mock_settings,
            confirm=False,
        )

    assert "requires confirmation" in str(excinfo.value).lower()


# =============================================================================
# get_wlan_statistics Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_wlan_statistics_success(mock_settings):
    """Test getting WLAN statistics for a site."""
    mock_wlans_response = {
        "data": [
            {
                "_id": "wlan1",
                "name": "Home WiFi",
                "enabled": True,
                "security": "wpapsk",
                "is_guest": False,
            },
            {
                "_id": "wlan2",
                "name": "Guest WiFi",
                "enabled": True,
                "security": "wpapsk",
                "is_guest": True,
            },
        ]
    }
    mock_clients_response = {
        "data": [
            {"essid": "Home WiFi", "tx_bytes": 1000000, "rx_bytes": 500000, "is_wired": False},
            {"essid": "Home WiFi", "tx_bytes": 2000000, "rx_bytes": 1000000, "is_wired": False},
            {"essid": "Guest WiFi", "tx_bytes": 100000, "rx_bytes": 50000, "is_wired": False},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_wlans_response, mock_clients_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await get_wlan_statistics("default", mock_settings)

    assert "wlans" in result
    assert len(result["wlans"]) == 2
    home_wifi = next(w for w in result["wlans"] if w["name"] == "Home WiFi")
    assert home_wifi["client_count"] == 3
    assert home_wifi["total_tx_bytes"] == 3100000
    assert home_wifi["total_rx_bytes"] == 1550000


@pytest.mark.asyncio
async def test_get_wlan_statistics_specific_wlan(mock_settings):
    """Test getting statistics for a specific WLAN."""
    mock_wlans_response = {
        "data": [
            {
                "_id": "wlan1",
                "name": "Home WiFi",
                "enabled": True,
                "security": "wpapsk",
                "is_guest": False,
            },
            {
                "_id": "wlan2",
                "name": "Guest WiFi",
                "enabled": True,
                "security": "wpapsk",
                "is_guest": True,
            },
        ]
    }
    mock_clients_response = {
        "data": [
            {"essid": "Home WiFi", "tx_bytes": 1000000, "rx_bytes": 500000, "is_wired": False},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_wlans_response, mock_clients_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await get_wlan_statistics("default", mock_settings, wlan_id="wlan1")

    # Should return single WLAN stats, not wrapped in list
    assert result["wlan_id"] == "wlan1"
    assert result["name"] == "Home WiFi"


@pytest.mark.asyncio
async def test_get_wlan_statistics_no_clients(mock_settings):
    """Test WLAN statistics with no clients."""
    mock_wlans_response = {
        "data": [
            {
                "_id": "wlan1",
                "name": "Empty WiFi",
                "enabled": True,
                "security": "wpapsk",
                "is_guest": False,
            },
        ]
    }
    mock_clients_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_wlans_response, mock_clients_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await get_wlan_statistics("default", mock_settings)

    assert len(result["wlans"]) == 1
    assert result["wlans"][0]["client_count"] == 0
    assert result["wlans"][0]["total_bytes"] == 0


@pytest.mark.asyncio
async def test_get_wlan_statistics_wlan_not_found(mock_settings):
    """Test WLAN statistics for non-existent WLAN returns empty."""
    mock_wlans_response = {
        "data": [
            {"_id": "wlan1", "name": "Home WiFi", "enabled": True, "security": "wpapsk"},
        ]
    }
    mock_clients_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_wlans_response, mock_clients_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        result = await get_wlan_statistics("default", mock_settings, wlan_id="nonexistent")

    # Should return empty dict when specific WLAN not found
    assert result == {}
