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


# =============================================================================
# WPA3 / 6 GHz payload tests (issue #77)
# =============================================================================


@pytest.mark.asyncio
async def test_create_wlan_wpa3_sends_correct_api_payload(mock_settings):
    """wpa_mode='wpa3' must NOT be sent literally to the UniFi API.

    UniFi controllers reject wpa_mode='wpa3' with api.err.InvalidPayload.
    The correct API payload uses wpa_mode='wpa2' together with wpa3_support=True.
    """
    mock_response = {"data": [{"_id": "wlan_wpa3", "name": "WPA3 SSID"}]}
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        await create_wlan(
            site_id="default",
            name="WPA3 SSID",
            security="wpapsk",
            settings=mock_settings,
            password="SecurePass123!",
            wpa_mode="wpa3",
            confirm=True,
        )

    payload = mock_client.post.call_args.kwargs["json_data"]
    assert payload["wpa_mode"] == "wpa2", (
        "UniFi API expects wpa_mode='wpa2', not 'wpa3'. " "WPA3 is signalled via wpa3_support=True."
    )
    assert payload.get("wpa3_support") is True, "wpa_mode='wpa3' must set wpa3_support=True"


@pytest.mark.asyncio
async def test_create_wlan_6g_band_auto_infers_wpa3_pmf(mock_settings):
    """6 GHz SSIDs mandate WPA3 + PMF — these must be auto-inferred when not explicit.

    802.11ax (Wi-Fi 6E) requires WPA3 and Protected Management Frames on 6 GHz.
    A controller returns api.err.InvalidPayload if these fields are missing.
    """
    mock_response = {"data": [{"_id": "wlan_6g", "name": "6G SSID"}]}
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        await create_wlan(
            site_id="default",
            name="6G SSID",
            security="wpapsk",
            settings=mock_settings,
            password="SecurePass123!",
            wlan_bands=["6g"],
            confirm=True,
        )

    payload = mock_client.post.call_args.kwargs["json_data"]
    assert payload.get("wpa3_support") is True, "6G band requires wpa3_support=True"
    assert payload.get("wpa3_transition") is False, "6G band must disable WPA2/WPA3 transition"
    assert payload.get("pmf_mode") == "required", "6G band mandates pmf_mode='required'"


@pytest.mark.asyncio
async def test_create_wlan_6g_dry_run_includes_wpa3_fields(mock_settings):
    """dry_run for a 6G SSID must preview the inferred WPA3+PMF payload fields."""
    result = await create_wlan(
        site_id="default",
        name="6G SSID",
        security="wpapsk",
        settings=mock_settings,
        password="SecurePass123!",
        wlan_bands=["6g"],
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    would_create = result["would_create"]
    assert would_create.get("wpa3_support") is True, "dry_run should show inferred wpa3_support"
    assert would_create.get("pmf_mode") == "required", "dry_run should show inferred pmf_mode"


@pytest.mark.asyncio
async def test_create_wlan_explicit_wpa3_params_are_sent(mock_settings):
    """Explicitly provided wpa3_support/wpa3_transition/pmf_mode must be included in payload."""
    mock_response = {"data": [{"_id": "wlan_trans", "name": "Transition SSID"}]}
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        await create_wlan(
            site_id="default",
            name="Transition SSID",
            security="wpapsk",
            settings=mock_settings,
            password="SecurePass123!",
            wpa3_support=True,
            wpa3_transition=True,
            pmf_mode="optional",
            confirm=True,
        )

    payload = mock_client.post.call_args.kwargs["json_data"]
    assert payload.get("wpa3_support") is True
    assert payload.get("wpa3_transition") is True
    assert payload.get("pmf_mode") == "optional"


@pytest.mark.asyncio
async def test_create_wlan_invalid_pmf_mode_raises_validation_error(mock_settings):
    """An unrecognised pmf_mode value must be caught before hitting the API."""
    with pytest.raises(ValidationError, match="pmf_mode"):
        await create_wlan(
            site_id="default",
            name="Bad SSID",
            security="wpapsk",
            settings=mock_settings,
            password="SecurePass123!",
            pmf_mode="bogus_mode",
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_wlan_6g_explicit_params_override_defaults(mock_settings):
    """Explicit params on a 6G SSID override auto-inferred defaults (WPA3 transition mode)."""
    mock_response = {"data": [{"_id": "wlan_6g_t", "name": "6G Transition"}]}
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        await create_wlan(
            site_id="default",
            name="6G Transition",
            security="wpapsk",
            settings=mock_settings,
            password="SecurePass123!",
            wlan_bands=["6g"],
            wpa3_transition=True,  # caller explicitly wants transition mode
            pmf_mode="optional",  # caller explicitly sets optional PMF
            confirm=True,
        )

    payload = mock_client.post.call_args.kwargs["json_data"]
    assert payload.get("wpa3_support") is True  # still auto-inferred for 6G
    assert payload.get("wpa3_transition") is True  # caller override respected
    assert payload.get("pmf_mode") == "optional"  # caller override respected


@pytest.mark.asyncio
async def test_create_wlan_invalid_band_raises_validation_error(mock_settings):
    """Band strings must be lowercase '2g'/'5g'/'6g'; '6G' or 'wifi6' must be rejected."""
    with pytest.raises(ValidationError, match="band"):
        await create_wlan(
            site_id="default",
            name="Bad Band SSID",
            security="wpapsk",
            settings=mock_settings,
            password="SecurePass123!",
            wlan_bands=["6G"],  # uppercase — invalid
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_wlan_wpa3_mode_also_sets_transition_and_pmf_defaults(mock_settings):
    """wpa_mode='wpa3' must default wpa3_transition=False and pmf_mode='required'.

    A WPA3-only request should not silently produce a mixed-mode or
    unprotected (PMF-less) payload. Explicit caller values still override.
    """
    mock_response = {"data": [{"_id": "wlan_wpa3_full", "name": "WPA3 Full"}]}
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(wifi_module, "UniFiClient", return_value=mock_client):
        await create_wlan(
            site_id="default",
            name="WPA3 Full",
            security="wpapsk",
            settings=mock_settings,
            password="SecurePass123!",
            wpa_mode="wpa3",
            confirm=True,
        )

    payload = mock_client.post.call_args.kwargs["json_data"]
    assert payload["wpa_mode"] == "wpa2"
    assert payload.get("wpa3_support") is True
    assert (
        payload.get("wpa3_transition") is False
    ), "wpa_mode='wpa3' must default wpa3_transition=False (WPA3-only, not mixed)"
    assert (
        payload.get("pmf_mode") == "required"
    ), "wpa_mode='wpa3' must default pmf_mode='required' (WPA3 mandates PMF)"
