"""Unit tests for tool registry behavior."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest

if importlib.util.find_spec("fastmcp") is None:
    fastmcp_stub = ModuleType("fastmcp")

    class FastMCP:  # type: ignore[too-many-ancestors]
        pass

    fastmcp_stub.FastMCP = FastMCP
    sys.modules["fastmcp"] = fastmcp_stub

from src.tool_registry import MUTATING_TOOLS_WITHOUT_GATE, is_mutating_tool, register_module_tools
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
    # Explicit: a bare MagicMock attribute is truthy, which would silently
    # enable read-only, dry-run, and metrics mode for every test here.
    mock.read_only = False
    mock.dry_run = False
    mock.metrics_enabled = False
    return mock


@pytest.fixture
def read_only_settings() -> MagicMock:
    """Mock settings with read-only mode enabled.

    Deliberately a separate instance from the ``settings`` fixture so a test can
    request both and compare them.
    """
    mock = MagicMock()
    mock.log_level = "INFO"
    mock.read_only = True
    mock.dry_run = False
    mock.metrics_enabled = False
    return mock


@pytest.fixture
def dry_run_settings() -> MagicMock:
    """Mock settings with global dry-run mode enabled."""
    mock = MagicMock()
    mock.log_level = "INFO"
    mock.read_only = False
    mock.dry_run = True
    mock.metrics_enabled = False
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


# ---------------------------------------------------------------------------
# Read-only mode
# ---------------------------------------------------------------------------


async def _read_tool(site_id: str, settings: Any = None) -> dict[str, Any]:
    """Stand-in for a non-mutating tool."""
    return {}


async def _confirm_tool(site_id: str, confirm: bool | str = False, settings: Any = None) -> dict:
    """Stand-in for a tool gated by ``confirm``."""
    return {}


async def _dry_run_tool(site_id: str, dry_run: bool | str = False, settings: Any = None) -> dict:
    """Stand-in for a tool gated by ``dry_run``."""
    return {}


def _iter_tool_modules() -> list[ModuleType]:
    """Import and return every public module under ``src.tools``."""
    import importlib
    import pkgutil

    import src.tools as tools_pkg

    modules = []
    for info in pkgutil.iter_modules(tools_pkg.__path__):
        if info.name.startswith("_"):
            continue
        modules.append(importlib.import_module(f"src.tools.{info.name}"))
    return modules


def test_is_mutating_tool_detects_gate_parameters() -> None:
    """A ``confirm`` or ``dry_run`` parameter marks a tool as mutating."""
    assert is_mutating_tool(_confirm_tool) is True
    assert is_mutating_tool(_dry_run_tool) is True


def test_is_mutating_tool_allows_read_tools() -> None:
    """A tool without gate parameters is treated as read-only."""
    assert is_mutating_tool(_read_tool) is False


def test_is_mutating_tool_detects_ungated_mutators() -> None:
    """Mutating tools without gate parameters are caught by the explicit list."""
    assert MUTATING_TOOLS_WITHOUT_GATE, "the explicit list must not be empty"

    for name in MUTATING_TOOLS_WITHOUT_GATE:
        fn = MagicMock()
        fn.__name__ = name
        assert is_mutating_tool(fn) is True, name


def test_read_only_mode_skips_mutating_tools(read_only_settings: MagicMock) -> None:
    """Read-only mode must not register tools that can change state."""
    module = ModuleType("fake_tools")
    for fn in (_read_tool, _confirm_tool, _dry_run_tool):
        fn.__module__ = "fake_tools"
        setattr(module, fn.__name__.lstrip("_"), fn)

    mcp: Any = FakeMCP()
    registered = register_module_tools(mcp, module, read_only_settings)

    assert registered == ["read_tool"]
    assert "confirm_tool" not in mcp.registered
    assert "dry_run_tool" not in mcp.registered


def test_default_mode_still_registers_mutating_tools(settings: MagicMock) -> None:
    """Read-only mode is opt-in: the default must not change behaviour."""
    module = ModuleType("fake_tools_default")
    for fn in (_read_tool, _confirm_tool, _dry_run_tool):
        fn.__module__ = "fake_tools_default"
        setattr(module, fn.__name__.lstrip("_"), fn)

    mcp: Any = FakeMCP()
    registered = register_module_tools(mcp, module, settings)

    assert sorted(registered) == ["confirm_tool", "dry_run_tool", "read_tool"]


def test_read_only_mode_exposes_no_mutating_tool_across_all_modules(
    read_only_settings: MagicMock,
) -> None:
    """Regression guard: no module may leak a mutating tool in read-only mode.

    This is the check that catches a newly added write tool which forgets its
    ``confirm``/``dry_run`` gate — the class of bug that the explicit
    :data:`MUTATING_TOOLS_WITHOUT_GATE` list exists for.
    """
    import inspect as _inspect

    mcp: Any = FakeMCP()
    modules = _iter_tool_modules()
    assert modules, "expected to discover tool modules"

    for module in modules:
        register_module_tools(mcp, module, read_only_settings)

    registered = set(mcp.registered)
    assert registered, "expected at least some read-only tools to be registered"

    leaked = []
    for module in modules:
        for name, obj in _inspect.getmembers(module, _inspect.isfunction):
            if name in registered and obj.__module__ == module.__name__:
                if is_mutating_tool(obj):
                    leaked.append(f"{module.__name__}.{name}")

    assert not leaked, f"mutating tools registered in read-only mode: {sorted(leaked)}"


def test_read_only_mode_registers_fewer_tools_than_default(
    settings: MagicMock, read_only_settings: MagicMock
) -> None:
    """Sanity check that the filter actually removes a meaningful number of tools."""
    modules = _iter_tool_modules()

    full: Any = FakeMCP()
    for module in modules:
        register_module_tools(full, module, settings)

    limited: Any = FakeMCP()
    for module in modules:
        register_module_tools(limited, module, read_only_settings)

    assert len(limited.registered) < len(full.registered)
    assert set(limited.registered).issubset(set(full.registered))


# ---------------------------------------------------------------------------
# Global dry-run mode
# ---------------------------------------------------------------------------


def _make_module(name: str, fns: list[Any]) -> ModuleType:
    """Build a synthetic tool module from stand-in functions."""
    module = ModuleType(name)
    for fn in fns:
        fn.__module__ = name
        setattr(module, fn.__name__.lstrip("_"), fn)
    return module


def test_dry_run_mode_skips_mutating_tools_without_dry_run_gate(
    dry_run_settings: MagicMock,
) -> None:
    """Dry-run mode registers gated tools but drops mutating tools it cannot gate."""
    module = _make_module("fake_tools_dry_run_skip", [_read_tool, _confirm_tool, _dry_run_tool])

    mcp: Any = FakeMCP()
    registered = register_module_tools(mcp, module, dry_run_settings)

    assert sorted(registered) == ["dry_run_tool", "read_tool"]
    assert "confirm_tool" not in mcp.registered


async def test_dry_run_mode_forces_dry_run_on_gated_tools(dry_run_settings: MagicMock) -> None:
    """A gated tool must preview even when the caller explicitly passes dry_run=False."""
    seen: list[Any] = []

    async def _spy_tool(site_id: str, dry_run: bool | str = False, settings: Any = None) -> dict:
        seen.append(dry_run)
        return {"dry_run": dry_run}

    from src.tool_registry import _make_tool_wrapper

    wrapped = _make_tool_wrapper(_spy_tool, dry_run_settings)
    result = await wrapped("default", dry_run=False)

    assert seen == [True]
    assert result == {"dry_run": True}


async def test_default_mode_respects_caller_dry_run(settings: MagicMock) -> None:
    """With the global mode off, a caller-supplied dry_run passes through unchanged."""
    seen: list[Any] = []

    async def _spy_tool(site_id: str, dry_run: bool | str = False, settings: Any = None) -> dict:
        seen.append(dry_run)
        return {"dry_run": dry_run}

    from src.tool_registry import _make_tool_wrapper

    wrapped = _make_tool_wrapper(_spy_tool, settings)
    result = await wrapped("default", dry_run=False)

    assert seen == [False]
    assert result == {"dry_run": False}


# ---------------------------------------------------------------------------
# Metrics recording
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_metrics(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Swap the tool-registry metrics singleton for an isolated registry."""
    from src.utils.metrics import MetricsRegistry

    registry = MetricsRegistry()
    monkeypatch.setattr("src.tool_registry.METRICS", registry)
    return registry


