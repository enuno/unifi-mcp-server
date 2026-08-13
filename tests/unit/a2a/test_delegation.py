"""Unit tests for src/a2a/delegation.py."""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from typing import Any

import pytest

from src.a2a import delegation
from src.a2a.delegation import (
    _active_mcp,
    _auth_mode_for_settings,
    _is_destructive_tool_name,
    _now_iso,
    _run_sync,
    create_delegation_contract,
    execute_delegated_call,
    validate_delegation,
)
from src.a2a.types import AuthenticationMode, DelegationContract, SafetyRequirement
from src.config.config import Settings

from .conftest import FakeMCP, delete_site_device, list_site_clients, make_tool


def build_contract(**overrides: Any) -> DelegationContract:
    """Create a valid contract, overriding individual fields as needed."""
    defaults: dict[str, Any] = {
        "contractId": "contract-1",
        "toolName": "list_site_clients",
        "params": {"site_id": "default"},
        "requestingAgent": "agent-a",
        "authenticationMode": AuthenticationMode.BOTH,
        "createdAt": "2026-01-01T00:00:00+00:00",
        "requiresConfirmation": False,
    }
    defaults.update(overrides)
    return DelegationContract(**defaults)


class TestNowIso:
    """Tests for _now_iso."""

    def test_returns_a_utc_iso_timestamp(self) -> None:
        stamp = _now_iso()

        assert stamp.endswith("+00:00")
        assert "T" in stamp


class TestRunSync:
    """Tests for _run_sync."""

    def test_runs_a_coroutine_outside_an_event_loop(self) -> None:
        async def answer() -> int:
            return 42

        assert _run_sync(answer()) == 42

    def test_rejects_being_called_inside_a_running_loop(self) -> None:
        async def answer() -> int:
            return 42

        async def caller() -> None:
            coro = answer()
            try:
                with pytest.raises(RuntimeError, match="inside a running event loop"):
                    _run_sync(coro)
            finally:
                coro.close()

        asyncio.run(caller())

    def test_delegates_to_an_existing_idle_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def answer() -> int:
            return 42

        loop = asyncio.new_event_loop()
        monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)
        try:
            assert _run_sync(answer()) == 42
        finally:
            loop.close()


class Marker:
    """Stands in for FastMCP so sys.modules scanning has exactly one match."""


class TestActiveMcp:
    """Tests for _active_mcp."""

    @pytest.fixture(autouse=True)
    def only_marker_counts_as_a_server(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Narrow the isinstance check so unrelated imports cannot match.

        src/main.py holds a module-level FastMCP, so scanning the real
        sys.modules would otherwise make these tests depend on import order.
        """
        monkeypatch.setattr(delegation, "FastMCP", Marker)

    def test_returns_none_when_no_module_exposes_a_server(self) -> None:
        assert _active_mcp() is None

    def test_skips_none_entries_in_sys_modules(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "tests_a2a_stale_module", None)

        assert _active_mcp() is None

    def test_finds_a_module_level_server_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        server = Marker()
        holder = ModuleType("tests_a2a_holder")
        holder.mcp = server
        monkeypatch.setitem(sys.modules, "tests_a2a_holder", holder)

        assert _active_mcp() is server

    def test_ignores_attributes_named_mcp_that_are_not_servers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        decoy = ModuleType("tests_a2a_decoy")
        decoy.mcp = "not-a-server"
        monkeypatch.setitem(sys.modules, "tests_a2a_decoy", decoy)

        assert _active_mcp() is None


class TestAuthModeForSettings:
    """Tests for _auth_mode_for_settings."""

    def test_always_reports_both(self, local_settings: Settings) -> None:
        assert _auth_mode_for_settings(local_settings) is AuthenticationMode.BOTH


class TestIsDestructiveToolName:
    """Tests for _is_destructive_tool_name."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "delete_site_device",
            "remove_client",
            "reset_controller",
            "restore_backup",
            "reboot_device",
            "restart_service",
            "disable_wlan",
            "flush_dns",
            "purge_logs",
            "provision_device",
            "deprovision_device",
            "DELETE_SITE_DEVICE",
        ],
    )
    def test_detects_destructive_names(self, tool_name: str) -> None:
        assert _is_destructive_tool_name(tool_name) is True

    @pytest.mark.parametrize("tool_name", ["list_site_clients", "get_device", "search_events"])
    def test_treats_read_only_names_as_safe(self, tool_name: str) -> None:
        assert _is_destructive_tool_name(tool_name) is False


