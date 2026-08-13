"""Unit tests for src/a2a/audit.py."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from src.a2a import audit as audit_module
from src.a2a.audit import AuditLog, AuditLogger, get_audit_logger


def make_entry(
    agent_id: str = "agent-a",
    tool_name: str = "list_site_clients",
    minutes: int = 0,
    **overrides: Any,
) -> AuditLog:
    """Build an audit entry offset from a fixed base timestamp."""
    defaults: dict[str, Any] = {
        "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes),
        "agent_id": agent_id,
        "tool_name": tool_name,
        "params": {"site_id": "default"},
        "result": {"ok": True},
        "safety_level": "none",
        "duration_ms": 12.5,
    }
    defaults.update(overrides)
    return AuditLog(**defaults)


@pytest.fixture
def logger(tmp_path: Path) -> AuditLogger:
    """Return an audit logger writing to an isolated temp file."""
    return AuditLogger(log_file=tmp_path / "audit" / "trail.jsonl")


class TestAuditLoggerInit:
    """Tests for AuditLogger construction."""

    def test_creates_the_parent_directory_for_the_log_file(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "deeper" / "trail.jsonl"

        AuditLogger(log_file=target)

        assert target.parent.is_dir()

    def test_defaults_to_a_logs_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        instance = AuditLogger()

        assert instance.log_file == Path("logs") / "a2a-audit.jsonl"

    def test_accepts_a_string_path(self, tmp_path: Path) -> None:
        instance = AuditLogger(log_file=str(tmp_path / "trail.jsonl"))

        assert instance.log_file == tmp_path / "trail.jsonl"

    def test_starts_with_an_empty_trail(self, logger: AuditLogger) -> None:
        assert logger.get_audit_trail() == []


class TestSerialize:
    """Tests for the AuditLogger._serialize JSON fallback."""

    def test_datetimes_become_iso_strings(self) -> None:
        moment = datetime(2026, 1, 1, tzinfo=timezone.utc)

        assert AuditLogger._serialize(moment) == moment.isoformat()

    def test_paths_become_strings(self) -> None:
        assert AuditLogger._serialize(Path("a") / "b") == str(Path("a") / "b")

    def test_sets_become_sorted_lists(self) -> None:
        assert AuditLogger._serialize({"b", "a"}) == ["a", "b"]

    def test_objects_with_model_dump_are_unwrapped(self) -> None:
        class Model:
            def model_dump(self) -> dict[str, int]:
                return {"value": 1}

        assert AuditLogger._serialize(Model()) == {"value": 1}

    def test_plain_objects_fall_back_to_their_dict(self) -> None:
        class Plain:
            def __init__(self) -> None:
                self.value = 1

        assert AuditLogger._serialize(Plain()) == {"value": 1}

    def test_classes_are_returned_untouched(self) -> None:
        class Plain:
            pass

        assert AuditLogger._serialize(Plain) is Plain

    def test_primitives_are_returned_untouched(self) -> None:
        assert AuditLogger._serialize(7) == 7


class TestLogInvocation:
    """Tests for AuditLogger.log_invocation."""

    def test_appends_the_entry_to_the_in_memory_trail(self, logger: AuditLogger) -> None:
        entry = make_entry()

        logger.log_invocation(entry)

        assert logger.get_audit_trail() == [entry]

    def test_writes_one_json_line_per_call(self, logger: AuditLogger) -> None:
        logger.log_invocation(make_entry())
        logger.log_invocation(make_entry(agent_id="agent-b", minutes=1))

        lines = logger.log_file.read_text(encoding="utf-8").strip().splitlines()

        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["agent_id"] == "agent-a"
        assert first["timestamp"] == "2026-01-01T00:00:00+00:00"
        assert json.loads(lines[1])["agent_id"] == "agent-b"

    def test_non_serializable_results_use_the_fallback_encoder(self, logger: AuditLogger) -> None:
        class Model:
            def model_dump(self) -> dict[str, str]:
                return {"kind": "model"}

        logger.log_invocation(make_entry(result=Model()))

        row = json.loads(logger.log_file.read_text(encoding="utf-8").strip())
        assert row["result"] == {"kind": "model"}

    def test_write_failures_are_logged_and_do_not_propagate(
        self, logger: AuditLogger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        errors: list[str] = []

        def explode(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(Path, "open", explode)
        monkeypatch.setattr(logger.logger, "error", lambda msg, **kw: errors.append(msg))

        logger.log_invocation(make_entry())

        assert errors == ["Failed to write A2A audit log"]
        assert len(logger.get_audit_trail()) == 1


class TestGetAuditTrail:
    """Tests for AuditLogger.get_audit_trail filtering."""

    @pytest.fixture
    def populated(self, logger: AuditLogger) -> AuditLogger:
        logger.log_invocation(make_entry(agent_id="agent-a", tool_name="list_sites", minutes=0))
        logger.log_invocation(make_entry(agent_id="agent-b", tool_name="list_sites", minutes=10))
        logger.log_invocation(make_entry(agent_id="agent-a", tool_name="delete_site", minutes=20))
        return logger

    def test_returns_every_entry_with_no_filter(self, populated: AuditLogger) -> None:
        assert len(populated.get_audit_trail()) == 3

    def test_filters_by_agent(self, populated: AuditLogger) -> None:
        entries = populated.get_audit_trail(agent_id="agent-a")

        assert [entry.tool_name for entry in entries] == ["list_sites", "delete_site"]

    def test_filters_by_tool(self, populated: AuditLogger) -> None:
        entries = populated.get_audit_trail(tool_name="list_sites")

        assert [entry.agent_id for entry in entries] == ["agent-a", "agent-b"]

    def test_filters_by_start_time(self, populated: AuditLogger) -> None:
        entries = populated.get_audit_trail(start=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc))

        assert len(entries) == 2

    def test_filters_by_end_time(self, populated: AuditLogger) -> None:
        entries = populated.get_audit_trail(end=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc))

        assert len(entries) == 1

    def test_accepts_iso_strings_for_the_time_range(self, populated: AuditLogger) -> None:
        entries = populated.get_audit_trail(
            start="2026-01-01T00:05:00Z", end="2026-01-01T00:15:00Z"
        )

        assert [entry.agent_id for entry in entries] == ["agent-b"]

    def test_combines_filters(self, populated: AuditLogger) -> None:
        entries = populated.get_audit_trail(agent_id="agent-a", tool_name="delete_site")

        assert len(entries) == 1


class TestCoerceDatetime:
    """Tests for AuditLogger._coerce_datetime."""

    def test_none_passes_through(self) -> None:
        assert AuditLogger._coerce_datetime(None) is None

    def test_aware_datetimes_are_unchanged(self) -> None:
        moment = datetime(2026, 1, 1, tzinfo=timezone.utc)

        assert AuditLogger._coerce_datetime(moment) is moment

    def test_naive_datetimes_are_assumed_utc(self) -> None:
        assert AuditLogger._coerce_datetime(datetime(2026, 1, 1)).tzinfo is timezone.utc

    def test_iso_strings_with_a_z_suffix_are_parsed(self) -> None:
        parsed = AuditLogger._coerce_datetime("2026-01-01T00:00:00Z")

        assert parsed == datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestExportAuditLog:
    """Tests for AuditLogger.export_audit_log."""

    def test_json_export_is_a_parsable_array(self, logger: AuditLogger) -> None:
        logger.log_invocation(make_entry())

        payload = json.loads(logger.export_audit_log())

        assert len(payload) == 1
        assert payload[0]["timestamp"] == "2026-01-01T00:00:00+00:00"

    def test_jsonl_export_has_one_row_per_entry(self, logger: AuditLogger) -> None:
        logger.log_invocation(make_entry())
        logger.log_invocation(make_entry(agent_id="agent-b", minutes=1))

        lines = logger.export_audit_log("jsonl").splitlines()

        assert [json.loads(line)["agent_id"] for line in lines] == ["agent-a", "agent-b"]

    def test_format_is_case_insensitive(self, logger: AuditLogger) -> None:
        logger.log_invocation(make_entry())

        assert json.loads(logger.export_audit_log("JSON"))
        assert logger.export_audit_log("JSONL")

    def test_empty_trail_exports_cleanly(self, logger: AuditLogger) -> None:
        assert logger.export_audit_log() == "[]"
        assert logger.export_audit_log("jsonl") == ""

    def test_unsupported_formats_raise(self, logger: AuditLogger) -> None:
        with pytest.raises(ValueError, match="Unsupported export format"):
            logger.export_audit_log("csv")


class TestGetAuditLogger:
    """Tests for the module-level get_audit_logger singleton."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(audit_module, "_audit_logger", None)

    def test_returns_the_same_instance_on_repeat_calls(self, tmp_path: Path) -> None:
        first = get_audit_logger(log_file=tmp_path / "trail.jsonl")
        second = get_audit_logger(log_file=tmp_path / "other.jsonl")

        assert first is second
        assert second.log_file == tmp_path / "trail.jsonl"
