"""Tests that the FastMCP server publishes usage instructions to MCP clients.

The instructions field is shown to the client at initialize time and must carry
the cross-cutting rules that individual tool docstrings cannot express.
"""

import importlib
import sys
from types import ModuleType
from unittest.mock import patch

_BASE_ENV = {
    "UNIFI_NETWORK_API_KEY": "test-key",
    "UNIFI_API_TYPE": "cloud-ea",
    "AGNOST_ENABLED": "false",
}


def _reload_main() -> ModuleType:
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]
    with patch.dict("os.environ", _BASE_ENV, clear=False):
        return importlib.import_module("src.main")


class TestServerInstructions:
    def test_instructions_are_set(self) -> None:
        main = _reload_main()
        assert main.mcp.instructions, "FastMCP server must set instructions"

    def test_instructions_cover_cross_cutting_rules(self) -> None:
        text = _reload_main().mcp.instructions
        assert text is not None
        for phrase in (
            "confirm=True",
            "dry-run",
            "UUID",
            "ObjectId",
            "RESTART",
            "locate_device",
            "upgrade_device",
            "list_all_sites",
            "unpaginated",
            "search_clients",
        ):
            assert phrase in text, f"instructions missing: {phrase}"
