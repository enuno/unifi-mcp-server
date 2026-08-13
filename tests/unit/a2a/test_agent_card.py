"""Unit tests for src/a2a/agent_card.py."""

from __future__ import annotations

import importlib.metadata
from types import SimpleNamespace
from typing import Any

import pytest

from src.a2a.agent_card import (
    _authentication_mode,
    _example_call_payload,
    _example_value_for_schema,
    _is_destructive_tool,
    _iter_registered_components,
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


class TestIterRegisteredComponents:
    """Tests for _iter_registered_components."""

    def test_yields_components_from_each_provider(self) -> None:
        tool = make_tool(list_site_clients)
        mcp = FakeMCP({"list_site_clients": tool})

        assert list(_iter_registered_components(mcp)) == [("list_site_clients", tool)]

    def test_returns_nothing_when_mcp_has_no_providers(self) -> None:
        assert list(_iter_registered_components(object())) == []

    def test_skips_providers_whose_components_are_not_a_dict(self) -> None:
        class BadProvider:
            _components = ["not", "a", "dict"]

        mcp = type("M", (), {"providers": [BadProvider()]})()

        assert list(_iter_registered_components(mcp)) == []


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


class TestIsDestructiveTool:
    """Tests for _is_destructive_tool."""

    def test_destructive_name_is_detected(self) -> None:
        assert _is_destructive_tool(make_tool(delete_site_device)) is True

    def test_a_destructive_description_is_detected(self) -> None:
        def touch_site(site_id: str) -> dict[str, Any]:
            """Reboot the controller."""
            return {}

        assert _is_destructive_tool(make_tool(touch_site)) is True

    def test_confirm_parameter_marks_a_tool_destructive(self) -> None:
        def ambiguous(site_id: str, confirm: bool = False) -> dict[str, Any]:
            """Do something unremarkable."""
            return {}

        assert _is_destructive_tool(make_tool(ambiguous)) is True

    def test_read_only_tool_is_not_destructive(self) -> None:
        assert _is_destructive_tool(make_tool(list_site_clients)) is False


class TestSensitiveFields:
    """Tests for _sensitive_fields."""

    def test_detects_and_sorts_sensitive_parameter_names(self) -> None:
        def login(username: str, password: str, api_key: str, site_id: str) -> dict[str, Any]:
            """Authenticate."""
            return {}

        assert _sensitive_fields(make_tool(login)) == ["api_key", "password", "username"]

    def test_returns_empty_list_when_nothing_is_sensitive(self) -> None:
        assert _sensitive_fields(make_tool(list_site_clients)) == []

    def test_returns_empty_list_when_properties_are_not_a_dict(self) -> None:
        tool = make_tool(list_site_clients)
        tool.parameters = {"type": "object", "properties": "bogus"}

        assert _sensitive_fields(tool) == []


class TestSafetyRequirementForTool:
    """Tests for _safety_requirement_for_tool."""

    def test_returns_none_for_a_safe_read_only_tool(self) -> None:
        assert _safety_requirement_for_tool(make_tool(list_site_clients)) is None

    def test_destructive_tool_requires_confirmation(self) -> None:
        requirement = _safety_requirement_for_tool(make_tool(delete_site_device))

        assert requirement is not None
        assert requirement.confirmationLevel == "required"
        assert requirement.destructive is True
        assert requirement.toolName == "delete_site_device"
        assert "confirmation" in (requirement.reason or "")

    def test_sensitive_only_tool_is_recommended_not_required(self) -> None:
        def authenticate(token: str) -> dict[str, Any]:
            """Exchange a token."""
            return {}

        requirement = _safety_requirement_for_tool(make_tool(authenticate))

        assert requirement is not None
        assert requirement.confirmationLevel == "recommended"
        assert requirement.destructive is False
        assert requirement.sensitiveFields == ["token"]


class TestAuthenticationMode:
    """Tests for _authentication_mode."""

    @pytest.mark.parametrize("api_type", [APIType.LOCAL, APIType.CLOUD_V1, APIType.CLOUD_EA])
    def test_every_api_type_supports_both_modes(
        self, local_settings: Settings, api_type: APIType
    ) -> None:
        local_settings.api_type = api_type

        assert _authentication_mode(local_settings) is AuthenticationMode.BOTH

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
        self, local_settings: Settings
    ) -> None:
        mcp = FakeMCP(
            {
                "list_site_clients": make_tool(list_site_clients),
                "delete_site_device": make_tool(delete_site_device),
                "sites": make_resource(lambda: "payload", uri="unifi://sites", name="sites"),
            }
        )

        card = build_agent_card(mcp, local_settings)

        assert {skill.name for skill in card.skills} == {
            "list_site_clients",
            "delete_site_device",
        }
        assert [resource.uri for resource in card.resources] == ["unifi://sites"]
        assert [req.toolName for req in card.safetyRequirements] == ["delete_site_device"]
        assert card.protocol == "A2A"
        assert card.integrationExamples

    def test_ignores_components_that_are_neither_tools_nor_resources(
        self, local_settings: Settings
    ) -> None:
        mcp = FakeMCP(
            {
                "list_site_clients": make_tool(list_site_clients),
                "some_prompt": object(),
            }
        )

        card = build_agent_card(mcp, local_settings)

        assert [skill.name for skill in card.skills] == ["list_site_clients"]
        assert card.resources == []

    def test_local_settings_expose_the_local_host(self, local_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), local_settings)

        assert card.metadata is not None
        assert card.metadata["localHost"] == "192.0.2.10"
        assert "cloudApiUrl" not in card.metadata
        assert card.metadata["skillCount"] == 0
        assert card.metadata["apiType"] == APIType.LOCAL.value

    def test_cloud_settings_expose_the_cloud_api_url(self, cloud_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(), cloud_settings)

        assert card.metadata is not None
        assert card.metadata["cloudApiUrl"] == cloud_settings.cloud_api_url
        assert "localHost" not in card.metadata

    def test_server_name_is_read_from_the_mcp_instance(self, local_settings: Settings) -> None:
        card = build_agent_card(FakeMCP(name="Custom Server"), local_settings)

        assert card.name == "Custom Server"

    def test_falls_back_to_the_default_server_name(self, local_settings: Settings) -> None:
        card = build_agent_card(object(), local_settings)

        assert card.name == "UniFi MCP Server"
        assert card.metadata is not None
        assert card.metadata["toolModules"] == 0
