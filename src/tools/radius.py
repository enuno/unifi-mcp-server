"""RADIUS profile and guest portal management tools."""

from typing import Any

from ..api.client import UniFiClient
from ..config import Settings
from ..models.radius import GuestPortalConfig, HotspotPackage, RADIUSAccount, RADIUSProfile
from ..utils import audit_action, get_logger, validate_confirmation

logger = get_logger(__name__)


# =============================================================================
# RADIUS Profile Management
# =============================================================================


async def list_radius_profiles(
    site_id: str,
    settings: Settings,
) -> list[dict]:
    """List all RADIUS profiles for a site.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        List of RADIUS profiles
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Listing RADIUS profiles for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/radiusprofile")
        data = response if isinstance(response, list) else response.get("data", [])

        return [RADIUSProfile(**profile).model_dump() for profile in data]


async def get_radius_profile(
    site_id: str,
    profile_id: str,
    settings: Settings,
) -> dict:
    """Get details for a specific RADIUS profile.

    Args:
        site_id: Site identifier
        profile_id: RADIUS profile ID
        settings: Application settings

    Returns:
        RADIUS profile details
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Getting RADIUS profile {profile_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/radiusprofile/{profile_id}")
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        return RADIUSProfile(**data).model_dump()  # type: ignore[no-any-return]


async def create_radius_profile(
    site_id: str,
    name: str,
    auth_server: str,
    auth_secret: str,
    settings: Settings,
    auth_port: int = 1812,
    acct_server: str | None = None,
    acct_port: int = 1813,
    acct_secret: str | None = None,
    use_same_secret: bool = True,
    vlan_enabled: bool = False,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new RADIUS profile.

    Args:
        site_id: Site identifier
        name: Profile name
        auth_server: Authentication server IP/hostname
        auth_secret: Shared secret for authentication
        settings: Application settings
        auth_port: Authentication port (default: 1812)
        acct_server: Accounting server IP/hostname (optional)
        acct_port: Accounting port (default: 1813)
        acct_secret: Accounting server secret (optional)
        use_same_secret: Use auth_secret for accounting
        vlan_enabled: Enable VLAN assignment
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created RADIUS profile
    """
    validate_confirmation(confirm, "create RADIUS profile", dry_run)

    async with UniFiClient(settings) as client:
        logger.info(f"Creating RADIUS profile '{name}' for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload
        payload: dict[str, Any] = {
            "name": name,
            "auth_server": auth_server,
            "auth_port": auth_port,
            "auth_secret": auth_secret,
            "acct_port": acct_port,
            "use_same_secret": use_same_secret,
            "vlan_enabled": vlan_enabled,
            "enabled": True,
        }

        if acct_server:
            payload["acct_server"] = acct_server
        if acct_secret:
            payload["acct_secret"] = acct_secret

        if dry_run:
            # Build safe payload without secrets for logging
            payload_safe = {
                "name": name,
                "auth_server": auth_server,
                "auth_port": auth_port,
                "auth_secret": "***REDACTED***",
                "acct_port": acct_port,
                "use_same_secret": use_same_secret,
                "vlan_enabled": vlan_enabled,
                "enabled": True,
            }
            if acct_server:
                payload_safe["acct_server"] = acct_server
            if acct_secret:
                payload_safe["acct_secret"] = "***REDACTED***"
            logger.info(f"[DRY RUN] Would create RADIUS profile with payload: {payload_safe}")
            return {"dry_run": True, "payload": payload_safe}

        response = await client.post(f"/ea/sites/{site_id}/rest/radiusprofile", json_data=payload)
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        # Audit the action
        await audit_action(
            settings,
            action_type="create_radius_profile",
            resource_type="radius_profile",
            resource_id=data.get("_id", "unknown"),
            site_id=site_id,
            details={"name": name, "auth_server": auth_server},
        )

        return RADIUSProfile(**data).model_dump()  # type: ignore[no-any-return]


async def update_radius_profile(
    site_id: str,
    profile_id: str,
    settings: Settings,
    name: str | None = None,
    auth_server: str | None = None,
    auth_secret: str | None = None,
    auth_port: int | None = None,
    acct_server: str | None = None,
    acct_port: int | None = None,
    acct_secret: str | None = None,
    vlan_enabled: bool | None = None,
    enabled: bool | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing RADIUS profile.

    Args:
        site_id: Site identifier
        profile_id: RADIUS profile ID
        settings: Application settings
        name: Profile name
        auth_server: Authentication server IP/hostname
        auth_secret: Shared secret for authentication
        auth_port: Authentication port
        acct_server: Accounting server IP/hostname
        acct_port: Accounting port
        acct_secret: Accounting server secret
        vlan_enabled: Enable VLAN assignment
        enabled: Profile enabled status
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Updated RADIUS profile
    """
    validate_confirmation(confirm, "update RADIUS profile", dry_run)

    async with UniFiClient(settings) as client:
        logger.info(f"Updating RADIUS profile {profile_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build update payload with only provided fields
        payload: dict[str, Any] = {}

        if name is not None:
            payload["name"] = name
        if auth_server is not None:
            payload["auth_server"] = auth_server
        if auth_secret is not None:
            payload["auth_secret"] = auth_secret
        if auth_port is not None:
            payload["auth_port"] = auth_port
        if acct_server is not None:
            payload["acct_server"] = acct_server
        if acct_port is not None:
            payload["acct_port"] = acct_port
        if acct_secret is not None:
            payload["acct_secret"] = acct_secret
        if vlan_enabled is not None:
            payload["vlan_enabled"] = vlan_enabled
        if enabled is not None:
            payload["enabled"] = enabled

        if dry_run:
            # Build safe payload without secrets for logging
            payload_safe = {}
            if name is not None:
                payload_safe["name"] = name
            if auth_server is not None:
                payload_safe["auth_server"] = auth_server
            if auth_secret is not None:
                payload_safe["auth_secret"] = "***REDACTED***"
            if auth_port is not None:
                payload_safe["auth_port"] = auth_port
            if acct_server is not None:
                payload_safe["acct_server"] = acct_server
            if acct_port is not None:
                payload_safe["acct_port"] = acct_port
            if acct_secret is not None:
                payload_safe["acct_secret"] = "***REDACTED***"
            if vlan_enabled is not None:
                payload_safe["vlan_enabled"] = vlan_enabled
            if enabled is not None:
                payload_safe["enabled"] = enabled
            logger.info(f"[DRY RUN] Would update RADIUS profile with payload: {payload_safe}")
            return {"dry_run": True, "profile_id": profile_id, "payload": payload_safe}

        response = await client.put(
            f"/ea/sites/{site_id}/rest/radiusprofile/{profile_id}", json_data=payload
        )
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        # Audit the action
        await audit_action(
            settings,
            action_type="update_radius_profile",
            resource_type="radius_profile",
            resource_id=profile_id,
            site_id=site_id,
            details=payload,
        )

        return RADIUSProfile(**data).model_dump()  # type: ignore[no-any-return]


async def delete_radius_profile(
    site_id: str,
    profile_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Delete a RADIUS profile.

    Args:
        site_id: Site identifier
        profile_id: RADIUS profile ID
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion status
    """
    validate_confirmation(confirm, "delete RADIUS profile", dry_run)

    async with UniFiClient(settings) as client:
        logger.info(f"Deleting RADIUS profile {profile_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(f"[DRY RUN] Would delete RADIUS profile {profile_id}")
            return {"dry_run": True, "profile_id": profile_id}

        await client.delete(f"/ea/sites/{site_id}/rest/radiusprofile/{profile_id}")

        # Audit the action
        await audit_action(
            settings,
            action_type="delete_radius_profile",
            resource_type="radius_profile",
            resource_id=profile_id,
            site_id=site_id,
            details={},
        )

        return {"success": True, "message": f"RADIUS profile {profile_id} deleted successfully"}


# =============================================================================
# RADIUS Account Management
# =============================================================================


async def list_radius_accounts(
    site_id: str,
    settings: Settings,
) -> list[dict]:
    """List all RADIUS accounts for a site.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        List of RADIUS accounts
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Listing RADIUS accounts for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/account")
        data = response if isinstance(response, list) else response.get("data", [])

        # Redact passwords in response
        for account in data:
            if "x_password" in account:
                account["x_password"] = "***REDACTED***"

        return [RADIUSAccount(**account).model_dump() for account in data]


async def create_radius_account(
    site_id: str,
    username: str,
    password: str,
    settings: Settings,
    vlan_id: int | None = None,
    tunnel_type: int | None = None,
    tunnel_medium_type: int | None = None,
    enabled: bool = True,
    note: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new RADIUS account (local credential).

    Uses the /rest/account endpoint for local RADIUS user management.

    Args:
        site_id: Site identifier
        username: Account username
        password: Account password
        settings: Application settings
        vlan_id: Assigned VLAN ID (auto-sets tunnel_type=13 and tunnel_medium_type=6)
        tunnel_type: RADIUS tunnel type (13 for VLAN, auto-set when vlan_id is provided)
        tunnel_medium_type: RADIUS tunnel medium type (6 for 802, auto-set when vlan_id is provided)
        enabled: Account enabled status
        note: Admin notes
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created RADIUS account
    """
    validate_confirmation(confirm, "create RADIUS account", dry_run)

    async with UniFiClient(settings) as client:
        logger.info(f"Creating RADIUS account '{username}' for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload using correct API field names
        payload: dict[str, Any] = {
            "name": username,
            "x_password": password,
        }

        if vlan_id is not None:
            payload["vlan"] = vlan_id
            # Auto-set tunnel attributes for VLAN assignment if not explicitly provided
            payload["tunnel_type"] = tunnel_type if tunnel_type is not None else 13
            payload["tunnel_medium_type"] = (
                tunnel_medium_type if tunnel_medium_type is not None else 6
            )
        else:
            if tunnel_type is not None:
                payload["tunnel_type"] = tunnel_type
            if tunnel_medium_type is not None:
                payload["tunnel_medium_type"] = tunnel_medium_type

        if note:
            payload["note"] = note

        if dry_run:
            logger.info(f"[DRY RUN] Would create RADIUS account with username: {username}")
            payload_safe = payload.copy()
            payload_safe["x_password"] = "***REDACTED***"
            return {"dry_run": True, "payload": payload_safe}

        response = await client.post(f"/ea/sites/{site_id}/rest/account", json_data=payload)
        data = response if isinstance(response, list) else response.get("data", response)

        # Handle list response (auto-unwrapped)
        if isinstance(data, list):
            data = data[0] if data else {}

        # Audit the action
        await audit_action(
            settings,
            action_type="create_radius_account",
            resource_type="radius_account",
            resource_id=data.get("_id", "unknown"),
            site_id=site_id,
            details={"username": username, "vlan_id": vlan_id},
        )

        # Redact password before returning
        if "x_password" in data:
            data["x_password"] = "***REDACTED***"

        return RADIUSAccount(**data).model_dump()  # type: ignore[no-any-return]


async def delete_radius_account(
    site_id: str,
    account_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Delete a RADIUS account.

    Args:
        site_id: Site identifier
        account_id: RADIUS account ID
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion status
    """
    validate_confirmation(confirm, "delete RADIUS account", dry_run)

    async with UniFiClient(settings) as client:
        logger.info(f"Deleting RADIUS account {account_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(f"[DRY RUN] Would delete RADIUS account {account_id}")
            return {"dry_run": True, "account_id": account_id}

        await client.delete(f"/ea/sites/{site_id}/rest/account/{account_id}")

        # Audit the action
        await audit_action(
            settings,
            action_type="delete_radius_account",
            resource_type="radius_account",
            resource_id=account_id,
            site_id=site_id,
            details={},
        )

        return {"success": True, "message": f"RADIUS account {account_id} deleted successfully"}


# =============================================================================
# Guest Portal Configuration
# =============================================================================


async def get_guest_portal_config(
    site_id: str,
    settings: Settings,
) -> dict:
    """Get guest portal configuration for a site.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Guest portal configuration
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Getting guest portal config for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/guest-portal/config")
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        return GuestPortalConfig(**data).model_dump()  # type: ignore[no-any-return]


async def configure_guest_portal(
    site_id: str,
    settings: Settings,
    portal_title: str | None = None,
    auth_method: str | None = None,
    password: str | None = None,
    session_timeout: int | None = None,
    redirect_enabled: bool | None = None,
    redirect_url: str | None = None,
    terms_of_service_enabled: bool | None = None,
    terms_of_service_text: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Configure guest portal settings.

    Args:
        site_id: Site identifier
        settings: Application settings
        portal_title: Portal page title
        auth_method: Authentication method (none/password/voucher/radius/external)
        password: Portal password (if auth_method=password)
        session_timeout: Session timeout in minutes
        redirect_enabled: Enable redirect after authentication
        redirect_url: Redirect URL
        terms_of_service_enabled: Require ToS acceptance
        terms_of_service_text: Terms of service text
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Updated guest portal configuration
    """
    validate_confirmation(confirm, "configure guest portal", dry_run)

    async with UniFiClient(settings) as client:
        logger.info(f"Configuring guest portal for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build update payload
        payload: dict[str, Any] = {}

        if portal_title is not None:
            payload["portal_title"] = portal_title
        if auth_method is not None:
            payload["auth_method"] = auth_method
        if password is not None:
            payload["password"] = password
        if session_timeout is not None:
            payload["session_timeout"] = session_timeout
        if redirect_enabled is not None:
            payload["redirect_enabled"] = redirect_enabled
        if redirect_url is not None:
            payload["redirect_url"] = redirect_url
        if terms_of_service_enabled is not None:
            payload["terms_of_service_enabled"] = terms_of_service_enabled
        if terms_of_service_text is not None:
            payload["terms_of_service_text"] = terms_of_service_text

        if dry_run:
            # Build safe payload without secrets for logging
            payload_safe = {}
            if portal_title is not None:
                payload_safe["portal_title"] = portal_title
            if auth_method is not None:
                payload_safe["auth_method"] = auth_method
            if password is not None:
                payload_safe["password"] = "***REDACTED***"
            if session_timeout is not None:
                payload_safe["session_timeout"] = session_timeout
            if redirect_enabled is not None:
                payload_safe["redirect_enabled"] = redirect_enabled
            if redirect_url is not None:
                payload_safe["redirect_url"] = redirect_url
            if terms_of_service_enabled is not None:
                payload_safe["terms_of_service_enabled"] = terms_of_service_enabled
            if terms_of_service_text is not None:
                payload_safe["terms_of_service_text"] = terms_of_service_text
            logger.info(f"[DRY RUN] Would configure guest portal with payload: {payload_safe}")
            return {"dry_run": True, "payload": payload_safe}

        response = await client.put(
            f"/integration/v1/sites/{site_id}/guest-portal/config", json_data=payload
        )
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        # Audit the action
        await audit_action(
            settings,
            action_type="configure_guest_portal",
            resource_type="guest_portal_config",
            resource_id=site_id,
            site_id=site_id,
            details=payload,
        )

        return GuestPortalConfig(**data).model_dump()  # type: ignore[no-any-return]


# =============================================================================
# Hotspot Package Management
# =============================================================================


async def list_hotspot_packages(
    site_id: str,
    settings: Settings,
) -> list[dict]:
    """List all hotspot packages for a site.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        List of hotspot packages
    """
    async with UniFiClient(settings) as client:
        logger.info(f"Listing hotspot packages for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/integration/v1/sites/{site_id}/hotspot/packages")
        data = response if isinstance(response, list) else response.get("data", [])

        return [HotspotPackage(**package).model_dump() for package in data]


async def create_hotspot_package(
    site_id: str,
    name: str,
    duration_minutes: int,
    settings: Settings,
    download_limit_kbps: int | None = None,
    upload_limit_kbps: int | None = None,
    download_quota_mb: int | None = None,
    upload_quota_mb: int | None = None,
    price: float | None = None,
    currency: str = "USD",
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new hotspot package.

    Args:
        site_id: Site identifier
        name: Package name
        duration_minutes: Duration in minutes
        settings: Application settings
        download_limit_kbps: Download speed limit in kbps
        upload_limit_kbps: Upload speed limit in kbps
        download_quota_mb: Download quota in MB
        upload_quota_mb: Upload quota in MB
        price: Package price
        currency: Currency code
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created hotspot package
    """
    validate_confirmation(confirm, "create hotspot package", dry_run)

    async with UniFiClient(settings) as client:
        logger.info(f"Creating hotspot package '{name}' for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload
        payload: dict[str, Any] = {
            "name": name,
            "duration_minutes": duration_minutes,
            "currency": currency,
            "enabled": True,
        }

        if download_limit_kbps is not None:
            payload["download_limit_kbps"] = download_limit_kbps
        if upload_limit_kbps is not None:
            payload["upload_limit_kbps"] = upload_limit_kbps
        if download_quota_mb is not None:
            payload["download_quota_mb"] = download_quota_mb
        if upload_quota_mb is not None:
            payload["upload_quota_mb"] = upload_quota_mb
        if price is not None:
            payload["price"] = price

        if dry_run:
            logger.info(f"[DRY RUN] Would create hotspot package with payload: {payload}")
            return {"dry_run": True, "payload": payload}

        response = await client.post(
            f"/integration/v1/sites/{site_id}/hotspot/packages", json_data=payload
        )
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        # Audit the action
        await audit_action(
            settings,
            action_type="create_hotspot_package",
            resource_type="hotspot_package",
            resource_id=data.get("_id", "unknown"),
            site_id=site_id,
            details={"name": name, "duration_minutes": duration_minutes},
        )

        return HotspotPackage(**data).model_dump()  # type: ignore[no-any-return]


async def delete_hotspot_package(
    site_id: str,
    package_id: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Delete a hotspot package.

    Args:
        site_id: Site identifier
        package_id: Hotspot package ID
        settings: Application settings
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Deletion status
    """
    validate_confirmation(confirm, "delete hotspot package", dry_run)

    async with UniFiClient(settings) as client:
        logger.info(f"Deleting hotspot package {package_id} for site {site_id}")

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(f"[DRY RUN] Would delete hotspot package {package_id}")
            return {"dry_run": True, "package_id": package_id}

        await client.delete(f"/integration/v1/sites/{site_id}/hotspot/packages/{package_id}")

        # Audit the action
        await audit_action(
            settings,
            action_type="delete_hotspot_package",
            resource_type="hotspot_package",
            resource_id=package_id,
            site_id=site_id,
            details={},
        )

        return {"success": True, "message": f"Hotspot package {package_id} deleted successfully"}
