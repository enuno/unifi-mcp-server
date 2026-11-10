"""Versioned, minimized evidence contract for bounded inventory reads."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class EvidenceScope(BaseModel):
    """Controller and resolved site that produced the evidence."""

    controller: Literal["default"] = "default"
    site_id: str


class EvidenceSection(BaseModel):
    """Outcome for one source collection, distinct from payload emptiness."""

    status: Literal["ok", "empty", "partial", "failed", "unsupported", "unavailable"]
    source: Literal["integration.v1"] = "integration.v1"
    observed_at: datetime | None = None
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"
    count: int = Field(ge=0)
    pages: int = Field(ge=0)
    truncated: bool = False
    reason: (
        Literal[
            "collection_error",
            "timeout",
            "repeated_page",
            "invalid_response",
            "page_limit",
            "missing_identity",
        ]
        | None
    ) = None


class DeviceEvidence(BaseModel):
    """Allowlisted device identity; no names, addresses or raw payloads."""

    id: str
    state: Literal["ONLINE", "OFFLINE", "UNKNOWN"] = "UNKNOWN"


class ClientEvidence(BaseModel):
    """Ephemeral client reference scoped to one response, not a person identifier."""

    ref: str


class InventoryData(BaseModel):
    """Only explicit, minimized inventory fields may leave the collector."""

    devices: list[DeviceEvidence] = Field(default_factory=list)
    clients: list[ClientEvidence] = Field(default_factory=list)


class EvidenceRelationship(BaseModel):
    """Link reported explicitly by the controller, never inferred from absence."""

    source: str
    target: str
    kind: Literal["uplink"] = "uplink"
    basis: Literal["observed"] = "observed"


class InventoryEvidence(BaseModel):
    """Additive schema-v1 response; not an atomic or persisted snapshot."""

    schema_version: Literal["1"] = "1"
    scope: EvidenceScope
    collection_started_at: datetime
    collection_completed_at: datetime
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"
    completeness: Literal["complete", "partial", "failed"]
    sections: dict[Literal["devices", "clients"], EvidenceSection]
    data: InventoryData
    relationships: list[EvidenceRelationship] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=lambda: ["non_atomic_collection"])
    redaction: Literal["allowlist; client names, addresses and raw payloads excluded"] = (
        "allowlist; client names, addresses and raw payloads excluded"
    )

    @model_validator(mode="after")
    def reject_false_complete(self) -> "InventoryEvidence":
        """A failed or truncated child cannot yield a complete envelope."""
        if self.completeness == "complete" and (
            set(self.sections) != {"devices", "clients"}
            or any(
                section.status not in {"ok", "empty"} or section.truncated
                for section in self.sections.values()
            )
        ):
            raise ValueError("Complete evidence requires two successful, untruncated sections")
        return self
