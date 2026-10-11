"""Postgres audit store (docs/FLEET_SCALING_PLAN.md §3.7, Phase 2b).

With DATABASE_URL set, audit records go to the ``audit_log`` table instead of
the JSONL file. Each server keeps its own hash chain (``chain_id``) and stores
every record exactly as hashed, so :func:`verify` runs the same checks as the
file verifier. A trigger makes ``audit_log`` append-only for every role.
"""

import asyncio
import contextlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ...config import Settings
from ...utils.audit import (
    GENESIS_HASH,
    INSTANCE_ID,
    AuditLogger,
    AuditUnavailableError,
    get_audit_logger,
    seal_record,
)
from ...utils.audit_verify import Head, VerifyReport, verify_records
from ...utils.logger import get_logger
from .models import AuditChainHead, AuditLogEntry
from .retention import archive_problems, archived_starts

logger = get_logger(__name__)

#: Most records one search or export returns.
MAX_RECORDS = 1000


class PostgresAuditSink:
    """Appends this server's chained audit records to ``audit_log``."""

    def __init__(self, engine: AsyncEngine, chain_id: str = INSTANCE_ID) -> None:
        """Create a sink starting a new chain.

        Args:
            engine: The registry's engine
            chain_id: This server's chain (one per process; tests may pass their own)
        """
        self.engine = engine
        self.chain_id = chain_id
        self._lock = asyncio.Lock()
        self._seq = 0
        self._prev_hash = GENESIS_HASH

    async def append(
        self,
        record: dict[str, Any],
        *,
        key: bytes | None,
        strict: bool,
        conn: AsyncConnection | None = None,
    ) -> bool:
        """Chain and insert one record (payload fields already encrypted).

        Args:
            record: The record
            key: The chain HMAC key
            strict: Raise instead of logging when the record is not stored
            conn: Insert inside this connection's open transaction (the
                caller commits) instead of a transaction of its own

        Returns:
            True if the record was stored (False only when not ``strict``)

        Raises:
            AuditUnavailableError: When ``strict`` and the record was not stored
        """
        async with self._lock:
            seal_record(
                record, chain_id=self.chain_id, seq=self._seq, prev_hash=self._prev_hash, key=key
            )
            principal = record.get("principal")
            row = {
                "event_id": record["event_id"],
                "event_type": record["event_type"],
                "operation": record["operation"],
                "result": record["result"],
                "tier": record.get("tier"),
                "controller": record.get("controller"),
                "principal_id": principal.get("id") if isinstance(principal, dict) else None,
                "call_id": record.get("call_id"),
                "chain_id": self.chain_id,
                "seq": self._seq,
                "hash": record["hash"],
                "record": json.dumps(record),
            }
            try:
                async with contextlib.AsyncExitStack() as stack:
                    if conn is None:
                        conn = await stack.enter_async_context(self.engine.begin())
                    await conn.execute(insert(AuditLogEntry).values(**row))
                    await conn.execute(
                        insert(AuditChainHead)
                        .values(chain_id=self.chain_id, seq=self._seq, hash=record["hash"])
                        .on_conflict_do_update(
                            index_elements=["chain_id"],
                            set_={
                                "seq": self._seq,
                                "hash": record["hash"],
                                "updated_at": func.now(),
                            },
                        )
                    )
            except Exception as e:
                if strict:
                    raise AuditUnavailableError(f"Audit store unavailable: {e}") from e
                logger.error("Failed to write audit record: %s", e)
                return False
            self._seq += 1
            self._prev_hash = record["hash"]
            return True


def install(settings: Settings, engine: AsyncEngine) -> AuditLogger | None:
    """Send this server's audit records to Postgres.

    Returns:
        The audit logger now writing to Postgres, or None if auditing is off
    """
    if not settings.audit_log_enabled:
        return None
    audit = get_audit_logger(settings.audit_log_file)
    audit.sink = PostgresAuditSink(engine)
    return audit


def _filters(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    event_type: str | None = None,
    operation: str | None = None,
    principal_id: str | None = None,
    controller: str | None = None,
    result: str | None = None,
) -> list[Any]:
    clauses: list[Any] = []
    if since is not None:
        clauses.append(AuditLogEntry.ts >= since)
    if until is not None:
        clauses.append(AuditLogEntry.ts < until)
    for column, value in (
        (AuditLogEntry.event_type, event_type),
        (AuditLogEntry.operation, operation),
        (AuditLogEntry.principal_id, principal_id),
        (AuditLogEntry.controller, controller),
        (AuditLogEntry.result, result),
    ):
        if value is not None:
            clauses.append(column == value)
    return clauses


