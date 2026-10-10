"""Tool registration helper for UniFi MCP Server.

Provides auto-registration of tool module functions onto a FastMCP instance,
eliminating the per-tool boilerplate in main.py.

Each tool module exposes plain async functions that accept ``settings`` as a
positional or keyword argument.  ``register_module_tools`` inspects a module,
finds all public async callables, and registers a ``functools.partial`` wrapper
(with ``settings`` pre-bound) as an MCP tool, preserving the public signature
visible to MCP clients (i.e. the signature *without* the ``settings`` param).
"""

from __future__ import annotations

import functools
import inspect
import time
import types
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_context
from pydantic import Field

from .access import current_principal, request_principal
from .config import Settings
from .fleet import DEFAULT_CONTROLLER_NAME
from .fleet.router import FleetRouter, current_controller
from .utils.audit import AuditLogger, ToolCallRecorder, get_audit_logger
from .utils.exceptions import ResourceNotFoundError, ValidationError
from .utils.logger import get_logger
from .utils.metrics import REGISTRY as METRICS
from .utils.validators import coerce_bool

#: Type of the ``controller`` argument every controller-bound tool gains.
ControllerArg = Annotated[
    str | None,
    Field(
        description=(
            "Controller to run against (see list_controllers). Defaults to the "
            "controller chosen with select_controller, then the server default."
        )
    ),
]

#: Parameters that mark a tool as state-changing.
#:
#: Every mutating tool in this codebase takes a ``confirm`` and/or ``dry_run``
#: parameter, so the signature itself is a reliable classifier — and one that
#: stays correct as new tools are added, unlike a hand-maintained name list.
_MUTATION_MARKERS = ("confirm", "dry_run")

#: Mutating tools that do not (yet) carry a ``confirm``/``dry_run`` parameter.
#:
#: These are listed explicitly so read-only mode does not expose them. This set
#: is a *classification* hint only; it does not change the tools' behaviour.
#: Entries should be removed as the corresponding tools gain proper gates.
MUTATING_TOOLS_WITHOUT_GATE = frozenset(
    {
        "create_protect_live_view",
        "run_speed_test",
        "send_protect_alarm_webhook",
        "update_protect_chime",
        "update_protect_device",
        "update_protect_light",
        "update_protect_live_view",
        "update_protect_sensor",
        "update_protect_viewer",
    }
)


#: Risk tier of a tool; roles grant tiers (docs/FLEET_SCALING_PLAN.md §3.6).
Tier = Literal["read", "write", "destructive"]

#: Mutating tools whose name starts with one of these are always destructive,
#: so a newly added delete tool cannot land in a lower tier by omission.
_DESTRUCTIVE_PREFIXES = ("delete_", "remove_", "bulk_delete_")

#: Mutating tools that delete, restore, re-image, cut service or lock out, and
#: whose names do not carry a destructive prefix.
DESTRUCTIVE_TOOLS = frozenset(
    {
        # Raw API passthrough: arbitrary requests to the controller.
        "connector_network_delete",
        "connector_network_patch",
        "connector_network_post",
        "connector_network_put",
        "connector_protect_delete",
        "connector_protect_patch",
        "connector_protect_post",
        "connector_protect_put",
        # Restore, re-image, or hand a device to another controller.
        "migrate_device",
        "restore_backup",
        "upgrade_device",
        # Service interruption.
        "execute_port_action",
        "force_provision_device",
        "move_device_to_site",
        "restart_device",
        "suspend_carrier_subscriber",
        # Blocking clients or traffic.
        "block_application_by_zone",
        "block_client",
        "block_flow_application",
        "block_flow_destination_ip",
        "block_flow_source_ip",
        # Physical security posture.
        "disable_protect_alarm",
        "set_current_protect_arm_profile",
    }
)

#: Tier of every tool registered through :func:`register_module_tools`, by
#: public tool name. A2A delegation looks tiers up here instead of guessing
#: from tool names.
TOOL_TIERS: dict[str, Tier] = {}


def tool_tier(fn: Any) -> Tier:
    """Return the risk tier of tool *fn*.

    Args:
        fn: The tool function to classify.

    Returns:
        ``read`` for non-mutating tools, ``destructive`` for mutating tools in
        :data:`DESTRUCTIVE_TOOLS` or with a destructive name prefix, and
        ``write`` for every other mutating tool.
    """
    if not is_mutating_tool(fn):
        return "read"
    name = getattr(fn, "__name__", "").lstrip("_")
    if name in DESTRUCTIVE_TOOLS or name.startswith(_DESTRUCTIVE_PREFIXES):
        return "destructive"
    return "write"


def _audit_logger_for(settings: Any) -> AuditLogger | None:
    """Return the audit logger for wrapper records, or None when auditing is off."""
    if getattr(settings, "audit_log_enabled", False) is not True:
        return None
    log_file = getattr(settings, "audit_log_file", None)
    return get_audit_logger(log_file if isinstance(log_file, str) else None)


def _request_ids() -> tuple[str | None, str | None]:
    """Return the MCP session and request ids of the current call, if any."""
    try:
        ctx = get_context()
    except RuntimeError:
        return None, None
    return ctx.session_id, ctx.request_id


