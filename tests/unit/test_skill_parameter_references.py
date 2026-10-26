"""Checks that the skills' parameter names match the registered tools.

A skill can name a tool that exists and still get its arguments wrong. An
operator following the skill then calls the tool with a parameter the
schema does not have, and the call fails at the controller rather than at
the schema check.

This test parses the parameter names a skill mentions next to a tool name
and compares them against the tool's registered input schema.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"

#: The environment the registry is read in. It mirrors the one the artifact
#: generator uses, so the two cannot disagree about the tool surface.
_REGISTRY_ENV = {
    "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
    "UNIFI_API_TYPE": "local",
    "UNIFI_LOCAL_HOST": "192.0.2.1",
    "AGNOST_ENABLED": "false",
}

#: Arguments the server adds to every tool, so a skill never mentions them.
_SERVER_ARGUMENTS = frozenset(
    {
        "confirm",
        "controller",
        "dry_run",
        "site_id",
    }
)

#: A parameter name, in backticks, next to a tool name in the same cell.
_PARAMETER_PATTERN = re.compile(r"`([a-z][a-z0-9_]*)`")


def _registered_schemas() -> dict[str, dict[str, list[str]]]:
    """Return every registered tool's parameter names and required arguments.

    The registry is read in a subprocess, because importing the server
    in-process would reuse whatever ``src.main`` another test module already
    cached under a different environment.
    """
    script = (
        "import json\n"
        "import src.main as M\n"
        "out = {}\n"
        "for key, component in M.mcp._local_provider._components.items():\n"
        "    if not key.startswith('tool:'):\n"
        "        continue\n"
        "    name = key[5:].split('@', 1)[0]\n"
        "    schema = getattr(component, 'parameters', None) or {}\n"
        "    out[name] = {\n"
        "        'props': sorted(schema.get('properties', {})),\n"
        "        'required': sorted(schema.get('required', [])),\n"
        "    }\n"
        "print(json.dumps(out))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT),
        env={
            **{k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
            **_REGISTRY_ENV,
        },
        capture_output=True,
        text=True,
        check=True,
    )
    import json

    schemas = json.loads(result.stdout)
    _TOOL_NAMES.clear()
    _TOOL_NAMES.extend(sorted(schemas))
    return schemas


#: Every registered tool name, filled in when the registry is read.
_TOOL_NAMES: list[str] = []


def _skill_files() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def _mentioned_parameters(text: str, tool: str) -> set[str]:
    """Return the parameter names a skill states for a tool.

    A parameter counts as stated when it appears in backticks in a phrase
    that names the tool, such as "authorize_guest with client_id ..." or
    "`create_vouchers` (`count`, `time_limit_minutes`)".
    """
    found: set[str] = set()
    for line in text.splitlines():
        if tool not in line:
            continue
        for phrase in _parameter_phrases(line, tool):
            found.update(_PARAMETER_PATTERN.findall(phrase))
    return found


def _parameter_phrases(line: str, tool: str) -> list[str]:
    """Return the stretches of a line that state parameters for a tool.

    Only an explicit argument list counts: a parenthesised or bracketed
    group of backticked names that follows the tool name. Prose that merely
    mentions a word near the tool name is not an argument claim, because a
    skill legitimately mentions response fields, function names and
    contrasting spellings in the same breath.
    """
    index = line.find(tool)
    if index < 0:
        return []
    remainder = line[index + len(tool) :]

    phrases: list[str] = []
    for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
        start = remainder.find(opening)
        if start < 0:
            continue
        end = remainder.find(closing, start)
        if end < 0:
            continue
        group = remainder[start : end + 1]
        # The group has to hold backticked names to be an argument list.
        if _PARAMETER_PATTERN.findall(group):
            phrases.append(group)
    return phrases


class TestSkillParameterNames:
    def test_the_registry_was_read(self) -> None:
        assert len(_registered_schemas()) > 100

    @pytest.mark.parametrize(
        "skill_file",
        _skill_files(),
        ids=lambda path: path.parent.name,
    )
    def test_no_skill_states_a_parameter_the_tool_does_not_accept(self, skill_file: Path) -> None:
        """A skill must not name an argument its tool does not have."""
        schemas = _registered_schemas()
        if not _TOOL_NAMES:
            _TOOL_NAMES.extend(sorted(schemas))
        text = skill_file.read_text()

        problems: list[str] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            for tool in _tools_in_line(line, schemas):
                stated = _mentioned_parameters(line, tool)
                for parameter in stated:
                    if parameter in _SERVER_ARGUMENTS:
                        continue
                    if parameter not in schemas[tool]["props"]:
                        problems.append(
                            f"{skill_file.parent.name}/SKILL.md:{line_number} "
                            f"{tool} does not accept {parameter!r}"
                        )

        assert not problems, "\n".join(problems)


def _tools_in_line(line: str, schemas: dict[str, dict[str, list[str]]]) -> list[str]:
    """Return the tool names a line refers to."""
    return [name for name in schemas if f"`{name}`" in line]
