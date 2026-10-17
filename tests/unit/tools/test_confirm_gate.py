"""The registry wrapper enforces ``confirm`` for every tool that declares it.

Each handler also calls ``validate_confirmation`` itself, but that is 139
separate checks, and one of them (``update_site_to_site_vpn``) tested the raw
``bool | str`` value with a bare ``if``. MCP clients send booleans as strings,
so ``confirm="false"`` was truthy there and the PUT went out. The wrapper now
refuses an unconfirmed call before the handler runs, for every module.

These tests cover every ``confirm``-carrying tool: each one is wrapped around a
spy with the tool's real signature, so a refusal proves the handler was never
reached, whatever the handler itself would have done.
"""

from __future__ import annotations

import ast
import functools
import importlib
import inspect
import pkgutil
import textwrap
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools as tools_pkg
from src.fleet.admin_tools import build_admin_tools, build_token_tools
from src.tool_registry import _make_tool_wrapper
from src.tools import site_vpn
from src.utils.exceptions import ValidationError

#: Strings that must not count as confirmation.
UNCONFIRMED = [False, None, "false", "False", "FALSE", "0", "no", "", "off", "nope"]

#: Strings that do.
CONFIRMED = [True, "true", "True", "1", "yes"]


def _tool_modules() -> list[Any]:
    return [
        importlib.import_module(f"src.tools.{info.name}")
        for info in pkgutil.iter_modules(tools_pkg.__path__)
        if not info.name.startswith("_")
    ]


def _confirm_tools() -> list[Any]:
    """Every public async tool, in any module, whose signature carries ``confirm``."""
    found = [
        obj
        for module in _tool_modules()
        for name, obj in inspect.getmembers(module, inspect.iscoroutinefunction)
        if obj.__module__ == module.__name__
        and not name.startswith("_")
        and "confirm" in inspect.signature(obj).parameters
    ]
    found += build_admin_tools(MagicMock()) + build_token_tools(MagicMock())
    return [fn for fn in found if "confirm" in inspect.signature(fn).parameters]


CONFIRM_TOOLS = _confirm_tools()
IDS = [f"{fn.__module__.rsplit('.', 1)[-1]}.{fn.__name__}" for fn in CONFIRM_TOOLS]


@pytest.fixture
def settings() -> MagicMock:
    mock = MagicMock()
    mock.log_level = "INFO"
    mock.read_only = False
    mock.dry_run = False
    mock.metrics_enabled = False
    mock.audit_log_enabled = False
    return mock


def _spy(tool: Any) -> tuple[Any, list[dict[str, Any]]]:
    """Return a stand-in with *tool*'s signature that records each call."""
    calls: list[dict[str, Any]] = []

    @functools.wraps(tool)
    async def spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"ok": True}

    return spy, calls


def test_every_module_is_covered() -> None:
    """Guard against the discovery silently finding nothing."""
    modules = {fn.__module__ for fn in CONFIRM_TOOLS}
    assert len(CONFIRM_TOOLS) >= 130
    assert "src.tools.site_vpn" in modules
    assert "src.fleet.admin_tools" in modules


@pytest.mark.parametrize("tool", CONFIRM_TOOLS, ids=IDS)
async def test_missing_confirm_is_refused(tool: Any, settings: MagicMock) -> None:
    spy, calls = _spy(tool)
    with pytest.raises(ValidationError, match="requires confirmation"):
        await _make_tool_wrapper(spy, settings, routed=False)()
    assert calls == []


@pytest.mark.parametrize("confirm", UNCONFIRMED)
@pytest.mark.parametrize("tool", CONFIRM_TOOLS, ids=IDS)
async def test_unconfirmed_value_is_refused(tool: Any, confirm: Any, settings: MagicMock) -> None:
    spy, calls = _spy(tool)
    with pytest.raises(ValidationError, match="requires confirmation"):
        await _make_tool_wrapper(spy, settings, routed=False)(confirm=confirm)
    assert calls == []


