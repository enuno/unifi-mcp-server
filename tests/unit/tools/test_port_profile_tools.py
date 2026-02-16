"""Unit tests for port profile and device port override tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.port_profiles as port_profiles_module
from src.tools.port_profiles import (
    create_port_profile,
    delete_port_profile,
    get_device_by_mac,
    get_device_port_overrides,
    get_port_profile,
    list_port_profiles,
    set_device_port_overrides,
    update_port_profile,
)
from src.utils.exceptions import (
    DuplicateResourceError,
    ResourceNotFoundError,
    ValidationError,
)


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


def _make_client(get_return=None, post_return=None, put_return=None, delete_return=None):
    """Helper to create a mock UniFi client."""
    client = MagicMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value=get_return or {"data": []})
    client.post = AsyncMock(return_value=post_return or {"data": []})
    client.put = AsyncMock(return_value=put_return or {"data": []})
    client.delete = AsyncMock(return_value=delete_return or {"data": []})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# =============================================================================
# list_port_profiles Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_port_profiles_success(mock_settings):
    """Test successful listing of port profiles."""
    mock_response = {
        "data": [
            {"_id": "pp1", "name": "All", "forward": "all"},
            {"_id": "pp2", "name": "IoT", "forward": "native"},
        ]
    }
    client = _make_client(get_return=mock_response)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await list_port_profiles("default", mock_settings)

    assert len(result) == 2
    assert result[0]["name"] == "All"
    assert result[1]["name"] == "IoT"
    client.get.assert_called_once_with("/ea/sites/default/rest/portconf")


@pytest.mark.asyncio
async def test_list_port_profiles_empty(mock_settings):
    """Test listing with no profiles."""
    client = _make_client(get_return={"data": []})

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await list_port_profiles("default", mock_settings)

    assert result == []


@pytest.mark.asyncio
async def test_list_port_profiles_list_response(mock_settings):
    """Test listing when API returns a list directly."""
    mock_response = [
        {"_id": "pp1", "name": "All", "forward": "all"},
    ]
    client = _make_client(get_return=mock_response)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await list_port_profiles("default", mock_settings)

    assert len(result) == 1
    assert result[0]["_id"] == "pp1"


@pytest.mark.asyncio
async def test_list_port_profiles_pagination(mock_settings):
    """Test port profiles listing with pagination."""
    mock_response = {
        "data": [{"_id": f"pp{i}", "name": f"Profile {i}"} for i in range(10)]
    }
    client = _make_client(get_return=mock_response)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await list_port_profiles("default", mock_settings, limit=3, offset=2)

    assert len(result) == 3
    assert result[0]["_id"] == "pp2"
    assert result[2]["_id"] == "pp4"


@pytest.mark.asyncio
async def test_list_port_profiles_invalid_site_id(mock_settings):
    """Test listing with invalid site ID."""
    with pytest.raises(ValidationError):
        await list_port_profiles("", mock_settings)


# =============================================================================
# get_port_profile Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_port_profile_success(mock_settings):
    """Test successful retrieval of a port profile."""
    mock_response = {
        "data": [
            {
                "_id": "pp1",
                "name": "IoT Profile",
                "forward": "native",
                "native_networkconf_id": "net1",
            }
        ]
    }
    client = _make_client(get_return=mock_response)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await get_port_profile("default", "pp1", mock_settings)

    assert result["_id"] == "pp1"
    assert result["name"] == "IoT Profile"
    assert result["forward"] == "native"
    client.get.assert_called_once_with("/ea/sites/default/rest/portconf/pp1")


@pytest.mark.asyncio
async def test_get_port_profile_not_found(mock_settings):
    """Test getting a non-existent port profile."""
    client = _make_client(get_return={"data": []})

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(ResourceNotFoundError):
            await get_port_profile("default", "nonexistent", mock_settings)


@pytest.mark.asyncio
async def test_get_port_profile_empty_id(mock_settings):
    """Test getting a profile with empty ID."""
    with pytest.raises(ValidationError, match="Profile ID cannot be empty"):
        await get_port_profile("default", "", mock_settings)


# =============================================================================
# create_port_profile Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_port_profile_success(mock_settings):
    """Test successful port profile creation."""
    created = {
        "data": [
            {"_id": "new_pp", "name": "IoT Profile", "forward": "native"}
        ]
    }
    client = _make_client(get_return={"data": []}, post_return=created)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await create_port_profile(
            site_id="default",
            name="IoT Profile",
            forward="native",
            settings=mock_settings,
            native_networkconf_id="net1",
            confirm=True,
        )

    assert result["_id"] == "new_pp"
    assert result["name"] == "IoT Profile"
    client.post.assert_called_once()
    call_args = client.post.call_args
    assert call_args[1]["json_data"]["name"] == "IoT Profile"
    assert call_args[1]["json_data"]["forward"] == "native"
    assert call_args[1]["json_data"]["native_networkconf_id"] == "net1"


@pytest.mark.asyncio
async def test_create_port_profile_with_all_options(mock_settings):
    """Test profile creation with all optional fields."""
    created = {"data": [{"_id": "new_pp", "name": "Full Profile", "forward": "customize"}]}
    client = _make_client(get_return={"data": []}, post_return=created)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await create_port_profile(
            site_id="default",
            name="Full Profile",
            forward="customize",
            settings=mock_settings,
            tagged_networkconf_ids=["net1", "net2"],
            excluded_networkconf_ids=["net3"],
            poe_mode="auto",
            speed=1000,
            full_duplex=True,
            autoneg=True,
            dot1x_ctrl="force_authorized",
            lldpmed_enabled=True,
            confirm=True,
        )

    assert result["_id"] == "new_pp"
    call_data = client.post.call_args[1]["json_data"]
    assert call_data["tagged_networkconf_ids"] == ["net1", "net2"]
    assert call_data["excluded_networkconf_ids"] == ["net3"]
    assert call_data["poe_mode"] == "auto"
    assert call_data["speed"] == 1000
    assert call_data["full_duplex"] is True
    assert call_data["autoneg"] is True
    assert call_data["dot1x_ctrl"] == "force_authorized"
    assert call_data["lldpmed_enabled"] is True


@pytest.mark.asyncio
async def test_create_port_profile_dry_run(mock_settings):
    """Test port profile creation in dry-run mode."""
    client = _make_client(get_return={"data": []})

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await create_port_profile(
            site_id="default",
            name="Test Profile",
            forward="all",
            settings=mock_settings,
            confirm=True,
            dry_run=True,
        )

    assert result["dry_run"] is True
    assert result["would_create"]["name"] == "Test Profile"
    assert result["would_create"]["forward"] == "all"
    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_port_profile_duplicate_name(mock_settings):
    """Test creation fails with duplicate name."""
    existing = {"data": [{"_id": "pp1", "name": "IoT Profile", "forward": "native"}]}
    client = _make_client(get_return=existing)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(DuplicateResourceError):
            await create_port_profile(
                site_id="default",
                name="IoT Profile",
                forward="native",
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_create_port_profile_invalid_forward(mock_settings):
    """Test creation fails with invalid forward mode."""
    with pytest.raises(ValidationError, match="Invalid forward mode"):
        await create_port_profile(
            site_id="default",
            name="Bad Profile",
            forward="invalid",
            settings=mock_settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_port_profile_no_confirm(mock_settings):
    """Test creation fails without confirmation."""
    with pytest.raises(ValidationError, match="requires confirmation"):
        await create_port_profile(
            site_id="default",
            name="Test",
            forward="all",
            settings=mock_settings,
            confirm=False,
        )


@pytest.mark.asyncio
async def test_create_port_profile_list_response(mock_settings):
    """Test creation when API returns a list directly."""
    client = _make_client(
        get_return={"data": []},
        post_return=[{"_id": "new_pp", "name": "Test", "forward": "all"}],
    )

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await create_port_profile(
            site_id="default",
            name="Test",
            forward="all",
            settings=mock_settings,
            confirm=True,
        )

    assert result["_id"] == "new_pp"


# =============================================================================
# update_port_profile Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_port_profile_success(mock_settings):
    """Test successful port profile update."""
    existing = {
        "data": [{"_id": "pp1", "name": "Old Name", "forward": "all"}]
    }
    updated = {
        "data": [{"_id": "pp1", "name": "New Name", "forward": "native"}]
    }
    client = _make_client(get_return=existing, put_return=updated)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await update_port_profile(
            site_id="default",
            profile_id="pp1",
            settings=mock_settings,
            name="New Name",
            forward="native",
            confirm=True,
        )

    assert result["name"] == "New Name"
    assert result["forward"] == "native"
    client.put.assert_called_once()
    put_data = client.put.call_args[1]["json_data"]
    assert put_data["name"] == "New Name"
    assert put_data["forward"] == "native"


@pytest.mark.asyncio
async def test_update_port_profile_dry_run(mock_settings):
    """Test port profile update in dry-run mode."""
    result = await update_port_profile(
        site_id="default",
        profile_id="pp1",
        settings=mock_settings,
        name="New Name",
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_update"]["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_port_profile_not_found(mock_settings):
    """Test update fails when profile not found."""
    client = _make_client(get_return={"data": []})

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(ResourceNotFoundError):
            await update_port_profile(
                site_id="default",
                profile_id="nonexistent",
                settings=mock_settings,
                name="New Name",
                confirm=True,
            )


@pytest.mark.asyncio
async def test_update_port_profile_invalid_forward(mock_settings):
    """Test update fails with invalid forward mode."""
    with pytest.raises(ValidationError, match="Invalid forward mode"):
        await update_port_profile(
            site_id="default",
            profile_id="pp1",
            settings=mock_settings,
            forward="bad_mode",
            confirm=True,
        )


@pytest.mark.asyncio
async def test_update_port_profile_no_confirm(mock_settings):
    """Test update fails without confirmation."""
    with pytest.raises(ValidationError, match="requires confirmation"):
        await update_port_profile(
            site_id="default",
            profile_id="pp1",
            settings=mock_settings,
            name="New Name",
            confirm=False,
        )


@pytest.mark.asyncio
async def test_update_port_profile_empty_id(mock_settings):
    """Test update fails with empty profile ID."""
    with pytest.raises(ValidationError, match="Profile ID cannot be empty"):
        await update_port_profile(
            site_id="default",
            profile_id="",
            settings=mock_settings,
            name="New Name",
            confirm=True,
        )


@pytest.mark.asyncio
async def test_update_port_profile_merges_fields(mock_settings):
    """Test that update merges only provided fields."""
    existing = {
        "data": [
            {
                "_id": "pp1",
                "name": "Original",
                "forward": "all",
                "poe_mode": "auto",
                "speed": 1000,
            }
        ]
    }
    updated = {
        "data": [
            {
                "_id": "pp1",
                "name": "Original",
                "forward": "native",
                "poe_mode": "auto",
                "speed": 1000,
            }
        ]
    }
    client = _make_client(get_return=existing, put_return=updated)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        await update_port_profile(
            site_id="default",
            profile_id="pp1",
            settings=mock_settings,
            forward="native",
            confirm=True,
        )

    put_data = client.put.call_args[1]["json_data"]
    # Original fields preserved
    assert put_data["name"] == "Original"
    assert put_data["poe_mode"] == "auto"
    assert put_data["speed"] == 1000
    # Updated field changed
    assert put_data["forward"] == "native"


# =============================================================================
# delete_port_profile Tests
# =============================================================================


@pytest.mark.asyncio
async def test_delete_port_profile_success(mock_settings):
    """Test successful port profile deletion."""
    existing = {"data": [{"_id": "pp1", "name": "To Delete"}]}
    client = _make_client(get_return=existing)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await delete_port_profile(
            site_id="default",
            profile_id="pp1",
            settings=mock_settings,
            confirm=True,
        )

    assert result["success"] is True
    assert result["deleted_profile_id"] == "pp1"
    client.delete.assert_called_once_with("/ea/sites/default/rest/portconf/pp1")


@pytest.mark.asyncio
async def test_delete_port_profile_dry_run(mock_settings):
    """Test port profile deletion in dry-run mode."""
    result = await delete_port_profile(
        site_id="default",
        profile_id="pp1",
        settings=mock_settings,
        confirm=True,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["would_delete"] == "pp1"


@pytest.mark.asyncio
async def test_delete_port_profile_not_found(mock_settings):
    """Test deletion fails when profile not found."""
    client = _make_client(get_return={"data": []})

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(ResourceNotFoundError):
            await delete_port_profile(
                site_id="default",
                profile_id="nonexistent",
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_delete_port_profile_no_confirm(mock_settings):
    """Test deletion fails without confirmation."""
    with pytest.raises(ValidationError, match="requires confirmation"):
        await delete_port_profile(
            site_id="default",
            profile_id="pp1",
            settings=mock_settings,
            confirm=False,
        )


@pytest.mark.asyncio
async def test_delete_port_profile_empty_id(mock_settings):
    """Test deletion fails with empty profile ID."""
    with pytest.raises(ValidationError, match="Profile ID cannot be empty"):
        await delete_port_profile(
            site_id="default",
            profile_id="",
            settings=mock_settings,
            confirm=True,
        )


# =============================================================================
# get_device_port_overrides Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_device_port_overrides_success(mock_settings):
    """Test successful retrieval of device port overrides."""
    mock_response = {
        "data": [
            {
                "_id": "dev1",
                "name": "Switch-24",
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "USW-24-PoE",
                "port_overrides": [
                    {"port_idx": 1, "portconf_id": "pp1", "name": "Server"},
                    {"port_idx": 5, "portconf_id": "pp2", "name": "IoT"},
                ],
                "port_table": [
                    {"port_idx": 1, "name": "Port 1", "up": True, "speed": 1000},
                    {"port_idx": 2, "name": "Port 2", "up": False, "speed": 0},
                ],
            }
        ]
    }
    client = _make_client(get_return=mock_response)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await get_device_port_overrides("default", "dev1", mock_settings)

    assert result["device_id"] == "dev1"
    assert result["name"] == "Switch-24"
    assert result["mac"] == "aa:bb:cc:dd:ee:ff"
    assert len(result["port_overrides"]) == 2
    assert result["port_overrides"][0]["port_idx"] == 1
    assert len(result["port_table"]) == 2
    client.get.assert_called_once_with("/ea/sites/default/rest/device/dev1")


@pytest.mark.asyncio
async def test_get_device_port_overrides_no_overrides(mock_settings):
    """Test device with no port overrides."""
    mock_response = {
        "data": [
            {
                "_id": "dev1",
                "name": "Switch",
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "USW-8",
                "port_table": [{"port_idx": 1, "up": True}],
            }
        ]
    }
    client = _make_client(get_return=mock_response)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await get_device_port_overrides("default", "dev1", mock_settings)

    assert result["port_overrides"] == []
    assert len(result["port_table"]) == 1


@pytest.mark.asyncio
async def test_get_device_port_overrides_not_found(mock_settings):
    """Test getting overrides for non-existent device."""
    client = _make_client(get_return={"data": []})

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(ResourceNotFoundError):
            await get_device_port_overrides("default", "nonexistent", mock_settings)


@pytest.mark.asyncio
async def test_get_device_port_overrides_empty_id(mock_settings):
    """Test getting overrides with empty device ID."""
    with pytest.raises(ValidationError, match="Device ID cannot be empty"):
        await get_device_port_overrides("default", "", mock_settings)


# =============================================================================
# set_device_port_overrides Tests
# =============================================================================


@pytest.mark.asyncio
async def test_set_device_port_overrides_merge_mode(mock_settings):
    """Test setting port overrides with merge mode (default)."""
    existing_device = {
        "data": [
            {
                "_id": "dev1",
                "name": "Switch",
                "port_overrides": [
                    {"port_idx": 1, "portconf_id": "pp1", "name": "Server"},
                    {"port_idx": 3, "portconf_id": "pp1", "name": "Printer"},
                ],
            }
        ]
    }
    updated_device = {
        "data": [
            {
                "_id": "dev1",
                "port_overrides": [
                    {"port_idx": 1, "portconf_id": "pp2", "name": "IoT Device"},
                    {"port_idx": 3, "portconf_id": "pp1", "name": "Printer"},
                    {"port_idx": 5, "portconf_id": "pp2", "name": "Camera"},
                ],
            }
        ]
    }
    client = _make_client(get_return=existing_device, put_return=updated_device)

    new_overrides = [
        {"port_idx": 1, "portconf_id": "pp2", "name": "IoT Device"},
        {"port_idx": 5, "portconf_id": "pp2", "name": "Camera"},
    ]

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await set_device_port_overrides(
            site_id="default",
            device_id="dev1",
            port_overrides=new_overrides,
            settings=mock_settings,
            merge=True,
            confirm=True,
        )

    assert result["device_id"] == "dev1"
    # Verify the PUT was called with merged overrides
    put_data = client.put.call_args[1]["json_data"]
    merged = {o["port_idx"]: o for o in put_data["port_overrides"]}
    # Port 1 updated to pp2
    assert merged[1]["portconf_id"] == "pp2"
    assert merged[1]["name"] == "IoT Device"
    # Port 3 preserved from existing
    assert merged[3]["portconf_id"] == "pp1"
    # Port 5 added new
    assert merged[5]["portconf_id"] == "pp2"


@pytest.mark.asyncio
async def test_set_device_port_overrides_replace_mode(mock_settings):
    """Test setting port overrides in replace mode."""
    existing_device = {
        "data": [
            {
                "_id": "dev1",
                "name": "Switch",
                "port_overrides": [
                    {"port_idx": 1, "portconf_id": "pp1"},
                    {"port_idx": 2, "portconf_id": "pp1"},
                ],
            }
        ]
    }
    updated_device = {
        "data": [
            {
                "_id": "dev1",
                "port_overrides": [
                    {"port_idx": 5, "portconf_id": "pp2"},
                ],
            }
        ]
    }
    client = _make_client(get_return=existing_device, put_return=updated_device)

    new_overrides = [{"port_idx": 5, "portconf_id": "pp2"}]

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        await set_device_port_overrides(
            site_id="default",
            device_id="dev1",
            port_overrides=new_overrides,
            settings=mock_settings,
            merge=False,
            confirm=True,
        )

    # In replace mode, only the new override should be sent
    put_data = client.put.call_args[1]["json_data"]
    assert len(put_data["port_overrides"]) == 1
    assert put_data["port_overrides"][0]["port_idx"] == 5


@pytest.mark.asyncio
async def test_set_device_port_overrides_dry_run(mock_settings):
    """Test setting port overrides in dry-run mode."""
    existing_device = {
        "data": [
            {
                "_id": "dev1",
                "name": "Switch",
                "port_overrides": [
                    {"port_idx": 1, "portconf_id": "pp1"},
                ],
            }
        ]
    }
    client = _make_client(get_return=existing_device)

    new_overrides = [{"port_idx": 2, "portconf_id": "pp2"}]

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await set_device_port_overrides(
            site_id="default",
            device_id="dev1",
            port_overrides=new_overrides,
            settings=mock_settings,
            merge=True,
            confirm=True,
            dry_run=True,
        )

    assert result["dry_run"] is True
    assert result["merge"] is True
    # Should show merged result (existing port 1 + new port 2)
    override_idxs = {o["port_idx"] for o in result["would_set_overrides"]}
    assert 1 in override_idxs
    assert 2 in override_idxs
    client.put.assert_not_called()


@pytest.mark.asyncio
async def test_set_device_port_overrides_not_found(mock_settings):
    """Test setting overrides on non-existent device."""
    client = _make_client(get_return={"data": []})

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(ResourceNotFoundError):
            await set_device_port_overrides(
                site_id="default",
                device_id="nonexistent",
                port_overrides=[{"port_idx": 1, "portconf_id": "pp1"}],
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_set_device_port_overrides_no_confirm(mock_settings):
    """Test setting overrides fails without confirmation."""
    with pytest.raises(ValidationError, match="requires confirmation"):
        await set_device_port_overrides(
            site_id="default",
            device_id="dev1",
            port_overrides=[{"port_idx": 1, "portconf_id": "pp1"}],
            settings=mock_settings,
            confirm=False,
        )


@pytest.mark.asyncio
async def test_set_device_port_overrides_empty_list(mock_settings):
    """Test setting overrides with empty list."""
    with pytest.raises(ValidationError, match="port_overrides cannot be empty"):
        await set_device_port_overrides(
            site_id="default",
            device_id="dev1",
            port_overrides=[],
            settings=mock_settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_set_device_port_overrides_missing_port_idx(mock_settings):
    """Test setting overrides with missing port_idx."""
    with pytest.raises(ValidationError, match="port_idx"):
        await set_device_port_overrides(
            site_id="default",
            device_id="dev1",
            port_overrides=[{"portconf_id": "pp1"}],
            settings=mock_settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_set_device_port_overrides_missing_portconf_id(mock_settings):
    """Test setting overrides with missing portconf_id."""
    with pytest.raises(ValidationError, match="portconf_id"):
        await set_device_port_overrides(
            site_id="default",
            device_id="dev1",
            port_overrides=[{"port_idx": 1}],
            settings=mock_settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_set_device_port_overrides_empty_device_id(mock_settings):
    """Test setting overrides with empty device ID."""
    with pytest.raises(ValidationError, match="Device ID cannot be empty"):
        await set_device_port_overrides(
            site_id="default",
            device_id="",
            port_overrides=[{"port_idx": 1, "portconf_id": "pp1"}],
            settings=mock_settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_set_device_port_overrides_merge_no_existing(mock_settings):
    """Test merge mode when device has no existing overrides."""
    existing_device = {
        "data": [{"_id": "dev1", "name": "Switch"}]
    }
    updated_device = {
        "data": [
            {
                "_id": "dev1",
                "port_overrides": [{"port_idx": 1, "portconf_id": "pp1"}],
            }
        ]
    }
    client = _make_client(get_return=existing_device, put_return=updated_device)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        await set_device_port_overrides(
            site_id="default",
            device_id="dev1",
            port_overrides=[{"port_idx": 1, "portconf_id": "pp1"}],
            settings=mock_settings,
            merge=True,
            confirm=True,
        )

    put_data = client.put.call_args[1]["json_data"]
    assert len(put_data["port_overrides"]) == 1
    assert put_data["port_overrides"][0]["port_idx"] == 1


# =============================================================================
# get_device_by_mac Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_device_by_mac_success(mock_settings):
    """Test successful device retrieval by MAC."""
    mock_response = {
        "data": [
            {
                "_id": "dev1",
                "name": "Switch-24",
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "USW-24-PoE",
                "ip": "192.168.1.10",
            }
        ]
    }
    client = _make_client(get_return=mock_response)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await get_device_by_mac("default", "AA:BB:CC:DD:EE:FF", mock_settings)

    assert result["_id"] == "dev1"
    assert result["name"] == "Switch-24"
    # MAC should be normalized to lowercase colon-separated
    client.get.assert_called_once_with("/ea/sites/default/stat/device/aa:bb:cc:dd:ee:ff")


@pytest.mark.asyncio
async def test_get_device_by_mac_hyphen_format(mock_settings):
    """Test MAC address with hyphen format."""
    mock_response = {"data": [{"_id": "dev1", "mac": "aa:bb:cc:dd:ee:ff"}]}
    client = _make_client(get_return=mock_response)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await get_device_by_mac("default", "AA-BB-CC-DD-EE-FF", mock_settings)

    assert result["_id"] == "dev1"
    client.get.assert_called_once_with("/ea/sites/default/stat/device/aa:bb:cc:dd:ee:ff")


@pytest.mark.asyncio
async def test_get_device_by_mac_not_found(mock_settings):
    """Test device not found by MAC."""
    client = _make_client(get_return={"data": []})

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(ResourceNotFoundError):
            await get_device_by_mac("default", "aa:bb:cc:dd:ee:ff", mock_settings)


@pytest.mark.asyncio
async def test_get_device_by_mac_invalid_mac(mock_settings):
    """Test invalid MAC address format."""
    with pytest.raises(ValidationError, match="Invalid MAC address"):
        await get_device_by_mac("default", "not-a-mac", mock_settings)


@pytest.mark.asyncio
async def test_get_device_by_mac_short_mac(mock_settings):
    """Test too-short MAC address."""
    with pytest.raises(ValidationError, match="Invalid MAC address"):
        await get_device_by_mac("default", "AA:BB:CC", mock_settings)


@pytest.mark.asyncio
async def test_get_device_by_mac_list_response(mock_settings):
    """Test when API returns a list directly."""
    mock_response = [{"_id": "dev1", "mac": "aa:bb:cc:dd:ee:ff"}]
    client = _make_client(get_return=mock_response)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await get_device_by_mac("default", "aa:bb:cc:dd:ee:ff", mock_settings)

    assert result["_id"] == "dev1"


# =============================================================================
# Input Validation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_port_profiles_invalid_site_id_special_chars(mock_settings):
    """Test listing with special characters in site ID."""
    with pytest.raises(ValidationError):
        await list_port_profiles("site with spaces", mock_settings)


@pytest.mark.asyncio
async def test_create_port_profile_invalid_site_id(mock_settings):
    """Test creation with invalid site ID."""
    with pytest.raises(ValidationError):
        await create_port_profile(
            site_id="",
            name="Test",
            forward="all",
            settings=mock_settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_get_device_port_overrides_invalid_site_id(mock_settings):
    """Test getting overrides with invalid site ID."""
    with pytest.raises(ValidationError):
        await get_device_port_overrides("", "dev1", mock_settings)


# =============================================================================
# Additional Coverage Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_port_profile_with_all_merge_fields(mock_settings):
    """Test update with all optional merge fields to cover all branches."""
    existing = {
        "data": [{"_id": "pp1", "name": "Original", "forward": "all"}]
    }
    updated = {
        "data": [
            {
                "_id": "pp1",
                "name": "Updated",
                "forward": "customize",
                "native_networkconf_id": "net1",
                "excluded_networkconf_ids": ["net2"],
                "tagged_networkconf_ids": ["net3"],
                "poe_mode": "auto",
                "speed": 1000,
                "full_duplex": True,
                "autoneg": True,
                "dot1x_ctrl": "force_authorized",
                "lldpmed_enabled": True,
            }
        ]
    }
    client = _make_client(get_return=existing, put_return=updated)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await update_port_profile(
            site_id="default",
            profile_id="pp1",
            settings=mock_settings,
            name="Updated",
            forward="customize",
            native_networkconf_id="net1",
            excluded_networkconf_ids=["net2"],
            tagged_networkconf_ids=["net3"],
            poe_mode="auto",
            speed=1000,
            full_duplex=True,
            autoneg=True,
            dot1x_ctrl="force_authorized",
            lldpmed_enabled=True,
            confirm=True,
        )

    put_data = client.put.call_args[1]["json_data"]
    assert put_data["name"] == "Updated"
    assert put_data["forward"] == "customize"
    assert put_data["native_networkconf_id"] == "net1"
    assert put_data["excluded_networkconf_ids"] == ["net2"]
    assert put_data["tagged_networkconf_ids"] == ["net3"]
    assert put_data["poe_mode"] == "auto"
    assert put_data["speed"] == 1000
    assert put_data["full_duplex"] is True
    assert put_data["autoneg"] is True
    assert put_data["dot1x_ctrl"] == "force_authorized"
    assert put_data["lldpmed_enabled"] is True


@pytest.mark.asyncio
async def test_update_port_profile_list_response(mock_settings):
    """Test update when API returns a list directly."""
    existing = {"data": [{"_id": "pp1", "name": "Original", "forward": "all"}]}
    updated = [{"_id": "pp1", "name": "Updated", "forward": "native"}]
    client = _make_client(get_return=existing, put_return=updated)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await update_port_profile(
            site_id="default",
            profile_id="pp1",
            settings=mock_settings,
            name="Updated",
            forward="native",
            confirm=True,
        )

    assert result["_id"] == "pp1"
    assert result["name"] == "Updated"


@pytest.mark.asyncio
async def test_update_port_profile_generic_error(mock_settings):
    """Test update port profile error handling path."""
    client = _make_client()
    client.authenticate = AsyncMock(side_effect=RuntimeError("Connection failed"))

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(RuntimeError, match="Connection failed"):
            await update_port_profile(
                site_id="default",
                profile_id="pp1",
                settings=mock_settings,
                name="Test",
                confirm=True,
            )


@pytest.mark.asyncio
async def test_create_port_profile_generic_error(mock_settings):
    """Test create port profile error handling path."""
    client = _make_client()
    client.authenticate = AsyncMock(side_effect=RuntimeError("Connection failed"))

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(RuntimeError, match="Connection failed"):
            await create_port_profile(
                site_id="default",
                name="Test",
                forward="all",
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_delete_port_profile_generic_error(mock_settings):
    """Test delete port profile error handling path."""
    client = _make_client()
    client.authenticate = AsyncMock(side_effect=RuntimeError("Connection failed"))

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(RuntimeError, match="Connection failed"):
            await delete_port_profile(
                site_id="default",
                profile_id="pp1",
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_set_device_port_overrides_generic_error(mock_settings):
    """Test set port overrides error handling path."""
    client = _make_client()
    client.authenticate = AsyncMock(side_effect=RuntimeError("Connection failed"))

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        with pytest.raises(RuntimeError, match="Connection failed"):
            await set_device_port_overrides(
                site_id="default",
                device_id="dev1",
                port_overrides=[{"port_idx": 1, "portconf_id": "pp1"}],
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_set_device_port_overrides_list_response(mock_settings):
    """Test set overrides when API returns a list directly."""
    existing_device = {
        "data": [{"_id": "dev1", "name": "Switch", "port_overrides": []}]
    }
    updated_device = [
        {
            "_id": "dev1",
            "port_overrides": [{"port_idx": 1, "portconf_id": "pp1"}],
        }
    ]
    client = _make_client(get_return=existing_device, put_return=updated_device)

    with patch.object(port_profiles_module, "UniFiClient", return_value=client):
        result = await set_device_port_overrides(
            site_id="default",
            device_id="dev1",
            port_overrides=[{"port_idx": 1, "portconf_id": "pp1"}],
            settings=mock_settings,
            confirm=True,
        )

    assert result["device_id"] == "dev1"
