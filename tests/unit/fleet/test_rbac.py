"""Role, module and controller enforcement in the tool wrapper (plan §3.6, Phase 2b)."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken

from src.access import PermissionDeniedError
from src.config.config import APIType, Settings
from src.fleet import ControllerProfile
from src.fleet.router import FleetRouter
from src.fleet.tools import register_fleet_tools
from src.tool_registry import _make_tool_wrapper

from .test_router import StaticRegistry

ROLES = ("viewer", "operator", "admin", "fleet-admin")
TIERS = ("read", "write", "destructive", "fleet-admin")
GRANTS = {
    "viewer": {"read"},
    "operator": {"read", "write"},
    "admin": {"read", "write", "destructive"},
    "fleet-admin": set(TIERS),
}


@pytest.fixture(autouse=True)
def _fresh_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.utils.audit._audit_logger", None)
    monkeypatch.delenv("UNIFI_AUDIT_CHAIN_KEY", raising=False)
    monkeypatch.delenv("UNIFI_AUDIT_LOG_KEY", raising=False)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "base-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    return Settings()


def _profile(name: str, host: str, **labels: str) -> ControllerProfile:
    return ControllerProfile(
        name=name,
        api_type=APIType.LOCAL,
        api_key=f"{name}-key",  # pragma: allowlist secret
        local_host=host,
        labels=labels,
    )


@pytest.fixture
def router(settings: Settings) -> FleetRouter:
    registry = StaticRegistry(
        _profile("hq", "10.0.0.1", group="retail"), _profile("branch", "10.0.1.1"), default="hq"
    )
    return FleetRouter(settings, registry)


def _as(monkeypatch: pytest.MonkeyPatch, role: str, **claims: Any) -> None:
    """Make every call run as an issued token with ``role``."""
    token = AccessToken(
        token="umcp_test",  # noqa: S106
        client_id="t",
        scopes=[],
        claims={"token_id": "tok-1", "name": "t", "role": role, **claims},
    )
    monkeypatch.setattr("src.access.get_access_token", lambda: token)


def _records(settings: Settings) -> list[dict[str, Any]]:
    path = Path(settings.audit_log_file)
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


calls: list[str] = []


async def read_tool(site_id: str, settings: Any = None) -> str:
    calls.append("read")
    return "read"


async def write_tool(site_id: str, confirm: bool = False, settings: Any = None) -> str:
    calls.append("write")
    return "write"


async def delete_thing(site_id: str, confirm: bool = False, settings: Any = None) -> str:
    calls.append("destructive")
    return "destructive"


async def admin_tool(confirm: bool = False, settings: Any = None) -> str:
    calls.append("fleet-admin")
    return "fleet-admin"


def _tools(settings: Settings, router: FleetRouter) -> dict[str, Any]:
    return {
        "read": _make_tool_wrapper(read_tool, settings, router),
        "write": _make_tool_wrapper(write_tool, settings, router),
        "destructive": _make_tool_wrapper(delete_thing, settings, router),
        "fleet-admin": _make_tool_wrapper(
            admin_tool, settings, routed=False, tier="fleet-admin", event_type="admin"
        ),
    }


async def _call(tool: Any, tier: str) -> Any:
    if tier == "fleet-admin":
        return await tool(confirm=True)
    if tier == "read":
        return await tool("default", controller="hq")
    return await tool("default", confirm=True, controller="hq")


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("tier", TIERS)
async def test_role_tier_matrix(role, tier, settings, router, monkeypatch):
    _as(monkeypatch, role)
    calls.clear()
    tool = _tools(settings, router)[tier]

    if tier in GRANTS[role]:
        assert await _call(tool, tier) == tier
        assert calls == [tier]
        assert all(r["event_type"] != "denied" for r in _records(settings))
    else:
        with pytest.raises(PermissionDeniedError, match=f"needs the '{tier}' tier"):
            await _call(tool, tier)
        assert calls == []
        (denied,) = _records(settings)
        assert (denied["event_type"], denied["result"], denied["tier"]) == (
            "denied",
            "denied",
            tier,
        )
        assert denied["principal"]["role"] == role


async def test_denial_names_only_the_required_tier(settings, router, monkeypatch):
    _as(monkeypatch, "viewer")

    with pytest.raises(PermissionDeniedError) as err:
        await _make_tool_wrapper(delete_thing, settings, router)("s", confirm=True, controller="hq")

    assert "viewer" not in str(err.value)
    assert "read" not in str(err.value)


async def test_module_filters(settings, router, monkeypatch):
    _as(monkeypatch, "admin", allow_modules=["devices"])

    with pytest.raises(PermissionDeniedError, match="module 'test_rbac'"):
        await _make_tool_wrapper(read_tool, settings, router)("s", controller="hq")

    _as(monkeypatch, "admin", deny_modules=["test_*"])
    with pytest.raises(PermissionDeniedError, match="module"):
        await _make_tool_wrapper(read_tool, settings, router)("s", controller="hq")


async def test_controller_label_scope(settings, router, monkeypatch):
    _as(monkeypatch, "admin", controller_labels={"group": "retail"})
    tool = _make_tool_wrapper(write_tool, settings, router)

    assert await tool("s", confirm=True, controller="hq") == "write"
    with pytest.raises(PermissionDeniedError, match="controller 'branch'"):
        await tool("s", confirm=True, controller="branch")

    denied = [r for r in _records(settings) if r["event_type"] == "denied"]
    assert [r["controller"] for r in denied] == ["branch"]


async def test_session_tools_respect_the_label_scope(settings, router, monkeypatch):
    _as(monkeypatch, "admin", controller_labels={"group": "retail"})
    mcp = FastMCP("scope")
    register_fleet_tools(mcp, router)

    async with Client(mcp) as client:
        listed = (await client.call_tool("list_controllers", {})).data
        with pytest.raises(ToolError, match="outside this caller's scope"):
            await client.call_tool("select_controller", {"name": "branch"})

    assert [c["name"] for c in listed["controllers"]] == ["hq"]


async def test_stdio_role_can_be_lowered(monkeypatch, tmp_path):
    monkeypatch.setenv("UNIFI_API_KEY", "k")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UNIFI_STDIO_ROLE", "viewer")
    settings = Settings()

    assert await _make_tool_wrapper(read_tool, settings)("s") == "read"
    with pytest.raises(PermissionDeniedError):
        await _make_tool_wrapper(write_tool, settings)("s", confirm=True)


async def test_break_glass_callers_keep_full_access(settings, router):
    # stdio, no token: fleet-admin, as before enforcement existed.
    assert await _call(_tools(settings, router)["fleet-admin"], "fleet-admin") == "fleet-admin"
    assert await _call(_tools(settings, router)["destructive"], "destructive") == "destructive"
