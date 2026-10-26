"""End-to-end tests for the A2A HTTP surface.

These drive the real Streamable HTTP endpoint with real bearer tokens, so
they cover the parts a client actually meets: the card, the discovery
manifest, the well-known path, the role gates and the delegation path.

No controller is contacted. A delegated call runs against a stub tool that
the test registers, so the network is never touched.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

_BASE_ENV = {
    "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
    "UNIFI_API_TYPE": "local",
    "UNIFI_LOCAL_HOST": "127.0.0.1",
    "AGNOST_ENABLED": "false",
}

_TOKENS = "viewer:tok-view,operator:tok-op,admin:tok-admin,fleet-admin:tok-fleet"


def _reload_main(**extra_env: str) -> Any:
    """Re-import src.main with a clean module cache under a known env."""
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]
    with patch.dict("os.environ", {**_BASE_ENV, **extra_env}, clear=False):
        return importlib.import_module("src.main")


def _auth(token: str) -> dict[str, str]:
    """Return the Authorization header for a token."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def server() -> Any:
    """Return a running server with the A2A routes registered.

    The server is built once for the module: re-importing it for every test
    costs several seconds each time and the configuration is identical.
    """
    main = _reload_main(MCP_SERVER_TRANSPORT="streamable_http", MCP_AUTH_TOKEN=_TOKENS)
    # ``run`` is stubbed so importing the module does not start a listener.
    main.mcp.run = lambda *args, **kwargs: None
    main.main()
    return main


@pytest.fixture
def client(server: Any):
    """Return a TestClient for the running server."""
    with TestClient(server.mcp.http_app(transport="streamable-http")) as test_client:
        yield test_client


class TestAgentCardEndpoint:
    def test_the_card_is_served(self, client: TestClient) -> None:
        response = client.get("/a2a/agent-card", headers=_auth("tok-view"))

        assert response.status_code == 200
        card = response.json()
        assert card["name"] == "unifi-mcp-server"
        assert card["protocolVersion"] == "0.3.0"

    def test_the_card_lists_the_registered_tools(self, client: TestClient) -> None:
        card = client.get("/a2a/agent-card", headers=_auth("tok-view")).json()

        assert len(card["skills"]) == card["metadata"]["toolCount"]
        assert card["metadata"]["toolCount"] > 100

    def test_the_card_declares_only_the_implemented_capabilities(self, client: TestClient) -> None:
        card = client.get("/a2a/agent-card", headers=_auth("tok-view")).json()

        assert card["capabilities"] == {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        }

    def test_the_card_carries_no_credential(self, client: TestClient) -> None:
        body = client.get("/a2a/agent-card", headers=_auth("tok-view")).text

        assert "test-key" not in body
        assert "UNIFI_API_KEY" not in body

    def test_the_card_carries_no_controller_address(self, client: TestClient) -> None:
        """The card names this server, never the controller behind it."""
        card = client.get("/a2a/agent-card", headers=_auth("tok-view")).json()

        assert "localHost" not in card["metadata"]
        assert "cloudApiUrl" not in card["metadata"]

    def test_the_card_requires_a_token(self, client: TestClient) -> None:
        assert client.get("/a2a/agent-card").status_code == 401

    def test_the_card_rejects_a_wrong_token(self, client: TestClient) -> None:
        assert client.get("/a2a/agent-card", headers=_auth("wrong")).status_code == 401


class TestWellKnownEndpoint:
    """SPEC.md requires the well-known path when HTTP transport is enabled."""

    def test_the_well_known_path_serves_the_card(self, client: TestClient) -> None:
        response = client.get("/.well-known/agent-card.json", headers=_auth("tok-view"))

        assert response.status_code == 200
        assert response.json()["name"] == "unifi-mcp-server"

    def test_the_well_known_path_serves_the_same_card(self, client: TestClient) -> None:
        well_known = client.get("/.well-known/agent-card.json", headers=_auth("tok-view")).json()
        card = client.get("/a2a/agent-card", headers=_auth("tok-view")).json()

        assert well_known == card

    def test_the_well_known_path_requires_a_token(self, client: TestClient) -> None:
        assert client.get("/.well-known/agent-card.json").status_code == 401


