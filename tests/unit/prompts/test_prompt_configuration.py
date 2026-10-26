"""Configuration-matrix tests for the prompt catalog.

Each test builds a real server under a different configuration and asserts
which prompts it advertises. This is the guard that keeps the catalog honest:
a workflow whose tools are not registered must not be discoverable.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any
from unittest.mock import patch

import pytest

from src.prompts.registry import _registered_prompt_names

_BASE_ENV = {
    "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
    "UNIFI_API_TYPE": "local",
    "UNIFI_LOCAL_HOST": "127.0.0.1",
    "AGNOST_ENABLED": "false",
}


def _build(**extra_env: str) -> Any:
    """Import src.main under the given environment and return the server."""
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]
    with patch.dict("os.environ", {**_BASE_ENV, **extra_env}, clear=False):
        return importlib.import_module("src.main").mcp


def _prompts(**extra_env: str) -> set[str]:
    """Return the prompt names the server advertises under the given config."""
    return _registered_prompt_names(_build(**extra_env))


def _stub_tool(name: str) -> Any:
    """Return a no-op tool function to register under *name*."""
    from fastmcp.tools import Tool

    async def stub() -> str:
        """A stub tool that does nothing."""
        return "stub"

    stub.__name__ = name
    stub.__doc__ = "A stub tool that does nothing."
    return Tool.from_function(stub, name=name)


#: Every tool a workflow in the catalog requires. A server carrying all of
#: them may advertise every workflow.
_ALL_REQUIRED_TOOLS: set[str] = {
    "get_site_statistics",
    "list_devices_by_type",
    "list_active_clients",
    "get_network_topology",
    "get_client_details",
    "search_clients",
    "get_client_statistics",
    "list_client_rf_health",
    "list_wlans",
    "get_device_details",
    "get_device_by_mac",
    "search_devices",
    "get_device_statistics",
    "list_firewall_policies",
    "list_firewall_rules",
    "list_firewall_zones_v2",
    "list_firewall_zones",
    "get_site_details",
    "list_vlans",
    "list_protect_devices",
    "list_protect_cameras",
    "list_controllers",
    "fleet_health",
}


class TestApiMode:
    def test_local_mode_advertises_the_network_workflows(self) -> None:
        names = _prompts(UNIFI_API_TYPE="local")
        assert "network_health_check" in names
        assert "troubleshoot_client_connectivity" in names
        assert "troubleshoot_wifi_performance" in names
        assert "investigate_device" in names
        assert "review_firewall_policy" in names
        assert "plan_network_change" in names

    def test_cloud_mode_advertises_no_local_only_workflow(self) -> None:
        """Cloud mode has none of the local tools the workflows depend on."""
        names = _prompts(UNIFI_API_TYPE="cloud-v1")
        assert "troubleshoot_client_connectivity" not in names
        assert "troubleshoot_wifi_performance" not in names
        assert "investigate_device" not in names
        assert "review_firewall_policy" not in names

    def test_cloud_mode_with_site_manager_advertises_the_health_check(self) -> None:
        names = _prompts(UNIFI_API_TYPE="cloud-v1", UNIFI_SITE_MANAGER_ENABLED="true")
        assert "network_health_check" in names
        assert "troubleshoot_client_connectivity" not in names


class TestProfiles:
    def test_minimal_profile_stays_minimal(self) -> None:
        names = _prompts(UNIFI_API_TYPE="local", UNIFI_PROFILE="minimal")
        assert len(names) <= 2

    def test_protect_profile_advertises_the_protect_workflow(self) -> None:
        names = _prompts(UNIFI_API_TYPE="local", UNIFI_PROFILE="protect")
        assert "protect_health_check" in names

    def test_protect_workflow_is_absent_without_protect_tools(self) -> None:
        names = _prompts(UNIFI_API_TYPE="local", UNIFI_PROFILE="network")
        assert "protect_health_check" not in names

    def test_security_profile_advertises_the_firewall_workflow(self) -> None:
        names = _prompts(UNIFI_API_TYPE="local", UNIFI_PROFILE="security")
        assert "review_firewall_policy" in names

    def test_firewall_workflow_is_absent_without_firewall_tools(self) -> None:
        names = _prompts(UNIFI_API_TYPE="local", UNIFI_PROFILE="devices")
        assert "review_firewall_policy" not in names

    def test_devices_profile_advertises_the_device_workflow(self) -> None:
        names = _prompts(UNIFI_API_TYPE="local", UNIFI_PROFILE="devices")
        assert "investigate_device" in names


class TestReadOnlyAndDryRun:
    def test_read_only_keeps_every_read_workflow(self) -> None:
        baseline = _prompts(UNIFI_API_TYPE="local")
        read_only = _prompts(UNIFI_API_TYPE="local", UNIFI_READ_ONLY="true")
        assert baseline <= read_only

    def test_read_only_keeps_the_planning_workflow(self) -> None:
        """The planning workflow stays, because it only ever plans."""
        names = _prompts(UNIFI_API_TYPE="local", UNIFI_READ_ONLY="true")
        assert "plan_network_change" in names

    def test_dry_run_keeps_every_read_workflow(self) -> None:
        baseline = _prompts(UNIFI_API_TYPE="local")
        dry_run = _prompts(UNIFI_API_TYPE="local", UNIFI_DRY_RUN="true")
        assert baseline <= dry_run

    def test_read_only_and_dry_run_do_not_change_the_prompt_set(self) -> None:
        baseline = _prompts(UNIFI_API_TYPE="local")
        assert _prompts(UNIFI_API_TYPE="local", UNIFI_READ_ONLY="true") == baseline
        assert _prompts(UNIFI_API_TYPE="local", UNIFI_DRY_RUN="true") == baseline


class TestFleet:
    def test_fleet_workflow_needs_the_fleet_snapshot_tools(self) -> None:
        """Without DATABASE_URL there is no fleet snapshot to summarise."""
        names = _prompts(UNIFI_API_TYPE="local")
        assert "fleet_health_summary" not in names


class TestIdempotence:
    def _fresh_server_with_tools(self, tool_names: set[str]) -> Any:
        """Return a FastMCP server carrying the named stub tools."""
        from fastmcp import FastMCP

        mcp = FastMCP("fresh")
        for name in tool_names:
            mcp.add_tool(_stub_tool(name))
        return mcp

    def test_registering_twice_does_not_duplicate_a_prompt(self) -> None:
        from src.prompts import register_prompts

        mcp = self._fresh_server_with_tools(_ALL_REQUIRED_TOOLS)
        first = register_prompts(mcp)
        assert first
        before = _registered_prompt_names(mcp)
        register_prompts(mcp)
        after = _registered_prompt_names(mcp)
        assert before == after
        assert len(before) == len(set(before))

    def test_a_second_registration_adds_no_new_names(self) -> None:
        from src.prompts import register_prompts

        mcp = self._fresh_server_with_tools(_ALL_REQUIRED_TOOLS)
        first = register_prompts(mcp)
        second = register_prompts(mcp)
        assert first
        assert second == []

    def test_the_imported_server_registers_each_prompt_once(self) -> None:
        """src.main registers the prompts at import; re-registering is a no-op."""
        from src.prompts import register_prompts

        mcp = _build(UNIFI_API_TYPE="local")
        before = _registered_prompt_names(mcp)
        assert before
        assert register_prompts(mcp) == []
        assert _registered_prompt_names(mcp) == before


def teardown_module(module: Any) -> None:  # noqa: D401
    """Restore a pristine src.main for any later tests in the session."""
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]
    with patch.dict("os.environ", _BASE_ENV, clear=False):
        importlib.import_module("src.main")


@pytest.mark.parametrize(
    "profile", ["minimal", "protect", "network", "security", "devices", "system"]
)
def test_every_profile_registers_at_least_one_prompt_or_none(profile: str) -> None:
    """No configuration may raise while registering prompts."""
    names = _prompts(UNIFI_API_TYPE="local", UNIFI_PROFILE=profile)
    assert isinstance(names, set)
