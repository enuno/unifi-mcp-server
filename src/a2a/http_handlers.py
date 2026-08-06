"""HTTP handlers for the UniFi MCP A2A protocol surface.

The functions in this module are framework-agnostic so they can be mounted onto
FastMCP's HTTP transport, a Starlette/FastAPI app, or any compatible ASGI
adapter. The handlers intentionally return plain JSON-serializable structures.
"""

from __future__ import annotations

import importlib.metadata
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, Mapping

from ..config import APIType, Settings
from ..utils import get_logger
from .audit import AuditLog, AuditLogger, get_audit_logger
from .auth import AuthManager
from .route_policy import ConfirmationWorkflow, SafetyController, SafetyResult

try:
    _SERVER_VERSION = importlib.metadata.version("unifi-mcp-server")
except importlib.metadata.PackageNotFoundError:
    _SERVER_VERSION = "unknown"


ToolExecutor = Callable[[str, dict[str, Any]], Any | Awaitable[Any]]


@dataclass(slots=True)
class A2AState:
    """Mutable state shared by the A2A HTTP handlers."""

    settings: Settings | None = None
    audit_logger: AuditLogger = field(default_factory=get_audit_logger)
    auth_manager: AuthManager = field(default_factory=AuthManager)
    safety_controller: SafetyController = field(default_factory=SafetyController)
    confirmation_workflow: ConfirmationWorkflow = field(default_factory=ConfirmationWorkflow)
    tool_executor: ToolExecutor | None = None


_STATE = A2AState()
logger = get_logger(__name__)


def _state(state: A2AState | None = None) -> A2AState:
    return state or _STATE


def _agent_id_from_payload(payload: Mapping[str, Any]) -> str:
    return str(
        payload.get("agent_id")
        or payload.get("agentId")
        or payload.get("client_id")
        or payload.get("clientId")
        or payload.get("subject")
        or payload.get("sub")
        or "anonymous"
    )


async def _payload_from_request(request: Any) -> dict[str, Any]:
    """Extract a JSON payload from a request object or return an empty mapping."""
    if request is None:
        return {}
    if isinstance(request, Mapping):
        return dict(request)
    if hasattr(request, "json"):
        result = request.json()
        return dict(await result) if hasattr(result, "__await__") else dict(result)
    if hasattr(request, "body"):
        body = request.body()
        raw = await body if hasattr(body, "__await__") else body
        if isinstance(raw, bytes) and raw:
            return json.loads(raw.decode("utf-8"))
        if isinstance(raw, str) and raw:
            return json.loads(raw)
    return {}


def get_agent_card_handler() -> dict[str, Any]:
    """Return the A2A agent card advertised by this service."""
    return {
        "name": "unifi-mcp-server",
        "description": "MCP server for managing UniFi Network, Protect, Site Manager, and A2A delegation",
        "version": _SERVER_VERSION,
        "protocol": "MCP/1.0",
        "capabilities": [
            "network-management",
            "multi-site",
            "audit-log",
            "safety-controls",
            "multi-auth",
        ],
        "authentication": {
            "schemes": ["bearer", "api-key"],
            "modes": [APIType.LOCAL.value, APIType.CLOUD_V1.value, APIType.CLOUD_EA.value],
            "scopes": ["read", "write", "destructive", "admin"],
        },
        "tools_manifest_url": "/a2a/discover",
        "delegate_url": "/a2a/delegate",
        "audit_url": "/a2a/audit",
        "contact": {"url": "https://github.com/enuno/unifi-mcp-server"},
    }