class TestDiscoveryEndpoint:
    def test_the_manifest_lists_the_domains(self, client: TestClient) -> None:
        manifest = client.post("/a2a/discover", headers=_auth("tok-view"), json={}).json()

        assert "network" in manifest["domains"]
        assert "protect" in manifest["domains"]
        assert "list_sites" in manifest["domains"]["system"]

    def test_the_manifest_counts_the_tools_by_tier(self, client: TestClient) -> None:
        manifest = client.post("/a2a/discover", headers=_auth("tok-view"), json={}).json()

        counts = manifest["tool_counts"]
        assert counts["total"] == counts["read"] + counts["write"] + counts["destructive"]
        assert counts["total"] > 100

    def test_the_manifest_carries_the_card(self, client: TestClient) -> None:
        manifest = client.post("/a2a/discover", headers=_auth("tok-view"), json={}).json()

        assert manifest["agent"]["name"] == "unifi-mcp-server"
        assert len(manifest["agent"]["skills"]) == manifest["tool_counts"]["total"]

    def test_the_manifest_reports_the_running_api_mode(self, client: TestClient) -> None:
        manifest = client.post("/a2a/discover", headers=_auth("tok-view"), json={}).json()

        assert manifest["api_modes"] == ["local"]

    def test_the_optional_sections_appear_on_request(self, client: TestClient) -> None:
        manifest = client.post(
            "/a2a/discover",
            headers=_auth("tok-view"),
            json={"include_audit": True, "include_rate_limits": True},
        ).json()

        assert manifest["audit"] == {"enabled": True, "endpoint": "/a2a/audit"}
        limits = manifest["rate_limits"]
        assert limits["read"] >= limits["write"] >= limits["destructive"] >= 1

    def test_the_manifest_requires_a_token(self, client: TestClient) -> None:
        assert client.post("/a2a/discover", json={}).status_code == 401


class TestAuditEndpointRole:
    """The route policy declares the audit trail as admin-only."""

    def test_a_viewer_token_is_refused(self, client: TestClient) -> None:
        assert client.get("/a2a/audit", headers=_auth("tok-view")).status_code == 403

    def test_an_operator_token_is_refused(self, client: TestClient) -> None:
        assert client.get("/a2a/audit", headers=_auth("tok-op")).status_code == 403

    def test_an_admin_token_is_served(self, client: TestClient) -> None:
        response = client.get("/a2a/audit", headers=_auth("tok-admin"))

        assert response.status_code == 200
        assert "count" in response.json()

    def test_a_fleet_admin_token_is_served(self, client: TestClient) -> None:
        assert client.get("/a2a/audit", headers=_auth("tok-fleet")).status_code == 200

    def test_an_unauthenticated_request_is_refused(self, client: TestClient) -> None:
        assert client.get("/a2a/audit").status_code == 401


class TestDelegationAuthorization:
    """The caller's token decides what a delegated call may do."""

    def test_a_missing_tool_name_is_reported(self, client: TestClient) -> None:
        response = client.post("/a2a/delegate", headers=_auth("tok-admin"), json={})

        assert response.json()["status"] == "error"

    def test_a_payload_cannot_widen_the_callers_access(self, client: TestClient) -> None:
        """A viewer asking for destructive access is refused."""
        response = client.post(
            "/a2a/delegate",
            headers=_auth("tok-view"),
            json={
                "tool_name": "delete_firewall_zone",
                "params": {"site_id": "default", "name": "X", "confirm": True},
                "auth": {"permissions": ["destructive", "admin"]},
            },
        )

        assert response.json()["status"] == "denied"

    def test_a_write_call_without_the_right_role_is_refused(self, client: TestClient) -> None:
        """A viewer may not run a write-tier tool, whatever the payload says."""
        response = client.post(
            "/a2a/delegate",
            headers=_auth("tok-view"),
            json={"tool_name": "create_network", "params": {"site_id": "default"}},
        )

        assert response.json()["status"] == "denied"

    def test_an_unknown_tool_is_refused(self, client: TestClient) -> None:
        response = client.post(
            "/a2a/delegate",
            headers=_auth("tok-admin"),
            json={"tool_name": "no_such_tool", "params": {}},
        )

        assert response.json()["status"] in {"denied", "error"}


