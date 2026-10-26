"""Unit tests for src/a2a/agent_card.py."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.a2a.agent_card import (
    _authentication_mode,
    _example_call_payload,
    _example_value_for_schema,
    _output_schema_for_tool,
    _package_version,
    _resource_uri,
    _safety_requirement_for_tool,
    _schema_for_tool,
    _sensitive_fields,
    _tool_description,
    _tool_skill,
    build_agent_card,
)
from src.a2a.types import AuthenticationMode
from src.config.config import APIType, Settings
from src.tool_registry import TOOL_TIERS

from .conftest import FakeMCP, delete_site_device, list_site_clients, make_resource, make_tool


class TestPackageVersion:
    """Tests for _package_version."""

    def test_returns_version_when_package_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "9.9.9")
        assert _package_version() == "9.9.9"

    def test_returns_unknown_when_package_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(_name: str) -> str:
            raise importlib.metadata.PackageNotFoundError(_name)

        monkeypatch.setattr(importlib.metadata, "version", _raise)
        assert _package_version() == "unknown"


class TestIterRegisteredTools:
    """Tests for the tool and resource iterators."""

    def test_yields_the_tools_of_each_provider(self) -> None:
        from src.a2a.capabilities import iter_registered_tools

        tool = make_tool(list_site_clients)
        mcp = FakeMCP({"tool:list_site_clients@": tool})

        assert list(iter_registered_tools(mcp)) == [tool]

    def test_returns_nothing_when_mcp_has_no_providers(self) -> None:
        from src.a2a.capabilities import iter_registered_tools

        assert list(iter_registered_tools(object())) == []

    def test_skips_providers_whose_components_are_not_a_dict(self) -> None:
        from src.a2a.capabilities import iter_registered_tools

        class BadProvider:
            _components = ["not", "a", "dict"]

        mcp = type("M", (), {"providers": [BadProvider()]})()

        assert list(iter_registered_tools(mcp)) == []


class TestToolDescription:
    """Tests for _tool_description."""

    def test_prefers_the_explicit_description(self) -> None:
        tool = make_tool(list_site_clients, description="Explicit description")
        assert _tool_description(tool) == "Explicit description"

    def test_falls_back_to_the_first_docstring_line(self) -> None:
        tool = make_tool(list_site_clients)
        tool.description = None

        assert _tool_description(tool) == "List clients for a site."

    def test_falls_back_to_the_tool_name(self) -> None:
        def undocumented(site_id: str) -> dict[str, Any]:
            return {}

        tool = make_tool(undocumented)
        tool.description = None

        assert _tool_description(tool) == "MCP tool: undocumented"


class TestSchemaAccessors:
    """Tests for _schema_for_tool and _output_schema_for_tool."""

    def test_schema_for_tool_returns_the_parameter_schema(self) -> None:
        tool = make_tool(list_site_clients)
        assert _schema_for_tool(tool)["properties"]["site_id"]["type"] == "string"

    def test_schema_for_tool_defaults_when_parameters_missing(self) -> None:
        tool = make_tool(list_site_clients)
        tool.parameters = None

        assert _schema_for_tool(tool) == {"type": "object", "properties": {}}

    def test_output_schema_defaults_if_missing(self) -> None:
        tool = make_tool(list_site_clients)
        tool.output_schema = None

        assert _output_schema_for_tool(tool) == {"type": "object"}

    def test_output_schema_returned_if_present(self) -> None:
        tool = make_tool(list_site_clients)
        tool.output_schema = {"type": "object", "properties": {"clients": {"type": "array"}}}

        assert _output_schema_for_tool(tool)["properties"]["clients"]["type"] == "array"


class TestExampleValueForSchema:
    """Tests for _example_value_for_schema."""

    def test_default_wins_over_type(self) -> None:
        assert _example_value_for_schema({"type": "integer", "default": 42}, "count") == 42

    @pytest.mark.parametrize(
        ("schema_type", "expected"),
        [("integer", 1), ("number", 1.0), ("boolean", True), ("object", {})],
    )
    def test_scalar_and_object_types(self, schema_type: str, expected: Any) -> None:
        assert _example_value_for_schema({"type": schema_type}, "field") == expected

    def test_array_type_wraps_the_item_example(self) -> None:
        schema = {"type": "array", "items": {"type": "integer"}}
        assert _example_value_for_schema(schema, "ports") == [1]

    def test_array_with_non_dict_items_falls_back_to_a_string_example(self) -> None:
        assert _example_value_for_schema({"type": "array", "items": "bogus"}, "tags") == [
            "example-tags"
        ]

    def test_identifier_fields_get_example_ids(self) -> None:
        assert _example_value_for_schema({}, "device_id") == "example-id"
        assert _example_value_for_schema({}, "clientid") == "example-id"

    def test_site_fields_default_to_the_default_site(self) -> None:
        assert _example_value_for_schema({}, "site_name") == "default"

    def test_name_like_fields_use_a_named_example(self) -> None:
        assert _example_value_for_schema({}, "label") == "example-label"

    def test_unrecognized_fields_use_a_generic_example(self) -> None:
        assert _example_value_for_schema({}, "colour") == "example-colour"


class TestExampleCallPayload:
    """Tests for _example_call_payload."""

    def test_uses_required_fields(self) -> None:
        payload = _example_call_payload(make_tool(list_site_clients))

        assert payload["tool"] == "list_site_clients"
        assert payload["arguments"]["site_id"] == "example-id"

    def test_adds_confirm_and_dry_run_when_offered(self) -> None:
        def risky(site_id: str, confirm: bool = False, dry_run: bool = False) -> dict[str, Any]:
            """Delete something."""
            return {}

        payload = _example_call_payload(make_tool(risky))

        assert payload["arguments"]["confirm"] is True
        assert payload["arguments"]["dry_run"] is True

    def test_falls_back_to_the_first_optional_property(self) -> None:
        def optional_only(limit: int = 10) -> dict[str, Any]:
            """Do a thing."""
            return {}

        payload = _example_call_payload(make_tool(optional_only))

        assert payload["arguments"] == {"limit": 10}

    def test_returns_empty_arguments_for_a_tool_without_parameters(self) -> None:
        tool = make_tool(list_site_clients)
        tool.parameters = {"type": "object", "properties": {}}

        assert _example_call_payload(tool)["arguments"] == {}


class TestToolTier:
    """The tier comes from the tool registry, not from the tool's name."""

    def test_a_destructive_tool_is_tiered_destructive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.a2a.capabilities import tool_tier
        from src.tool_registry import TOOL_TIERS

        monkeypatch.setitem(TOOL_TIERS, "delete_site_device", "destructive")
        assert tool_tier("delete_site_device") == "destructive"

    def test_an_unknown_tool_is_treated_as_destructive(self) -> None:
        from src.a2a.capabilities import tool_tier

        assert tool_tier("never_registered") == "destructive"

    def test_a_read_tool_is_tiered_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.a2a.capabilities import tool_tier
        from src.tool_registry import TOOL_TIERS

        monkeypatch.setitem(TOOL_TIERS, "list_site_clients", "read")
        assert tool_tier("list_site_clients") == "read"


