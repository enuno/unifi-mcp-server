"""Fleet-wide read tools (docs/FLEET_SCALING_PLAN.md §3.4, Phase 4).

``fleet_health``, ``fleet_sites`` and ``fleet_inventory`` answer from the
worker's snapshots in Postgres (``python -m src.worker``), so a question about
a thousand controllers costs one query and no controller calls. Each result
says how old its data is.

``fleet_fanout`` runs one read-tier tool live on many controllers: at most
``UNIFI_FLEET_FANOUT_CONCURRENCY`` at once, each with its own timeout, under
one overall deadline. Every controller gets its own entry, ``{"ok": true,
"data": ...}`` or ``{"ok": false, "error": ...}``, so one unreachable
controller never fails the whole call. Each per-controller call goes through
the normal tool pipeline, so the caller's role, module filters, controller
scope and the read cache apply exactly as if it had been made directly.

Every tool lists only controllers inside the caller's controller scope.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from fastmcp import FastMCP

from ..access import ROLES, Principal, request_principal
from ..config import Settings
from ..tool_registry import TOOL_TIERS, _make_tool_wrapper
from ..utils.exceptions import ValidationError
from ..utils.tool_kind import read_tool
from .db.snapshots import FleetStatus, SnapshotStore
from .registry import ControllerRegistry

#: Most devices one fleet_inventory call returns.
MAX_INVENTORY_LIMIT = 1000

#: A health check older than this many health intervals is reported as stale.
STALE_INTERVALS = 3

#: Device model substring that flags a site as USG-gated (DEVELOPMENT_PLAN.md
#: §4 Phase 8, Fix 6 / N6). The last USG firmware release is 10.6; UniFi OS 6
#: / Network 11 requires a UniFi OS console or gateway, so a controller with
#: at least one USG on its device inventory cannot run Network 11 as-is.
#: Covers every USG variant (USG, USG-PRO-4, USG-3P, ...); no other UniFi
#: model name contains this substring.
USG_MODEL_SUBSTRING = "USG"

#: Human-readable reason attached to a USG-gated controller's platform_compat
#: field, matching the wording in DEVELOPMENT_PLAN.md §2.4 and §4 Phase 8.
USG_GATED_REASON = (
    "USG-gated: at least one USG gateway was seen in this controller's device "
    "inventory. UniFi Network 11 / UniFi OS 6 removed USG support (10.6 is the "
    "last USG release) — this controller cannot run Network 11 until the "
    "gateway is replaced. Not a confirmed break for every call; it means the "
    "site has no Network 11 target at all."
)

#: Longest error message kept per controller in fleet_fanout results.
_ERROR_LENGTH = 500


def _caller(settings: Settings) -> Principal:
    role = getattr(settings, "stdio_role", None)
    return request_principal(role if role in ROLES else "fleet-admin")


def _age(when: datetime | None, now: datetime) -> float | None:
    return None if when is None else round((now - when).total_seconds(), 1)


def version_key(version: str) -> tuple[int, ...]:
    """Order firmware versions numerically: ``4.0.10`` sorts after ``4.0.9``.

    Trailing zero parts are dropped, so ``8.0`` and ``8.0.0`` compare equal.
    """
    parts = [int(part) for part in re.findall(r"\d+", version)]
    while parts and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _matches(labels: Mapping[str, str], selector: Mapping[str, str] | None) -> bool:
    return all(labels.get(key) == value for key, value in (selector or {}).items())


async def _in_scope(
    registry: ControllerRegistry,
    caller: Principal,
    controllers: Sequence[str] | None,
    labels: Mapping[str, str] | None,
) -> list[str]:
    """Names of the registered controllers this call covers, sorted.

    Raises:
        ValidationError: If ``controllers`` names one that is unknown or out of scope
    """
    visible = {
        p.name: p
        for p in await registry.list_controllers()
        if caller.allows_controller(p.labels) and _matches(p.labels, labels)
    }
    if controllers is None:
        return sorted(visible)
    unknown = sorted(set(controllers) - set(visible))
    if unknown:
        raise ValidationError(
            f"Unknown controllers (or outside this caller's scope): {', '.join(unknown)}"
        )
    return sorted(set(controllers))


def build_snapshot_tools(
    registry: ControllerRegistry, snapshots: SnapshotStore, config: Settings
) -> list[Any]:
    """Return the snapshot-backed fleet tools bound to ``registry`` and ``snapshots``."""
    stale_after = STALE_INTERVALS * config.fleet_worker_health_seconds

    def _status_view(
        status: FleetStatus, now: datetime, usg_gated: frozenset[str]
    ) -> dict[str, Any]:
        health = status.health
        age = _age(health.checked_at, now)
        view = {
            "name": status.name,
            "api_type": status.api_type,
            "labels": status.labels,
            "health": health.health or "unknown",
            "detail": health.detail,
            "checked_seconds_ago": age,
            "stale": age is None or age > stale_after,
            "last_seen_seconds_ago": _age(health.last_seen_at, now),
            "capabilities": health.capabilities,
        }
        if status.name in usg_gated:
            view["platform_compat"] = {
                "network_11_capable": False,
                "reason": USG_GATED_REASON,
            }
        return view

    @read_tool
    async def fleet_health(
        health: str | None = None,
        labels: dict[str, str] | None = None,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Health of every controller, as last checked by the fleet worker.

        Answers from the worker's snapshot (no controller is contacted). An
        entry is ``stale`` when its last check is more than three health
        intervals old or the worker has never checked it (``unknown``).

        A controller with a USG gateway anywhere in its synced device
        inventory carries ``platform_compat.network_11_capable: false`` — USG
        support ends at Network 10.6, so the site has no Network 11 target at
        all (DEVELOPMENT_PLAN.md §4 Phase 8, Fix 6). Cloud controllers are
        never flagged this way: the worker does not inventory them. There is
        no API signal that distinguishes a classic, self-hosted Network
        Application Server from a UniFi OS console, so that platform break
        cannot be auto-detected here; tag those controllers with a label
        (e.g. ``deployment=classic-server``) and use the ``labels`` filter to
        track them instead.

        Args:
            health: Only controllers in this state: ok, degraded, down or unknown
            labels: Only controllers carrying all of these labels
            settings: Injected by the server

        Returns:
            Per-controller health, capabilities (Network version), platform
            compatibility (when USG-gated) and ages in seconds, plus a count
            per state
        """
        if health is not None and health not in ("ok", "degraded", "down", "unknown"):
            raise ValidationError("health must be one of: ok, degraded, down, unknown")
        names = await _in_scope(registry, _caller(settings or config), None, labels)
        now = datetime.now(UTC)
        usg_gated = frozenset(
            d.controller for d in await snapshots.fleet_devices(names, model=USG_MODEL_SUBSTRING)
        )
        entries = [_status_view(s, now, usg_gated) for s in await snapshots.fleet_status(names)]
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry["health"]] = counts.get(entry["health"], 0) + 1
        if health is not None:
            entries = [e for e in entries if e["health"] == health]
        return {"controllers": entries, "counts": counts, "total": len(names)}

    @read_tool
    async def fleet_sites(
        controllers: list[str] | None = None,
        labels: dict[str, str] | None = None,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Sites of every controller, as last synced by the fleet worker.

        Args:
            controllers: Only these controllers
            labels: Only controllers carrying all of these labels
            settings: Injected by the server

        Returns:
            Sites (controller, site UUID, short name, display name, age in seconds)
        """
        caller = _caller(settings or config)
        names = await _in_scope(registry, caller, controllers, labels)
        now = datetime.now(UTC)
        sites = await snapshots.fleet_sites(names)
        return {
            "sites": [
                {
                    "controller": s.controller,
                    "site_id": s.site.site_uuid,
                    "short_name": s.site.short_name,
                    "name": s.site.display_name,
                    "synced_seconds_ago": _age(s.synced_at, now),
                }
                for s in sites
            ],
            "count": len(sites),
        }

    @read_tool
    async def fleet_inventory(
        model: str | None = None,
        firmware_below: str | None = None,
        state: str | None = None,
        controllers: list[str] | None = None,
        labels: dict[str, str] | None = None,
        limit: int = 200,
        offset: int = 0,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Devices across the fleet, as last synced by the fleet worker.

        For questions like "which gateways run firmware older than 4.1" over
        many controllers without contacting any of them. Local controllers
        only: the worker does not inventory cloud controllers.

        Args:
            model: Only models containing this text (case-insensitive), e.g. UDM
            firmware_below: Only firmware older than this version, e.g. 4.1.0
                (compared numerically; devices without a version are left out)
            state: Only devices in this state, e.g. ONLINE or OFFLINE
            controllers: Only these controllers
            labels: Only controllers carrying all of these labels
            limit: Most devices to return (max 1000)
            offset: Devices to skip, for paging
            settings: Injected by the server

        Returns:
            Matching devices (controller, site, id, MAC, name, model, firmware,
            state, age in seconds), the total match count and per-model counts
        """
        if not 1 <= limit <= MAX_INVENTORY_LIMIT:
            raise ValidationError(f"limit must be between 1 and {MAX_INVENTORY_LIMIT}")
        if offset < 0:
            raise ValidationError("offset must not be negative")
        below = version_key(firmware_below) if firmware_below else None
        if firmware_below and not below:
            raise ValidationError("firmware_below must contain a version number, e.g. 4.1.0")
        caller = _caller(settings or config)
        names = await _in_scope(registry, caller, controllers, labels)
        devices = await snapshots.fleet_devices(names, model=model, state=state)
        if below is not None:
            devices = [
                d for d in devices if d.device.version and version_key(d.device.version) < below
            ]
        by_model: dict[str, int] = {}
        for d in devices:
            key = d.device.model or "unknown"
            by_model[key] = by_model.get(key, 0) + 1
        now = datetime.now(UTC)
        page = devices[offset : offset + limit]
        return {
            "devices": [
                {
                    "controller": d.controller,
                    "site_id": d.site_uuid,
                    "id": d.device.device_id,
                    "mac": d.device.mac,
                    "name": d.device.name,
                    "model": d.device.model,
                    "firmware_version": d.device.version,
                    "state": d.device.state,
                    "synced_seconds_ago": _age(d.synced_at, now),
                }
                for d in page
            ],
            "total": len(devices),
            "offset": offset,
            "by_model": dict(sorted(by_model.items())),
        }

    @read_tool
    async def fleet_compare_versions(
        model: str | None = None,
        controllers: list[str] | None = None,
        labels: dict[str, str] | None = None,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Compare firmware versions of devices across controllers.

        Answers from the worker's device-inventory snapshot, so no controller is
        contacted. Use it to find controllers running older firmware or mixed
        versions for a given model.

        Args:
            model: Only compare this model (case-insensitive substring match)
            controllers: Only these controllers (default: every controller in scope)
            labels: Only controllers carrying all of these labels
            settings: Injected by the server

        Returns:
            Per-model version summary, per-controller counts and versions, the
            newest version seen, and which controllers are behind it
        """
        caller = _caller(settings or config)
        names = await _in_scope(registry, caller, controllers, labels)
        devices = await snapshots.fleet_devices(names, model=model)
        now = datetime.now(UTC)
        stale_seconds = config.fleet_worker_health_seconds * STALE_INTERVALS

        by_model: dict[str, dict[str, Any]] = {}
        for d in devices:
            key = d.device.model or "unknown"
            entry = by_model.setdefault(
                key,
                {
                    "versions": set(),
                    "controllers": {},
                    "total": 0,
                    "oldest_synced_at": None,
                },
            )
            version = d.device.version
            if version:
                entry["versions"].add(version)
            entry["total"] += 1
            if entry["oldest_synced_at"] is None or (
                d.synced_at and d.synced_at < entry["oldest_synced_at"]
            ):
                entry["oldest_synced_at"] = d.synced_at
            ctrl = entry["controllers"].setdefault(
                d.controller,
                {"count": 0, "versions": set(), "oldest_synced_at": None},
            )
            ctrl["count"] += 1
            if version:
                ctrl["versions"].add(version)
            if ctrl["oldest_synced_at"] is None or (
                d.synced_at and d.synced_at < ctrl["oldest_synced_at"]
            ):
                ctrl["oldest_synced_at"] = d.synced_at

        models_out: dict[str, Any] = {}
        for key, entry in sorted(by_model.items()):
            versions = sorted(entry["versions"], key=version_key, reverse=True)
            newest = versions[0] if versions else None
            controllers_out: dict[str, Any] = {}
            for name in names:
                ctrl = entry["controllers"].get(name, {"count": 0, "versions": set()})
                ctrl_versions = sorted(ctrl["versions"], key=version_key, reverse=True)
                behind = False
                if newest and ctrl_versions:
                    behind = version_key(ctrl_versions[0]) < version_key(newest)
                ctrl_age = _age(ctrl.get("oldest_synced_at"), now)
                controllers_out[name] = {
                    "count": ctrl["count"],
                    "versions": ctrl_versions,
                    "behind": behind,
                    "synced_seconds_ago": ctrl_age,
                    "stale": (ctrl_age is not None and ctrl_age > stale_seconds),
                }
            model_age = _age(entry["oldest_synced_at"], now)
            models_out[key] = {
                "versions": versions,
                "newest": newest,
                "controllers": controllers_out,
                "data_as_of_seconds_ago": model_age,
                "stale": (model_age is not None and model_age > stale_seconds),
            }

        return {
            "models": models_out,
            "controllers_compared": names,
            "total_devices": len(devices),
        }

    @read_tool
    async def fleet_compare_sites(
        controllers: list[str] | None = None,
        labels: dict[str, str] | None = None,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Compare site names across controllers.

        Answers from the worker's site snapshot, so no controller is contacted.
        Shows sites that exist on every controller and sites that exist only on
        some.

        Args:
            controllers: Only these controllers (default: every controller in scope)
            labels: Only controllers carrying all of these labels
            settings: Injected by the server

        Returns:
            Common site short names, per-controller unique sites, the full
            per-controller site lists, and the controllers compared
        """
        caller = _caller(settings or config)
        names = await _in_scope(registry, caller, controllers, labels)
        sites = await snapshots.fleet_sites(names)
        now = datetime.now(UTC)
        stale_seconds = config.fleet_worker_health_seconds * STALE_INTERVALS

        by_controller: dict[str, list[dict[str, Any]]] = {name: [] for name in names}
        by_short: dict[str, set[str]] = {}
        by_uuid: dict[str, set[str]] = {}
        oldest_by_controller: dict[str, datetime | None] = dict.fromkeys(names)
        oldest_overall: datetime | None = None
        for s in sites:
            site_age = _age(s.synced_at, now)
            by_controller[s.controller].append(
                {
                    "site_id": s.site.site_uuid,
                    "short_name": s.site.short_name,
                    "name": s.site.display_name,
                    "synced_seconds_ago": site_age,
                    "stale": (site_age is not None and site_age > stale_seconds),
                }
            )
            if s.site.short_name:
                by_short.setdefault(s.site.short_name, set()).add(s.controller)
            by_uuid.setdefault(s.site.site_uuid, set()).add(s.controller)
            controller_oldest = oldest_by_controller[s.controller]
            if controller_oldest is None or s.synced_at < controller_oldest:
                oldest_by_controller[s.controller] = s.synced_at
            if oldest_overall is None or s.synced_at < oldest_overall:
                oldest_overall = s.synced_at

        common_short = sorted(name for name, ctrls in by_short.items() if ctrls == set(names))
        common_uuid = sorted(uuid for uuid, ctrls in by_uuid.items() if ctrls == set(names))

        unique_short: dict[str, list[str]] = {}
        for name in names:
            unique_short[name] = sorted(
                s["short_name"]
                for s in by_controller[name]
                if s["short_name"] and s["short_name"] not in common_short
            )

        controller_sync_age = {name: _age(oldest_by_controller[name], now) for name in names}
        overall_age = _age(oldest_overall, now)

        return {
            "common_sites": common_short,
            "common_site_ids": common_uuid,
            "unique_sites": unique_short,
            "by_controller": {
                name: sorted(entries, key=lambda x: x["short_name"] or "")
                for name, entries in by_controller.items()
            },
            "controller_sync_age": controller_sync_age,
            "data_as_of_seconds_ago": overall_age,
            "stale": (overall_age is not None and overall_age > stale_seconds),
            "controllers_compared": names,
            "total_sites": len(sites),
        }

    return [fleet_health, fleet_sites, fleet_inventory, fleet_compare_versions, fleet_compare_sites]


def build_fanout_tool(mcp: FastMCP, registry: ControllerRegistry, config: Settings) -> Any:
    """Return ``fleet_fanout``, which runs read tools registered on ``mcp``."""

    async def run_one(tool: Any, arguments: dict[str, Any], name: str, timeout: float) -> Any:
        result = await asyncio.wait_for(tool.run({**arguments, "controller": name}), timeout)
        structured = result.structured_content
        if structured is None:
            return "\n".join(getattr(block, "text", "") for block in result.content)
        if (tool.output_schema or {}).get("x-fastmcp-wrap-result"):
            return structured.get("result")
        return structured

    @read_tool
    async def fleet_fanout(
        tool: str,
        arguments: dict[str, Any] | None = None,
        controllers: list[str] | None = None,
        labels: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
        deadline_seconds: float | None = None,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Run one read-only tool on many controllers at once, live.

        Prefer fleet_health, fleet_sites and fleet_inventory, which answer from
        snapshots without contacting controllers; use this for anything they
        do not cover or when the data must be current. Only read-tier tools
        can be fanned out. Each controller's result is separate: one failing
        or slow controller does not fail the call.

        Args:
            tool: Name of a read tool, e.g. list_devices or get_network_health
            arguments: The tool's arguments, except ``controller``
            controllers: Run on these controllers (default: every controller
                in scope, filtered by ``labels``)
            labels: Only controllers carrying all of these labels
            timeout_seconds: Per-controller timeout (default
                UNIFI_FLEET_FANOUT_TIMEOUT_SECONDS)
            deadline_seconds: Overall deadline; controllers not done by then
                are reported as timed out (default UNIFI_FLEET_FANOUT_DEADLINE_SECONDS)
            settings: Injected by the server

        Returns:
            ``results`` keyed by controller, each ``{"ok": true, "data": ...}``
            or ``{"ok": false, "error": ...}``, with success and failure counts
            and the elapsed time
        """
        config_ = settings or config
        arguments = dict(arguments or {})
        if "controller" in arguments:
            raise ValidationError(
                "Pass target controllers in `controllers`, not in `arguments.controller`"
            )
        if tool.startswith("fleet_") or TOOL_TIERS.get(tool) != "read":
            raise ValidationError(
                f"'{tool}' cannot be fanned out: only read-tier controller tools can"
            )
        target = await mcp.get_tool(tool)
        if target is None or "controller" not in (target.parameters or {}).get("properties", {}):
            raise ValidationError(f"'{tool}' is not a controller tool on this server")
        timeout = (
            config_.fleet_fanout_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        deadline = (
            config_.fleet_fanout_deadline_seconds if deadline_seconds is None else deadline_seconds
        )
        if timeout <= 0 or deadline <= 0:
            raise ValidationError("timeout_seconds and deadline_seconds must be positive")

        names = await _in_scope(registry, _caller(config_), controllers, labels)
        semaphore = asyncio.Semaphore(config_.fleet_fanout_concurrency)
        results: dict[str, dict[str, Any]] = {}

        async def one(name: str) -> None:
            async with semaphore:
                try:
                    data = await run_one(target, arguments, name, timeout)
                except TimeoutError:
                    results[name] = {"ok": False, "error": f"timed out after {timeout:g}s"}
                except Exception as e:
                    message = str(e) or type(e).__name__
                    results[name] = {"ok": False, "error": message[:_ERROR_LENGTH]}
                else:
                    results[name] = {"ok": True, "data": data}

        started = time.monotonic()
        tasks = [asyncio.create_task(one(name)) for name in names]
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=deadline)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        for name in names:
            results.setdefault(
                name, {"ok": False, "error": f"not finished within the {deadline:g}s deadline"}
            )
        succeeded = sum(1 for r in results.values() if r["ok"])
        return {
            "tool": tool,
            "results": {name: results[name] for name in names},
            "succeeded": succeeded,
            "failed": len(names) - succeeded,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }

    return fleet_fanout


def register_fleet_read_tools(
    mcp: FastMCP,
    registry: ControllerRegistry,
    settings: Settings,
    snapshots: SnapshotStore | None,
) -> list[str]:
    """Register ``fleet_fanout`` and, with a snapshot store, the snapshot tools.

    Args:
        mcp: The FastMCP server instance
        registry: The controllers the tools cover
        settings: Process-wide settings
        snapshots: The worker's snapshots (None without DATABASE_URL)

    Returns:
        The registered tool names
    """
    tools = [build_fanout_tool(mcp, registry, settings)]
    if snapshots is not None:
        tools += build_snapshot_tools(registry, snapshots, settings)
    names = []
    for tool in tools:
        mcp.tool()(_make_tool_wrapper(tool, settings, routed=False, tier="read", module="fleet"))
        TOOL_TIERS[tool.__name__] = "read"
        names.append(tool.__name__)
    return names
