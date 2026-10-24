"""Retention archives shared by the Postgres and JSONL stores (Phase 5c).

An archive is the stored records, unchanged, as gzip-compressed JSON lines,
next to a manifest (``<archive>.manifest.json``) giving its SHA-256, its
record count and each chain's first and last record. ``python -m
src.utils.audit_verify ARCHIVE --manifest MANIFEST`` checks one on its own.
"""

import contextlib
import gzip
import json
import os
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .audit_verify import file_sha256
from .exceptions import UniFiMCPException


class RetentionRefusedError(UniFiMCPException):
    """Raised when records cannot be archived safely, so nothing is deleted."""


@dataclass
class ChainArchive:
    """The records of one chain moved to an archive."""

    chain_id: str
    first_seq: int
    last_seq: int
    prev_hash: str
    last_hash: str
    records: int


@dataclass
class RetentionResult:
    """What a retention run archived (or, for a dry run, would archive)."""

    cutoff: datetime
    dry_run: bool
    records: int = 0
    chains: list[ChainArchive] = field(default_factory=list)
    archive: Path | None = None
    manifest: Path | None = None
    #: JSONL retention only: the rotated files removed (or that would be)
    files: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """A JSON-ready summary."""
        summary = {
            "cutoff": self.cutoff.isoformat(),
            "dry_run": self.dry_run,
            "records": self.records,
            "chains": [asdict(c) for c in self.chains],
            "archive": str(self.archive) if self.archive else None,
            "manifest": str(self.manifest) if self.manifest else None,
        }
        if self.files:
            summary["files"] = self.files
        return summary


def private_dir(path: Path) -> None:
    """Create ``path`` (and parents) owner-only; a new one is fsynced into its parent."""
    created = not path.exists()
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    if created:
        _fsync_dir(path.parent)


def _fsync_dir(path: Path) -> None:
    with contextlib.suppress(OSError):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def write_archive(
    archive_dir: Path, cutoff: datetime, lines: Iterable[str], chains: list[ChainArchive]
) -> tuple[Path, Path, str]:
    """Write an archive and its manifest durably (mode 0600, directory 0700).

    Args:
        archive_dir: Where archives go
        cutoff: Records before this time were archived (named in the file)
        lines: The stored records, one JSON document each
        chains: Each chain's first and last archived record

    Returns:
        ``(archive, manifest, archive SHA-256)``; on failure nothing is left behind
    """
    private_dir(archive_dir)
    name = f"audit-before-{cutoff.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}.jsonl.gz"
    archive = archive_dir / name
    manifest = archive_dir / f"{name}.manifest.json"
    partial = archive.with_name(name + ".partial")
    count = 0
    try:
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as f:
                for line in lines:
                    f.write(line.rstrip("\n").encode("utf-8") + b"\n")
                    count += 1
            raw.flush()
            os.fsync(raw.fileno())
        partial.rename(archive)
        digest = file_sha256(archive)
        fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(
                {
                    "archive": name,
                    "sha256": digest,
                    "records": count,
                    "cutoff": cutoff.isoformat(),
                    "created_at": datetime.now(UTC).isoformat(),
                    "chains": [asdict(c) for c in chains],
                },
                out,
                indent=2,
            )
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        # Both new entries must survive a power loss before any record is deleted.
        _fsync_dir(archive_dir)
    except BaseException:
        remove(partial, archive, manifest)
        raise
    return archive, manifest, digest


def remove(*paths: Path) -> None:
    """Delete files, ignoring ones already gone."""
    for path in paths:
        with contextlib.suppress(OSError):
            path.unlink()
