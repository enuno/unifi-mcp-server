"""Verify the hash chains in an audit log file.

Usage::

    UNIFI_AUDIT_CHAIN_KEY=... python -m src.utils.audit_verify /var/log/unifi-mcp/audit.log
    ... audit_verify audit.log --head 4f9c...e2:1532:7d1a...b0   # an anchored head

Each process appends its own chain (``chain_id``) to the file. For every
chain this checks that ``seq`` starts at 0 and has no gaps, that each record's
``prev_hash`` is the previous record's ``hash``, and that each ``hash``
matches the record. That detects edited, deleted, inserted and reordered
records. Records written before chaining existed are counted as legacy, but
an unchained record after a chained one is reported, since stripping the
chain fields would otherwise hide an edit.

Not detectable from the records alone: removing the *last* records of a
chain, or a whole chain. Give the chain heads recorded elsewhere (``--head
CHAIN:SEQ:HASH``, e.g. from the SIEM or the Postgres ``audit_chain_heads``
table) and each chain must reach exactly that head
(docs/FLEET_SCALING_PLAN.md §3.7).

Exit codes: 0 intact, 1 problems found, 2 usage error or missing key.
"""

import argparse
import gzip
import hashlib
import json
import sys
import zlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .audit import GENESIS_HASH, record_hash, resolve_chain_key


class ChainKeyMissingError(Exception):
    """Raised when HMAC-chained records are found but no key was given."""


@dataclass
class VerifyReport:
    """Result of verifying one audit file."""

    records: int = 0
    legacy: int = 0
    chains: int = 0
    problems: list[str] = field(default_factory=list)
    #: The chains seen in the records
    chain_ids: set[str] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        """True when no problem was found."""
        return not self.problems


#: A chain's expected last record: ``(seq, hash)``.
Head = tuple[int, str]

#: Where a chain with nothing archived starts: before seq 0.
GENESIS: Head = (-1, GENESIS_HASH)


def verify_file(
    path: Path,
    key: bytes | None,
    expected_heads: Mapping[str, Head] | None = None,
    starts: Mapping[str, Head] | None = None,
) -> VerifyReport:
    """Verify every chain in an audit file (gzip-compressed when it ends in ``.gz``).

    Args:
        path: The audit log file, or an archive written by retention
        key: The chain HMAC key, needed for ``hmac-sha256`` records
        expected_heads: Chain heads recorded elsewhere, by chain id (see
            :func:`verify_records`)
        starts: Where chains whose earlier records were archived resume (see
            :func:`verify_records`)

    Returns:
        What was checked and any problems, each naming its line number

    Raises:
        ChainKeyMissingError: If the file has HMAC-chained records and no key
    """
    opener: Any = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return verify_records(
            ((f"line {number}", line) for number, line in enumerate(f, start=1)),
            key,
            expected_heads,
            starts,
        )


