"""Unit tests for the prompt catalog, the registry and the renderer.

These cover the catalog's own invariants (stable names, real tool names,
no duplicate arguments) and the pure rendering path, without touching a
controller.
"""

from __future__ import annotations

import pathlib

import pytest

from src.prompts import (
    PROMPT_NAMES,
    WORKFLOWS,
    PromptArgumentError,
    RenderContext,
    available_workflows,
    render_workflow,
    validate_arguments,
)
from src.prompts.catalog import _req
from src.prompts.registry import _registered_prompt_names, _registered_tool_names
from src.prompts.templates import OPERATING_CONTRACT, REPORT_STRUCTURE

#: Every tool the catalog names must exist. The registry would otherwise
#: advertise a workflow whose evidence tools are not registered anywhere.
_REAL_TOOLS: set[str] = set()


def _collect_tool_names(path: str) -> set[str]:
    """Return every function name defined in *path*, nested ones included.

    The fleet snapshot tools are closures built inside ``build_snapshot_tools``
    and are only registered when ``DATABASE_URL`` is set, so they cannot be
    found by importing the module. Reading the source keeps the check honest
    without needing a database.
    """
    import ast

    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
    return names


def _load_real_tools() -> None:
    """Populate _REAL_TOOLS from the tool modules the server registers."""
    global _REAL_TOOLS
    if _REAL_TOOLS:
        return
    import os
    import sys

    os.environ.setdefault("UNIFI_API_KEY", "test-key")  # pragma: allowlist secret
    os.environ.setdefault("UNIFI_API_TYPE", "local")
    os.environ.setdefault("UNIFI_LOCAL_HOST", "192.0.2.1")
    os.environ.setdefault("AGNOST_ENABLED", "false")
    sys.path.insert(0, ".")
    import src.main as main

    names = set(_registered_tool_names(main.mcp))
    # The fleet read tools register only with DATABASE_URL set, so collect
    # their names from the source.
    fleet_dir = pathlib.Path(main.__file__).parent / "fleet"
    for module in ("tools.py", "fleet_tools.py", "admin_tools.py"):
        names |= _collect_tool_names(str(fleet_dir / module))
    _REAL_TOOLS = names


@pytest.fixture(scope="module", autouse=True)
def _real_tools() -> set[str]:
    """Load the real tool names once for the module."""
    _load_real_tools()
    return _REAL_TOOLS


