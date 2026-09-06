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
import types
from typing import Any

from fastmcp import FastMCP

from .config import Settings
from .utils.logger import get_logger

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


def _make_tool_wrapper(fn: Any, settings: Settings) -> Any:
    """Return an async wrapper for *fn* with ``settings`` bound.

    The wrapper's ``__signature__`` is set to the public signature (all
    parameters except ``settings``) so FastMCP generates the correct JSON
    schema for MCP clients.

    Args:
        fn: The original async tool function.
        settings: Application settings instance to bind.

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

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            kwargs["settings"] = settings
            return await fn(*args, **kwargs)

    else:

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            kwargs["settings"] = settings
            return fn(*args, **kwargs)

    wrapper.__signature__ = public_sig  # type: ignore[attr-defined]
    return wrapper


def register_module_tools(
    mcp: FastMCP,
    module: types.ModuleType,
    settings: Settings,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
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

    Returns:
        List of registered tool names.
    """
    registered: list[str] = []
    skipped: list[str] = []
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

        params = inspect.signature(obj).parameters
        if "settings" in params:
            tool_fn = _make_tool_wrapper(obj, settings)
        else:
            tool_fn = obj

        if name in registered_names:
            # Keep the first registered variant when multiple modules define the
            # same public tool name.
            continue

        mcp.tool()(tool_fn)
        registered_names.add(name)
        registered.append(name)

    if skipped:
        get_logger(__name__).info(
            "Read-only mode: skipped %d mutating tool(s) from %s: %s",
            len(skipped),
            module.__name__,
            ", ".join(sorted(skipped)),
        )

    return registered
