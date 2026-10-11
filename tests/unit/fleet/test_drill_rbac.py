"""RBAC deny-path drill (docs/FLEET_SCALING_PLAN.md Phase 5): every tool, every role.

Registers every tool module the way the server does (plus the fleet session,
read and admin tools), then calls every tool as every role that lacks the
tool's tier. Each call must be refused before anything reaches a controller
or the registry, and each refusal must leave a ``denied`` audit record. The
role x tier matrix test in test_rbac.py checks the rule on sample tools; this
checks that no registered tool escapes it.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken

import src.tools
from src.access import ROLE_TIERS, PermissionDeniedError
from src.config.config import APIType, Settings
from src.fleet import ControllerProfile
from src.fleet.admin_tools import register_admin_tools
from src.fleet.fleet_tools import register_fleet_read_tools
from src.fleet.router import FleetRouter
from src.fleet.tools import register_fleet_tools
from src.tool_registry import TOOL_TIERS, register_module_tools

from .test_router import StaticRegistry

ROLES = ("viewer", "operator", "admin")

#: Registered without the tier-checking wrapper, each for a stated reason.
UNWRAPPED = {
    # Session selection: no controller is contacted, and each checks the
    # caller's controller scope itself (test_rbac.py).
    "list_controllers": "session tool",
    "select_controller": "session tool",
    "get_active_controller": "session tool",
}


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "drill-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.0.2.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.delenv("UNIFI_AUDIT_CHAIN_KEY", raising=False)
    monkeypatch.delenv("UNIFI_AUDIT_LOG_KEY", raising=False)
    monkeypatch.setattr("src.utils.audit._audit_logger", None)
    return Settings()


@pytest.fixture
def server(settings: Settings) -> FastMCP:
    profile = ControllerProfile(
        name="hq",
        api_type=APIType.LOCAL,
        api_key="hq-key",  # pragma: allowlist secret
        local_host="192.0.2.1",
    )
    router = FleetRouter(settings, StaticRegistry(profile, default="hq"))
    mcp = FastMCP("rbac-drill")
    for info in pkgutil.iter_modules(src.tools.__path__):
        module = importlib.import_module(f"src.tools.{info.name}")
        register_module_tools(mcp, module, settings, router=router)
    register_fleet_tools(mcp, router)
    register_fleet_read_tools(mcp, router.registry, settings, MagicMock())
    register_admin_tools(mcp, MagicMock(), settings)
    return mcp


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    reached: list[str] = []

    async def send(self: Any, request: httpx.Request, *args: Any, **kwargs: Any) -> Any:
        reached.append(str(request.url))
        raise AssertionError(f"a refused call reached {request.url}")

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    return reached


def _as(monkeypatch: pytest.MonkeyPatch, role: str) -> None:
    token = AccessToken(
        token="umcp_drill",  # noqa: S106
        client_id="drill",
        scopes=[],
        claims={"token_id": f"tok-{role}", "name": f"drill-{role}", "role": role},
    )
    monkeypatch.setattr("src.access.get_access_token", lambda: token)


async def _tools(server: FastMCP) -> dict[str, Any]:
    return {tool.name: tool for tool in await server.list_tools()}


async def test_every_wrapped_tool_has_a_known_tier(server: FastMCP) -> None:
    tools = await _tools(server)
    untiered = sorted(set(tools) - set(TOOL_TIERS))

    assert untiered == sorted(UNWRAPPED)
    assert {TOOL_TIERS[n] for n in tools if n not in UNWRAPPED} <= {
        "read",
        "write",
        "destructive",
        "fleet-admin",
    }
    assert len(tools) > 300  # every module registered, not a subset


@pytest.mark.parametrize("role", ROLES)
async def test_every_tool_beyond_the_role_is_refused_before_any_call(
    server: FastMCP,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    no_network: list[str],
    role: str,
) -> None:
    _as(monkeypatch, role)
    tools = await _tools(server)
    beyond = sorted(
        name for name in tools if name not in UNWRAPPED and TOOL_TIERS[name] not in ROLE_TIERS[role]
    )
    assert beyond, f"{role} should lack some tier"

    escaped = []
    for name in beyond:
        try:
            await tools[name].fn()
        except PermissionDeniedError as e:
            assert f"needs the '{TOOL_TIERS[name]}' tier" in str(e)
        else:
            escaped.append(name)

    assert escaped == []
    assert no_network == []
    denied = [
        json.loads(line)
        for line in Path(settings.audit_log_file).read_text().splitlines()
        if json.loads(line).get("event_type") == "denied"
    ]
    assert sorted(r["operation"] for r in denied) == beyond
    assert {r["principal"]["role"] for r in denied} == {role}


async def test_the_matrix_covers_every_tier(server: FastMCP) -> None:
    tools = await _tools(server)
    counts: dict[str, int] = {}
    for name in tools:
        if name not in UNWRAPPED:
            tier = TOOL_TIERS[name]
            counts[tier] = counts.get(tier, 0) + 1

    # Each tier is represented, so each role's refusals are exercised.
    assert set(counts) == {"read", "write", "destructive", "fleet-admin"}