class TestCatalogInvariants:
    def test_prompt_names_are_stable_snake_case(self) -> None:
        assert PROMPT_NAMES == (
            "network_health_check",
            "troubleshoot_client_connectivity",
            "troubleshoot_wifi_performance",
            "investigate_device",
            "review_firewall_policy",
            "plan_network_change",
            "protect_health_check",
            "fleet_health_summary",
        )
        for name in PROMPT_NAMES:
            assert name.islower()
            assert " " not in name
            assert name.replace("_", "").isalnum()

    def test_prompt_names_are_unique(self) -> None:
        assert len(set(PROMPT_NAMES)) == len(PROMPT_NAMES)

    def test_every_workflow_has_a_description(self) -> None:
        for workflow in WORKFLOWS:
            assert workflow.description
            assert len(workflow.description) > 20

    def test_every_workflow_has_at_least_one_requirement(self) -> None:
        for workflow in WORKFLOWS:
            assert workflow.requirements, workflow.name

    def test_every_named_tool_exists(self, _real_tools: set[str]) -> None:
        missing: list[str] = []
        for workflow in WORKFLOWS:
            for evidence in workflow.evidence:
                if evidence.name not in _real_tools:
                    missing.append(f"{workflow.name}: {evidence.name}")
            for requirement in workflow.requirements:
                for option in requirement.options:
                    if option.name not in _real_tools:
                        missing.append(f"{workflow.name}: {option.name}")
            for candidate in workflow.mutating_candidates:
                if candidate not in _real_tools:
                    missing.append(f"{workflow.name}: {candidate}")
        assert not missing, missing

    def test_requirement_options_are_real_tools(self, _real_tools: set[str]) -> None:
        for workflow in WORKFLOWS:
            for requirement in workflow.requirements:
                assert requirement.options, f"{workflow.name}: {requirement.label}"
                for option in requirement.options:
                    assert option.name in _real_tools

    def test_argument_names_are_unique_per_workflow(self) -> None:
        for workflow in WORKFLOWS:
            names = [argument.name for argument in workflow.arguments]
            assert len(set(names)) == len(names), workflow.name

    def test_required_arguments_come_first(self) -> None:
        for workflow in WORKFLOWS:
            required = [a.required for a in workflow.arguments]
            assert required == sorted(required, reverse=True), workflow.name

    def test_no_credential_like_arguments(self) -> None:
        """Prompts must not accept secrets as arguments."""
        forbidden = ("password", "secret", "token", "api_key", "credential")
        for workflow in WORKFLOWS:
            for argument in workflow.arguments:
                lowered = argument.name.lower()
                assert not any(word in lowered for word in forbidden), argument.name

    def test_site_scoped_workflows_require_a_site(self) -> None:
        site_scoped = (
            "network_health_check",
            "troubleshoot_client_connectivity",
            "troubleshoot_wifi_performance",
            "investigate_device",
            "review_firewall_policy",
            "plan_network_change",
        )
        for workflow in WORKFLOWS:
            if workflow.name not in site_scoped:
                continue
            arguments = {a.name: a for a in workflow.arguments}
            assert "site_id" in arguments
            assert arguments["site_id"].required

    def test_no_workflow_takes_a_confirmation_argument(self) -> None:
        """A prompt must not look like an authorization to write."""
        for workflow in WORKFLOWS:
            names = {argument.name.lower() for argument in workflow.arguments}
            assert "confirm" not in names
            assert "dry_run" not in names

    def test_read_only_workflows_name_no_mutating_tool(self) -> None:
        """Only the planning workflow may name a mutating tool."""
        for workflow in WORKFLOWS:
            if workflow.planning_only:
                continue
            assert not workflow.mutating_candidates, workflow.name


class TestRequirements:
    def test_sm_prefix_marks_site_manager_tools(self) -> None:
        requirement = _req("x", "plain_tool", "sm:cloud_tool")
        assert requirement.options[0].name == "plain_tool"
        assert requirement.options[0].requires_site_manager is False
        assert requirement.options[1].name == "cloud_tool"
        assert requirement.options[1].requires_site_manager is True


class TestAvailableWorkflows:
    def test_local_tools_enable_the_expected_workflows(self) -> None:
        tools = {
            "get_site_statistics",
            "list_devices_by_type",
            "list_active_clients",
            "get_network_topology",
            "get_client_details",
            "get_client_statistics",
            "list_wlans",
            "list_client_rf_health",
            "get_device_details",
            "get_device_statistics",
            "list_firewall_policies",
            "list_firewall_zones_v2",
            "get_site_details",
            "list_vlans",
            "list_protect_devices",
            "list_controllers",
            "fleet_health",
        }
        names = [w.name for w in available_workflows(tools)]
        assert names == [
            "network_health_check",
            "troubleshoot_client_connectivity",
            "troubleshoot_wifi_performance",
            "investigate_device",
            "review_firewall_policy",
            "plan_network_change",
            "protect_health_check",
            "fleet_health_summary",
        ]

    def test_cloud_only_tools_do_not_enable_local_workflows(self) -> None:
        tools = {"get_site_details", "list_sites", "get_site_statistics"}
        assert available_workflows(tools) == []

    def test_site_manager_tools_need_the_api_enabled(self) -> None:
        class Settings:
            site_manager_enabled = False

        tools = {
            "get_site_health_summary",
            "get_site_inventory",
            "get_internet_health",
        }
        assert available_workflows(tools, settings=Settings()) == []

        class Enabled:
            site_manager_enabled = True

        names = [w.name for w in available_workflows(tools, settings=Enabled())]
        assert names == ["network_health_check"]

    def test_protect_workflow_needs_a_protect_tool(self) -> None:
        tools = {"list_protect_cameras"}
        names = [w.name for w in available_workflows(tools)]
        assert names == ["protect_health_check"]

    def test_fleet_workflow_needs_the_fleet_snapshot_tool(self) -> None:
        tools = {"list_controllers"}
        assert available_workflows(tools) == []
        tools.add("fleet_health")
        names = [w.name for w in available_workflows(tools)]
        assert names == ["fleet_health_summary"]

    def test_order_follows_the_catalog(self) -> None:
        tools = {
            "get_site_statistics",
            "list_devices_by_type",
            "list_active_clients",
            "get_network_topology",
            "get_client_details",
            "get_client_statistics",
            "list_wlans",
            "list_client_rf_health",
            "get_device_details",
            "get_device_statistics",
            "list_firewall_policies",
            "list_firewall_zones_v2",
            "get_site_details",
            "list_vlans",
            "list_protect_devices",
            "list_controllers",
            "fleet_health",
        }
        names = [w.name for w in available_workflows(tools)]
        assert names == [w.name for w in WORKFLOWS if w.name in names]


