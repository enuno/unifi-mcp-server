"""Checks that the skills stay honest about the server's tool surface.

A skill that names a tool the server does not have is worse than no skill:
it sends an agent to a tool that is not there. These tests read the live
registry and compare it with what the skills claim.

They also check the skills' own structure, so a new skill cannot arrive
without the frontmatter, the naming convention and a description.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"
FLEET_DIR = ROOT / "src" / "fleet"

#: The environment the registry is read under. The local mode registers the
#: full tool surface.
_REGISTRY_ENV = {
    "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
    "UNIFI_API_TYPE": "local",
    "UNIFI_LOCAL_HOST": "192.0.2.1",
    "AGNOST_ENABLED": "false",
}

#: A tool named in a skill's tool table: a backticked identifier in the
#: first cell of a markdown table row.
_TOOL_ROW = re.compile(r"^\|\s*`([a-z][a-z0-9_]*)`\s*\|", re.MULTILINE)

#: Identifiers a skill's tables may name that are not tools: the roles, the
#: settings and the token claims the server defines.
_NON_TOOL_NAMES = frozenset(
    {
        "admin",
        "operator",
        "viewer",
        "fleet_admin",
        "local",
        "cloud_v1",
        "cloud_ea",
        "allow_modules",
        "deny_modules",
        "controller_labels",
        "site_manager_enabled",
        "read_only",
        "dry_run",
        "api_type",
        "api_key",
    }
)


def _skill_files() -> list[Path]:
    """Return every SKILL.md under skills/."""
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _skill_names() -> list[str]:
    """Return the skill directory names."""
    return sorted(path.parent.name for path in _skill_files())


def _registered_tools() -> set[str]:
    """Return the tool names the server registers in local mode.

    The registry is read in a subprocess. Importing the server in-process
    would reuse whatever ``src.main`` another test module already cached
    under a different environment, and the tool surface is what this test
    compares against. A subprocess gives a clean import every time and
    leaves the test session's module cache alone.
    """
    script = (
        "import src.main as M\n"
        "print('\\n'.join(sorted("
        "k[len('tool:'):].split('@', 1)[0] "
        "for k in M.mcp._local_provider._components if k.startswith('tool:'))))\n"
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
    return {line for line in result.stdout.splitlines() if line.strip()}


def _registered_tools_by_module() -> dict[str, list[str]]:
    """Return the registered tool names, grouped by defining module.

    The grouping follows the same rule the registry uses: a tool belongs to
    the module that defines its function.
    """
    script = (
        "import src.main as M\n"
        "out = {}\n"
        "for key, component in M.mcp._local_provider._components.items():\n"
        "    if not key.startswith('tool:'):\n"
        "        continue\n"
        "    name = key[5:].split('@', 1)[0]\n"
        "    fn = getattr(component, 'fn', None)\n"
        "    module = getattr(fn, '__module__', '?')\n"
        "    out.setdefault(module, []).append(name)\n"
        "import json\n"
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

    return json.loads(result.stdout)


def _registered_tool_module_count() -> int:
    """Return how many tool modules the server registers in local mode."""
    script = "import src.main as M\n" "print(len(M._TOOL_MODULES))\n"
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
    return int(result.stdout.strip())


def _fleet_tools() -> set[str]:
    """Return the tool names the fleet stack registers.

    The fleet tools are built by closures and only register when
    ``DATABASE_URL`` is set, so they are read from the source.
    """
    names: set[str] = set()
    for module in ("tools.py", "admin_tools.py", "fleet_tools.py"):
        tree = ast.parse((FLEET_DIR / module).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            # A builder returns the tools it defines.
            if node.name.startswith("build_"):
                for inner in ast.walk(node):
                    if (
                        isinstance(inner, ast.FunctionDef | ast.AsyncFunctionDef)
                        and inner is not node
                    ):
                        names.add(inner.name)
            # A registration helper defines one tool.
            if node.name.startswith("register_") or node.name.startswith("build_"):
                names.add(node.name)
    return names


def _known_tool_names() -> set[str]:
    """Return every tool name a skill may legitimately name."""
    return _registered_tools() | _fleet_tools()


@pytest.fixture(scope="module")
def known_tools() -> set[str]:
    """Return the tool names a skill may name."""
    return _known_tool_names()


class TestSkillStructure:
    """Every skill follows the repository's conventions."""

    @pytest.mark.parametrize("skill", _skill_files(), ids=lambda p: p.parent.name)
    def test_the_frontmatter_names_the_folder(self, skill: Path) -> None:
        text = skill.read_text()
        match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)

        assert match, f"{skill} has no YAML frontmatter"
        frontmatter = match.group(1)
        assert re.search(
            rf"^name:\s*{re.escape(skill.parent.name)}\s*$", frontmatter, re.M
        ), f"{skill} frontmatter name does not match its folder"
        assert re.search(r"^description:", frontmatter, re.M)

    @pytest.mark.parametrize("skill", _skill_files(), ids=lambda p: p.parent.name)
    def test_the_description_names_the_trigger(self, skill: Path) -> None:
        text = skill.read_text()
        match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        assert match
        frontmatter = match.group(1)

        description = re.search(
            r"^description:\s*(?:>-\s*)?(.*?)(?=\n[a-z_]+:|\Z)",
            frontmatter,
            re.M | re.DOTALL,
        )
        assert description, f"{skill} has no description"

        body = " ".join(description.group(1).split())
        assert "Use when" in body, f"{skill} description does not say when to use the skill"

    def test_the_new_skills_are_present(self) -> None:
        """The coverage gaps this work closed have a skill each."""
        names = _skill_names()
        for expected in (
            "unifi-discovery",
            "unifi-safe-changes",
            "unifi-fleet-operations",
            "unifi-protect",
            "unifi-docs-sync",
        ):
            assert expected in names, f"{expected} is missing"

    @pytest.mark.parametrize("skill", _skill_files(), ids=lambda p: p.parent.name)
    def test_the_skill_is_not_empty(self, skill: Path) -> None:
        body = skill.read_text().split("---", 2)[-1]
        assert len(body.strip()) > 400, f"{skill} has no useful body"


