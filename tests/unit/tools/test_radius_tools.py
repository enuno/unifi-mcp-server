"""Tests for RADIUS and guest portal tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.radius import (
    configure_guest_portal,
    create_hotspot_package,
    create_radius_account,
    create_radius_profile,
    delete_hotspot_package,
    delete_radius_account,
    delete_radius_profile,
    get_guest_portal_config,
    get_hotspot_package,
    get_radius_account,
    get_radius_profile,
    list_hotspot_packages,
    list_radius_accounts,
    list_radius_profiles,
    update_hotspot_package,
    update_radius_account,
    update_radius_profile,
)
from src.utils.exceptions import ValidationError


def test_radius_profile_without_auth_server():
    """Local API may return auth_servers (plural) instead of auth_server."""
    from src.models.radius import RADIUSProfile

    data = {
        "_id": "profile-1",
        "name": "Default",
        "auth_servers": [{"port": 1812, "x_secret": "test-placeholder"}],
        "use_usg_auth_server": True,
    }
    profile = RADIUSProfile.model_validate(data)
    assert profile.name == "Default"
    assert profile.auth_server is None


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.audit_log_enabled = False
    return settings


# =============================================================================
# RADIUS Profile Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_radius_profiles_success(mock_settings):
    """Test successful RADIUS profile listing."""
    mock_response = {
        "data": [
            {
                "_id": "profile-1",
                "name": "Corporate RADIUS",
                "auth_server": "radius.example.com",
                "auth_port": 1812,
                "acct_port": 1813,
                "enabled": True,
                "vlan_enabled": False,
            },
            {
                "_id": "profile-2",
                "name": "Guest RADIUS",
                "auth_server": "radius2.example.com",
                "auth_port": 1812,
                "enabled": True,
                "vlan_enabled": True,
            },
        ]
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await list_radius_profiles("default", mock_settings)

        assert len(result) == 2
        assert result[0]["id"] == "profile-1"
        assert result[0]["name"] == "Corporate RADIUS"
        assert result[1]["vlan_enabled"] is True
        mock_client.get.assert_called_once_with("/ea/sites/default/rest/radiusprofile")


@pytest.mark.asyncio
async def test_get_radius_profile_success(mock_settings):
    """Test getting specific RADIUS profile."""
    mock_response = {
        "data": {
            "_id": "profile-1",
            "name": "Corporate RADIUS",
            "auth_server": "radius.example.com",
            "auth_port": 1812,
            "auth_secret": "secret123",
            "acct_port": 1813,
            "enabled": True,
            "vlan_enabled": True,
        }
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_radius_profile("default", "profile-1", mock_settings)

        assert result["id"] == "profile-1"
        assert result["name"] == "Corporate RADIUS"
        assert result["vlan_enabled"] is True


@pytest.mark.asyncio
async def test_create_radius_profile_success(mock_settings):
    """Test creating a RADIUS profile."""
    mock_response = {
        "data": {
            "_id": "profile-new",
            "name": "New RADIUS",
            "auth_server": "radius.test.com",
            "auth_port": 1812,
            "enabled": True,
            "vlan_enabled": False,
        }
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_radius_profile(
            site_id="default",
            name="New RADIUS",
            auth_server="radius.test.com",
            auth_secret="test_secret",
            settings=mock_settings,
            confirm=True,
        )

        assert result["id"] == "profile-new"
        assert result["name"] == "New RADIUS"
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_create_radius_profile_dry_run(mock_settings):
    """Test create RADIUS profile dry run."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_radius_profile(
            site_id="default",
            name="Test RADIUS",
            auth_server="radius.test.com",
            auth_secret="secret123",
            settings=mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["payload"]["name"] == "Test RADIUS"
        assert result["payload"]["auth_secret"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_create_radius_profile_no_confirm(mock_settings):
    """Test that creation fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await create_radius_profile(
            site_id="default",
            name="Test",
            auth_server="radius.test.com",
            auth_secret="secret",
            settings=mock_settings,
            confirm=False,
        )

    assert "confirm=true" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_radius_profile_success(mock_settings):
    """Test updating a RADIUS profile."""
    mock_response = {
        "data": {
            "_id": "profile-1",
            "name": "Updated RADIUS",
            "auth_server": "radius.example.com",
            "auth_port": 1812,
            "enabled": True,
            "vlan_enabled": True,
        }
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_radius_profile(
            site_id="default",
            profile_id="profile-1",
            settings=mock_settings,
            name="Updated RADIUS",
            vlan_enabled=True,
            confirm=True,
        )

        assert result["name"] == "Updated RADIUS"
        assert result["vlan_enabled"] is True
        mock_client.put.assert_called_once()


@pytest.mark.asyncio
async def test_delete_radius_profile_success(mock_settings):
    """Test deleting a RADIUS profile."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.delete = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await delete_radius_profile(
            site_id="default", profile_id="profile-1", settings=mock_settings, confirm=True
        )

        assert result["success"] is True
        assert "deleted successfully" in result["message"]
        mock_client.delete.assert_called_once_with("/ea/sites/default/rest/radiusprofile/profile-1")


