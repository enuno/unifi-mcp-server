"""Tests for the A2A agent card, discovery manifest and delegation path.

These cover the claims the card makes about the deployment: that its skills
are the tools this server registered, that its capability flags follow the
configuration, that it names no credential, and that the delegation path
runs a tool through the same wrapper an MCP client would use.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp.resources.function_resource import FunctionResource
from fastmcp.tools.function_tool import FunctionTool

from src.a2a.agent_card import build_agent_card
from src.a2a.capabilities import (
    A2A_PROTOCOL_VERSION,
    advertised_api_modes,
    advertised_capabilities,
    domain_for_tool,
    summarize_capabilities,
    tool_tier,
)
from src.a2a.executor import UnknownToolError, execute_tool_call
from src.config import Settings


class FakeProvider:
    """Stand-in for a FastMCP provider exposing a ``_components`` mapping."""

    def __init__(self, components: dict[str, Any]) -> None:
        self._components = components


class FakeMCP:
    """Minimal FastMCP stand-in exposing the attributes the A2A layer reads."""

    def __init__(self, components: dict[str, Any] | None = None) -> None:
        self.providers = [FakeProvider(components or {})]
        self._mcp_server = type("Server", (), {"name": "Fake UniFi"})()


def make_tool(fn: Any, **kwargs: Any) -> FunctionTool:
    """Build a real ``FunctionTool`` so isinstance checks in src/ still hold."""
    return FunctionTool.from_function(fn, **kwargs)


def make_resource(fn: Any, uri: str, **kwargs: Any) -> FunctionResource:
    """Build a real ``FunctionResource`` for resource-discovery assertions."""
    return FunctionResource.from_function(fn, uri=uri, **kwargs)


def list_site_clients(site_id: str) -> dict[str, Any]:
    """List clients for a site."""
    return {"clients": []}


def create_site_network(site_id: str, name: str, confirm: bool = False) -> dict[str, Any]:
    """Create a network on a site."""
    return {"ok": True, "name": name}


def delete_site_device(site_id: str, confirm: bool = False) -> dict[str, Any]:
    """Delete a device from the site."""
    return {"ok": True}


@pytest.fixture
def local_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Return Settings configured for local controller access."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.0.2.10")
    return Settings()


@pytest.fixture
def cloud_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Return Settings configured for cloud access."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
    return Settings()


class TestAgentCardShape:
    """The card must carry the fields an A2A client reads."""

    def test_card_has_the_agentcard_fields(
        self, local_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(
            __import__("src.tool_registry", fromlist=["TOOL_TIERS"]).TOOL_TIERS,
            "list_site_clients",
            "read",
        )
        card = build_agent_card(FakeMCP(), local_settings)

        for field in (
            "protocolVersion",
            "name",
            "description",
            "url",
            "version",
            "capabilities",
            "skills",
            "defaultInputModes",
            "defaultOutputModes",
        ):
            assert field in card, field

    def test_protocol_version_is_the_spec_version(self, local_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), local_settings)
        assert card["protocolVersion"] == A2A_PROTOCOL_VERSION

    def test_capabilities_declare_only_what_is_implemented(self, local_settings: Settings) -> None:
        """The server has no task protocol, so it must not claim one."""
        card = build_agent_card(FakeMCP(), local_settings)

        assert card["capabilities"]["streaming"] is False
        assert card["capabilities"]["pushNotifications"] is False
        assert card["capabilities"]["stateTransitionHistory"] is False

    def test_security_scheme_describes_the_bearer_token(self, local_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), local_settings)

        assert card["securitySchemes"]["bearerAuth"]["type"] == "http"
        assert card["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
        assert card["security"] == [{"bearerAuth": []}]

    def test_url_points_at_the_running_server(self, local_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), local_settings)
        assert (
            card["url"] == f"http://{local_settings.server_host}:{local_settings.server_port}/a2a"
        )

    def test_card_names_the_repository_as_provider(self, local_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), local_settings)
        assert "github.com/enuno/unifi-mcp-server" in card["provider"]["url"]


class TestCardReflectsTheDeployment:
    """The card must describe this deployment, not a fixed template."""

    def _mcp_with(self, *tools: FunctionTool) -> FakeMCP:
        return FakeMCP({f"tool:{tool.name}@": tool for tool in tools})

    def test_skills_are_the_registered_tools(self, local_settings: Settings) -> None:
        mcp = self._mcp_with(make_tool(list_site_clients, name="list_site_clients"))
        card = build_agent_card(mcp, local_settings)

        assert [skill["name"] for skill in card["skills"]] == ["list_site_clients"]

    def test_tool_count_matches_the_registry(self, local_settings: Settings) -> None:
        mcp = self._mcp_with(
            make_tool(list_site_clients, name="list_site_clients"),
            make_tool(create_site_network, name="create_site_network"),
        )
        card = build_agent_card(mcp, local_settings)

        assert card["metadata"]["toolCount"] == 2

    def test_api_modes_list_only_the_running_mode(
        self, local_settings: Settings, cloud_settings: Settings
    ) -> None:
        local_card = build_agent_card(FakeMCP(), local_settings)
        cloud_card = build_agent_card(FakeMCP(), cloud_settings)

        assert local_card["metadata"]["apiModes"] == ["local"]
        assert cloud_card["metadata"]["apiModes"] == ["cloud-ea"]

    def test_authentication_mode_follows_the_api_type(
        self, local_settings: Settings, cloud_settings: Settings
    ) -> None:
        local_card = build_agent_card(FakeMCP(), local_settings)
        cloud_card = build_agent_card(FakeMCP(), cloud_settings)

        assert local_card["metadata"]["authenticationMode"] == "local"
        assert cloud_card["metadata"]["authenticationMode"] == "cloud"

    def test_read_only_is_advertised(
        self, local_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(local_settings, "read_only", True)
        card = build_agent_card(FakeMCP(), local_settings)

        assert card["metadata"]["readOnly"] is True
        assert "read-only" in card["metadata"]["capabilities"]

    def test_dry_run_is_advertised(
        self, local_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(local_settings, "dry_run", True)
        card = build_agent_card(FakeMCP(), local_settings)

        assert card["metadata"]["dryRun"] is True
        assert "dry-run" in card["metadata"]["capabilities"]

    def test_fleet_is_advertised_only_with_a_registry(
        self, local_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(local_settings, "database_url", None)
        card = build_agent_card(FakeMCP(), local_settings)
        assert card["metadata"]["fleet"] is False

        monkeypatch.setattr(local_settings, "database_url", "postgresql://x/y")
        card = build_agent_card(FakeMCP(), local_settings)
        assert card["metadata"]["fleet"] is True
        assert "multi-controller" in card["metadata"]["capabilities"]

    def test_safety_requirements_follow_the_tier(
        self, local_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A write tool is not advertised as destructive when the registry says otherwise."""
        tiers = __import__("src.tool_registry", fromlist=["TOOL_TIERS"]).TOOL_TIERS
        monkeypatch.setitem(tiers, "create_site_network", "write")
        monkeypatch.setitem(tiers, "list_site_clients", "read")

        mcp = self._mcp_with(
            make_tool(list_site_clients, name="list_site_clients"),
            make_tool(create_site_network, name="create_site_network"),
        )
        card = build_agent_card(mcp, local_settings)

        requirements = {r["toolName"]: r for r in card["metadata"]["safetyRequirements"]}
        assert requirements["create_site_network"]["destructive"] is False
        assert requirements["create_site_network"]["confirmationLevel"] == "required"
        assert "list_site_clients" not in requirements

    def test_the_advertised_tier_is_the_enforced_tier(self, local_settings: Settings) -> None:
        """A card must not advertise a tier other than the one enforced.

        The card tells a client which role a tool needs. If the advertised
        tier were not the enforced one, a client would either refuse a
        call the server would allow, or believe a call is safe when the
        server treats it as destructive.
        """
        import src.main as main
        from src.a2a.auth import AuthManager
        from src.a2a.capabilities import iter_registered_tools, tool_tier
        from src.tool_registry import TOOL_TIERS
        from src.tool_registry import tool_tier as registry_tool_tier

        auth = AuthManager()
        auth.register_tools({tool.name: tool for tool in iter_registered_tools(main.mcp)}, main.mcp)

        mismatches: list[str] = []
        for tool in iter_registered_tools(main.mcp):
            advertised = tool_tier(tool)
            enforced = TOOL_TIERS.get(tool.name) or registry_tool_tier(getattr(tool, "fn", None))
            if advertised != enforced:
                mismatches.append(f"{tool.name}: advertised={advertised} enforced={enforced}")

        assert not mismatches, "\n".join(mismatches)

    def test_destructive_tools_require_confirmation(
        self, local_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tiers = __import__("src.tool_registry", fromlist=["TOOL_TIERS"]).TOOL_TIERS
        monkeypatch.setitem(tiers, "delete_site_device", "destructive")

        mcp = self._mcp_with(make_tool(delete_site_device, name="delete_site_device"))
        card = build_agent_card(mcp, local_settings)

        requirement = card["metadata"]["safetyRequirements"][0]
        assert requirement["destructive"] is True
        assert requirement["confirmationLevel"] == "required"

    def test_sensitive_fields_match_only_credential_names(
        self, local_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``ssid`` and ``description`` are not credentials."""

        def tool_with_fields(password: str = "", ssid: str = "", token: str = "") -> dict:
            """A tool with several parameter names."""
            return {}

        tiers = __import__("src.tool_registry", fromlist=["TOOL_TIERS"]).TOOL_TIERS
        monkeypatch.setitem(tiers, "tool_with_fields", "read")
        mcp = self._mcp_with(make_tool(tool_with_fields, name="tool_with_fields"))
        card = build_agent_card(mcp, local_settings)

        sensitive = card["metadata"]["safetyRequirements"][0]["sensitiveFields"]
        assert "password" in sensitive
        assert "token" in sensitive
        assert "ssid" not in sensitive
        assert "description" not in sensitive


class TestCardLeaksNothing:
    """The card is public metadata. It must carry no secret and no topology."""

    def test_no_credential_value_appears(self, local_settings: Settings) -> None:
        mcp = FakeMCP(
            {
                f"tool:{tool.name}@": tool
                for tool in [make_tool(list_site_clients, name="list_site_clients")]
            }
        )
        card = build_agent_card(mcp, local_settings)
        rendered = str(card)

        assert "test-key" not in rendered
        assert "UNIFI_API_KEY" not in rendered

    def test_no_local_controller_host_appears(self, local_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), local_settings)
        rendered = str(card)

        assert "192.0.2.10" not in rendered

    def test_no_filesystem_path_appears(self, local_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), local_settings)
        rendered = str(card)

        assert "/home/" not in rendered
        assert "/Users/" not in rendered


class TestCapabilitySummary:
    """The summary is the shared source of truth."""

    def test_counts_split_by_tier(
        self, local_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tiers = __import__("src.tool_registry", fromlist=["TOOL_TIERS"]).TOOL_TIERS
        monkeypatch.setitem(tiers, "list_site_clients", "read")
        monkeypatch.setitem(tiers, "create_site_network", "write")
        monkeypatch.setitem(tiers, "delete_site_device", "destructive")

        mcp = FakeMCP(
            {
                f"tool:{tool.name}@": tool
                for tool in [
                    make_tool(list_site_clients, name="list_site_clients"),
                    make_tool(create_site_network, name="create_site_network"),
                    make_tool(delete_site_device, name="delete_site_device"),
                ]
            }
        )
        summary = summarize_capabilities(mcp, local_settings)

        assert summary.tool_count == 3
        assert summary.read_count == 1
        assert summary.write_count == 1
        assert summary.destructive_count == 1

    def test_unknown_tool_is_treated_as_destructive(self, local_settings: Settings) -> None:
        assert tool_tier("never_registered_tool") == "destructive"

    def test_advertised_capabilities_follow_the_domains(self, local_settings: Settings) -> None:
        summary = summarize_capabilities(FakeMCP(), local_settings)
        assert advertised_capabilities(summary) == [
            "tool-delegation",
            "safety-controls",
            "audit-log",
        ]

    def test_advertised_api_modes_is_one_mode(self, local_settings: Settings) -> None:
        summary = summarize_capabilities(FakeMCP(), local_settings)
        assert advertised_api_modes(summary) == ["local"]


class TestDomainMapping:
    def test_a_tool_from_a_known_module_gets_its_domain(self) -> None:
        def sample() -> None:
            """A sample tool."""

        sample.__module__ = "src.tools.firewall_policies"
        tool = make_tool(sample, name="sample")
        assert domain_for_tool(tool) == "security"

    def test_a_fleet_tool_gets_the_fleet_domain(self) -> None:
        def sample() -> None:
            """A sample tool."""

        sample.__module__ = "src.fleet.tools"
        tool = make_tool(sample, name="sample")
        assert domain_for_tool(tool) == "fleet"


class TestExecutor:
    """The executor runs a registered tool through its wrapper."""

    def test_unknown_tool_is_refused(self, local_settings: Settings) -> None:
        import asyncio

        with pytest.raises(UnknownToolError):
            asyncio.run(execute_tool_call(FakeMCP(), "no_such_tool", {}))

    def test_the_registered_function_is_called(self, local_settings: Settings) -> None:
        import asyncio

        called: list[tuple[Any, ...]] = []

        async def sample(site_id: str) -> dict[str, Any]:
            """A sample tool."""
            called.append((site_id,))
            return {"ok": True}

        mcp = FakeMCP({"tool:sample@": make_tool(sample, name="sample")})
        result = asyncio.run(execute_tool_call(mcp, "sample", {"site_id": "default"}))

        assert result == {"ok": True}
        assert called == [("default",)]


class TestLiveServerCard:
    """The card built from the real server lists the real tools."""

    @pytest.mark.asyncio
    async def test_card_lists_the_registered_tools(self) -> None:
        import os
        import sys

        os.environ.setdefault("UNIFI_API_KEY", "test-key")
        os.environ.setdefault("UNIFI_API_TYPE", "local")
        os.environ.setdefault("UNIFI_LOCAL_HOST", "192.0.2.1")
        os.environ.setdefault("AGNOST_ENABLED", "false")
        sys.path.insert(0, ".")
        import src.main as main

        card = build_agent_card(main.mcp, main.settings)

        assert card["metadata"]["toolCount"] == len(card["skills"])
        assert card["metadata"]["toolCount"] > 100
        names = {skill["name"] for skill in card["skills"]}
        assert "list_sites" in names
        assert "get_site_statistics" in names

    @pytest.mark.asyncio
    async def test_every_skill_is_a_registered_tool(self) -> None:
        import os
        import sys

        os.environ.setdefault("UNIFI_API_KEY", "test-key")
        os.environ.setdefault("UNIFI_API_TYPE", "local")
        os.environ.setdefault("UNIFI_LOCAL_HOST", "192.0.2.1")
        os.environ.setdefault("AGNOST_ENABLED", "false")
        sys.path.insert(0, ".")
        import src.main as main

        card = build_agent_card(main.mcp, main.settings)
        from src.a2a.capabilities import iter_registered_tools

        registered = {tool.name for tool in iter_registered_tools(main.mcp)}
        assert {skill["name"] for skill in card["skills"]} == registered

    @pytest.mark.asyncio
    async def test_the_card_contains_no_credential(self) -> None:
        import os
        import sys

        os.environ.setdefault("UNIFI_API_KEY", "test-key")
        os.environ.setdefault("UNIFI_API_TYPE", "local")
        os.environ.setdefault("UNIFI_LOCAL_HOST", "192.0.2.1")
        os.environ.setdefault("AGNOST_ENABLED", "false")
        sys.path.insert(0, ".")
        import src.main as main

        card = build_agent_card(main.mcp, main.settings)
        rendered = str(card)

        assert "test-key" not in rendered
        assert "192.0.2.1" not in rendered
