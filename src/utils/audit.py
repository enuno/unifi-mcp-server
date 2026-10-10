"""Audit logging for mutating operations.

Every record appended to the audit file is hash-chained: it carries the
writer's ``chain_id``, a ``seq`` number, the previous record's hash, and its
own ``hash`` over the stored (redacted, possibly encrypted) record. With
``UNIFI_AUDIT_CHAIN_KEY`` set the hash is an HMAC-SHA256, so the chain cannot
be recomputed by someone who can only edit the file. ``python -m
src.utils.audit_verify`` checks a file (docs/FLEET_SCALING_PLAN.md §3.7).
"""

import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from cryptography.fernet import MultiFernet

from .audit_encryption import (
    AuditEncryptionError,
    decrypt_field,
    encrypt_field,
    resolve_audit_cipher,
)
from .exceptions import UniFiMCPException
from .helpers import get_iso_timestamp
from .logger import get_logger
from .sanitize import sanitize_credentials

#: Environment variable holding the HMAC key for the audit hash chain.
CHAIN_KEY_ENV = "UNIFI_AUDIT_CHAIN_KEY"

#: ``prev_hash`` of the first record in a chain.
GENESIS_HASH = "0" * 64

#: Identifies this process's chain in a shared audit file.
INSTANCE_ID = uuid.uuid4().hex

#: Payload fields that carry operation data and are encrypted at rest.
_PAYLOAD_FIELDS = ("parameters", "error", "details")


class AuditUnavailableError(UniFiMCPException):
    """Raised when a required audit record cannot be written."""


def resolve_chain_key(env: dict[str, str] | None = None) -> bytes | None:
    """Return the audit chain HMAC key from the environment, if set."""
    raw = (os.environ if env is None else env).get(CHAIN_KEY_ENV, "").strip()
    return raw.encode("utf-8") if raw else None


def record_hash(record: dict[str, Any], key: bytes | None) -> str:
    """Hash a stored audit record (every field except ``hash`` itself).

    Args:
        record: The record as written to disk
        key: HMAC key; plain SHA-256 when None

    Returns:
        Hex digest
    """
    body = {k: v for k, v in record.items() if k != "hash"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if key is not None:
        return hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _Chain:
    """Position of this process's chain in one audit file."""

    def __init__(self) -> None:
        self.seq = 0
        self.prev_hash = GENESIS_HASH


#: Chains by resolved audit file path; one lock orders seq numbers and writes.
_chains: dict[str, _Chain] = {}
_chain_lock = threading.Lock()

#: Detail reports collected for the wrapper-level record of the tool call in
#: progress; ``None`` outside such a call. See :class:`ToolCallRecorder`.
_active_tool_call: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "unifi_active_tool_call", default=None
)


