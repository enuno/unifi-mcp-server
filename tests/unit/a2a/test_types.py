"""Unit tests for src/a2a/types.py."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path

import pytest

from src.a2a.types import (
    A2AJSONEncoder,
    AgentCard,
    AuthenticationMode,
    DelegationContract,
    ResourceURI,
    SafetyRequirement,
    Skill,
)


def make_skill() -> Skill:
    """Build a representative skill."""
    return Skill(
        name="list_site_clients",
        description="List clients for a site.",
        inputSchema={"type": "object"},
        outputSchema={"type": "object"},
        examples=[{"tool": "list_site_clients", "arguments": {}}],
    )


class TestAuthenticationMode:
    """Tests for the AuthenticationMode enum."""

    def test_values(self) -> None:
        assert AuthenticationMode.LOCAL.value == "local"
        assert AuthenticationMode.CLOUD.value == "cloud"
        assert AuthenticationMode.BOTH.value == "both"

    def test_behaves_as_a_string(self) -> None:
        assert AuthenticationMode.LOCAL == "local"


class TestA2AJSONEncoder:
    """Tests for A2AJSONEncoder."""

    def test_encodes_dataclasses(self) -> None:
        payload = json.loads(json.dumps(make_skill(), cls=A2AJSONEncoder))

        assert payload["name"] == "list_site_clients"

    def test_encodes_enums_by_value(self) -> None:
        class Colour(Enum):
            RED = "red"

        assert json.dumps(Colour.RED, cls=A2AJSONEncoder) == '"red"'

    def test_string_enums_serialize_as_their_value(self) -> None:
        assert json.dumps(AuthenticationMode.BOTH, cls=A2AJSONEncoder) == '"both"'

    def test_encodes_datetimes_and_dates_as_iso_strings(self) -> None:
        moment = datetime(2026, 1, 1, tzinfo=timezone.utc)

        assert json.dumps(moment, cls=A2AJSONEncoder) == f'"{moment.isoformat()}"'
        assert json.dumps(date(2026, 1, 1), cls=A2AJSONEncoder) == '"2026-01-01"'

    def test_encodes_paths_as_strings(self) -> None:
        target = Path("logs") / "audit.jsonl"

        assert json.dumps(target, cls=A2AJSONEncoder) == json.dumps(str(target))

    def test_encodes_sets_as_sorted_lists(self) -> None:
        assert json.dumps({"b", "a"}, cls=A2AJSONEncoder) == '["a", "b"]'

    def test_unsupported_types_still_raise(self) -> None:
        with pytest.raises(TypeError):
            json.dumps(object(), cls=A2AJSONEncoder)


class TestSkill:
    """Tests for Skill."""

    def test_to_dict_round_trips(self) -> None:
        payload = make_skill().to_dict()

        assert payload["name"] == "list_site_clients"
        assert payload["examples"][0]["tool"] == "list_site_clients"


class TestResourceURI:
    """Tests for ResourceURI."""

    def test_to_dict_round_trips(self) -> None:
        resource = ResourceURI(
            uri="unifi://sites",
            name="sites",
            description="All sites.",
            mimeType="application/json",
        )

        assert resource.to_dict() == {
            "uri": "unifi://sites",
            "name": "sites",
            "description": "All sites.",
            "mimeType": "application/json",
        }


class TestSafetyRequirement:
    """Tests for SafetyRequirement."""

    def test_optional_fields_default_to_none(self) -> None:
        requirement = SafetyRequirement(
            confirmationLevel="required", destructive=True, sensitiveFields=["confirm"]
        )

        assert requirement.toolName is None
        assert requirement.reason is None

    def test_to_dict_round_trips(self) -> None:
        requirement = SafetyRequirement("required", True, ["confirm"], "delete_site", "Deletes.")

        assert requirement.to_dict() == {
            "confirmationLevel": "required",
            "destructive": True,
            "sensitiveFields": ["confirm"],
            "toolName": "delete_site",
            "reason": "Deletes.",
        }


class TestDelegationContract:
    """Tests for DelegationContract."""

    def test_optional_fields_default_sensibly(self) -> None:
        contract = DelegationContract(
            contractId="c1",
            toolName="list_site_clients",
            params={},
            requestingAgent="agent-a",
            authenticationMode=AuthenticationMode.BOTH,
            createdAt="2026-01-01T00:00:00+00:00",
            requiresConfirmation=False,
        )

        assert contract.safetyRequirement is None
        assert contract.metadata is None
        assert contract.dryRun is False

    def test_to_dict_nests_the_safety_requirement(self) -> None:
        contract = DelegationContract(
            contractId="c1",
            toolName="delete_site",
            params={"confirm": True},
            requestingAgent="agent-a",
            authenticationMode=AuthenticationMode.LOCAL,
            createdAt="2026-01-01T00:00:00+00:00",
            requiresConfirmation=True,
            safetyRequirement=SafetyRequirement("required", True, ["confirm"]),
        )

        payload = contract.to_dict()

        assert payload["safetyRequirement"]["destructive"] is True
        assert json.dumps(payload, cls=A2AJSONEncoder)


class TestAgentCard:
    """Tests for AgentCard."""

    def test_defaults_to_the_a2a_protocol(self) -> None:
        card = AgentCard(
            name="UniFi",
            version="1.0.0",
            description="UniFi MCP server.",
            authenticationMode=AuthenticationMode.BOTH,
            skills=[],
            resources=[],
            safetyRequirements=[],
            integrationExamples=[],
        )

        assert card.protocol == "A2A"
        assert card.metadata is None

    def test_to_dict_serializes_nested_members(self) -> None:
        card = AgentCard(
            name="UniFi",
            version="1.0.0",
            description="UniFi MCP server.",
            authenticationMode=AuthenticationMode.BOTH,
            skills=[make_skill()],
            resources=[ResourceURI("unifi://sites", "sites", "All sites.", "application/json")],
            safetyRequirements=[SafetyRequirement("required", True, ["confirm"])],
            integrationExamples=["Ask the agent to list clients."],
            metadata={"skillCount": 1},
        )

        payload = card.to_dict()

        assert payload["skills"][0]["name"] == "list_site_clients"
        assert payload["resources"][0]["uri"] == "unifi://sites"
        assert payload["safetyRequirements"][0]["confirmationLevel"] == "required"
        assert json.dumps(payload, cls=A2AJSONEncoder)
