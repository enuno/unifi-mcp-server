"""Cloud Connector proxy tools for remote UniFi controller access.

The UniFi Cloud Connector allows reaching into a locally-managed UniFi
controller through Ubiquiti's cloud relay without requiring a public IP or VPN.

Endpoint pattern:
  Network:  /v1/connector/{console_id}/proxy/network/{path}
  Protect:  /v1/connector/{console_id}/proxy/protect/{path}

The ``console_id`` is the host identifier returned by ``list_hosts``.
These tools require ``UNIFI_SITE_MANAGER_ENABLED=true``.

Mutating tools (POST, PUT, PATCH, DELETE) require ``confirm=True`` per the
project's safety convention for any operation that can change controller state.
"""

from __future__ import annotations

from typing import Any

from ..api.site_manager_client import SiteManagerClient
from ..config import Settings
from ..utils import ValidationError, get_logger, validate_confirmation


def _validate_connector_params(console_id: str, path: str) -> str:
    """Validate console_id and path, return normalised path (no leading slash)."""
    if not console_id or not console_id.strip():
        raise ValidationError("console_id must not be empty")
    if not path or not path.strip():
        raise ValidationError("path must not be empty")
    return path.lstrip("/")


# ---------------------------------------------------------------------------
# Network proxy tools
# ---------------------------------------------------------------------------


