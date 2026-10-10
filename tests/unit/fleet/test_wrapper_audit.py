"""Wrapper-level audit records (docs/FLEET_SCALING_PLAN.md §3.7, Phase 1)."""

import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastmcp.server.auth import AccessToken

from src.config.config import APIType, Settings
from src.fleet import ControllerProfile
from src.fleet.router import FleetRouter
from src.tool_registry import _make_tool_wrapper
from src.tools.wifi import delete_wlan
from src.utils.audit import AuditUnavailableError, get_audit_logger
from src.utils.audit_verify import verify_file
from src.utils.exceptions import ValidationError

from .test_router import StaticRegistry


@pytest.fixture(autouse=True)
def _fresh_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.utils.audit._audit_logger", None)
    for name in ("UNIFI_AUDIT_CHAIN_KEY", "UNIFI_AUDIT_LOG_KEY", "UNIFI_AUDIT_ENCRYPTION_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "audit.log"


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, log_path: Path) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "base-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(log_path))
    return Settings()


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


async def read_tool(site_id: str, settings: Any = None) -> dict:
    """A read: never audited."""
    return {}


async def write_tool(
    site_id: str, passphrase: str = "", confirm: bool = False, settings: Any = None
) -> dict:
    """A mutating tool."""
    return {"ok": True}


async def failing_tool(site_id: str, confirm: bool = False, settings: Any = None) -> dict:
    """A mutating tool that fails."""
    raise RuntimeError("controller said no")


class TestWhatIsRecorded:
    async def test_reads_are_not_audited(self, settings, log_path):
        await _make_tool_wrapper(read_tool, settings)("default")

        assert _records(log_path) == []

    async def test_write_records_attempt_and_outcome(self, settings, log_path):
        await _make_tool_wrapper(write_tool, settings)(
            "default", passphrase="hunter2", confirm=True  # pragma: allowlist secret
        )

        attempt, outcome = _records(log_path)
        assert (attempt["result"], outcome["result"]) == ("attempt", "success")
        assert attempt["call_id"] == outcome["call_id"]
        for record in (attempt, outcome):
            assert record["v"] == 2
            assert record["event_type"] == "tool_call"
            assert record["operation"] == record["tool"] == "write_tool"
            assert record["tier"] == "write"
            assert record["controller"] == "default"
            assert record["site_id"] == "default"
            assert record["principal"] == {
                "id": "local",
                "name": "stdio",
                "role": "fleet-admin",
                "break_glass": True,
            }
            assert record["parameters"]["passphrase"] != "hunter2"  # pragma: allowlist secret
        assert outcome["duration_ms"] >= 0

    async def test_tool_error_is_recorded_and_raised(self, settings, log_path):
        with pytest.raises(RuntimeError, match="controller said no"):
            await _make_tool_wrapper(failing_tool, settings)("default", confirm=True)

        _, outcome = _records(log_path)
        assert outcome["result"] == "error"
        assert outcome["error"] == "controller said no"

    async def test_audit_disabled_records_nothing(self, monkeypatch, log_path):
        monkeypatch.setenv("UNIFI_API_KEY", "k")  # pragma: allowlist secret
        monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(log_path))
        monkeypatch.setenv("UNIFI_AUDIT_LOG_ENABLED", "false")

        await _make_tool_wrapper(write_tool, Settings())("default", confirm=True)

        assert _records(log_path) == []

    async def test_env_token_caller_is_recorded(self, settings, log_path, monkeypatch):
        token = AccessToken(token="t0ken", client_id="mcp-client", scopes=[])  # noqa: S106
        monkeypatch.setattr("src.access.get_access_token", lambda: token)

        await _make_tool_wrapper(write_tool, settings)("default", confirm=True)

        principal = _records(log_path)[0]["principal"]
        assert principal["id"].startswith("env:")
        assert principal["break_glass"] is True
        assert "t0ken" not in log_path.read_text()

    async def test_records_form_a_verifiable_chain(self, settings, log_path):
        wrapped = _make_tool_wrapper(write_tool, settings)
        for _ in range(3):
            await wrapped("default", confirm=True)

        assert verify_file(log_path, None).ok