class TestCreateDelegationContract:
    """Tests for create_delegation_contract."""

    def test_rejects_params_that_are_not_json_serializable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(delegation, "_active_mcp", lambda: None)

        with pytest.raises(TypeError):
            create_delegation_contract("list_site_clients", {"when": object()}, "agent-a")

    def test_falls_back_to_the_name_heuristic_without_an_active_server(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(delegation, "_active_mcp", lambda: None)

        contract = create_delegation_contract("delete_site_device", {"site_id": "s"}, "agent-a")

        assert contract.requiresConfirmation is True
        assert contract.safetyRequirement is None
        assert contract.toolName == "delete_site_device"
        assert contract.requestingAgent == "agent-a"
        assert contract.dryRun is False
        assert contract.metadata == {"source": "a2a.delegation"}
        assert contract.authenticationMode is AuthenticationMode.BOTH
        assert contract.contractId

    def test_generates_a_unique_id_per_contract(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(delegation, "_active_mcp", lambda: None)

        first = create_delegation_contract("list_site_clients", {}, "agent-a")
        second = create_delegation_contract("list_site_clients", {}, "agent-a")

        assert first.contractId != second.contractId

    def test_reads_safety_metadata_from_the_registered_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mcp = FakeMCP({"delete_site_device": make_tool(delete_site_device)})
        monkeypatch.setattr(delegation, "_active_mcp", lambda: mcp)

        contract = create_delegation_contract("delete_site_device", {"site_id": "s"}, "agent-a")

        assert contract.safetyRequirement is not None
        assert contract.safetyRequirement.destructive is True
        assert contract.requiresConfirmation is True

    def test_read_only_registered_tools_do_not_require_confirmation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mcp = FakeMCP({"list_site_clients": make_tool(list_site_clients)})
        monkeypatch.setattr(delegation, "_active_mcp", lambda: mcp)

        contract = create_delegation_contract("list_site_clients", {"site_id": "s"}, "agent-a")

        assert contract.requiresConfirmation is False

    def test_ignores_providers_without_a_component_mapping(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mcp = FakeMCP({"delete_site_device": make_tool(delete_site_device)})
        mcp.providers.insert(0, type("Bare", (), {"_components": "not-a-dict"})())
        monkeypatch.setattr(delegation, "_active_mcp", lambda: mcp)

        contract = create_delegation_contract("delete_site_device", {"site_id": "s"}, "agent-a")

        assert contract.safetyRequirement is not None

    def test_unregistered_tool_names_fall_back_to_the_heuristic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mcp = FakeMCP({"list_site_clients": make_tool(list_site_clients)})
        monkeypatch.setattr(delegation, "_active_mcp", lambda: mcp)

        contract = create_delegation_contract("purge_logs", {}, "agent-a")

        assert contract.safetyRequirement is None
        assert contract.requiresConfirmation is True


class TestValidateDelegation:
    """Tests for validate_delegation."""

    def test_accepts_a_well_formed_read_only_contract(self) -> None:
        assert validate_delegation(build_contract()) is True

    @pytest.mark.parametrize("field", ["contractId", "toolName", "requestingAgent"])
    def test_rejects_missing_identity_fields(self, field: str) -> None:
        assert validate_delegation(build_contract(**{field: ""})) is False

    def test_rejects_params_that_are_not_a_mapping(self) -> None:
        assert validate_delegation(build_contract(params=["site_id"])) is False

    def test_rejects_confirmation_contracts_without_safety_metadata(self) -> None:
        contract = build_contract(requiresConfirmation=True, params={"confirm": True})

        assert validate_delegation(contract) is False

    def test_rejects_confirmation_contracts_without_an_explicit_confirm_flag(self) -> None:
        contract = build_contract(
            requiresConfirmation=True,
            safetyRequirement=SafetyRequirement("required", True, []),
            params={},
        )

        assert validate_delegation(contract) is False

    def test_accepts_a_confirmed_destructive_contract(self) -> None:
        contract = build_contract(
            requiresConfirmation=True,
            safetyRequirement=SafetyRequirement("required", True, []),
            params={"confirm": True},
        )

        assert validate_delegation(contract) is True


class TestExecuteDelegatedCall:
    """Tests for execute_delegated_call."""

    def test_rejects_an_invalid_contract(self, local_settings: Settings) -> None:
        with pytest.raises(ValueError, match="Invalid delegation contract"):
            execute_delegated_call(build_contract(contractId=""), local_settings)

    def test_requires_an_active_server(
        self, monkeypatch: pytest.MonkeyPatch, local_settings: Settings
    ) -> None:
        monkeypatch.setattr(delegation, "_active_mcp", lambda: None)

        with pytest.raises(RuntimeError, match="No active FastMCP instance"):
            execute_delegated_call(build_contract(), local_settings)

    def test_invokes_the_named_tool_with_the_contract_params(
        self, monkeypatch: pytest.MonkeyPatch, local_settings: Settings
    ) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        class RecordingMCP:
            async def call_tool(self, name: str, params: dict[str, Any]) -> str:
                calls.append((name, params))
                return "tool-result"

        monkeypatch.setattr(delegation, "_active_mcp", lambda: RecordingMCP())

        result = execute_delegated_call(build_contract(), local_settings)

        assert result == "tool-result"
        assert calls == [("list_site_clients", {"site_id": "default"})]

    def test_confirmed_destructive_contracts_are_executed(
        self, monkeypatch: pytest.MonkeyPatch, local_settings: Settings
    ) -> None:
        class RecordingMCP:
            async def call_tool(self, name: str, params: dict[str, Any]) -> str:
                return "deleted"

        monkeypatch.setattr(delegation, "_active_mcp", lambda: RecordingMCP())
        contract = build_contract(
            toolName="delete_site_device",
            requiresConfirmation=True,
            safetyRequirement=SafetyRequirement("required", True, []),
            params={"confirm": True},
        )

        assert execute_delegated_call(contract, local_settings) == "deleted"
