"""MCP tools for choosing which controller later tool calls target."""

from typing import Any

from fastmcp import FastMCP

from ..access import ROLES, PermissionDeniedError, Principal, request_principal
from ..config import APIType
from .registry import ControllerProfile
from .router import FleetRouter


def _describe(profile: ControllerProfile, router: FleetRouter) -> dict[str, Any]:
    """Public view of a profile: connection target, never credentials."""
    settings = router.settings_for(profile)
    host = settings.local_host if settings.api_type == APIType.LOCAL else settings.cloud_api_url
    return {
        "name": profile.name,
        "api_type": settings.api_type.value,
        "host": host,
        "default_site": settings.default_site,
        "labels": dict(profile.labels),
    }


def _caller(router: FleetRouter) -> Principal:
    role = getattr(router.base, "stdio_role", None)
    return request_principal(role if role in ROLES else "fleet-admin")


def register_fleet_tools(mcp: FastMCP, router: FleetRouter) -> list[str]:
    """Register ``list_controllers``, ``select_controller`` and ``get_active_controller``.

    Args:
        mcp: The FastMCP server instance
        router: The router the server's tools resolve controllers through

    Returns:
        The registered tool names
    """

    async def list_controllers() -> dict[str, Any]:
        """List the UniFi controllers this server can reach.

        Every controller-bound tool accepts a ``controller`` argument naming one
        of these; without it, calls go to the controller chosen with
        select_controller, then to the default.

        Returns:
            Controllers (name, API type, host, default site, labels), the
            default controller, and this session's selection
        """
        caller = _caller(router)
        profiles = [
            p
            for p in await router.registry.list_controllers()
            if caller.allows_controller(p.labels)
        ]
        return {
            "controllers": [_describe(p, router) for p in profiles],
            "default": await router.registry.default_controller(),
            "selected": await router.session_controller(),
        }

    async def select_controller(name: str) -> dict[str, Any]:
        """Choose the controller this session's later tool calls target.

        A tool call's own ``controller`` argument still takes precedence.

        Args:
            name: A controller name from list_controllers

        Returns:
            The selected controller
        """
        profile = await router.registry.get_controller(name)
        if not _caller(router).allows_controller(profile.labels):
            raise PermissionDeniedError(
                f"Permission denied: controller '{name}' is outside this caller's scope"
            )
        profile = await router.select(name)
        return {"selected": profile.name}

    async def get_active_controller() -> dict[str, Any]:
        """Show which controller a tool call without ``controller`` would target.

        Returns:
            The controller name and where it came from: ``session``
            (select_controller) or ``default``; both are None when neither is set
        """
        selected = await router.session_controller()
        if selected is not None:
            return {"name": selected, "source": "session"}
        default = await router.registry.default_controller()
        return {"name": default, "source": "default" if default is not None else None}

    tools = (list_controllers, select_controller, get_active_controller)
    for tool in tools:
        mcp.tool()(tool)
    return [tool.__name__ for tool in tools]
