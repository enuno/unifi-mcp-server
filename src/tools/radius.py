"""RADIUS profile and guest portal management tools."""

from typing import Any

from ..api.client import UniFiClient
from ..config import Settings
from ..models.radius import RADIUSAccount, RADIUSProfile
from ..utils import (
    APIError,
    ValidationError,
    audit_action,
    get_logger,
    sanitize_log_message,
    validate_confirmation,
)

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
        logger.info(sanitize_log_message(f"Listing RADIUS profiles for site {site_id}"))

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
        logger.info(sanitize_log_message(f"Getting RADIUS profile {profile_id} for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/radiusprofile/{profile_id}")
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        return RADIUSProfile(**data).model_dump()


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
        logger.info(sanitize_log_message(f"Creating RADIUS profile '{name}' for site {site_id}"))

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
            payload_safe: dict[str, Any] = {
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
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would create RADIUS profile '{name}' for site {site_id}"
                )
            )
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

        return RADIUSProfile(**data).model_dump()


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
        logger.info(
            sanitize_log_message(f"Updating RADIUS profile {profile_id} for site {site_id}")
        )

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
            payload_safe: dict[str, Any] = {}
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
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would update RADIUS profile {profile_id} for site {site_id}"
                )
            )
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

        return RADIUSProfile(**data).model_dump()


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
        logger.info(
            sanitize_log_message(f"Deleting RADIUS profile {profile_id} for site {site_id}")
        )

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(sanitize_log_message(f"[DRY RUN] Would delete RADIUS profile {profile_id}"))
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
        logger.info(sanitize_log_message(f"Listing RADIUS accounts for site {site_id}"))

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
        logger.info(sanitize_log_message(f"Creating RADIUS account for site {site_id}"))

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
            logger.info(
                sanitize_log_message(f"[DRY RUN] Would create RADIUS account for site {site_id}")
            )
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

        return RADIUSAccount(**data).model_dump()


async def get_radius_account(
    site_id: str,
    account_id: str,
    settings: Settings,
) -> dict:
    """Get details for a specific RADIUS account.

    Args:
        site_id: Site identifier
        account_id: RADIUS account ID
        settings: Application settings

    Returns:
        RADIUS account details with password redacted
    """
    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Getting RADIUS account {account_id} for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/account/{account_id}")
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        if not data:
            return {}

        if "x_password" in data:
            data["x_password"] = "***REDACTED***"

        return RADIUSAccount(**data).model_dump()