# =============================================================================
# RADIUS Account Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_radius_accounts_success(mock_settings):
    """Test listing RADIUS accounts."""
    mock_response = {
        "data": [
            {
                "_id": "account-1",
                "name": "user1",
                "x_password": "password123",
                "enabled": True,
                "site_id": "default",
            },
            {
                "_id": "account-2",
                "name": "user2",
                "x_password": "password456",
                "enabled": False,
                "site_id": "default",
            },
        ]
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await list_radius_accounts("default", mock_settings)

        assert len(result) == 2
        assert result[0]["name"] == "user1"
        assert result[0]["password"] == "***REDACTED***"  # Password should be redacted
        mock_client.get.assert_called_once_with("/ea/sites/default/rest/account")


@pytest.mark.asyncio
async def test_create_radius_account_success(mock_settings):
    """Test creating a RADIUS account."""
    mock_response = {
        "data": {
            "_id": "account-new",
            "name": "newuser",
            "x_password": "newpass",
            "enabled": True,
            "vlan": 10,
            "tunnel_type": 13,
            "tunnel_medium_type": 6,
            "site_id": "default",
        }
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_radius_account(
            site_id="default",
            username="newuser",
            password="newpass",
            settings=mock_settings,
            vlan_id=10,
            confirm=True,
        )

        assert result["id"] == "account-new"
        assert result["name"] == "newuser"
        assert result["password"] == "***REDACTED***"
        assert result["vlan_id"] == 10
        assert result["tunnel_type"] == 13
        assert result["tunnel_medium_type"] == 6

        # Verify correct endpoint and payload
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/ea/sites/default/rest/account"
        payload = call_args[1]["json_data"]
        assert payload["x_password"] == "newpass"
        assert payload["vlan"] == 10
        assert payload["tunnel_type"] == 13
        assert payload["tunnel_medium_type"] == 6


@pytest.mark.asyncio
async def test_delete_radius_account_success(mock_settings):
    """Test deleting a RADIUS account."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.delete = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await delete_radius_account(
            site_id="default", account_id="account-1", settings=mock_settings, confirm=True
        )

        assert result["success"] is True
        mock_client.delete.assert_called_once_with("/ea/sites/default/rest/account/account-1")


# =============================================================================
# Guest Portal Tests
# =============================================================================
#
# These tools read and write the legacy ``setting/guest_access`` section.
# The fixtures mirror its real shape: a list under "data", auth="hotspot"
# disambiguated by *_enabled flags, secrets in x_-prefixed fields.


def _guest_access_section(**overrides):
    section = {
        "_id": "ga-settings-1",
        "key": "guest_access",
        "site_id": "site-1",
        "portal_enabled": True,
        "auth": "hotspot",
        "password_enabled": False,
        "voucher_enabled": True,
        "radius_enabled": False,
        "expire": 480,
        "redirect_enabled": False,
        "x_password": "test-placeholder",
    }
    section.update(overrides)
    return section


@pytest.mark.asyncio
async def test_get_guest_portal_config_success(mock_settings):
    """Reads setting/guest_access and translates the section."""
    mock_response = {"data": [_guest_access_section()]}

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_guest_portal_config("default", mock_settings)

        mock_client.get.assert_called_once_with("/ea/sites/default/get/setting/guest_access")
        assert result["portal_enabled"] is True
        assert result["auth_method"] == "voucher"
        assert result["session_timeout"] == 480
        # Raw section is passed through for version-specific fields,
        # but never with secrets in it.
        assert result["raw"]["key"] == "guest_access"
        assert "x_password" not in result["raw"]


@pytest.mark.asyncio
async def test_get_guest_portal_config_missing_section(mock_settings):
    """An empty data list must raise, not crash or fabricate defaults."""
    from src.utils.exceptions import APIError

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value={"data": []})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        # A bare AsyncMock() __aexit__ returns a truthy mock, which tells
        # `async with` to SUPPRESS the exception under test.
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(APIError, match="guest_access"):
            await get_guest_portal_config("default", mock_settings)


@pytest.mark.asyncio
async def test_configure_guest_portal_disable_portal(mock_settings):
    """portal_enabled=False reaches the controller with the settings _id."""
    current = _guest_access_section()
    updated = _guest_access_section(portal_enabled=False)

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value={"data": [current]})
        mock_client.put = AsyncMock(return_value={"data": [updated]})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await configure_guest_portal(
            site_id="default",
            settings=mock_settings,
            portal_enabled=False,
            confirm=True,
        )

        mock_client.put.assert_called_once_with(
            "/ea/sites/default/set/setting/guest_access/ga-settings-1",
            json_data={"portal_enabled": False},
        )
        assert result["portal_enabled"] is False
        assert result["skipped_fields"] == []


@pytest.mark.asyncio
async def test_configure_guest_portal_auth_method_clears_siblings(mock_settings):
    """Choosing one hotspot method must clear the other method flags."""
    current = _guest_access_section()
    updated = _guest_access_section(password_enabled=True, voucher_enabled=False)

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value={"data": [current]})
        mock_client.put = AsyncMock(return_value={"data": [updated]})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await configure_guest_portal(
            site_id="default",
            settings=mock_settings,
            auth_method="password",
            password="hunter2",
            confirm=True,
        )

        payload = mock_client.put.call_args.kwargs["json_data"]
        assert payload["auth"] == "hotspot"
        assert payload["password_enabled"] is True
        assert payload["voucher_enabled"] is False
        assert payload["radius_enabled"] is False
        assert payload["x_password"] == "hunter2"
        assert result["auth_method"] == "password"


@pytest.mark.asyncio
async def test_configure_guest_portal_invalid_auth_method(mock_settings):
    """Unknown auth_method is rejected before touching the controller."""
    with pytest.raises(ValidationError, match="Invalid auth_method"):
        await configure_guest_portal(
            site_id="default",
            settings=mock_settings,
            auth_method="carrier-pigeon",
            confirm=True,
        )


@pytest.mark.asyncio
async def test_configure_guest_portal_password_with_other_method_rejected(mock_settings):
    """A password alongside a non-password method would be written unused."""
    with pytest.raises(ValidationError, match="auth_method='password'"):
        await configure_guest_portal(
            site_id="default",
            settings=mock_settings,
            auth_method="voucher",
            password="hunter2",
            confirm=True,
        )


@pytest.mark.asyncio
async def test_configure_guest_portal_password_switch_needs_a_password(mock_settings):
    """Switching to password auth with nothing stored and nothing given fails."""
    current = _guest_access_section()
    current.pop("x_password", None)

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get = AsyncMock(return_value={"data": [current]})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ValidationError, match="requires a password"):
            await configure_guest_portal(
                site_id="default",
                settings=mock_settings,
                auth_method="password",
                confirm=True,
            )


@pytest.mark.asyncio
async def test_configure_guest_portal_password_without_method_change_rejected(mock_settings):
    """A new password while the portal is on another method needs the switch."""
    current = _guest_access_section(voucher_enabled=True, password_enabled=False)

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.get = AsyncMock(return_value={"data": [current]})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ValidationError, match="pass\\s+auth_method='password'"):
            await configure_guest_portal(
                site_id="default",
                settings=mock_settings,
                password="hunter2",
                confirm=True,
            )


@pytest.mark.asyncio
async def test_configure_guest_portal_dry_run(mock_settings):
    """Dry run previews the legacy-field payload with secrets redacted."""
    current = _guest_access_section()

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value={"data": [current]})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await configure_guest_portal(
            site_id="default",
            settings=mock_settings,
            portal_enabled=False,
            auth_method="password",
            password="test123",
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["settings_id"] == "ga-settings-1"
        assert result["payload"]["portal_enabled"] is False
        assert result["payload"]["x_password"] == "***REDACTED***"
        mock_client.put.assert_not_called()


# =============================================================================
# Hotspot Package Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_hotspot_packages_success(mock_settings):
    """Listing reads the classic surface and passes its rows through."""
    mock_response = {
        "data": [
            {"_id": "package-1", "name": "1 Hour Basic", "hours": 1},
            {
                "_id": "package-2",
                "name": "1 Day Premium",
                "hours": 24,
                "amount": 9.99,
                "currency": "USD",
            },
        ]
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await list_hotspot_packages("default", mock_settings)

        assert "/rest/hotspotpackage" in mock_client.get.call_args[0][0]
        assert len(result) == 2
        assert result[0]["name"] == "1 Hour Basic"
        assert result[1]["amount"] == 9.99


@pytest.mark.asyncio
async def test_create_hotspot_package_success(mock_settings):
    """Test creating a hotspot package."""
    mock_response = {
        "data": {
            "_id": "package-new",
            "name": "2 Hour Package",
            "hours": 2,
            "amount": 4.99,
            "currency": "USD",
        }
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_hotspot_package(
            site_id="default",
            name="2 Hour Package",
            duration_minutes=120,
            settings=mock_settings,
            price=4.99,
            confirm=True,
        )

        assert result["_id"] == "package-new"
        assert result["name"] == "2 Hour Package"
        payload = mock_client.post.call_args[1]["json_data"]
        assert payload == {
            "name": "2 Hour Package",
            "hours": 2,
            "amount": 4.99,
            "currency": "USD",
        }


@pytest.mark.asyncio
async def test_create_hotspot_package_rejects_nonpositive_duration(mock_settings):
    """duration_minutes < 1 must be rejected, not rounded up to a paid hour."""
    from src.utils.exceptions import ValidationError

    for bad in (0, -30):
        with pytest.raises(ValidationError, match="duration_minutes"):
            await create_hotspot_package(
                site_id="default",
                name="Broken",
                duration_minutes=bad,
                settings=mock_settings,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_update_hotspot_package_rejects_currency_without_price(mock_settings):
    """currency rides alongside amount; alone it changes nothing."""
    from src.utils.exceptions import ValidationError

    with pytest.raises(ValidationError, match="currency"):
        await update_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
            currency="EUR",
            confirm=True,
        )


@pytest.mark.asyncio
async def test_update_hotspot_package_rejects_nonpositive_duration(mock_settings):
    """duration_minutes < 1 must be rejected on update too."""
    from src.utils.exceptions import ValidationError

    with pytest.raises(ValidationError, match="duration_minutes"):
        await update_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
            duration_minutes=0,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_hotspot_package_rounds_duration_up_to_hours(mock_settings):
    """The classic surface stores whole hours; partial hours round up."""
    mock_response = {"data": {"_id": "package-rounded", "name": "90 minutes", "hours": 2}}

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_hotspot_package(
            site_id="default",
            name="90 minutes",
            duration_minutes=90,
            settings=mock_settings,
            confirm=True,
        )

        assert mock_client.post.call_args[1]["json_data"]["hours"] == 2
        assert result["hours"] == 2


@pytest.mark.asyncio
async def test_delete_hotspot_package_success(mock_settings):
    """Test deleting a hotspot package."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.delete = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await delete_hotspot_package(
            site_id="default", package_id="package-1", settings=mock_settings, confirm=True
        )

        assert result["success"] is True
        assert "deleted successfully" in result["message"]
        mock_client.delete.assert_called_once()


# =============================================================================
# List Response Unwrapping Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_radius_profiles_list_response(mock_settings):
    """Test listing when API returns a list directly (not wrapped in data)."""
    mock_response = [
        {
            "_id": "profile-1",
            "name": "Direct RADIUS",
            "auth_server": "radius.example.com",
            "auth_port": 1812,
            "enabled": True,
        },
    ]

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await list_radius_profiles("default", mock_settings)

        assert len(result) == 1
        assert result[0]["name"] == "Direct RADIUS"


@pytest.mark.asyncio
async def test_get_radius_profile_list_response(mock_settings):
    """Test getting profile when API returns a list directly."""
    mock_response = [
        {
            "_id": "profile-1",
            "name": "List RADIUS",
            "auth_server": "radius.example.com",
            "auth_port": 1812,
            "enabled": True,
        },
    ]

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_radius_profile("default", "profile-1", mock_settings)

        assert result["name"] == "List RADIUS"


@pytest.mark.asyncio
async def test_get_radius_profile_empty_list_response(mock_settings):
    """Test getting profile when API returns an empty list."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=[])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        # Empty list should still be processed (may raise validation error)
        try:
            await get_radius_profile("default", "profile-1", mock_settings)
        except Exception:
            pass  # Expected - empty data can't construct RADIUSProfile


@pytest.mark.asyncio
async def test_create_radius_profile_list_response(mock_settings):
    """Test create profile when API returns a list directly."""
    mock_response = [
        {
            "_id": "profile-new",
            "name": "Created RADIUS",
            "auth_server": "radius.test.com",
            "auth_port": 1812,
            "enabled": True,
        },
    ]

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_radius_profile(
            site_id="default",
            name="Created RADIUS",
            auth_server="radius.test.com",
            auth_secret="test_secret",
            settings=mock_settings,
            confirm=True,
        )

        assert result["name"] == "Created RADIUS"


@pytest.mark.asyncio
async def test_create_radius_profile_with_acct_server(mock_settings):
    """Test create with optional accounting server and secret."""
    mock_response = {
        "data": {
            "_id": "profile-new",
            "name": "Full RADIUS",
            "auth_server": "radius.test.com",
            "auth_port": 1812,
            "acct_server": "acct.test.com",
            "acct_port": 1813,
            "enabled": True,
        }
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        await create_radius_profile(
            site_id="default",
            name="Full RADIUS",
            auth_server="radius.test.com",
            auth_secret="test_secret",
            settings=mock_settings,
            acct_server="acct.test.com",
            acct_secret="acct_secret",
            confirm=True,
        )

        # Verify payload includes accounting fields
        call_args = mock_client.post.call_args
        payload = call_args[1]["json_data"]
        assert payload["acct_server"] == "acct.test.com"
        assert payload["acct_secret"] == "acct_secret"


@pytest.mark.asyncio
async def test_create_radius_profile_dry_run_with_acct(mock_settings):
    """Test dry run includes redacted acct_secret."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_radius_profile(
            site_id="default",
            name="Test",
            auth_server="radius.test.com",
            auth_secret="secret",
            settings=mock_settings,
            acct_server="acct.test.com",
            acct_secret="acct_secret",
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["payload"]["acct_server"] == "acct.test.com"
        assert result["payload"]["acct_secret"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_update_radius_profile_list_response(mock_settings):
    """Test update when API returns a list directly."""
    mock_response = [
        {
            "_id": "profile-1",
            "name": "Updated RADIUS",
            "auth_server": "radius.example.com",
            "auth_port": 1812,
            "enabled": True,
        },
    ]

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_radius_profile(
            site_id="default",
            profile_id="profile-1",
            settings=mock_settings,
            name="Updated RADIUS",
            confirm=True,
        )

        assert result["name"] == "Updated RADIUS"


@pytest.mark.asyncio
async def test_update_radius_profile_dry_run(mock_settings):
    """Test update RADIUS profile dry run with all optional fields."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_radius_profile(
            site_id="default",
            profile_id="profile-1",
            settings=mock_settings,
            name="New Name",
            auth_server="new.radius.com",
            auth_secret="new_secret",
            auth_port=1812,
            acct_server="new.acct.com",
            acct_port=1813,
            acct_secret="new_acct_secret",
            vlan_enabled=True,
            enabled=False,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["profile_id"] == "profile-1"
        payload = result["payload"]
        assert payload["name"] == "New Name"
        assert payload["auth_server"] == "new.radius.com"
        assert payload["auth_secret"] == "***REDACTED***"
        assert payload["auth_port"] == 1812
        assert payload["acct_server"] == "new.acct.com"
        assert payload["acct_port"] == 1813
        assert payload["acct_secret"] == "***REDACTED***"
        assert payload["vlan_enabled"] is True
        assert payload["enabled"] is False


@pytest.mark.asyncio
async def test_update_radius_profile_with_all_fields(mock_settings):
    """Test update with all optional fields set."""
    mock_response = {
        "data": {
            "_id": "profile-1",
            "name": "Full Update",
            "auth_server": "new.radius.com",
            "auth_port": 1812,
            "enabled": True,
        }
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        await update_radius_profile(
            site_id="default",
            profile_id="profile-1",
            settings=mock_settings,
            name="Full Update",
            auth_server="new.radius.com",
            auth_secret="new_secret",
            auth_port=1812,
            acct_server="new.acct.com",
            acct_port=1813,
            acct_secret="new_acct_secret",
            vlan_enabled=True,
            enabled=True,
            confirm=True,
        )

        call_args = mock_client.put.call_args
        payload = call_args[1]["json_data"]
        assert payload["name"] == "Full Update"
        assert payload["auth_server"] == "new.radius.com"
        assert payload["auth_secret"] == "new_secret"
        assert payload["auth_port"] == 1812
        assert payload["acct_server"] == "new.acct.com"
        assert payload["acct_port"] == 1813
        assert payload["acct_secret"] == "new_acct_secret"
        assert payload["vlan_enabled"] is True
        assert payload["enabled"] is True


@pytest.mark.asyncio
async def test_update_radius_profile_no_confirm(mock_settings):
    """Test that update fails without confirmation."""
    with pytest.raises(ValidationError, match="requires confirmation"):
        await update_radius_profile(
            site_id="default",
            profile_id="profile-1",
            settings=mock_settings,
            name="Test",
            confirm=False,
        )


@pytest.mark.asyncio
async def test_delete_radius_profile_dry_run(mock_settings):
    """Test delete RADIUS profile dry run."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await delete_radius_profile(
            site_id="default",
            profile_id="profile-1",
            settings=mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["profile_id"] == "profile-1"
        mock_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_list_radius_accounts_list_response(mock_settings):
    """Test listing accounts when API returns a list directly."""
    mock_response = [
        {
            "_id": "account-1",
            "name": "user1",
            "x_password": "password123",
            "site_id": "default",
        },
    ]

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await list_radius_accounts("default", mock_settings)

        assert len(result) == 1
        assert result[0]["password"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_create_radius_account_dry_run(mock_settings):
    """Test create RADIUS account dry run."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_radius_account(
            site_id="default",
            username="testuser",
            password="testpass",
            settings=mock_settings,
            vlan_id=10,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["payload"]["x_password"] == "***REDACTED***"
        assert result["payload"]["vlan"] == 10


@pytest.mark.asyncio
async def test_create_radius_account_list_response(mock_settings):
    """Test create account when API returns a list directly."""
    mock_response = [
        {
            "_id": "account-new",
            "name": "newuser",
            "x_password": "newpass",
            "site_id": "default",
        }
    ]

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_radius_account(
            site_id="default",
            username="newuser",
            password="newpass",
            settings=mock_settings,
            confirm=True,
        )

        assert result["name"] == "newuser"
        assert result["password"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_create_radius_account_without_vlan(mock_settings):
    """Test create account without VLAN but with tunnel attributes."""
    mock_response = {
        "data": {
            "_id": "account-new",
            "name": "newuser",
            "x_password": "newpass",
            "tunnel_type": 13,
            "site_id": "default",
        }
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        await create_radius_account(
            site_id="default",
            username="newuser",
            password="newpass",
            settings=mock_settings,
            tunnel_type=13,
            tunnel_medium_type=6,
            confirm=True,
        )

        # Verify tunnel attrs set without vlan
        call_args = mock_client.post.call_args
        payload = call_args[1]["json_data"]
        assert payload["tunnel_type"] == 13
        assert payload["tunnel_medium_type"] == 6
        assert "vlan" not in payload


@pytest.mark.asyncio
async def test_create_radius_account_with_note(mock_settings):
    """Test create account with admin note."""
    mock_response = {
        "data": {
            "_id": "account-new",
            "name": "newuser",
            "x_password": "newpass",
            "note": "Test note",
            "site_id": "default",
        }
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        await create_radius_account(
            site_id="default",
            username="newuser",
            password="newpass",
            settings=mock_settings,
            note="Test note",
            confirm=True,
        )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json_data"]
        assert payload["note"] == "Test note"


@pytest.mark.asyncio
async def test_delete_radius_account_dry_run(mock_settings):
    """Test delete RADIUS account dry run."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await delete_radius_account(
            site_id="default",
            account_id="account-1",
            settings=mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["account_id"] == "account-1"
        mock_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_configure_guest_portal_put_not_echoed(mock_settings):
    """When PUT returns no body, re-read so the caller sees stored state."""
    current = _guest_access_section()
    stored = _guest_access_section(portal_enabled=False)

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[{"data": [current]}, {"data": [stored]}])
        mock_client.put = AsyncMock(return_value={"data": []})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await configure_guest_portal(
            site_id="default",
            settings=mock_settings,
            portal_enabled=False,
            confirm=True,
        )

        assert mock_client.get.call_count == 2
        assert result["portal_enabled"] is False


@pytest.mark.asyncio
async def test_configure_guest_portal_versioned_fields(mock_settings):
    """Title/ToS keys are written only when this controller reports them."""
    # Controller knows portal_customized_title but not the ToS keys.
    current = _guest_access_section(portal_customized_title="Old title")

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value={"data": [current]})
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await configure_guest_portal(
            site_id="default",
            settings=mock_settings,
            portal_title="New title",
            terms_of_service_enabled=True,
            terms_of_service_text="Accept these terms.",
            session_timeout=120,
            redirect_enabled=True,
            redirect_url="https://example.com",
            confirm=True,
            dry_run=True,
        )

        payload = result["payload"]
        assert payload["portal_customized_title"] == "New title"
        assert payload["expire"] == 120
        assert payload["redirect_enabled"] is True
        assert payload["redirect_url"] == "https://example.com"
        assert "portal_customized_tos" not in payload
        assert sorted(result["skipped_fields"]) == [
            "portal_customized_tos",
            "portal_customized_tos_enabled",
        ]


@pytest.mark.asyncio
async def test_configure_guest_portal_no_confirm(mock_settings):
    """Test configure portal fails without confirmation."""
    with pytest.raises(ValidationError, match="requires confirmation"):
        await configure_guest_portal(
            site_id="default",
            settings=mock_settings,
            portal_title="Test",
            confirm=False,
        )


@pytest.mark.asyncio
async def test_list_hotspot_packages_list_response(mock_settings):
    """Test listing hotspot packages when API returns a list."""
    mock_response = [
        {
            "_id": "package-1",
            "name": "1 Hour Basic",
            "duration_minutes": 60,
            "enabled": True,
            "site_id": "default",
        },
    ]

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await list_hotspot_packages("default", mock_settings)

        assert len(result) == 1
        assert result[0]["name"] == "1 Hour Basic"


@pytest.mark.asyncio
async def test_create_hotspot_package_dry_run(mock_settings):
    """Test create hotspot package dry run."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_hotspot_package(
            site_id="default",
            name="Test Package",
            duration_minutes=60,
            settings=mock_settings,
            price=4.99,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["payload"] == {
            "name": "Test Package",
            "hours": 1,
            "amount": 4.99,
            "currency": "USD",
        }


@pytest.mark.asyncio
async def test_create_hotspot_package_list_response(mock_settings):
    """Test create hotspot when API returns a list directly."""
    mock_response = [
        {
            "_id": "package-new",
            "name": "New Package",
            "duration_minutes": 120,
            "enabled": True,
            "site_id": "default",
        }
    ]

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await create_hotspot_package(
            site_id="default",
            name="New Package",
            duration_minutes=120,
            settings=mock_settings,
            confirm=True,
        )

        assert result["name"] == "New Package"


@pytest.mark.asyncio
async def test_create_hotspot_package_no_confirm(mock_settings):
    """Test create hotspot fails without confirmation."""
    with pytest.raises(ValidationError, match="requires confirmation"):
        await create_hotspot_package(
            site_id="default",
            name="Test",
            duration_minutes=60,
            settings=mock_settings,
            confirm=False,
        )


@pytest.mark.asyncio
async def test_delete_hotspot_package_dry_run(mock_settings):
    """Test delete hotspot package dry run."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await delete_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["package_id"] == "package-1"
        mock_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_hotspot_package_no_confirm(mock_settings):
    """Test delete hotspot fails without confirmation."""
    with pytest.raises(ValidationError, match="requires confirmation"):
        await delete_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
            confirm=False,
        )


