"""MCP tools for UniFi Network Integration API v1 endpoints.

These tools expose the official integration API (``/proxy/network/integration/v1/``)
which uses X-API-KEY authentication and returns UUID-based identifiers rather than
the legacy MongoDB ObjectIds used by the internal classic API.
"""

from __future__ import annotations

from typing import Any

from ..api import UniFiClient
from ..config import Settings
from ..models import (
    DPICategory,
    IntegrationClient,
    IntegrationDevice,
    IntegrationDeviceTag,
    IntegrationDNSPolicy,
    IntegrationNetwork,
    IntegrationSite,
    IntegrationVPNServer,
    IntegrationWAN,
    IntegrationWifiBroadcast,
)
from ..utils import get_logger, sanitize_log_message, validate_limit_offset, validate_site_id

# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------


async def list_integration_sites(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List sites via the integration API.

    Returns UUID-based site identifiers suitable for use with other
    integration API tools in this module.

    Args:
        settings: Application settings
        limit: Maximum number of sites to return (1-1000)
        offset: Number of sites to skip

    Returns:
        Paginated list of integration API sites
    """
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_integration_path("sites"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    sites = [IntegrationSite.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(sanitize_log_message(f"Listed {len(sites)} integration API sites"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": sites,
    }


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------


async def list_integration_devices(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List adopted devices via the integration API.

    Args:
        site_id: Site identifier (UUID or internal reference)
        settings: Application settings
        limit: Maximum number of devices to return (1-1000)
        offset: Number of devices to skip

    Returns:
        Paginated list of integration API devices
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/devices"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    devices = [IntegrationDevice.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(
        sanitize_log_message(f"Listed {len(devices)} integration API devices for site {site_id}")
    )

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": devices,
    }


async def get_integration_device(
    site_id: str,
    device_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get a single adopted device via the integration API.

    Args:
        site_id: Site identifier
        device_id: Device UUID
        settings: Application settings

    Returns:
        Device details
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/devices/{device_id}")
        )

    device_data = response.get("data", response) if isinstance(response, dict) else response
    device = IntegrationDevice.model_validate(device_data)
    logger.info(sanitize_log_message(f"Retrieved integration API device {device_id}"))
    return device.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


async def list_integration_clients(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List connected clients via the integration API.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of clients to return (1-1000)
        offset: Number of clients to skip

    Returns:
        Paginated list of integration API clients
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/clients"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    clients = [IntegrationClient.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(
        sanitize_log_message(f"Listed {len(clients)} integration API clients for site {site_id}")
    )

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": clients,
    }


async def get_integration_client(
    site_id: str,
    client_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get a single connected client via the integration API.

    Args:
        site_id: Site identifier
        client_id: Client UUID
        settings: Application settings

    Returns:
        Client details
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/clients/{client_id}")
        )

    client_data = response.get("data", response) if isinstance(response, dict) else response
    client_obj = IntegrationClient.model_validate(client_data)
    logger.info(sanitize_log_message(f"Retrieved integration API client {client_id}"))
    return client_obj.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# Networks
# ---------------------------------------------------------------------------


async def list_integration_networks(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List networks via the integration API.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of networks to return (1-1000)
        offset: Number of networks to skip

    Returns:
        Paginated list of integration API networks
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/networks"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    networks = [IntegrationNetwork.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(
        sanitize_log_message(f"Listed {len(networks)} integration API networks for site {site_id}")
    )

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": networks,
    }


# ---------------------------------------------------------------------------
# WiFi Broadcasts
# ---------------------------------------------------------------------------


async def list_integration_wifi_broadcasts(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List WiFi broadcasts (SSIDs) via the integration API.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of broadcasts to return (1-1000)
        offset: Number of broadcasts to skip

    Returns:
        Paginated list of WiFi broadcasts
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/wifi/broadcasts"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    broadcasts = [
        IntegrationWifiBroadcast.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    logger.info(
        sanitize_log_message(
            f"Listed {len(broadcasts)} integration API WiFi broadcasts for site {site_id}"
        )
    )

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": broadcasts,
    }


async def get_integration_wifi_broadcast(
    site_id: str,
    broadcast_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get a single WiFi broadcast via the integration API.

    Args:
        site_id: Site identifier
        broadcast_id: WiFi broadcast UUID
        settings: Application settings

    Returns:
        WiFi broadcast details
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(
                f"sites/{resolved_site_id}/wifi/broadcasts/{broadcast_id}"
            )
        )

    broadcast_data = response.get("data", response) if isinstance(response, dict) else response
    broadcast = IntegrationWifiBroadcast.model_validate(broadcast_data)
    logger.info(sanitize_log_message(f"Retrieved integration API WiFi broadcast {broadcast_id}"))
    return broadcast.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# DNS Policies
# ---------------------------------------------------------------------------


async def list_integration_dns_policies(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List DNS policies via the integration API.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of policies to return (1-1000)
        offset: Number of policies to skip

    Returns:
        Paginated list of DNS policies
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/dns/policies"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    policies = [
        IntegrationDNSPolicy.model_validate(item).model_dump(by_alias=True) for item in data
    ]
    logger.info(
        sanitize_log_message(
            f"Listed {len(policies)} integration API DNS policies for site {site_id}"
        )
    )

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": policies,
    }


async def get_integration_dns_policy(
    site_id: str,
    policy_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Get a single DNS policy via the integration API.

    Args:
        site_id: Site identifier
        policy_id: DNS policy UUID
        settings: Application settings

    Returns:
        DNS policy details
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/dns/policies/{policy_id}")
        )

    policy_data = response.get("data", response) if isinstance(response, dict) else response
    policy = IntegrationDNSPolicy.model_validate(policy_data)
    logger.info(sanitize_log_message(f"Retrieved integration API DNS policy {policy_id}"))
    return policy.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# WANs
# ---------------------------------------------------------------------------


async def list_integration_wans(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List WAN connections via the integration API.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of WANs to return (1-1000)
        offset: Number of WANs to skip

    Returns:
        Paginated list of WAN connections
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/wans"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    wans = [IntegrationWAN.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(sanitize_log_message(f"Listed {len(wans)} integration API WANs for site {site_id}"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": wans,
    }


# ---------------------------------------------------------------------------
# VPN Servers
# ---------------------------------------------------------------------------


async def list_integration_vpn_servers(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List VPN servers via the integration API.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of servers to return (1-1000)
        offset: Number of servers to skip

    Returns:
        Paginated list of VPN servers
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/vpn/servers"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    servers = [IntegrationVPNServer.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(
        sanitize_log_message(
            f"Listed {len(servers)} integration API VPN servers for site {site_id}"
        )
    )

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": servers,
    }


# ---------------------------------------------------------------------------
# Device Tags
# ---------------------------------------------------------------------------


async def list_integration_device_tags(
    site_id: str,
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List device tags via the integration API.

    Args:
        site_id: Site identifier
        settings: Application settings
        limit: Maximum number of tags to return (1-1000)
        offset: Number of tags to skip

    Returns:
        Paginated list of device tags
    """
    logger = get_logger(__name__, settings.log_level)
    site_id = validate_site_id(site_id)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        resolved_site_id = await client.resolve_site_id(site_id)
        response = await client.get(
            settings.get_integration_path(f"sites/{resolved_site_id}/device-tags"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    tags = [IntegrationDeviceTag.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(
        sanitize_log_message(f"Listed {len(tags)} integration API device tags for site {site_id}")
    )

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": tags,
    }


# ---------------------------------------------------------------------------
# DPI Categories
# ---------------------------------------------------------------------------


async def list_dpi_application_categories(
    settings: Settings,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List DPI application categories via the integration API.

    This endpoint is global (not site-scoped) and returns the canonical
    list of application categories used by DPI and traffic-routing features.

    Args:
        settings: Application settings
        limit: Maximum number of categories to return (1-1000)
        offset: Number of categories to skip

    Returns:
        Paginated list of DPI categories
    """
    logger = get_logger(__name__, settings.log_level)
    final_limit, final_offset = validate_limit_offset(limit, offset)

    async with UniFiClient(settings) as client:
        await client.authenticate()
        response = await client.get(
            settings.get_integration_path("dpi/categories"),
            params={"limit": final_limit, "offset": final_offset},
        )

    data = response.get("data", []) if isinstance(response, dict) else []
    total_count = response.get("totalCount", len(data)) if isinstance(response, dict) else len(data)
    count = response.get("count", len(data)) if isinstance(response, dict) else len(data)

    categories = [DPICategory.model_validate(item).model_dump(by_alias=True) for item in data]
    logger.info(sanitize_log_message(f"Listed {len(categories)} DPI application categories"))

    return {
        "offset": final_offset,
        "limit": final_limit,
        "count": count,
        "totalCount": total_count,
        "data": categories,
    }
