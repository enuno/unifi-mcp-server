"""Unit tests for src/a2a/discovery.py."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

from src.a2a import discovery
from src.a2a.discovery import (
    _iter_components,
    _resolve_active_mcp,
    build_agent_card,
    get_resource_endpoints,
    get_skills_manifest,
)
from src.config.config import Settings

from .conftest import FakeMCP, delete_site_device, list_site_clients, make_resource, make_tool


class Marker:
    """Stands in for FastMCP so sys.modules scanning has exactly one match."""


def build_populated_mcp() -> FakeMCP:
    """Return a fake server exposing one tool, one resource, and one other component."""
    return FakeMCP(
        {
            "list_site_clients": make_tool(list_site_clients),
            "delete_site_device": make_tool(delete_site_device),
            "sites": make_resource(lambda: "payload", uri="unifi://sites", name="sites"),
            "some_prompt": object(),
        }
    )


class TestIterComponents:
    """Tests for _iter_components."""

    def test_yields_nothing_for_a_server_without_providers(self) -> None:
        assert list(_iter_components(object())) == []

    def test_yields_every_registered_component(self) -> None:
        mcp = FakeMCP({"a": "first", "b": "second"})

        assert list(_iter_components(mcp)) == ["first", "second"]

    def test_skips_providers_without_a_component_mapping(self) -> None:
        mcp = FakeMCP({"a": "first"})
        mcp.providers.insert(0, type("Bare", (), {"_components": None})())

        assert list(_iter_components(mcp)) == ["first"]

    def test_spans_multiple_providers(self) -> None:
        mcp = FakeMCP({"a": "first"})
        mcp.providers.append(type("Extra", (), {"_components": {"b": "second"}})())

        assert list(_iter_components(mcp)) == ["first", "second"]


class TestResolveActiveMcp:
    """Tests for _resolve_active_mcp."""

    @pytest.fixture(autouse=True)
    def only_marker_counts_as_a_server(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Narrow the isinstance check so unrelated imports cannot match.

        src/main.py holds a module-level FastMCP, so scanning the real
        sys.modules would otherwise make these tests depend on import order.
        """
        monkeypatch.setattr(discovery, "FastMCP", Marker)

    def test_returns_none_when_no_module_exposes_a_server(self) -> None:
        assert _resolve_active_mcp() is None

    def test_skips_none_entries_in_sys_modules(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "tests_a2a_discovery_stale", None)

        assert _resolve_active_mcp() is None

    def test_finds_a_module_level_server_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        server = Marker()
        holder = ModuleType("tests_a2a_discovery_holder")
        holder.mcp = server
        monkeypatch.setitem(sys.modules, "tests_a2a_discovery_holder", holder)

        assert _resolve_active_mcp() is server

    def test_ignores_attributes_named_mcp_that_are_not_servers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        decoy = ModuleType("tests_a2a_discovery_decoy")
        decoy.mcp = "not-a-server"
        monkeypatch.setitem(sys.modules, "tests_a2a_discovery_decoy", decoy)

        assert _resolve_active_mcp() is None


class TestBuildAgentCard:
    """Tests for the discovery build_agent_card wrapper."""

    def test_delegates_to_the_card_builder(self, local_settings: Settings) -> None:
        card = build_agent_card(build_populated_mcp(), local_settings)

        assert {skill.name for skill in card.skills} == {
            "list_site_clients",
            "delete_site_device",
        }
        assert [resource.uri for resource in card.resources] == ["unifi://sites"]


class TestGetSkillsManifest:
    """Tests for get_skills_manifest."""

    def test_returns_an_empty_list_without_an_active_server(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(discovery, "_resolve_active_mcp", lambda: None)

        assert get_skills_manifest() == []

    def test_returns_only_tool_components(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(discovery, "_resolve_active_mcp", build_populated_mcp)

        skills = get_skills_manifest()

        assert {skill.name for skill in skills} == {"list_site_clients", "delete_site_device"}
        assert all(skill.description for skill in skills)


class TestGetResourceEndpoints:
    """Tests for get_resource_endpoints."""

    def test_returns_an_empty_list_without_an_active_server(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(discovery, "_resolve_active_mcp", lambda: None)

        assert get_resource_endpoints() == []

    def test_returns_only_resource_components(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(discovery, "_resolve_active_mcp", build_populated_mcp)

        resources = get_resource_endpoints()

        assert [resource.uri for resource in resources] == ["unifi://sites"]
        assert resources[0].name == "sites"
