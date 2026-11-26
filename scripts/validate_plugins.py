#!/usr/bin/env python3
"""Validate the plugin manifests and the shared skills manifest.

Checks, in order:

1. Every JSON file the plugins read is valid JSON.
2. The version is the same in ``pyproject.toml``, ``server.json``,
   ``.claude-plugin/plugin.json``, ``.claude-plugin/marketplace.json`` and
   ``skills/manifest.json``.
3. Every skill a manifest names exists on disk, and its frontmatter names
   its own folder.
4. No manifest carries a secret.

The secret check runs a regex pass over the manifests and, when the GitHub
secret-scanning tool is available, runs it over the same files. The regex
pass is always on, so the check does not depend on a network service.

Run it in CI and before publishing:

    python scripts/validate_plugins.py

Exit status is 0 when everything passes and 1 when anything fails.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

#: The manifests this script checks.
MANIFESTS = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".mcp.json",
    "skills/manifest.json",
    "server.json",
)

#: The files the version is read from, and the pattern that finds it.
VERSION_SOURCES = (
    ("pyproject.toml", r'^version\s*=\s*"([^"]+)"', re.MULTILINE),
    ("server.json", r'"version"\s*:\s*"([^"]+)"', re.MULTILINE),
    (".claude-plugin/plugin.json", r'"version"\s*:\s*"([^"]+)"', re.MULTILINE),
    (".claude-plugin/marketplace.json", r'"version"\s*:\s*"([^"]+)"', re.MULTILINE),
    ("skills/manifest.json", r'"version"\s*:\s*"([^"]+)"', re.MULTILINE),
    # The MCP server pins the published package, so a version bump that
    # misses it would leave the plugin launching an old release.
    (".mcp.json", r'unifi-mcp-server==([^"\s]+)', re.MULTILINE),
)

#: Patterns that look like a secret in a manifest.
#:
#: A key that names a credential must carry a ``${...}`` placeholder, never a
#: literal value. A value that looks like a key, a token or a password is a
#: finding. The patterns are deliberately broad: a false positive is a line
#: to look at, a false negative is a credential in a published manifest.
SECRET_PATTERNS = (
    # A credential-looking key with a literal value.
    (
        re.compile(
            r'"(?P<key>[A-Za-z0-9_]*(?:api[_-]?key|secret|password|passwd|token|credential)'
            r'[A-Za-z0-9_]*)"\s*:\s*"(?P<value>[^"$][^"]*)"',
            re.IGNORECASE,
        ),
        "credential-like key with a literal value",
    ),
    # A bearer token in a header.
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}"), "bearer token"),
    # A UniFi API key: site-scoped prefix plus a long suffix.
    (
        re.compile(
            r"\b[A-Za-z0-9]{6}-[A-Za-z0-9]{2}-[A-Za-z0-9]{2}-[A-Za-z0-9]{2}-"
            r"[A-Za-z0-9]{2}-[A-Za-z0-9]{12,}\b"
        ),
        "UniFi-shaped API key",
    ),
    # A private key block.
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    # A GitHub token.
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    # An AWS access key id.
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "AWS access key id"),
)

#: The files that must not be committed, checked by name.
FORBIDDEN_NAMES = (".env", ".env.local", ".env.production", "credentials.json")

#: The directories a secret may never be committed in.
SECRET_DIRS = (".claude-plugin", "skills", "docs", "scripts")


class Report:
    """Collects findings so the script reports everything in one run."""

    def __init__(self) -> None:
        """Start with no findings."""
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def error(self, message: str) -> None:
        """Record a finding that fails the run."""
        self.errors.append(message)

    def warn(self, message: str) -> None:
        """Record a finding that does not fail the run."""
        self.warnings.append(message)

    def note(self, message: str) -> None:
        """Record a finding the reader should know about."""
        self.notes.append(message)


def check_json_valid(report: Report) -> dict[str, dict]:
    """Check that every manifest parses, and return the parsed documents."""
    documents: dict[str, dict] = {}
    for relative in MANIFESTS:
        path = ROOT / relative
        if not path.is_file():
            report.error(f"{relative}: missing")
            continue
        try:
            documents[relative] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.error(f"{relative}: invalid JSON: {exc}")
    return documents


def check_versions(report: Report, documents: dict[str, dict]) -> None:
    """Check that every manifest carries the same version."""
    versions: dict[str, str] = {}
    for relative, pattern, flags in VERSION_SOURCES:
        path = ROOT / relative
        if not path.is_file():
            continue
        match = re.search(pattern, path.read_text(encoding="utf-8"), flags)
        if not match:
            report.error(f"{relative}: no version found")
            continue
        versions[relative] = match.group(1)

    if not versions:
        report.error("no version found in any source")
        return

    unique = set(versions.values())
    if len(unique) > 1:
        detail = ", ".join(f"{name}={value}" for name, value in sorted(versions.items()))
        report.error(f"versions differ: {detail}")
        return

    version = next(iter(unique))
    report.note(f"version: {version} (all {len(versions)} sources agree)")

    # The plugin version pins the published package, so a version mismatch
    # with the server would run a different server than the manifest names.
    for relative in (".claude-plugin/plugin.json", "skills/manifest.json"):
        document = documents.get(relative)
        if document and document.get("version") != version:
            report.error(f"{relative}: version {document.get('version')!r} != {version!r}")


def check_skills(report: Report, documents: dict[str, dict]) -> None:
    """Check that every skill a manifest names exists on disk."""
    manifest = documents.get("skills/manifest.json")
    if manifest is None:
        report.error("skills/manifest.json: cannot check skills without it")
        return

    entries = manifest.get("skills")
    if not isinstance(entries, list) or not entries:
        report.error("skills/manifest.json: no skills listed")
        return

    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            report.error(f"skills/manifest.json: entry is not an object: {entry!r}")
            continue

        name = entry.get("name")
        relative = entry.get("path")
        if not name:
            report.error(f"skills/manifest.json: entry without a name: {entry!r}")
            continue
        if name in seen:
            report.error(f"skills/manifest.json: duplicate skill {name!r}")
        seen.add(name)

        audience = entry.get("audience")
        if audience not in ("operator", "developer"):
            report.error(f"skills/manifest.json: {name}: unknown audience {audience!r}")

        if not relative:
            report.error(f"skills/manifest.json: {name}: no path")
            continue

        path = ROOT / relative
        if not path.is_file():
            report.error(f"skills/manifest.json: {name}: {relative} does not exist")
            continue

        text = path.read_text(encoding="utf-8")
        frontmatter = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not frontmatter:
            report.error(f"{relative}: no frontmatter")
            continue
        try:
            parsed = yaml.safe_load(frontmatter.group(1)) or {}
        except yaml.YAMLError as exc:
            report.error(f"{relative}: frontmatter is not valid YAML: {exc}")
            continue
        if not isinstance(parsed, dict):
            report.error(f"{relative}: frontmatter is not a mapping")
            continue
        declared = str(parsed.get("name", "")).strip()
        if declared != name:
            report.error(f"{relative}: frontmatter name {declared!r} != manifest name {name!r}")
        description = str(parsed.get("description", "")).strip()
        if len(description) < 40:
            report.error(f"{relative}: description is shorter than 40 characters")

    operator = sum(1 for e in entries if isinstance(e, dict) and e.get("audience") == "operator")
    developer = len(entries) - operator
    report.note(f"skills: {len(entries)} listed ({operator} operator, {developer} developer)")


def check_no_secrets(report: Report, documents: dict[str, dict]) -> None:
    """Check that no manifest carries a secret."""
    for relative in documents:
        raw = (ROOT / relative).read_text(encoding="utf-8")
        for pattern, description in SECRET_PATTERNS:
            for match in pattern.finditer(raw):
                # A placeholder is not a secret.
                if "${" in match.group(0):
                    continue
                # Report where the secret is, never what it is. Printing the
                # value would copy the credential into CI logs and terminal
                # scrollback, which is what this check exists to prevent.
                line = raw.count("\n", 0, match.start()) + 1
                report.error(
                    f"{relative}:{line}: {description} "
                    f"({len(match.group(0))} characters, value withheld)"
                )

    # The MCP config must not carry a literal credential.
    mcp = documents.get(".mcp.json")
    if mcp:
        for server_name, server in (mcp.get("mcpServers") or {}).items():
            env = server.get("env") or {}
            for key, value in env.items():
                if not isinstance(value, str):
                    report.error(f".mcp.json: {server_name}: {key} is not a string")
                    continue
                if "${" in value:
                    continue
                if re.search(r"(?i)(key|secret|token|password|credential)", key):
                    report.error(
                        f".mcp.json: {server_name}: {key} has a literal value; "
                        "use a ${VAR} placeholder"
                    )

    # A file whose name says it holds credentials must not be tracked.
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.splitlines()
    for tracked_file in tracked:
        name = Path(tracked_file).name
        if name in FORBIDDEN_NAMES:
            report.error(f"{tracked_file}: a credentials file is tracked")
        parts = Path(tracked_file).parts
        if any(part in SECRET_DIRS for part in parts) and name.endswith(".env"):
            report.error(f"{tracked_file}: an environment file is tracked")


def run_secret_scanner(report: Report, documents: dict[str, dict]) -> None:
    """Run the GitHub secret-scanning tool over the manifests, when available.

    The tool is ``gitleaks``. It is not a dependency of this repository, so
    the check is skipped when it is not installed, and the regex pass above
    remains the guarantee.
    """
    binary = shutil.which("gitleaks")
    if not binary:
        report.note("gitleaks not installed; the regex secret pass ran instead")
        return

    with tempfile.TemporaryDirectory() as workdir:
        # The report goes in its own directory. gitleaks scans the directory
        # it is given, so a report inside that directory can be picked up by
        # the scan itself.
        scan_dir = Path(workdir) / "manifests"
        report_path = Path(workdir) / "gitleaks-report.json"
        scan_dir.mkdir(parents=True, exist_ok=True)

        for relative in documents:
            target = scan_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8")

        # gitleaks prints each finding only in verbose mode, and its exit
        # code says whether it found any. Ask for a JSON report and read the
        # exit status, rather than grepping stdout for lines that may not be
        # there at all.
        result = subprocess.run(
            [
                binary,
                "detect",
                "--no-git",
                "--source",
                str(scan_dir),
                "--redact",
                "--report-format",
                "json",
                "--report-path",
                str(report_path),
                "--exit-code",
                "1",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        findings: list[dict] = []
        if report_path.is_file():
            try:
                findings = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                findings = []

        if result.returncode != 0 or findings:
            for finding in findings:
                # Report the rule and the location, never the secret.
                rule = finding.get("RuleID", finding.get("Rule", "unknown"))
                location = finding.get("File", "unknown")
                line = finding.get("StartLine", "?")
                report.error(f"gitleaks: {rule} at {location}:{line} (value withheld)")
            if not findings:
                report.error(
                    f"gitleaks: the scan failed with exit code {result.returncode}: "
                    f"{result.stderr.strip()[:200]}"
                )
        else:
            report.note("gitleaks: no findings in the manifests")


def check_built_package(report: Report) -> None:
    """Check that the built package matches the repository's manifests.

    The build script reads the repository's manifests rather than
    synthesising its own, so the package and the repository cannot describe
    the plugin differently. This proves it for the package that was built.
    """
    package = ROOT / "dist"
    claude_manifest = package / "claude" / "unifi-mcp-server" / ".claude-plugin" / "plugin.json"
    if not claude_manifest.is_file():
        report.note("no built Claude package found; skipped the package comparison")
        return

    repository = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    built = json.loads(claude_manifest.read_text(encoding="utf-8"))

    for field in ("name", "description", "author", "homepage", "repository", "license", "keywords"):
        if repository.get(field) != built.get(field):
            report.error(
                f"the built package differs from the repository manifest: "
                f"{field} is {built.get(field)!r} in the package and "
                f"{repository.get(field)!r} in the repository"
            )

    repository_mcp = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    built_mcp_path = package / "claude" / "unifi-mcp-server" / ".mcp.json"
    if built_mcp_path.is_file():
        built_mcp = json.loads(built_mcp_path.read_text(encoding="utf-8"))
        if repository_mcp != built_mcp:
            report.error("the built package's .mcp.json differs from the repository's .mcp.json")


def check_package_skills(report: Report, documents: dict[str, dict]) -> None:
    """Check that the built packages ship only the operator skills.

    The developer skills help a coding agent change this codebase and are of
    no use to an operator, so they must not ship in a package.
    """
    manifest = documents.get("skills/manifest.json")
    if manifest is None:
        return

    developer = {
        entry["name"]
        for entry in manifest.get("skills", [])
        if isinstance(entry, dict) and entry.get("audience") == "developer"
    }
    operator = {
        entry["name"]
        for entry in manifest.get("skills", [])
        if isinstance(entry, dict) and entry.get("audience") == "operator"
    }
    if not developer:
        report.error("skills/manifest.json: no skill has the developer audience")
        return

    for package in ("claude", "chatgpt"):
        skills_dir = ROOT / "dist" / package / "unifi-mcp-server" / "skills"
        if not skills_dir.is_dir():
            report.note(f"no built {package} package found; skipped its skill check")
            continue

        shipped = {path.parent.name for path in skills_dir.glob("*/SKILL.md")}
        leaked = shipped & developer
        if leaked:
            report.error(
                f"the built {package} package ships developer skills: "
                f"{', '.join(sorted(leaked))}"
            )
        missing = operator - shipped
        if missing:
            report.error(
                f"the built {package} package is missing operator skills: "
                f"{', '.join(sorted(missing))}"
            )
        if not leaked and not missing:
            report.note(
                f"the built {package} package ships {len(shipped)} operator skills "
                "and no developer skills"
            )


def main() -> int:
    """Run every check and report what was found."""
    report = Report()

    documents = check_json_valid(report)
    if documents:
        check_versions(report, documents)
        check_skills(report, documents)
        check_no_secrets(report, documents)
        run_secret_scanner(report, documents)
        check_built_package(report)
        check_package_skills(report, documents)

    for note in report.notes:
        print(f"note: {note}")
    for warning in report.warnings:
        print(f"warning: {warning}")
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)

    if report.errors:
        print(f"\n{len(report.errors)} problem(s) found", file=sys.stderr)
        return 1

    print("\nAll plugin manifests are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