def is_mutating_tool(fn: Any) -> bool:
    """Return whether *fn* can change controller state.

    A tool counts as mutating when its signature carries one of the mutation
    markers (``confirm``/``dry_run``), or when it is listed in
    :data:`MUTATING_TOOLS_WITHOUT_GATE`.

    Args:
        fn: The tool function to classify.

    Returns:
        True if the tool can change state, False if it is read-only.
    """
    if getattr(fn, "__name__", "") in MUTATING_TOOLS_WITHOUT_GATE:
        return True
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return True
    return any(marker in params for marker in _MUTATION_MARKERS)


def _get_registered_tool_names(mcp: FastMCP) -> set[str]:
    """Return the tool names already registered on this MCP instance.

    FastMCP's duplicate-component warnings are emitted when the same tool name
    is registered more than once on a live server instance.  We keep a per-
    instance registry so repeated registration passes can safely skip names that
    were already seen, instead of relying on FastMCP's warning path.
    """
    try:
        registry = mcp.__dict__
    except AttributeError:
        registered = getattr(mcp, "_registered_tool_names", None)
        if registered is None:
            registered = set()
            mcp._registered_tool_names = registered
        return registered

    registered = registry.get("_registered_tool_names")
    if registered is None:
        registered = set()
        registry["_registered_tool_names"] = registered
    return registered


def _make_tool_wrapper(fn: Any, settings: Settings, router: FleetRouter | None = None) -> Any:
    """Return an async wrapper for *fn* with ``settings`` bound.

    The wrapper's ``__signature__`` is set to the public signature (all
    parameters except ``settings``) so FastMCP generates the correct JSON
    schema for MCP clients.

    Async tools also gain an optional keyword-only ``controller`` argument.
    Each call is resolved to one controller by *router*, and the tool receives
    that controller's settings. Without a router the wrapper serves only the
    ``default`` controller with *settings*, exactly as before routing existed.

    Args:
        fn: The original async tool function.
        settings: Application settings instance to bind.
        router: Resolves each call to a controller (see ``src/fleet/router.py``).

    Returns:
        An async callable with the ``settings`` parameter removed from its
        visible signature.
    """
    sig = inspect.signature(fn)
    params = sig.parameters

    # Determine whether settings is a positional-or-keyword vs keyword-only param
    # and build the public signature without it.
    public_params = [p for name, p in params.items() if name != "settings"]
    public_sig = sig.replace(parameters=public_params)

    # Global change-safe mode: a tool that declares a dry_run parameter can be
    # forced into preview mode regardless of what the caller passes. Tools
    # without a dry_run gate never reach this point in dry-run mode (they are
    # filtered at registration), so forcing here is always safe.
    force_dry_run = "dry_run" in params

    # Metric labels must match the public MCP tool name, not the private
    # module-level spelling (tools are defined as ``_list_devices`` but
    # registered as ``list_devices``).
    metric_tool_name = fn.__name__.lstrip("_")
    mutating = is_mutating_tool(fn)
    tier = tool_tier(fn)

    if inspect.iscoroutinefunction(fn):
        public_sig = _with_controller_param(public_sig)

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            requested = kwargs.pop("controller", None)
            principal = request_principal()
            # Reads are not audited; every mutating call is (plan §3.7).
            audit = _audit_logger_for(settings) if mutating else None
            context: dict[str, Any] = {}
            if audit is not None:
                session_id, request_id = _request_ids()
                arguments = dict(public_sig.bind_partial(*args, **kwargs).arguments)
                context = {
                    "operation": metric_tool_name,
                    "tool": metric_tool_name,
                    "tier": tier,
                    "principal": {
                        "id": principal.id,
                        "name": principal.name,
                        "role": principal.role,
                        "break_glass": principal.break_glass,
                    },
                    "user": principal.id,
                    "site_id": arguments.get("site_id"),
                    "session_id": session_id,
                    "request_id": request_id,
                    "parameters": arguments,
                }

            try:
                if router is None:
                    if requested not in (None, DEFAULT_CONTROLLER_NAME):
                        raise ResourceNotFoundError("controller", requested)
                    controller, call_settings = DEFAULT_CONTROLLER_NAME, settings
                else:
                    resolution = await router.resolve(requested, mutating=mutating)
                    controller, call_settings = resolution.name, resolution.settings
            except (ResourceNotFoundError, ValidationError) as e:
                if audit is not None:
                    audit.log_event(
                        "denied", result="denied", error=str(e), controller=requested, **context
                    )
                raise

            if force_dry_run and getattr(settings, "dry_run", False):
                kwargs["dry_run"] = True
            kwargs["settings"] = call_settings
            recorder = None
            if audit is not None:
                recorder = ToolCallRecorder(
                    audit,
                    fail_closed=getattr(settings, "audit_fail_closed", True) is not False,
                    controller=controller,
                    **context,
                )
                recorder.attempt()

            metrics_on = getattr(settings, "metrics_enabled", False)
            token = current_controller.set(controller)
            principal_token = current_principal.set(principal)
            try:
                if metrics_on:
                    METRICS.record_controller_call(controller)
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                except Exception as e:
                    if metrics_on:
                        METRICS.record_tool_call(
                            metric_tool_name, "error", time.perf_counter() - start
                        )
                    if recorder is not None:
                        recorder.outcome("error", error=str(e))
                    raise
                if metrics_on:
                    METRICS.record_tool_call(
                        metric_tool_name, "success", time.perf_counter() - start
                    )
                if recorder is not None:
                    dry_run = coerce_bool(kwargs.get("dry_run", False))
                    recorder.outcome("dry_run" if dry_run else "success")
                return result
            finally:
                current_principal.reset(principal_token)
                current_controller.reset(token)

        # functools.wraps shares fn's annotation dict; give the wrapper its own
        # so the added parameter reaches the schema without touching fn.
        wrapper.__annotations__ = {**fn.__annotations__, "controller": ControllerArg}

    else:

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if force_dry_run and getattr(settings, "dry_run", False):
                kwargs["dry_run"] = True
            kwargs["settings"] = settings
            if not getattr(settings, "metrics_enabled", False):
                return fn(*args, **kwargs)
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            except Exception:
                METRICS.record_tool_call(metric_tool_name, "error", time.perf_counter() - start)
                raise
            METRICS.record_tool_call(metric_tool_name, "success", time.perf_counter() - start)
            return result

    wrapper.__signature__ = public_sig  # type: ignore[attr-defined]
    return wrapper


