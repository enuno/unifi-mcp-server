"""What the ``audit_archives`` table says about each chain (migration 0005).

Shared by verification (``audit_store``) and retention (``retention``), so
neither imports the other for it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ...utils.audit_verify import GENESIS, Head
from .models import AuditArchive

__all__ = ["archive_problems", "archived_starts"]


async def archived_starts(conn: Any) -> dict[str, Head]:
    """Per chain, its latest archived record: where verification resumes."""
    rows = await conn.execute(
        select(AuditArchive.chain_id, AuditArchive.last_seq, AuditArchive.last_hash)
    )
    starts: dict[str, Head] = {}
    for row in rows:
        if row.last_seq > starts.get(row.chain_id, GENESIS)[0]:
            starts[str(row.chain_id)] = (int(row.last_seq), str(row.last_hash))
    return starts


async def archive_problems(conn: Any) -> list[str]:
    """Gaps or overlaps between one chain's successive archives."""
    rows = await conn.execute(
        select(AuditArchive).order_by(AuditArchive.chain_id, AuditArchive.first_seq)
    )
    problems = []
    last: dict[str, Head] = {}
    for row in rows:
        prev_seq, prev_hash = last.get(row.chain_id, GENESIS)
        if row.first_seq != prev_seq + 1 or row.prev_hash != prev_hash:
            problems.append(
                f"chain {row.chain_id[:8]}: archive {row.archive} does not continue "
                f"from seq {prev_seq}"
            )
        last[row.chain_id] = (int(row.last_seq), str(row.last_hash))
    return problems
