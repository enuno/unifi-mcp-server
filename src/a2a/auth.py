"""Multi-authentication helpers for A2A delegation.

The project supports both local controller access and UniFi cloud access.
This module normalizes those modes into an ``AuthContext`` used by the safety
layer and HTTP endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping

from ..config import APIType
from ..utils import get_logger


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
        self.logger = get_logger(__name__)
        self.local_provider = LocalAuthProvider()
        self.cloud_provider = CloudAuthProvider()

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
        required = self._required_permission(tool_name)
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

    @staticmethod
    def _required_permission(tool_name: str) -> str:
        normalized = tool_name.strip().lower()
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
        return "read"


__all__ = [
    "AuthContext",
    "LocalAuthProvider",
    "CloudAuthProvider",
    "AuthManager",
]
