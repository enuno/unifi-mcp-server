"""Core A2A prompt playbook engine.

The playbook engine turns structured operational workflows into prompt-ready
instructions for an agent that can call UniFi MCP tools.

Example:
    >>> from src.a2a.prompt_playbook import render_playbook
    >>> print(render_playbook("network_diagnostics", {"site_id": "default"}))
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class PlaybookStep:
    """A single ordered action in a prompt playbook."""

    order: int
    action: str
    tool: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    validation: str = ""
    fallback: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the step."""
        return asdict(self)


@dataclass(slots=True)
class PromptPlaybook:
    """A structured operational prompt for a specific UniFi workflow."""

    name: str
    description: str
    steps: list[PlaybookStep] = field(default_factory=list)
    requiredSkills: list[str] = field(default_factory=list)
    safetyLevel: str = "none"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the playbook."""
        payload = asdict(self)
        payload["steps"] = [step.to_dict() for step in self.steps]
        return payload


class PlaybookRegistry:
    """Registry for prompt playbooks."""

    def __init__(self, playbooks: Iterable[PromptPlaybook] | None = None) -> None:
        """Create an empty registry, registering any playbooks supplied up front."""
        self._playbooks: dict[str, PromptPlaybook] = {}
        if playbooks:
            for playbook in playbooks:
                self.register(playbook)

    def register(self, playbook: PromptPlaybook) -> None:
        """Register or replace a playbook by name."""
        self._playbooks[playbook.name] = playbook

    def get(self, name: str) -> PromptPlaybook:
        """Return a playbook by name."""
        try:
            return self._playbooks[name]
        except KeyError as exc:
            raise KeyError(f"Unknown playbook: {name}") from exc

    def names(self) -> list[str]:
        """Return registered playbook names in sorted order."""
        return sorted(self._playbooks)

    def items(self) -> list[tuple[str, PromptPlaybook]]:
        """Return registered playbooks as ``(name, playbook)`` pairs."""
        return [(name, self._playbooks[name]) for name in self.names()]

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Return the registry as a JSON-serializable mapping."""
        return {name: playbook.to_dict() for name, playbook in self.items()}

    @classmethod
    def load_builtin(cls) -> PlaybookRegistry:
        """Load bundled playbooks from ``src.a2a.playbooks``."""
        module = importlib.import_module("src.a2a.playbooks")
        playbooks = getattr(module, "PLAYBOOKS", [])
        return cls(playbooks)


DEFAULT_PLAYBOOK_REGISTRY = PlaybookRegistry.load_builtin()


def _default_registry() -> PlaybookRegistry:
    """Return the bundled registry, populating it on first use if it is empty.

    ``src.a2a.playbooks`` imports this module, so importing that package first
    builds the registry above while the package is still initializing and
    ``PLAYBOOKS`` does not exist yet, leaving it empty.
    """
    if not DEFAULT_PLAYBOOK_REGISTRY.names():
        for _, playbook in PlaybookRegistry.load_builtin().items():
            DEFAULT_PLAYBOOK_REGISTRY.register(playbook)
    return DEFAULT_PLAYBOOK_REGISTRY


def _format_params(params: Mapping[str, Any] | None) -> str:
    if not params:
        return "{}"
    return json.dumps(dict(params), indent=2, sort_keys=True, ensure_ascii=False, default=str)


def render_playbook(
    playbook_name: str,
    context: Mapping[str, Any] | None = None,
    registry: PlaybookRegistry | None = None,
) -> str:
    """Render a playbook into structured prompt text.

    Args:
        playbook_name: Name of the playbook to render.
        context: Optional JSON-serializable runtime context.
        registry: Optional registry instance. Defaults to the bundled registry.

    Returns:
        A prompt-ready string with steps, validation criteria, and fallbacks.
    """
    active_registry = registry or _default_registry()
    playbook = active_registry.get(playbook_name)
    context_data = dict(context or {})

    lines: list[str] = [
        f"# A2A Prompt Playbook: {playbook.name}",
        "",
        f"Description: {playbook.description}",
        f"Safety level: {playbook.safetyLevel}",
        f"Required skills: {', '.join(playbook.requiredSkills) if playbook.requiredSkills else 'none'}",
        "",
        "## Context",
        "```json",
        json.dumps(context_data, indent=2, sort_keys=True, ensure_ascii=False, default=str),
        "```",
        "",
        "## Execution Steps",
    ]

    for step in sorted(playbook.steps, key=lambda item: item.order):
        lines.extend(
            [
                f"### Step {step.order}: {step.action}",
                f"Tool: {step.tool or 'none'}",
                "Parameters:",
                "```json",
                _format_params(step.params),
                "```",
                f"Validation: {step.validation or 'confirm the action completed successfully.'}",
                f"Fallback: {step.fallback or 'pause and request human guidance.'}",
                "",
            ]
        )

    lines.extend(
        [
            "## Operating Notes",
            "- Prefer the least disruptive action that satisfies the workflow.",
            "- Use the validation steps before moving to the next step.",
            "- Stop immediately if the safety level requires confirmation and consent is missing.",
        ]
    )
    return "\n".join(lines)