class TestSensitiveFields:
    """Tests for _sensitive_fields."""

    def test_detects_and_sorts_sensitive_parameter_names(self) -> None:
        def login(username: str, password: str, api_key: str, site_id: str) -> dict[str, Any]:
            """Authenticate."""
            return {}

        assert _sensitive_fields(make_tool(login)) == ["api_key", "password"]

    def test_returns_empty_list_when_nothing_is_sensitive(self) -> None:
        assert _sensitive_fields(make_tool(list_site_clients)) == []

    def test_returns_empty_list_when_properties_are_not_a_dict(self) -> None:
        tool = make_tool(list_site_clients)
        tool.parameters = {"type": "object", "properties": "bogus"}

        assert _sensitive_fields(tool) == []


class TestSafetyRequirementForTool:
    """Tests for _safety_requirement_for_tool."""

    def test_returns_none_for_a_safe_read_only_tool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.tool_registry import TOOL_TIERS

        monkeypatch.setitem(TOOL_TIERS, "list_site_clients", "read")
        assert _safety_requirement_for_tool(make_tool(list_site_clients)) is None

    def test_destructive_tool_requires_confirmation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.tool_registry import TOOL_TIERS

        monkeypatch.setitem(TOOL_TIERS, "delete_site_device", "destructive")
        monkeypatch.setitem(TOOL_TIERS, "list_site_clients", "read")
        requirement = _safety_requirement_for_tool(make_tool(delete_site_device))

        assert requirement is not None
        assert requirement.confirmationLevel == "required"
        assert requirement.destructive is True
        assert requirement.toolName == "delete_site_device"
        assert "destructive" in (requirement.reason or "").lower()

    def test_write_tool_requires_confirmation_but_is_not_destructive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A write mutates state, so the server requires confirm=True for it."""
        from src.tool_registry import TOOL_TIERS

        def create_thing(site_id: str, name: str) -> dict[str, Any]:
            """Create a thing."""
            return {}

        monkeypatch.setitem(TOOL_TIERS, "create_thing", "write")
        requirement = _safety_requirement_for_tool(make_tool(create_thing))

        assert requirement is not None
        assert requirement.confirmationLevel == "required"
        assert requirement.destructive is False

    def test_sensitive_only_tool_is_recommended_not_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.tool_registry import TOOL_TIERS

        def authenticate(token: str) -> dict[str, Any]:
            """Exchange a token."""
            return {}

        monkeypatch.setitem(TOOL_TIERS, "authenticate", "read")
        requirement = _safety_requirement_for_tool(make_tool(authenticate))

        assert requirement is not None
        assert requirement.confirmationLevel == "recommended"
        assert requirement.destructive is False
        assert requirement.sensitiveFields == ["token"]


class TestAuthenticationMode:
    """Tests for _authentication_mode."""

    def test_local_settings_report_the_local_mode(self, local_settings: Settings) -> None:
        local_settings.api_type = APIType.LOCAL

        assert _authentication_mode(local_settings) is AuthenticationMode.LOCAL

    @pytest.mark.parametrize("api_type", [APIType.CLOUD_V1, APIType.CLOUD_EA])
    def test_cloud_settings_report_the_cloud_mode(
        self, local_settings: Settings, api_type: APIType
    ) -> None:
        local_settings.api_type = api_type

        assert _authentication_mode(local_settings) is AuthenticationMode.CLOUD

    def test_defaults_to_both_for_an_unrecognized_api_type(self) -> None:
        settings = SimpleNamespace(api_type="something-new")

        assert _authentication_mode(settings) is AuthenticationMode.BOTH


class TestComponentConversion:
    """Tests for _tool_skill and _resource_uri."""

    def test_tool_skill_carries_schemas_and_an_example(self) -> None:
        skill = _tool_skill(make_tool(list_site_clients))

        assert skill.name == "list_site_clients"
        assert skill.description == "List clients for a site."
        assert skill.inputSchema["properties"]["site_id"]["type"] == "string"
        assert skill.examples[0]["tool"] == "list_site_clients"

    def test_resource_uri_uses_the_declared_description(self) -> None:
        resource = make_resource(
            lambda: "payload", uri="unifi://sites", name="sites", description="All sites"
        )

        converted = _resource_uri(resource)

        assert converted.uri == "unifi://sites"
        assert converted.description == "All sites"

    def test_resource_uri_falls_back_to_a_generated_description(self) -> None:
        resource = make_resource(lambda: "payload", uri="unifi://devices", name="devices")

        converted = _resource_uri(resource)

        assert converted.description == "MCP resource: devices"
        assert converted.mimeType == "text/plain"


class TestBuildAgentCard:
    """Tests for build_agent_card."""

    def test_builds_skills_resources_and_safety_requirements(
        self, local_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(TOOL_TIERS, "list_site_clients", "read")
        monkeypatch.setitem(TOOL_TIERS, "delete_site_device", "destructive")
        mcp = FakeMCP(
            {
                "tool:list_site_clients@": make_tool(list_site_clients),
                "tool:delete_site_device@": make_tool(delete_site_device),
                "resource:sites@": make_resource(
                    lambda: "payload", uri="unifi://sites", name="sites"
                ),
            }
        )

        card = build_agent_card(mcp, local_settings)

        assert {skill["name"] for skill in card["skills"]} == {
            "list_site_clients",
            "delete_site_device",
        }
        resources = card["metadata"]["resources"]
        assert [resource["uri"] for resource in resources] == ["unifi://sites"]
        requirements = card["metadata"]["safetyRequirements"]
        assert [req["toolName"] for req in requirements] == ["delete_site_device"]
        assert card["protocolVersion"] == "0.3.0"
        assert card["metadata"]["integrationExamples"]

    def test_ignores_components_that_are_neither_tools_nor_resources(
        self, local_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(TOOL_TIERS, "list_site_clients", "read")
        mcp = FakeMCP(
            {
                "tool:list_site_clients@": make_tool(list_site_clients),
                "prompt:some_prompt@": object(),
            }
        )

        card = build_agent_card(mcp, local_settings)

        assert [skill["name"] for skill in card["skills"]] == ["list_site_clients"]
        assert card["metadata"]["resources"] == []

    def test_the_card_carries_no_controller_address(self, local_settings: Settings) -> None:
        """The card is public metadata: it must not name the controller."""
        card = build_agent_card(FakeMCP(), local_settings)

        assert "192.0.2.10" not in str(card)
        assert "localHost" not in card["metadata"]
        assert "cloudApiUrl" not in card["metadata"]

    def test_the_card_reports_the_api_type(self, local_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), local_settings)

        assert card["metadata"]["apiType"] == APIType.LOCAL.value
        assert card["metadata"]["toolCount"] == 0

    def test_the_cloud_card_reports_the_cloud_api_type(self, cloud_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), cloud_settings)

        assert card["metadata"]["apiType"] == cloud_settings.api_type.value
        assert card["metadata"]["apiModes"] == [cloud_settings.api_type.value]

    def test_the_card_names_the_server(self, local_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), local_settings)

        assert card["name"] == "unifi-mcp-server"


def test_repository_agent_card_matches_the_reference_card() -> None:
    """``agent-card.json`` is the reference card for a default deployment.

    The file once advertised a "planned" 0.4.0 card with capabilities the
    route never listed. The card is now built from the live tool registry,
    so the served card legitimately differs between configurations; the
    repository artifact pins the *default* configuration and this test
    checks that the builder still produces it.

    Regenerate the file with
    ``python scripts/generate_agent_card.py`` when this fails.
    """
    import json

    card_file = Path(__file__).resolve().parents[3] / "agent-card.json"
    stored = json.loads(card_file.read_text())

    card = _reference_card()

    # The version follows the package version, so a release bump changes
    # one field of the artifact.
    assert _canonical(stored) == _canonical(card)


#: The repository root, for the paths this module reads.
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def local_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Return Settings configured for local controller access.

    Defined here rather than taken from the package conftest, so this module
    does not depend on how pytest registers that conftest.
    """
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


