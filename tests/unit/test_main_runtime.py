"""Runtime paths of src/main.py: resource handlers, debug tool registration, the
lifespan, the start-up audit record, and main()'s transport branches.

``src.main`` builds its server at import time from the environment, so each
test reloads it with the environment it needs. ``mcp.run`` is always patched:
nothing here opens a socket or talks to a controller.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_LOCAL_ENV = {
    "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
    "UNIFI_API_TYPE": "local",
    "UNIFI_LOCAL_HOST": "192.0.2.1",
    "AGNOST_ENABLED": "false",
    "MCP_SERVER_TRANSPORT": "stdio",
}


def _reload_main(**overrides: str) -> ModuleType:
    for mod_name in list(sys.modules):
        if mod_name == "src.main" or mod_name.startswith("src.main."):
            del sys.modules[mod_name]
    with patch.dict("os.environ", {**_LOCAL_ENV, **overrides}, clear=False):
        return importlib.import_module("src.main")


def _fn(component):
    """The undecorated function behind a FastMCP resource or tool."""
    return getattr(component, "fn", component)


@pytest.fixture(scope="module")
def main_mod() -> ModuleType:
    return _reload_main()


class TestLocalResources:
    @pytest.mark.asyncio
    async def test_devices(self, main_mod: ModuleType) -> None:
        device = MagicMock(model="U6-Pro", mac="aa:bb", ip="10.0.0.2")
        device.name = None
        with patch.object(
            main_mod.devices_resource, "list_devices", AsyncMock(return_value=[device])
        ):
            text = await _fn(main_mod.get_devices_resource)("default")
        assert text == "Device: U6-Pro (aa:bb) - 10.0.0.2"

    @pytest.mark.asyncio
    async def test_clients(self, main_mod: ModuleType) -> None:
        client = MagicMock(hostname=None, mac="aa:cc", ip="10.0.0.3")
        client.name = "Laptop"
        resource = main_mod.clients_resource
        with patch.object(
            resource, "list_clients", AsyncMock(return_value=[client])
        ) as list_clients:
            text = await _fn(main_mod.get_clients_resource)("default")
        list_clients.assert_awaited_once_with("default", active_only=True)
        assert text == "Client: Laptop (10.0.0.3)"

    @pytest.mark.asyncio
    async def test_networks(self, main_mod: ModuleType) -> None:
        network = MagicMock(vlan_id=None, ip_subnet="10.0.0.0/24")
        network.name = "LAN"
        with patch.object(
            main_mod.networks_resource, "list_networks", AsyncMock(return_value=[network])
        ):
            text = await _fn(main_mod.get_networks_resource)("default")
        assert text == "Network: LAN (VLAN none) - 10.0.0.0/24"

    @pytest.mark.asyncio
    async def test_traffic_flows(self, main_mod: ModuleType) -> None:
        with patch.object(
            main_mod.traffic_flows_tools, "get_traffic_flows", AsyncMock(return_value=[{"id": 1}])
        ):
            text = await _fn(main_mod.get_traffic_flows_resource)("default")
        assert '"id": 1' in text

    @pytest.mark.asyncio
    async def test_protect_nvrs_and_cameras(self, main_mod: ModuleType) -> None:
        nvr = MagicMock(id="n1", model="UNVR")
        nvr.name = "Main"
        cam = MagicMock(id="c1", model="G5")
        cam.name = "Door"
        res = main_mod.protect_res
        with (
            patch.object(res, "list_nvrs", AsyncMock(return_value=[nvr])),
            patch.object(res, "get_nvr", AsyncMock(side_effect=[nvr, None])),
            patch.object(res, "list_cameras", AsyncMock(return_value=[cam])),
            patch.object(res, "get_camera", AsyncMock(side_effect=[cam, None])),
        ):
            assert await _fn(main_mod.get_protect_nvrs_resource)() == "NVR: Main (n1) - UNVR"
            assert await _fn(main_mod.get_protect_nvr_resource)("n1") == "NVR: Main (n1) - UNVR"
            assert await _fn(main_mod.get_protect_nvr_resource)("nx") == "NVR nx not found"
            assert await _fn(main_mod.get_protect_cameras_resource)() == "Camera: Door (c1) - G5"
            assert await _fn(main_mod.get_protect_camera_resource)("c1") == "Camera: Door (c1) - G5"
            assert await _fn(main_mod.get_protect_camera_resource)("cx") == "Camera cx not found"

    @pytest.mark.asyncio
    async def test_site_manager_resources(self, main_mod: ModuleType) -> None:
        res = main_mod.site_manager_res
        with (
            patch.object(res, "get_all_sites", AsyncMock(return_value="sites")),
            patch.object(res, "get_health_metrics", AsyncMock(return_value="health")),
            patch.object(res, "get_internet_health_status", AsyncMock(return_value="inet")),
        ):
            assert await _fn(main_mod.get_site_manager_sites_resource)() == "sites"
            assert await _fn(main_mod.get_site_manager_health_resource)() == "health"
            assert await _fn(main_mod.get_site_manager_internet_health_resource)() == "inet"


class TestAuditServerStart:
    @pytest.mark.asyncio
    async def test_disabled_writes_nothing(self, main_mod: ModuleType) -> None:
        with (
            patch.object(main_mod.settings, "audit_log_enabled", False),
            patch.object(main_mod, "get_tool_audit_logger") as get_logger,
        ):
            await main_mod.audit_server_start()
        get_logger.assert_not_called()

    @pytest.mark.asyncio
    async def test_records_safety_configuration(self, main_mod: ModuleType) -> None:
        audit = MagicMock()
        audit.alog_event = AsyncMock()
        with (
            patch.object(main_mod.settings, "audit_log_enabled", True),
            patch.object(main_mod, "get_tool_audit_logger", return_value=audit),
        ):
            await main_mod.audit_server_start()

        args, kwargs = audit.alog_event.await_args
        assert args == ("system", "server_start", "success")
        config = kwargs["config"]
        assert config["api_type"] == "local"
        assert config["transport"] == "stdio"
        assert config["audit_store"] == "jsonl"
        assert config["controller_registry"] == "EnvRegistry"
        assert config["tools_registered"] > 0


class TestLifespan:
    @pytest.mark.asyncio
    async def test_audits_start_and_closes_pool(self, main_mod: ModuleType) -> None:
        with (
            patch.object(main_mod, "audit_server_start", AsyncMock()) as start,
            patch.object(main_mod.client_pool, "aclose", AsyncMock()) as aclose,
        ):
            async with main_mod._lifespan(None):
                start.assert_awaited_once()
                aclose.assert_not_called()
        aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_siem_forwarder_starts_before_the_registry(self, main_mod: ModuleType) -> None:
        order: list[str] = []
        forwarder = MagicMock()
        forwarder.stop = AsyncMock(side_effect=lambda: order.append("forwarder.stop"))

        async def start_forwarder(_: object) -> MagicMock:
            order.append("forwarder.start")
            return forwarder

        async def registry_start() -> None:
            order.append("registry.start")  # may store registry_seeded
            raise RuntimeError("database down")

        registry = MagicMock()
        registry.start = registry_start
        # Imported here so the patch below does not depend on test order.
        pytest.importorskip("sqlalchemy")
        from src.fleet.db import audit_store

        with (
            patch.object(main_mod, "start_siem_forwarder", start_forwarder),
            patch.object(main_mod, "fleet_registry", registry),
            patch.object(audit_store, "install"),
            pytest.raises(RuntimeError, match="database down"),
        ):
            async with main_mod._lifespan(None):
                pass  # pragma: no cover - startup fails first
        assert order == ["forwarder.start", "registry.start", "forwarder.stop"]

    @pytest.mark.asyncio
    async def test_warns_about_registry_controllers_after_loading(
        self, main_mod: ModuleType
    ) -> None:
        order: list[str] = []
        registry = MagicMock()
        registry.start = AsyncMock(side_effect=lambda: order.append("registry.start"))
        registry.stop = AsyncMock()
        pytest.importorskip("sqlalchemy")
        from src.fleet.db import audit_store

        async def warn() -> None:
            order.append("warn")

        with (
            patch.object(main_mod, "fleet_registry", registry),
            patch.object(main_mod.fleet_router, "warn_insecure_controllers", warn),
            patch.object(main_mod, "audit_server_start", AsyncMock()),
            patch.object(main_mod.client_pool, "aclose", AsyncMock()),
            patch.object(audit_store, "install"),
        ):
            async with main_mod._lifespan(None):
                pass
        assert order == ["registry.start", "warn"]


class TestMainEntryPoint:
    def test_stdio(self, main_mod: ModuleType) -> None:
        with (
            patch.object(main_mod.mcp, "run") as run,
            patch.object(main_mod, "register_webhook_route") as webhook,
        ):
            main_mod.main()
        run.assert_called_once_with()
        webhook.assert_not_called()  # stdio serves no HTTP

    def test_streamable_http_adds_session_guard(self) -> None:
        mod = _reload_main(
            MCP_SERVER_TRANSPORT="streamable_http",
            MCP_AUTH_TOKEN="a-long-enough-test-token-value",  # pragma: allowlist secret
            UNIFI_METRICS_ENABLED="true",
            UNIFI_PROFILE="network",
        )
        with (
            patch.object(mod.mcp, "run") as run,
            patch.object(mod, "register_a2a_routes") as a2a,
            patch.object(mod, "register_metrics_route") as metrics,
            patch.object(mod, "register_health_route") as health,
            patch.object(mod, "register_webhook_route", return_value=None) as webhook,
        ):
            mod.main()

        a2a.assert_called_once()
        health.assert_called_once_with(mod.mcp)
        metrics.assert_called_once()
        webhook.assert_called_once_with(mod.mcp, mod.settings)
        kwargs = run.call_args.kwargs
        assert kwargs["transport"] == "streamable-http"
        assert [m.cls.__name__ for m in kwargs["middleware"]] == [
            "BearerFailureLimiter",
            "SessionlessRequestGuard",
        ]
        assert kwargs["middleware"][0].kwargs == {"max_failures": 10, "window_seconds": 60.0}

    def test_stateless_http_is_passed_to_streamable_http(self) -> None:
        mod = _reload_main(
            MCP_SERVER_TRANSPORT="streamable_http",
            MCP_AUTH_TOKEN="a-long-enough-test-token-value",  # pragma: allowlist secret
            MCP_STATELESS_HTTP="true",
        )
        with patch.object(mod.mcp, "run") as run, patch.object(mod, "register_a2a_routes"):
            mod.main()

        assert run.call_args.kwargs["stateless_http"] is True
        # The session guard would answer every sessionless call with 400.
        names = [m.cls.__name__ for m in run.call_args.kwargs["middleware"]]
        assert names == ["BearerFailureLimiter"]

    def test_stateful_by_default(self) -> None:
        mod = _reload_main(
            MCP_SERVER_TRANSPORT="streamable_http",
            MCP_AUTH_TOKEN="a-long-enough-test-token-value",  # pragma: allowlist secret
        )
        with patch.object(mod.mcp, "run") as run, patch.object(mod, "register_a2a_routes"):
            mod.main()

        assert "stateless_http" not in run.call_args.kwargs

    def test_sse_has_no_session_guard(self) -> None:
        mod = _reload_main(
            MCP_SERVER_TRANSPORT="sse",
            MCP_AUTH_TOKEN="a-long-enough-test-token-value",  # pragma: allowlist secret
        )
        with patch.object(mod.mcp, "run") as run, patch.object(mod, "register_a2a_routes"):
            mod.main()

        assert run.call_args.kwargs["transport"] == "sse"
        names = [m.cls.__name__ for m in run.call_args.kwargs["middleware"]]
        assert names == ["BearerFailureLimiter"]

    def test_bearer_failure_limit_configurable_and_can_be_disabled(self) -> None:
        mod = _reload_main(
            MCP_SERVER_TRANSPORT="sse",
            MCP_AUTH_TOKEN="a-long-enough-test-token-value",  # pragma: allowlist secret
            MCP_AUTH_MAX_FAILURES="0",
        )
        with patch.object(mod.mcp, "run") as run, patch.object(mod, "register_a2a_routes"):
            mod.main()
        assert "middleware" not in run.call_args.kwargs

        mod = _reload_main(
            MCP_SERVER_TRANSPORT="sse",
            MCP_AUTH_TOKEN="a-long-enough-test-token-value",  # pragma: allowlist secret
            MCP_AUTH_MAX_FAILURES="3",
            MCP_AUTH_FAILURE_WINDOW_SECONDS="300",
        )
        with patch.object(mod.mcp, "run") as run, patch.object(mod, "register_a2a_routes"):
            mod.main()
        assert run.call_args.kwargs["middleware"][0].kwargs == {
            "max_failures": 3,
            "window_seconds": 300.0,
        }


class TestImportTimeBranches:
    def test_unknown_profile_warns_and_registers_everything(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING"):
            mod = _reload_main(UNIFI_PROFILE="no-such-profile")
        assert "Unknown UNIFI_PROFILE='no-such-profile'" in caplog.text
        assert len(mod._TOOL_MODULES) == len(mod._CLOUD_TOOL_MODULES) + len(mod._LOCAL_TOOL_MODULES)

    @pytest.mark.asyncio
    async def test_debug_tool_absent_without_debug(self) -> None:
        mod = _reload_main()
        names = {tool.name for tool in await mod.mcp.list_tools()}
        assert "debug_api_request" not in names

    @pytest.mark.asyncio
    async def test_debug_tool_registered_destructive_under_debug(self) -> None:
        from src.tool_registry import TOOL_TIERS

        mod = _reload_main(DEBUG="true")
        names = {tool.name for tool in await mod.mcp.list_tools()}
        assert "debug_api_request" in names
        assert TOOL_TIERS["debug_api_request"] == "destructive"

    @pytest.mark.asyncio
    async def test_read_only_removes_debug_tool_even_under_debug(self) -> None:
        mod = _reload_main(DEBUG="true", UNIFI_READ_ONLY="true")
        names = {tool.name for tool in await mod.mcp.list_tools()}
        assert "debug_api_request" not in names
        assert not hasattr(mod, "debug_api_request")


class TestToolModuleSets:
    # Tool names defined in two modules before this guard existed. The module
    # registered first wins and the other copy is never reachable. Remove an
    # entry once its duplicate is gone; never add one.
    _KNOWN_DUPLICATES = {"list_countries", "list_radius_profiles"}

    _CLOUD_API_TOOLS = (
        "list_mobility_workspaces",
        "list_innerspace_access_points",
        "list_carrier_service_plans",
    )

    @pytest.mark.parametrize("api_type", ["cloud-v1", "cloud-ea", "local"])
    def test_cloud_api_modules_register_in_every_mode(self, api_type: str) -> None:
        from src.tool_registry import _get_registered_tool_names

        mod = _reload_main(UNIFI_API_TYPE=api_type)
        names = _get_registered_tool_names(mod.mcp)
        for tool in self._CLOUD_API_TOOLS:
            assert tool in names, f"{tool} not registered with UNIFI_API_TYPE={api_type}"

    def test_cloud_api_profiles_work_in_cloud_mode(self) -> None:
        from src.tool_registry import _get_registered_tool_names

        mod = _reload_main(UNIFI_API_TYPE="cloud-v1", UNIFI_PROFILE="mobility")
        assert mod._TOOL_MODULES == [mod.mobility_tools]
        assert "list_mobility_workspaces" in _get_registered_tool_names(mod.mcp)

    def test_no_tool_name_is_defined_in_two_modules(self, main_mod: ModuleType) -> None:
        import collections
        import inspect

        owners: dict[str, list[str]] = collections.defaultdict(list)
        modules = dict.fromkeys(main_mod._CLOUD_TOOL_MODULES + main_mod._LOCAL_TOOL_MODULES)
        for module in modules:
            for name, obj in inspect.getmembers(module, inspect.iscoroutinefunction):
                if not name.startswith("_") and obj.__module__ == module.__name__:
                    owners[name].append(module.__name__)
        duplicates = {name for name, mods in owners.items() if len(mods) > 1}
        assert duplicates - self._KNOWN_DUPLICATES == set(), {
            name: owners[name] for name in duplicates - self._KNOWN_DUPLICATES
        }
        assert "list_protect_device_updates" not in duplicates


def teardown_module() -> None:
    # Leave a default (local, stdio) src.main behind for later test modules.
    _reload_main()


class TestRelativeAuditPathWarning:
    @staticmethod
    def _settings(**fields: object) -> MagicMock:
        defaults = {"audit_log_enabled": True, "database_url": None, "audit_log_file": None}
        return MagicMock(**{**defaults, **fields})

    @pytest.mark.parametrize("path", [None, "audit.log", "logs/audit.log"])
    def test_relative_path_warns_with_resolved_location(
        self, main_mod: ModuleType, caplog: pytest.LogCaptureFixture, path: str | None
    ) -> None:
        with caplog.at_level("WARNING"):
            main_mod.warn_relative_audit_path(self._settings(audit_log_file=path))
        expected = Path(path or "audit.log").absolute()
        assert f"writing to {expected}" in caplog.text
        assert "UNIFI_AUDIT_LOG_PATH" in caplog.text

    @pytest.mark.parametrize(
        "fields",
        [
            {"audit_log_file": "/var/log/unifi-mcp/audit.log"},
            {"audit_log_enabled": False},
            {"database_url": "postgresql://registry"},
        ],
    )
    def test_no_warning(
        self, main_mod: ModuleType, caplog: pytest.LogCaptureFixture, fields: dict
    ) -> None:
        with caplog.at_level("WARNING"):
            main_mod.warn_relative_audit_path(self._settings(**fields))
        assert "UNIFI_AUDIT_LOG_PATH" not in caplog.text
