"""A2A audit trail support.

The audit logger keeps an in-memory trail for filtered lookups while also
emitting structured events through the project's logging infrastructure.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from ..utils import get_logger, log_audit_event


@dataclass(slots=True)
class AuditLog:
    """Structured audit entry for delegated A2A operations."""

    timestamp: datetime
    agent_id: str
    tool_name: str
    params: dict[str, Any]
    result: Any
    safety_level: str
    duration_ms: float


class AuditLogger:
    """Collect and export A2A audit logs."""

    def __init__(self, log_file: str | Path | None = None, log_level: str = "INFO") -> None:
        """Resolve the audit log path and create its parent directory."""
        self.logger = get_logger(__name__, log_level)
        self.log_file = Path(log_file) if log_file else Path("logs") / "a2a-audit.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._entries: list[AuditLog] = []

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, set):
            return sorted(value)
        if hasattr(value, "model_dump"):
            return value.model_dump()  # type: ignore[no-any-return]
        if hasattr(value, "__dict__") and not isinstance(value, type):
            try:
                return dict(value.__dict__)
            except Exception:  # pragma: no cover - defensive
                return str(value)
        return value

    def log_invocation(self, log_entry: AuditLog) -> None:
        """Persist a new audit log entry and emit a structured log message."""
        with self._lock:
            self._entries.append(log_entry)
            serialized = asdict(log_entry)
            serialized["timestamp"] = log_entry.timestamp.isoformat()
            try:
                with self.log_file.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(serialized, default=self._serialize) + "\n")
            except Exception as exc:  # pragma: no cover - I/O fallback
                self.logger.error("Failed to write A2A audit log", extra={"error": str(exc)})

        log_audit_event(
            self.logger,
            operation="a2a_delegate",
            resource_type="tool",
            resource_id=log_entry.tool_name,
            success=True,
            agent_id=log_entry.agent_id,
            safety_level=log_entry.safety_level,
            duration_ms=log_entry.duration_ms,
            result=log_entry.result,
        )

    def get_audit_trail(
        self,
        agent_id: str | None = None,
        tool_name: str | None = None,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> list[AuditLog]:
        """Return audit entries filtered by agent, tool, and time range."""
        start_dt = self._coerce_datetime(start)
        end_dt = self._coerce_datetime(end)

        with self._lock:
            entries = list(self._entries)

        result: list[AuditLog] = []
        for entry in entries:
            if agent_id is not None and entry.agent_id != agent_id:
                continue
            if tool_name is not None and entry.tool_name != tool_name:
                continue
            if start_dt is not None and entry.timestamp < start_dt:
                continue
            if end_dt is not None and entry.timestamp > end_dt:
                continue
            result.append(entry)
        return result

    def export_audit_log(self, format: str = "json") -> str:
        """Export the current audit trail as JSON or JSONL."""
        entries = self.get_audit_trail()
        if format.lower() == "json":
            payload = [
                {
                    **asdict(entry),
                    "timestamp": entry.timestamp.isoformat(),
                }
                for entry in entries
            ]
            return json.dumps(payload, default=self._serialize, indent=2)
        if format.lower() == "jsonl":
            lines = []
            for entry in entries:
                row = asdict(entry)
                row["timestamp"] = entry.timestamp.isoformat()
                lines.append(json.dumps(row, default=self._serialize))
            return "\n".join(lines)
        raise ValueError("Unsupported export format. Expected 'json' or 'jsonl'.")

    @staticmethod
    def _coerce_datetime(value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))


_audit_logger: AuditLogger | None = None


def get_audit_logger(log_file: str | Path | None = None, log_level: str = "INFO") -> AuditLogger:
    """Return the shared A2A audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(log_file=log_file, log_level=log_level)
    return _audit_logger


__all__ = ["AuditLog", "AuditLogger", "get_audit_logger"]
