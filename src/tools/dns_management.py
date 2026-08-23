"""DNS management tools (WAN DNS, DNS filtering).

Manages WAN upstream DNS servers via ``/rest/networkconf/{wan_id}`` and
per-network DNS filtering (CyberSecure DNS-level) via the ``[ips]``
settings endpoint. Both are on the legacy V1 internal API, local-only.

**DoT (DNS-over-TLS)** configuration is NOT exposed via REST API on
current UDM firmware (10.2.x). The ``rest/setting/connectivity`` endpoint
has no DoT-related fields. DoT must be configured in the UI for now.
"""

from typing import Any

from ..api.client import UniFiClient
from ..config import APIType, Settings
from ..utils import APIError, get_logger, log_audit, sanitize_log_message, validate_site_id
from ..utils.validators import coerce_bool

logger = get_logger(__name__)


def _ensure_local_api(settings: Settings) -> None:
    if settings.api_type != APIType.LOCAL:
        raise NotImplementedError("DNS management tools require UNIFI_API_TYPE='local'.")


def _unwrap(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [i for i in response if isinstance(i, dict)]
    if isinstance(response, dict):
        inner = response.get("data")
        if isinstance(inner, list):
            return [i for i in inner if isinstance(i, dict)]
        if isinstance(inner, dict):
            return [inner]
    return []


# --------------------------------------------------------------------------- #
# WAN DNS                                                                     #
# --------------------------------------------------------------------------- #


async def list_wan_dns(
    site_id: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    """List WAN connections with their DNS settings.

    Returns each WAN interface's name, ID, current DNS servers, and
    dns_preference mode (``auto`` or ``manual``).
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Listing WAN DNS for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(f"/ea/sites/{site_id}/rest/networkconf")
        except APIError:
            logger.exception(sanitize_log_message(f"Failed to list networks for site {site_id}"))
            raise

        items = _unwrap(response)
        wans = [n for n in items if n.get("purpose") == "wan"]

        return [
            {
                "id": w.get("_id"),
                "name": w.get("name"),
                "wan_dns1": w.get("wan_dns1"),
                "wan_dns2": w.get("wan_dns2"),
                "wan_dns_preference": w.get("wan_dns_preference", "auto"),
                "wan_type": w.get("wan_type"),
                "wan_networkgroup": w.get("wan_networkgroup"),
            }
            for w in wans
        ]


async def update_wan_dns(
    wan_network_id: str,
    site_id: str,
    settings: Settings,
    dns1: str | None = None,
    dns2: str | None = None,
    dns_preference: str | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update DNS settings on a WAN interface.

    Args:
        wan_network_id: The WAN network's ``_id`` (from ``list_wan_dns``)
        site_id: Site identifier
        settings: Application settings (must be local)
        dns1: Primary DNS server IP (e.g. ``"172.64.36.1"``)
        dns2: Secondary DNS server IP
        dns_preference: ``"manual"`` to use dns1/dns2, ``"auto"`` for
            DHCP-provided DNS
        confirm: REQUIRED True
        dry_run: Preview without applying
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)

    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)
    if not dry_run_bool and not confirm_bool:
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    overrides: dict[str, Any] = {}
    if dns1 is not None:
        overrides["wan_dns1"] = dns1
    if dns2 is not None:
        overrides["wan_dns2"] = dns2
    if dns_preference is not None:
        if dns_preference not in ("auto", "manual"):
            raise ValueError("dns_preference must be 'auto' or 'manual'")
        overrides["wan_dns_preference"] = dns_preference

    # Auto-set to manual when specific DNS servers are provided
    if (dns1 is not None or dns2 is not None) and dns_preference is None:
        overrides["wan_dns_preference"] = "manual"

    if dry_run_bool:
        logger.info(sanitize_log_message(f"DRY RUN: Would update WAN DNS on {wan_network_id}"))
        return {"status": "dry_run", "wan_network_id": wan_network_id, "changes": overrides}

    async with UniFiClient(settings) as client:
        logger.info(
            sanitize_log_message(f"Updating WAN DNS on {wan_network_id} for site {site_id}")
        )
        if not client.is_authenticated:
            await client.authenticate()

        endpoint = f"/ea/sites/{site_id}/rest/networkconf/{wan_network_id}"

        try:
            response = await client.put(endpoint, json_data=overrides)
        except APIError:
            logger.exception(sanitize_log_message(f"Failed to update WAN DNS on {wan_network_id}"))
            raise

        items = _unwrap(response)
        data = items[0] if items else {}

        log_audit(
            operation="update_wan_dns",
            parameters={"site_id": site_id, "wan_network_id": wan_network_id, **overrides},
            result="success",
            site_id=site_id,
        )

        return {
            "id": data.get("_id"),
            "name": data.get("name"),
            "wan_dns1": data.get("wan_dns1"),
            "wan_dns2": data.get("wan_dns2"),
            "wan_dns_preference": data.get("wan_dns_preference"),
        }


# --------------------------------------------------------------------------- #
# DNS Filtering (CyberSecure DNS-level, per-network)                          #
# --------------------------------------------------------------------------- #


async def get_dns_filter_settings(
    site_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get DNS filtering settings (CyberSecure DNS-level).

    Returns the global ``dns_filtering`` toggle and the per-network
    ``dns_filters`` list from the ``[ips]`` settings.
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Getting DNS filter settings for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        try:
            response = await client.get(f"/ea/sites/{site_id}/get/setting/ips")
        except APIError:
            logger.exception(sanitize_log_message("Failed to get DNS filter settings"))
            raise

        items = _unwrap(response)
        if not items:
            return {"dns_filtering": False, "dns_filters": []}

        ips_settings = items[0]
        return {
            "id": ips_settings.get("_id"),
            "dns_filtering": ips_settings.get("dns_filtering", False),
            "dns_filters": ips_settings.get("dns_filters", []),
        }


async def update_dns_filter(
    site_id: str,
    settings: Settings,
    network_id: str | None = None,
    dns_filtering: bool | None = None,
    filter_level: str | None = None,
    blocked_sites: list[str] | None = None,
    allowed_sites: list[str] | None = None,
    blocked_tld: list[str] | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update DNS filtering settings.

    Can toggle the global ``dns_filtering`` switch and/or update a specific
    network's DNS filter configuration.

    Args:
        site_id: Site identifier
        settings: Application settings (must be local)
        network_id: Target a specific network's DNS filter entry. Required
            when updating per-network settings (filter_level, blocked_sites,
            etc.).
        dns_filtering: Toggle the global DNS filtering feature on/off
        filter_level: DNS filter level for the specified network. Common
            values: ``"none"``, ``"family"``, ``"work"``, ``"custom"``
        blocked_sites: Replace the blocked-sites list for this network
        allowed_sites: Replace the allowed-sites list
        blocked_tld: Replace the blocked TLD list
        confirm: REQUIRED True
        dry_run: Preview without applying
    """
    site_id = validate_site_id(site_id)
    _ensure_local_api(settings)

    confirm_bool = coerce_bool(confirm)
    dry_run_bool = coerce_bool(dry_run)
    if not dry_run_bool and not confirm_bool:
        raise ValueError(
            "This operation requires confirm=True to execute. "
            "Use dry_run=True to preview changes first."
        )

    async with UniFiClient(settings) as client:
        logger.info(sanitize_log_message(f"Updating DNS filter settings for site {site_id}"))
        if not client.is_authenticated:
            await client.authenticate()

        # Fetch current IPS settings
        try:
            response = await client.get(f"/ea/sites/{site_id}/get/setting/ips")
        except APIError:
            logger.exception(sanitize_log_message("Failed to get current DNS filter settings"))
            raise

        items = _unwrap(response)
        if not items:
            raise APIError("IPS settings not found")
        current = items[0]
        settings_id = current.get("_id")

        # Build the update
        update_payload: dict[str, Any] = {}

        if dns_filtering is not None:
            update_payload["dns_filtering"] = dns_filtering

        if network_id is not None and (
            filter_level is not None
            or blocked_sites is not None
            or allowed_sites is not None
            or blocked_tld is not None
        ):
            # Update a specific network's entry in dns_filters
            dns_filters = list(current.get("dns_filters", []))
            target_entry = None
            for entry in dns_filters:
                if isinstance(entry, dict) and entry.get("network_id") == network_id:
                    target_entry = entry
                    break

            if target_entry is None:
                # Create a new entry for this network
                target_entry = {
                    "network_id": network_id,
                    "filter": "none",
                    "blocked_tld": [],
                    "blocked_sites": [],
                    "allowed_sites": [],
                    "name": "",
                    "description": "",
                    "version": "v4",
                }
                dns_filters.append(target_entry)

            if filter_level is not None:
                target_entry["filter"] = filter_level
            if blocked_sites is not None:
                target_entry["blocked_sites"] = list(blocked_sites)
            if allowed_sites is not None:
                target_entry["allowed_sites"] = list(allowed_sites)
            if blocked_tld is not None:
                target_entry["blocked_tld"] = list(blocked_tld)

            update_payload["dns_filters"] = dns_filters

        if dry_run_bool:
            logger.info(sanitize_log_message("DRY RUN: Would update DNS filter settings"))
            return {
                "status": "dry_run",
                "settings_id": settings_id,
                "changes": update_payload,
            }

        try:
            put_response = await client.put(
                f"/ea/sites/{site_id}/set/setting/ips/{settings_id}",
                json_data=update_payload,
            )
        except APIError:
            logger.exception(sanitize_log_message("Failed to update DNS filter settings"))
            raise

        put_items = _unwrap(put_response)
        result = put_items[0] if put_items else {}

        log_audit(
            operation="update_dns_filter",
            parameters={"site_id": site_id, **update_payload},
            result="success",
            site_id=site_id,
        )

        return {
            "id": result.get("_id"),
            "dns_filtering": result.get("dns_filtering"),
            "dns_filters": result.get("dns_filters", []),
        }
