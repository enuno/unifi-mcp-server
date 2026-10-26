"""HTTP handlers for the UniFi MCP A2A protocol surface.

The functions in this module are framework-agnostic so they can be mounted
onto FastMCP's HTTP transport, a Starlette/FastAPI app, or any compatible
ASGI adapter. The handlers intentionally return plain JSON-serializable
structures.

The agent card and the discovery manifest are both built from the live tool
registry through :mod:`src.a2a.capabilities`, so a client sees the tools this
deployment registered rather than a hand-maintained list.
"""

from __future__ import annotations

import importlib.metadata
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..config import APIType, Settings
from ..utils import get_logger
from .audit import AuditLog, AuditLogger, get_audit_logger
from .auth import AuthManager, current_caller_role
from .capabilities import advertised_api_modes, advertised_capabilities, summarize_capabilities
from .route_policy import ConfirmationWorkflow, SafetyController, SafetyResult

try:
    _SERVER_VERSION = importlib.metadata.version("unifi-mcp-server")
except importlib.metadata.PackageNotFoundError:
    _SERVER_VERSION = "unknown"


ToolExecutor = Callable[[str, dict[str, Any]], Any | Awaitable[Any]]


@dataclass(slots=True)
class A2AState:
    """Mutable state shared by the A2A HTTP handlers.

    Attributes:
        settings: The server settings.
        audit_logger: Where delegated calls are recorded.
        auth_manager: The A2A authentication and authorization layer.
        safety_controller: The risk classification and rate limiter.
        confirmation_workflow: The pending-confirmation store.
        tool_executor: Runs a delegated tool call. When None, the delegation
            endpoint reports that it cannot execute rather than pretending to
            succeed.
        mcp: The FastMCP server whose registered tools describe this
            deployment.
    """

    settings: Settings | None = None
    audit_logger: AuditLogger = field(default_factory=get_audit_logger)
    auth_manager: AuthManager = field(default_factory=AuthManager)
    safety_controller: SafetyController = field(default_factory=SafetyController)
    confirmation_workflow: ConfirmationWorkflow = field(default_factory=ConfirmationWorkflow)
    tool_executor: ToolExecutor | None = None
    mcp: Any = None


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
        decoded = await result if hasattr(result, "__await__") else result
        return dict(decoded) if isinstance(decoded, Mapping) else {}
    if hasattr(request, "body"):
        body = request.body()
        raw = await body if hasattr(body, "__await__") else body
        if isinstance(raw, bytes) and raw:
            raw = raw.decode("utf-8")
        if isinstance(raw, str) and raw:
            decoded = json.loads(raw)
            return dict(decoded) if isinstance(decoded, Mapping) else {}
    return {}


def get_agent_card_handler(state: A2AState | None = None) -> dict[str, Any]:
    """Return the A2A agent card advertised by this service.

    The card is built from the live tool registry, so it lists the skills
    this deployment registered and the capabilities those skills imply.

    Args:
        state: The shared A2A state. When it carries an MCP server and
            settings, the card is built from them; otherwise a card
            describing an empty deployment is returned.

    Returns:
        The card document.
    """
    active_state = _state(state)
    from .agent_card import build_agent_card

    if active_state.mcp is None or active_state.settings is None:
        return {
            "protocolVersion": "0.3.0",
            "name": "unifi-mcp-server",
            "description": "UniFi Network and Protect control surface.",
            "url": "/a2a",
            "preferredTransport": "HTTP+JSON",
            "version": _SERVER_VERSION,
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": False,
            },
            "skills": [],
            "defaultInputModes": ["application/json"],
            "defaultOutputModes": ["application/json"],
        }
    return build_agent_card(active_state.mcp, active_state.settings)


async def discover_handler(
    payload: Mapping[str, Any] | None = None,
    *,
    state: A2AState | None = None,
) -> dict[str, Any]:
    """Return the capability manifest for agent discovery.

    The manifest carries the same live tool surface as the agent card, plus
    the per-domain tool inventory an orchestrator needs to pick a task.

    Args:
        payload: Optional request payload. ``transport`` overrides the
            reported transport, and ``include_audit`` / ``include_rate_limits``
            add the optional sections.
        state: The shared A2A state.

    Returns:
        The manifest.
    """
    active_state = _state(state)
    payload = payload or {}

    manifest: dict[str, Any] = {
        "agent": get_agent_card_handler(active_state),
        "transport": payload.get("transport") or "streamable_http",
    }

    if active_state.mcp is not None and active_state.settings is not None:
        summary = summarize_capabilities(active_state.mcp, active_state.settings)
        manifest["api_modes"] = advertised_api_modes(summary)
        manifest["capabilities"] = advertised_capabilities(summary)
        manifest["domains"] = {domain: list(summary.tools_in(domain)) for domain in summary.domains}
        manifest["tool_counts"] = {
            "total": summary.tool_count,
            "read": summary.read_count,
            "write": summary.write_count,
            "destructive": summary.destructive_count,
        }
    else:
        manifest["api_modes"] = [APIType.LOCAL.value]
        manifest["capabilities"] = []
        manifest["domains"] = {}
        manifest["tool_counts"] = {"total": 0, "read": 0, "write": 0, "destructive": 0}

    if payload.get("include_audit"):
        manifest["audit"] = {"enabled": True, "endpoint": "/a2a/audit"}
    if payload.get("include_rate_limits"):
        policies = active_state.safety_controller._build_default_policies()
        manifest["rate_limits"] = {
            "read": policies[0].rateLimit,
            "write": policies[2].rateLimit,
            "destructive": policies[6].rateLimit,
        }
    return manifest