class TestDelegationExecution:
    """A delegated call runs a real registered tool through its wrapper."""

    @pytest.fixture(scope="class")
    def stub_server(self, server: Any) -> Any:
        """Return a server carrying one stub tool that records its call."""
        from fastmcp.tools import Tool

        from src.utils.tool_kind import read_tool

        calls: list[dict[str, Any]] = []

        @read_tool
        async def stub_site_reader(site_id: str = "default") -> dict[str, Any]:
            """Read a site without touching a controller."""
            calls.append({"site_id": site_id})
            return {"ok": True, "site_id": site_id}

        tool = Tool.from_function(stub_site_reader, name="stub_site_reader")
        server.mcp._local_provider._components["tool:stub_site_reader@"] = tool
        server.stub_calls = calls
        return server

    def test_a_delegated_read_runs_the_tool(self, stub_server: Any) -> None:
        stub_server.stub_calls.clear()
        with TestClient(stub_server.mcp.http_app(transport="streamable-http")) as client:
            response = client.post(
                "/a2a/delegate",
                headers=_auth("tok-view"),
                json={"tool_name": "stub_site_reader", "params": {"site_id": "default"}},
            )

        body = response.json()
        assert body["status"] == "ok"
        assert body["result"] == {"ok": True, "site_id": "default"}
        assert stub_server.stub_calls == [{"site_id": "default"}]

    def test_a_delegated_call_is_audited(self, stub_server: Any) -> None:
        with TestClient(stub_server.mcp.http_app(transport="streamable-http")) as client:
            client.post(
                "/a2a/delegate",
                headers=_auth("tok-view"),
                json={
                    "tool_name": "stub_site_reader",
                    "params": {"site_id": "default"},
                    "agent_id": "agent-7",
                },
            )

        import src.main as main

        entries = main.a2a_state.audit_logger.get_audit_trail()
        assert any(entry.agent_id == "agent-7" for entry in entries)

    def test_a_delegation_requires_a_token(self, stub_server: Any) -> None:
        stub_server.stub_calls.clear()
        with TestClient(stub_server.mcp.http_app(transport="streamable-http")) as client:
            response = client.post(
                "/a2a/delegate",
                json={"tool_name": "stub_site_reader", "params": {}},
            )

        assert response.status_code == 401
        assert not stub_server.stub_calls


class TestConfirmationEndpoint:
    def test_a_missing_token_is_reported(self, client: TestClient) -> None:
        response = client.post("/a2a/confirm", headers=_auth("tok-admin"), json={})

        assert response.json()["status"] == "error"

    def test_an_unknown_token_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/a2a/confirm",
            headers=_auth("tok-admin"),
            json={"token": "nope", "response": "approved"},
        )

        assert response.json()["status"] == "rejected"

    def test_confirmation_requires_a_token(self, client: TestClient) -> None:
        response = client.post("/a2a/confirm", json={"token": "x", "response": "approved"})

        assert response.status_code == 401


