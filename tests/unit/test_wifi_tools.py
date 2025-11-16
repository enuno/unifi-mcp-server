"""Unit tests for WiFi (WLAN) management tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.tools.wifi import create_wlan, delete_wlan, get_wlan_statistics, list_wlans, update_wlan
from src.utils.exceptions import ResourceNotFoundError, ValidationError

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_wlan():
    """Sample WLAN configuration for testing."""
    return {
        "_id": "wlan123",
        "name": "TestSSID",
        "enabled": True,
        "security": "wpapsk",
        "wpa_enc": "ccmp",
        "wpa_mode": "wpa2",
        "passphrase": "SecurePassword123",
        "wlan_band": "both",
        "channel": 0,
        "ht": "20",
        "vht": "80",
        "minrate_ng_enabled": False,
        "minrate_na_enabled": False,
        "usergroup_id": "default",
        "is_guest": False,
        "hide_ssid": False,
    }


@pytest.fixture
def sample_wlan_list():
    """Sample list of WLANs for testing."""
    return [
        {
            "_id": "wlan123",
            "name": "MainNetwork",
            "enabled": True,
            "security": "wpapsk",
        },
        {
            "_id": "wlan456",
            "name": "GuestNetwork",
            "enabled": True,
            "security": "open",
            "is_guest": True,
        },
        {"_id": "wlan789", "name": "Staff5GHz", "enabled": True, "wlan_band": "na"},
    ]


@pytest.fixture
def sample_wlan_stats():
    """Sample WLAN statistics for testing."""
    return {
        "_id": "wlan123",
        "name": "TestSSID",
        "num_sta": 15,
        "rx_bytes": 1024000000,
        "tx_bytes": 2048000000,
        "rx_packets": 1000000,
        "tx_packets": 2000000,
        "rx_errors": 10,
        "tx_errors": 5,
    }


# ============================================================================
# Test: list_wlans - WLAN Listing
# ============================================================================


@pytest.mark.asyncio
async def test_list_wlans_success(settings, sample_wlan_list):
    """Test listing all WLANs successfully."""
    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.get.return_value = {"data": sample_wlan_list}
        mock_client.return_value = mock_instance

        result = await list_wlans(site_id="default", settings=settings)

        assert len(result) == 3
        assert result[0]["name"] == "MainNetwork"
        assert result[1]["is_guest"] is True
        mock_instance.get.assert_called_once_with("/ea/sites/default/rest/wlanconf")


@pytest.mark.asyncio
async def test_list_wlans_with_pagination(settings, sample_wlan_list):
    """Test listing WLANs with limit and offset."""
    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.get.return_value = {"data": sample_wlan_list}
        mock_client.return_value = mock_instance

        result = await list_wlans(site_id="default", settings=settings, limit=2, offset=1)

        assert len(result) == 2
        assert result[0]["name"] == "GuestNetwork"
        assert result[1]["name"] == "Staff5GHz"


@pytest.mark.asyncio
async def test_list_wlans_empty(settings):
    """Test listing WLANs when none exist."""
    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.get.return_value = {"data": []}
        mock_client.return_value = mock_instance

        result = await list_wlans(site_id="default", settings=settings)

        assert result == []
        assert len(result) == 0


# ============================================================================
# Test: create_wlan - WLAN Creation
# ============================================================================


@pytest.mark.asyncio
async def test_create_wlan_wpa2_personal(settings, sample_wlan):
    """Test creating a WPA2-Personal WiFi network."""
    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.post.return_value = {"data": [sample_wlan]}
        mock_client.return_value = mock_instance

        result = await create_wlan(
            site_id="default",
            name="TestSSID",
            password="SecurePassword123",
            security="wpapsk",
            settings=settings,
            confirm=True,
        )

        assert result["name"] == "TestSSID"
        assert result["security"] == "wpapsk"
        mock_instance.post.assert_called_once()
        call_args = mock_instance.post.call_args
        assert call_args[0][0] == "/ea/sites/default/rest/wlanconf"
        assert "name" in call_args[1]["json_data"]


@pytest.mark.asyncio
async def test_create_wlan_open_network(settings):
    """Test creating an open (no password) WiFi network."""
    open_wlan = {
        "_id": "wlan_open",
        "name": "OpenWiFi",
        "enabled": True,
        "security": "open",
    }

    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.post.return_value = {"data": [open_wlan]}
        mock_client.return_value = mock_instance

        result = await create_wlan(
            site_id="default",
            name="OpenWiFi",
            security="open",
            settings=settings,
            confirm=True,
        )

        assert result["name"] == "OpenWiFi"
        assert result["security"] == "open"


@pytest.mark.asyncio
async def test_create_wlan_guest_network(settings):
    """Test creating a guest WiFi network."""
    guest_wlan = {
        "_id": "wlan_guest",
        "name": "GuestWiFi",
        "is_guest": True,
        "security": "wpapsk",
    }

    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.post.return_value = {"data": [guest_wlan]}
        mock_client.return_value = mock_instance

        result = await create_wlan(
            site_id="default",
            name="GuestWiFi",
            security="wpapsk",
            password="GuestPass123",
            is_guest=True,
            settings=settings,
            confirm=True,
        )

        assert result["is_guest"] is True
        assert result["name"] == "GuestWiFi"


@pytest.mark.asyncio
async def test_create_wlan_with_vlan(settings):
    """Test creating a WLAN with VLAN isolation."""
    vlan_wlan = {
        "_id": "wlan_vlan",
        "name": "StaffVLAN",
        "vlan": 100,
        "vlan_enabled": True,
        "security": "wpapsk",
    }

    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.post.return_value = {"data": [vlan_wlan]}
        mock_client.return_value = mock_instance

        result = await create_wlan(
            site_id="default",
            name="StaffVLAN",
            security="wpapsk",
            password="StaffPass123",
            vlan_id=100,
            settings=settings,
            confirm=True,
        )

        assert result["vlan"] == 100
        assert result["name"] == "StaffVLAN"


@pytest.mark.asyncio
async def test_create_wlan_without_confirmation(settings):
    """Test that creating WLAN requires confirmation."""
    with pytest.raises(ValidationError):
        await create_wlan(
            site_id="default",
            name="TestSSID",
            security="wpapsk",
            password="SecurePassword123",
            settings=settings,
            confirm=False,
        )


@pytest.mark.asyncio
async def test_create_wlan_hidden_ssid(settings):
    """Test creating a hidden SSID network."""
    hidden_wlan = {
        "_id": "wlan_hidden",
        "name": "HiddenNetwork",
        "hide_ssid": True,
        "security": "wpapsk",
    }

    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.post.return_value = {"data": [hidden_wlan]}
        mock_client.return_value = mock_instance

        result = await create_wlan(
            site_id="default",
            name="HiddenNetwork",
            security="wpapsk",
            password="HiddenPass123",
            hide_ssid=True,
            settings=settings,
            confirm=True,
        )

        assert result["hide_ssid"] is True


# ============================================================================
# Test: update_wlan - WLAN Updates
# ============================================================================


@pytest.mark.asyncio
async def test_update_wlan_name(settings, sample_wlan):
    """Test updating WLAN name."""
    updated_wlan = {**sample_wlan, "name": "UpdatedSSID"}

    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.get.return_value = {"data": [sample_wlan]}
        mock_instance.put.return_value = {"data": [updated_wlan]}
        mock_client.return_value = mock_instance

        result = await update_wlan(
            site_id="default",
            wlan_id="wlan123",
            name="UpdatedSSID",
            settings=settings,
            confirm=True,
        )

        assert result["name"] == "UpdatedSSID"
        mock_instance.put.assert_called_once()


@pytest.mark.asyncio
async def test_update_wlan_password(settings, sample_wlan):
    """Test updating WLAN password."""
    updated_wlan = {**sample_wlan, "x_passphrase": "NewSecurePass456"}

    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.get.return_value = {"data": [sample_wlan]}
        mock_instance.put.return_value = {"data": [updated_wlan]}
        mock_client.return_value = mock_instance

        result = await update_wlan(
            site_id="default",
            wlan_id="wlan123",
            password="NewSecurePass456",
            settings=settings,
            confirm=True,
        )

        assert result["x_passphrase"] == "NewSecurePass456"


@pytest.mark.asyncio
async def test_update_wlan_enable_disable(settings, sample_wlan):
    """Test enabling/disabling a WLAN."""
    disabled_wlan = {**sample_wlan, "enabled": False}

    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.get.return_value = {"data": [sample_wlan]}
        mock_instance.put.return_value = {"data": [disabled_wlan]}
        mock_client.return_value = mock_instance

        result = await update_wlan(
            site_id="default", wlan_id="wlan123", enabled=False, settings=settings, confirm=True
        )

        assert result["enabled"] is False


@pytest.mark.asyncio
async def test_update_wlan_without_confirmation(settings):
    """Test that updating WLAN requires confirmation."""
    with pytest.raises(ValidationError):
        await update_wlan(
            site_id="default",
            wlan_id="wlan123",
            name="UpdatedSSID",
            settings=settings,
            confirm=False,
        )


# ============================================================================
# Test: delete_wlan - WLAN Deletion
# ============================================================================


@pytest.mark.asyncio
async def test_delete_wlan_success(settings, sample_wlan):
    """Test deleting a WLAN successfully."""
    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.get.return_value = {"data": [sample_wlan]}
        mock_instance.delete.return_value = {"success": True}
        mock_client.return_value = mock_instance

        result = await delete_wlan(
            site_id="default", wlan_id="wlan123", settings=settings, confirm=True
        )

        assert result["success"] is True
        assert result["deleted_wlan_id"] == "wlan123"
        mock_instance.delete.assert_called_once_with("/ea/sites/default/rest/wlanconf/wlan123")


@pytest.mark.asyncio
async def test_delete_wlan_without_confirmation(settings):
    """Test that deleting WLAN requires confirmation."""
    with pytest.raises(ValidationError):
        await delete_wlan(site_id="default", wlan_id="wlan123", settings=settings, confirm=False)


@pytest.mark.asyncio
async def test_delete_wlan_not_found(settings):
    """Test deleting a non-existent WLAN."""
    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.get.return_value = {"data": []}  # Empty list - WLAN doesn't exist
        mock_client.return_value = mock_instance

        with pytest.raises(ResourceNotFoundError) as exc_info:
            await delete_wlan(site_id="default", wlan_id="wlan999", settings=settings, confirm=True)

        assert "wlan999" in str(exc_info.value)


# ============================================================================
# Test: get_wlan_statistics - WLAN Stats
# ============================================================================


@pytest.mark.asyncio
async def test_get_wlan_statistics_success(settings, sample_wlan):
    """Test retrieving WLAN statistics successfully."""
    sample_clients = [
        {"essid": "TestSSID", "tx_bytes": 1000000, "rx_bytes": 2000000},
        {"essid": "TestSSID", "tx_bytes": 500000, "rx_bytes": 1000000},
    ]

    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        # get() is called twice - once for WLANs, once for clients
        mock_instance.get.side_effect = [
            {"data": [sample_wlan]},  # WLANs
            {"data": sample_clients},  # Clients
        ]
        mock_client.return_value = mock_instance

        result = await get_wlan_statistics(site_id="default", wlan_id="wlan123", settings=settings)

        assert result["name"] == "TestSSID"
        assert result["wlan_id"] == "wlan123"
        assert result["client_count"] == 2
        assert result["total_tx_bytes"] == 1500000
        assert result["total_rx_bytes"] == 3000000
        assert result["total_bytes"] == 4500000


@pytest.mark.asyncio
async def test_get_wlan_statistics_no_data(settings):
    """Test retrieving statistics when WLAN has no data."""
    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        # get() is called twice - return empty for WLANs
        mock_instance.get.side_effect = [
            {"data": []},  # No WLANs found
            {"data": []},  # No clients
        ]
        mock_client.return_value = mock_instance

        result = await get_wlan_statistics(site_id="default", wlan_id="wlan999", settings=settings)
        assert result == {}  # Returns empty dict when WLAN not found


# ============================================================================
# Test: Edge Cases and Error Scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_create_wlan_invalid_site_id(settings):
    """Test creating WLAN with invalid site ID."""
    with pytest.raises(ValidationError):
        await create_wlan(
            site_id="",  # Invalid empty site ID
            name="TestSSID",
            security="wpapsk",
            password="SecurePassword123",
            settings=settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_list_wlans_invalid_pagination(settings):
    """Test listing WLANs with invalid pagination parameters."""
    with pytest.raises(ValidationError):
        await list_wlans(site_id="default", settings=settings, limit=-1, offset=-1)


@pytest.mark.asyncio
async def test_create_wlan_wpa_without_password(settings):
    """Test creating WPA network without password should fail."""
    with pytest.raises(ValidationError):
        await create_wlan(
            site_id="default",
            name="TestSSID",
            security="wpapsk",
            # Missing password parameter
            settings=settings,
            confirm=True,
        )


# ============================================================================
# Test: Advanced WiFi Features (Add as functionality expands)
# ============================================================================


@pytest.mark.asyncio
async def test_create_wlan_with_vlan_advanced(settings):
    """Test creating WLAN with VLAN assignment (advanced test)."""
    vlan_wlan = {
        "_id": "wlan_vlan",
        "name": "VLANNetwork",
        "vlan": 10,
        "vlan_enabled": True,
        "security": "wpapsk",
    }

    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.post.return_value = {"data": [vlan_wlan]}
        mock_client.return_value = mock_instance

        result = await create_wlan(
            site_id="default",
            name="VLANNetwork",
            security="wpapsk",
            password="VLANPass123",
            vlan_id=10,
            settings=settings,
            confirm=True,
        )

        assert result.get("vlan") == 10
        assert result.get("vlan_enabled") is True


# ============================================================================
# Performance and Stress Tests (Optional)
# ============================================================================


@pytest.mark.asyncio
async def test_list_wlans_large_dataset(settings):
    """Test listing WLANs with large dataset."""
    large_wlan_list = [
        {"_id": f"wlan{i}", "name": f"Network{i}", "enabled": True} for i in range(100)
    ]

    with patch("src.tools.wifi.UniFiClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.is_authenticated = True
        mock_instance.get.return_value = {"data": large_wlan_list}
        mock_client.return_value = mock_instance

        result = await list_wlans(site_id="default", settings=settings, limit=50, offset=25)

        assert len(result) == 50
        assert result[0]["name"] == "Network25"
        assert result[-1]["name"] == "Network74"
