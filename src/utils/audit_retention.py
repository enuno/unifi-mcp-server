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

    python -m src.utils.audit_verify audit.log.* audit.log --checkpoints audit.log.checkpoints.jsonl

If a run stops between writing its checkpoints and deleting its files, the
next run deletes them first (they are in the archive).

Exit codes: 0 done (or nothing to do), 1 refused, 2 usage error or missing key.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
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
from .audit_verify import GENESIS, ChainKeyMissingError, Head, UnreadableLogError, verify_files


def checkpoints_path(log_file: Path) -> Path:
    """Where retention records the chain checkpoints of ``log_file``."""
    return log_file.with_name(f"{log_file.name}.checkpoints.jsonl")


def _checkpoint_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if not isinstance(entry, dict):
                raise TypeError("not an object")
            if "chain_id" in entry:  # a line without one only lists legacy files
                int(entry["seq"]), str(entry["chain_id"]), str(entry["hash"])
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise ValueError(f"line {number} is not a checkpoint: {e}") from e
        entries.append(entry)
    return entries


def read_checkpoints(path: Path) -> dict[str, Head]:
    """Per chain, its latest checkpoint ``(seq, hash)``: where it resumes.

    Raises:
        ValueError: If the file holds something other than checkpoints
    """
    if not path.exists():
        raise ValueError(f"{path} not found")
    starts: dict[str, Head] = {}
    for entry in _checkpoint_lines(path):
        if "chain_id" not in entry:
            continue
        chain_id, seq = str(entry["chain_id"]), int(entry["seq"])
        if seq > starts.get(chain_id, GENESIS)[0]:
            starts[chain_id] = (seq, str(entry["hash"]))
    return starts


def _finish_interrupted(log_file: Path, entries: list[dict[str, Any]]) -> list[str]:
    """Delete files the latest run archived and checkpointed but did not delete."""
    if not entries:
        return []
    latest = entries[-1].get("archive")
    names = {name for e in entries if e.get("archive") == latest for name in e.get("files", [])}
    left = [log_file.with_name(name) for name in sorted(names)]
    left = [p for p in left if p.exists() and p != log_file]
    remove(*left)
    return [p.name for p in left]


def _timestamp(record: dict[str, Any]) -> datetime | None:
    stamp = record.get("timestamp")
    if not isinstance(stamp, str):
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _expired(path: Path, cutoff: datetime) -> bool:
    """Every record in ``path`` is older than ``cutoff`` (and so is the file)."""
    if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) >= cutoff:
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
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    result = RetentionResult(cutoff=cutoff, dry_run=dry_run)
    checkpoints = checkpoints_path(log_file)
    entries = _checkpoint_lines(checkpoints)
    if not dry_run:
        finished = _finish_interrupted(log_file, entries)
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

    lines: list[str] = []
    chains: dict[str, ChainArchive] = {}
    for path in expired:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            lines.append(line)
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
    result.records = len(lines)
    result.chains = [chains[c] for c in sorted(chains)]
    result.files = [p.name for p in expired]
    if dry_run:
        return result

    archive, manifest, _ = write_archive(archive_dir, cutoff, lines, result.chains)
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
    archived_at = datetime.now(timezone.utc).isoformat()
    fd = os.open(checkpoints, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        for chain in result.chains:
            entry = {
                "chain_id": chain.chain_id,
                "seq": chain.last_seq,
                "hash": chain.last_hash,
                "archive": archive.name,
                "files": result.files,
                "archived_at": archived_at,
            }
            f.write(json.dumps(entry) + "\n")
        if not result.chains:  # only legacy records: still note the files
            f.write(
                json.dumps(
                    {"archive": archive.name, "files": result.files, "archived_at": archived_at}
                )
                + "\n"
            )
        f.flush()
        os.fsync(f.fileno())
    remove(*expired)
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
