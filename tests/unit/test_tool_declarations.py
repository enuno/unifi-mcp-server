"""Every ``@read_tool`` declaration is checked against what the tool calls.

``UNIFI_READ_ONLY`` registers only tools declared ``@read_tool``, so a write
tool declared read is a write tool in a read-only session. This walks each read
tool's call graph, through the helpers it calls in ``src``, and fails if it
reaches a controller write: an HTTP ``post``/``put``/``patch``/``delete``, a
client method whose name says it changes state, or a ``@write_tool``.

It is a static check and can be fooled (a write built from a string method
name, say), but it fails on the plain case: a tool that writes and was
declared read, or copied from a read tool and never re-declared.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import textwrap
from types import ModuleType
from typing import Any

import pytest

import src.tools
from src.utils.tool_kind import declared_kind, read_tool, write_tool

#: HTTP verbs that change state when called as a client method.
WRITE_VERBS = frozenset({"post", "put", "patch", "delete"})

#: Client method name prefixes that change state (``client.delete_backup``,
#: ``client.trigger_backup``). Matched on the attribute name only.
WRITE_METHOD_PREFIXES = (
    "adopt_",
    "block_",
    "create_",
    "delete_",
    "disable_",
    "enable_",
    "forget_",
    "provision_",
    "reboot_",
    "remove_",
    "reset_",
    "restart_",
    "restore_",
    "set_",
    "trigger_",
    "unblock_",
    "update_",
    "upgrade_",
)

#: Read tools that query with POST: the legacy ``stat/`` reports and the
#: traffic-flow search take their filter as a POST body and change nothing.
#: Only ``post`` is exempt for these; any other write call still fails.
READS_THAT_POST = frozenset(
    {
        "export_traffic_flows",
        "filter_traffic_flows",
        "find_flows_for_rule_reference",
        "get_client_flow_aggregation",
        "get_dpi_statistics",
        "get_flow_analytics",
        "get_flow_risks",
        "get_flow_statistics",
        "get_historical_stats",
        "get_speed_test_history",
        "get_top_flows",
        "get_traffic_flow_details",
        "get_traffic_flows",
        "list_alarms",
        "list_events",
        "list_top_applications",
    }
)


def _function_ast(fn: Any) -> ast.AST | None:
    """Return the AST of *fn*'s own definition, or None without source."""
    try:
        source = inspect.getsource(inspect.unwrap(fn))
    except (OSError, TypeError):
        return None
    return ast.parse(textwrap.dedent(source))


def _resolve(node: ast.expr, scope: dict[str, Any]) -> Any:
    """Resolve a ``name`` or ``module.name`` call target in *scope*, or None."""
    if isinstance(node, ast.Name):
        return scope.get(node.id)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        owner = scope.get(node.value.id)
        if isinstance(owner, ModuleType):
            return getattr(owner, node.attr, None)
    return None


def _is_ours(obj: Any) -> bool:
    return inspect.isfunction(obj) and (obj.__module__ or "").split(".")[0] in ("src", __name__)


def write_calls(fn: Any, *, allow_post: bool = False) -> list[str]:
    """Return the write calls reachable from *fn*, as ``where: what`` strings.

    Args:
        fn: The tool function to inspect.
        allow_post: Do not count ``.post(...)`` (see :data:`READS_THAT_POST`).

    Returns:
        One entry per write call found, empty when the tool only reads.
    """
    found: list[str] = []
    seen: set[Any] = set()

    def visit(func: Any) -> None:
        func = inspect.unwrap(func)
        if func in seen:
            return
        seen.add(func)
        tree = _function_ast(func)
        if tree is None:
            return
        scope = {**vars(inspect.getmodule(func) or ModuleType("_")), **_closure(func)}
        where = f"{func.__module__}.{func.__qualname__}"
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if isinstance(target, ast.Attribute):
                attr = target.attr
                if attr in WRITE_VERBS and not (allow_post and attr == "post"):
                    found.append(f"{where}: .{attr}()")
                    continue
                if attr.startswith(WRITE_METHOD_PREFIXES) and _resolve(target, scope) is None:
                    found.append(f"{where}: .{attr}()")
                    continue
            callee = _resolve(target, scope)
            if callee is None or not _is_ours(callee):
                continue
            if declared_kind(callee) == "write":
                found.append(f"{where}: calls @write_tool {callee.__name__}")
                continue
            visit(callee)

    visit(fn)
    return found


