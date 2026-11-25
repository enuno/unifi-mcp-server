#!/usr/bin/env python3
"""Build the distributable plugin packages from the skills in this repository.

The repository's ``skills/`` directory is the single source of truth for skill
content. This script assembles two packages from it without editing or
duplicating a single skill file in the repository:

``claude``
    A Claude Code plugin. Contains ``.claude-plugin/plugin.json`` and
    ``.mcp.json``, and only the operator skills, because the developer skills
    help a coding agent change this codebase rather than help an operator run
    a network.

``chatgpt``
    A ChatGPT/Codex plugin. Contains a manifest and the same operator skills,
    and no MCP configuration, because a skills-only upload carries no MCP
    server.

Both packages are written to ``dist/`` and are build artefacts. The
``dist/`` directory is not tracked by git.

Run it after changing a skill or a manifest:

    python scripts/build_plugin_packages.py

It refuses to build when a skill named in ``skills/manifest.json`` is missing
from disk, so a package can never be produced from an incomplete skill set.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
MANIFEST_PATH = SKILLS_DIR / "manifest.json"
DIST_DIR = ROOT / "dist"

#: The audience that ships in a distributable package.
SHIPPED_AUDIENCE = "operator"

#: Files copied into every package, relative to the repository root.
PACKAGE_FILES = (
    "LICENSE",
    "README.md",
)

#: The plugin icon, copied into the package under this path.
ICON_SOURCE = ROOT / ".claude-plugin" / "icon.png"
ICON_TARGET = Path(".claude-plugin/icon.png")


def load_manifest() -> dict[str, Any]:
    """Return the parsed skills manifest."""
    if not MANIFEST_PATH.is_file():
        raise SystemExit(
            f"error: {MANIFEST_PATH} does not exist; run "
            "scripts/generate_skills_manifest.py first"
        )
    parsed: dict[str, Any] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return parsed


def shipped_skills(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the manifest entries whose audience ships."""
    entries = [entry for entry in manifest["skills"] if entry.get("audience") == SHIPPED_AUDIENCE]
    if not entries:
        raise SystemExit(f"error: no skill has audience {SHIPPED_AUDIENCE!r}")
    return sorted(entries, key=lambda entry: entry["name"])


def copy_skill(manifest_entry: dict[str, Any], target_root: Path) -> None:
    """Copy one skill into a package.

    The content is copied, not moved and not symlinked, so the package is
    self-contained and survives being zipped and uploaded.
    """
    source = ROOT / manifest_entry["path"]
    if not source.is_file():
        raise SystemExit(f"error: skill file missing: {source}")

    target = target_root / "skills" / manifest_entry["name"] / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_icon(package: Path) -> None:
    """Copy the plugin icon into a package."""
    if not ICON_SOURCE.is_file():
        raise SystemExit(f"error: plugin icon missing: {ICON_SOURCE}")
    target = package / ICON_TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ICON_SOURCE, target)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON file with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def plugin_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the manifest fields every package carries."""
    return {
        "name": "unifi-mcp-server",
        "version": manifest["version"],
        "description": manifest["pluginDescription"],
        "author": manifest["author"],
        "homepage": manifest["homepage"],
        "repository": manifest["repository"],
        "license": manifest["license"],
        "keywords": manifest["keywords"],
    }


def mcp_config(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the MCP server configuration.

    Env values are placeholders only. The API key is never written into a
    package; Claude Code expands ``${UNIFI_API_KEY}`` from the user's own
    environment, and warns when the variable is unset.
    """
    return {
        "mcpServers": {
            "unifi": {
                "command": "uvx",
                "args": [f"unifi-mcp-server=={manifest['version']}"],
                "env": {
                    "UNIFI_API_KEY": "${UNIFI_API_KEY}",
                    "UNIFI_API_TYPE": "${UNIFI_API_TYPE:-cloud-ea}",
                    "UNIFI_DEFAULT_SITE": "${UNIFI_DEFAULT_SITE:-default}",
                    "UNIFI_LOCAL_HOST": "${UNIFI_LOCAL_HOST:-}",
                    "UNIFI_LOCAL_PORT": "${UNIFI_LOCAL_PORT:-443}",
                    "UNIFI_LOCAL_VERIFY_SSL": "${UNIFI_LOCAL_VERIFY_SSL:-true}",
                    "UNIFI_READ_ONLY": "${UNIFI_READ_ONLY:-true}",
                    "UNIFI_PROFILE": "${UNIFI_PROFILE:-minimal}",
                },
            }
        }
    }


def build_claude(manifest: dict[str, Any], out_dir: Path) -> Path:
    """Build the Claude Code plugin package."""
    package = out_dir / "claude" / "unifi-mcp-server"
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)

    for relative in PACKAGE_FILES:
        source = ROOT / relative
        if source.is_file():
            shutil.copy2(source, package / relative)

    copy_icon(package)

    plugin_json = plugin_metadata(manifest)
    plugin_json["icon"] = "./.claude-plugin/icon.png"
    # The package ships a skills/ directory holding only the operator skills,
    # so the default scan and the declared path agree.
    plugin_json["skills"] = "./skills"
    write_json(package / ".claude-plugin" / "plugin.json", plugin_json)

    write_json(package / ".mcp.json", mcp_config(manifest))

    for entry in shipped_skills(manifest):
        copy_skill(entry, package)

    return package


def build_chatgpt(manifest: dict[str, Any], out_dir: Path) -> Path:
    """Build the ChatGPT/Codex skills-only plugin package.

    The package carries no MCP server. A user configures the MCP server
    separately, because a skills-only upload cannot carry an MCP server and
    this project has no hosted endpoint to point one at.
    """
    package = out_dir / "chatgpt" / "unifi-mcp-server"
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)

    for relative in PACKAGE_FILES:
        source = ROOT / relative
        if source.is_file():
            shutil.copy2(source, package / relative)

    copy_icon(package)

    plugin_json = plugin_metadata(manifest)
    plugin_json["$schema"] = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    write_json(package / "plugin.json", plugin_json)

    # The Claude manifest, so the same archive qualifies for a direct Claude
    # upload: a nonempty description and at least one skill at
    # skills/<skill-name>/SKILL.md.
    write_json(package / ".claude-plugin" / "plugin.json", plugin_json)

    for entry in shipped_skills(manifest):
        copy_skill(entry, package)

    return package


def zip_package(package: Path) -> Path:
    """Zip a package directory into an archive next to it."""
    archive = package.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(package.parent))
    return archive


def main() -> int:
    """Build both packages and print what was written."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(DIST_DIR),
        help="Directory to write the packages into. Defaults to dist/.",
    )
    args = parser.parse_args()

    manifest = load_manifest()
    out_dir = Path(args.out).resolve()

    claude = build_claude(manifest, out_dir)
    chatgpt = build_chatgpt(manifest, out_dir)

    claude_zip = zip_package(claude)
    chatgpt_zip = zip_package(chatgpt)

    skills = shipped_skills(manifest)
    print(f"claude package: {claude}")
    print(f"claude archive: {claude_zip}")
    print(f"chatgpt package: {chatgpt}")
    print(f"chatgpt archive: {chatgpt_zip}")
    print(f"skills shipped: {len(skills)}")
    for entry in skills:
        print(f"  {entry['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
