"""Audit retention for the Postgres store (docs/FLEET_SCALING_PLAN.md §3.7, Phase 5c).

Records older than ``UNIFI_AUDIT_RETENTION_DAYS`` are verified, written to a
gzip-compressed JSON-lines archive with a manifest of each chain's first and
last record, and only then deleted. Each chain loses a prefix only: a chain
keeps everything from its first record that is not yet expired, so its
remaining records still link to each other. ``audit_archives`` records where
each chain was cut, and :func:`~src.fleet.db.audit_store.verify` resumes the
chain right after it.

Run it as the schema owner (``python -m src.fleet.cli audit-retention``): the
append-only trigger lets only the table's owner delete, and only inside a
transaction that set ``unifi_mcp.audit_retention``. The server itself never
deletes audit records.
"""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from ...utils.audit_archive import (
    ChainArchive,
    RetentionRefusedError,
    RetentionResult,
    remove,
    write_archive,
)
from ...utils.audit_verify import GENESIS, Head, verify_records
from ...utils.logger import get_logger
from .models import AuditArchive, AuditLogEntry

logger = get_logger(__name__)

#: Rows deleted per statement.
DELETE_BATCH = 1000


__all__ = [
    "ChainArchive",
    "RetentionRefusedError",
    "RetentionResult",
    "archive_problems",
    "archived_starts",
    "purge_expired",
]


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


def _expired_prefixes(rows: list[Any], cutoff: datetime) -> dict[str, list[Any]]:
    """Per chain, its leading records older than ``cutoff`` (rows in seq order)."""
    prefixes: dict[str, list[Any]] = {}
    stopped: set[str] = set()
    for row in rows:
        if row.chain_id in stopped:
            continue
        if row.ts < cutoff:
            prefixes.setdefault(row.chain_id, []).append(row)
        else:
            stopped.add(row.chain_id)  # a later record kept means the rest stay too
    return prefixes


async def purge_expired(
    engine: AsyncEngine,
    key: bytes | None,
    *,
    retention_days: int,
    archive_dir: Path,
    dry_run: bool = True,
    now: datetime | None = None,
) -> RetentionResult:
    """Archive and delete audit records older than ``retention_days``.

    The whole store is verified first, and the expired records again in the
    deleting transaction; any problem refuses the run and deletes nothing.
    The archive and its manifest are on disk (fsynced) before the delete
    commits.

    Args:
        engine: An engine connected as the schema owner
        key: The chain HMAC key
        retention_days: Keep records this many days
        archive_dir: Where archives go (created mode 0700)
        dry_run: Report what would be archived without writing or deleting
        now: The current time (tests)

    Raises:
        RetentionRefusedError: If verification found problems
        ChainKeyMissingError: If records are HMAC-chained and no key is given
    """
    from .audit_store import verify

    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    result = RetentionResult(cutoff=cutoff, dry_run=dry_run)

    report = await verify(engine, key)
    if not report.ok:
        raise RetentionRefusedError(
            "The audit store does not verify, so nothing was archived or deleted: "
            + "; ".join(report.problems[:5])
            + (f" (and {len(report.problems) - 5} more)" if len(report.problems) > 5 else "")
        )

    written: list[Path] = []
    try:
        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="REPEATABLE READ")
            async with conn.begin():
                starts = await archived_starts(conn)
                chains = [
                    row.chain_id
                    for row in await conn.execute(
                        select(AuditLogEntry.chain_id)
                        .where(AuditLogEntry.ts < cutoff)
                        .group_by(AuditLogEntry.chain_id)
                    )
                ]
                if not chains:
                    return result
                rows = list(
                    (
                        await conn.execute(
                            select(AuditLogEntry)
                            .where(AuditLogEntry.chain_id.in_(chains))
                            .order_by(AuditLogEntry.chain_id, AuditLogEntry.seq)
                        )
                    ).all()
                )
                prefixes = _expired_prefixes(rows, cutoff)
                expired = [row for chain in sorted(prefixes) for row in prefixes[chain]]

                recheck = verify_records(
                    ((f"row {row.id}", str(row.record)) for row in expired), key, starts=starts
                )
                if not recheck.ok:
                    raise RetentionRefusedError(
                        "Expired records changed since verification: "
                        + "; ".join(recheck.problems[:5])
                    )
                for chain_id in sorted(prefixes):
                    chain_rows = prefixes[chain_id]
                    result.chains.append(
                        ChainArchive(
                            chain_id=chain_id,
                            first_seq=int(chain_rows[0].seq),
                            last_seq=int(chain_rows[-1].seq),
                            prev_hash=starts.get(chain_id, GENESIS)[1],
                            last_hash=str(chain_rows[-1].hash),
                            records=len(chain_rows),
                        )
                    )
                result.records = len(expired)
                if dry_run or not expired:
                    return result

                archive, manifest, digest = write_archive(
                    archive_dir, cutoff, (str(row.record) for row in expired), result.chains
                )
                written += [archive, manifest]
                await conn.execute(text("SET LOCAL unifi_mcp.audit_retention = 'on'"))
                ids = [int(row.id) for row in expired]
                for start in range(0, len(ids), DELETE_BATCH):
                    await conn.execute(
                        delete(AuditLogEntry).where(
                            AuditLogEntry.id.in_(ids[start : start + DELETE_BATCH])
                        )
                    )
                await conn.execute(
                    insert(AuditArchive),
                    [
                        {
                            **asdict(c),
                            "archive": archive.name,
                            "archive_sha256": digest,
                            "cutoff": cutoff,
                        }
                        for c in result.chains
                    ],
                )
    except Exception:
        # Nothing was deleted (the transaction did not commit): the records are
        # still in the store, and an archive without its delete would only
        # confuse a later audit.
        remove(*written)
        raise
    result.archive, result.manifest = archive, manifest
    logger.info(
        "Archived %d audit record(s) from %d chain(s) older than %s to %s",
        result.records,
        len(result.chains),
        cutoff.isoformat(),
        archive,
    )
    return result