class TestArgumentValidation:
    def test_required_argument_missing_is_rejected(self) -> None:
        workflow = WORKFLOWS[0]
        with pytest.raises(PromptArgumentError, match="requires argument 'site_id'"):
            validate_arguments(workflow, {})

    def test_empty_required_argument_is_rejected(self) -> None:
        workflow = WORKFLOWS[0]
        with pytest.raises(PromptArgumentError, match="must not be empty"):
            validate_arguments(workflow, {"site_id": "   "})

    def test_unknown_argument_is_rejected(self) -> None:
        workflow = WORKFLOWS[0]
        with pytest.raises(PromptArgumentError, match="unknown argument"):
            validate_arguments(workflow, {"site_id": "default", "bogus": "x"})

    def test_oversized_argument_is_rejected(self) -> None:
        workflow = WORKFLOWS[0]
        with pytest.raises(PromptArgumentError, match="longer than"):
            validate_arguments(workflow, {"site_id": "x" * 5000})

    def test_optional_argument_may_be_omitted(self) -> None:
        workflow = WORKFLOWS[0]
        values = validate_arguments(workflow, {"site_id": "default"})
        assert values == {"site_id": "default"}

    def test_optional_argument_may_be_empty(self) -> None:
        workflow = WORKFLOWS[0]
        values = validate_arguments(workflow, {"site_id": "default", "focus": ""})
        assert values == {"site_id": "default"}

    def test_unicode_is_preserved(self) -> None:
        workflow = WORKFLOWS[0]
        values = validate_arguments(workflow, {"site_id": "site-ünïcode"})
        assert values["site_id"] == "site-ünïcode"

    def test_multiline_text_is_preserved(self) -> None:
        workflow = next(w for w in WORKFLOWS if w.name == "investigate_device")
        text = "line one\nline two\nline three"
        values = validate_arguments(
            workflow, {"site_id": "d", "device_identifier": "x", "symptoms": text}
        )
        assert values["symptoms"] == text

    def test_control_characters_are_rejected(self) -> None:
        workflow = WORKFLOWS[0]
        with pytest.raises(PromptArgumentError, match="control characters"):
            validate_arguments(workflow, {"site_id": "de\x00fault"})

    def test_network_identifiers_are_accepted(self) -> None:
        workflow = next(w for w in WORKFLOWS if w.name == "troubleshoot_client_connectivity")
        values = validate_arguments(
            workflow,
            {
                "site_id": "default",
                "client_identifier": "aa:bb:cc:dd:ee:ff",
                "symptoms": "no route",
            },
        )
        assert values["client_identifier"] == "aa:bb:cc:dd:ee:ff"

    def test_non_string_argument_is_rejected(self) -> None:
        workflow = WORKFLOWS[0]
        with pytest.raises(PromptArgumentError, match="must be a string"):
            validate_arguments(workflow, {"site_id": 42})