async def update_radius_account(
    site_id: str,
    account_id: str,
    settings: Settings,
    username: str | None = None,
    password: str | None = None,
    vlan_id: int | None = None,
    tunnel_type: int | None = None,
    tunnel_medium_type: int | None = None,
    enabled: bool | None = None,
    note: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing RADIUS account.

    Args:
        site_id: Site identifier
        account_id: RADIUS account ID
        settings: Application settings
        username: New username (maps to 'name' in API)
        password: New password (maps to 'x_password' in API)
        vlan_id: Assigned VLAN ID (maps to 'vlan' in API)
        tunnel_type: RADIUS tunnel type (13=VLAN)
        tunnel_medium_type: RADIUS tunnel medium type (6=802)
        enabled: Account enabled status
        note: Admin notes
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Updated RADIUS account with password redacted
    """
    validate_confirmation(confirm, "update RADIUS account", dry_run)

    payload: dict[str, Any] = {}

    if username is not None:
        payload["name"] = username
    if password is not None:
        payload["x_password"] = password
    if vlan_id is not None:
        payload["vlan"] = vlan_id
    if tunnel_type is not None:
        payload["tunnel_type"] = tunnel_type
    if tunnel_medium_type is not None:
        payload["tunnel_medium_type"] = tunnel_medium_type
    if enabled is not None:
        payload["enabled"] = enabled
    if note is not None:
        payload["note"] = note

    if not payload and not dry_run:
        raise ValueError("At least one field must be provided to update.")

    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(f"Updating RADIUS account {account_id} for site {site_id}")
        )

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            payload_safe = payload.copy()
            if "x_password" in payload_safe:
                payload_safe["x_password"] = "***REDACTED***"
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would update RADIUS account {account_id} for site {site_id}"
                )
            )
            return {"dry_run": True, "account_id": account_id, "payload": payload_safe}

        response = await client.put(
            f"/ea/sites/{site_id}/rest/account/{account_id}", json_data=payload
        )
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        await audit_action(
            settings,
            action_type="update_radius_account",
            resource_type="radius_account",
            resource_id=account_id,
            site_id=site_id,
            details={k: ("***REDACTED***" if k == "x_password" else v) for k, v in payload.items()},
        )

        if "x_password" in data:
            data["x_password"] = "***REDACTED***"

        return RADIUSAccount(**data).model_dump()


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
        logger.info(
            sanitize_log_message(f"Deleting RADIUS account {account_id} for site {site_id}")
        )

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(sanitize_log_message(f"[DRY RUN] Would delete RADIUS account {account_id}"))
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


def _first_item(response: Any) -> dict[str, Any]:
    """First object from a controller response, ``{}`` when nothing came back.

    ``response.get("data", [{}])[0]`` does not survive an accepted-but-unechoed
    write: the default only applies when the key is absent, not when the list
    is empty.
    """
    if isinstance(response, list):
        items: Any = response
    elif isinstance(response, dict):
        items = response.get("data", [])
    else:
        # None or a scalar reply must not raise mid-parse.
        return {}
    if not isinstance(items, list) or not items:
        return {}
    first = items[0]
    return first if isinstance(first, dict) else {}


def _translate_guest_access(section: dict[str, Any]) -> dict[str, Any]:
    """Map the ``guest_access`` settings section to this tool's public shape.

    ``auth`` alone does not identify the method: ``"hotspot"`` covers
    password, voucher and RADIUS, distinguished by their ``*_enabled`` flags.

    A section reporting ``auth="hotspot"`` with none of those flags set is an
    ambiguous controller state; it is reported faithfully as
    ``auth_method="hotspot"`` — an output-only value that
    :func:`configure_guest_portal` deliberately rejects as input. Remapping it
    to a configurable value would misstate what the controller holds; the raw
    section accompanies the translation as ground truth.
    """
    auth = section.get("auth", "none")
    if auth == "hotspot":
        if section.get("password_enabled"):
            auth_method = "password"
        elif section.get("voucher_enabled"):
            auth_method = "voucher"
        elif section.get("radius_enabled"):
            auth_method = "radius"
        else:
            auth_method = "hotspot"
    elif auth == "custom":
        auth_method = "external"
    else:
        auth_method = "none"

    return {
        "id": section.get("_id"),
        "portal_enabled": section.get("portal_enabled", False),
        "auth_method": auth_method,
        "session_timeout": section.get("expire"),
        "redirect_enabled": section.get("redirect_enabled", False),
        "redirect_url": section.get("redirect_url"),
    }


def _scrub_secrets(section: dict[str, Any]) -> dict[str, Any]:
    """Drop ``x_``-prefixed fields (controller convention for secrets)."""
    return {k: v for k, v in section.items() if not k.startswith("x_")}


async def get_guest_portal_config(
    site_id: str,
    settings: Settings,
) -> dict:
    """Get guest portal (hotspot) configuration for a site.

    Reads the legacy ``setting/guest_access`` section, which is where this
    configuration actually lives. An earlier version called
    ``/integration/v1/sites/{site}/guest-portal/config``, an endpoint no
    known Network version serves — it returned 404 everywhere.

    Args:
        site_id: Site identifier
        settings: Application settings

    Returns:
        Translated portal settings plus the raw section (secrets removed)
        under ``"raw"``, since field names in this section vary across
        Network versions and callers may need ground truth.
    """
    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Getting guest portal config for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/get/setting/guest_access")
        section = _first_item(response)
        if not section:
            raise APIError("guest_access settings section not found in controller response")

        return {**_translate_guest_access(section), "raw": _scrub_secrets(section)}


VALID_PORTAL_AUTH_METHODS = ["none", "password", "voucher", "radius", "external"]

# The Hotspot portal's auth is stored as auth="hotspot" plus per-method
# *_enabled flags, so selecting one method must clear the other two or the
# controller keeps whichever was set before.
_HOTSPOT_METHOD_FLAGS = {
    "password": "password_enabled",  # pragma: allowlist secret
    "voucher": "voucher_enabled",
    "radius": "radius_enabled",
}


async def configure_guest_portal(
    site_id: str,
    settings: Settings,
    portal_enabled: bool | None = None,
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
    """Configure guest portal (hotspot) settings.

    Writes the legacy ``setting/guest_access`` section — see
    :func:`get_guest_portal_config` for why the integration endpoint this
    tool previously used could never work.

    ``portal_enabled=False`` turns the captive portal off entirely. Networks
    with purpose ``guest`` keep their guest policies (client isolation from
    private subnets); clients just stop being intercepted for authorization.

    Args:
        site_id: Site identifier
        settings: Application settings
        portal_enabled: Enable/disable the captive portal itself
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
        Updated portal settings; ``skipped_fields`` lists requested fields
        this controller version has no key for (see below).
    """
    validate_confirmation(confirm, "configure guest portal", dry_run)

    if auth_method is not None and auth_method not in VALID_PORTAL_AUTH_METHODS:
        raise ValidationError(
            f"Invalid auth_method '{auth_method}'. "
            f"Must be one of: {', '.join(VALID_PORTAL_AUTH_METHODS)}"
        )
    if password is not None and auth_method is not None and auth_method != "password":
        raise ValidationError(
            f"password only applies when auth_method='password', not '{auth_method}'"
        )

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Configuring guest portal for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        current_response = await client.get(f"/ea/sites/{site_id}/get/setting/guest_access")
        current = _first_item(current_response)
        settings_id = current.get("_id")
        if not settings_id:
            raise APIError("guest_access settings section not found in controller response")

        # Switching to password auth needs a password from somewhere: either
        # this call or one already stored on the section. Without one the
        # controller would be left demanding a password nobody set.
        if auth_method == "password" and password is None and not current.get("x_password"):
            raise ValidationError(
                "auth_method='password' requires a password: none was provided "
                "and the section has none stored"
            )
        # Likewise a password sent while the section stays on a non-password
        # method would be written and never used; require the method change.
        if password is not None and auth_method is None:
            translated = _translate_guest_access(current)
            if translated.get("auth_method") != "password":
                raise ValidationError(
                    "password was provided but the portal's auth method is "
                    f"'{translated.get('auth_method')}'; pass "
                    "auth_method='password' to switch"
                )

        payload: dict[str, Any] = {}

        if portal_enabled is not None:
            payload["portal_enabled"] = portal_enabled
        if auth_method is not None:
            if auth_method in _HOTSPOT_METHOD_FLAGS:
                payload["auth"] = "hotspot"
                for method, flag in _HOTSPOT_METHOD_FLAGS.items():
                    payload[flag] = method == auth_method
            elif auth_method == "external":
                payload["auth"] = "custom"
            else:
                payload["auth"] = "none"
        if password is not None:
            payload["x_password"] = password
        if session_timeout is not None:
            payload["expire"] = session_timeout
        if redirect_enabled is not None:
            payload["redirect_enabled"] = redirect_enabled
        if redirect_url is not None:
            payload["redirect_url"] = redirect_url

        # Portal-customization key names (title, ToS) vary across Network
        # versions. Only write keys this controller already reports, and name
        # what was skipped rather than inventing schema the controller would
        # silently drop or reject.
        skipped_fields: list[str] = []
        versioned = {
            "portal_customized_title": portal_title,
            "portal_customized_tos_enabled": terms_of_service_enabled,
            "portal_customized_tos": terms_of_service_text,
        }
        for key, value in versioned.items():
            if value is None:
                continue
            if key in current:
                payload[key] = value
            else:
                skipped_fields.append(key)

        payload_safe = {
            k: ("***REDACTED***" if k.startswith("x_") else v) for k, v in payload.items()
        }

        if dry_run:
            logger.info(
                sanitize_log_message(f"[DRY RUN] Would configure guest portal for site {site_id}")
            )
            return {
                "dry_run": True,
                "settings_id": settings_id,
                "payload": payload_safe,
                "skipped_fields": skipped_fields,
            }

        response = await client.put(
            f"/ea/sites/{site_id}/set/setting/guest_access/{settings_id}",
            json_data=payload,
        )
        updated = _first_item(response)
        if not updated:
            # Not every version echoes the updated section on PUT; re-read so
            # the caller sees stored state, not their own input reflected back.
            updated = _first_item(await client.get(f"/ea/sites/{site_id}/get/setting/guest_access"))

        # Audit the action
        await audit_action(
            settings,
            action_type="configure_guest_portal",
            resource_type="guest_portal_config",
            resource_id=settings_id,
            site_id=site_id,
            details=payload_safe,
        )

        return {**_translate_guest_access(updated), "skipped_fields": skipped_fields}


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
        logger.info(sanitize_log_message(f"Listing hotspot packages for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/hotspotpackage")
        data = response if isinstance(response, list) else response.get("data", [])

        return [dict(package) for package in data]


async def create_hotspot_package(
    site_id: str,
    name: str,
    duration_minutes: int,
    settings: Settings,
    price: float | None = None,
    currency: str = "USD",
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Create a new hotspot package.

    Duration is hours-granular on the classic surface, so
    ``duration_minutes`` is rounded up to whole hours. A controller with no
    hotspot payment gateway configured refuses package creation with
    ``api.err.Invalid``; with ``amount`` left at 0 it instead reports the
    misleading ``api.err.InvalidHotspotPackageDuration``.

    The earlier bandwidth/quota parameters are gone: the classic validator
    never acknowledged them, and carrying parameters the controller ignores
    misrepresents what the tool can do.

    Args:
        site_id: Site identifier
        name: Package name
        duration_minutes: Duration in minutes (stored as whole hours)
        settings: Application settings
        price: Package price (``amount``)
        currency: Currency code, sent alongside ``price``
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Created hotspot package
    """
    validate_confirmation(confirm, "create hotspot package", dry_run)

    if duration_minutes < 1:
        # Without this, 0 or a negative value would silently round up to a
        # 1-hour paid package instead of being rejected.
        raise ValidationError(f"duration_minutes must be at least 1, got {duration_minutes}")

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Creating hotspot package '{name}' for site {site_id}"))

        if not client.is_authenticated:
            await client.authenticate()

        # Build request payload from the fields the classic validator is
        # known to read (it echoes amount, hours and trial_duration_minutes
        # on rejection). Duration is hours-granular on this surface.
        payload: dict[str, Any] = {
            "name": name,
            "hours": -(-duration_minutes // 60),
        }

        if price is not None:
            payload["amount"] = price
            payload["currency"] = currency

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would create hotspot package '{name}' for site {site_id}"
                )
            )
            return {"dry_run": True, "payload": payload}

        response = await client.post(f"/ea/sites/{site_id}/rest/hotspotpackage", json_data=payload)
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

        return dict(data)


