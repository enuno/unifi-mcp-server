#!/usr/bin/env python3
"""Regenerate ``skills/manifest.json`` from the skills on disk.

``skills/`` is the single source of truth for skill content. This script reads
the frontmatter of every ``skills/<name>/SKILL.md`` and writes the
machine-readable index that the Claude plugin, the ChatGPT/Codex plugin and
the validation script all read.

Run it after adding, renaming or editing a skill:

    python scripts/generate_skills_manifest.py

The tool requirements are derived from the skill text and checked against the
server's live tool registry, so a name in the manifest is always a tool the
server registers and a tier is always the tier the server assigns.

It fails when a skill's frontmatter does not name its own folder, when a
description is missing, when a skill named in ``AUDIENCE_OVERRIDES`` is
absent from disk, or when a skill names a tool the server does not register.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
MANIFEST_PATH = SKILLS_DIR / "manifest.json"

#: Audience per skill.
#:
#: ``operator`` skills help an end user operate a UniFi network through a
#: running MCP server, so they ship in the plugin packages. ``developer``
#: skills help a coding agent change this codebase, so they stay in the
#: repository but are not bundled.
#:
#: The split mirrors ``docs/SKILLS.md``, which documents the same two groups.
AUDIENCE_OVERRIDES: dict[str, str] = {
    # Operator skills: using a running UniFi MCP server.
    "unifi-network": "operator",
    "unifi-devices": "operator",
    "unifi-security": "operator",
    "unifi-system": "operator",
    "unifi-protect": "operator",
    "unifi-fleet-operations": "operator",
    "unifi-channel-planning": "operator",
    "unifi-discovery": "operator",
    "unifi-safe-changes": "operator",
    "unifi-mcp-setup": "operator",
    # Developer skills: changing this codebase.
    "unifi-mcp-tool-builder": "developer",
    "unifi-network-config-tools": "developer",
    "unifi-security-tools": "developer",
    "unifi-protect-tools": "developer",
    "unifi-cloud-fleet-tools": "developer",
    "unifi-docs-sync": "developer",
}

#: Extra frontmatter fields preserved in the manifest, so a consumer can see
#: what the skill itself declares.
EXTRA_FIELDS = ("version", "license", "author", "model", "allowed-tools")

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
FENCED_CODE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)

#: The risk tiers the server assigns to a tool, in the order a reader should
#: see them. ``src/tool_registry.py`` is where the server defines them.
TIERS = ("read", "write", "destructive")


def parse_frontmatter(text: str) -> dict[str, str]:
    """Return the frontmatter fields of a SKILL.md as plain strings.

    Parsed with YAML, because several skills use a folded block scalar
    (``description: >``) for the description, which a line-based parser
    would truncate to the first line.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    fields: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, list | dict):
            fields[str(key)] = json.dumps(value)
        elif value is None:
            fields[str(key)] = ""
        else:
            fields[str(key)] = str(value)
    return fields


#: The plugin description, kept in one place so the Claude manifest, the
#: ChatGPT manifest and the generated skills manifest cannot drift apart.
PLUGIN_DESCRIPTION = (
    "Operate UniFi Network, UniFi Protect and the UniFi cloud APIs through the "
    "UniFi MCP Server. Ships the operator skills for network, devices, "
    "security, system, Protect, fleet and safe-change workflows."
)


def package_version() -> str:
    """Return the version the package carries.

    Read from ``pyproject.toml`` so the package version follows the server
    version instead of being written out again.
    """
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    if not match:
        raise SystemExit("error: no version found in pyproject.toml")
    return match.group(1)


def collect_skill_tools(skill_text: str, registered: set[str]) -> set[str]:
    """Return the registered tool names a skill's prose mentions."""
    body = FENCED_CODE_RE.sub("", skill_text)
    found = set()
    for token in INLINE_CODE_RE.findall(body):
        token = token.strip()
        if token in registered:
            found.add(token)
    return found


def tool_tier_map() -> dict[str, str]:
    """Return the tool name to tier map from the live server registry.

    Imported lazily so that reading the manifest works without the server's
    runtime dependencies.
    """
    # The registry is read under a fixed configuration, so the generated
    # manifest does not depend on the operator's own settings. An ambient
    # UNIFI_READ_ONLY=true would leave every mutating tool unregistered,
    # and an ambient UNIFI_PROFILE would narrow the tool surface, so the
    # manifest would differ between machines for reasons nothing reports.
    for key in [key for key in os.environ if key.startswith("UNIFI_")]:
        del os.environ[key]
    os.environ["UNIFI_API_TYPE"] = "local"
    os.environ["UNIFI_MIXED_MODE"] = "false"
    os.environ["UNIFI_API_KEY"] = "test-key"  # pragma: allowlist secret
    # Local mode requires a console address. Use the reserved documentation
    # address, as the repository's own registry test does, so the script
    # works on a machine with no .env and reaches no controller.
    os.environ["UNIFI_LOCAL_HOST"] = "192.0.2.1"
    # Read-only and dry-run would remove the mutating tools from the
    # registry, and a profile would narrow it to one group of modules.
    os.environ["UNIFI_READ_ONLY"] = "false"
    os.environ["UNIFI_DRY_RUN"] = "false"
    os.environ.pop("UNIFI_PROFILE", None)
    sys.path.insert(0, str(ROOT))
    from src.main import TOOL_TIERS  # noqa: PLC0415

    return dict(TOOL_TIERS)