def verify_records(
    records: Iterable[tuple[str, str]],
    key: bytes | None,
    expected_heads: Mapping[str, Head] | None = None,
    starts: Mapping[str, Head] | None = None,
) -> VerifyReport:
    """Verify every chain in a sequence of stored records, in storage order.

    Args:
        records: ``(location, stored JSON)`` pairs, e.g. ``("line 3", ...)``
            for a file or ``("row 17", ...)`` for the Postgres audit store
        key: The chain HMAC key, needed for ``hmac-sha256`` records
        expected_heads: Chain heads recorded elsewhere, by chain id. Each
            named chain must end exactly at its head: fewer records means
            records were removed from the end (or the whole chain was), and
            more means the head record was rewritten or replaced.
        starts: For chains whose earlier records were archived and removed by
            retention, the last archived record as ``(seq, hash)``: the chain
            must resume right after it. A chain with a start and no records
            left is complete when its head is that start. Without a start a
            chain must begin at seq 0.

    Returns:
        What was checked and any problems, each naming its location

    Raises:
        ChainKeyMissingError: If there are HMAC-chained records and no key
    """
    report = VerifyReport()
    heads: dict[str, tuple[int, str]] = {}
    seen_chained = False

    for number, line in records:
        if not line.strip():
            continue
        report.records += 1
        try:
            record: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            report.problems.append(f"{number}: not valid JSON")
            continue

        if "hash" not in record:
            if seen_chained:
                report.problems.append(f"{number}: unchained record after chained ones")
            else:
                report.legacy += 1
            continue
        seen_chained = True

        if record.get("hash_alg") == "hmac-sha256":
            if key is None:
                raise ChainKeyMissingError(
                    "The file has HMAC-chained records: set UNIFI_AUDIT_CHAIN_KEY or pass --key"
                )
            expected = record_hash(record, key)
        else:
            expected = record_hash(record, None)
        if record["hash"] != expected:
            report.problems.append(f"{number}: hash does not match the record")

        chain_id = str(record.get("chain_id"))
        seq = record.get("seq")
        if chain_id not in heads:
            report.chains += 1
            report.chain_ids.add(chain_id)
            start_seq, start_hash = (starts or {}).get(chain_id, GENESIS)
            if seq != start_seq + 1 or record.get("prev_hash") != start_hash:
                where = "seq 0" if start_seq < 0 else f"seq {start_seq + 1} after its archive"
                report.problems.append(f"{number}: chain {chain_id[:8]} does not start at {where}")
        else:
            last_seq, last_hash = heads[chain_id]
            if seq != last_seq + 1:
                report.problems.append(
                    f"{number}: chain {chain_id[:8]} expected seq {last_seq + 1}, " f"found {seq}"
                )
            if record.get("prev_hash") != last_hash:
                report.problems.append(
                    f"{number}: chain {chain_id[:8]} prev_hash does not match the "
                    "previous record"
                )
        heads[chain_id] = (seq if isinstance(seq, int) else -1, record["hash"])

    for chain_id, (head_seq, head_hash) in sorted((expected_heads or {}).items()):
        label = f"chain {chain_id[:8]}"
        if chain_id not in heads and (starts or {}).get(chain_id) == (head_seq, head_hash):
            continue  # every record up to the head was archived
        if chain_id not in heads:
            report.problems.append(
                f"{label}: its recorded head is seq {head_seq} but none of its records remain"
            )
            continue
        last_seq, last_hash = heads[chain_id]
        if last_seq < head_seq:
            report.problems.append(
                f"{label}: ends at seq {last_seq} but its recorded head is seq {head_seq} "
                f"({head_seq - last_seq} record(s) missing from the end)"
            )
        elif last_seq > head_seq:
            report.problems.append(
                f"{label}: continues to seq {last_seq} past its recorded head at seq {head_seq}"
            )
        elif last_hash != head_hash:
            report.problems.append(
                f"{label}: its last record (seq {last_seq}) does not match the recorded head"
            )

    return report


@dataclass
class ArchiveManifest:
    """What retention recorded about one archive (``<archive>.manifest.json``)."""

    sha256: str
    records: int
    #: Per chain, the record before the archive's first one (``GENESIS`` for seq 0)
    starts: dict[str, Head]
    #: Per chain, the archive's last record
    heads: dict[str, Head]


def read_manifest(path: Path) -> ArchiveManifest:
    """Read an archive manifest written by audit retention.

    Raises:
        ValueError: If the file is not a manifest
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        chains = data["chains"]
        return ArchiveManifest(
            sha256=str(data["sha256"]),
            records=int(data["records"]),
            starts={
                str(c["chain_id"]): (int(c["first_seq"]) - 1, str(c["prev_hash"])) for c in chains
            },
            heads={str(c["chain_id"]): (int(c["last_seq"]), str(c["last_hash"])) for c in chains},
        )
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(f"not an audit archive manifest: {e}") from e


def file_sha256(path: Path) -> str:
    """Hex SHA-256 of a file's bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_head(value: str) -> tuple[str, Head]:
    """Parse ``CHAIN:SEQ:HASH`` (``--head``) into ``(chain_id, (seq, hash))``.

    Raises:
        ValueError: If the value is not in that form
    """
    chain_id, sep, rest = value.partition(":")
    seq_text, sep2, head_hash = rest.partition(":")
    if not (sep and sep2 and chain_id and head_hash and seq_text.isdigit()):
        raise ValueError(f"expected CHAIN:SEQ:HASH, got {value!r}")
    return chain_id, (int(seq_text), head_hash)