async def discover_handler(
    payload: Mapping[str, Any] | None = None,
    *,
    state: A2AState | None = None,
) -> dict[str, Any]:
    """Return a lightweight skills manifest for agent discovery."""
    payload = payload or {}
    manifest = {
        "agent": get_agent_card_handler(),
        "skills": [
            {
                "name": "read-network-state",
                "description": "Read-only site, client, device, and topology queries.",
                "risk": "read",
            },
            {
                "name": "mutate-network-state",
                "description": "Create and update UniFi resources.",
                "risk": "write",
            },
            {
                "name": "destructive-operations",
                "description": "Removal, reset, and other irreversible actions.",
                "risk": "destructive",
            },
        ],
        "transport": payload.get("transport") or "streamable_http",
        "api_modes": [APIType.LOCAL.value, APIType.CLOUD_V1.value, APIType.CLOUD_EA.value],
    }
    if payload.get("include_audit"):
        manifest["audit"] = {"enabled": True, "endpoint": "/a2a/audit"}
    if payload.get("include_rate_limits"):
        active_state = _state(state)
        manifest["rate_limits"] = {
            "read": active_state.safety_controller._build_default_policies()[0].rateLimit,
            "write": active_state.safety_controller._build_default_policies()[2].rateLimit,
            "destructive": active_state.safety_controller._build_default_policies()[6].rateLimit,
        }
    return manifest


async def delegate_handler(
    payload: Mapping[str, Any],
    *,
    state: A2AState | None = None,
) -> dict[str, Any]:
    """Validate, audit, and execute a delegated tool call.

    The payload should contain at minimum ``tool_name`` and ``params``. Optional
    keys include ``auth`` (credentials), ``agent_id``, and ``confirmation``.
    """
    active_state = _state(state)
    tool_name = str(payload.get("tool_name") or payload.get("toolName") or "").strip()
    params = dict(payload.get("params") or payload.get("arguments") or {})
    auth_payload = dict(payload.get("auth") or payload.get("credentials") or {})
    agent_id = _agent_id_from_payload(payload)
    started = datetime.now(tz=UTC)

    if not tool_name:
        return {"status": "error", "error": "tool_name is required"}

    mode = auth_payload.get("mode") or payload.get("mode") or APIType.LOCAL.value
    auth_context = active_state.auth_manager.authenticate(mode, auth_payload)
    if not active_state.auth_manager.validate_permissions(auth_context, tool_name):
        return {"status": "denied", "error": "insufficient permissions", "tool_name": tool_name}

    safety: SafetyResult = active_state.safety_controller.validate_safety_constraints(
        tool_name,
        params,
        auth_context,
    )
    if safety.requires_confirmation:
        token = active_state.confirmation_workflow.request_confirmation(
            tool_name,
            params,
            reason=f"{safety.risk_level} action requires confirmation",
        )
        return {
            "status": "confirmation_required",
            "tool_name": tool_name,
            "confirmation_token": token.token,
            "expires_at": token.expires_at.isoformat(),
            "reason": token.reason,
        }
    if not safety.allowed:
        return {
            "status": "denied",
            "tool_name": tool_name,
            "error": safety.reason,
            "risk_level": safety.risk_level,
        }

    executor = active_state.tool_executor
    if executor is None:
        result: Any = {
            "status": "accepted",
            "tool_name": tool_name,
            "message": "no tool executor configured",
        }
    else:
        result = executor(tool_name, params)
        if hasattr(result, "__await__"):
            result = await result  # type: ignore[func-returns-value]

    duration_ms = (datetime.now(tz=UTC) - started).total_seconds() * 1000.0
    active_state.audit_logger.log_invocation(
        AuditLog(
            timestamp=datetime.now(tz=UTC),
            agent_id=agent_id,
            tool_name=tool_name,
            params=params,
            result=result,
            safety_level=safety.risk_level,
            duration_ms=duration_ms,
        )
    )
    return {
        "status": "ok",
        "tool_name": tool_name,
        "result": result,
        "safety_level": safety.risk_level,
        "duration_ms": duration_ms,
    }


async def confirm_handler(
    payload: Mapping[str, Any],
    *,
    state: A2AState | None = None,
) -> dict[str, Any]:
    """Handle a response to a previously issued confirmation request."""
    active_state = _state(state)
    token_value = str(payload.get("token") or payload.get("confirmation_token") or "").strip()
    response = payload.get("response")
    if not token_value:
        return {"status": "error", "error": "confirmation token is required"}

    approved = active_state.confirmation_workflow.verify_confirmation(
        token_value, response or payload
    )
    if approved:
        active_state.confirmation_workflow.expire_confirmation(token_value)
        return {"status": "approved", "token": token_value}
    return {"status": "rejected", "token": token_value}