async def connector_network_get(
    console_id: str,
    path: str,
    settings: Settings,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Proxy a GET request to the Network Application via Cloud Connector.

    Forwards the request to
    ``https://api.ui.com/v1/connector/{console_id}/proxy/network/{path}``
    and returns the raw response.

    Args:
        console_id: UniFi console/host identifier (from list_hosts)
        path: Network API sub-path, e.g. ``api/s/default/stat/device``
        settings: Application settings (UNIFI_SITE_MANAGER_ENABLED required)
        params: Optional query parameters

    Returns:
        Raw response from the proxied Network API endpoint

    Raises:
        ValidationError: If console_id or path is empty
        ValueError: If Site Manager API is not enabled
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    path = _validate_connector_params(console_id, path)
    logger = get_logger(__name__, settings.log_level)

    async with SiteManagerClient(settings) as client:
        endpoint = f"connector/{console_id}/proxy/network/{path}"
        logger.info(f"Connector network GET: {endpoint}")
        return await client.get(endpoint, params=params)


async def connector_network_post(
    console_id: str,
    path: str,
    settings: Settings,
    body: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Proxy a POST request to the Network Application via Cloud Connector.

    Args:
        console_id: UniFi console/host identifier (from list_hosts)
        path: Network API sub-path, e.g. ``api/s/default/rest/wlanconf``
        settings: Application settings
        body: Optional request body to forward
        confirm: Must be True to execute (mutating operation)
        dry_run: If True, preview the request without sending it

    Returns:
        Raw response or dry-run preview

    Raises:
        ValidationError: If console_id/path is empty or confirm not provided
        ValueError: If Site Manager API is not enabled
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    validate_confirmation(confirm, "connector_network_post", dry_run)
    path = _validate_connector_params(console_id, path)
    logger = get_logger(__name__, settings.log_level)
    endpoint = f"connector/{console_id}/proxy/network/{path}"

    if dry_run:
        return {"dry_run": True, "would_post_to": endpoint, "body": body}

    async with SiteManagerClient(settings) as client:
        logger.info(f"Connector network POST: {endpoint}")
        return await client.post(endpoint, json_data=body)


async def connector_network_put(
    console_id: str,
    path: str,
    settings: Settings,
    body: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Proxy a PUT request to the Network Application via Cloud Connector.

    Args:
        console_id: UniFi console/host identifier
        path: Network API sub-path
        settings: Application settings
        body: Optional request body
        confirm: Must be True to execute
        dry_run: Preview without sending

    Returns:
        Raw response or dry-run preview
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    validate_confirmation(confirm, "connector_network_put", dry_run)
    path = _validate_connector_params(console_id, path)
    logger = get_logger(__name__, settings.log_level)
    endpoint = f"connector/{console_id}/proxy/network/{path}"

    if dry_run:
        return {"dry_run": True, "would_put_to": endpoint, "body": body}

    async with SiteManagerClient(settings) as client:
        logger.info(f"Connector network PUT: {endpoint}")
        return await client.put(endpoint, json_data=body)


async def connector_network_patch(
    console_id: str,
    path: str,
    settings: Settings,
    body: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Proxy a PATCH request to the Network Application via Cloud Connector.

    Args:
        console_id: UniFi console/host identifier
        path: Network API sub-path
        settings: Application settings
        body: Optional request body
        confirm: Must be True to execute
        dry_run: Preview without sending

    Returns:
        Raw response or dry-run preview
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    validate_confirmation(confirm, "connector_network_patch", dry_run)
    path = _validate_connector_params(console_id, path)
    logger = get_logger(__name__, settings.log_level)
    endpoint = f"connector/{console_id}/proxy/network/{path}"

    if dry_run:
        return {"dry_run": True, "would_patch_to": endpoint, "body": body}

    async with SiteManagerClient(settings) as client:
        logger.info(f"Connector network PATCH: {endpoint}")
        return await client.patch(endpoint, json_data=body)


async def connector_network_delete(
    console_id: str,
    path: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Proxy a DELETE request to the Network Application via Cloud Connector.

    Args:
        console_id: UniFi console/host identifier
        path: Network API sub-path
        settings: Application settings
        confirm: Must be True to execute
        dry_run: Preview without sending

    Returns:
        Raw response or dry-run preview
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    validate_confirmation(confirm, "connector_network_delete", dry_run)
    path = _validate_connector_params(console_id, path)
    logger = get_logger(__name__, settings.log_level)
    endpoint = f"connector/{console_id}/proxy/network/{path}"

    if dry_run:
        return {"dry_run": True, "would_delete": endpoint}

    async with SiteManagerClient(settings) as client:
        logger.info(f"Connector network DELETE: {endpoint}")
        return await client.delete(endpoint)


# ---------------------------------------------------------------------------
# Protect proxy tools
# ---------------------------------------------------------------------------


async def connector_protect_get(
    console_id: str,
    path: str,
    settings: Settings,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Proxy a GET request to the Protect Application via Cloud Connector.

    Forwards the request to
    ``https://api.ui.com/v1/connector/{console_id}/proxy/protect/{path}``
    and returns the raw response.

    Args:
        console_id: UniFi console/host identifier (from list_hosts)
        path: Protect API sub-path, e.g. ``v1/cameras``
        settings: Application settings (UNIFI_SITE_MANAGER_ENABLED required)
        params: Optional query parameters

    Returns:
        Raw response from the proxied Protect API endpoint

    Raises:
        ValidationError: If console_id or path is empty
        ValueError: If Site Manager API is not enabled
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    path = _validate_connector_params(console_id, path)
    logger = get_logger(__name__, settings.log_level)

    async with SiteManagerClient(settings) as client:
        endpoint = f"connector/{console_id}/proxy/protect/{path}"
        logger.info(f"Connector protect GET: {endpoint}")
        return await client.get(endpoint, params=params)


async def connector_protect_post(
    console_id: str,
    path: str,
    settings: Settings,
    body: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Proxy a POST request to the Protect Application via Cloud Connector.

    Args:
        console_id: UniFi console/host identifier
        path: Protect API sub-path, e.g. ``v1/cameras/{id}/snapshot``
        settings: Application settings
        body: Optional request body
        confirm: Must be True to execute
        dry_run: Preview without sending

    Returns:
        Raw response or dry-run preview
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    validate_confirmation(confirm, "connector_protect_post", dry_run)
    path = _validate_connector_params(console_id, path)
    logger = get_logger(__name__, settings.log_level)
    endpoint = f"connector/{console_id}/proxy/protect/{path}"

    if dry_run:
        return {"dry_run": True, "would_post_to": endpoint, "body": body}

    async with SiteManagerClient(settings) as client:
        logger.info(f"Connector protect POST: {endpoint}")
        return await client.post(endpoint, json_data=body)


async def connector_protect_put(
    console_id: str,
    path: str,
    settings: Settings,
    body: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Proxy a PUT request to the Protect Application via Cloud Connector.

    Args:
        console_id: UniFi console/host identifier
        path: Protect API sub-path
        settings: Application settings
        body: Optional request body
        confirm: Must be True to execute
        dry_run: Preview without sending

    Returns:
        Raw response or dry-run preview
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    validate_confirmation(confirm, "connector_protect_put", dry_run)
    path = _validate_connector_params(console_id, path)
    logger = get_logger(__name__, settings.log_level)
    endpoint = f"connector/{console_id}/proxy/protect/{path}"

    if dry_run:
        return {"dry_run": True, "would_put_to": endpoint, "body": body}

    async with SiteManagerClient(settings) as client:
        logger.info(f"Connector protect PUT: {endpoint}")
        return await client.put(endpoint, json_data=body)


async def connector_protect_patch(
    console_id: str,
    path: str,
    settings: Settings,
    body: dict[str, Any] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Proxy a PATCH request to the Protect Application via Cloud Connector.

    Args:
        console_id: UniFi console/host identifier
        path: Protect API sub-path
        settings: Application settings
        body: Optional request body
        confirm: Must be True to execute
        dry_run: Preview without sending

    Returns:
        Raw response or dry-run preview
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    validate_confirmation(confirm, "connector_protect_patch", dry_run)
    path = _validate_connector_params(console_id, path)
    logger = get_logger(__name__, settings.log_level)
    endpoint = f"connector/{console_id}/proxy/protect/{path}"

    if dry_run:
        return {"dry_run": True, "would_patch_to": endpoint, "body": body}

    async with SiteManagerClient(settings) as client:
        logger.info(f"Connector protect PATCH: {endpoint}")
        return await client.patch(endpoint, json_data=body)


async def connector_protect_delete(
    console_id: str,
    path: str,
    settings: Settings,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Proxy a DELETE request to the Protect Application via Cloud Connector.

    Args:
        console_id: UniFi console/host identifier
        path: Protect API sub-path
        settings: Application settings
        confirm: Must be True to execute
        dry_run: Preview without sending

    Returns:
        Raw response or dry-run preview
    """
    if not settings.site_manager_enabled:
        raise ValueError("Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true")

    validate_confirmation(confirm, "connector_protect_delete", dry_run)
    path = _validate_connector_params(console_id, path)
    logger = get_logger(__name__, settings.log_level)
    endpoint = f"connector/{console_id}/proxy/protect/{path}"

    if dry_run:
        return {"dry_run": True, "would_delete": endpoint}

    async with SiteManagerClient(settings) as client:
        logger.info(f"Connector protect DELETE: {endpoint}")
        return await client.delete(endpoint)
