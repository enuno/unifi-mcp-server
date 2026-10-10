"""Tool risk tiers (docs/FLEET_SCALING_PLAN.md §3.6).

To accept an intended tier change, regenerate the snapshot with::

    UPDATE_TOOL_TIERS=1 pytest tests/unit/fleet/test_tiers.py
"""

import importlib
import inspect
import json
import os
import pkgutil
from pathlib import Path
from typing import Any

import pytest

import src.tools
from src.a2a.auth import AuthManager
from src.a2a.route_policy import SafetyController
from src.tool_registry import (
    DESTRUCTIVE_TOOLS,
    TOOL_TIERS,
    is_mutating_tool,
    register_module_tools,
    tool_tier,
)

SNAPSHOT = Path(__file__).with_name("tool_tiers.json")

#: Words that suggest a tool deletes, resets, cuts service or locks out.
RISKY_WORDS = (
    "block",
    "delete",
    "disable",
    "factory",
    "forget",
    "migrate",
    "purge",
    "reboot",
    "remove",
    "reset",
    "restart",
    "restore",
    "revoke",
    "suspend",
    "upgrade",
    "wipe",
)

#: Mutating tools with a risky word in their name that are deliberately only
#: ``write``: each entry needs a reason.
RISKY_NAME_EXEMPTIONS = {
    "unblock_client": "restores access rather than removing it",
}


def _all_tools() -> dict[str, Any]:
    tools: dict[str, Any] = {}
    for info in pkgutil.iter_modules(src.tools.__path__):
        module = importlib.import_module(f"src.tools.{info.name}")
        for name, fn in inspect.getmembers(module, inspect.iscoroutinefunction):
            if not name.startswith("_") and fn.__module__ == module.__name__:
                tools.setdefault(name, fn)
    return tools


def test_tier_map_matches_snapshot():
    tiers = {name: tool_tier(fn) for name, fn in sorted(_all_tools().items())}

    if os.environ.get("UPDATE_TOOL_TIERS"):
        SNAPSHOT.write_text(json.dumps(tiers, indent=2) + "\n")

    expected = json.loads(SNAPSHOT.read_text())
    changed = {
        name: (expected.get(name), tier)
        for name, tier in tiers.items()
        if expected.get(name) != tier
    }
    removed = sorted(set(expected) - set(tiers))
    assert not changed and not removed, (
        f"Tool tiers changed {changed} / removed {removed}. If intended, regenerate with "
        "UPDATE_TOOL_TIERS=1 pytest tests/unit/fleet/test_tiers.py"
    )


def test_destructive_tools_are_real_mutating_tools():
    tools = _all_tools()

    unknown = sorted(DESTRUCTIVE_TOOLS - set(tools))
    not_mutating = sorted(
        n for n in DESTRUCTIVE_TOOLS & set(tools) if not is_mutating_tool(tools[n])
    )

    assert unknown == [], "DESTRUCTIVE_TOOLS lists tools that do not exist"
    assert not_mutating == [], "DESTRUCTIVE_TOOLS lists read-only tools"


def test_risky_names_are_destructive_or_exempt():
    suspicious = sorted(
        name
        for name, fn in _all_tools().items()
        if is_mutating_tool(fn)
        and any(word in name for word in RISKY_WORDS)
        and tool_tier(fn) != "destructive"
        and name not in RISKY_NAME_EXEMPTIONS
    )

    assert suspicious == [], (
        "Mutating tools whose names suggest deletion, reset or lock-out are not "
        "destructive: add them to DESTRUCTIVE_TOOLS or to RISKY_NAME_EXEMPTIONS with a reason"
    )


@pytest.mark.parametrize(
    ("name", "tier"),
    [
        ("list_wlans", "read"),
        ("create_wlan", "write"),
        ("delete_wlan", "destructive"),
        ("restore_backup", "destructive"),
        ("upgrade_device", "destructive"),
        ("restart_device", "destructive"),
        ("unblock_client", "write"),
    ],
)
def test_known_tiers(name: str, tier: str):
    assert tool_tier(_all_tools()[name]) == tier


def test_registration_records_tiers():
    from src.tools import backups

    class _FakeMCP:
        def tool(self):
            return lambda fn: fn

    settings = type("S", (), {"read_only": False, "dry_run": False})()
    register_module_tools(_FakeMCP(), backups, settings)

    assert TOOL_TIERS["restore_backup"] == "destructive"


class TestA2AUsesTiers:
    """A2A delegation used to guess from names: restore_backup counted as a read."""

    @pytest.fixture(autouse=True)
    def _tiers(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setitem(TOOL_TIERS, "restore_backup", "destructive")
        monkeypatch.setitem(TOOL_TIERS, "reconnect_client", "write")
        monkeypatch.setitem(TOOL_TIERS, "list_wlans", "read")

    def test_auth_manager_requires_registry_tier(self):
        assert AuthManager._required_permission("restore_backup") == "destructive"
        assert AuthManager._required_permission("reconnect_client") == "write"
        assert AuthManager._required_permission("list_wlans") == "read"

    def test_safety_controller_requires_registry_tier(self):
        controller = SafetyController()

        assert controller._classify_tool("restore_backup", {})[0] == "destructive"
        assert controller._classify_tool("reconnect_client", {})[0] == "write"
        assert controller._classify_tool("list_wlans", {})[0] == "read"

    def test_unknown_names_keep_name_heuristics(self):
        assert AuthManager._required_permission("delete_imaginary") == "destructive"
        assert SafetyController()._classify_tool("create_imaginary", {})[0] == "write"