async def search(
    engine: AsyncEngine,
    *,
    limit: int = 100,
    before_id: int | None = None,
    **filters: Any,
) -> tuple[list[tuple[int, str]], int | None]:
    """Return stored records matching ``filters``, newest first.

    Args:
        engine: The registry's engine
        limit: Most records to return (capped at :data:`MAX_RECORDS`)
        before_id: Cursor from a previous page
        **filters: ``since``, ``until``, ``event_type``, ``operation``,
            ``principal_id``, ``controller``, ``result``

    Returns:
        ``(row id, stored JSON)`` pairs and the cursor for the next page
    """
    limit = max(1, min(limit, MAX_RECORDS))
    query = select(AuditLogEntry.id, AuditLogEntry.record).where(*_filters(**filters))
    if before_id is not None:
        query = query.where(AuditLogEntry.id < before_id)
    query = query.order_by(AuditLogEntry.id.desc()).limit(limit + 1)
    async with engine.connect() as conn:
        rows = [(int(r.id), str(r.record)) for r in await conn.execute(query)]
    next_cursor = rows[limit - 1][0] if len(rows) > limit else None
    return rows[:limit], next_cursor


async def verify(
    engine: AsyncEngine, key: bytes | None, extra_heads: Mapping[str, Head] | None = None
) -> VerifyReport:
    """Verify every chain in the audit store, in insertion order.

    Chains whose oldest records were archived by retention resume right
    after their latest ``audit_archives`` entry, and successive archives of a
    chain must not leave gaps. Each chain must also end exactly at its
    ``audit_chain_heads`` entry, so
    records removed from the end of a chain (or a whole chain, or the whole
    table) are reported. Records and heads are read from one snapshot: a
    record and its head are written in one transaction.

    Args:
        engine: The registry's engine
        key: The chain HMAC key
        extra_heads: Heads recorded outside the database (e.g. SIEM anchors);
            they take precedence over the table, which someone with write
            access to the database could have rewritten along with the records

    Raises:
        ChainKeyMissingError: If records are HMAC-chained and no key is given
    """
    query = select(AuditLogEntry).order_by(AuditLogEntry.id)
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="REPEATABLE READ")
        async with conn.begin():
            entries = list((await conn.execute(query)).all())
            heads: dict[str, Head] = {
                str(h.chain_id): (int(h.seq), str(h.hash))
                for h in await conn.execute(select(AuditChainHead))
            }
            starts = await archived_starts(conn)
            gaps = await archive_problems(conn)
    heads.update(extra_heads or {})
    rows = [(f"row {e.id}", str(e.record)) for e in entries]
    report = verify_records(rows, key, heads, starts)
    report.problems.extend(gaps)

    # Every chain the sink writes has a head; one without a head (its row
    # deleted) would otherwise escape the end-of-chain check.
    for chain_id in sorted({str(e.chain_id) for e in entries} - set(heads)):
        report.problems.append(f"chain {chain_id[:8]}: has records but no recorded head")
    # A fully archived chain has no rows left; its head must still be there.
    for chain_id in sorted(set(starts) - {str(e.chain_id) for e in entries} - set(heads)):
        report.problems.append(f"chain {chain_id[:8]}: was archived but has no recorded head")
    for entry in entries:
        report.problems.extend(_column_problems(entry))
    return report


#: Searchable columns copied out of each record, and where they come from.
_COPIED_COLUMNS = (
    "event_id",
    "event_type",
    "operation",
    "result",
    "tier",
    "controller",
    "call_id",
    "chain_id",
    "seq",
    "hash",
)

#: Most a row's insert time (``ts``) may differ from the record's own timestamp.
_TS_TOLERANCE_SECONDS = 300


def _column_problems(entry: Any) -> list[str]:
    """Columns of one row that disagree with its sealed record.

    Searches filter on these columns, so editing one could hide a record from
    a search or misfile it without touching the hash-covered record.
    """
    where = f"row {entry.id}"
    try:
        record = json.loads(entry.record)
    except (TypeError, ValueError):
        return []  # reported by verify_records
    if not isinstance(record, dict):
        return []
    problems = [
        f"{where}: column {name} does not match the record"
        for name in _COPIED_COLUMNS
        if getattr(entry, name) != record.get(name)
    ]
    principal = record.get("principal")
    principal_id = principal.get("id") if isinstance(principal, dict) else None
    if entry.principal_id != principal_id:
        problems.append(f"{where}: column principal_id does not match the record")
    stamp = record.get("timestamp")
    if isinstance(stamp, str) and entry.ts is not None:
        try:
            recorded = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            recorded = None
        if recorded is not None:
            if recorded.tzinfo is None:
                recorded = recorded.replace(tzinfo=timezone.utc)
            if abs((entry.ts - recorded).total_seconds()) > _TS_TOLERANCE_SECONDS:
                problems.append(f"{where}: column ts is far from the record's timestamp")
    return problems


async def chain_heads(engine: AsyncEngine) -> list[dict[str, Any]]:
    """Return each chain's latest seq and hash (anchor them off the server)."""
    async with engine.connect() as conn:
        rows = await conn.execute(select(AuditChainHead).order_by(AuditChainHead.chain_id))
        return [
            {
                "chain_id": r.chain_id,
                "seq": r.seq,
                "hash": r.hash,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ]
