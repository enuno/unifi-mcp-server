"""The A2A tool executor.

The delegation endpoint must run a registered MCP tool, and it must run it
through the same path an MCP client would take. That is what keeps the
server's controls in force: the tool wrapper checks the caller's role
against the tool's tier, refuses a write without ``confirm=True``, forces a
preview in dry-run mode, and writes the audit record.

Calling the registered component's function directly, rather than
re-implementing the call, is what makes the delegation path identical to the
MCP path. The wrapper binds the principal itself, so the role that
authorises the call is the one resolved from the request's bearer token.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from fastmcp.tools.function_tool import FunctionTool

from ..utils import get_logger
from .capabilities import iter_registered_tools

logger = get_logger(__name__)


class UnknownToolError(LookupError):
    """Raised when a delegation names a tool this server did not register."""


def _tool_map(mcp: FastMCP) -> dict[str, FunctionTool]:
    """Return the registered tools of *mcp*, keyed by public name.

    Args:
        mcp: The FastMCP server.

    Returns:
        The tool map.
    """
    return {tool.name: tool for tool in iter_registered_tools(mcp)}


async def execute_tool_call(mcp: FastMCP, tool_name: str, params: dict[str, Any]) -> Any:
    """Run a registered tool as a delegated call.

    The tool is invoked through its registered wrapper, so the role check,
    the confirmation gate, the dry-run behaviour and the audit record all
    apply exactly as they do for an MCP client.

    Args:
        mcp: The FastMCP server whose registered tools may be called.
        tool_name: The public name of the tool to run.
        params: The arguments for the tool.

    Returns:
        The tool's result.

    Raises:
        UnknownToolError: When the tool is not registered on this server.
    """
    tool = _tool_map(mcp).get(tool_name)
    if tool is None:
        raise UnknownToolError(f"Unknown tool: {tool_name}")

    arguments = dict(params or {})
    # The wrapper needs the settings the tool was registered with. They are
    # bound in the wrapper's closure, so only the public arguments are
    # passed.
    result = await tool.fn(**arguments)
    return result


def build_tool_executor(mcp: FastMCP) -> Any:
    """Return a callable that runs a delegated tool call.

    Args:
        mcp: The FastMCP server whose registered tools may be called.

    Returns:
        An async callable taking the tool name and the arguments.
    """

    async def executor(tool_name: str, params: dict[str, Any]) -> Any:
        """Run one registered tool.

        Args:
            tool_name: The public name of the tool to run.
            params: The arguments for the tool.

        Returns:
            The tool's result.
        """
        return await execute_tool_call(mcp, tool_name, params)

    return executor


__all__ = ["UnknownToolError", "build_tool_executor", "execute_tool_call"]
