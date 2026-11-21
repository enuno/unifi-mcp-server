"""Contract checks against the pinned UniFi Protect 7.4.96 specification."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.models import ProtectModelUpdateMessage

SPEC_PATH = Path(__file__).parents[3] / "scripts" / "protect-api-spec-v7.4.96.json"


def _spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def test_model_updates_contract_is_websocket_with_required_filter():
    operation = _spec()["paths"]["/v1/subscribe/updates"]["get"]

    assert "WebSocket" in operation["description"]
    assert "WebSocket updates" in operation["tags"]
    model_keys = next(item for item in operation["parameters"] if item["name"] == "modelKeys")
    assert model_keys["required"] is True
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/modelUpdateEvent"
    }


def test_model_update_model_matches_pinned_discriminator_values():
    schema = _spec()["components"]["schemas"]["integrationExternalArmProfileEvent"]
    expected_types = set(schema["discriminator"]["mapping"])

    assert expected_types == {"add", "update", "remove"}
    for event_type in expected_types:
        message = ProtectModelUpdateMessage.model_validate(
            {"type": event_type, "item": {"id": "record-1", "modelKey": "externalArmProfile"}}
        )
        assert message.type == event_type

    with pytest.raises(ValidationError):
        ProtectModelUpdateMessage.model_validate({"type": "invalid", "item": {"id": "record-1"}})


def test_model_update_uses_protect_v7_model_architecture():
    assert ProtectModelUpdateMessage.__module__ == "src.models.protect_v7"
