"""Unit tests for src/a2a/http_handlers.py.

The auth manager, safety controller and audit logger are mocked so these
tests pin down the handlers' own branching: what each handler returns for
denied, confirmation-required, blocked and executed calls, and how the
router and its ASGI entry point dispatch requests.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.a2a import http_handlers as h
from src.a2a.audit import AuditLog
from src.a2a.route_policy import ConfirmationWorkflow, SafetyResult

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def _state(
    *,
    permitted: bool = True,
    safety: SafetyResult | None = None,
    executor: Any = None,
) -> h.A2AState:
    auth = MagicMock()
    auth.authenticate.return_value = MagicMock(name="auth_context")
    auth.validate_permissions.return_value = permitted
    safety_controller = MagicMock()
    safety_controller.validate_safety_constraints.return_value = safety or SafetyResult(
        allowed=True, risk_level="read", reason="ok"
    )
    return h.A2AState(
        audit_logger=MagicMock(),
        auth_manager=auth,
        safety_controller=safety_controller,
        confirmation_workflow=ConfirmationWorkflow(),
        tool_executor=executor,
    )


class TestPayloadFromRequest:
    @pytest.mark.asyncio
    async def test_none_and_mapping(self) -> None:
        assert await h._payload_from_request(None) == {}
        assert await h._payload_from_request({"a": 1}) == {"a": 1}

    @pytest.mark.asyncio
    async def test_sync_and_async_json(self) -> None:
        class Sync:
            def json(self) -> dict:
                return {"a": 1}

        class Async:
            async def json(self) -> dict:
                return {"b": 2}

        assert await h._payload_from_request(Sync()) == {"a": 1}
        assert await h._payload_from_request(Async()) == {"b": 2}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("raw", [b'{"c": 3}', '{"c": 3}'])
    async def test_body_bytes_or_str(self, raw: bytes | str) -> None:
        class Body:
            async def body(self) -> bytes | str:
                return raw

        assert await h._payload_from_request(Body()) == {"c": 3}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("raw", [b"[]", b'"text"', b"3"])
    async def test_non_object_body_is_empty_payload(self, raw: bytes) -> None:
        class Body:
            async def body(self) -> bytes:
                return raw

        assert await h._payload_from_request(Body()) == {}

    @pytest.mark.asyncio
    async def test_non_object_json_is_empty_payload(self) -> None:
        class Json:
            async def json(self) -> list:
                return [["tool_name", "x"]]

        assert await h._payload_from_request(Json()) == {}

    @pytest.mark.asyncio
    async def test_empty_body_and_unknown_object(self) -> None:
        class Body:
            def body(self) -> bytes:
                return b""

        assert await h._payload_from_request(Body()) == {}
        assert await h._payload_from_request(object()) == {}


class TestAgentId:
    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            ({"agent_id": "a"}, "a"),
            ({"agentId": "b"}, "b"),
            ({"client_id": "c"}, "c"),
            ({"sub": "d"}, "d"),
            ({}, "anonymous"),
        ],
    )
    def test_fallbacks(self, payload: dict, expected: str) -> None:
        assert h._agent_id_from_payload(payload) == expected


class TestDiscover:
    @pytest.mark.asyncio
    async def test_default_manifest(self) -> None:
        manifest = await h.discover_handler(None, state=_state())

        assert manifest["transport"] == "streamable_http"
        assert {s["risk"] for s in manifest["skills"]} == {"read", "write", "destructive"}
        assert "audit" not in manifest
        assert "rate_limits" not in manifest

    @pytest.mark.asyncio
    async def test_optional_sections(self) -> None:
        state = h.A2AState(audit_logger=MagicMock())
        manifest = await h.discover_handler(
            {"transport": "sse", "include_audit": True, "include_rate_limits": True}, state=state
        )

        assert manifest["transport"] == "sse"
        assert manifest["audit"] == {"enabled": True, "endpoint": "/a2a/audit"}
        limits = manifest["rate_limits"]
        assert limits["read"] >= limits["write"] >= limits["destructive"] >= 1


class TestDelegate:
    @pytest.mark.asyncio
    async def test_requires_tool_name(self) -> None:
        result = await h.delegate_handler({"tool_name": "  "}, state=_state())
        assert result == {"status": "error", "error": "tool_name is required"}

    @pytest.mark.asyncio
    async def test_permission_denied(self) -> None:
        state = _state(permitted=False)
        result = await h.delegate_handler({"toolName": "delete_device"}, state=state)

        assert result["status"] == "denied"
        assert result["error"] == "insufficient permissions"
        state.safety_controller.validate_safety_constraints.assert_not_called()

    @pytest.mark.asyncio
    async def test_mode_from_auth_payload(self) -> None:
        state = _state()
        await h.delegate_handler(
            {"tool_name": "list_sites", "auth": {"mode": "cloud-v1", "token": "t"}}, state=state
        )

        mode, creds = state.auth_manager.authenticate.call_args.args
        assert mode == "cloud-v1"
        assert creds == {"mode": "cloud-v1", "token": "t"}

    @pytest.mark.asyncio
    async def test_confirmation_required(self) -> None:
        safety = SafetyResult(
            allowed=False, risk_level="destructive", reason="", requires_confirmation=True
        )
        state = _state(safety=safety, executor=MagicMock())
        result = await h.delegate_handler(
            {"tool_name": "delete_device", "params": {"id": "x"}}, state=state
        )

        assert result["status"] == "confirmation_required"
        assert result["reason"] == "destructive action requires confirmation"
        assert datetime.fromisoformat(result["expires_at"]) > datetime.now(tz=UTC)
        assert result["confirmation_token"] in state.confirmation_workflow._tokens
        state.tool_executor.assert_not_called()
        state.audit_logger.log_invocation.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocked_by_safety(self) -> None:
        safety = SafetyResult(allowed=False, risk_level="write", reason="rate limited")
        state = _state(safety=safety, executor=MagicMock())
        result = await h.delegate_handler({"tool_name": "update_wlan"}, state=state)

        assert result == {
            "status": "denied",
            "tool_name": "update_wlan",
            "error": "rate limited",
            "risk_level": "write",
        }
        state.tool_executor.assert_not_called()

    @pytest.mark.asyncio
    async def test_without_executor_is_accepted_and_audited(self) -> None:
        state = _state()
        result = await h.delegate_handler(
            {"tool_name": "list_sites", "agent_id": "agent-7", "arguments": {"limit": 5}},
            state=state,
        )

        assert result["status"] == "ok"
        assert result["result"]["message"] == "no tool executor configured"
        entry = state.audit_logger.log_invocation.call_args.args[0]
        assert (entry.agent_id, entry.tool_name, entry.params) == (
            "agent-7",
            "list_sites",
            {"limit": 5},
        )
        assert entry.safety_level == "read"

    @pytest.mark.asyncio
    async def test_sync_executor(self) -> None:
        executor = MagicMock(return_value={"sites": []})
        state = _state(executor=executor)
        result = await h.delegate_handler(
            {"tool_name": "list_sites", "params": {"a": 1}}, state=state
        )

        executor.assert_called_once_with("list_sites", {"a": 1})
        assert result["result"] == {"sites": []}
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_async_executor(self) -> None:
        async def executor(name: str, params: dict) -> dict:
            return {"name": name}

        result = await h.delegate_handler(
            {"tool_name": "list_sites"}, state=_state(executor=executor)
        )

        assert result["result"] == {"name": "list_sites"}


class TestConfirm:
    @pytest.mark.asyncio
    async def test_requires_token(self) -> None:
        result = await h.confirm_handler({}, state=_state())
        assert result == {"status": "error", "error": "confirmation token is required"}

    @pytest.mark.asyncio
    async def test_approved_token_is_expired(self) -> None:
        state = _state()
        state.confirmation_workflow = MagicMock()
        state.confirmation_workflow.verify_confirmation.return_value = True

        result = await h.confirm_handler({"token": "t1", "response": "yes"}, state=state)

        assert result == {"status": "approved", "token": "t1"}
        state.confirmation_workflow.verify_confirmation.assert_called_once_with("t1", "yes")
        state.confirmation_workflow.expire_confirmation.assert_called_once_with("t1")

    @pytest.mark.asyncio
    async def test_unknown_token_rejected(self) -> None:
        result = await h.confirm_handler({"confirmation_token": "nope"}, state=_state())
        assert result == {"status": "rejected", "token": "nope"}


class TestAudit:
    @pytest.mark.asyncio
    async def test_serialises_entries(self) -> None:
        state = _state()
        entry = AuditLog(
            timestamp=NOW,
            agent_id="a",
            tool_name="list_sites",
            params={},
            result={"ok": True},
            safety_level="read",
            duration_ms=1.5,
        )
        state.audit_logger.get_audit_trail.return_value = [entry]

        result = await h.get_audit_handler({"agentId": "a", "toolName": "list_sites"}, state=state)

        state.audit_logger.get_audit_trail.assert_called_once_with(
            agent_id="a", tool_name="list_sites", start=None, end=None
        )
        assert result["count"] == 1
        assert result["entries"][0]["timestamp"] == NOW.isoformat()
        assert result["entries"][0]["duration_ms"] == 1.5

    @pytest.mark.asyncio
    async def test_no_payload(self) -> None:
        state = _state()
        state.audit_logger.get_audit_trail.return_value = []
        assert await h.get_audit_handler(state=state) == {"count": 0, "entries": []}


class TestRouter:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "key"),
        [
            ("get", "/a2a/agent-card", "name"),
            ("POST", "/a2a/discover", "skills"),
            ("POST", "/a2a/delegate", "status"),
            ("POST", "/a2a/confirm", "status"),
            ("GET", "/a2a/audit", "count"),
        ],
    )
    async def test_routes(self, method: str, path: str, key: str) -> None:
        state = _state()
        state.audit_logger.get_audit_trail.return_value = []
        result = await h.A2AHTTPRouter(state).route(method, path, None)
        assert key in result

    @pytest.mark.asyncio
    async def test_unknown_route(self) -> None:
        result = await h.A2AHTTPRouter(_state()).route("DELETE", "/a2a/delegate")
        assert result == {"status": "error", "error": "unknown A2A route: DELETE /a2a/delegate"}

    @pytest.mark.asyncio
    async def test_mount_with_add_route(self) -> None:
        state = _state()
        state.audit_logger.get_audit_trail.return_value = []
        router = h.A2AHTTPRouter(state)
        app = MagicMock(spec=["add_route"])

        assert router.mount(app) is app

        routes = {call.args[0]: call for call in app.add_route.call_args_list}
        assert set(routes) == {
            "/a2a/agent-card",
            "/a2a/discover",
            "/a2a/delegate",
            "/a2a/confirm",
            "/a2a/audit",
        }
        assert routes["/a2a/agent-card"].args[1](None)["name"] == "unifi-mcp-server"
        assert "skills" in await routes["/a2a/discover"].args[1]({})
        assert (await routes["/a2a/delegate"].args[1]({}))["status"] == "error"
        assert (await routes["/a2a/confirm"].args[1]({}))["status"] == "error"
        assert (await routes["/a2a/audit"].args[1](None))["count"] == 0

    def test_mount_with_mount(self) -> None:
        router = h.A2AHTTPRouter(_state())
        app = MagicMock(spec=["mount"])

        assert router.mount(app) is app
        app.mount.assert_called_once_with("/a2a", router)

    def test_mount_unsupported(self) -> None:
        with pytest.raises(TypeError, match="Unsupported"):
            h.A2AHTTPRouter(_state()).mount(object())


class TestAsgi:
    @staticmethod
    def _receive(*messages: dict):
        queue = list(messages)

        async def receive() -> dict:
            return queue.pop(0)

        return receive

    @pytest.mark.asyncio
    async def test_rejects_non_http(self) -> None:
        with pytest.raises(TypeError, match="HTTP scopes"):
            await h.A2AHTTPRouter(_state())({"type": "websocket"}, None, None)

    @pytest.mark.asyncio
    async def test_reads_chunked_body_and_responds(self) -> None:
        sent: list[dict] = []

        async def send(message: dict) -> None:
            sent.append(message)

        receive = self._receive(
            {"type": "lifespan.unrelated"},
            {"type": "http.request", "body": b'{"tool_', "more_body": True},
            {"type": "http.request", "body": b'name": "list_sites"}'},
        )
        scope = {"type": "http", "method": "POST", "path": "/a2a/delegate"}

        await h.A2AHTTPRouter(_state())(scope, receive, send)

        assert sent[0]["status"] == 200
        assert (b"content-type", b"application/json") in sent[0]["headers"]
        body = json.loads(sent[1]["body"])
        assert body["status"] == "ok"
        assert body["tool_name"] == "list_sites"

    @pytest.mark.asyncio
    async def test_disconnect_ends_the_request_without_a_response(self) -> None:
        # http.disconnect is terminal: receive() keeps returning it, so waiting
        # for more body would spin forever.
        send = AsyncMock()

        async def receive() -> dict:
            await asyncio.sleep(0)  # yield like a real server, so wait_for can time out
            return {"type": "http.disconnect"}

        scope = {"type": "http", "method": "POST", "path": "/a2a/delegate"}
        await asyncio.wait_for(h.A2AHTTPRouter(_state())(scope, receive, send), timeout=1)

        send.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_body_defaults(self) -> None:
        sent: list[dict] = []

        async def send(message: dict) -> None:
            sent.append(message)

        await h.A2AHTTPRouter(_state())(
            {"type": "http", "path": "/a2a/agent-card"},
            self._receive({"type": "http.request", "body": b""}),
            send,
        )

        assert json.loads(sent[1]["body"])["name"] == "unifi-mcp-server"
