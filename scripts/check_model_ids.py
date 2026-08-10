#!/usr/bin/env python3
"""Check that Claude model ids referenced in this repo are still served.

Model ids silently rot: a pinned dated snapshot keeps working until the
retirement date, then every workflow using it starts failing at once. This
script turns that into a check you can run.

Usage:
    python scripts/check_model_ids.py            # needs ANTHROPIC_API_KEY
    python scripts/check_model_ids.py --offline  # only report what is referenced

Exit codes:
    0  every referenced id is currently served (or --offline)
    1  at least one referenced id is no longer served
    2  could not reach the API
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.anthropic.com/v1/models?limit=100"
API_VERSION = "2023-06-01"

# Matches ids we actually pass to the API, e.g. claude-sonnet-4-6,
# claude-opus-4-8, claude-3-7-sonnet-20250219. Deliberately excludes
# product names such as claude-code-action or claude-desktop.
MODEL_RE = re.compile(
    r"claude-(?:"
    r"opus|sonnet|haiku"                 # claude-<family>-<version>
    r")-[0-9][a-z0-9-]*"
    r"|claude-[0-9][a-z0-9-]*-(?:opus|sonnet|haiku)[a-z0-9-]*"  # legacy claude-3-7-sonnet-...
)

SEARCH_SUFFIXES = {".py", ".yml", ".yaml", ".md", ".json", ".ts", ".js", ".toml"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}


def find_referenced_ids(root: Path) -> dict[str, list[str]]:
    """Return {model_id: [relative paths where it appears]}."""
    found: dict[str, list[str]] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in SEARCH_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name == Path(__file__).name:
            continue  # don't flag our own regex examples
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in MODEL_RE.findall(text):
            rel = str(path.relative_to(root))
            found.setdefault(match, [])
            if rel not in found[match]:
                found[match].append(rel)
    return found


def fetch_served_ids(credential: str, header: str) -> set[str]:
    """Query the models endpoint. `header` is 'x-api-key' or 'authorization'."""
    if header == "authorization":
        headers = {
            "authorization": f"Bearer {credential}",
            "anthropic-version": API_VERSION,
        }
    else:
        headers = {"x-api-key": credential, "anthropic-version": API_VERSION}
    req = urllib.request.Request(API_URL, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    return {entry["id"] for entry in payload.get("data", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="list referenced ids without calling the API",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root to scan (default: parent of scripts/)",
    )
    args = parser.parse_args()

    referenced = find_referenced_ids(args.root)
    if not referenced:
        print("No Claude model ids referenced in this repository.")
        return 0

    print(f"Referenced model ids ({len(referenced)}):")
    for model_id in sorted(referenced):
        print(f"  {model_id}")
        for location in referenced[model_id]:
            print(f"      {location}")

    if args.offline:
        return 0

    # ANTHROPIC_API_KEY is the documented variable. ANTHROPIC_AUTH_TOKEN is
    # what Claude Code writes for OAuth logins, and it needs a Bearer header
    # instead of x-api-key — accept either so the check works in both setups.
    credential = os.environ.get("ANTHROPIC_API_KEY")
    header = "x-api-key"
    if not credential:
        credential = os.environ.get("ANTHROPIC_AUTH_TOKEN")
        header = "authorization"
    if not credential:
        print(
            "\nNeither ANTHROPIC_API_KEY nor ANTHROPIC_AUTH_TOKEN is set. "
            "Re-run with --offline to skip the live check.",
            file=sys.stderr,
        )
        return 2

    try:
        served = fetch_served_ids(credential, header)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        print(f"\nCould not reach the Anthropic API: {exc}", file=sys.stderr)
        return 2

    print(f"\nAPI currently serves {len(served)} models.")

    stale = sorted(m for m in referenced if m not in served)
    if stale:
        print("\nRETIRED — these ids are referenced but no longer served:")
        for model_id in stale:
            print(f"  {model_id}")
            for location in referenced[model_id]:
                print(f"      {location}")
        return 1

    print("OK — every referenced model id is currently served.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
