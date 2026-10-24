"""Audit retention for the JSONL file (docs/FLEET_SCALING_PLAN.md §3.7, Phase 5c).

Usage::

    python -m src.utils.audit_retention /var/log/unifi-mcp/audit.log --days 365
    python -m src.utils.audit_retention /var/log/unifi-mcp/audit.log --days 365 --confirm

With ``UNIFI_AUDIT_LOG_ROTATE_MB`` set the server rotates the audit file into
``<log>.<UTC time>Z`` files. This removes the oldest rotated files whose every
record is older than the retention period; the file being written is never
touched, so it is safe while the server runs. First the whole log (rotated
files and the current one) is verified; any problem refuses the run. Then the
expired files go into one archive with a manifest (see
:mod:`src.utils.audit_archive`), each chain's last archived record is appended
to ``<log>.checkpoints.jsonl``, and only then are the files deleted. Verify
what remains with::

    python -m src.utils.audit_verify audit.log.[0-9]* audit.log --checkpoints audit.log.checkpoints.jsonl

If a run stops between writing its checkpoints and deleting its files, the
next run deletes them first (they are in the archive).

Exit codes: 0 done (or nothing to do), 1 refused, 2 usage error or missing key.
"""

import argparse
import contextlib
import json
import os
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .audit import AuditLogger, AuditUnavailableError, audit_files, resolve_chain_key
from .audit_archive import (
    ChainArchive,
    RetentionRefusedError,
    RetentionResult,
    remove,
    write_archive,
)
from .audit_verify import (
    ChainKeyMissingError,
    UnreadableLogError,
    checkpoint_batches,
    checkpoints_path,
    file_sha256,
    read_checkpoints,
    verify_files,
)


def _delete(paths: list[Path]) -> None:
    """Delete files; one already gone is fine, any other failure is raised."""
    for path in paths:
        with contextlib.suppress(FileNotFoundError):  # already gone: nothing to do
            path.unlink()


def _finish_interrupted(
    log_file: Path, batches: list[dict[str, Any]], archive_dir: Path
) -> list[str]:
    """Delete files the latest run checkpointed but did not delete.

    Only once that run's archive is confirmed intact: if it is missing or
    changed, the files may be the only good copy, so nothing is deleted.

    Raises:
        RetentionRefusedError: If the archive is missing or does not match
    """
    if not batches:
        return []
    latest = batches[-1]
    left = [log_file.with_name(name) for name in latest["files"]]
    left = [p for p in left if p.exists() and p != log_file]
    if not left:
        return []
    archive = archive_dir / str(latest["archive"])
    if not archive.exists() or file_sha256(archive) != latest["sha256"]:
        raise RetentionRefusedError(
            f"A previous run archived {len(left)} file(s) to {archive} but did not delete them, "
            "and that archive is missing or changed; nothing was deleted. Restore the archive "
            "(or point --archive-dir at it) and run again."
        )
    _delete(left)
    return [p.name for p in left]