async def test_metrics_disabled_records_nothing(settings: MagicMock, fresh_metrics: Any) -> None:
    """metrics_enabled=False keeps the wrapper off the metrics path entirely."""

    async def _spy_tool(site_id: str, settings: Any = None) -> dict:
        return {}

    from src.tool_registry import _make_tool_wrapper

    wrapped = _make_tool_wrapper(_spy_tool, settings)
    await wrapped("default")

    assert fresh_metrics.render(version="0.0.0", api_type="local").count("tool_calls") == 0


async def test_metrics_records_success_and_error(
    settings: MagicMock, fresh_metrics: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful calls count as success; exceptions count as error and re-raise."""

    async def _ok_tool(site_id: str, settings: Any = None) -> dict:
        return {}

    async def _fail_tool(site_id: str, settings: Any = None) -> dict:
        raise ValueError("boom")

    monkeypatch.setattr(settings, "metrics_enabled", True)

    from src.tool_registry import _make_tool_wrapper

    ok = _make_tool_wrapper(_ok_tool, settings)
    fail = _make_tool_wrapper(_fail_tool, settings)

    await ok("default")
    with pytest.raises(ValueError, match="boom"):
        await fail("default")

    body = fresh_metrics.render(version="0.0.0", api_type="local")
    assert 'unifi_mcp_tool_calls_total{tool="ok_tool",status="success"} 1' in body
    assert 'unifi_mcp_tool_calls_total{tool="fail_tool",status="error"} 1' in body
