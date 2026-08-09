"""A2A protocol core infrastructure for the UniFi MCP server.

The legacy A2A helpers in this package depend on optional FastMCP internals.
To keep package imports safe in minimal environments, this module only exposes
lightweight wrappers and the new safety / auth / audit / HTTP helpers.
"""

from __future__ import annotations

from .audit import AuditLog, AuditLogger
from .auth import AuthContext, AuthManager, CloudAuthProvider, LocalAuthProvider
from .http_handlers import (
    A2AHTTPRouter,
    A2AState,
    confirm_handler,
    delegate_handler,
    discover_handler,
    get_agent_card_handler,
    get_audit_handler,
)
from .route_policy import (
    ConfirmationToken,
    ConfirmationWorkflow,
    RoutePolicy,
    SafetyController,
    SafetyResult,
)
from .types import (
    AgentCard,
    AuthenticationMode,
    DelegationContract,
    ResourceURI,
    SafetyRequirement,
    Skill,
)


def build_agent_card(*args, **kwargs):
    """Lazily invoke the legacy agent-card builder when FastMCP is available."""
    from .agent_card import build_agent_card as _build_agent_card

    return _build_agent_card(*args, **kwargs)


def get_skills_manifest(*args, **kwargs):
    """Lazily invoke the legacy discovery helper when FastMCP is available."""
    from .discovery import get_skills_manifest as _get_skills_manifest

    return _get_skills_manifest(*args, **kwargs)


def get_resource_endpoints(*args, **kwargs):
    """Lazily invoke the legacy resource discovery helper when FastMCP is available."""
    from .discovery import get_resource_endpoints as _get_resource_endpoints

    return _get_resource_endpoints(*args, **kwargs)


def create_delegation_contract(*args, **kwargs):
    """Lazily invoke the legacy delegation helper when FastMCP is available."""
    from .delegation import create_delegation_contract as _create_delegation_contract

    return _create_delegation_contract(*args, **kwargs)


def execute_delegated_call(*args, **kwargs):
    """Lazily invoke the legacy delegated-call helper when FastMCP is available."""
    from .delegation import execute_delegated_call as _execute_delegated_call

    return _execute_delegated_call(*args, **kwargs)


def validate_delegation(*args, **kwargs):
    """Lazily invoke the legacy delegation validation helper when FastMCP is available."""
    from .delegation import validate_delegation as _validate_delegation

    return _validate_delegation(*args, **kwargs)


__all__ = [
    "A2AHTTPRouter",
    "A2AState",
    "AgentCard",
    "AuditLog",
    "AuditLogger",
    "AuthContext",
    "AuthManager",
    "AuthenticationMode",
    "CloudAuthProvider",
    "ConfirmationToken",
    "ConfirmationWorkflow",
    "DelegationContract",
    "LocalAuthProvider",
    "ResourceURI",
    "RoutePolicy",
    "SafetyController",
    "SafetyRequirement",
    "SafetyResult",
    "Skill",
    "build_agent_card",
    "confirm_handler",
    "create_delegation_contract",
    "delegate_handler",
    "discover_handler",
    "execute_delegated_call",
    "get_agent_card_handler",
    "get_audit_handler",
    "get_resource_endpoints",
    "get_skills_manifest",
    "validate_delegation",
]