def _append_batch(path: Path, batch: dict[str, Any]) -> None:
    """Append one checkpoint batch as a single line, durably."""
    created = not path.exists()
    data = (json.dumps(batch) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        written = os.write(fd, data)
        if written != len(data):  # pragma: no cover - a short append is a disk error
            raise OSError(f"short write to {path}")
        os.fsync(fd)
    finally:
        os.close(fd)
    if created:
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def _records(paths: list[Path]) -> Iterator[str]:
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield line


def _timestamp(record: dict[str, Any]) -> datetime | None:
    stamp = record.get("timestamp")
    if not isinstance(stamp, str):
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _expired(path: Path, cutoff: datetime) -> bool:
    """Every record in ``path`` is older than ``cutoff`` (and so is the file)."""
    if datetime.fromtimestamp(path.stat().st_mtime, UTC) >= cutoff:
        return False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            stamp = _timestamp(json.loads(line))
            if stamp is None or stamp >= cutoff:
                return False
    return True


def purge_expired_files(
    log_file: Path,
    key: bytes | None,
    *,
    retention_days: int,
    archive_dir: Path,
    dry_run: bool = True,
    now: datetime | None = None,
    audit: AuditLogger | None = None,
) -> RetentionResult:
    """Archive and delete the rotated audit files older than ``retention_days``.

    Args:
        log_file: The audit file being written (never removed)
        key: The chain HMAC key
        retention_days: Keep records this many days
        archive_dir: Where archives go (created mode 0700)
        dry_run: Report what would be archived without writing or deleting
        now: The current time (tests)
        audit: Writes the run's ``audit_retention`` admin event (strictly,
            before anything is deleted; none when omitted)

    Raises:
        AuditUnavailableError: If the admin event could not be written (the
            archive is removed again and nothing is deleted)
        UnreadableLogError: If a file cannot be read
        RetentionRefusedError: If the log does not verify
        ChainKeyMissingError: If records are HMAC-chained and no key is given
        ValueError: For a bad ``retention_days`` or checkpoint file
    """
    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    result = RetentionResult(cutoff=cutoff, dry_run=dry_run)
    checkpoints = checkpoints_path(log_file)
    batches = checkpoint_batches(checkpoints)
    if not dry_run:
        finished = _finish_interrupted(log_file, batches, archive_dir)
        if finished:
            print(f"Removed {len(finished)} file(s) a previous run archived", file=sys.stderr)

    files = audit_files(log_file)
    starts = read_checkpoints(checkpoints) if checkpoints.exists() else {}
    report = verify_files(files, key, starts=starts)
    if not report.ok:
        raise RetentionRefusedError(
            "The audit log does not verify, so nothing was archived or deleted: "
            + "; ".join(report.problems[:5])
            + (f" (and {len(report.problems) - 5} more)" if len(report.problems) > 5 else "")
        )

    expired: list[Path] = []
    for path in files:
        if path == log_file or not _expired(path, cutoff):
            break  # files are in order: everything after a kept one stays
        expired.append(path)
    if not expired:
        return result

    count = 0
    chains: dict[str, ChainArchive] = {}
    for line in _records(expired):  # one pass for the manifest, nothing kept in memory
        count += 1
        record = json.loads(line)
        if "hash" not in record:
            continue  # legacy, unchained
        chain_id, seq = str(record["chain_id"]), int(record["seq"])
        if chain_id in chains:
            chain = chains[chain_id]
            chain.last_seq, chain.last_hash = seq, str(record["hash"])
            chain.records += 1
        else:
            chains[chain_id] = ChainArchive(
                chain_id=chain_id,
                first_seq=seq,
                last_seq=seq,
                prev_hash=str(record["prev_hash"]),
                last_hash=str(record["hash"]),
                records=1,
            )
    result.records = count
    result.chains = [chains[c] for c in sorted(chains)]
    result.files = [p.name for p in expired]
    if dry_run:
        return result

    archive, manifest, digest = write_archive(archive_dir, cutoff, _records(expired), result.chains)
    if audit is not None:
        try:
            audit.log_event(
                "admin",
                "audit_retention",
                "success",
                parameters={
                    "retention_days": retention_days,
                    "cutoff": cutoff.isoformat(),
                    "records": result.records,
                    "files": len(result.files),
                    "archive": archive.name,
                },
                strict=True,
            )
        except BaseException:
            remove(archive, manifest)  # nothing deleted without its record
            raise
    _append_batch(
        checkpoints,
        {
            "archive": archive.name,
            "sha256": digest,
            "files": result.files,
            "archived_at": datetime.now(UTC).isoformat(),
            "chains": [
                {"chain_id": c.chain_id, "seq": c.last_seq, "hash": c.last_hash}
                for c in result.chains
            ],
        },
    )
    _delete(expired)
    result.archive, result.manifest = archive, manifest
    return result


def main(argv: list[str] | None = None) -> int:
    """Run JSONL audit retention.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``)

    Returns:
        Process exit code
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.utils.audit_retention",
        description="Archive and delete rotated audit files past the retention period.",
    )
    parser.add_argument("log_file", type=Path, help="The audit log file (not a rotated one)")
    parser.add_argument(
        "--days", type=int, default=None, help="Default: UNIFI_AUDIT_RETENTION_DAYS"
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=None,
        help="Default: UNIFI_AUDIT_ARCHIVE_DIR, else audit-archive next to the log",
    )
    parser.add_argument(
        "--confirm", action="store_true", help="Archive and delete (without it: a dry run)"
    )
    parser.add_argument("--key", default=None, help="Chain key (default: UNIFI_AUDIT_CHAIN_KEY)")
    args = parser.parse_args(argv)

    days = args.days
    if days is None and os.environ.get("UNIFI_AUDIT_RETENTION_DAYS", "").strip():
        raw = os.environ["UNIFI_AUDIT_RETENTION_DAYS"].strip()
        days = int(raw) if raw.isdigit() else 0
    if days is None or days < 1:
        print("error: set UNIFI_AUDIT_RETENTION_DAYS or pass --days N (N >= 1)", file=sys.stderr)
        return 2
    read_only = os.environ.get("UNIFI_READ_ONLY", "").strip().lower() in ("1", "true", "yes", "on")
    if args.confirm and read_only:
        print("error: UNIFI_READ_ONLY is set; run without --confirm for a dry run", file=sys.stderr)
        return 2
    archive_dir = args.archive_dir or (
        Path(os.environ["UNIFI_AUDIT_ARCHIVE_DIR"])
        if os.environ.get("UNIFI_AUDIT_ARCHIVE_DIR", "").strip()
        else args.log_file.parent / "audit-archive"
    )
    key = args.key.encode("utf-8") if args.key else resolve_chain_key()

    try:
        result = purge_expired_files(
            args.log_file,
            key,
            retention_days=days,
            archive_dir=archive_dir,
            dry_run=not args.confirm,
            audit=AuditLogger(args.log_file),
        )
    except (RetentionRefusedError, UnreadableLogError, AuditUnavailableError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except (ChainKeyMissingError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result.as_dict(), indent=2))
    if not args.confirm:
        print(
            f"Dry run: {result.records} record(s) in {len(result.files)} file(s) would be "
            "archived; pass --confirm to do it",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