class AuditLogger:
    """Audit logger for tracking mutating operations."""

    def __init__(
        self,
        log_file: str | Path | None = None,
        log_level: str = "INFO",
        encryption: MultiFernet | None = None,
    ):
        """Initialize audit logger.

        Args:
            log_file: Path to audit log file. If None, uses default location.
            log_level: Logging level
            encryption: Optional ``MultiFernet`` for at-rest encryption of
                sensitive payload fields (``parameters``, ``error``). When
                omitted, the key is resolved from the
                ``UNIFI_AUDIT_LOG_KEY`` environment variable; when neither
                is present, records are written in the historical plaintext
                format (backward compatible). When a key *is* configured
                but invalid, construction fails closed with
                :class:`AuditEncryptionError` rather than silently writing
                plaintext the operator believed was encrypted.

        Raises:
            AuditEncryptionError: If a key is configured but unusable.
        """
        self.log_file = Path(log_file) if log_file else Path("audit.log")
        self.logger = get_logger(__name__, log_level)
        # None means "not specified" → resolve from the environment.
        # Explicitly passing a cipher (including one built from env by a
        # caller) skips re-resolution so tests and embeddings control wiring.
        self.cipher = resolve_audit_cipher() if encryption is None else encryption
        self.chain_key = resolve_chain_key()

        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _opener(path: str, flags: int) -> int:
        """Open the audit log owner-readable only.

        The record contains operation parameters, so it must not be created
        with the default 0644 an unrestricted umask would give it.
        """
        return os.open(path, flags, 0o600)

    def log_operation(
        self,
        operation: str,
        parameters: dict[str, Any],
        result: str,
        user: str | None = None,
        site_id: str | None = None,
        dry_run: bool = False,
        error: str | None = None,
    ) -> None:
        """Log a mutating operation.

        Args:
            operation: Name of the operation (e.g., "create_firewall_rule")
            parameters: Parameters passed to the operation
            result: Result of the operation ("success", "failed", "dry_run")
            user: User who performed the operation (optional)
            error: Error message if the operation failed (optional)
            site_id: Site ID where operation was performed
            dry_run: Whether this was a dry run
        """
        reports = _active_tool_call.get()
        if reports is not None:
            # Inside a wrapper-audited tool call: the wrapper writes one record
            # for the whole call; this report becomes part of it.
            report: dict[str, Any] = {
                "operation": operation,
                "result": result,
                "parameters": sanitize_credentials(parameters),
            }
            if site_id:
                report["site_id"] = site_id
            if error:
                report["error"] = error
            reports.append(report)
            return

        timestamp = get_iso_timestamp()

        # Redact credentials because tools pass their request payloads
        # straight through, and several carry secrets (RADIUS shared secrets,
        # WLAN passphrases, IPsec PSKs). The record is persisted, so this
        # cannot be left to call sites. Identifiers are deliberately kept: an
        # audit trail that cannot say which site or resource was touched has
        # lost its purpose.
        audit_record = {
            "timestamp": timestamp,
            "operation": operation,
            "parameters": sanitize_credentials(parameters),
            "result": result,
            "dry_run": dry_run,
        }

        if user:
            audit_record["user"] = user

        if site_id:
            audit_record["site_id"] = site_id

        if error:
            audit_record["error"] = error

        self._write(audit_record, strict=False)

        # Log to application logger
        log_message = f"AUDIT: {operation} - {result}"
        if dry_run:
            log_message += " (DRY RUN)"

        if result == "success":
            self.logger.info(log_message, extra=audit_record)
        elif result == "failed":
            self.logger.warning(log_message, extra=audit_record)
        else:
            self.logger.info(log_message, extra=audit_record)

    def log_event(
        self,
        event_type: str,
        operation: str,
        result: str,
        *,
        parameters: dict[str, Any] | None = None,
        error: str | None = None,
        strict: bool = False,
        **fields: Any,
    ) -> dict[str, Any]:
        """Write one schema-v2 audit record.

        Args:
            event_type: ``tool_call``, ``denied``, ``admin`` or ``system``
            operation: Tool or event name (kept as ``operation`` so v1 readers
                and filters still work)
            result: Outcome, e.g. ``attempt``, ``success``, ``error``,
                ``dry_run``, ``denied``
            parameters: Call arguments; credentials are redacted
            error: Error text, if any
            strict: Raise :class:`AuditUnavailableError` if the write fails
                instead of logging the failure
            **fields: Further record fields; ``None`` values are omitted

        Returns:
            The record as written
        """
        record: dict[str, Any] = {
            "v": 2,
            "event_id": uuid.uuid4().hex,
            "timestamp": get_iso_timestamp(),
            "event_type": event_type,
            "operation": operation,
            "result": result,
            "instance_id": INSTANCE_ID,
        }
        if parameters is not None:
            record["parameters"] = sanitize_credentials(parameters)
        if error:
            record["error"] = error
        record.update({key: value for key, value in fields.items() if value is not None})
        self._write(record, strict=strict)
        self.logger.info(f"AUDIT: {event_type} {operation} - {result}")
        return record

    def _write(self, record: dict[str, Any], *, strict: bool) -> None:
        """Encrypt payload fields, chain the record, and append it to the file.

        Args:
            record: The record; payload fields must already be redacted
            strict: Raise :class:`AuditUnavailableError` on failure instead
                of logging it

        Raises:
            AuditUnavailableError: When ``strict`` and the record was not written
        """
        # At-rest encryption for the sensitive payloads (issue #22). This
        # runs on the already-redacted record: encryption complements
        # redaction, it does not replace it, so a decrypted entry is exactly
        # the redacted record an operator would see without a key. Controller
        # error text is encrypted too — errors quote offending values back
        # (e.g. "api.err.MacUsed for aa:bb:cc:dd:ee:ff"), so encrypting
        # parameters alone would still leak identifiers to disk. The caller
        # passes the same ciphertext record to the application logger,
        # keeping plaintext payloads out of stdout/stderr logs when
        # encryption is enabled (CodeQL py/clear-text-logging).
        if self.cipher is not None:
            for field in _PAYLOAD_FIELDS:
                if field in record:
                    record[field] = encrypt_field(self.cipher, record[field])
                    record[f"{field}_encrypted"] = True

        with _chain_lock:
            chain = _chains.setdefault(str(self.log_file.resolve()), _Chain())
            record["chain_id"] = INSTANCE_ID
            record["seq"] = chain.seq
            record["prev_hash"] = chain.prev_hash
            record["hash_alg"] = "hmac-sha256" if self.chain_key is not None else "sha256"
            record["hash"] = record_hash(record, self.chain_key)
            try:
                with open(self.log_file, "a", encoding="utf-8", opener=self._opener) as f:
                    f.write(json.dumps(record) + "\n")
            except Exception as e:
                if strict:
                    raise AuditUnavailableError(f"Audit log unavailable: {e}") from e
                self.logger.error(f"Failed to write audit log: {e}")
                return
            chain.seq += 1
            chain.prev_hash = record["hash"]

    def _decrypt_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Decrypt the encrypted payload fields of one audit entry, in place.

        Args:
            entry: A parsed audit record. Records without encryption
                markers are returned unchanged (historical plaintext stays
                readable after enabling encryption, and after rotation).

        Returns:
            The entry with ``parameters`` / ``error`` decrypted and the
            ``*_encrypted`` markers removed. If a field cannot be decrypted
            (wrong key, tampered token, or no key configured), the field is
            replaced with a ``<undecryptable: field>`` placeholder and a
            warning is logged — one bad line must not cost the rest of the
            trail, but it must not pass silently either.
        """
        for field in _PAYLOAD_FIELDS:
            if not entry.get(f"{field}_encrypted"):
                continue
            token = entry[field]
            try:
                if self.cipher is None:
                    raise AuditEncryptionError(
                        f"Audit log entry has encrypted {field} but no key is configured."
                    )
                entry[field] = decrypt_field(self.cipher, token)
            except AuditEncryptionError as e:
                self.logger.warning(f"Cannot decrypt audit log {field}: {e}")
                entry[field] = f"<undecryptable: {field}>"
            del entry[f"{field}_encrypted"]
        return entry

    def get_recent_operations(
        self, limit: int = 100, operation: str | None = None
    ) -> list[dict[str, Any]]:
        """Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return
            operation: Filter by operation name (optional)

        Returns:
            List of audit log entries. Encrypted payload fields are
            decrypted when a usable key is configured; metadata stays
            readable either way.
        """
        if not self.log_file.exists():
            return []

        entries = []
        try:
            with open(self.log_file, encoding="utf-8") as f:
                # Read file in reverse to get most recent entries first
                lines = f.readlines()
                for line in reversed(lines):
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        if operation is None or entry.get("operation") == operation:
                            entries.append(self._decrypt_entry(entry))

                        if len(entries) >= limit:
                            break
                    except json.JSONDecodeError:
                        self.logger.warning(f"Invalid JSON in audit log: {line}")
                        continue

        except Exception as e:
            self.logger.error(f"Failed to read audit log: {e}")

        return entries


class ToolCallRecorder:
    """Writes the wrapper-level audit records of one mutating tool call.

    :meth:`attempt` writes a record before the tool contacts a controller;
    :meth:`outcome` writes the result. Manual ``log_audit`` calls the tool
    makes in between are folded into the outcome record's ``details`` instead
    of becoming records of their own, so each call yields one attempt and one
    outcome record that share a ``call_id``.
    """

    def __init__(self, logger: AuditLogger, *, fail_closed: bool, **fields: Any) -> None:
        """Prepare the records for one call.

        Args:
            logger: Where records are written
            fail_closed: Refuse the call if the attempt record cannot be written
            **fields: Fields common to both records: ``operation``,
                ``parameters`` and context such as ``tool``, ``tier``,
                ``controller``, ``principal``, ``user``, ``site_id``,
                ``session_id``, ``request_id``
        """
        self._logger = logger
        self._fail_closed = fail_closed
        self._fields = {"call_id": uuid.uuid4().hex, **fields}
        self._reports: list[dict[str, Any]] = []
        self._token: Any = None
        self._started = 0.0

    def attempt(self) -> None:
        """Write the attempt record and start collecting tool reports.

        Raises:
            AuditUnavailableError: If the record cannot be written and the
                recorder fails closed
        """
        self._logger.log_event(
            "tool_call", result="attempt", strict=self._fail_closed, **self._fields
        )
        self._token = _active_tool_call.set(self._reports)
        self._started = time.perf_counter()

    def outcome(self, result: str, error: str | None = None) -> None:
        """Write the outcome record.

        Args:
            result: ``success``, ``error`` or ``dry_run``
            error: Error text when the tool raised
        """
        if self._token is not None:
            _active_tool_call.reset(self._token)
            self._token = None
        duration_ms = round((time.perf_counter() - self._started) * 1000, 3)
        self._logger.log_event(
            "tool_call",
            result=result,
            error=error,
            details=self._reports or None,
            duration_ms=duration_ms,
            **self._fields,
        )


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger(log_file: str | Path | None = None, log_level: str = "INFO") -> AuditLogger:
    """Get or create the global audit logger instance.

    Args:
        log_file: Path to audit log file
        log_level: Logging level

    Returns:
        AuditLogger instance
    """
    global _audit_logger

    if _audit_logger is None:
        _audit_logger = AuditLogger(log_file, log_level)

    return _audit_logger


def log_audit(
    operation: str,
    parameters: dict[str, Any],
    result: str,
    user: str | None = None,
    site_id: str | None = None,
    dry_run: bool = False,
    error: str | None = None,
    log_file: str | Path | None = None,
) -> None:
    """Convenience function to log an audit entry.

    Args:
        operation: Name of the operation
        parameters: Parameters passed to the operation
        result: Result of the operation
        user: User who performed the operation
        site_id: Site ID where operation was performed
        dry_run: Whether this was a dry run
        error: Error message if the operation failed
        log_file: Path to audit log file
    """
    logger = get_audit_logger(log_file)
    logger.log_operation(operation, parameters, result, user, site_id, dry_run, error)


async def audit_action(
    settings: Any,
    action_type: str,
    resource_type: str,
    resource_id: str,
    site_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Audit a mutating action.

    Args:
        settings: Application settings
        action_type: Type of action (e.g., "create_firewall_zone")
        resource_type: Type of resource (e.g., "firewall_zone")
        resource_id: Resource identifier
        site_id: Site identifier
        details: Additional details about the action
    """
    if not getattr(settings, "audit_log_enabled", True):
        return

    parameters = {
        "action_type": action_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "site_id": site_id,
    }

    params_to_log: dict[str, Any] = dict(parameters)
    if details:
        params_to_log["details"] = details

    # Get audit log file from settings if available
    log_file = getattr(settings, "audit_log_file", None)

    log_audit(
        operation=action_type,
        parameters=params_to_log,
        result="success",
        site_id=site_id,
        log_file=log_file,
    )
