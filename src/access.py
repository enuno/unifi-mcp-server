"""Who is calling a tool, and what they may do (docs/FLEET_SCALING_PLAN.md §3.6).

The tool wrapper binds a :class:`Principal` to :data:`current_principal` for
each call and checks it before any controller is contacted:

- the principal's role must grant the tool's risk tier (:data:`ROLE_TIERS`),
- the tool's module must pass the principal's ``allow_modules`` /
  ``deny_modules`` patterns, and
- the target controller's labels must match its ``controller_labels``.

Server-issued API tokens carry a role and filters. ``MCP_AUTH_TOKEN`` tokens
and stdio are break-glass callers with the ``fleet-admin`` role, so they keep
everything they could do before enforcement existed; ``UNIFI_STDIO_ROLE`` can
lower stdio.
"""

import fnmatch
import hashlib
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal

from fastmcp.server.dependencies import get_access_token

from .utils.exceptions import UniFiMCPException

Role = Literal["viewer", "operator", "admin", "fleet-admin"]

#: Risk tier of a tool; roles grant tiers.
Tier = Literal["read", "write", "destructive", "fleet-admin"]

ROLES: tuple[Role, ...] = ("viewer", "operator", "admin", "fleet-admin")

#: The tiers each role may use.
ROLE_TIERS: dict[str, frozenset[str]] = {
    "viewer": frozenset({"read"}),
    "operator": frozenset({"read", "write"}),
    "admin": frozenset({"read", "write", "destructive"}),
    "fleet-admin": frozenset({"read", "write", "destructive", "fleet-admin"}),
}


class PermissionDeniedError(UniFiMCPException):
    """Raised when the caller may not run a tool or reach a controller."""


@dataclass(frozen=True)
class Principal:
    """The identity a tool call runs as.

    Attributes:
        id: Stable identifier: ``local`` for stdio, ``env:<fingerprint>`` for
            an ``MCP_AUTH_TOKEN`` token, ``token:<id>`` for an issued token
            (never the token itself)
        name: Human-readable name
        role: Grants tiers (:data:`ROLE_TIERS`)
        break_glass: True for stdio and ``MCP_AUTH_TOKEN`` callers, which are
            flagged as such in audit records
        allow_modules: If set, only tool modules matching one of these
            ``fnmatch`` patterns
        deny_modules: Tool modules matching one of these patterns are refused
        controller_labels: Labels a controller must carry for this caller to
            reach it (all must match)
    """

    id: str
    name: str
    role: Role
    break_glass: bool = False
    allow_modules: tuple[str, ...] | None = None
    deny_modules: tuple[str, ...] = ()
    controller_labels: Mapping[str, str] = field(default_factory=dict)

    def can_use(self, tier: str) -> bool:
        """Whether this principal's role grants ``tier``."""
        return tier in ROLE_TIERS.get(self.role, frozenset())

    def allows_module(self, module: str) -> bool:
        """Whether tools from ``module`` pass the module filters."""
        if any(fnmatch.fnmatchcase(module, pattern) for pattern in self.deny_modules):
            return False
        if self.allow_modules is None:
            return True
        return any(fnmatch.fnmatchcase(module, pattern) for pattern in self.allow_modules)

    def allows_controller(self, labels: Mapping[str, str]) -> bool:
        """Whether a controller with ``labels`` matches the label selector."""
        return all(labels.get(key) == value for key, value in self.controller_labels.items())

    def audit_view(self) -> dict[str, Any]:
        """The principal as recorded in audit records."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "break_glass": self.break_glass,
        }


def local_principal(role: Role = "fleet-admin") -> Principal:
    """The caller when there is no authenticated request: stdio, or a direct call."""
    return Principal(id="local", name="stdio", role=role, break_glass=True)


#: The local principal with the default role.
LOCAL_PRINCIPAL = local_principal()

#: Principal of the tool call in progress; ``None`` outside a call.
current_principal: ContextVar[Principal | None] = ContextVar(
    "unifi_current_principal", default=None
)


def token_fingerprint(token: str) -> str:
    """Return a short, non-reversible identifier for a bearer token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def request_principal(local_role: Role = "fleet-admin") -> Principal:
    """Return the principal of the current MCP request.

    Args:
        local_role: Role of the caller when there is no authenticated request

    Returns:
        An issued token's principal (from the claims its verifier attached),
        a break-glass ``fleet-admin`` for an ``MCP_AUTH_TOKEN`` token, or the
        local principal
    """
    access_token = get_access_token()
    if access_token is None:
        return local_principal(local_role)
    claims = access_token.claims or {}
    if "token_id" in claims:
        allow = claims.get("allow_modules")
        return Principal(
            id=f"token:{claims['token_id']}",
            name=str(claims.get("name", access_token.client_id)),
            role=claims["role"],
            allow_modules=tuple(allow) if allow is not None else None,
            deny_modules=tuple(claims.get("deny_modules") or ()),
            controller_labels=dict(claims.get("controller_labels") or {}),
        )
    return Principal(
        id=f"env:{token_fingerprint(access_token.token)}",
        name=access_token.client_id,
        role="fleet-admin",
        break_glass=True,
    )