# =============================================================================
# RADIUS Account - get and update (new P2 operations)
# =============================================================================


@pytest.mark.asyncio
async def test_get_radius_account_success(mock_settings):
    """Test successful retrieval of a single RADIUS account."""
    mock_response = {
        "data": [
            {
                "_id": "acct-1",
                "name": "alice",
                "x_password": "secret",
                "enabled": True,
                "site_id": "default",
            }
        ]
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_radius_account(
            site_id="default",
            account_id="acct-1",
            settings=mock_settings,
        )

        assert result["name"] == "alice"
        assert result["password"] == "***REDACTED***"
        mock_client.get.assert_called_once_with("/ea/sites/default/rest/account/acct-1")


@pytest.mark.asyncio
async def test_get_radius_account_list_response(mock_settings):
    """Test get radius account when API returns a list directly."""
    mock_response = [
        {
            "_id": "acct-2",
            "name": "bob",
            "x_password": "hunter2",
            "enabled": True,
            "site_id": "default",
        }
    ]

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_radius_account(
            site_id="default",
            account_id="acct-2",
            settings=mock_settings,
        )

        assert result["name"] == "bob"
        assert result["password"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_get_radius_account_empty_response(mock_settings):
    """Test get radius account when API returns empty list."""
    mock_response = {"data": []}

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_radius_account(
            site_id="default",
            account_id="nonexistent",
            settings=mock_settings,
        )

        assert result == {}


@pytest.mark.asyncio
async def test_update_radius_account_username_only(mock_settings):
    """Test update radius account with username change only."""
    mock_response = {
        "data": [
            {
                "_id": "acct-1",
                "name": "bob",
                "x_password": "secret",
                "enabled": True,
                "site_id": "default",
            }
        ]
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_radius_account(
            site_id="default",
            account_id="acct-1",
            settings=mock_settings,
            username="bob",
            confirm=True,
        )

        assert result["name"] == "bob"
        call_kwargs = mock_client.put.call_args[1]["json_data"]
        assert call_kwargs == {"name": "bob"}


@pytest.mark.asyncio
async def test_update_radius_account_vlan(mock_settings):
    """Test update radius account sets correct API field names for VLAN."""
    mock_response = {
        "data": [
            {
                "_id": "acct-1",
                "name": "alice",
                "x_password": "secret",
                "enabled": True,
                "vlan": 10,
                "site_id": "default",
            }
        ]
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_radius_account(
            site_id="default",
            account_id="acct-1",
            settings=mock_settings,
            vlan_id=10,
            confirm=True,
        )

        assert result["vlan_id"] == 10
        call_kwargs = mock_client.put.call_args[1]["json_data"]
        assert call_kwargs == {"vlan": 10}


@pytest.mark.asyncio
async def test_update_radius_account_no_confirm(mock_settings):
    """Test update radius account requires confirmation."""
    with pytest.raises(ValidationError, match="requires confirmation"):
        await update_radius_account(
            site_id="default",
            account_id="acct-1",
            settings=mock_settings,
            username="newname",
            confirm=False,
        )


@pytest.mark.asyncio
async def test_update_radius_account_dry_run(mock_settings):
    """Test update radius account dry run does not call API."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_radius_account(
            site_id="default",
            account_id="acct-1",
            settings=mock_settings,
            username="dryuser",
            password="s3cr3t",
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["account_id"] == "acct-1"
        assert result["payload"]["name"] == "dryuser"
        assert result["payload"]["x_password"] == "***REDACTED***"
        mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_update_radius_account_all_fields(mock_settings):
    """Test update radius account with all optional fields."""
    mock_response = {
        "data": [
            {
                "_id": "acct-1",
                "name": "alice",
                "x_password": "newpass",
                "enabled": False,
                "vlan": 20,
                "tunnel_type": 13,
                "tunnel_medium_type": 6,
                "note": "updated",
                "site_id": "default",
            }
        ]
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_radius_account(
            site_id="default",
            account_id="acct-1",
            settings=mock_settings,
            username="alice",
            password="newpass",
            vlan_id=20,
            tunnel_type=13,
            tunnel_medium_type=6,
            enabled=False,
            note="updated",
            confirm=True,
        )

        call_kwargs = mock_client.put.call_args[1]["json_data"]
        assert "name" in call_kwargs
        assert "x_password" in call_kwargs
        assert call_kwargs["vlan"] == 20
        assert call_kwargs["enabled"] is False
        assert call_kwargs["note"] == "updated"
        assert result["password"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_update_radius_account_no_fields_raises(mock_settings):
    """Test update radius account with no fields raises ValueError before opening connection."""
    with pytest.raises(ValueError, match="At least one field"):
        await update_radius_account(
            site_id="default",
            account_id="acct-1",
            settings=mock_settings,
            confirm=True,
        )


# =============================================================================
# Hotspot Package - get and update (new P2 operations)
# =============================================================================


@pytest.mark.asyncio
async def test_get_hotspot_package_success(mock_settings):
    """Test successful retrieval of a single hotspot package."""
    mock_response = {"data": [{"_id": "package-1", "name": "1 Hour", "hours": 1}]}

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
        )

        assert result["name"] == "1 Hour"
        assert result["hours"] == 1
        mock_client.get.assert_called_once_with("/ea/sites/default/rest/hotspotpackage/package-1")


@pytest.mark.asyncio
async def test_get_hotspot_package_list_response(mock_settings):
    """Test get hotspot package when API returns a list directly."""
    mock_response = [
        {
            "_id": "package-2",
            "name": "Day Pass",
            "duration_minutes": 1440,
            "enabled": True,
            "site_id": "default",
        }
    ]

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_hotspot_package(
            site_id="default",
            package_id="package-2",
            settings=mock_settings,
        )

        assert result["name"] == "Day Pass"
        assert result["duration_minutes"] == 1440


@pytest.mark.asyncio
async def test_update_hotspot_package_name_only(mock_settings):
    """Test update hotspot package with name change only."""
    mock_response = {
        "data": [
            {
                "_id": "package-1",
                "name": "Renamed Package",
                "duration_minutes": 60,
                "enabled": True,
                "site_id": "default",
            }
        ]
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
            name="Renamed Package",
            confirm=True,
        )

        assert result["name"] == "Renamed Package"
        call_kwargs = mock_client.put.call_args[1]["json_data"]
        assert call_kwargs == {"name": "Renamed Package"}


@pytest.mark.asyncio
async def test_update_hotspot_package_price_and_duration(mock_settings):
    """Updates map to the classic amount/hours fields."""
    mock_response = {"data": [{"_id": "package-1", "name": "Limited", "hours": 2, "amount": 9.99}]}

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
            duration_minutes=120,
            price=9.99,
            confirm=True,
        )

        assert result["amount"] == 9.99
        call_kwargs = mock_client.put.call_args[1]["json_data"]
        assert call_kwargs == {"hours": 2, "amount": 9.99}


@pytest.mark.asyncio
async def test_update_hotspot_package_no_confirm(mock_settings):
    """Test update hotspot package requires confirmation."""
    with pytest.raises(ValidationError, match="requires confirmation"):
        await update_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
            name="New Name",
            confirm=False,
        )


@pytest.mark.asyncio
async def test_update_hotspot_package_dry_run(mock_settings):
    """Test update hotspot package dry run does not call API."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
            name="Preview Name",
            duration_minutes=30,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["package_id"] == "package-1"
        assert result["payload"]["name"] == "Preview Name"
        assert result["payload"]["hours"] == 1
        mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_update_hotspot_package_no_fields_raises(mock_settings):
    """Test update hotspot package with no fields raises ValueError before opening connection."""
    with pytest.raises(ValueError, match="At least one field"):
        await update_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_update_hotspot_package_all_fields(mock_settings):
    """Test update hotspot package with every supported field."""
    mock_response = {
        "data": [
            {
                "_id": "package-1",
                "name": "Full Package",
                "hours": 2,
                "amount": 4.99,
                "currency": "EUR",
            }
        ]
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_hotspot_package(
            site_id="default",
            package_id="package-1",
            settings=mock_settings,
            name="Full Package",
            duration_minutes=120,
            price=4.99,
            currency="EUR",
            confirm=True,
        )

        call_kwargs = mock_client.put.call_args[1]["json_data"]
        assert call_kwargs == {
            "name": "Full Package",
            "hours": 2,
            "amount": 4.99,
            "currency": "EUR",
        }
        assert result["amount"] == 4.99


@pytest.mark.asyncio
async def test_get_hotspot_package_empty_response(mock_settings):
    """Test get hotspot package when API returns empty list."""
    mock_response = {"data": []}

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_hotspot_package(
            site_id="default",
            package_id="nonexistent",
            settings=mock_settings,
        )

        assert result == {}


# ---------------------------------------------------------------------------
# Branch coverage: already-authenticated, dict responses, missing fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_radius_account_already_authenticated(mock_settings):
    """Cover is_authenticated=True branch and dict (non-list) data response."""
    mock_response = {
        "_id": "acct-1",
        "name": "alice",
        "x_password": "secret",
        "enabled": True,
        "site_id": "default",
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_radius_account(
            site_id="default", account_id="acct-1", settings=mock_settings
        )

        mock_client.authenticate.assert_not_called()
        assert result["name"] == "alice"


@pytest.mark.asyncio
async def test_update_radius_account_dry_run_no_password(mock_settings):
    """Cover False branch of 'if x_password in payload_safe' in dry_run."""
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = False
        mock_client.authenticate = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_radius_account(
            site_id="default",
            account_id="acct-1",
            settings=mock_settings,
            username="nopass",
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert "x_password" not in result["payload"]
        mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_update_radius_account_already_auth_dict_response(mock_settings):
    """Cover is_authenticated=True and dict (non-list) PUT response."""
    mock_response = {
        "_id": "acct-1",
        "name": "alice",
        "x_password": "secret",
        "enabled": True,
        "site_id": "default",
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_radius_account(
            site_id="default",
            account_id="acct-1",
            settings=mock_settings,
            username="alice",
            confirm=True,
        )

        mock_client.authenticate.assert_not_called()
        assert result["name"] == "alice"


@pytest.mark.asyncio
async def test_get_hotspot_package_already_authenticated(mock_settings):
    """Cover is_authenticated=True branch and dict (non-list) data response."""
    mock_response = {
        "_id": "pkg-1",
        "name": "Basic",
        "duration_minutes": 60,
        "download_limit_kbps": 5000,
        "upload_limit_kbps": 2000,
        "site_id": "default",
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await get_hotspot_package(
            site_id="default", package_id="pkg-1", settings=mock_settings
        )

        mock_client.authenticate.assert_not_called()
        assert result["name"] == "Basic"


@pytest.mark.asyncio
async def test_update_hotspot_package_already_auth_dict_response(mock_settings):
    """Cover is_authenticated=True and dict PUT response in update_hotspot_package."""
    mock_response = {
        "_id": "pkg-1",
        "name": "Updated",
        "duration_minutes": 120,
        "download_limit_kbps": 10000,
        "upload_limit_kbps": 5000,
        "site_id": "default",
    }

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.is_authenticated = True
        mock_client.authenticate = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = await update_hotspot_package(
            site_id="default",
            package_id="pkg-1",
            settings=mock_settings,
            name="Updated",
            confirm=True,
        )

        mock_client.authenticate.assert_not_called()
        assert result["name"] == "Updated"


# ---------------------------------------------------------------------------
# Guest portal: translation and write branches codecov flagged as uncovered.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_guest_portal_config_radius_method(mock_settings):
    """auth=hotspot with radius_enabled translates to auth_method=radius."""
    section = _guest_access_section(
        password_enabled=False, voucher_enabled=False, radius_enabled=True
    )
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        client = MagicMock()
        client.is_authenticated = True
        client.get = AsyncMock(return_value={"data": [section]})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = client

        result = await get_guest_portal_config("site-1", mock_settings)

    assert result["auth_method"] == "radius"


@pytest.mark.asyncio
async def test_get_guest_portal_config_ambiguous_hotspot(mock_settings):
    """auth=hotspot with no method flag is reported faithfully, not remapped."""
    section = _guest_access_section(
        password_enabled=False, voucher_enabled=False, radius_enabled=False
    )
    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        client = MagicMock()
        client.is_authenticated = True
        client.get = AsyncMock(return_value={"data": [section]})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = client

        result = await get_guest_portal_config("site-1", mock_settings)

    assert result["auth_method"] == "hotspot"


@pytest.mark.asyncio
async def test_get_guest_portal_config_external_and_none(mock_settings):
    """auth=custom maps to external; anything else maps to none."""
    for auth, expected in (("custom", "external"), ("none", "none"), ("", "none")):
        section = _guest_access_section(auth=auth)
        with patch("src.tools.radius.UniFiClient") as mock_client_class:
            client = MagicMock()
            client.is_authenticated = True
            client.get = AsyncMock(return_value={"data": [section]})
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = client

            result = await get_guest_portal_config("site-1", mock_settings)

        assert result["auth_method"] == expected, auth


@pytest.mark.asyncio
async def test_configure_guest_portal_missing_section_raises(mock_settings):
    """A response with no settings id cannot be written to."""
    from src.utils.exceptions import APIError

    with patch("src.tools.radius.UniFiClient") as mock_client_class:
        client = MagicMock()
        client.is_authenticated = True
        client.get = AsyncMock(return_value={"data": []})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = client

        with pytest.raises(APIError, match="guest_access settings section"):
            await configure_guest_portal(
                site_id="site-1",
                settings=mock_settings,
                portal_enabled=True,
                confirm=True,
            )


@pytest.mark.asyncio
async def test_configure_guest_portal_external_and_none_payloads(mock_settings):
    """external writes auth=custom; none writes auth=none."""
    for method, expected in (("external", "custom"), ("none", "none")):
        with patch("src.tools.radius.UniFiClient") as mock_client_class:
            client = MagicMock()
            client.is_authenticated = True
            client.get = AsyncMock(return_value={"data": [_guest_access_section()]})
            client.put = AsyncMock(return_value={"data": [_guest_access_section()]})
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = client

            with patch("src.tools.radius.audit_action", new_callable=AsyncMock):
                await configure_guest_portal(
                    site_id="site-1",
                    settings=mock_settings,
                    auth_method=method,
                    confirm=True,
                )

        payload = client.put.call_args[1]["json_data"]
        assert payload["auth"] == expected, method


def test_first_item_handles_bare_list_and_scalars():
    """The unwrap helper accepts a bare list and refuses scalars."""
    from src.tools.radius import _first_item

    assert _first_item([{"_id": "a"}]) == {"_id": "a"}
    assert _first_item([]) == {}
    assert _first_item("nonsense") == {}
    assert _first_item(None) == {}