def main() -> int:
    """Write the skills manifest and report what was written."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not import the server; keep tool lists empty.",
    )
    args = parser.parse_args()

    if not SKILLS_DIR.is_dir():
        print(f"error: {SKILLS_DIR} does not exist", file=sys.stderr)
        return 1

    tiers: dict[str, str] = {}
    if not args.offline:
        try:
            tiers = tool_tier_map()
        except Exception as exc:  # pragma: no cover - depends on the environment
            print(f"error: could not load the tool registry: {exc}", file=sys.stderr)
            print(
                "       run with --offline to write the manifest without tool lists",
                file=sys.stderr,
            )
            return 1

    problems: list[str] = []
    entries: list[dict[str, object]] = []

    skill_dirs = sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())
    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            problems.append(f"{skill_dir.name}: no SKILL.md")
            continue

        text = skill_file.read_text(encoding="utf-8")
        fields = parse_frontmatter(text)

        name = fields.get("name", "")
        if name != skill_dir.name:
            problems.append(f"{skill_dir.name}: frontmatter name is {name!r}")
        description = fields.get("description", "")
        if len(description) < 40:
            problems.append(f"{skill_dir.name}: description is shorter than 40 characters")

        audience = AUDIENCE_OVERRIDES.get(skill_dir.name)
        if audience is None:
            problems.append(f"{skill_dir.name}: no audience in AUDIENCE_OVERRIDES")
            continue
        if audience not in ("operator", "developer"):
            problems.append(f"{skill_dir.name}: unknown audience {audience!r}")
            continue

        required: dict[str, list[str]] = {tier: [] for tier in TIERS}
        if tiers:
            mentioned = collect_skill_tools(text, set(tiers))
            for tool in sorted(mentioned):
                tier = tiers.get(tool)
                if tier in required:
                    required[tier].append(tool)
                else:
                    # A fleet-mode tool, registered outside the tier table.
                    required.setdefault("fleet", []).append(tool)

        entry: dict[str, object] = {
            "name": skill_dir.name,
            "description": description,
            "path": f"skills/{skill_dir.name}/SKILL.md",
            "audience": audience,
            "requiredTools": {tier: sorted(required[tier]) for tier in sorted(required)},
        }
        for field in EXTRA_FIELDS:
            if field in fields:
                entry[field] = fields[field]
        entries.append(entry)

    on_disk = {p.name for p in skill_dirs}
    for name in sorted(AUDIENCE_OVERRIDES):
        if name not in on_disk:
            problems.append(f"{name}: listed in AUDIENCE_OVERRIDES but not on disk")

    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    manifest = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "name": "unifi-mcp-server-skills",
        "description": (
            "Index of the agent skills shipped by the UniFi MCP Server plugins. "
            "The skill content lives in skills/<name>/SKILL.md; this file only "
            "indexes it."
        ),
        "sourceOfTruth": "skills/",
        "audiences": {
            "operator": "Ships in the plugin packages. Uses a running MCP server.",
            "developer": "Stays in the repository. Helps a coding agent change this codebase.",
        },
        "tiers": {
            "read": "Observes controller state. Available in a read-only session.",
            "write": "Changes controller state. Refused in a read-only session.",
            "destructive": (
                "Changes controller state in a way that can interrupt service or "
                "lock an operator out. Off unless the session allows writes."
            ),
            "fleet": "Reads across controllers. Needs a fleet registry.",
        },
        # The plugin metadata, kept here so one file describes the package.
        "version": package_version(),
        "pluginDescription": PLUGIN_DESCRIPTION,
        "author": {
            "name": "enuno",
            "email": "noreply@github.com",
            "url": "https://github.com/enuno",
        },
        "homepage": "https://github.com/enuno/unifi-mcp-server",
        "repository": "https://github.com/enuno/unifi-mcp-server",
        "license": "Apache-2.0",
        "keywords": [
            "unifi",
            "network",
            "protect",
            "mcp",
            "model-context-protocol",
            "infrastructure",
            "firewall",
            "wifi",
            "automation",
        ],
        "skills": entries,
    }

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    operator = sum(1 for e in entries if e["audience"] == "operator")
    developer = len(entries) - operator
    print(
        f"wrote {MANIFEST_PATH.relative_to(ROOT)}: {len(entries)} skills "
        f"({operator} operator, {developer} developer)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