class TestConfirmationReauthorizes:
    """A confirmation token authorises a call; it does not replace the role.

    A confirmation token is a bearer capability: it can be handed to
    another caller, and the role that requested it may be the only reason
    the call was allowed. The confirming caller is therefore authorized
    again before the held call runs.
    """

    @pytest.fixture(scope="class")
    def stub_server(self, server: Any) -> Any:
        """Return a server carrying a stub tool that records its call."""
        from fastmcp.tools import Tool

        from src.utils.tool_kind import write_tool

        calls: list[dict[str, Any]] = []

        @write_tool
        async def stub_deleter(site_id: str = "default") -> dict[str, Any]:
            """Stand in for a destructive tool without touching a controller."""
            calls.append({"site_id": site_id})
            return {"ok": True, "site_id": site_id}

        # The name starts with a destructive prefix, so the A2A layer
        # classifies it as destructive whatever the registry says about
        # the function.
        tool = Tool.from_function(stub_deleter, name="delete_stub_thing")
        server.mcp._local_provider._components["tool:delete_stub_thing@"] = tool
        server.stub_calls = calls
        return server

    def test_a_lower_privileged_caller_cannot_confirm_someone_elses_call(
        self, stub_server: Any
    ) -> None:
        stub_server.stub_calls.clear()
        with TestClient(stub_server.mcp.http_app(transport="streamable-http")) as client:
            # An admin asks for a destructive call and is issued a token.
            issued = client.post(
                "/a2a/delegate",
                headers=_auth("tok-admin"),
                json={"tool_name": "delete_stub_thing", "params": {"site_id": "default"}},
            )
            body = issued.json()
            assert body["status"] == "confirmation_required"
            token = body["confirmation_token"]

            # A viewer redeems that token.
            confirmed = client.post(
                "/a2a/confirm",
                headers=_auth("tok-view"),
                json={"token": token, "response": True},
            )

        assert confirmed.json()["status"] == "denied"
        assert not stub_server.stub_calls, "the held call must not have run"

    def test_the_caller_who_requested_the_call_can_confirm_it(self, stub_server: Any) -> None:
        stub_server.stub_calls.clear()
        with TestClient(stub_server.mcp.http_app(transport="streamable-http")) as client:
            issued = client.post(
                "/a2a/delegate",
                headers=_auth("tok-admin"),
                json={"tool_name": "delete_stub_thing", "params": {"site_id": "default"}},
            )
            token = issued.json()["confirmation_token"]

            confirmed = client.post(
                "/a2a/confirm",
                headers=_auth("tok-admin"),
                json={"token": token, "response": True},
            )

        assert confirmed.json()["status"] == "ok"
        assert stub_server.stub_calls == [{"site_id": "default"}]


class TestConfirmationRateLimit:
    """Regression: confirmed executions consume the rate limit.

    Previously the confirmation path executed the held call without
    re-checking rate limits, so any number of confirmed calls could run
    even after the delegate path had exhausted its quota.
    """

    @pytest.fixture(scope="class")
    def rate_limited_server(self) -> Any:
        main = _reload_main(
            MCP_SERVER_TRANSPORT="streamable_http",
            MCP_AUTH_TOKEN=_TOKENS,
            UNIFI_RATE_LIMIT_REQUESTS="40",
        )
        main.mcp.run = lambda *args, **kwargs: None
        main.main()
        self._inject_stub_tool(main)
        return main

    @staticmethod
    def _inject_stub_tool(main: Any) -> None:
        """Add a destructive stub tool that records its calls."""
        from fastmcp.tools import Tool

        from src.utils.tool_kind import write_tool

        calls: list[dict[str, Any]] = []

        @write_tool
        async def stub_deleter(site_id: str = "default") -> dict[str, Any]:
            """Stand in for a destructive tool without touching a controller."""
            calls.append({"site_id": site_id})
            return {"ok": True, "site_id": site_id}

        tool = Tool.from_function(stub_deleter, name="delete_stub_thing")
        main.mcp._local_provider._components["tool:delete_stub_thing@"] = tool
        main.stub_calls = calls

    @pytest.fixture
    def rl_client(self, rate_limited_server: Any):
        with TestClient(
            rate_limited_server.mcp.http_app(transport="streamable-http")
        ) as test_client:
            yield test_client

    def test_rate_limit_is_enforced_on_confirmation(self, rl_client: TestClient) -> None:
        tokens = []
        for i in range(3):
            issued = rl_client.post(
                "/a2a/delegate",
                headers=_auth("tok-admin"),
                json={
                    "tool_name": "delete_stub_thing",
                    "params": {"site_id": f"site-{i}"},
                },
            )
            assert issued.json()["status"] == "confirmation_required"
            tokens.append(issued.json()["confirmation_token"])

        results = []
        for token in tokens:
            confirmed = rl_client.post(
                "/a2a/confirm",
                headers=_auth("tok-admin"),
                json={"token": token, "response": True},
            )
            results.append(confirmed.json()["status"])

        assert results == ["ok", "ok", "error"]