def _closure(func: Any) -> dict[str, Any]:
    """Return the free variables *func* closes over, by name."""
    cells = func.__closure__ or ()
    return {
        name: cell.cell_contents
        for name, cell in zip(func.__code__.co_freevars, cells, strict=False)
        if _cell_is_set(cell)
    }


def _cell_is_set(cell: Any) -> bool:
    try:
        cell.cell_contents  # noqa: B018 - probing for an empty cell
    except ValueError:
        return False
    return True


def _read_tools() -> list[tuple[str, Any]]:
    tools = []
    for info in pkgutil.iter_modules(src.tools.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"src.tools.{info.name}")
        for name, fn in inspect.getmembers(module, inspect.iscoroutinefunction):
            if name.startswith("_") or fn.__module__ != module.__name__:
                continue
            if declared_kind(fn) == "read":
                tools.append((f"{info.name}.{name}", fn))
    return tools


def test_no_read_tool_reaches_a_write_call() -> None:
    """A tool declared ``@read_tool`` must not reach a controller write."""
    tools = _read_tools()
    assert len(tools) > 100, "expected to find the read tools"

    offenders = {
        name: calls
        for name, fn in tools
        if (calls := write_calls(fn, allow_post=fn.__name__ in READS_THAT_POST))
    }

    assert not offenders, (
        "Tools declared @read_tool reach a write call. Declare them @write_tool "
        f"(with confirm and dry_run), or fix the call: {offenders}"
    )


def test_reads_that_post_are_real_read_tools() -> None:
    """The POST exemption list names only existing read tools, so it cannot rot."""
    read_names = {fn.__name__ for _, fn in _read_tools()}
    assert sorted(READS_THAT_POST - read_names) == []


# ---------------------------------------------------------------------------
# The check itself: it must fail on an unmarked mutator.
# ---------------------------------------------------------------------------


class _Client:
    async def get(self, path: str) -> dict:
        return {}

    async def put(self, path: str, json_data: dict) -> dict:
        return {}

    async def trigger_backup(self) -> dict:
        return {}


async def _apply_led(client: _Client, device_id: str, colour: str) -> dict:
    return await client.put(f"/devices/{device_id}", json_data={"led": colour})


@write_tool
async def _set_led(device_id: str, confirm: bool = False, dry_run: bool = False) -> dict:
    return await _apply_led(_Client(), device_id, "red")


@read_tool
async def _honest_read(device_id: str) -> dict:
    return await _Client().get(f"/devices/{device_id}")


@read_tool
async def _mislabelled_direct(device_id: str, colour: str) -> dict:
    return await _Client().put(f"/devices/{device_id}", json_data={"led": colour})


@read_tool
async def _mislabelled_via_helper(device_id: str) -> dict:
    return await _apply_led(_Client(), device_id, "blue")


@read_tool
async def _mislabelled_client_method() -> dict:
    return await _Client().trigger_backup()


@read_tool
async def _mislabelled_calls_write_tool(device_id: str) -> dict:
    return await _set_led(device_id, confirm=True)


def test_check_passes_an_honest_read_tool() -> None:
    assert write_calls(_honest_read) == []


@pytest.mark.parametrize(
    "tool",
    [
        _mislabelled_direct,
        _mislabelled_via_helper,
        _mislabelled_client_method,
        _mislabelled_calls_write_tool,
    ],
)
def test_check_fails_on_an_unmarked_mutator(tool: Any) -> None:
    """A write tool declared ``@read_tool`` is caught, however it reaches the write."""
    assert write_calls(tool), f"{tool.__name__} writes but the check passed it"


def test_post_exemption_covers_post_only() -> None:
    """Exempting a POST query does not exempt a PUT in the same tool."""
    assert write_calls(_mislabelled_direct, allow_post=True)
