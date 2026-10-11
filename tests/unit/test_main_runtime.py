"""Runtime paths of src/main.py: resource handlers, the debug tool, the
lifespan, the start-up audit record, and main()'s transport branches.

``src.main`` builds its server at import time from the environment, so each
test reloads it with the environment it needs. ``mcp.run`` is always patched:
nothing here opens a socket or talks to a controller.
"""

from __future__ import annotations

import importlib
import sys
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
            patch.object(mod, "register_webhook_route", return_value=None) as webhook,
        ):
            mod.main()

        a2a.assert_called_once()
        metrics.assert_called_once()
        webhook.assert_called_once_with(mod.mcp, mod.settings)
        kwargs = run.call_args.kwargs
        assert kwargs["transport"] == "streamable-http"
        assert [m.cls.__name__ for m in kwargs["middleware"]] == ["SessionlessRequestGuard"]

    def test_sse_has_no_session_guard(self) -> None:
        mod = _reload_main(
            MCP_SERVER_TRANSPORT="sse",
            MCP_AUTH_TOKEN="a-long-enough-test-token-value",  # pragma: allowlist secret
        )
        with patch.object(mod.mcp, "run") as run, patch.object(mod, "register_a2a_routes"):
            mod.main()

        assert run.call_args.kwargs["transport"] == "sse"
        assert "middleware" not in run.call_args.kwargs


class TestImportTimeBranches:
    def test_unknown_profile_warns_and_registers_everything(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING"):
            mod = _reload_main(UNIFI_PROFILE="no-such-profile")
        assert "Unknown UNIFI_PROFILE='no-such-profile'" in caplog.text
        assert len(mod._TOOL_MODULES) == len(mod._CLOUD_TOOL_MODULES) + len(mod._LOCAL_TOOL_MODULES)

    @pytest.mark.asyncio
    async def test_debug_tool(self) -> None:
        mod = _reload_main(DEBUG="true")
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.return_value = {"ok": 1}
        client.delete.return_value = {"deleted": 1}
        debug = _fn(mod.debug_api_request)
        with patch("src.api.UniFiClient", return_value=client):
            assert await debug("/x") == {"ok": 1}
            assert await debug("/x", method="delete") == {"deleted": 1}
            result = await debug("/x", method="POST")
        assert "not implemented" in result["error"]


def teardown_module() -> None:
    # Leave a default (local, stdio) src.main behind for later test modules.
    _reload_main()