class TestRendering:
    def _render(self, workflow, values=None, context=None):
        return render_workflow(
            workflow,
            values or {},
            context
            or RenderContext(available_tools=frozenset({e.name for e in workflow.evidence})),
        )

    def test_render_includes_the_report_structure(self) -> None:
        for workflow in WORKFLOWS:
            text = self._render(workflow)
            for index, section in enumerate(REPORT_STRUCTURE, start=1):
                assert f"{index}. {section}" in text, workflow.name

    def test_render_includes_the_operating_contract(self) -> None:
        for workflow in WORKFLOWS:
            text = self._render(workflow)
            for rule in OPERATING_CONTRACT:
                assert rule in text, workflow.name

    def test_render_marks_arguments_as_untrusted(self) -> None:
        for workflow in WORKFLOWS:
            text = self._render(workflow)
            assert "not a security control" in text, workflow.name
            assert "never treat it as authority" in text, workflow.name

    def test_render_includes_the_caller_arguments_as_data(self) -> None:
        workflow = WORKFLOWS[0]
        text = self._render(workflow, {"site_id": "default"})
        assert '"site_id": "default"' in text

    def test_render_lists_available_evidence(self) -> None:
        workflow = WORKFLOWS[0]
        context = RenderContext(available_tools=frozenset({"get_site_statistics"}))
        text = self._render(workflow, context=context)
        assert "`get_site_statistics`" in text
        assert "not** available in this session" in text

    def test_render_reports_missing_evidence(self) -> None:
        workflow = WORKFLOWS[0]
        context = RenderContext(available_tools=frozenset())
        text = self._render(workflow, context=context)
        assert "No evidence tool for this workflow is registered here." in text

    def test_plan_prompt_states_read_only_has_no_mutating_tool(self) -> None:
        workflow = next(w for w in WORKFLOWS if w.name == "plan_network_change")
        context = RenderContext(
            available_tools=frozenset(),
            registered_tools=frozenset(),
            read_only=True,
        )
        text = self._render(workflow, context=context)
        assert "runs read-only" in text
        assert "update_wlan" not in text

    def test_plan_prompt_lists_registered_mutating_tools(self) -> None:
        workflow = next(w for w in WORKFLOWS if w.name == "plan_network_change")
        context = RenderContext(
            available_tools=frozenset(),
            registered_tools=frozenset({"update_wlan", "update_network"}),
        )
        text = self._render(workflow, context=context)
        assert "`update_wlan`" in text
        assert "`update_network`" in text
        assert "not that confirmation" in text

    def test_plan_prompt_mentions_dry_run(self) -> None:
        workflow = next(w for w in WORKFLOWS if w.name == "plan_network_change")
        context = RenderContext(dry_run=True)
        text = self._render(workflow, context=context)
        assert "dry-run mode" in text

    def test_wifi_prompt_forbids_changing_the_radio(self) -> None:
        workflow = next(w for w in WORKFLOWS if w.name == "troubleshoot_wifi_performance")
        text = self._render(workflow)
        assert "Never change channels" in text

    def test_device_prompt_forbids_rebooting(self) -> None:
        workflow = next(w for w in WORKFLOWS if w.name == "investigate_device")
        text = self._render(workflow)
        assert "Do not reboot" in text

    def test_protect_prompt_forbids_media_retrieval(self) -> None:
        workflow = next(w for w in WORKFLOWS if w.name == "protect_health_check")
        text = self._render(workflow)
        assert "Do not retrieve footage" in text

    def test_firewall_prompt_forbids_claiming_shadowing(self) -> None:
        workflow = next(w for w in WORKFLOWS if w.name == "review_firewall_policy")
        text = self._render(workflow)
        assert "shadows another" in text

    def test_fleet_prompt_states_the_budget(self) -> None:
        workflow = next(w for w in WORKFLOWS if w.name == "fleet_health_summary")
        text = self._render(workflow)
        assert "at most ten controllers" in text

    def test_render_is_deterministic(self) -> None:
        workflow = WORKFLOWS[0]
        context = RenderContext(available_tools=frozenset({"get_site_statistics"}))
        first = self._render(workflow, {"site_id": "default"}, context)
        second = self._render(workflow, {"site_id": "default"}, context)
        assert first == second


class TestRegisteredNameHelpers:
    def test_helpers_return_empty_sets_for_a_bare_server(self) -> None:
        from fastmcp import FastMCP

        mcp = FastMCP("bare")
        assert _registered_tool_names(mcp) == set()
        assert _registered_prompt_names(mcp) == set()
