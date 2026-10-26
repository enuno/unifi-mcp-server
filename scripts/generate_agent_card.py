#!/usr/bin/env python
"""Regenerate the repository-root ``agent-card.json`` artifact.

The agent card is built from the live tool registry, so the served card
changes when the tool surface or the configuration changes. This script
pins the *default* local configuration and writes the resulting card to the
repository root, where ``tests/unit/a2a/test_agent_card.py`` checks it.

Run it after changing the card, the tool surface or the package version:

    python scripts/generate_agent_card.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

#: The configuration the artifact represents. It must match the one the
#: test uses, so both read the same settings. The test imports this
#: mapping, so the two cannot drift apart.
ENVIRONMENT = {
    "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
    "UNIFI_API_TYPE": "local",
    "UNIFI_LOCAL_HOST": "192.0.2.1",
    "AGNOST_ENABLED": "false",
}

#: Where the artifact is written.
OUTPUT = Path(__file__).resolve().parents[1] / "agent-card.json"


def main() -> int:
    """Write the reference agent card and report what changed.

    Returns:
        The process exit code.
    """
    os.environ.update(ENVIRONMENT)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    import src.main as main
    from src.a2a.agent_card import build_agent_card
    from src.config import Settings

    card = build_agent_card(main.mcp, Settings())
    # The skills are sorted by name so the artifact does not depend on the
    # order the tools happened to register in.
    card["skills"] = sorted(card["skills"], key=lambda skill: skill["name"])
    rendered = json.dumps(card, indent=2, sort_keys=True) + "\n"

    previous = OUTPUT.read_text() if OUTPUT.exists() else ""
    OUTPUT.write_text(rendered)

    if previous == rendered:
        print(f"{OUTPUT.name} is unchanged")
    else:
        print(f"{OUTPUT.name} regenerated ({card['metadata']['toolCount']} tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
