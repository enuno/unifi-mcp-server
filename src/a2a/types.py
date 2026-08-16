"""Core A2A protocol data types for UniFi MCP Server.

These types are intentionally lightweight dataclasses so they can be serialized
into JSON payloads without additional runtime dependencies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
from json import JSONEncoder
from pathlib import Path
from typing import Any


class A2AJSONEncoder(JSONEncoder):
    """JSON encoder that knows how to serialize A2A dataclasses and enums."""

    def default(self, o: Any) -> Any:
        """Convert supported types into JSON-serializable values."""
        if is_dataclass(o):
            return asdict(o)
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, datetime | date):
            return o.isoformat()
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, set):
            return sorted(o)
        return super().default(o)


class AuthenticationMode(str, Enum):
    """Supported authentication modes for the UniFi MCP server."""

    LOCAL = "local"
    CLOUD = "cloud"
    BOTH = "both"


@dataclass(slots=True)
class Skill:
    """A specialized capability exposed by the MCP server.

    Attributes:
        name: Skill name, typically matching the MCP tool name.
        description: Human readable description of the skill.
        inputSchema: JSON schema describing accepted inputs.
        outputSchema: JSON schema describing tool output.
        examples: Example invocation payloads.
    """

    name: str
    description: str
    inputSchema: dict[str, Any]
    outputSchema: dict[str, Any]
    examples: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the skill."""
        return asdict(self)


@dataclass(slots=True)
class ResourceURI:
    """A discoverable MCP resource URI."""

    uri: str
    name: str
    description: str
    mimeType: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the resource URI."""
        return asdict(self)


@dataclass(slots=True)
class SafetyRequirement:
    """Safety metadata for a tool or skill.

    Attributes:
        confirmationLevel: Confirmation policy required before execution.
        destructive: Whether the operation mutates or removes controller state.
        sensitiveFields: Parameter names that should be handled carefully.
    """

    confirmationLevel: str
    destructive: bool
    sensitiveFields: list[str]
    toolName: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the safety requirement."""
        return asdict(self)


@dataclass(slots=True)
class DelegationContract:
    """Contract used to delegate a tool invocation between agents."""

    contractId: str
    toolName: str
    params: dict[str, Any]
    requestingAgent: str
    authenticationMode: AuthenticationMode
    createdAt: str
    requiresConfirmation: bool
    safetyRequirement: SafetyRequirement | None = None
    metadata: dict[str, Any] | None = None
    dryRun: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the delegation contract."""
        return asdict(self)


@dataclass(slots=True)
class AgentCard:
    """A dynamically generated A2A agent card for the UniFi MCP server."""

    name: str
    version: str
    description: str
    authenticationMode: AuthenticationMode
    skills: list[Skill]
    resources: list[ResourceURI]
    safetyRequirements: list[SafetyRequirement]
    integrationExamples: list[str]
    protocol: str = "A2A"
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the agent card."""
        return asdict(self)


__all__ = [
    "A2AJSONEncoder",
    "AgentCard",
    "AuthenticationMode",
    "DelegationContract",
    "ResourceURI",
    "SafetyRequirement",
    "Skill",
]
