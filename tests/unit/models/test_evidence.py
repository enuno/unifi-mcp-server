"""Offline evidence-contract invariants (EV-02)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.models.evidence import EvidenceScope, EvidenceSection, InventoryData, InventoryEvidence


def evidence(sections, completeness):
    now = datetime.now(UTC)
    return InventoryEvidence(
        scope=EvidenceScope(site_id="site"),
        collection_started_at=now,
        collection_completed_at=now,
        sections=sections,
        completeness=completeness,
        data=InventoryData(),
    )


def test_complete_requires_all_sections_succeeded_without_truncation():
    ok = EvidenceSection(status="empty", count=0, pages=1)
    evidence({"devices": ok, "clients": ok}, "complete")
    with pytest.raises(ValidationError, match="Complete evidence"):
        evidence(
            {"devices": ok, "clients": EvidenceSection(status="failed", count=0, pages=0)},
            "complete",
        )
    with pytest.raises(ValidationError, match="Complete evidence"):
        evidence(
            {
                "devices": EvidenceSection(status="partial", count=2, pages=1, truncated=True),
                "clients": ok,
            },
            "complete",
        )


def test_missing_observation_timestamp_keeps_freshness_unknown():
    section = EvidenceSection(status="ok", count=1, pages=1)
    assert section.observed_at is None
    assert section.freshness == "unknown"
    assert evidence({"devices": section, "clients": section}, "complete").freshness == "unknown"
