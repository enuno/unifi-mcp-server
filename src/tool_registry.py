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
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
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
    exclude_set = set(exclude or [])

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

        params = inspect.signature(obj).parameters
        if "settings" in params:
            tool_fn = _make_tool_wrapper(obj, settings)
        else:
            tool_fn = obj

        mcp.tool()(tool_fn)
        registered.append(name)

    return registered
