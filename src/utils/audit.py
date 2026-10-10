"""Audit logging for mutating operations."""

import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import MultiFernet

from .audit_encryption import (
    AuditEncryptionError,
    decrypt_field,
    encrypt_field,
    resolve_audit_cipher,
)
from .helpers import get_iso_timestamp
from .logger import get_logger
from .sanitize import sanitize_credentials


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

        # At-rest encryption for the sensitive payloads (issue #22). This
        # runs on the already-redacted record: encryption complements the
        # redaction above, it does not replace it, so a decrypted entry is
        # exactly the redacted record an operator would see without a key.
        # Controller error text is encrypted too — errors quote offending
        # values back (e.g. "api.err.MacUsed for aa:bb:cc:dd:ee:ff"), so
        # encrypting parameters alone would still leak identifiers to disk.
        # The same ciphertext record is also passed to the application
        # logger below, keeping plaintext payloads out of stdout/stderr logs
        # when encryption is enabled (CodeQL py/clear-text-logging).
        if self.cipher is not None:
            audit_record["parameters"] = encrypt_field(self.cipher, audit_record["parameters"])
            audit_record["parameters_encrypted"] = True
            if "error" in audit_record:
                audit_record["error"] = encrypt_field(self.cipher, audit_record["error"])
                audit_record["error_encrypted"] = True

        # Log to file
        try:
            with open(self.log_file, "a", encoding="utf-8", opener=self._opener) as f:
                f.write(json.dumps(audit_record) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}")

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
        for field in ("parameters", "error"):
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