def _with_controller_param(sig: inspect.Signature) -> inspect.Signature:
    """Return *sig* with an optional keyword-only ``controller`` parameter."""
    controller = inspect.Parameter(
        "controller", inspect.Parameter.KEYWORD_ONLY, default=None, annotation=ControllerArg
    )
    params = list(sig.parameters.values())
    if params and params[-1].kind is inspect.Parameter.VAR_KEYWORD:
        params.insert(len(params) - 1, controller)
    else:
        params.append(controller)
    return sig.replace(parameters=params)


def register_module_tools(
    mcp: FastMCP,
    module: types.ModuleType,
    settings: Settings,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    router: FleetRouter | None = None,
) -> list[str]:
    """Register all public async functions from *module* as MCP tools.

    Functions are registered only if:
    - They are async callables defined in *module* (not imported from elsewhere).
    - Their name does not start with ``_``.
    - They are in *include* (if specified) or not in *exclude* (if specified).
    - They accept a ``settings`` parameter (otherwise registered as-is).
    - They are non-mutating, when ``settings.read_only`` is enabled.

    Args:
        mcp: The FastMCP server instance.
        module: The tool module to introspect.
        settings: Settings instance to bind.
        include: Optional explicit list of function names to register.
        exclude: Optional list of function names to skip.
        router: Resolves each call to a controller; see :func:`_make_tool_wrapper`.

    Returns:
        List of registered tool names.
    """
    registered: list[str] = []
    skipped: list[str] = []
    skipped_dry_run: list[str] = []
    exclude_set = set(exclude or [])
    registered_names = _get_registered_tool_names(mcp)

    for name, obj in inspect.getmembers(module, inspect.isfunction):
        # Skip private / dunder names
        if name.startswith("_"):
            continue
        # Only functions defined in this module (not re-exported imports)
        if obj.__module__ != module.__name__:
            continue
        if include is not None and name not in include:
            continue
        if name in exclude_set:
            continue
        if not inspect.iscoroutinefunction(obj):
            continue
        # Read-only mode: never expose state-changing tools to the client.
        # Filtering at registration means the tool is absent from the MCP tool
        # list entirely, rather than relying on a caller-supplied ``confirm``.
        if getattr(settings, "read_only", False) and is_mutating_tool(obj):
            skipped.append(name)
            continue

        # Global dry-run mode: gated tools get dry_run forced on at call time,
        # but a mutating tool with no dry_run parameter at all cannot honour
        # the "no write reaches the controller" promise — leave it out.
        if (
            getattr(settings, "dry_run", False)
            and "dry_run" not in inspect.signature(obj).parameters
            and is_mutating_tool(obj)
        ):
            skipped_dry_run.append(name)
            continue

        params = inspect.signature(obj).parameters
        if "settings" in params:
            tool_fn = _make_tool_wrapper(obj, settings, router)
        else:
            tool_fn = obj

        if name in registered_names:
            # Keep the first registered variant when multiple modules define the
            # same public tool name.
            continue

        mcp.tool()(tool_fn)
        TOOL_TIERS[name] = tool_tier(obj)
        registered_names.add(name)
        METRICS.note_tool_registered()
        registered.append(name)

    if skipped:
        get_logger(__name__).info(
            "Read-only mode: skipped %d mutating tool(s) from %s: %s",
            len(skipped),
            module.__name__,
            ", ".join(sorted(skipped)),
        )
    if skipped_dry_run:
        get_logger(__name__).info(
            "Dry-run mode: skipped %d mutating tool(s) without a dry_run gate from %s: %s",
            len(skipped_dry_run),
            module.__name__,
            ", ".join(sorted(skipped_dry_run)),
        )

    return registered
