"""Operator CLI to decrypt an audit log file.

Usage::

    UNIFI_AUDIT_LOG_KEY=... python -m src.utils.audit_decrypt /var/log/unifi-mcp/audit.log
    python -m src.utils.audit_decrypt audit.log --key gAAAA... --operation create_wlan --limit 50

Reads JSON-lines audit records, decrypts the ``parameters`` and ``error``
payloads using the configured key(s), and prints one decrypted JSON object
per line. Metadata (timestamp, operation, result, site_id, user) passes
through untouched. Undecryptable fields print as ``<undecryptable: field>``
placeholders; the exit code stays 0 so the command is safe in pipelines.

The key is read from the ``UNIFI_AUDIT_LOG_KEY`` environment variable unless
``--key`` is given. Key material is never echoed to stdout or logs.

Generate a fresh key with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import argparse
import json
import sys
from pathlib import Path

from .audit import AuditLogger
from .audit_encryption import AuditEncryptionError, resolve_audit_cipher


def main(argv: list[str] | None = None) -> int:
    """Run the audit-log decryption CLI.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code: 0 on success (including per-entry decrypt
        failures, which are reported inline), 2 on usage/key errors.
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.utils.audit_decrypt",
        description="Decrypt an encrypted audit log file (issue #22).",
    )
    parser.add_argument("log_file", type=Path, help="Path to the audit log file.")
    parser.add_argument(
        "--key",
        default=None,
        help=(
            "Encryption key (or comma-separated keys, newest first). "
            "Prefer the UNIFI_AUDIT_LOG_KEY environment variable so the key "
            "does not appear in shell history."
        ),
    )
    parser.add_argument("--operation", default=None, help="Filter by operation name.")
    parser.add_argument("--limit", type=int, default=100, help="Max entries (default: 100).")
    args = parser.parse_args(argv)

    if args.key is not None:
        import os

        cipher = resolve_audit_cipher({**os.environ, "UNIFI_AUDIT_LOG_KEY": args.key})
    else:
        cipher = resolve_audit_cipher()

    if cipher is None:
        print(
            "error: no audit encryption key configured; set UNIFI_AUDIT_LOG_KEY or pass --key",
            file=sys.stderr,
        )
        return 2

    if not args.log_file.exists():
        print(f"error: log file not found: {args.log_file}", file=sys.stderr)
        return 2

    logger = AuditLogger(log_file=args.log_file, encryption=cipher)
    try:
        entries = logger.get_recent_operations(limit=args.limit, operation=args.operation)
    except AuditEncryptionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    for entry in entries:
        print(json.dumps(entry, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
