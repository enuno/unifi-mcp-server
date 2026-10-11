"""The worker's per-controller jobs (docs/FLEET_SCALING_PLAN.md §3.5).

* :func:`check_health` probes the controller (the same authentication probe
  tools use), reads its Network application version on local controllers and
  records ``ok``; failures record ``degraded`` until ``down_after`` in a row,
  then ``down``.
* :func:`sync_controller` replaces the controller's ``sites`` snapshot and, on
  local controllers, each site's ``device_inventory``. The cloud APIs list
  devices per host rather than per site, so cloud controllers get sites only.

Jobs talk to controllers through :class:`~src.api.client.UniFiClient`, so the
worker gets the same retries, circuit breaker and (with Redis) the controller
rate limit shared with the API replicas.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..api.client import UniFiClient
from ..api.pool import connection_key
from ..config import APIType, Settings
from ..fleet.bus import HealthBus
from ..fleet.db.snapshots import DeviceRecord, Health, SiteRecord, SnapshotStore
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: Page size for the integration API's site and device listings.
PAGE_SIZE = 200


@dataclass(frozen=True)
class SyncResult:
    """What one sync stored."""

    sites: int
    devices: int


def _describe(error: BaseException) -> str:
    """Name a failure without echoing request details."""
    message = str(error).strip()
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


def _entries(response: Any) -> list[Any]:
    """The entries of a listing, bare or in a ``data`` envelope.

    Raises:
        ValueError: For any other shape (e.g. ``{}`` from an empty 2xx body),
            so a sync fails and keeps the last snapshot instead of replacing
            it with nothing
    """
    if isinstance(response, list):
        return response
    if isinstance(response, Mapping) and isinstance(response.get("data"), list):
        return list(response["data"])
    raise ValueError(f"unexpected listing shape: {type(response).__name__}")


async def _paged(client: UniFiClient, endpoint: str) -> list[Any]:
    """Every entry of an integration API listing, page by page."""
    entries: list[Any] = []
    offset = 0
    while True:
        batch = _entries(await client.get(endpoint, params={"offset": offset, "limit": PAGE_SIZE}))
        entries.extend(batch)
        if len(batch) < PAGE_SIZE:
            return entries
        offset += len(batch)


async def check_health(
    name: str,
    settings: Settings,
    snapshots: SnapshotStore,
    *,
    failures: dict[str, int],
    down_after: int,
    bus: HealthBus | None = None,
) -> Health:
    """Probe one controller and record the outcome.

    Args:
        name: The controller
        settings: Its settings (from the registry)
        snapshots: Where the outcome is recorded
        failures: Consecutive failures per controller, updated in place
        down_after: Failures in a row that mark the controller ``down``
        bus: Announces a successful check, so replicas half-open the
            controller's circuit breaker (none without Redis)

    Returns:
        The recorded health
    """
    started = time.monotonic()
    try:
        async with UniFiClient(settings) as client:
            await client.authenticate()
            capabilities: dict[str, Any] = {"api_type": settings.api_type.value}
            if settings.api_type == APIType.LOCAL:
                capabilities.update(await _versions(client, settings))
    except Exception as e:
        failures[name] = failures.get(name, 0) + 1
        health: Health = "down" if failures[name] >= down_after else "degraded"
        logger.warning(
            "Health check of %s failed (%d in a row): %s", name, failures[name], _describe(e)
        )
        await snapshots.record_health(name, health, detail=_describe(e))
        return health
    failures.pop(name, None)
    await snapshots.record_health(name, "ok", capabilities=capabilities)
    if bus is not None:
        await bus.publish_ok(connection_key(settings), time.monotonic() - started)
    return "ok"


async def _versions(client: UniFiClient, settings: Settings) -> dict[str, Any]:
    """The Network application version, or nothing if the controller does not say."""
    try:
        response = await client.get(settings.get_integration_path("info"))
    except Exception as e:  # an old controller without /info is still healthy
        logger.debug("No application info from %s: %s", settings.local_host, _describe(e))
        return {}
    data = response.get("data", response) if isinstance(response, Mapping) else response
    if isinstance(data, list):
        data = data[0] if data else {}
    version = data.get("applicationVersion") if isinstance(data, Mapping) else None
    return {"network_version": version} if isinstance(version, str) else {}


def _site_record(entry: Any) -> SiteRecord | None:
    """Read a site from the integration API (local) or Site Manager (cloud) shape."""
    if not isinstance(entry, Mapping):
        return None
    site_uuid = entry.get("id") or entry.get("siteId") or entry.get("_id")
    if not isinstance(site_uuid, str) or not site_uuid:
        return None
    raw_meta = entry.get("meta")
    meta: Mapping[str, Any] = raw_meta if isinstance(raw_meta, Mapping) else {}
    short_name = entry.get("internalReference") or meta.get("name")
    display_name = entry.get("name") or meta.get("desc")
    return SiteRecord(
        site_uuid=site_uuid,
        short_name=short_name if isinstance(short_name, str) else None,
        display_name=display_name if isinstance(display_name, str) else None,
    )


def _device_record(entry: Any) -> DeviceRecord | None:
    """Read a device from the integration API shape."""
    if not isinstance(entry, Mapping):
        return None
    device_id = entry.get("id") or entry.get("_id")
    if not isinstance(device_id, str) or not device_id:
        return None

    def text(*keys: str) -> str | None:
        for key in keys:
            value = entry.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    return DeviceRecord(
        device_id=device_id,
        payload=dict(entry),
        mac=text("macAddress", "mac"),
        name=text("name"),
        model=text("model"),
        version=text("firmwareVersion", "version"),
        state=text("state"),
    )


async def sync_controller(name: str, settings: Settings, snapshots: SnapshotStore) -> SyncResult:
    """Replace one controller's site snapshot and (local only) its device inventory.

    Raises:
        Exception: Whatever reaching the controller raised; the previous
            snapshot is left as it was
    """
    async with UniFiClient(settings) as client:
        await client.authenticate()
        if settings.api_type == APIType.LOCAL:
            raw_sites = await _paged(client, settings.get_integration_path("sites"))
        elif settings.api_type == APIType.CLOUD_V1:
            raw_sites = _entries(await client.get("/v1/sites"))
        else:
            raw_sites = _entries(await client.get("/ea/sites"))
        sites = [site for entry in raw_sites if (site := _site_record(entry)) is not None]

        inventories: dict[str, list[DeviceRecord]] = {}
        if settings.api_type == APIType.LOCAL:
            for site in sites:
                raw = await _paged(
                    client, settings.get_integration_path(f"sites/{site.site_uuid}/devices")
                )
                inventories[site.site_uuid] = [
                    device for entry in raw if (device := _device_record(entry)) is not None
                ]

    stored_sites = await snapshots.replace_sites(name, sites)
    devices = 0
    for site_uuid, records in inventories.items():
        devices += await snapshots.replace_inventory(name, site_uuid, records)
    return SyncResult(sites=stored_sites, devices=devices)
