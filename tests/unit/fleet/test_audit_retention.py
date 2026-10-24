"""Audit retention (docs/FLEET_SCALING_PLAN.md §3.7, Phase 5c): verify, archive, then delete."""

from __future__ import annotations

import gzip
import json
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from src.utils import audit_verify
from src.utils.audit_verify import GENESIS, file_sha256, read_manifest, verify_records

verify_cli = audit_verify.main

sqlalchemy = pytest.importorskip("sqlalchemy")

from sqlalchemy import text  # noqa: E402

from src.fleet.db import audit_store, retention  # noqa: E402
from src.fleet.db.audit_store import PostgresAuditSink  # noqa: E402
from src.fleet.db.retention import RetentionRefusedError, purge_expired  # noqa: E402

CHAIN_KEY = b"retention-chain-key"  # pragma: allowlist secret
A, B = "a" * 32, "b" * 32
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


async def _fill(engine: Any, chain_id: str, ages_days: list[float]) -> PostgresAuditSink:
    """One record per age, in order, with ``ts`` and the record's timestamp that old."""
    sink = PostgresAuditSink(engine, chain_id=chain_id)
    for n, age in enumerate(ages_days):
        await sink.append(
            {
                "event_id": f"{chain_id[:4]}-{n}",
                "timestamp": (NOW - timedelta(days=age)).isoformat(),
                "event_type": "tool_call",
                "operation": "update_network",
                "result": "success",
            },
            key=CHAIN_KEY,
            strict=True,
        )
    await _as_superuser(
        engine,
        "UPDATE audit_log SET ts = (record::json->>'timestamp')::timestamptz "
        f"WHERE chain_id = '{chain_id}'",
    )
    return sink


async def _as_superuser(engine: Any, *statements: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL session_replication_role = replica"))
        for statement in statements:
            await conn.execute(text(statement))


async def _seqs(engine: Any, chain_id: str) -> list[int]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT seq FROM audit_log WHERE chain_id = :c ORDER BY seq"), {"c": chain_id}
        )
        return [int(r.seq) for r in rows]


async def _purge(engine: Any, tmp_path: Path, **kwargs: Any) -> retention.RetentionResult:
    options: dict[str, Any] = {
        "retention_days": 30,
        "archive_dir": tmp_path / "archive",
        "dry_run": False,
        "now": NOW,
    }
    options.update(kwargs)
    return await purge_expired(engine, CHAIN_KEY, **options)


class TestVerifyWithStarts:
    def _records(self, seqs: range) -> list[tuple[str, str]]:
        from src.utils.audit import seal_record

        out, prev = [], GENESIS[1]
        for seq in range(seqs.stop):
            record: dict[str, Any] = {"event_id": str(seq)}
            seal_record(record, chain_id=A, seq=seq, prev_hash=prev, key=None)
            prev = record["hash"]
            if seq in seqs:
                out.append((f"line {seq}", json.dumps(record)))
        return out

    def test_a_chain_resumes_after_its_start(self) -> None:
        records = self._records(range(3, 6))
        start_hash = json.loads(records[0][1])["prev_hash"]
        assert verify_records(records, None, starts={A: (2, start_hash)}).ok
        report = verify_records(records, None)
        assert "does not start at seq 0" in report.problems[0]

    def test_a_wrong_start_is_reported(self) -> None:
        report = verify_records(self._records(range(3, 6)), None, starts={A: (1, "f" * 64)})
        assert "does not start at seq 2 after its archive" in report.problems[0]

    def test_a_fully_archived_chain_matches_its_head(self) -> None:
        assert verify_records([], None, {A: (5, "c" * 64)}, {A: (5, "c" * 64)}).ok
        report = verify_records([], None, {A: (6, "d" * 64)}, {A: (5, "c" * 64)})
        assert "none of its records remain" in report.problems[0]


