"""Delegation contract helpers for A2A tool invocation."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastmcp import FastMCP

from ..config import Settings
from ..utils import validate_confirmation
from .agent_card import _safety_requirement_for_tool
from .types import AuthenticationMode, DelegationContract


def _now_iso() -> str:
    """Return a UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _run_sync(coro: Any) -> Any:
    """Run an awaitable from synchronous code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if loop.is_running():
        raise RuntimeError(
            "Cannot synchronously wait for a delegated call inside a running event loop"
        )
    return loop.run_until_complete(coro)


def _active_mcp() -> FastMCP | None:
    """Return the live FastMCP instance if it has already been imported."""
    import sys

    for module in list(sys.modules.values()):
        if module is None:
            continue
        mcp = getattr(module, "mcp", None)
        if isinstance(mcp, FastMCP):
            return mcp
    return None


def _auth_mode_for_settings(settings: Settings) -> AuthenticationMode:
    """Choose the broadest appropriate auth mode for the current settings."""
    return AuthenticationMode.BOTH if settings.api_type.value else AuthenticationMode.BOTH


def _is_destructive_tool_name(tool_name: str) -> bool:
    """Heuristically detect destructive actions from a tool name."""
    lowered = tool_name.lower()
    return any(
        token in lowered
        for token in (
            "delete",
            "remove",
            "reset",
            "restore",
            "reboot",
            "restart",
            "disable",
            "flush",
            "purge",
            "provision",
            "deprovision",
        )
    )


def create_delegation_contract(
    tool_name: str,
    params: dict[str, Any],
    requesting_agent: str,
) -> DelegationContract:
    """Create a delegation contract for a tool invocation."""
    import json

    json.dumps(params)
    safety = None
    mcp = _active_mcp()
    if mcp is not None:
        for provider in getattr(mcp, "providers", []):
            components = getattr(provider, "_components", None)
            if not isinstance(components, dict):
                continue
            for component in components.values():
                if getattr(component, "name", None) == tool_name:
                    safety = _safety_requirement_for_tool(component)
                    break
            if safety is not None:
                break

    requires_confirmation = (
        bool(safety.destructive) if safety is not None else _is_destructive_tool_name(tool_name)
    )
    return DelegationContract(
        contractId=str(uuid.uuid4()),
        toolName=tool_name,
        params=params,
        requestingAgent=requesting_agent,
        authenticationMode=AuthenticationMode.BOTH,
        createdAt=_now_iso(),
        requiresConfirmation=requires_confirmation,
        safetyRequirement=safety,
        metadata={"source": "a2a.delegation"},
        dryRun=False,
    )


def validate_delegation(contract: DelegationContract) -> bool:
    """Validate that a delegation contract is safe and well formed."""
    if not contract.contractId or not contract.toolName or not contract.requestingAgent:
        return False
    if not isinstance(contract.params, dict):
        return False
    if contract.requiresConfirmation and contract.safetyRequirement is None:
        return False
    if contract.requiresConfirmation and not bool(contract.params.get("confirm")):
        return False
    return True


async def _call_tool(mcp: FastMCP, tool_name: str, params: dict[str, Any]) -> Any:
    """Call a registered MCP tool by name."""
    return await mcp.call_tool(tool_name, params)


def execute_delegated_call(contract: DelegationContract, settings: Settings) -> Any:
    """Execute a delegated tool call against the active MCP server."""
    if not validate_delegation(contract):
        raise ValueError("Invalid delegation contract")

    mcp = _active_mcp()
    if mcp is None:
        raise RuntimeError("No active FastMCP instance is available for delegation execution")

    if contract.requiresConfirmation:
        validate_confirmation(True, contract.toolName, contract.dryRun)

    _ = _auth_mode_for_settings(settings)
    return _run_sync(_call_tool(mcp, contract.toolName, contract.params))


__all__ = [
    "create_delegation_contract",
    "execute_delegated_call",
    "validate_delegation",
]
