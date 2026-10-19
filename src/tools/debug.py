"""Debug passthrough tool for querying arbitrary UniFi API endpoints.

This module is not in any tool list. ``src/main.py`` registers it only when
the ``DEBUG`` environment variable is truthy, and it goes through
``register_module_tools`` like every other module, so it is removed under
``UNIFI_READ_ONLY``, forced into preview under ``UNIFI_DRY_RUN``, audited, and
limited to callers holding the ``destructive`` tier.
"""

from __future__ import annotations

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..utils import ValidationError, coerce_bool, get_logger, validate_confirmation
from ..utils.tool_kind import write_tool

#: HTTP methods the passthrough supports.
_METHODS = ("GET", "DELETE")


def _require_controller_path(endpoint: str) -> None:
    """Refuse anything but a path relative to the controller's base URL.

    ``UniFiClient`` sends an endpoint that does not start with ``/`` as a
    complete URL, with its ``X-API-KEY`` default header attached. An absolute
    or scheme-relative endpoint would hand the controller credential to
    another host, so only a single-slash root-relative path is accepted.

    Args:
        endpoint: Endpoint the caller asked for

    Raises:
        ValidationError: If the endpoint is empty or is not a controller path
    """
    if not endpoint or not endpoint.strip():
        raise ValidationError("endpoint must not be empty")
    if (
        not endpoint.startswith("/")
        or endpoint.startswith("//")
        or "\\" in endpoint
        or any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in endpoint)
    ):
        raise ValidationError(
            "endpoint must be a controller-relative path starting with a single '/' "
            "(e.g. /proxy/network/api/s/default/stat/device); URLs are not accepted"
        )


@write_tool
async def debug_api_request(
    endpoint: str,
    settings: Settings,
    method: str = "GET",
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Debug tool to query arbitrary UniFi API endpoints.

    Only registered when the ``DEBUG`` environment variable is set, and never
    in read-only mode. Needs the ``destructive`` tier for every method.

    Args:
        endpoint: Controller-relative API path starting with ``/`` (e.g.,
            /proxy/network/api/s/default/rest/networkconf). Absolute and
            scheme-relative URLs are refused.
        settings: Application settings
        method: HTTP method, ``GET`` or ``DELETE``
        confirm: Must be true to send a ``DELETE`` (required unless dry_run)
        dry_run: Preview the request without sending it

    Returns:
        Raw JSON response from the API, or a dry-run preview

    Raises:
        ValidationError: If the endpoint is empty, the method is unsupported,
            or a ``DELETE`` is not confirmed
    """
    verb = method.strip().upper()
    if verb not in _METHODS:
        raise ValidationError(
            f"Method {method} is not supported by debug_api_request; use GET or DELETE"
        )
    _require_controller_path(endpoint)
    if verb == "DELETE":
        validate_confirmation(confirm, "debug_api_request DELETE", dry_run)

    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "debug_api_request",
            "method": verb,
            "endpoint": endpoint,
        }

    logger = get_logger(__name__, settings.log_level)
    logger.warning(f"debug_api_request {verb} {endpoint}")
    async with UniFiClient(settings) as client:
        await client.authenticate()
        if verb == "DELETE":
            return await client.delete(endpoint)
        return await client.get(endpoint)