class TestPurge:
    async def test_dry_run_changes_nothing(self, migrated_engine: Any, tmp_path: Path) -> None:
        await _fill(migrated_engine, A, [40, 35, 1])
        result = await _purge(migrated_engine, tmp_path, dry_run=True)

        assert result.dry_run and result.records == 2
        assert [(c.first_seq, c.last_seq) for c in result.chains] == [(0, 1)]
        assert await _seqs(migrated_engine, A) == [0, 1, 2]
        assert not (tmp_path / "archive").exists()

    async def test_archives_then_deletes_the_expired_prefix(
        self, migrated_engine: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        await _fill(migrated_engine, A, [40, 35, 1])
        await _fill(migrated_engine, B, [50, 2, 1])
        result = await _purge(migrated_engine, tmp_path)

        assert result.records == 3
        assert await _seqs(migrated_engine, A) == [2]
        assert await _seqs(migrated_engine, B) == [1, 2]
        assert (await audit_store.verify(migrated_engine, CHAIN_KEY)).ok

        archive, manifest = result.archive, result.manifest
        assert archive is not None and manifest is not None
        assert stat.S_IMODE((tmp_path / "archive").stat().st_mode) == 0o700
        assert stat.S_IMODE(archive.stat().st_mode) == 0o600
        assert stat.S_IMODE(manifest.stat().st_mode) == 0o600
        with gzip.open(archive, "rt", encoding="utf-8") as f:
            archived = [json.loads(line) for line in f]
        assert [(r["chain_id"][0], r["seq"]) for r in archived] == [("a", 0), ("a", 1), ("b", 0)]
        assert read_manifest(manifest).sha256 == file_sha256(archive)

        key = CHAIN_KEY.decode()
        assert verify_cli([str(archive), "--key", key, "--manifest", str(manifest)]) == 0
        assert "OK: 3 record(s), 2 chain(s)" in capsys.readouterr().out

    async def test_a_second_run_continues_where_the_first_stopped(
        self, migrated_engine: Any, tmp_path: Path
    ) -> None:
        await _fill(migrated_engine, A, [60, 50, 20, 1])
        first = await _purge(migrated_engine, tmp_path)
        second = await _purge(migrated_engine, tmp_path, retention_days=10)

        assert [(c.first_seq, c.last_seq) for c in first.chains] == [(0, 1)]
        assert [(c.first_seq, c.last_seq) for c in second.chains] == [(2, 2)]
        assert second.chains[0].prev_hash == first.chains[0].last_hash
        assert await _seqs(migrated_engine, A) == [3]
        assert (await audit_store.verify(migrated_engine, CHAIN_KEY)).ok
        assert second.archive is not None and second.manifest is not None
        key = CHAIN_KEY.decode()
        assert (
            verify_cli([str(second.archive), "--key", key, "--manifest", str(second.manifest)]) == 0
        )

    async def test_a_fully_expired_chain_still_verifies(
        self, migrated_engine: Any, tmp_path: Path
    ) -> None:
        await _fill(migrated_engine, A, [40, 35])
        result = await _purge(migrated_engine, tmp_path)

        assert result.records == 2
        assert await _seqs(migrated_engine, A) == []
        assert (await audit_store.verify(migrated_engine, CHAIN_KEY)).ok

    async def test_a_newer_record_keeps_everything_after_it(
        self, migrated_engine: Any, tmp_path: Path
    ) -> None:
        await _fill(migrated_engine, A, [40, 1, 40])  # clock skew: seq 2 looks old
        result = await _purge(migrated_engine, tmp_path)

        assert result.records == 1
        assert await _seqs(migrated_engine, A) == [1, 2]
        assert (await audit_store.verify(migrated_engine, CHAIN_KEY)).ok

    async def test_an_old_record_after_a_kept_one_stays(
        self, migrated_engine: Any, tmp_path: Path
    ) -> None:
        await _fill(migrated_engine, A, [1, 40])
        result = await _purge(migrated_engine, tmp_path)
        assert result.records == 0 and result.archive is None
        assert await _seqs(migrated_engine, A) == [0, 1]

    async def test_nothing_expired(self, migrated_engine: Any, tmp_path: Path) -> None:
        await _fill(migrated_engine, A, [1, 1])
        result = await _purge(migrated_engine, tmp_path)
        assert result.records == 0 and result.archive is None
        assert not (tmp_path / "archive").exists()

    async def test_a_store_that_does_not_verify_is_refused(
        self, migrated_engine: Any, tmp_path: Path
    ) -> None:
        await _fill(migrated_engine, A, [40, 35, 1])
        await _as_superuser(
            migrated_engine, f"DELETE FROM audit_log WHERE seq = 1 AND chain_id = '{A}'"
        )

        with pytest.raises(RetentionRefusedError, match="expected seq 1"):
            await _purge(migrated_engine, tmp_path)
        assert await _seqs(migrated_engine, A) == [0, 2]
        assert not (tmp_path / "archive").exists()

    async def test_a_failed_delete_removes_the_archive(
        self, migrated_engine: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await _fill(migrated_engine, A, [40, 1])

        def broken_insert(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("insert failed")

        monkeypatch.setattr(retention, "insert", broken_insert)
        with pytest.raises(RuntimeError, match="insert failed"):
            await _purge(migrated_engine, tmp_path)
        assert await _seqs(migrated_engine, A) == [0, 1]
        assert list((tmp_path / "archive").iterdir()) == []

    async def test_retention_days_must_be_positive(
        self, migrated_engine: Any, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            await _purge(migrated_engine, tmp_path, retention_days=0)


class TestReviewFixes:
    async def test_a_fully_archived_chain_needs_its_head(
        self, migrated_engine: Any, tmp_path: Path
    ) -> None:
        await _fill(migrated_engine, A, [40, 35])
        await _purge(migrated_engine, tmp_path)
        await _as_superuser(
            migrated_engine, f"DELETE FROM audit_chain_heads WHERE chain_id = '{A}'"
        )

        report = await audit_store.verify(migrated_engine, CHAIN_KEY)
        assert any("was archived but has no recorded head" in p for p in report.problems)

    async def test_the_admin_event_is_written_with_the_delete(
        self, migrated_engine: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.utils.audit import AuditLogger

        await _fill(migrated_engine, A, [40, 1])
        audit = AuditLogger(tmp_path / "audit.log")
        audit.chain_key = CHAIN_KEY
        await _purge(migrated_engine, tmp_path, audit=audit)
        async with migrated_engine.connect() as conn:
            rows = list(
                await conn.execute(text("SELECT record FROM audit_log WHERE event_type = 'admin'"))
            )
        (record,) = [json.loads(r.record) for r in rows]
        assert record["operation"] == "audit_retention"
        assert record["parameters"]["records"] == 1
        assert (await audit_store.verify(migrated_engine, CHAIN_KEY)).ok

    async def test_a_failed_admin_event_deletes_nothing(
        self, migrated_engine: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.utils.audit import AuditLogger, AuditUnavailableError

        await _fill(migrated_engine, A, [40, 1])

        async def refuse(self: Any, *args: Any, **kwargs: Any) -> bool:
            raise AuditUnavailableError("audit store unavailable")

        monkeypatch.setattr(PostgresAuditSink, "append", refuse)
        with pytest.raises(AuditUnavailableError):
            await _purge(migrated_engine, tmp_path, audit=AuditLogger(tmp_path / "audit.log"))
        assert await _seqs(migrated_engine, A) == [0, 1]
        assert list((tmp_path / "archive").iterdir()) == []

    async def test_an_unknown_commit_outcome_keeps_the_archive(
        self, migrated_engine: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await _fill(migrated_engine, A, [40, 1])

        def broken_insert(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("connection lost")

        async def maybe_committed(engine: Any, name: str) -> bool:
            return True

        monkeypatch.setattr(retention, "insert", broken_insert)
        monkeypatch.setattr(retention, "_archive_recorded", maybe_committed)
        with pytest.raises(RuntimeError, match="connection lost"):
            await _purge(migrated_engine, tmp_path)
        assert len(list((tmp_path / "archive").iterdir())) == 2

    async def test_archive_check_keeps_files_when_the_database_cannot_answer(self) -> None:
        from src.fleet.db.schema import make_engine

        engine = make_engine("postgresql://nobody@127.0.0.1:1/none")
        try:
            assert await retention._archive_recorded(engine, "x.jsonl.gz") is True
        finally:
            await engine.dispose()

    async def test_downgrade_is_refused_after_retention(
        self, migrated_engine: Any, tmp_path: Path
    ) -> None:
        from src.fleet.db.schema import downgrade

        await _fill(migrated_engine, A, [40, 1])
        await _purge(migrated_engine, tmp_path)
        with pytest.raises(RuntimeError, match="unverifiable"):
            await downgrade(migrated_engine, "0004")

    async def test_a_chain_left_out_of_the_manifest_is_caught(
        self, migrated_engine: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        await _fill(migrated_engine, A, [40, 1])
        await _fill(migrated_engine, B, [40, 1])
        result = await _purge(migrated_engine, tmp_path)
        assert result.manifest is not None and result.archive is not None
        data = json.loads(result.manifest.read_text(encoding="utf-8"))
        data["chains"] = [c for c in data["chains"] if c["chain_id"] != B]
        result.manifest.write_text(json.dumps(data), encoding="utf-8")

        key = CHAIN_KEY.decode()
        assert (
            verify_cli([str(result.archive), "--key", key, "--manifest", str(result.manifest)]) == 1
        )
        assert "chain bbbbbbbb is not in its manifest" in capsys.readouterr().out

    def test_a_corrupt_archive_fails_cleanly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        archive = tmp_path / "broken.jsonl.gz"
        archive.write_bytes(gzip.compress(b"{}\n" * 100)[:-6])  # trailer cut off
        assert verify_cli([str(archive)]) == 1
        assert "cannot read" in capsys.readouterr().out
        archive.write_bytes(b"not gzip at all")
        assert verify_cli([str(archive)]) == 1


class TestArchiveTampering:
    async def test_deleting_an_archive_row_is_caught(
        self, migrated_engine: Any, tmp_path: Path
    ) -> None:
        await _fill(migrated_engine, A, [40, 35, 1])
        await _purge(migrated_engine, tmp_path)
        await _as_superuser(migrated_engine, "DELETE FROM audit_archives")

        report = await audit_store.verify(migrated_engine, CHAIN_KEY)
        assert any("does not start at seq 0" in p for p in report.problems)

    async def test_a_gap_between_archives_is_caught(
        self, migrated_engine: Any, tmp_path: Path
    ) -> None:
        await _fill(migrated_engine, A, [60, 50, 20, 1])
        await _purge(migrated_engine, tmp_path)
        await _purge(migrated_engine, tmp_path, retention_days=10)
        await _as_superuser(migrated_engine, "DELETE FROM audit_archives WHERE first_seq = 0")

        report = await audit_store.verify(migrated_engine, CHAIN_KEY)
        assert any("does not continue from seq -1" in p for p in report.problems)

    async def test_an_edited_archive_fails_its_manifest(
        self, migrated_engine: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        await _fill(migrated_engine, A, [40, 35, 1])
        result = await _purge(migrated_engine, tmp_path)
        assert result.archive is not None and result.manifest is not None
        with gzip.open(result.archive, "rt", encoding="utf-8") as f:
            lines = f.read().splitlines()
        with gzip.open(result.archive, "wt", encoding="utf-8") as f:
            f.write(lines[0] + "\n")  # drop the archive's last record

        key = CHAIN_KEY.decode()
        assert (
            verify_cli([str(result.archive), "--key", key, "--manifest", str(result.manifest)]) == 1
        )
        out = capsys.readouterr().out
        assert "SHA-256 does not match" in out
        assert "missing from the end" in out
        assert "its manifest says 2" in out

    def test_a_bad_manifest_is_a_usage_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = tmp_path / "audit.log"
        log.write_text("", encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text("{}", encoding="utf-8")
        assert verify_cli([str(log), "--manifest", str(manifest)]) == 2
        assert "not an audit archive manifest" in capsys.readouterr().err


class TestAppendOnlyTrigger:
    async def test_the_owner_cannot_delete_without_the_retention_flag(
        self, migrated_engine: Any
    ) -> None:
        await _fill(migrated_engine, A, [1])
        with pytest.raises(Exception, match="append-only"):
            async with migrated_engine.begin() as conn:
                await conn.execute(text("DELETE FROM audit_log"))

    async def test_truncate_is_refused_even_with_the_flag(self, migrated_engine: Any) -> None:
        await _fill(migrated_engine, A, [1])
        with pytest.raises(Exception, match="append-only"):
            async with migrated_engine.begin() as conn:
                await conn.execute(text("SET LOCAL unifi_mcp.audit_retention = 'on'"))
                await conn.execute(text("TRUNCATE audit_log"))

    async def test_another_role_cannot_delete_with_the_flag(self, migrated_engine: Any) -> None:
        import uuid

        await _fill(migrated_engine, A, [1])
        role = f"retention_intruder_{uuid.uuid4().hex[:8]}"
        async with migrated_engine.begin() as conn:
            await conn.execute(text(f"CREATE ROLE {role}"))
            await conn.execute(text(f"GRANT SELECT, DELETE ON audit_log TO {role}"))
        with pytest.raises(Exception, match="append-only"):
            async with migrated_engine.begin() as conn:
                await conn.execute(text(f"SET LOCAL ROLE {role}"))
                await conn.execute(text("SET LOCAL unifi_mcp.audit_retention = 'on'"))
                await conn.execute(text("DELETE FROM audit_log"))
        assert await _seqs(migrated_engine, A) == [0]

    async def test_archive_rows_are_append_only(self, migrated_engine: Any, tmp_path: Path) -> None:
        await _fill(migrated_engine, A, [40, 1])
        await _purge(migrated_engine, tmp_path)
        for statement in ("UPDATE audit_archives SET records = 0", "DELETE FROM audit_archives"):
            with pytest.raises(Exception, match="audit_archives is append-only"):
                async with migrated_engine.begin() as conn:
                    await conn.execute(text("SET LOCAL unifi_mcp.audit_retention = 'on'"))
                    await conn.execute(text(statement))


class TestCli:
    def _env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, database_url: str) -> None:
        monkeypatch.delenv("UNIFI_API_KEY", raising=False)  # not needed by retention
        monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
        monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", CHAIN_KEY.decode())
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)

    def test_needs_a_retention_period(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        database_url: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from src.fleet.cli import main

        self._env(monkeypatch, tmp_path, database_url)
        monkeypatch.delenv("UNIFI_AUDIT_RETENTION_DAYS", raising=False)
        assert main(["audit-retention"]) == 2
        assert "UNIFI_AUDIT_RETENTION_DAYS" in capsys.readouterr().err

    def test_read_only_refuses_confirm(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        database_url: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from src.fleet.cli import main

        self._env(monkeypatch, tmp_path, database_url)
        monkeypatch.setenv("UNIFI_READ_ONLY", "true")
        assert main(["audit-retention", "--days", "30", "--confirm"]) == 2
        assert "UNIFI_READ_ONLY" in capsys.readouterr().err

    async def test_dry_run_then_confirm(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        database_url: str,
        migrated_engine: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import asyncio

        from src.fleet.cli import main

        self._env(monkeypatch, tmp_path, database_url)
        monkeypatch.setenv("UNIFI_AUDIT_RETENTION_DAYS", "30")
        await _fill(migrated_engine, A, [400, 300, 0])

        loop = asyncio.get_running_loop()
        assert await loop.run_in_executor(None, main, ["audit-retention"]) == 0
        out = capsys.readouterr()
        assert json.loads(out.out)["records"] == 2
        assert "pass --confirm" in out.err
        assert await _seqs(migrated_engine, A) == [0, 1, 2]

        assert await loop.run_in_executor(None, main, ["audit-retention", "--confirm"]) == 0
        summary = json.loads(capsys.readouterr().out)
        assert summary["records"] == 2 and not summary["dry_run"]
        assert Path(summary["archive"]).parent == tmp_path / "audit-archive"
        assert await _seqs(migrated_engine, A) == [2]
        async with migrated_engine.connect() as conn:
            operations = [
                r.operation
                for r in await conn.execute(
                    text("SELECT operation FROM audit_log WHERE event_type = 'admin'")
                )
            ]
        assert operations == ["audit_retention"]
        assert (await audit_store.verify(migrated_engine, CHAIN_KEY)).ok

    async def test_a_missing_chain_key_is_a_usage_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        database_url: str,
        migrated_engine: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import asyncio

        from src.fleet.cli import main

        self._env(monkeypatch, tmp_path, database_url)
        monkeypatch.delenv("UNIFI_AUDIT_CHAIN_KEY")
        await _fill(migrated_engine, A, [400])
        loop = asyncio.get_running_loop()
        assert await loop.run_in_executor(None, main, ["audit-retention", "--days", "30"]) == 2
        assert "UNIFI_AUDIT_CHAIN_KEY" in capsys.readouterr().err

    async def test_a_refused_run_exits_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        database_url: str,
        migrated_engine: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import asyncio

        from src.fleet.cli import main

        self._env(monkeypatch, tmp_path, database_url)
        await _fill(migrated_engine, A, [400, 300])
        await _as_superuser(
            migrated_engine, f"DELETE FROM audit_log WHERE seq = 0 AND chain_id = '{A}'"
        )
        loop = asyncio.get_running_loop()
        args = [
            "audit-retention",
            "--days",
            "30",
            "--archive-dir",
            str(tmp_path / "x"),
            "--confirm",
        ]
        assert await loop.run_in_executor(None, main, args) == 1
        assert "does not verify" in capsys.readouterr().err
