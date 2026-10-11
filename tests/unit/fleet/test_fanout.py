"""fleet_fanout: one read tool on many controllers, with partial results.

The tools run behind the real wrapper and router on an in-memory FastMCP
server and are called through an MCP client, so per-controller calls take the
same path (role, module and controller checks, routing) as direct calls.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken

from src.config.config import APIType, Settings
from src.fleet.fleet_tools import register_fleet_read_tools
from src.fleet.registry import ControllerProfile
from src.fleet.router import FleetRouter
from src.tool_registry import TOOL_TIERS, _make_tool_wrapper, tool_tier
from src.utils.exceptions import ResourceNotFoundError

KEY = "k"  # pragma: allowlist secret
FLEET_SIZE = 1000


class StaticRegistry:
    def __init__(self, profiles: list[ControllerProfile]) -> None:
        self._profiles = {p.name: p for p in profiles}

    async def list_controllers(self) -> list[ControllerProfile]:
        return list(self._profiles.values())

    async def get_controller(self, name: str) -> ControllerProfile:
        try:
            return self._profiles[name]
        except KeyError:
            raise ResourceNotFoundError("controller", name) from None

    async def default_controller(self) -> str | None:
        return None


def _profile(n: int, **labels: str) -> ControllerProfile:
    return ControllerProfile(
        name=f"c-{n:04d}",
        api_type=APIType.LOCAL,
        api_key=KEY,
        local_host=f"10.{n // 256}.{n % 256}.1",
        labels=labels,
    )


# Controller behavior, by host: about one in 20 fails, and 10.0.1.1 (c-0001) hangs.
def _failing(host: str) -> bool:
    return int(host.split(".")[2]) % 20 == 7


async def get_thing(site_id: str = "default", settings: Any = None) -> dict[str, Any]:
    host = settings.local_host
    if host == "10.0.1.1":
        await asyncio.sleep(30)
    if _failing(host):
        raise ConnectionError(f"{host} unreachable")
    return {"host": host, "site": site_id}


async def list_things(settings: Any = None) -> list[str]:
    return [settings.local_host]


async def set_thing(value: str, confirm: bool = False, settings: Any = None) -> str:
    raise AssertionError("a write tool must never be fanned out")  # pragma: no cover


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", KEY)
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UNIFI_FLEET_FANOUT_CONCURRENCY", "100")
    monkeypatch.setenv("UNIFI_FLEET_FANOUT_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setenv("UNIFI_FLEET_FANOUT_DEADLINE_SECONDS", "10")
    monkeypatch.setattr("src.utils.audit._audit_logger", None)
    return Settings()


@pytest.fixture
def server(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> FastMCP:
    profiles = [_profile(n, group="even" if n % 2 == 0 else "odd") for n in range(FLEET_SIZE)]
    registry = StaticRegistry(profiles)
    router = FleetRouter(settings, registry)
    mcp = FastMCP("fanout-test")
    for fn in (get_thing, list_things, set_thing):
        mcp.tool()(_make_tool_wrapper(fn, settings, router))
        monkeypatch.setitem(TOOL_TIERS, fn.__name__, tool_tier(fn))
    for name in register_fleet_read_tools(mcp, registry, settings, None):
        monkeypatch.setitem(TOOL_TIERS, name, "read")
    return mcp


def _as(monkeypatch: pytest.MonkeyPatch, role: str, **claims: Any) -> None:
    token = AccessToken(
        token="umcp_test",  # noqa: S106
        client_id="t",
        scopes=[],
        claims={"token_id": "tok-1", "name": "t", "role": role, **claims},
    )
    monkeypatch.setattr("src.access.get_access_token", lambda: token)


async def _fanout(server: FastMCP, **arguments: Any) -> dict[str, Any]:
    async with Client(server) as client:
        result = await client.call_tool("fleet_fanout", arguments)
    assert isinstance(result.structured_content, dict)
    return result.structured_content


async def test_thousand_controllers_with_failures_return_partial_results(
    server: FastMCP, settings: Settings
) -> None:
    started = time.monotonic()
    result = await _fanout(server, tool="get_thing", arguments={"site_id": "default"})
    elapsed = time.monotonic() - started

    results = result["results"]
    assert len(results) == FLEET_SIZE
    failing = {name for name, r in results.items() if not r["ok"]}
    expected = {
        p.name for p in (_profile(n) for n in range(FLEET_SIZE)) if _failing(p.local_host or "")
    } | {
        "c-0001"
    }  # 10.0.1.1 hangs past the per-controller timeout
    assert failing == expected
    assert result["failed"] == len(expected)
    assert result["succeeded"] == FLEET_SIZE - len(expected)
    assert 0.04 < len(expected) / FLEET_SIZE < 0.07
    assert results["c-0001"]["error"] == "timed out after 0.5s"
    assert "unreachable" in results["c-0007"]["error"]
    assert results["c-0000"] == {"ok": True, "data": {"host": "10.0.0.1", "site": "default"}}
    assert elapsed < settings.fleet_fanout_deadline_seconds


async def test_overall_deadline_reports_unfinished_controllers(server: FastMCP) -> None:
    started = time.monotonic()
    result = await _fanout(
        server,
        tool="get_thing",
        controllers=["c-0000", "c-0001"],
        timeout_seconds=60,
        deadline_seconds=0.3,
    )

    assert time.monotonic() - started < 5
    assert result["results"]["c-0000"]["ok"] is True
    assert result["results"]["c-0001"] == {
        "ok": False,
        "error": "not finished within the 0.3s deadline",
    }


async def test_list_results_are_unwrapped(server: FastMCP) -> None:
    result = await _fanout(server, tool="list_things", controllers=["c-0002"])
    assert result["results"] == {"c-0002": {"ok": True, "data": ["10.0.2.1"]}}


async def test_label_filter(server: FastMCP) -> None:
    result = await _fanout(server, tool="list_things", labels={"group": "odd"})
    assert len(result["results"]) == FLEET_SIZE // 2
    assert all(int(name[2:]) % 2 for name in result["results"])


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"tool": "set_thing"}, "only read-tier controller tools"),
        ({"tool": "fleet_fanout"}, "only read-tier controller tools"),
        ({"tool": "no_such_tool"}, "only read-tier controller tools"),
        ({"tool": "get_thing", "arguments": {"controller": "c-0001"}}, "not in `arguments"),
        ({"tool": "get_thing", "controllers": ["nope"]}, "Unknown controllers"),
        ({"tool": "get_thing", "timeout_seconds": -1}, "must be positive"),
        ({"tool": "get_thing", "timeout_seconds": 0}, "must be positive"),
        ({"tool": "get_thing", "deadline_seconds": 0}, "must be positive"),
    ],
)
async def test_refused(server: FastMCP, arguments: dict[str, Any], message: str) -> None:
    with pytest.raises(ToolError, match=message):
        await _fanout(server, **arguments)


async def test_a_tool_without_a_controller_argument_is_refused(
    server: FastMCP, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(TOOL_TIERS, "fleet_health_like", "read")

    async def fleet_health_like() -> str:  # pragma: no cover - never called
        return "x"

    server.tool(name="unrouted_read")(fleet_health_like)
    monkeypatch.setitem(TOOL_TIERS, "unrouted_read", "read")
    with pytest.raises(ToolError, match="not a controller tool"):
        await _fanout(server, tool="unrouted_read")


class TestCallerScope:
    async def test_controller_scope_limits_the_targets(
        self, server: FastMCP, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _as(monkeypatch, "viewer", controller_labels={"group": "even"})

        result = await _fanout(server, tool="list_things")

        assert len(result["results"]) == FLEET_SIZE // 2
        assert all(int(name[2:]) % 2 == 0 for name in result["results"])

    async def test_naming_an_out_of_scope_controller_is_refused(
        self, server: FastMCP, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _as(monkeypatch, "viewer", controller_labels={"group": "even"})
        with pytest.raises(ToolError, match="Unknown controllers .*c-0001"):
            await _fanout(server, tool="list_things", controllers=["c-0000", "c-0001"])

    async def test_module_filters_apply_to_each_controller_call(
        self, server: FastMCP, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The tools above live in this test module; deny it but allow fleet.
        _as(monkeypatch, "viewer", deny_modules=["test_fanout"])

        result = await _fanout(server, tool="list_things", controllers=["c-0000"])

        assert result["results"]["c-0000"]["ok"] is False
        assert "not allowed" in result["results"]["c-0000"]["error"]

    async def test_the_fleet_module_can_be_denied(
        self, server: FastMCP, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _as(monkeypatch, "viewer", deny_modules=["fleet"])
        with pytest.raises(ToolError, match="module 'fleet'"):
            await _fanout(server, tool="list_things")