async def delegate_handler(
    payload: Mapping[str, Any],
    *,
    state: A2AState | None = None,
) -> dict[str, Any]:
    """Validate, audit, and execute a delegated tool call.

    The payload should contain at minimum ``tool_name`` and ``params``.

    Authorization uses the server's own role model, not a permission list
    supplied by the caller: the bearer token that authenticated the request
    determines what the caller may do, and the tool registry's tier
    determines what the call needs. A caller cannot widen its own access by
    naming permissions in the payload.

    Args:
        payload: The delegation request.
        state: The shared A2A state.

    Returns:
        The delegation outcome.
    """
    active_state = _state(state)
    tool_name = str(payload.get("tool_name") or payload.get("toolName") or "").strip()
    params = dict(payload.get("params") or payload.get("arguments") or {})
    agent_id = _agent_id_from_payload(payload)
    started = datetime.now(tz=UTC)

    if not tool_name:
        return {"status": "error", "error": "tool_name is required"}

    mode = active_state.settings.api_type.value if active_state.settings else APIType.LOCAL.value
    auth_context = active_state.auth_manager.authenticate(
        mode,
        active_state.auth_manager.credentials_for_caller(payload, current_caller_role.get()),
    )
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
        active_state.confirmation_workflow.remember_call(token.token, tool_name, params)
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
        return {
            "status": "unavailable",
            "tool_name": tool_name,
            "error": "this deployment has no tool executor configured",
            "risk_level": safety.risk_level,
        }

    try:
        result = executor(tool_name, params)
        if hasattr(result, "__await__"):
            result = await result
    except Exception as exc:
        # A failing delegated call is reported, not raised: the route has
        # already answered with 200 for the other outcomes.
        logger.warning("Delegated tool call failed", extra={"tool_name": tool_name})
        return {
            "status": "error",
            "tool_name": tool_name,
            "error": str(exc),
            "risk_level": safety.risk_level,
        }

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
    """Handle a response to a previously issued confirmation request.

    An approved confirmation runs the call that was held, with the same
    authorization and safety checks applied again at that moment. A rejected
    or expired confirmation runs nothing.

    Args:
        payload: The confirmation response.
        state: The shared A2A state.

    Returns:
        The confirmation outcome.
    """
    active_state = _state(state)
    token_value = str(payload.get("token") or payload.get("confirmation_token") or "").strip()
    response = payload.get("response")
    if not token_value:
        return {"status": "error", "error": "confirmation token is required"}

    approved = active_state.confirmation_workflow.verify_confirmation(
        token_value, response or payload
    )
    if not approved:
        return {"status": "rejected", "token": token_value}

    pending = active_state.confirmation_workflow.take_call(token_value)
    if pending is None:
        active_state.confirmation_workflow.expire_confirmation(token_value)
        return {
            "status": "error",
            "token": token_value,
            "error": "no pending call for this confirmation token",
        }

    tool_name, params = pending

    # The confirmation authorises the call; it does not replace the
    # authorization. A token is a bearer capability, so it can be handed to
    # another caller, and the role that requested it may have been the only
    # reason the call was allowed. The confirming caller is therefore
    # re-authorized here, against the same role model the delegation path
    # uses, before anything runs.
    mode = active_state.settings.api_type.value if active_state.settings else APIType.LOCAL.value
    auth_context = active_state.auth_manager.authenticate(
        mode,
        active_state.auth_manager.credentials_for_caller(payload, current_caller_role.get()),
    )
    safety = active_state.safety_controller.check_execution_constraints(
        tool_name, params, auth_context
    )
    if not safety.allowed:
        active_state.confirmation_workflow.expire_confirmation(token_value)
        auth_failure = safety.reason.startswith(
            ("missing required permission", "authentication required")
        )
        return {
            "status": "denied" if auth_failure else "error",
            "token": token_value,
            "tool_name": tool_name,
            "error": safety.reason,
            "rate_limited": safety.rate_limited,
        }

    executor = active_state.tool_executor
    if executor is None:
        active_state.confirmation_workflow.expire_confirmation(token_value)
        return {
            "status": "unavailable",
            "token": token_value,
            "tool_name": tool_name,
            "error": "this deployment has no tool executor configured",
        }

    try:
        result = executor(tool_name, params)
        if hasattr(result, "__await__"):
            result = await result
    except Exception as exc:
        active_state.confirmation_workflow.expire_confirmation(token_value)
        logger.warning("Confirmed tool call failed", extra={"tool_name": tool_name})
        return {
            "status": "error",
            "token": token_value,
            "tool_name": tool_name,
            "error": str(exc),
        }

    active_state.confirmation_workflow.expire_confirmation(token_value)
    active_state.audit_logger.log_invocation(
        AuditLog(
            timestamp=datetime.now(tz=UTC),
            agent_id=_agent_id_from_payload(payload),
            tool_name=tool_name,
            params=params,
            result=result,
            safety_level=safety.risk_level,
            duration_ms=0.0,
        )
    )
    return {
        "status": "ok",
        "token": token_value,
        "tool_name": tool_name,
        "result": result,
    }


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
        """Bind the router to an A2A state container, creating one if omitted."""
        self.state = _state(state)
        self.logger = get_logger(__name__)

    async def route(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Dispatch a request to the handler registered for its method and path."""
        payload = payload or {}
        method = method.upper()
        if method == "GET" and path in ("/a2a/agent-card", "/.well-known/agent-card.json"):
            return get_agent_card_handler(self.state)
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
                lambda request: get_agent_card_handler(self.state),
                methods=["GET"],
            )
            app.add_route(
                "/.well-known/agent-card.json",
                lambda request: get_agent_card_handler(self.state),
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
            if message.get("type") == "http.disconnect":
                return  # terminal: the client is gone, no more body will arrive
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
