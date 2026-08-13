"""Unit tests for src/a2a/prompt_playbook.py and the bundled playbooks."""

from __future__ import annotations

import json

import pytest

from src.a2a.playbooks import PLAYBOOKS
from src.a2a.prompt_playbook import (
    DEFAULT_PLAYBOOK_REGISTRY,
    PlaybookRegistry,
    PlaybookStep,
    PromptPlaybook,
    _default_registry,
    _format_params,
    render_playbook,
)

EXPECTED_BUILTIN_NAMES = [
    "device_provisioning",
    "guest_wifi_setup",
    "incident_response",
    "network_diagnostics",
    "security_audit",
    "site_migration",
]


def make_playbook(name: str = "demo", **overrides: object) -> PromptPlaybook:
    """Build a small playbook for registry and rendering tests."""
    defaults: dict[str, object] = {
        "name": name,
        "description": "Demo workflow.",
        "steps": [
            PlaybookStep(
                order=2,
                action="Second action.",
                tool="list_site_clients",
                params={"site_id": "default"},
                validation="Confirm clients are listed.",
                fallback="Retry with a narrower scope.",
            ),
            PlaybookStep(order=1, action="First action."),
        ],
        "requiredSkills": ["list_site_clients"],
        "safetyLevel": "confirm",
    }
    defaults.update(overrides)
    return PromptPlaybook(**defaults)  # type: ignore[arg-type]


class TestPlaybookStep:
    """Tests for PlaybookStep."""

    def test_defaults_are_empty(self) -> None:
        step = PlaybookStep(order=1, action="Do the thing.")

        assert step.tool is None
        assert step.params == {}
        assert step.validation == ""
        assert step.fallback == ""

    def test_to_dict_round_trips_every_field(self) -> None:
        step = PlaybookStep(order=3, action="Act.", tool="t", params={"a": 1})

        assert step.to_dict() == {
            "order": 3,
            "action": "Act.",
            "tool": "t",
            "params": {"a": 1},
            "validation": "",
            "fallback": "",
        }

    def test_params_are_not_shared_between_instances(self) -> None:
        first = PlaybookStep(order=1, action="One.")
        second = PlaybookStep(order=2, action="Two.")
        first.params["site_id"] = "default"

        assert second.params == {}


class TestPromptPlaybook:
    """Tests for PromptPlaybook."""

    def test_defaults_are_empty(self) -> None:
        playbook = PromptPlaybook(name="p", description="d")

        assert playbook.steps == []
        assert playbook.requiredSkills == []
        assert playbook.safetyLevel == "none"

    def test_to_dict_serializes_nested_steps(self) -> None:
        payload = make_playbook().to_dict()

        assert payload["name"] == "demo"
        assert payload["safetyLevel"] == "confirm"
        assert [step["order"] for step in payload["steps"]] == [2, 1]
        assert json.dumps(payload)


class TestPlaybookRegistry:
    """Tests for PlaybookRegistry."""

    def test_starts_empty(self) -> None:
        assert PlaybookRegistry().names() == []

    def test_registers_playbooks_supplied_to_the_constructor(self) -> None:
        registry = PlaybookRegistry([make_playbook("b"), make_playbook("a")])

        assert registry.names() == ["a", "b"]

    def test_register_replaces_an_existing_name(self) -> None:
        registry = PlaybookRegistry([make_playbook("a", description="first")])
        registry.register(make_playbook("a", description="second"))

        assert registry.get("a").description == "second"
        assert registry.names() == ["a"]

    def test_get_raises_a_descriptive_error_for_unknown_names(self) -> None:
        with pytest.raises(KeyError, match="Unknown playbook: missing"):
            PlaybookRegistry().get("missing")

    def test_items_are_sorted_by_name(self) -> None:
        registry = PlaybookRegistry([make_playbook("z"), make_playbook("a")])

        assert [name for name, _ in registry.items()] == ["a", "z"]
        assert all(name == playbook.name for name, playbook in registry.items())

    def test_to_dict_is_json_serializable(self) -> None:
        payload = PlaybookRegistry([make_playbook("a")]).to_dict()

        assert list(payload) == ["a"]
        assert json.dumps(payload)

    def test_load_builtin_registers_every_bundled_playbook(self) -> None:
        registry = PlaybookRegistry.load_builtin()

        assert registry.names() == EXPECTED_BUILTIN_NAMES


