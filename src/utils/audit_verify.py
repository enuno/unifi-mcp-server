"""Verify the hash chains in an audit log file.

Usage::

    UNIFI_AUDIT_CHAIN_KEY=... python -m src.utils.audit_verify /var/log/unifi-mcp/audit.log

Each process appends its own chain (``chain_id``) to the file. For every
chain this checks that ``seq`` starts at 0 and has no gaps, that each record's
``prev_hash`` is the previous record's ``hash``, and that each ``hash``
matches the record. That detects edited, deleted, inserted and reordered
records. Records written before chaining existed are counted as legacy, but
an unchained record after a chained one is reported, since stripping the
chain fields would otherwise hide an edit.

Not detectable from the file alone: removing the *last* records of a chain,
or a whole chain. Anchoring chain heads outside the server covers that
(docs/FLEET_SCALING_PLAN.md §3.7).

Exit codes: 0 intact, 1 problems found, 2 usage error or missing key.
"""

import argparse
import json
import sys
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

    @property
    def ok(self) -> bool:
        """True when no problem was found."""
        return not self.problems


def verify_file(path: Path, key: bytes | None) -> VerifyReport:
    """Verify every chain in an audit file.

    Args:
        path: The audit log file
        key: The chain HMAC key, needed for ``hmac-sha256`` records

    Returns:
        What was checked and any problems, each naming its line number

    Raises:
        ChainKeyMissingError: If the file has HMAC-chained records and no key
    """
    report = VerifyReport()
    heads: dict[str, tuple[int, str]] = {}
    seen_chained = False

    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            report.records += 1
            try:
                record: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                report.problems.append(f"line {number}: not valid JSON")
                continue

            if "hash" not in record:
                if seen_chained:
                    report.problems.append(f"line {number}: unchained record after chained ones")
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
                report.problems.append(f"line {number}: hash does not match the record")

            chain_id = str(record.get("chain_id"))
            seq = record.get("seq")
            if chain_id not in heads:
                report.chains += 1
                if seq != 0 or record.get("prev_hash") != GENESIS_HASH:
                    report.problems.append(
                        f"line {number}: chain {chain_id[:8]} does not start at seq 0"
                    )
            else:
                last_seq, last_hash = heads[chain_id]
                if seq != last_seq + 1:
                    report.problems.append(
                        f"line {number}: chain {chain_id[:8]} expected seq {last_seq + 1}, "
                        f"found {seq}"
                    )
                if record.get("prev_hash") != last_hash:
                    report.problems.append(
                        f"line {number}: chain {chain_id[:8]} prev_hash does not match the "
                        "previous record"
                    )
            heads[chain_id] = (seq if isinstance(seq, int) else -1, record["hash"])

    return report


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
    args = parser.parse_args(argv)

    if not args.log_file.exists():
        print(f"error: log file not found: {args.log_file}", file=sys.stderr)
        return 2
    key = args.key.encode("utf-8") if args.key else resolve_chain_key()

    try:
        report = verify_file(args.log_file, key)
    except ChainKeyMissingError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

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
