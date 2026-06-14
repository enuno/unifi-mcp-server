"""Unit tests for tool registry behavior."""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

if importlib.util.find_spec("fastmcp") is None:
    fastmcp_stub = ModuleType("fastmcp")

    class FastMCP:  # type: ignore[too-many-ancestors]
        pass

    setattr(fastmcp_stub, "FastMCP", FastMCP)
    sys.modules["fastmcp"] = fastmcp_stub

from src.tool_registry import register_module_tools
from src.tools import dpi_tools, reference_data


class FakeMCP:
    """Minimal FastMCP stand-in for registry tests."""

    def __init__(self) -> None:
        self.registered: list[str] = []

    def tool(self) -> Callable[[Any], Any]:
        def decorator(fn: Any) -> Any:
            self.registered.append(fn.__name__)
            return fn

        return decorator


@pytest.fixture
def settings() -> MagicMock:
    """Create mock settings for registry tests."""
    mock = MagicMock()
    mock.log_level = "INFO"
    return mock


def test_register_module_tools_skips_duplicate_names(settings: MagicMock) -> None:
    """Duplicate public tool names should only be registered once per MCP instance."""
    mcp: Any = FakeMCP()

    first = register_module_tools(mcp, reference_data, settings)
    second = register_module_tools(mcp, dpi_tools, settings)

    assert "list_countries" in first
    assert "list_radius_profiles" in first
    assert "list_countries" not in second
    assert "list_radius_profiles" not in second

    assert mcp.registered.count("list_countries") == 1
    assert mcp.registered.count("list_radius_profiles") == 1
    assert mcp.registered.count("list_dpi_categories") == 1
    assert mcp.registered.count("list_dpi_applications") == 1
    assert len(mcp.registered) == len(set(mcp.registered))


def test_register_module_tools_tracks_names_on_mcp_instance(settings: MagicMock) -> None:
    """The registry should persist per FastMCP instance."""
    mcp: Any = FakeMCP()

    register_module_tools(mcp, reference_data, settings)

    assert hasattr(mcp, "_registered_tool_names")
    assert "list_countries" in mcp._registered_tool_names
    assert "list_radius_profiles" in mcp._registered_tool_names