class TestDefaultRegistry:
    """Tests for the module-level DEFAULT_PLAYBOOK_REGISTRY."""

    def test_exposes_the_bundled_playbooks(self) -> None:
        assert _default_registry().names() == EXPECTED_BUILTIN_NAMES

    def test_recovers_when_the_registry_was_built_before_the_playbooks_package(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing src.a2a.playbooks first used to leave the registry empty."""
        monkeypatch.setattr(DEFAULT_PLAYBOOK_REGISTRY, "_playbooks", {})

        assert _default_registry().names() == EXPECTED_BUILTIN_NAMES
        assert "# A2A Prompt Playbook: security_audit" in render_playbook("security_audit")


class TestFormatParams:
    """Tests for _format_params."""

    @pytest.mark.parametrize("params", [None, {}])
    def test_empty_params_render_as_an_empty_object(self, params: dict[str, object] | None) -> None:
        assert _format_params(params) == "{}"

    def test_keys_are_sorted(self) -> None:
        assert _format_params({"b": 1, "a": 2}) == '{\n  "a": 2,\n  "b": 1\n}'

    def test_non_serializable_values_fall_back_to_their_string_form(self) -> None:
        rendered = _format_params({"when": object()})

        assert "object object" in rendered


class TestRenderPlaybook:
    """Tests for render_playbook."""

    def test_renders_steps_in_order(self) -> None:
        registry = PlaybookRegistry([make_playbook()])

        rendered = render_playbook("demo", {"site_id": "default"}, registry)

        assert rendered.index("### Step 1:") < rendered.index("### Step 2:")

    def test_includes_the_header_metadata_and_context(self) -> None:
        registry = PlaybookRegistry([make_playbook()])

        rendered = render_playbook("demo", {"site_id": "default"}, registry)

        assert "# A2A Prompt Playbook: demo" in rendered
        assert "Description: Demo workflow." in rendered
        assert "Safety level: confirm" in rendered
        assert "Required skills: list_site_clients" in rendered
        assert '"site_id": "default"' in rendered
        assert "## Operating Notes" in rendered

    def test_missing_context_renders_an_empty_object(self) -> None:
        registry = PlaybookRegistry([make_playbook()])

        rendered = render_playbook("demo", None, registry)

        assert "## Context\n```json\n{}\n```" in rendered

    def test_playbooks_without_required_skills_say_none(self) -> None:
        registry = PlaybookRegistry([make_playbook(requiredSkills=[])])

        assert "Required skills: none" in render_playbook("demo", {}, registry)

    def test_steps_without_a_tool_or_guidance_use_defaults(self) -> None:
        registry = PlaybookRegistry(
            [make_playbook(steps=[PlaybookStep(order=1, action="Summarize.")])]
        )

        rendered = render_playbook("demo", {}, registry)

        assert "Tool: none" in rendered
        assert "Validation: confirm the action completed successfully." in rendered
        assert "Fallback: pause and request human guidance." in rendered

    def test_defaults_to_the_bundled_registry(self) -> None:
        rendered = render_playbook("network_diagnostics", {"site_id": "default"})

        assert "# A2A Prompt Playbook: network_diagnostics" in rendered

    def test_unknown_playbooks_raise_key_error(self) -> None:
        with pytest.raises(KeyError, match="Unknown playbook: nope"):
            render_playbook("nope")


class TestBundledPlaybooks:
    """Contract tests covering every playbook in src/a2a/playbooks."""

    def test_names_are_unique_and_complete(self) -> None:
        assert sorted(playbook.name for playbook in PLAYBOOKS) == EXPECTED_BUILTIN_NAMES

    @pytest.mark.parametrize("playbook", PLAYBOOKS, ids=lambda item: item.name)
    def test_each_playbook_is_well_formed(self, playbook: PromptPlaybook) -> None:
        assert playbook.description
        assert playbook.steps
        assert [step.order for step in playbook.steps] == list(range(1, len(playbook.steps) + 1))
        for step in playbook.steps:
            assert step.action
            assert step.validation
            assert step.fallback

    @pytest.mark.parametrize("playbook", PLAYBOOKS, ids=lambda item: item.name)
    def test_each_playbook_renders(self, playbook: PromptPlaybook) -> None:
        rendered = render_playbook(playbook.name, {"site_id": "default"})

        assert f"# A2A Prompt Playbook: {playbook.name}" in rendered
        for step in playbook.steps:
            assert f"### Step {step.order}: {step.action}" in rendered
