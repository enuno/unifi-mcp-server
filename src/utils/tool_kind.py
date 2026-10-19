"""Read/write declarations for MCP tools.

Every tool says whether it can change controller state, with :func:`read_tool`
or :func:`write_tool` on its definition. ``register_module_tools`` refuses a
tool that declares neither, so read-only mode never has to guess: a new write
tool cannot reach a ``UNIFI_READ_ONLY`` session by forgetting a parameter.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, TypeVar

ToolKind = Literal["read", "write"]

F = TypeVar("F", bound=Callable[..., Any])

#: Attribute the decorators set on the tool function.
TOOL_KIND_ATTR = "__unifi_tool_kind__"


class UndeclaredToolError(TypeError):
    """A tool was registered without a read/write declaration."""


def _declare(fn: F, kind: ToolKind) -> F:
    existing = getattr(fn, TOOL_KIND_ATTR, None)
    if existing is not None and existing != kind:
        raise UndeclaredToolError(
            f"{getattr(fn, '__name__', fn)!r} is declared both {existing!r} and {kind!r}"
        )
    setattr(fn, TOOL_KIND_ATTR, kind)
    return fn


def read_tool(fn: F) -> F:
    """Declare that tool *fn* only reads controller state.

    Args:
        fn: The tool function.

    Returns:
        *fn* itself, marked as a read tool.
    """
    return _declare(fn, "read")


def write_tool(fn: F) -> F:
    """Declare that tool *fn* can change controller state.

    Read-only mode leaves write tools unregistered.

    Args:
        fn: The tool function.

    Returns:
        *fn* itself, marked as a write tool.
    """
    return _declare(fn, "write")


def declared_kind(fn: Any) -> ToolKind | None:
    """Return the read/write declaration of *fn*, or None when it has none.

    Args:
        fn: The tool function.

    Returns:
        ``"read"``, ``"write"`` or None.
    """
    kind = getattr(fn, TOOL_KIND_ATTR, None)
    return kind if kind in ("read", "write") else None
