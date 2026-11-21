"""NetFlow/IPFIX export configuration tools for local UniFi consoles."""

from typing import Any

from ..api import UniFiClient
from ..config import APIType, Settings
from ..utils import (
    ResourceNotFoundError,
    ValidationError,
    coerce_bool,
    validate_confirmation,
    validate_site_id,
)
from ..utils.tool_kind import read_tool, write_tool

_NETFLOW_VERSIONS = {5, 9, 10}
_SAMPLING_MODES = {"off", "hash", "random", "deterministic"}


def _require_local(settings: Settings) -> None:
    """Reject modes without an observed private Network API route."""
    if settings.api_type != APIType.LOCAL:
        raise ValidationError(
            "NetFlow configuration requires direct local-console access; "
            "no Cloud Connector route is documented"
        )


def _records(response: Any) -> list[dict[str, Any]]:
    """Extract dictionary records from a legacy response envelope."""
    data = response.get("data", []) if isinstance(response, dict) else response
    if not isinstance(data, list):
        return []
    return [record for record in data if isinstance(record, dict)]


def _validate_updates(updates: dict[str, Any]) -> None:
    """Validate NetFlow fields against Network 10.6.111 UI constraints."""
    if not updates:
        raise ValidationError("No NetFlow updates provided")
    if "version" in updates and updates["version"] not in _NETFLOW_VERSIONS:
        raise ValidationError("version must be one of 5, 9, or 10")
    if "port" in updates and not 1024 <= updates["port"] <= 65535:
        raise ValidationError("port must be between 1024 and 65535")
    if "sampling_mode" in updates and updates["sampling_mode"] not in _SAMPLING_MODES:
        raise ValidationError("sampling_mode must be one of off, hash, random, or deterministic")
    if "sampling_rate" in updates and not 2 <= updates["sampling_rate"] <= 16383:
        raise ValidationError("sampling_rate must be between 2 and 16383")
    if "export_frequency" in updates and not 1 <= updates["export_frequency"] <= 60:
        raise ValidationError("export_frequency must be between 1 and 60")
    if "refresh_rate" in updates and not 1 <= updates["refresh_rate"] <= 2_147_483_647:
        raise ValidationError("refresh_rate must be between 1 and 2147483647")
    if "engine_id" in updates and not 1 <= updates["engine_id"] <= 2_147_483_647:
        raise ValidationError("engine_id must be between 1 and 2147483647")


@read_tool
async def get_netflow_export_config(site_id: str, settings: Settings) -> dict[str, Any]:
    """Read the site's NetFlow/IPFIX export configuration.

    This direct-console-only tool uses the private Network settings route
    observed on Network 10.6.111. The official Integration API doesn't expose
    NetFlow settings.

    Args:
        site_id: Network site short name, such as ``default``.
        settings: Application settings.

    Returns:
        The controller's NetFlow settings record.

    Raises:
        ValidationError: If cloud mode is selected.
        ResourceNotFoundError: If the controller returns no NetFlow record.
    """
    _require_local(settings)
    site_id = validate_site_id(site_id)
    endpoint = settings.get_site_api_path(site_id, "get/setting/netflow")
    async with UniFiClient(settings) as client:
        await client.authenticate()
        records = _records(await client.get(endpoint))
    if len(records) != 1:
        raise ResourceNotFoundError("netflow settings", site_id)
    return records[0]


@write_tool
async def update_netflow_export_config(
    site_id: str,
    settings: Settings,
    enabled: bool | None = None,
    network_ids: list[str] | None = None,
    server: str | None = None,
    port: int | None = None,
    version: int | None = None,
    auto_engine_id_enabled: bool | None = None,
    engine_id: int | None = None,
    export_frequency: int | None = None,
    refresh_rate: int | None = None,
    sampling_mode: str | None = None,
    sampling_rate: int | None = None,
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Update and read back the site's NetFlow/IPFIX export configuration.

    The write is a read-modify-write because the controller merges the payload
    into the stored document instead of replacing it, so a field cannot be
    cleared by leaving it out. Route, verb, merge behaviour and the validation
    ranges below were verified live against Network 10.6.111.

    Args:
        site_id: Network site short name, such as ``default``.
        settings: Application settings.
        enabled: Whether NetFlow export is enabled.
        network_ids: Controller network object IDs to export.
        server: Collector hostname or IP address.
        port: Collector port, from 1024 through 65535.
        version: NetFlow version 5, 9, or 10.
        auto_engine_id_enabled: Let the controller select the engine ID.
        engine_id: Explicit engine ID when automatic selection is disabled.
        export_frequency: Export frequency from 1 through 60.
        refresh_rate: Template refresh rate from 1 through 2147483647.
        sampling_mode: ``off``, ``hash``, ``random``, or ``deterministic``.
        sampling_rate: Sampling rate from 2 through 16383.
        confirm: Must be true to apply the configuration.
        dry_run: Return the proposed changes without making requests.

    Returns:
        Dry-run changes, or before/after records with read-back verification.

    Raises:
        ValidationError: If confirmation is missing, a value is invalid, or
            required enabled fields are absent.
        ResourceNotFoundError: If the controller returns no NetFlow record.
    """
    validate_confirmation(confirm, "update NetFlow export configuration", dry_run)
    _require_local(settings)
    site_id = validate_site_id(site_id)
    updates = {
        key: value
        for key, value in {
            "enabled": enabled,
            "network_ids": network_ids,
            "server": server,
            "port": port,
            "version": version,
            "auto_engine_id_enabled": auto_engine_id_enabled,
            "engine_id": engine_id,
            "export_frequency": export_frequency,
            "refresh_rate": refresh_rate,
            "sampling_mode": sampling_mode,
            "sampling_rate": sampling_rate,
        }.items()
        if value is not None
    }
    _validate_updates(updates)
    if coerce_bool(dry_run):
        return {
            "dry_run": True,
            "operation": "update_netflow_export_config",
            "site_id": site_id,
            "changes": updates,
        }

    get_endpoint = settings.get_site_api_path(site_id, "get/setting/netflow")
    set_endpoint = settings.get_site_api_path(site_id, "set/setting/netflow")
    async with UniFiClient(settings) as client:
        await client.authenticate()
        before_records = _records(await client.get(get_endpoint))
        if len(before_records) != 1:
            raise ResourceNotFoundError("netflow settings", site_id)
        before = before_records[0]
        payload = {**before, **updates, "key": "netflow"}
        if payload.get("enabled"):
            if not str(payload.get("server") or "").strip():
                raise ValidationError("server is required when NetFlow is enabled")
            if not payload.get("network_ids"):
                raise ValidationError("network_ids must contain at least one network when enabled")
        if payload.get("version") == 5 and isinstance(payload.get("engine_id"), int):
            if payload["engine_id"] > 127:
                raise ValidationError("engine_id must be between 1 and 127 for NetFlow version 5")
        # The controller MERGES this payload into the stored document; it never
        # replaces it. A key left out is kept at its current value, so a field
        # cannot be cleared by omission (verified live on Network 10.6.111).
        # Hence the full read-modify-write above rather than a sparse patch.
        await client.post(set_endpoint, json_data=payload)
        after_records = _records(await client.get(get_endpoint))
    if len(after_records) != 1:
        raise ResourceNotFoundError("netflow settings", site_id)
    after = after_records[0]
    verified = all(after.get(key) == value for key, value in updates.items())
    return {
        "site_id": site_id,
        "changed_fields": sorted(updates),
        "before": before,
        "after": after,
        "verified": verified,
    }
