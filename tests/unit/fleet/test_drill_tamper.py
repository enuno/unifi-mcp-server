"""Tamper drill (docs/FLEET_SCALING_PLAN.md Phase 5): every edit is caught.

Each case changes a stored audit trail the way someone with direct access to
the store could: editing a record, deleting one, deleting the newest ones,
deleting a whole chain or emptying the store. Postgres cases run as the
database superuser with triggers disabled (``session_replication_role =
replica``), so the append-only trigger is out of the way and only the hash
chain and the recorded chain heads stand between the change and a clean
report. The JSONL cases do the same to the file, with a head anchored
elsewhere (``--head``) for the cases a file alone cannot reveal.

The last case of each store documents the limit: rewriting the records and
the recorded heads together passes the in-store check, and only a head kept
outside the store (a SIEM anchor) reveals it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from src.utils.audit import AuditLogger
from src.utils.audit_verify import main as verify_cli
from src.utils.audit_verify import parse_head, verify_file

CHAIN_KEY = b"drill-chain-key"  # pragma: allowlist secret
RECORDS = 6


# ---------------------------------------------------------------------------
# Postgres
# ---------------------------------------------------------------------------

sqlalchemy = pytest.importorskip("sqlalchemy")

from sqlalchemy import text  # noqa: E402

from src.fleet.db import audit_store  # noqa: E402
from src.fleet.db.audit_store import PostgresAuditSink  # noqa: E402


async def _fill(engine: Any, chain_id: str = "a" * 32, count: int = RECORDS) -> None:
    sink = PostgresAuditSink(engine, chain_id=chain_id)
    for n in range(count):
        await sink.append(
            {
                "event_id": f"{chain_id[:4]}-{n}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "tool_call",
                "operation": "update_network",
                "result": "success",
            },
            key=CHAIN_KEY,
            strict=True,
        )


async def _as_superuser(engine: Any, *statements: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL session_replication_role = replica"))
        for statement in statements:
            await conn.execute(text(statement))


A = "a" * 32
ONLY_A = f"chain_id = '{A}'"

POSTGRES_TAMPERING = {
    "edit a record": (
        "UPDATE audit_log SET record = replace(record, '\"success\"', '\"error\"') "
        f"WHERE seq = 2 AND {ONLY_A}",
        "hash does not match",
    ),
    "delete a record": (f"DELETE FROM audit_log WHERE seq = 2 AND {ONLY_A}", "expected seq 2"),
    "delete the newest records": (
        f"DELETE FROM audit_log WHERE seq >= {RECORDS - 2} AND {ONLY_A}",
        "missing from the end",
    ),
    "delete a whole chain": (
        f"DELETE FROM audit_log WHERE {ONLY_A}",
        "none of its records remain",
    ),
    "empty the table": ("TRUNCATE audit_log", "none of its records remain"),
    # Searchable columns copied out of the sealed record: editing one could
    # hide a record from search_audit_log or misfile it.
    "edit a searchable column": (
        f"UPDATE audit_log SET operation = 'list_devices' WHERE seq = 2 AND {ONLY_A}",
        "column operation does not match",
    ),
    "reattribute a record": (
        f"UPDATE audit_log SET principal_id = 'token:someone-else' WHERE seq = 2 AND {ONLY_A}",
        "column principal_id does not match",
    ),
    "move a record out of a time window": (
        f"UPDATE audit_log SET ts = ts - interval '30 days' WHERE seq = 2 AND {ONLY_A}",
        "column ts is far from",
    ),
    "edit the seq column": (
        f"UPDATE audit_log SET seq = 99 WHERE seq = 2 AND {ONLY_A}",
        "column seq does not match",
    ),
    # Without its head a chain would escape the end-of-chain check.
    "delete a head with the newest records": (
        f"DELETE FROM audit_log WHERE seq >= {RECORDS - 2} AND {ONLY_A}; "
        f"DELETE FROM audit_chain_heads WHERE {ONLY_A}",
        "has records but no recorded head",
    ),
    "reorder two records": (
        f"UPDATE audit_log SET id = id + 1000 WHERE seq = 1 AND {ONLY_A}",
        "expected seq 1",
    ),
}


class TestPostgres:
    async def test_untouched_store_verifies(self, migrated_engine: Any) -> None:
        await _fill(migrated_engine)
        await _fill(migrated_engine, chain_id="b" * 32)

        report = await audit_store.verify(migrated_engine, CHAIN_KEY)

        assert report.ok, report.problems
        assert (report.records, report.chains) == (2 * RECORDS, 2)

    @pytest.mark.parametrize("case", sorted(POSTGRES_TAMPERING))
    async def test_tampering_is_caught(self, migrated_engine: Any, case: str) -> None:
        statement, expected = POSTGRES_TAMPERING[case]
        await _fill(migrated_engine)
        await _fill(migrated_engine, chain_id="b" * 32)  # an untouched neighbour

        await _as_superuser(migrated_engine, *statement.split("; "))

        report = await audit_store.verify(migrated_engine, CHAIN_KEY)
        assert not report.ok, case
        assert any(expected in problem for problem in report.problems), report.problems
        if case != "empty the table":  # the only case that touches every chain
            assert not any("chain bbbbbbbb" in p for p in report.problems), "neighbour flagged"

    async def test_records_and_heads_rewritten_together_need_an_outside_anchor(
        self, migrated_engine: Any
    ) -> None:
        await _fill(migrated_engine)
        async with migrated_engine.connect() as conn:
            anchored = (
                await conn.execute(text("SELECT chain_id, seq, hash FROM audit_chain_heads"))
            ).one()

        # Drop the newest record and move the recorded head back to match.
        await _as_superuser(
            migrated_engine,
            f"DELETE FROM audit_log WHERE seq = {RECORDS - 1}",
            "UPDATE audit_chain_heads SET seq = sub.seq, hash = sub.hash FROM "
            "(SELECT seq, hash FROM audit_log ORDER BY seq DESC LIMIT 1) AS sub",
        )

        assert (await audit_store.verify(migrated_engine, CHAIN_KEY)).ok  # the limit
        report = await audit_store.verify(
            migrated_engine,
            CHAIN_KEY,
            extra_heads={anchored.chain_id: (anchored.seq, anchored.hash)},
        )
        assert any("missing from the end" in p for p in report.problems)


# ---------------------------------------------------------------------------
# JSONL
# ---------------------------------------------------------------------------


@pytest.fixture
def chain_key(monkeypatch: pytest.MonkeyPatch) -> bytes:
    monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", CHAIN_KEY.decode())
    monkeypatch.delenv("UNIFI_AUDIT_LOG_KEY", raising=False)
    return CHAIN_KEY


@pytest.fixture
def audit_file(tmp_path: Path, chain_key: bytes) -> Path:
    path = tmp_path / "audit.log"
    logger = AuditLogger(path)
    for n in range(RECORDS):
        logger.log_operation(
            operation="update_network",
            parameters={"n": n},
            result="success",
            user="drill",
        )
    return path


def _lines(path: Path) -> list[str]:
    return path.read_text().splitlines(keepends=True)


def _head(path: Path) -> tuple[str, tuple[int, str]]:
    last = json.loads(_lines(path)[-1])
    return str(last["chain_id"]), (int(last["seq"]), str(last["hash"]))


def _rewrite(path: Path, lines: list[str]) -> None:
    path.write_text("".join(lines))


class TestJsonl:
    def test_untouched_file_verifies_against_its_anchor(self, audit_file: Path) -> None:
        chain_id, head = _head(audit_file)
        report = verify_file(audit_file, CHAIN_KEY, {chain_id: head})
        assert report.ok, report.problems
        assert report.records == RECORDS

    def test_edit_is_caught(self, audit_file: Path) -> None:
        lines = _lines(audit_file)
        lines[2] = lines[2].replace('"success"', '"error"')
        _rewrite(audit_file, lines)
        report = verify_file(audit_file, CHAIN_KEY)
        assert any("hash does not match" in p for p in report.problems)

    def test_deletion_is_caught(self, audit_file: Path) -> None:
        lines = _lines(audit_file)
        del lines[2]
        _rewrite(audit_file, lines)
        report = verify_file(audit_file, CHAIN_KEY)
        assert any("expected seq 2" in p for p in report.problems)

    def test_truncating_the_end_needs_the_anchor(self, audit_file: Path) -> None:
        chain_id, head = _head(audit_file)
        _rewrite(audit_file, _lines(audit_file)[:-2])

        assert verify_file(audit_file, CHAIN_KEY).ok  # undetectable from the file alone
        report = verify_file(audit_file, CHAIN_KEY, {chain_id: head})
        assert any("2 record(s) missing from the end" in p for p in report.problems)

    def test_emptying_the_file_needs_the_anchor(self, audit_file: Path) -> None:
        chain_id, head = _head(audit_file)
        _rewrite(audit_file, [])
        report = verify_file(audit_file, CHAIN_KEY, {chain_id: head})
        assert any("none of its records remain" in p for p in report.problems)

    def test_replacing_the_last_record_is_caught_by_the_anchor(self, audit_file: Path) -> None:
        # A forger without the chain key cannot re-seal; with it, the anchor
        # still pins the head's hash.
        chain_id, (seq, _) = _head(audit_file)
        report = verify_file(audit_file, CHAIN_KEY, {chain_id: (seq, "0" * 64)})
        assert any("does not match the recorded head" in p for p in report.problems)

    def test_cli_head_option(self, audit_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        chain_id, (seq, head_hash) = _head(audit_file)
        anchor = f"{chain_id}:{seq}:{head_hash}"
        assert verify_cli([str(audit_file), "--head", anchor]) == 0

        _rewrite(audit_file, _lines(audit_file)[:-1])
        assert verify_cli([str(audit_file), "--head", anchor]) == 1
        assert "missing from the end" in capsys.readouterr().out

    @pytest.mark.parametrize("value", ["abc", "abc:1", "abc:x:hash", ":1:hash", "abc:1:"])
    def test_cli_rejects_malformed_heads(
        self, audit_file: Path, value: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert verify_cli([str(audit_file), "--head", value]) == 2
        assert "CHAIN:SEQ:HASH" in capsys.readouterr().err

    def test_parse_head(self) -> None:
        assert parse_head("abc:12:ff") == ("abc", (12, "ff"))


class TestColumnCheck:
    """Edge cases of the column-versus-record check, without a database."""

    @staticmethod
    def _entry(record: Any, **columns: Any) -> Any:
        from types import SimpleNamespace

        base = {
            "id": 7,
            "record": record if isinstance(record, str) else json.dumps(record),
            "event_id": "e1",
            "event_type": "tool_call",
            "operation": "update_network",
            "result": "success",
            "tier": None,
            "controller": None,
            "call_id": None,
            "chain_id": "c",
            "seq": 0,
            "hash": "h",
            "principal_id": None,
            "ts": datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc),
        }
        base.update(columns)
        return SimpleNamespace(**base)

    RECORD = {
        "event_id": "e1",
        "event_type": "tool_call",
        "operation": "update_network",
        "result": "success",
        "chain_id": "c",
        "seq": 0,
        "hash": "h",
    }

    def _problems(self, entry: Any) -> list[str]:
        from src.fleet.db.audit_store import _column_problems

        return _column_problems(entry)

    def test_matching_row(self) -> None:
        record = {**self.RECORD, "timestamp": "2026-10-11T12:00:30+00:00"}
        assert self._problems(self._entry(record)) == []

    @pytest.mark.parametrize("raw", ["not json", "[1, 2]"])
    def test_unreadable_records_are_left_to_the_chain_check(self, raw: str) -> None:
        assert self._problems(self._entry(raw)) == []

    def test_a_principal_is_compared_by_id(self) -> None:
        record = {**self.RECORD, "principal": {"id": "token:a", "role": "viewer"}}
        assert self._problems(self._entry(record, principal_id="token:a")) == []
        assert self._problems(self._entry(record, principal_id="token:b")) == [
            "row 7: column principal_id does not match the record"
        ]

    def test_naive_and_zulu_timestamps_are_utc(self) -> None:
        for stamp in ("2026-10-11T12:01:00", "2026-10-11T12:01:00Z"):
            assert self._problems(self._entry({**self.RECORD, "timestamp": stamp})) == []

    def test_unparsable_timestamp_is_not_a_column_problem(self) -> None:
        record = {**self.RECORD, "timestamp": "yesterday"}
        assert self._problems(self._entry(record)) == []


def test_a_chain_past_its_recorded_head_is_reported(audit_file: Path) -> None:
    chain_id, (seq, head_hash) = _head(audit_file)
    report = verify_file(audit_file, CHAIN_KEY, {chain_id: (seq - 2, head_hash)})
    assert any(f"past its recorded head at seq {seq - 2}" in p for p in report.problems)