async def get_audit_handler(
    payload: Mapping[str, Any] | None = None,
    *,
    state: A2AState | None = None,
) -> dict[str, Any]:
    """Return filtered audit entries for delegated A2A activity."""
    active_state = _state(state)
    payload = payload or {}
    entries = active_state.audit_logger.get_audit_trail(
        agent_id=payload.get("agent_id") or payload.get("agentId"),
        tool_name=payload.get("tool_name") or payload.get("toolName"),
        start=payload.get("start"),
        end=payload.get("end"),
    )
    return {
        "count": len(entries),
        "entries": [
            {
                **asdict(entry),
                "timestamp": entry.timestamp.isoformat(),
            }
            for entry in entries
        ],
    }


class A2AHTTPRouter:
    """Framework-agnostic router for the A2A HTTP surface."""

    def __init__(self, state: A2AState | None = None) -> None:
        self.state = _state(state)
        self.logger = get_logger(__name__)

    async def route(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = payload or {}
        method = method.upper()
        if method == "GET" and path == "/a2a/agent-card":
            return get_agent_card_handler()
        if method == "POST" and path == "/a2a/discover":
            return await discover_handler(payload, state=self.state)
        if method == "POST" and path == "/a2a/delegate":
            return await delegate_handler(payload, state=self.state)
        if method == "POST" and path == "/a2a/confirm":
            return await confirm_handler(payload, state=self.state)
        if method == "GET" and path == "/a2a/audit":
            return await get_audit_handler(payload, state=self.state)
        return {"status": "error", "error": f"unknown A2A route: {method} {path}"}

    async def _request_handler(self, method: str, path: str, request: Any) -> dict[str, Any]:
        payload = await _payload_from_request(request)
        return await self.route(method, path, payload)

    def mount(self, app: Any) -> Any:
        """Attempt to mount handlers onto a FastMCP/ASGI-compatible app.

        The method intentionally uses duck typing so it works with FastMCP's HTTP
        transport, Starlette, FastAPI, or custom ASGI wrappers without pulling in
        an additional dependency.
        """

        if hasattr(app, "add_route"):
            app.add_route(
                "/a2a/agent-card",
                lambda request: get_agent_card_handler(),
                methods=["GET"],
            )
            app.add_route(
                "/a2a/discover",
                lambda request: self._request_handler("POST", "/a2a/discover", request),
                methods=["POST"],
            )
            app.add_route(
                "/a2a/delegate",
                lambda request: self._request_handler("POST", "/a2a/delegate", request),
                methods=["POST"],
            )
            app.add_route(
                "/a2a/confirm",
                lambda request: self._request_handler("POST", "/a2a/confirm", request),
                methods=["POST"],
            )
            app.add_route(
                "/a2a/audit",
                lambda request: self._request_handler("GET", "/a2a/audit", request),
                methods=["GET"],
            )
            return app

        if hasattr(app, "mount"):
            app.mount("/a2a", self)
            return app

        raise TypeError("Unsupported application type for A2A router mounting")

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """Minimal ASGI entrypoint for wrapper compatibility."""
        if scope.get("type") != "http":
            raise TypeError("A2AHTTPRouter only handles HTTP scopes")
        path = scope.get("path", "")
        method = scope.get("method", "GET")
        body = bytearray()
        while True:
            message = await receive()
            if message.get("type") != "http.request":
                continue
            body.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break
        payload: dict[str, Any] = {}
        if body:
            payload = json.loads(body.decode("utf-8"))
        response = await self.route(method, path, payload)
        body_bytes = json.dumps(response, default=str).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body_bytes})


__all__ = [
    "A2AState",
    "A2AHTTPRouter",
    "confirm_handler",
    "delegate_handler",
    "discover_handler",
    "get_agent_card_handler",
    "get_audit_handler",
]