class TestRealToolWithManualAudit:
    """delete_wlan calls log_audit itself; the call must still yield one record pair."""

    async def test_manual_record_is_folded_into_the_outcome(self, settings, log_path):
        result = await _make_tool_wrapper(delete_wlan, settings)(
            "default", "wlan-1", confirm=True, dry_run=True
        )

        assert result == {"dry_run": True, "would_delete": "wlan-1"}
        records = _records(log_path)
        assert [r["result"] for r in records] == ["attempt", "dry_run"]
        assert records[1]["tier"] == "destructive"
        (detail,) = records[1]["details"]
        assert detail["operation"] == "delete_wlan"
        assert detail["result"] == "dry_run"

    async def test_details_are_encrypted_with_a_payload_key(self, settings, log_path, monkeypatch):
        monkeypatch.setenv("UNIFI_AUDIT_LOG_KEY", Fernet.generate_key().decode())

        await _make_tool_wrapper(delete_wlan, settings)(
            "default", "wlan-1", confirm=True, dry_run=True
        )

        outcome = _records(log_path)[1]
        assert outcome["details_encrypted"] is True
        assert "wlan-1" not in log_path.read_text()
        (decrypted,) = get_audit_logger().get_recent_operations(limit=1)
        assert decrypted["details"][0]["operation"] == "delete_wlan"


class TestDeniedAndFailClosed:
    @pytest.fixture
    def router(self, settings: Settings) -> FleetRouter:
        def profile(name: str, host: str) -> ControllerProfile:
            return ControllerProfile(
                name=name,
                api_type=APIType.LOCAL,
                api_key=f"{name}-key",  # pragma: allowlist secret
                local_host=host,
            )

        registry = StaticRegistry(
            profile("hq", "10.0.0.1"), profile("branch", "10.0.1.1"), default="hq"
        )
        return FleetRouter(settings, registry)

    async def test_refused_write_target_is_recorded_as_denied(self, settings, router, log_path):
        calls: list[str] = []

        async def guarded(site_id: str, confirm: bool = False, settings: Any = None) -> None:
            calls.append(site_id)

        with pytest.raises(ValidationError):
            await _make_tool_wrapper(guarded, settings, router)("default", confirm=True)

        (denied,) = _records(log_path)
        assert denied["event_type"] == "denied"
        assert denied["result"] == "denied"
        assert "controller" in denied["error"]
        assert calls == []

    async def test_unknown_controller_on_a_write_is_denied(self, settings, router, log_path):
        with pytest.raises(Exception, match="not found"):
            await _make_tool_wrapper(write_tool, settings, router)(
                "default", confirm=True, controller="nope"
            )

        (denied,) = _records(log_path)
        assert denied["controller"] == "nope"

    async def test_unwritable_audit_log_blocks_writes(self, monkeypatch, tmp_path):
        blocked = tmp_path / "is-a-directory"
        blocked.mkdir()
        monkeypatch.setenv("UNIFI_API_KEY", "k")  # pragma: allowlist secret
        monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(blocked))
        calls: list[str] = []

        async def guarded(site_id: str, confirm: bool = False, settings: Any = None) -> None:
            calls.append(site_id)

        with pytest.raises(AuditUnavailableError):
            await _make_tool_wrapper(guarded, Settings())("default", confirm=True)
        assert calls == []

    async def test_reads_still_work_with_unwritable_audit_log(self, monkeypatch, tmp_path):
        blocked = tmp_path / "is-a-directory"
        blocked.mkdir()
        monkeypatch.setenv("UNIFI_API_KEY", "k")  # pragma: allowlist secret
        monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(blocked))

        assert await _make_tool_wrapper(read_tool, Settings())("default") == {}

    async def test_fail_open_lets_writes_through(self, monkeypatch, tmp_path):
        blocked = tmp_path / "is-a-directory"
        blocked.mkdir()
        monkeypatch.setenv("UNIFI_API_KEY", "k")  # pragma: allowlist secret
        monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(blocked))
        monkeypatch.setenv("UNIFI_AUDIT_FAIL_CLOSED", "false")

        result = await _make_tool_wrapper(write_tool, Settings())("default", confirm=True)

        assert result == {"ok": True}
