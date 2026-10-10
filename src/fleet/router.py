"""Per-call controller resolution (Phase 1 of docs/FLEET_SCALING_PLAN.md).

The tool wrapper asks :class:`FleetRouter` which controller a call targets and
gets back that controller's :class:`Settings`. Resolution order:

1. the ``controller`` argument of the call,
2. the controller selected in this MCP session (``select_controller``),
3. the registry's default controller.

A mutating call may not rely on the registry default alone while more than one
controller is registered: it must name its target or use a selection made in
the same session, so a write never lands on a controller by accident.
"""

from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal

from fastmcp.server.dependencies import get_context

from ..config import Settings
from ..utils.exceptions import ValidationError
from .registry import ControllerProfile, ControllerRegistry

#: Session-state key holding the controller chosen with ``select_controller``.
SESSION_KEY = "unifi.active_controller"

#: Name of the controller the current tool call targets; ``None`` outside a
#: call. Set by the tool wrapper so logs, metrics and audit records can read it
#: without threading it through every signature.
current_controller: ContextVar[str | None] = ContextVar("unifi_current_controller", default=None)

Source = Literal["explicit", "session", "default"]


@dataclass(frozen=True)
class Resolution:
    """The controller a call targets and the settings to reach it."""

    name: str
    settings: Settings
    source: Source
    labels: Mapping[str, str] = field(default_factory=dict)


def _session_context() -> Any | None:
    """Return the current MCP request context, or None outside a request."""
    try:
        return get_context()
    except RuntimeError:
        return None


class FleetRouter:
    """Resolves each tool call to one controller from a registry."""

    def __init__(self, base: Settings, registry: ControllerRegistry) -> None:
        """Create a router.

        Args:
            base: Process-wide settings; per-controller settings derive from it
            registry: Where controller profiles are looked up
        """
        self.base = base
        self.registry = registry
        self._derived: dict[str, tuple[ControllerProfile, Settings]] = {}

    @property
    def stateless(self) -> bool:
        """Whether the server runs without MCP sessions (``MCP_STATELESS_HTTP``)."""
        return bool(getattr(self.base, "mcp_stateless_http", False))

    async def session_controller(self) -> str | None:
        """Return the controller selected in this MCP session, if any."""
        if self.stateless:
            return None
        ctx = _session_context()
        if ctx is None:
            return None
        name = await ctx.get_state(SESSION_KEY)
        return name if isinstance(name, str) else None

    async def select(self, name: str) -> ControllerProfile:
        """Make ``name`` the session's controller for later calls.

        Args:
            name: A registered controller name

        Returns:
            The selected controller's profile

        Raises:
            ResourceNotFoundError: If no controller has that name
            ValidationError: Outside an MCP session, or when the server runs
                stateless (no session would remember the choice)
        """
        if self.stateless:
            raise ValidationError(
                "select_controller is not available: this server runs stateless "
                "(MCP_STATELESS_HTTP), so no session remembers a choice. Pass "
                "controller=<name> to each tool call instead."
            )
        profile = await self.registry.get_controller(name)
        ctx = _session_context()
        if ctx is None:
            raise ValidationError("select_controller needs an MCP session to remember the choice")
        await ctx.set_state(SESSION_KEY, profile.name)
        return profile

    def _how_to_target(self) -> str:
        if self.stateless:
            return "pass controller=<name>"
        return "pass controller=<name> or call select_controller first"

    async def resolve(self, requested: str | None, *, mutating: bool) -> Resolution:
        """Resolve the controller for one call.

        Args:
            requested: The call's ``controller`` argument, if given
            mutating: Whether the tool can change controller state

        Returns:
            The target controller, its settings, and how it was chosen

        Raises:
            ResourceNotFoundError: If the named or session controller is unknown
            ValidationError: If no controller can be chosen, or a write would
                fall back to the registry default with several controllers
        """
        source: Source
        if requested:
            name, source = requested, "explicit"
        elif (selected := await self.session_controller()) is not None:
            name, source = selected, "session"
        elif (default := await self.registry.default_controller()) is not None:
            name, source = default, "default"
        else:
            raise ValidationError(f"No controller specified: {self._how_to_target()}")

        if mutating and source == "default" and len(await self.registry.list_controllers()) > 1:
            raise ValidationError(
                "This tool changes controller state and several controllers are registered: "
                f"{self._how_to_target()}"
            )

        profile = await self.registry.get_controller(name)
        return Resolution(
            name=profile.name,
            settings=self.settings_for(profile),
            source=source,
            labels=dict(profile.labels),
        )

    def settings_for(self, profile: ControllerProfile) -> Settings:
        """Return (and cache) the settings for ``profile``.

        A profile that changes nothing yields the base settings object itself,
        so a single env-configured controller behaves exactly as before.
        """
        cached = self._derived.get(profile.name)
        if cached is not None and cached[0] == profile:
            return cached[1]
        derived = profile.apply_to(self.base)
        if derived == self.base:
            derived = self.base
        self._derived[profile.name] = (profile, derived)
        return derived