class TestSkillToolReferences:
    """A skill must not name a tool the server does not have."""

    @pytest.mark.parametrize("skill", _skill_files(), ids=lambda p: p.parent.name)
    def test_the_tools_in_the_tables_exist(self, skill: Path, known_tools: set[str]) -> None:
        """The first cell of a tool table names a tool."""
        named = set(_TOOL_ROW.findall(skill.read_text()))
        unknown = {
            name for name in named if name not in known_tools and name not in _NON_TOOL_NAMES
        }

        assert not unknown, f"{skill} names tools that do not exist: {sorted(unknown)}"


class TestCorrectedSkills:
    """The corrections this work made must stay applied."""

    def test_the_zbf_names_are_the_real_ones(self) -> None:
        text = (SKILLS_DIR / "unifi-security" / "SKILL.md").read_text()

        assert "get_zone_policy_matrix" in text
        for wrong in (
            "get_zbf_matrix",
            "get_zone_policies",
            "get_zone_matrix_policy",
            "update_zbf_policy",
            "delete_zbf_policy",
            "block_application_by_zone",
            "list_blocked_applications",
        ):
            assert wrong not in text, f"unifi-security still names {wrong}"

    def test_the_tool_count_is_current(self) -> None:
        text = (SKILLS_DIR / "unifi-mcp-tool-builder" / "SKILL.md").read_text()

        assert "74-tool" not in text

    def test_the_stated_tool_count_matches_the_registry(self) -> None:
        """A stated tool count has to be the live one.

        A count in prose goes stale the moment a tool is added, and a
        stale count misleads a reader about the size of the surface. Any
        number the skill states next to "MCP tools" is compared with the
        registry.
        """
        text = (SKILLS_DIR / "unifi-mcp-tool-builder" / "SKILL.md").read_text()
        stated = {
            int(match.group(1).replace(",", ""))
            for match in re.finditer(r"([0-9][0-9,]*)[- ]tool", text)
        }
        stated.update(
            int(match.group(1).replace(",", ""))
            for match in re.finditer(r"([0-9][0-9,]*) MCP tools", text)
        )

        assert stated, "the skill states no tool count to check"
        assert stated == {len(_registered_tools())}

    def test_the_stated_module_count_matches_the_registry(self) -> None:
        """A stated module count has to be the live one.

        The tool builder skill and the README both state how many tool
        modules the server registers. Both are compared with the registry.
        """
        registered = _registered_tool_module_count()

        for path in (
            SKILLS_DIR / "unifi-mcp-tool-builder" / "SKILL.md",
            ROOT / "README.md",
        ):
            text = path.read_text()
            stated = {int(match.group(1)) for match in re.finditer(r"([0-9]+) tool modules", text)}
            stated.update(
                int(match.group(1)) for match in re.finditer(r"from ([0-9]+) modules", text)
            )
            if stated:
                assert stated == {registered}, f"{path.name} states {stated}"

    def test_the_protect_module_counts_match_the_registry(self) -> None:
        """The Protect skill's module, function and tool counts are exact."""
        text = (SKILLS_DIR / "unifi-protect-tools" / "SKILL.md").read_text()
        protect = _registered_tools_by_module()
        protect_modules = {module for module in protect if module.startswith("src.tools.protect_")}

        assert f"{len(protect_modules)} modules" in text
        registered = sum(len(protect[module]) for module in protect_modules)
        assert f"{registered} registered tool names" in text

    def test_the_traffic_route_claim_is_gone(self) -> None:
        text = (SKILLS_DIR / "unifi-system" / "SKILL.md").read_text()

        assert "Create traffic route" not in text

    def test_the_security_tools_reference_points_at_a_real_file(self) -> None:
        text = (SKILLS_DIR / "unifi-security-tools" / "SKILL.md").read_text()

        assert "in this folder" not in text
        guide = ROOT / ".claude" / "skills" / "zbf-implementation-guide.md"
        assert guide.is_file()

    def test_the_fleet_skill_names_the_real_fleet_tools(self) -> None:
        text = (SKILLS_DIR / "unifi-fleet-operations" / "SKILL.md").read_text()
        fleet = _fleet_tools()

        for name in ("fleet_health", "fleet_sites", "fleet_inventory", "fleet_fanout"):
            assert name in text
            assert name in fleet, f"{name} is not a real fleet tool"