async def get_hotspot_package(
    site_id: str,
    package_id: str,
    settings: Settings,
) -> dict:
    """Get details for a specific hotspot package.

    Args:
        site_id: Site identifier
        package_id: Hotspot package ID
        settings: Application settings

    Returns:
        Hotspot package details
    """
    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(f"Getting hotspot package {package_id} for site {site_id}")
        )

        if not client.is_authenticated:
            await client.authenticate()

        response = await client.get(f"/ea/sites/{site_id}/rest/hotspotpackage/{package_id}")
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        if not data:
            return {}

        return dict(data)


async def update_hotspot_package(
    site_id: str,
    package_id: str,
    settings: Settings,
    name: str | None = None,
    duration_minutes: int | None = None,
    price: float | None = None,
    currency: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict:
    """Update an existing hotspot package.

    Same field surface as :func:`create_hotspot_package`; see there for why
    the bandwidth/quota/enabled parameters are gone and how duration rounds.

    Args:
        site_id: Site identifier
        package_id: Hotspot package ID
        settings: Application settings
        name: Package name
        duration_minutes: Duration in minutes (stored as whole hours)
        price: Package price (``amount``)
        currency: Currency code
        confirm: Confirmation flag (required)
        dry_run: If True, validate but don't execute

    Returns:
        Updated hotspot package
    """
    validate_confirmation(confirm, "update hotspot package", dry_run)

    if duration_minutes is not None and duration_minutes < 1:
        raise ValidationError(f"duration_minutes must be at least 1, got {duration_minutes}")
    if currency is not None and price is None:
        # The classic validator reads currency only alongside amount; a
        # currency-only update would send a request that changes nothing.
        raise ValidationError("currency can only be set together with price")

    payload: dict[str, Any] = {}

    if name is not None:
        payload["name"] = name
    if duration_minutes is not None:
        payload["hours"] = -(-duration_minutes // 60)
    if price is not None:
        payload["amount"] = price
    if currency is not None:
        payload["currency"] = currency

    if not payload and not dry_run:
        raise ValueError("At least one field must be provided to update.")

    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(f"Updating hotspot package {package_id} for site {site_id}")
        )

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(
                sanitize_log_message(
                    f"[DRY RUN] Would update hotspot package {package_id} for site {site_id}"
                )
            )
            return {"dry_run": True, "package_id": package_id, "payload": payload}

        response = await client.put(
            f"/ea/sites/{site_id}/rest/hotspotpackage/{package_id}", json_data=payload
        )
        data = response if isinstance(response, list) else response.get("data", response)
        if isinstance(data, list):
            data = data[0] if data else {}

        await audit_action(
            settings,
            action_type="update_hotspot_package",
            resource_type="hotspot_package",
            resource_id=package_id,
            site_id=site_id,
            details=payload,
        )

        return dict(data)


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
        logger.info(
            sanitize_log_message(f"Deleting hotspot package {package_id} for site {site_id}")
        )

        if not client.is_authenticated:
            await client.authenticate()

        if dry_run:
            logger.info(
                sanitize_log_message(f"[DRY RUN] Would delete hotspot package {package_id}")
            )
            return {"dry_run": True, "package_id": package_id}

        await client.delete(f"/ea/sites/{site_id}/rest/hotspotpackage/{package_id}")

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
