"""Route policies and safety controls for A2A delegation.

This module centralizes the safety heuristics used by the UniFi MCP A2A layer:
confirmation requirements, rate limits, and authorization-aware validation.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from threading import RLock
from typing import Any

from ..config import Settings
from ..utils import get_logger


@dataclass(slots=True)
class RoutePolicy:
    """Safety policy for a route or delegated tool."""

    path: str
    methods: tuple[str, ...]
    requiredAuth: str
    confirmationLevel: str
    rateLimit: int


@dataclass(slots=True)
class SafetyResult:
    """Result returned by safety validation."""

    allowed: bool
    risk_level: str
    reason: str
    requires_confirmation: bool = False
    rate_limited: bool = False
    policy: RoutePolicy | None = None


@dataclass(slots=True)
class ConfirmationToken:
    """Represents a pending confirmation request."""

    token: str
    tool_name: str
    params_hash: str
    reason: str
    created_at: datetime
    expires_at: datetime
    confirmed: bool = False


class SafetyController:
    """Apply A2A safety rules, rate limits, and confirmation checks."""

    _READ_PREFIXES = ("get_", "list_", "fetch_", "read_", "inspect_", "stat_", "search_")
    _WRITE_PREFIXES = (
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
        "sync_",
    )
    _DESTRUCTIVE_PREFIXES = (
        "delete_",
        "remove_",
        "purge_",
        "forget_",
        "wipe_",
        "destroy_",
        "factory_reset",
        "reset_",
        "disconnect_",
        "block_",
        "revoke_",
    )
    _CONFIRMATION_KEYS = ("confirm", "confirmed", "confirmation", "approve")

    def __init__(
        self, settings: Settings | None = None, policies: list[RoutePolicy] | None = None
    ) -> None:
        """Set up rate-limit tracking and load the route policies to enforce."""
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level if settings else "INFO")
        self._lock = RLock()
        self._request_windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._pending_confirmation_tokens: dict[str, ConfirmationToken] = {}
        self._policies = policies or self._build_default_policies()

    def _build_default_policies(self) -> list[RoutePolicy]:
        """Build baseline policies for the A2A endpoints and delegated tools."""
        read_rate = self.settings.rate_limit_requests if self.settings else 120
        write_rate = max(1, (self.settings.rate_limit_requests // 4) if self.settings else 30)
        destructive_rate = max(1, (self.settings.rate_limit_requests // 20) if self.settings else 5)
        return [
            RoutePolicy("/a2a/agent-card", ("GET",), "read", "none", read_rate),
            RoutePolicy("/a2a/discover", ("POST",), "read", "none", read_rate),
            RoutePolicy("/a2a/delegate", ("POST",), "write", "standard", write_rate),
            RoutePolicy("/a2a/confirm", ("POST",), "read", "none", read_rate),
            RoutePolicy("/a2a/audit", ("GET",), "admin", "none", read_rate),
            RoutePolicy("tool://*", ("POST",), "read", "standard", read_rate),
            RoutePolicy("tool://write", ("POST",), "write", "standard", write_rate),
            RoutePolicy(
                "tool://destructive", ("POST",), "destructive", "critical", destructive_rate
            ),
        ]

    @staticmethod
    def _normalize_tool_name(tool_name: str) -> str:
        return tool_name.strip().lower()

    @staticmethod
    def _params_hash(params: Mapping[str, Any]) -> str:
        """Create a stable hash for confirmation tokens."""
        items = sorted((str(key), repr(value)) for key, value in params.items())
        digest = sha256(repr(items).encode("utf-8", errors="ignore")).hexdigest()
        return digest

    def _classify_tool(self, tool_name: str, params: Mapping[str, Any]) -> tuple[str, RoutePolicy]:
        normalized = self._normalize_tool_name(tool_name)
        if normalized.startswith(self._DESTRUCTIVE_PREFIXES) or any(
            keyword in normalized
            for keyword in (
                "delete",
                "remove",
                "reset",
                "factory_reset",
                "revoke",
                "purge",
                "wipe",
                "destroy",
            )
        ):
            return "destructive", RoutePolicy(
                path=f"tool://{normalized}",
                methods=("POST", "DELETE"),
                requiredAuth="destructive",
                confirmationLevel="critical",
                rateLimit=max(1, (self.settings.rate_limit_requests // 20) if self.settings else 5),
            )

        if normalized.startswith(self._WRITE_PREFIXES) or any(
            keyword in normalized
            for keyword in (
                "create",
                "update",
                "patch",
                "set",
                "enable",
                "disable",
                "execute",
                "assign",
                "unassign",
                "start",
                "stop",
                "restart",
                "reboot",
                "adopt",
                "sync",
            )
        ):
            return "write", RoutePolicy(
                path=f"tool://{normalized}",
                methods=("POST", "PUT", "PATCH"),
                requiredAuth="write",
                confirmationLevel="standard",
                rateLimit=max(1, (self.settings.rate_limit_requests // 4) if self.settings else 30),
            )

        return "read", RoutePolicy(
            path=f"tool://{normalized}",
            methods=("GET", "POST"),
            requiredAuth="read",
            confirmationLevel="none",
            rateLimit=self.settings.rate_limit_requests if self.settings else 120,
        )

    def _find_policy(self, tool_name: str) -> RoutePolicy:
        normalized = self._normalize_tool_name(tool_name)
        for policy in self._policies:
            if policy.path in {"tool://*", f"tool://{normalized}"}:
                return policy
        level, inferred = self._classify_tool(normalized, {})
        if level == "destructive":
            return inferred
        if level == "write":
            return inferred
        return inferred

    def requires_confirmation(self, tool_name: str, params: Mapping[str, Any]) -> bool:
        """Return True when a tool call should be explicitly confirmed."""
        normalized = self._normalize_tool_name(tool_name)
        if any(bool(params.get(key)) for key in self._CONFIRMATION_KEYS):
            return False
        risk_level, _ = self._classify_tool(normalized, params)
        if risk_level == "destructive":
            return True
        if risk_level == "write":
            # Treat device removals and configuration mutation as confirmable actions.
            destructive_markers = (
                "remove",
                "delete",
                "reset",
                "revoke",
                "factory",
                "update",
                "change",
                "configure",
                "provision",
                "unassign",
            )
            return any(marker in normalized for marker in destructive_markers) or bool(
                params.get("requires_confirmation")
            )
        return bool(params.get("requires_confirmation"))

    def check_rate_limit(self, agent_id: str, tool_name: str) -> bool:
        """Check whether the given agent may invoke the requested tool."""
        policy = self._find_policy(tool_name)
        key = (agent_id, self._normalize_tool_name(tool_name))
        period_seconds = self.settings.rate_limit_period if self.settings else 60
        now = datetime.now(tz=timezone.utc).timestamp()
        window_start = now - period_seconds

        with self._lock:
            window = self._request_windows[key]
            while window and window[0] < window_start:
                window.popleft()
            if len(window) >= policy.rateLimit:
                self.logger.warning(
                    "A2A rate limit exceeded", extra={"agent_id": agent_id, "tool_name": tool_name}
                )
                return False
            window.append(now)
            return True

    def _permissions_allow(self, permissions: set[str], required: str) -> bool:
        permission_set = {permission.lower() for permission in permissions}
        if "admin" in permission_set:
            return True
        if required == "read":
            return bool(permission_set & {"read", "write", "destructive"})
        if required == "write":
            return bool(permission_set & {"write", "destructive"})
        if required == "destructive":
            return "destructive" in permission_set
        return required in permission_set

    def validate_safety_constraints(
        self,
        tool_name: str,
        params: Mapping[str, Any],
        auth_context: Any,
    ) -> SafetyResult:
        """Validate auth, safety, and rate-limit constraints for a tool call."""
        policy = self._find_policy(tool_name)
        normalized = self._normalize_tool_name(tool_name)
        risk_level, inferred_policy = self._classify_tool(normalized, params)
        policy = policy if policy.path != "tool://*" else inferred_policy

        if auth_context is None:
            return SafetyResult(False, risk_level, "authentication required", policy=policy)

        permissions = set(getattr(auth_context, "permissions", set()) or set())
        if not self._permissions_allow(permissions, policy.requiredAuth):
            return SafetyResult(
                False,
                risk_level,
                f"missing required permission: {policy.requiredAuth}",
                policy=policy,
            )

        agent_id = str(
            getattr(auth_context, "credentials", {}).get("agent_id")
            or getattr(auth_context, "credentials", {}).get("client_id")
            or getattr(auth_context, "credentials", {}).get("subject")
            or getattr(auth_context, "credentials", {}).get("sub")
            or "anonymous"
        )
        if not self.check_rate_limit(agent_id, normalized):
            return SafetyResult(
                False,
                risk_level,
                "rate limit exceeded",
                rate_limited=True,
                policy=policy,
            )

        if self.requires_confirmation(normalized, params):
            return SafetyResult(
                False,
                risk_level,
                "confirmation required",
                requires_confirmation=True,
                policy=policy,
            )

        return SafetyResult(True, risk_level, "allowed", policy=policy)


class ConfirmationWorkflow:
    """Track confirmation requests for safety-sensitive actions."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        """Set how long an issued confirmation token stays valid, in seconds."""
        self.ttl_seconds = ttl_seconds
        self._lock = RLock()
        self._tokens: dict[str, ConfirmationToken] = {}
        self.logger = get_logger(__name__)

    def request_confirmation(
        self, tool_name: str, params: Mapping[str, Any], reason: str
    ) -> ConfirmationToken:
        """Create a confirmation token for a pending action."""
        now = datetime.now(tz=timezone.utc)
        token = ConfirmationToken(
            token=token_urlsafe(32),
            tool_name=tool_name,
            params_hash=SafetyController._params_hash(params),
            reason=reason,
            created_at=now,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )
        with self._lock:
            self._tokens[token.token] = token
        return token

    def verify_confirmation(self, token: ConfirmationToken | str, response: Any) -> bool:
        """Return True when the response matches an active confirmation token."""
        token_value = token.token if isinstance(token, ConfirmationToken) else token
        with self._lock:
            stored = self._tokens.get(token_value)
            if stored is None:
                return False
            if datetime.now(tz=timezone.utc) >= stored.expires_at:
                self._tokens.pop(token_value, None)
                return False

            approved = False
            response_token = None
            if isinstance(response, bool):
                approved = response
            elif isinstance(response, str):
                approved = response.lower() in {"true", "yes", "approved", "confirm"}
                response_token = response
            elif isinstance(response, Mapping):
                approved = bool(
                    response.get("approved")
                    or response.get("confirmed")
                    or response.get("ok")
                    or response.get("allow")
                )
                response_token = response.get("token") or response.get("confirmation_token")
                expected_hash = response.get("params_hash")
                if expected_hash and expected_hash != stored.params_hash:
                    return False
            else:
                approved = bool(response)

            if response_token and not compare_digest(str(response_token), token_value):
                return False
            if approved:
                stored.confirmed = True
            return approved

    def expire_confirmation(self, token: ConfirmationToken | str) -> None:
        """Remove a token from the pending confirmation store."""
        token_value = token.token if isinstance(token, ConfirmationToken) else token
        with self._lock:
            self._tokens.pop(token_value, None)


__all__ = [
    "RoutePolicy",
    "SafetyResult",
    "ConfirmationToken",
    "SafetyController",
    "ConfirmationWorkflow",
]
