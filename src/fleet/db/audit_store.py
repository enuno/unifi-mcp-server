"""Postgres audit store (docs/FLEET_SCALING_PLAN.md §3.7, Phase 2b).

With DATABASE_URL set, audit records go to the ``audit_log`` table instead of
the JSONL file. Each server keeps its own hash chain (``chain_id``) and stores
every record exactly as hashed, so :func:`verify` runs the same checks as the
file verifier. A trigger makes ``audit_log`` append-only for every role.
"""

import asyncio
import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from ...config import Settings
from ...utils.audit import (
    GENESIS_HASH,
    INSTANCE_ID,
    AuditLogger,
    AuditUnavailableError,
    get_audit_logger,
    seal_record,
)
from ...utils.audit_verify import VerifyReport, verify_records
from ...utils.logger import get_logger
from .models import AuditChainHead, AuditLogEntry

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

    async def append(self, record: dict[str, Any], *, key: bytes | None, strict: bool) -> None:
        """Chain and insert one record (payload fields already encrypted).

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
                async with self.engine.begin() as conn:
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
                return
            self._seq += 1
            self._prev_hash = record["hash"]


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


async def verify(engine: AsyncEngine, key: bytes | None) -> VerifyReport:
    """Verify every chain in the audit store, in insertion order.

    Raises:
        ChainKeyMissingError: If records are HMAC-chained and no key is given
    """
    query = select(AuditLogEntry.id, AuditLogEntry.record).order_by(AuditLogEntry.id)
    async with engine.connect() as conn:
        rows = [(f"row {r.id}", str(r.record)) for r in await conn.execute(query)]
    return verify_records(rows, key)


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
