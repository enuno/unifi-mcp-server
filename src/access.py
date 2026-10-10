"""Who is calling a tool (docs/FLEET_SCALING_PLAN.md §3.6).

The tool wrapper binds a :class:`Principal` to :data:`current_principal` for
each call, so authorization and audit records can name the caller without
threading it through tool signatures.

Phase 1 identifies callers but does not restrict them: every principal is
``admin``, which is what any authenticated caller can do today. Roles narrower
than ``admin`` arrive with server-issued tokens in Phase 2b.
"""

import hashlib
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

from fastmcp.server.dependencies import get_access_token

Role = Literal["viewer", "operator", "admin", "fleet-admin"]


@dataclass(frozen=True)
class Principal:
    """The identity a tool call runs as.

    Attributes:
        id: Stable identifier: ``local`` for stdio, ``env:<fingerprint>`` for
            an ``MCP_AUTH_TOKEN`` token (a hash prefix, never the token)
        name: Human-readable name (the token's client id, or ``stdio``)
        role: The role whose tiers the caller may use
        break_glass: True for ``MCP_AUTH_TOKEN`` tokens, which always have full
            access and are flagged as such in audit records
    """

    id: str
    name: str
    role: Role
    break_glass: bool = False


#: The caller when there is no authenticated request: stdio, or a direct call.
LOCAL_PRINCIPAL = Principal(id="local", name="stdio", role="admin")

#: Principal of the tool call in progress; ``None`` outside a call.
current_principal: ContextVar[Principal | None] = ContextVar(
    "unifi_current_principal", default=None
)


def token_fingerprint(token: str) -> str:
    """Return a short, non-reversible identifier for a bearer token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def request_principal() -> Principal:
    """Return the principal of the current MCP request.

    Returns:
        The token's principal on an authenticated network transport, else
        :data:`LOCAL_PRINCIPAL`
    """
    access_token = get_access_token()
    if access_token is None:
        return LOCAL_PRINCIPAL
    return Principal(
        id=f"env:{token_fingerprint(access_token.token)}",
        name=access_token.client_id,
        role="admin",
        break_glass=True,
    )
