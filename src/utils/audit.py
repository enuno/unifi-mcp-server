"""Audit logging for mutating operations."""

import json
from pathlib import Path
from typing import Any

from .helpers import get_iso_timestamp
from .logger import get_logger


class AuditLogger:
    """Audit logger for tracking mutating operations."""

    def __init__(self, log_file: str | Path | None = None, log_level: str = "INFO"):
        """Initialize audit logger.

        Args:
            log_file: Path to audit log file. If None, uses default location.
            log_level: Logging level
        """
        self.log_file = Path(log_file) if log_file else Path("audit.log")
        self.logger = get_logger(__name__, log_level)

        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_operation(
        self,
        operation: str,
        parameters: dict[str, Any],
        result: str,
        user: str | None = None,
        site_id: str | None = None,
        dry_run: bool = False,
    ) -> None:
        """Log a mutating operation.

        Args:
            operation: Name of the operation (e.g., "create_firewall_rule")
            parameters: Parameters passed to the operation
            result: Result of the operation ("success", "failed", "dry_run")
            user: User who performed the operation (optional)
            site_id: Site ID where operation was performed
            dry_run: Whether this was a dry run
        """
        timestamp = get_iso_timestamp()

        # Create audit record
        audit_record = {
            "timestamp": timestamp,
            "operation": operation,
            "parameters": parameters,
            "result": result,
            "dry_run": dry_run,
        }

        if user:
            audit_record["user"] = user

        if site_id:
            audit_record["site_id"] = site_id

        # Log to file
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
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

    def get_recent_operations(
        self, limit: int = 100, operation: str | None = None
    ) -> list[dict[str, Any]]:
        """Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return
            operation: Filter by operation name (optional)

        Returns:
            List of audit log entries
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
                            entries.append(entry)

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
        log_file: Path to audit log file
    """
    logger = get_audit_logger(log_file)
    logger.log_operation(operation, parameters, result, user, site_id, dry_run)
