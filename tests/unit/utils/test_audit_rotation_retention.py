"""JSONL audit rotation and retention (docs/FLEET_SCALING_PLAN.md §3.7, Phase 5c)."""

from __future__ import annotations

import gzip
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from src.utils import audit as audit_module
from src.utils import audit_retention, audit_verify
from src.utils.audit import AuditLogger, audit_files, resolve_rotate_bytes
from src.utils.audit_archive import RetentionRefusedError
from src.utils.audit_retention import checkpoints_path, purge_expired_files, read_checkpoints

verify_cli = audit_verify.main
retention_cli = audit_retention.main

KEY = b"rotation-chain-key"  # pragma: allowlist secret
NOW = datetime.now(timezone.utc)
OLD = NOW - timedelta(days=400)


def _logger(log: Path, rotate_bytes: int | None = 600) -> AuditLogger:
    logger = AuditLogger(log)
    logger.chain_key = KEY
    logger.rotate_bytes = rotate_bytes
    return logger


def _write(
    logger: AuditLogger, count: int, when: datetime, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as m:
        m.setattr(audit_module, "get_iso_timestamp", lambda: when.isoformat())
        for n in range(count):
            logger.log_event("tool_call", f"op_{n}", "success", parameters={"n": n})


def _age(paths: list[Path], when: datetime) -> None:
    for path in paths:
        os.utime(path, (when.timestamp(), when.timestamp()))


def _old_then_new(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, AuditLogger]:
    """Rotated files of 400-day-old records, then a current file of new ones."""
    log = tmp_path / "audit.log"
    logger = _logger(log)
    _write(logger, 8, OLD, monkeypatch)
    _age(audit_files(log), OLD)
    _write(logger, 3, NOW, monkeypatch)
    return log, logger


def _purge(log: Path, tmp_path: Path, **kwargs: Any) -> Any:
    options: dict[str, Any] = {
        "retention_days": 30,
        "archive_dir": tmp_path / "archive",
        "dry_run": False,
    }
    options.update(kwargs)
    return purge_expired_files(log, KEY, **options)


class TestRotation:
    def test_rotate_setting(self) -> None:
        assert resolve_rotate_bytes({}) is None
        assert resolve_rotate_bytes({"UNIFI_AUDIT_LOG_ROTATE_MB": " "}) is None
        assert resolve_rotate_bytes({"UNIFI_AUDIT_LOG_ROTATE_MB": "2"}) == 2 * 1024 * 1024
        for bad in ("0", "x", "-1"):
            with pytest.raises(ValueError, match="UNIFI_AUDIT_LOG_ROTATE_MB"):
                resolve_rotate_bytes({"UNIFI_AUDIT_LOG_ROTATE_MB": bad})

    def test_logger_reads_the_setting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UNIFI_AUDIT_LOG_ROTATE_MB", "3")
        assert AuditLogger(tmp_path / "a.log").rotate_bytes == 3 * 1024 * 1024

    def test_the_chain_continues_across_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log = tmp_path / "audit.log"
        _write(_logger(log), 10, NOW, monkeypatch)

        files = audit_files(log)  # the 10th record filled the file, so it was rotated too
        assert len(files) >= 3 and log not in files
        assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in files)
        assert [p.name for p in files] == sorted(p.name for p in files)
        report = audit_verify.verify_files(files, KEY)
        assert report.ok and report.records == 10 and report.chains == 1
        # each rotated file alone is only part of the chain
        assert not audit_verify.verify_file(files[1], KEY).ok

    def test_recent_operations_read_rotated_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log = tmp_path / "audit.log"
        logger = _logger(log)
        _write(logger, 10, NOW, monkeypatch)
        recent = logger.get_recent_operations(limit=8)
        assert [e["operation"] for e in recent] == [f"op_{n}" for n in range(9, 1, -1)]

    def test_a_failed_rename_keeps_writing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: Any
    ) -> None:
        log = tmp_path / "audit.log"
        logger = _logger(log, rotate_bytes=1)

        def refuse(self: Path, target: Path) -> None:
            raise OSError("read-only directory")

        with monkeypatch.context() as m:
            m.setattr(Path, "rename", refuse)
            logger.log_event("tool_call", "op", "success")
            logger.log_event("tool_call", "op", "success")
        assert audit_files(log) == [log]
        assert audit_verify.verify_file(log, KEY).records == 2
        assert "Failed to rotate" in caplog.text

    def test_rotated_names_never_collide(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class Frozen(datetime):
            @classmethod
            def now(cls, tz: Any = None) -> datetime:
                return datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)

        monkeypatch.setattr(audit_module, "datetime", Frozen)
        log = tmp_path / "audit.log"
        logger = _logger(log, rotate_bytes=1)
        for _ in range(3):
            logger.log_event("tool_call", "op", "success")
        names = [p.name for p in audit_files(log)]
        assert names == [
            "audit.log.20261011T120000000000Z",
            "audit.log.20261011T120000000000Z-1",
            "audit.log.20261011T120000000000Z-2",
        ]


