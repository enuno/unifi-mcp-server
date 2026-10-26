"""Multi-authentication helpers for A2A delegation.

The project supports both local controller access and UniFi cloud access.
This module normalizes those modes into an ``AuthContext`` used by the safety
layer and HTTP endpoints.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from ..config import APIType
from ..tool_registry import TOOL_TIERS, tool_tier
from ..utils import get_logger

#: The role of the caller whose request is being handled, as resolved from
#: its bearer token by the transport. None when the caller could not be
#: identified, which grants read only.
current_caller_role: ContextVar[str | None] = ContextVar("unifi_a2a_caller_role", default=None)


class _Tiers:
    """The risk tiers a role grants, in permission-name form.

    These mirror ``src.access.ROLE_TIERS``. The A2A layer cannot import the
    role table directly because that module reads the request context, so
    the mapping is restated here in the vocabulary the A2A auth providers
    use and checked against the role table by a unit test.
    """

    READ = frozenset({"read"})
    WRITE = frozenset({"read", "write"})
    DESTRUCTIVE = frozenset({"read", "write", "destructive"})
    ADMIN = frozenset({"read", "write", "destructive", "admin"})


#: The tiers each role grants.
_ROLE_TIERS: dict[str, frozenset[str]] = {
    "viewer": _Tiers.READ,
    "operator": _Tiers.WRITE,
    "admin": _Tiers.DESTRUCTIVE,
    "fleet-admin": _Tiers.ADMIN,
}


def _tiers_for_role(role: str | None) -> frozenset[str]:
    """Return the permission tiers a role grants.

    Args:
        role: The role name, or None when the caller is anonymous.

    Returns:
        The granted tiers. An unknown role grants read only, so an
        unrecognised role can never widen access.
    """
    if not role:
        return _Tiers.READ
    return _ROLE_TIERS.get(role, _Tiers.READ)


def _agent_id_from_payload(payload: Mapping[str, Any]) -> str:
    """Return the caller's identifier from a delegation payload.

    Args:
        payload: The delegation request.

    Returns:
        The agent identifier, or ``anonymous``.
    """
    return str(
        payload.get("agent_id")
        or payload.get("agentId")
        or payload.get("client_id")
        or payload.get("clientId")
        or payload.get("subject")
        or payload.get("sub")
        or "anonymous"
    )


@dataclass(slots=True)
class AuthContext:
    """Authentication context returned by an A2A auth provider."""

    mode: str
    credentials: dict[str, Any]
    permissions: set[str] = field(default_factory=set)
    expiry: datetime | None = None

    def is_expired(self) -> bool:
        """Return True when the authentication context has expired."""
        return self.expiry is not None and datetime.now(tz=UTC) >= self.expiry


class LocalAuthProvider:
    """Authenticate against a local UniFi controller."""

    def __init__(self, default_ttl_seconds: int = 3600) -> None:
        """Set the fallback lifetime for local auth contexts, in seconds."""
        self.default_ttl_seconds = default_ttl_seconds
        self.logger = get_logger(__name__)

    def authenticate(self, credentials: Mapping[str, Any]) -> AuthContext:
        """Create an auth context for local controller access."""
        credentials_dict = dict(credentials)
        permissions = self._permissions_from_credentials(credentials_dict)
        expiry = self._expiry_from_credentials(credentials_dict)
        return AuthContext(
            mode=APIType.LOCAL.value,
            credentials=credentials_dict,
            permissions=permissions,
            expiry=expiry,
        )

    def refresh(self, auth_context: AuthContext) -> AuthContext:
        """Refresh a local auth context without changing the credential payload."""
        credentials = dict(auth_context.credentials)
        expiry = self._expiry_from_credentials(credentials)
        return replace(auth_context, expiry=expiry)

    def _permissions_from_credentials(self, credentials: Mapping[str, Any]) -> set[str]:
        requested = {
            str(permission).lower()
            for permission in credentials.get("permissions", [])
            if permission is not None
        }
        if requested:
            return requested
        if credentials.get("api_key") or credentials.get("token") or credentials.get("username"):
            return {"read", "write", "destructive"}
        return {"read"}

    def _expiry_from_credentials(self, credentials: Mapping[str, Any]) -> datetime:
        expires_in = int(credentials.get("expires_in") or self.default_ttl_seconds)
        return datetime.now(tz=UTC) + timedelta(seconds=max(1, expires_in))


class CloudAuthProvider:
    """Authenticate against UniFi Cloud APIs."""

    def __init__(self, default_ttl_seconds: int = 1800) -> None:
        """Set the fallback lifetime for cloud auth contexts, in seconds."""
        self.default_ttl_seconds = default_ttl_seconds
        self.logger = get_logger(__name__)

    def authenticate(self, credentials: Mapping[str, Any]) -> AuthContext:
        """Create an auth context for cloud access."""
        credentials_dict = dict(credentials)
        permissions = self._permissions_from_credentials(credentials_dict)
        expiry = self._expiry_from_credentials(credentials_dict)
        mode = credentials_dict.get("mode") or APIType.CLOUD_EA.value
        return AuthContext(
            mode=str(mode).lower(),
            credentials=credentials_dict,
            permissions=permissions,
            expiry=expiry,
        )

    def refresh(self, auth_context: AuthContext) -> AuthContext:
        """Refresh a cloud auth context."""
        credentials = dict(auth_context.credentials)
        expiry = self._expiry_from_credentials(credentials)
        return replace(auth_context, expiry=expiry)

    def _permissions_from_credentials(self, credentials: Mapping[str, Any]) -> set[str]:
        scopes = credentials.get("scopes") or credentials.get("permissions") or []
        normalized = {str(scope).lower() for scope in scopes if scope is not None}
        permissions: set[str] = set()
        if normalized & {"read", "viewer", "view"}:
            permissions.add("read")
        if normalized & {"write", "editor", "manage"}:
            permissions.add("write")
        if normalized & {"destructive", "admin", "owner"}:
            permissions.update({"write", "destructive"})
        if normalized & {"admin", "owner"}:
            permissions.add("admin")
        if not permissions:
            permissions.add("read")
        return permissions

    def _expiry_from_credentials(self, credentials: Mapping[str, Any]) -> datetime:
        expires_in = int(credentials.get("expires_in") or self.default_ttl_seconds)
        return datetime.now(tz=UTC) + timedelta(seconds=max(1, expires_in))


class AuthManager:
    """Authenticate and authorize A2A requests across local and cloud modes."""

    def __init__(self) -> None:
        """Construct the local and cloud providers this manager dispatches to."""
        self.logger = get_logger(__name__)
        self.local_provider = LocalAuthProvider()
        self.cloud_provider = CloudAuthProvider()
        # The tools this deployment registered, keyed by public name. A
        # tool's tier decides what role may call it, so the tier is
        # resolved from the tool itself rather than from its name.
        self._registered_tools: dict[str, Any] = {}
        # The server the tools are registered on, when there is one.
        self._mcp: Any | None = None

    def register_tools(self, tools: Mapping[str, Any], mcp: Any | None = None) -> None:
        """Record the tools this deployment registered.

        The tool registry covers most tools; the fleet tools and the
        health check register by another path and are covered here.

        Args:
            tools: The registered tools, keyed by public name.
            mcp: The server the tools are registered on, so a tool
                registered later can still be classified.
        """
        self._registered_tools = dict(tools)
        self._mcp = mcp

    def _tier_of_registered_tool(self, tool_name: str) -> str | None:
        """Return the risk tier of a registered tool, or None if unknown.

        The tool's own function is classified with the registry's
        classifier, so a tool that mutates state is a write or destructive
        tool whatever its name happens to look like.

        The lookup is against the live server, not a snapshot taken at
        startup, so a tool registered later is classified correctly too.
        """
        tool = self._registered_tools.get(tool_name)
        if tool is None:
            tool = self._live_tool(tool_name)
        if tool is None:
            return None
        function = getattr(tool, "fn", None)
        if function is None:
            return None
        try:
            return tool_tier(function)
        except Exception:  # pragma: no cover - a tool with an odd signature
            return None

    def _live_tool(self, tool_name: str) -> Any | None:
        """Return a registered tool from the live server, if there is one."""
        server = self._mcp
        if server is None:
            return None
        for provider in getattr(server, "providers", []):
            components = getattr(provider, "_components", None)
            if not isinstance(components, dict):
                continue
            for key, component in components.items():
                if not key.startswith("tool:"):
                    continue
                if key[5:].split("@", 1)[0] == tool_name:
                    return component
        return None

    @staticmethod
    def _normalize_mode(mode: str | APIType) -> str:
        value = mode.value if isinstance(mode, APIType) else str(mode)
        value = value.lower().strip()
        if value == APIType.CLOUD.value:
            return APIType.CLOUD_EA.value
        return value

    def authenticate(self, mode: str | APIType, credentials: Mapping[str, Any]) -> AuthContext:
        """Authenticate using the appropriate provider for the requested mode."""
        normalized = self._normalize_mode(mode)
        if normalized == APIType.LOCAL.value:
            return self.local_provider.authenticate(credentials)
        if normalized in {APIType.CLOUD_EA.value, APIType.CLOUD_V1.value}:
            return self.cloud_provider.authenticate({**credentials, "mode": normalized})
        raise ValueError(f"Unsupported auth mode: {mode}")

    def refresh(self, auth_context: AuthContext) -> AuthContext:
        """Refresh an existing authentication context."""
        if self._normalize_mode(auth_context.mode) == APIType.LOCAL.value:
            return self.local_provider.refresh(auth_context)
        return self.cloud_provider.refresh(auth_context)

    def validate_permissions(self, auth_context: AuthContext, tool_name: str) -> bool:
        """Return True when the context grants permission for the requested tool."""
        required = self.required_permission(tool_name)
        permissions = {permission.lower() for permission in auth_context.permissions}
        if "admin" in permissions:
            return True
        if required == "read":
            return bool(permissions & {"read", "write", "destructive"})
        if required == "write":
            return bool(permissions & {"write", "destructive"})
        if required == "destructive":
            return "destructive" in permissions
        return required in permissions

    def credentials_for_caller(
        self,
        payload: Mapping[str, Any],
        role: str | None = None,
    ) -> dict[str, Any]:
        """Return the credentials describing the caller of a delegated request.

        The permissions come from the caller's authenticated role, not from
        the request body. A delegation payload may name scopes, but they can
        only narrow what the authenticated role already grants; they can
        never widen it. The server's role model (``src.access.ROLE_TIERS``)
        is the enforcement boundary, and a self-asserted permission list
        must not become a second one.

        Args:
            payload: The delegation request.
            role: The authenticated role of the caller, as resolved from the
                bearer token by the transport. None means the caller could
                not be identified, which grants read only.

        Returns:
            The credentials for the auth provider.
        """
        granted = _tiers_for_role(role)

        requested = {
            str(scope).lower() for scope in payload.get("scopes", []) or [] if scope is not None
        }
        if requested:
            granted = granted & requested

        return {
            "role": role,
            "permissions": sorted(granted),
            "agent_id": _agent_id_from_payload(payload),
        }

    def required_permission(self, tool_name: str) -> str:
        """Return the permission a tool needs, for this deployment.

        A tool the registry table does not cover is still a registered
        tool: the fleet tools and the health check register by another
        path. Its tier comes from its own function, classified the same
        way the registry classifies one, so the tier never depends on what
        the name happens to look like.

        Args:
            tool_name: The public name of the tool.

        Returns:
            The risk tier the tool requires.
        """
        tier = self._tier_of_registered_tool(tool_name.strip().lower())
        if tier is not None:
            return tier
        return self._required_permission(tool_name)

    @staticmethod
    def _required_permission(tool_name: str) -> str:
        normalized = tool_name.strip().lower()
        # Registered tools carry a tier from the tool registry; the name
        # heuristics below only cover names the server does not know.
        tier = TOOL_TIERS.get(normalized)
        if tier is not None:
            return tier
        if normalized.startswith(("delete_", "remove_", "reset_", "revoke_", "purge_", "wipe_")):
            return "destructive"
        if normalized.startswith(
            (
                "create_",
                "add_",
                "update_",
                "set_",
                "patch_",
                "enable_",
                "disable_",
                "execute_",
                "assign_",
                "unassign_",
                "start_",
                "stop_",
                "restart_",
                "reboot_",
                "adopt_",
            )
        ):
            return "write"
        if normalized.startswith(
            ("get_", "list_", "fetch_", "read_", "inspect_", "stat_", "search_")
        ):
            return "read"
        return "destructive"


__all__ = [
    "AuthContext",
    "LocalAuthProvider",
    "CloudAuthProvider",
    "AuthManager",
]
