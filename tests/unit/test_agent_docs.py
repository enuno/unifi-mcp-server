"""Checks that the agent instruction files only cite things that exist.

CLAUDE.md, AGENTS.md and the tool-set skills tell coding agents which
files, helpers, settings and tools to use. A renamed helper or a moved
file makes them send agents to code that is not there, so every repo
path, line number, link and identifier they cite is checked here.
"""

import re
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

DOCS = [
    "CLAUDE.md",
    "AGENTS.md",
    ".claude/skills/zbf-implementation-guide.md",
    ".claude/skills/unifi-protect-tools/SKILL.md",
    ".claude/skills/unifi-network-config-tools/SKILL.md",
    ".claude/skills/unifi-security-tools/SKILL.md",
    ".claude/skills/unifi-cloud-fleet-tools/SKILL.md",
]

SKILLS = [doc for doc in DOCS if doc.endswith("/SKILL.md")]

# Files whose text counts as "the code" when looking up a cited name.
CORPUS_GLOBS = [
    "src/**/*.py",
    "tests/**/*.py",
    "scripts/**/*.py",
    "Makefile",
    "pyproject.toml",
    ".env.example",
    ".pre-commit-config.yaml",
    ".github/workflows/*.yml",
]

FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
REPO_PATH = re.compile(
    r"^((?:src|tests|docs|scripts|\.claude|\.github)/[\w./-]+?)(?::(\d+)(?:-(\d+))?)?(?:,\d+)*$"
)
SNAKE_NAME = re.compile(r"^_{0,2}[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?:\(\))?$")
UPPER_NAME = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")


@cache
def _corpus() -> str:
    parts = []
    for pattern in CORPUS_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if "__pycache__" not in path.parts:
                parts.append(path.read_text(errors="replace"))
    return "\n".join(parts)


def _inline_code(text: str) -> list[str]:
    return INLINE_CODE.findall(FENCE.sub("", text))


def _missing_paths(text: str) -> list[str]:
    problems = []
    for token in _inline_code(text):
        match = REPO_PATH.match(token)
        if not match or any(ch in match.group(1) for ch in "*{}<>"):
            continue
        path = ROOT / match.group(1)
        if not path.exists():
            problems.append(f"missing path: {token}")
            continue
        if match.group(2) and path.is_file():
            last = int(match.group(3) or match.group(2))
            length = len(path.read_text(errors="replace").splitlines())
            if last > length:
                problems.append(f"line out of range: {token} (file has {length} lines)")
    return problems


def _broken_links(doc: Path, text: str) -> list[str]:
    problems = []
    for target in LINK.findall(FENCE.sub("", text)):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if not (doc.parent / target.split("#", 1)[0]).exists():
            problems.append(f"broken link: {target}")
    return problems


def _unknown_names(text: str) -> list[str]:
    corpus = _corpus()
    problems = []
    for token in sorted(set(_inline_code(text))):
        name = token.removesuffix("()")
        if not (SNAKE_NAME.match(token) or UPPER_NAME.match(token)):
            continue
        if not re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", corpus):
            problems.append(f"name not found in code: {token}")
    return problems


@pytest.mark.parametrize("doc_name", DOCS)
def test_doc_cites_only_existing_paths_links_and_names(doc_name: str) -> None:
    doc = ROOT / doc_name
    assert doc.is_file(), f"{doc_name} does not exist"
    text = doc.read_text()

    problems = _missing_paths(text) + _broken_links(doc, text) + _unknown_names(text)

    assert not problems, f"{doc_name}:\n" + "\n".join(problems)


@pytest.mark.parametrize("skill_name", SKILLS)
def test_skill_frontmatter_names_its_folder(skill_name: str) -> None:
    skill = ROOT / skill_name
    assert skill.is_file(), f"{skill_name} does not exist"
    text = skill.read_text()

    frontmatter = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert frontmatter, f"{skill_name} has no frontmatter"
    fields = dict(line.split(":", 1) for line in frontmatter.group(1).splitlines() if ":" in line)
    assert fields.get("name", "").strip() == skill.parent.name
    assert len(fields.get("description", "").strip()) >= 40