class TestRetention:
    def test_dry_run_changes_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log, _ = _old_then_new(tmp_path, monkeypatch)
        before = audit_files(log)
        result = _purge(log, tmp_path, dry_run=True)

        assert result.records == 8 and result.files
        assert audit_files(log) == before
        assert not (tmp_path / "archive").exists()
        assert not checkpoints_path(log).exists()

    def test_archives_then_deletes_expired_rotated_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        log, logger = _old_then_new(tmp_path, monkeypatch)
        old_files = [
            p for p in audit_files(log) if p != log and p.stat().st_mtime < NOW.timestamp() - 86400
        ]
        result = _purge(log, tmp_path)

        assert result.records == 8
        assert result.files == [p.name for p in old_files]
        assert not any(p.exists() for p in old_files)
        assert log.exists()
        archive, manifest = result.archive, result.manifest
        assert stat.S_IMODE(archive.stat().st_mode) == 0o600
        with gzip.open(archive, "rt", encoding="utf-8") as f:
            assert [json.loads(line)["operation"] for line in f] == [f"op_{n}" for n in range(8)]
        checkpoints = checkpoints_path(log)
        assert stat.S_IMODE(checkpoints.stat().st_mode) == 0o600
        (chain_id,) = read_checkpoints(checkpoints)

        key = KEY.decode()
        assert verify_cli([str(archive), "--key", key, "--manifest", str(manifest)]) == 0
        remaining = [str(p) for p in audit_files(log)]
        assert verify_cli([*remaining, "--key", key, "--checkpoints", str(checkpoints)]) == 0
        assert verify_cli([*remaining, "--key", key]) == 1
        assert "after its archive" not in capsys.readouterr().out

        _write(logger, 2, NOW, monkeypatch)  # the server keeps writing its chain
        remaining = [str(p) for p in audit_files(log)]
        assert verify_cli([*remaining, "--key", key, "--checkpoints", str(checkpoints)]) == 0

    def test_a_second_run_finds_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log, _ = _old_then_new(tmp_path, monkeypatch)
        _purge(log, tmp_path)
        again = _purge(log, tmp_path)
        assert again.records == 0 and again.archive is None

    def test_the_current_file_is_never_removed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log = tmp_path / "audit.log"
        _write(_logger(log, rotate_bytes=None), 3, OLD, monkeypatch)
        _age([log], OLD)
        result = _purge(log, tmp_path)
        assert result.records == 0 and log.exists()

    def test_a_recently_written_file_stays(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log = tmp_path / "audit.log"
        _write(_logger(log), 8, OLD, monkeypatch)  # old records, files touched now
        assert _purge(log, tmp_path).records == 0

    def test_a_log_that_does_not_verify_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log, _ = _old_then_new(tmp_path, monkeypatch)
        first = audit_files(log)[0]
        lines = first.read_text(encoding="utf-8").splitlines()
        first.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
        _age([first], OLD)

        with pytest.raises(RetentionRefusedError, match="does not start at seq 0"):
            _purge(log, tmp_path)
        assert first.exists()
        assert not (tmp_path / "archive").exists()

    def test_an_interrupted_run_is_finished_by_the_next(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log, _ = _old_then_new(tmp_path, monkeypatch)

        def crash(*paths: Path) -> None:
            raise KeyboardInterrupt  # stopped after the checkpoints, before the delete

        with monkeypatch.context() as m:
            m.setattr(audit_retention, "remove", crash)
            with pytest.raises(KeyboardInterrupt):
                _purge(log, tmp_path)
        checkpoints = checkpoints_path(log)
        assert read_checkpoints(checkpoints)
        files = audit_files(log)
        assert not audit_verify.verify_files(files, KEY, starts=read_checkpoints(checkpoints)).ok

        result = _purge(log, tmp_path)
        assert result.records == 0
        assert audit_verify.verify_files(
            audit_files(log), KEY, starts=read_checkpoints(checkpoints)
        ).ok

    def test_legacy_unchained_records_are_archived_without_checkpoints(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log = tmp_path / "audit.log"
        rotated = tmp_path / "audit.log.20250101T000000000000Z"
        rotated.write_text(
            json.dumps({"timestamp": OLD.isoformat(), "operation": "legacy"}) + "\n",
            encoding="utf-8",
        )
        _age([rotated], OLD)
        _write(_logger(log, rotate_bytes=None), 1, NOW, monkeypatch)

        result = _purge(log, tmp_path)
        assert result.records == 1 and result.chains == []
        assert not rotated.exists()
        assert read_checkpoints(checkpoints_path(log)) == {}

    def test_the_admin_event_comes_before_the_delete(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.utils.audit import AuditUnavailableError

        log, logger = _old_then_new(tmp_path, monkeypatch)
        before = audit_files(log)

        class Refusing:
            def log_event(self, *args: Any, **kwargs: Any) -> None:
                assert kwargs.get("strict") is True
                raise AuditUnavailableError("disk full")

        with pytest.raises(AuditUnavailableError):
            _purge(log, tmp_path, audit=Refusing())
        assert audit_files(log) == before
        assert list((tmp_path / "archive").iterdir()) == []
        assert not checkpoints_path(log).exists()

        _purge(log, tmp_path, audit=logger)
        newest = audit_files(log)[-1]  # the event may have filled and rotated the file
        last = json.loads(newest.read_text(encoding="utf-8").splitlines()[-1])
        assert last["operation"] == "audit_retention"

    def test_an_unreadable_file_refuses_the_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        log, _ = _old_then_new(tmp_path, monkeypatch)
        audit_files(log)[0].write_bytes(b"\xff\xfe not utf-8\n")
        monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", KEY.decode())
        assert retention_cli([str(log), "--days", "30", "--confirm"]) == 1
        assert "cannot read" in capsys.readouterr().err

    def test_bad_checkpoints(self, tmp_path: Path) -> None:
        path = tmp_path / "c.jsonl"
        path.write_text('{"chain_id": "a", "seq": "x"}\n', encoding="utf-8")
        with pytest.raises(ValueError, match="line 1 is not a checkpoint"):
            read_checkpoints(path)
        with pytest.raises(ValueError, match="not found"):
            read_checkpoints(tmp_path / "missing.jsonl")

    def test_retention_days_must_be_positive(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            _purge(tmp_path / "audit.log", tmp_path, retention_days=0)


class TestCli:
    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in (
            "UNIFI_AUDIT_RETENTION_DAYS",
            "UNIFI_AUDIT_ARCHIVE_DIR",
            "UNIFI_READ_ONLY",
            "UNIFI_AUDIT_LOG_ROTATE_MB",
        ):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", KEY.decode())

    def test_needs_a_retention_period(self, tmp_path: Path, capsys: Any) -> None:
        assert retention_cli([str(tmp_path / "audit.log")]) == 2
        assert "UNIFI_AUDIT_RETENTION_DAYS" in capsys.readouterr().err

    def test_read_only_refuses_confirm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        monkeypatch.setenv("UNIFI_READ_ONLY", "true")
        assert retention_cli([str(tmp_path / "audit.log"), "--days", "30", "--confirm"]) == 2
        assert "UNIFI_READ_ONLY" in capsys.readouterr().err

    def test_dry_run_then_confirm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        log, _ = _old_then_new(tmp_path, monkeypatch)
        monkeypatch.setenv("UNIFI_AUDIT_RETENTION_DAYS", "30")
        monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", KEY.decode())

        assert retention_cli([str(log)]) == 0
        out = capsys.readouterr()
        assert json.loads(out.out)["records"] == 8
        assert "pass --confirm" in out.err

        assert retention_cli([str(log), "--confirm"]) == 0
        summary = json.loads(capsys.readouterr().out)
        assert Path(summary["archive"]).parent == tmp_path / "audit-archive"
        last = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
        assert (last["event_type"], last["operation"]) == ("admin", "audit_retention")
        remaining = [str(p) for p in audit_files(log)]
        checkpoints = str(checkpoints_path(log))
        assert verify_cli([*remaining, "--checkpoints", checkpoints]) == 0

    def test_a_refused_run_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        log, _ = _old_then_new(tmp_path, monkeypatch)
        first = audit_files(log)[0]
        first.write_text("not json\n", encoding="utf-8")
        assert retention_cli([str(log), "--days", "30", "--confirm"]) == 1
        assert "does not verify" in capsys.readouterr().err

    def test_a_missing_key_is_a_usage_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        log, _ = _old_then_new(tmp_path, monkeypatch)
        monkeypatch.delenv("UNIFI_AUDIT_CHAIN_KEY")
        assert retention_cli([str(log), "--days", "30"]) == 2
        assert "UNIFI_AUDIT_CHAIN_KEY" in capsys.readouterr().err

    def test_verify_cli_usage_errors(self, tmp_path: Path, capsys: Any) -> None:
        log = tmp_path / "audit.log"
        log.write_text("", encoding="utf-8")
        bad = tmp_path / "c.jsonl"
        bad.write_text("[1]\n", encoding="utf-8")
        assert verify_cli([str(log), "--checkpoints", str(bad)]) == 2
        assert "--checkpoints" in capsys.readouterr().err
        assert verify_cli([str(log), str(log), "--manifest", str(bad)]) == 2
        assert "one archive at a time" in capsys.readouterr().err
        assert verify_cli([str(log), str(tmp_path / "missing")]) == 2