def main(argv: list[str] | None = None) -> int:
    """Run the audit-chain verification CLI.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``)

    Returns:
        Process exit code: 0 intact, 1 problems found, 2 usage error
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.utils.audit_verify",
        description="Verify the hash chains in an audit log file.",
    )
    parser.add_argument("log_file", type=Path, help="Path to the audit log file.")
    parser.add_argument(
        "--key",
        default=None,
        help=(
            "Chain HMAC key. Prefer the UNIFI_AUDIT_CHAIN_KEY environment variable so the "
            "key does not appear in shell history."
        ),
    )
    parser.add_argument(
        "--head",
        action="append",
        default=[],
        metavar="CHAIN:SEQ:HASH",
        help=(
            "A chain head recorded outside this file (repeatable). The chain must end "
            "exactly there, which detects records removed from its end."
        ),
    )
    parser.add_argument(
        "--anchors",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Chain anchors exported to the SIEM (JSON lines or a JSON array; other records "
            "are ignored). The latest anchor of each chain is used like --head."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Manifest of a retention archive (ARCHIVE.manifest.json): checks the archive's "
            "SHA-256 and that each chain runs exactly from its recorded start to its end."
        ),
    )
    args = parser.parse_args(argv)
    starts: dict[str, Head] = {}
    try:
        expected_heads = dict(parse_head(value) for value in args.head)
    except ValueError as e:
        print(f"error: --head: {e}", file=sys.stderr)
        return 2
    if args.anchors is not None:
        from .siem import load_anchors

        if not args.anchors.exists():
            print(f"error: anchors file not found: {args.anchors}", file=sys.stderr)
            return 2
        anchors = load_anchors(args.anchors)
        if not anchors:
            # A wrong or empty export must not pass as "truncation checked".
            print(f"error: no anchor events in {args.anchors}", file=sys.stderr)
            return 2
        expected_heads = {**anchors, **expected_heads}

    if not args.log_file.exists():
        print(f"error: log file not found: {args.log_file}", file=sys.stderr)
        return 2
    manifest_problems: list[str] = []
    if args.manifest is not None:
        try:
            manifest = read_manifest(args.manifest)
        except ValueError as e:
            print(f"error: --manifest: {e}", file=sys.stderr)
            return 2
        starts = manifest.starts
        expected_heads = {**manifest.heads, **expected_heads}
        if file_sha256(args.log_file) != manifest.sha256:
            manifest_problems.append("archive: SHA-256 does not match its manifest")
    key = args.key.encode("utf-8") if args.key else resolve_chain_key()

    try:
        report = verify_file(args.log_file, key, expected_heads, starts)
    except ChainKeyMissingError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (OSError, EOFError, UnicodeDecodeError, zlib.error) as e:
        # A truncated or corrupt archive (or an unreadable file) fails the check.
        print(f"FAILED: cannot read {args.log_file}: {type(e).__name__}: {e}")
        return 1

    report.problems[:0] = manifest_problems
    if args.manifest is not None:
        for chain_id in sorted(report.chain_ids - set(manifest.heads)):
            report.problems.append(f"archive: chain {chain_id[:8]} is not in its manifest")
    if args.manifest is not None and report.records != manifest.records:
        report.problems.append(
            f"archive: holds {report.records} record(s), its manifest says {manifest.records}"
        )
    for problem in report.problems:
        print(problem)
    status = "OK" if report.ok else f"FAILED ({len(report.problems)} problem(s))"
    print(
        f"{status}: {report.records} record(s), {report.chains} chain(s), "
        f"{report.legacy} legacy unchained record(s)"
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