@pytest.mark.parametrize("tool", CONFIRM_TOOLS, ids=IDS)
async def test_string_false_dry_run_does_not_bypass_confirm(tool: Any, settings: MagicMock) -> None:
    spy, calls = _spy(tool)
    with pytest.raises(ValidationError):
        await _make_tool_wrapper(spy, settings, routed=False)(confirm="false", dry_run="false")
    assert calls == []


@pytest.mark.parametrize("confirm", CONFIRMED)
@pytest.mark.parametrize("tool", CONFIRM_TOOLS, ids=IDS)
async def test_confirmed_call_reaches_the_tool_as_a_bool(
    tool: Any, confirm: Any, settings: MagicMock
) -> None:
    spy, calls = _spy(tool)
    await _make_tool_wrapper(spy, settings, routed=False)(confirm=confirm)
    assert len(calls) == 1
    assert calls[0]["confirm"] is True


@pytest.mark.parametrize("tool", CONFIRM_TOOLS, ids=IDS)
async def test_preview_needs_no_confirm(tool: Any, settings: MagicMock) -> None:
    spy, calls = _spy(tool)
    await _make_tool_wrapper(spy, settings, routed=False)(dry_run="true")
    assert calls[0]["dry_run"] is True


async def test_global_dry_run_mode_needs_no_confirm(settings: MagicMock) -> None:
    settings.dry_run = True
    spy, calls = _spy(site_vpn.update_site_to_site_vpn)
    await _make_tool_wrapper(spy, settings)("default", "vpn-1", dry_run=False)
    assert calls[0]["dry_run"] is True


async def test_positional_confirm_is_read(settings: MagicMock) -> None:
    async def tool(site_id: str, confirm: bool | str = False, settings: Any = None) -> dict:
        return {"confirm": confirm}

    wrapped = _make_tool_wrapper(tool, settings)
    with pytest.raises(ValidationError):
        await wrapped("default", "false")
    assert await wrapped("default", True) == {"confirm": True}


def test_sync_tool_is_gated_too(settings: MagicMock) -> None:
    calls: list[Any] = []

    def tool(confirm: bool | str = False, settings: Any = None) -> None:
        calls.append(confirm)

    wrapped = _make_tool_wrapper(tool, settings)
    with pytest.raises(ValidationError):
        wrapped(confirm="false")
    wrapped(confirm="true")
    assert calls == [True]


async def test_site_vpn_string_false_sends_no_put_through_the_wrapper(
    settings: MagicMock,
) -> None:
    """End to end on the real handler: the original bypass, now refused."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value={"_id": "vpn-1", "purpose": "site-vpn"})
    client.put = AsyncMock()
    with patch.object(site_vpn, "UniFiClient", return_value=client) as client_cls:
        wrapped = _make_tool_wrapper(site_vpn.update_site_to_site_vpn, settings)
        with pytest.raises(ValidationError):
            await wrapped("default", "vpn-1", name="x", confirm="false")
    client_cls.assert_not_called()
    client.put.assert_not_called()


def _raw_truthiness_tests(fn: Any, param: str) -> list[int]:
    """Return line numbers in *fn* that test *param* by bare truthiness."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    tested = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If | ast.IfExp | ast.While | ast.Assert):
            operands = [node.test]
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            operands = [node.operand]
        elif isinstance(node, ast.BoolOp):
            operands = list(node.values)
        else:
            continue
        tested += [n.lineno for n in operands if isinstance(n, ast.Name) and n.id == param]
    return tested


@pytest.mark.parametrize("tool", CONFIRM_TOOLS, ids=IDS)
def test_handler_never_tests_raw_confirm(tool: Any) -> None:
    """A handler called outside the wrapper must not trust a raw ``confirm``.

    ``bool | str`` makes ``if not confirm`` a string-truthiness test, which is
    exactly how ``"false"`` got through. Use ``validate_confirmation`` or
    ``coerce_bool``.
    """
    assert _raw_truthiness_tests(tool, "confirm") == []