def _subprocess_env() -> dict[str, str]:
    """Return a clean environment for a subprocess.

    The session's ``PYTHONPATH`` can point at a different interpreter's
    packages, which would break the child's imports.
    """
    import os

    return {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}


def _canonical(document: Any) -> Any:
    """Return a document with every mapping's keys in sorted order.

    The artifact is written with sorted keys, so the comparison must not
    depend on the order the builder happens to produce.
    """
    if isinstance(document, dict):
        return {key: _canonical(value) for key, value in sorted(document.items())}
    if isinstance(document, list):
        return [_canonical(value) for value in document]
    return document


def _reference_env() -> dict[str, str]:
    """Return the environment the repository card artifact was generated with.

    It is read from the generator script, so the artifact and this test
    cannot drift apart.
    """
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "scripts" / "generate_agent_card.py"
    spec = importlib.util.spec_from_file_location("generate_agent_card", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.ENVIRONMENT)


def _reference_settings() -> Settings:
    """Return the settings the repository card artifact was generated with.

    The values are set explicitly rather than read from the environment,
    because the test session clears the UNIFI_* variables.
    """
    return Settings.model_validate(_reference_env())


def _reference_card() -> Any:
    """Return the card the repository artifact was generated from.

    The import happens in a subprocess and the card is built there, because
    importing the server in-process would reuse whatever ``src.main``
    another test module already cached under a different environment, and
    the card is built from the tools that import registered. A subprocess
    gives a clean import and leaves the test session's module cache alone.
    """
    import json
    import subprocess
    import sys

    reference = _reference_env()
    script = (
        "import json\n"
        "import src.main as main\n"
        "from src.a2a.agent_card import build_agent_card\n"
        "from src.config import Settings\n"
        f"settings = Settings.model_validate({reference!r})\n"
        "card = build_agent_card(main.mcp, settings)\n"
        "card['skills'] = sorted(card['skills'], key=lambda s: s['name'])\n"
        "print(json.dumps(card))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT),
        env={**_subprocess_env(), **reference},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)
