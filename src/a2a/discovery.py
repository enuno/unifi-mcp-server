"""Discovery helpers for A2A agent card generation and manifests."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastmcp import FastMCP
from fastmcp.resources.function_resource import FunctionResource
from fastmcp.tools.function_tool import FunctionTool

from ..config import Settings
from .agent_card import build_agent_card as _build_agent_card
from .types import ResourceURI, Skill


def _iter_components(mcp: FastMCP) -> Iterable[Any]:
    """Yield registered components from a FastMCP instance."""
    for provider in getattr(mcp, "providers", []):
        components = getattr(provider, "_components", None)
        if isinstance(components, dict):
            yield from components.values()


def _resolve_active_mcp() -> FastMCP | None:
    """Return the live FastMCP instance if the main module is already loaded."""
    import sys

    for module in list(sys.modules.values()):
        if module is None:
            continue
        mcp = getattr(module, "mcp", None)
        if isinstance(mcp, FastMCP):
            return mcp
    return None


def build_agent_card(mcp: FastMCP, settings: Settings) -> dict[str, Any]:
    """Build an agent card from the registered FastMCP tools and resources."""
    return _build_agent_card(mcp, settings)


def get_skills_manifest() -> list[Skill]:
    """Return the discovered skill manifest for the active MCP server.

    If the live server has not been imported yet, an empty list is returned.
    """
    mcp = _resolve_active_mcp()
    if mcp is None:
        return []

    skills: list[Skill] = []
    from .agent_card import _tool_skill  # local import to avoid import cycles

    for component in _iter_components(mcp):
        if isinstance(component, FunctionTool):
            skills.append(_tool_skill(component))
    return skills


def get_resource_endpoints() -> list[ResourceURI]:
    """Return the discovered resource endpoints for the active MCP server.

    If the live server has not been imported yet, an empty list is returned.
    """
    mcp = _resolve_active_mcp()
    if mcp is None:
        return []

    resources: list[ResourceURI] = []
    from .agent_card import _resource_uri  # local import to avoid import cycles

    for component in _iter_components(mcp):
        if isinstance(component, FunctionResource):
            resources.append(_resource_uri(component))
    return resources


__all__ = ["build_agent_card", "get_resource_endpoints", "get_skills_manifest"]
