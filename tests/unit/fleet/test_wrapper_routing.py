"""Controller routing in the tool wrapper (Phase 1 of docs/FLEET_SCALING_PLAN.md)."""

import functools
import importlib
import inspect
import pkgutil
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool

import src.tools
from src.config.config import APIType, Settings
from src.fleet import ControllerProfile, EnvRegistry
from src.fleet.router import FleetRouter, current_controller
from src.fleet.tools import register_fleet_tools
from src.tool_registry import _make_tool_wrapper, register_module_tools
from src.utils.exceptions import ResourceNotFoundError, ValidationError
from src.utils.metrics import MetricsRegistry

from .test_router import StaticRegistry


@pytest.fixture
def base(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "base-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    return Settings()


def _profile(name: str, host: str) -> ControllerProfile:
    return ControllerProfile(
        name=name,
        api_type=APIType.LOCAL,
        api_key=f"{name}-key",  # pragma: allowlist secret
        local_host=host,
    )


@pytest.fixture
def fleet(base: Settings) -> FleetRouter:
    registry = StaticRegistry(
        _profile("hq", "10.0.0.1"), _profile("branch", "10.0.1.1"), default="hq"
    )
    return FleetRouter(base, registry)


async def read_tool(site_id: str, settings: Any = None) -> dict:
    """Report which controller host the call reached."""
    return {"host": settings.local_host, "controller": current_controller.get()}


async def write_tool(site_id: str, confirm: bool = False, settings: Any = None) -> dict:
    """A mutating tool (it carries ``confirm``)."""
    return {"host": settings.local_host}


class TestPublicSignature:
    def test_controller_is_an_optional_keyword(self, base: Settings):
        wrapped = _make_tool_wrapper(read_tool, base)

        param = inspect.signature(wrapped).parameters["controller"]

        assert param.kind is inspect.Parameter.KEYWORD_ONLY
        assert param.default is None
        assert "settings" not in inspect.signature(wrapped).parameters

    def test_tool_function_annotations_are_not_modified(self, base: Settings):
        before = dict(read_tool.__annotations__)

        _make_tool_wrapper(read_tool, base)

        assert read_tool.__annotations__ == before


class TestWithoutRouter:
    """No router (unit tests, direct use): behave exactly as before."""

    async def test_passes_base_settings(self, base: Settings):
        result = await _make_tool_wrapper(read_tool, base)("default")

        assert result["host"] == "192.168.2.1"

    async def test_accepts_default_by_name(self, base: Settings):
        result = await _make_tool_wrapper(read_tool, base)("default", controller="default")

        assert result["controller"] == "default"

    async def test_rejects_other_controllers(self, base: Settings):
        with pytest.raises(ResourceNotFoundError):
            await _make_tool_wrapper(read_tool, base)("default", controller="hq")


class TestWithRouter:
    async def test_zero_config_router_passes_the_base_settings_object(self, base: Settings):
        seen: list[Any] = []

        async def spy(site_id: str, settings: Any = None) -> None:
            seen.append(settings)

        await _make_tool_wrapper(spy, base, FleetRouter(base, EnvRegistry(base)))("default")

        assert seen == [base]
        assert seen[0] is base

    async def test_explicit_controller_routes_the_call(self, base, fleet):
        result = await _make_tool_wrapper(read_tool, base, fleet)("default", controller="branch")

        assert result == {"host": "10.0.1.1", "controller": "branch"}

    async def test_current_controller_is_reset_after_the_call(self, base, fleet):
        await _make_tool_wrapper(read_tool, base, fleet)("default", controller="branch")

        assert current_controller.get() is None

    async def test_write_on_default_is_refused_before_the_tool_runs(self, base, fleet):
        calls: list[str] = []

        async def guarded(site_id: str, confirm: bool = False, settings: Any = None) -> None:
            calls.append(site_id)

        with pytest.raises(ValidationError, match="controller"):
            await _make_tool_wrapper(guarded, base, fleet)("default", confirm=True)

        assert calls == []

    async def test_records_per_controller_call_count(self, base, fleet, monkeypatch):
        registry = MetricsRegistry()
        monkeypatch.setattr("src.tool_registry.METRICS", registry)
        enabled = base.model_copy(update={"metrics_enabled": True})
        wrapped = _make_tool_wrapper(read_tool, enabled, FleetRouter(enabled, fleet.registry))

        await wrapped("default", controller="branch")
        await wrapped("default", controller="branch")

        body = registry.render(version="0", api_type="local")
        assert 'unifi_mcp_controller_calls_total{controller="branch"} 2' in body


class TestThroughMCPSessions:
    """End to end through FastMCP: real sessions, real session state."""

    @pytest.fixture
    def server(self, base: Settings, fleet: FleetRouter) -> FastMCP:
        mcp = FastMCP("routing-test")
        mcp.tool()(_make_tool_wrapper(read_tool, base, fleet))
        mcp.tool()(_make_tool_wrapper(write_tool, base, fleet))
        register_fleet_tools(mcp, fleet)
        return mcp

    async def test_selection_is_per_session(self, server: FastMCP):
        async with Client(server) as first, Client(server) as second:
            await first.call_tool("select_controller", {"name": "branch"})

            mine = await first.call_tool("read_tool", {"site_id": "default"})
            theirs = await second.call_tool("read_tool", {"site_id": "default"})

        assert mine.data["host"] == "10.0.1.1"
        assert theirs.data["host"] == "10.0.0.1"

    async def test_write_needs_selection_or_explicit_target(self, server: FastMCP):
        async with Client(server) as selected, Client(server) as unselected:
            await selected.call_tool("select_controller", {"name": "branch"})

            ok = await selected.call_tool("write_tool", {"site_id": "default", "confirm": True})
            with pytest.raises(ToolError, match="controller"):
                await unselected.call_tool("write_tool", {"site_id": "default", "confirm": True})
            explicit = await unselected.call_tool(
                "write_tool", {"site_id": "default", "confirm": True, "controller": "hq"}
            )

        assert ok.data["host"] == "10.0.1.1"
        assert explicit.data["host"] == "10.0.0.1"

    async def test_fleet_tools(self, server: FastMCP):
        async with Client(server) as client:
            listed = (await client.call_tool("list_controllers", {})).data
            before = (await client.call_tool("get_active_controller", {})).data
            await client.call_tool("select_controller", {"name": "branch"})
            after = (await client.call_tool("get_active_controller", {})).data

        assert [c["name"] for c in listed["controllers"]] == ["hq", "branch"]
        assert all("api_key" not in c for c in listed["controllers"])
        assert before == {"name": "hq", "source": "default"}
        assert after == {"name": "branch", "source": "session"}

    async def test_fleet_tools_take_no_controller_argument(self, server: FastMCP):
        async with Client(server) as client:
            tools = {t.name: t for t in await client.list_tools()}

        for name in ("list_controllers", "select_controller", "get_active_controller"):
            assert "controller" not in tools[name].inputSchema.get("properties", {})


def _legacy_wrapper(fn: Any) -> Any:
    """Rebuild a tool the way the wrapper exposed it before Phase 1."""
    sig = inspect.signature(fn)
    public = sig.replace(parameters=[p for n, p in sig.parameters.items() if n != "settings"])

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover - never called
        return None

    wrapper.__signature__ = public  # type: ignore[attr-defined]
    return wrapper


async def test_every_tool_schema_only_gains_the_controller_field(base: Settings):
    mcp = FastMCP("schema-test")
    originals: dict[str, Any] = {}
    for info in pkgutil.iter_modules(src.tools.__path__):
        module = importlib.import_module(f"src.tools.{info.name}")
        for name in register_module_tools(mcp, module, base):
            originals[name] = getattr(module, name)

    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}

    checked = 0
    for name, fn in originals.items():
        if "settings" not in inspect.signature(fn).parameters:
            continue
        schema = dict(tools[name].inputSchema)
        props = dict(schema.pop("properties"))
        controller = props.pop("controller")
        baseline = dict(Tool.from_function(_legacy_wrapper(fn)).parameters)
        baseline_props = baseline.pop("properties")

        assert controller["anyOf"] == [{"type": "string"}, {"type": "null"}]
        assert controller["default"] is None
        assert "description" in controller
        assert props == baseline_props, name
        assert schema == baseline, name
        checked += 1

    assert checked > 200
