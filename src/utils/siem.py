"""Audit export to a SIEM (docs/FLEET_SCALING_PLAN.md §3.7, Phase 5).

``UNIFI_AUDIT_SIEM_TARGETS`` lists destinations, comma-separated; the scheme
picks the exporter:

- ``syslog+tls://host:6514``: RFC 5424 messages over TLS, octet-counted
  (RFC 5425). ``syslog+tcp://`` sends the same without TLS (loopback or a
  trusted network only).
- ``https://host/path``: an HMAC-signed webhook. Each POST carries a JSON
  array of records, ``X-UniFi-MCP-Timestamp`` and ``X-UniFi-MCP-Signature:
  sha256=HMAC(UNIFI_AUDIT_SIEM_WEBHOOK_SECRET, "<timestamp>.<body>")``.
  ``http://`` is accepted for loopback hosts only.
- ``otlp+https://collector:4318``: OTLP logs over HTTP/JSON (``/v1/logs``),
  with optional headers from ``UNIFI_AUDIT_SIEM_OTLP_HEADERS``
  (``key=value,key=value``). ``otlp+http://`` is accepted with a warning.

Records leave in their stored form: sealed (chain fields included) and with
payload fields encrypted when an audit key is set, so the SIEM can verify
them but cannot read parameters without the payload key.

Delivery never blocks a tool call. A stored record is appended to one spool
file per target (``UNIFI_AUDIT_SIEM_BUFFER_DIR``); a background task sends
spooled records in batches and deletes each segment once it is delivered,
backing off while the target is unreachable. Delivery is at least once (a
segment interrupted mid-send is sent again), so deduplicate on ``event_id``.
When a target's spool exceeds ``UNIFI_AUDIT_SIEM_BUFFER_MAX_MB``, the oldest
segments are dropped and the loss is logged.

Every ``UNIFI_AUDIT_SIEM_ANCHOR_SECONDS`` (and on shutdown) each chain's
latest ``(seq, hash)`` is sent as an ``anchor`` event. Kept outside the
server, anchors let ``python -m src.utils.audit_verify --anchors FILE``
detect records removed from the end of a chain even by someone who also
rewrote the stored chain heads.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import hmac
import json
import os
import socket
import ssl
import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from ..config import Settings
from .audit import CHAIN_KEY_ENV, resolve_chain_key
from .exceptions import ConfigurationError
from .logger import get_logger

logger = get_logger(__name__)

#: Most records sent in one batch.
BATCH_SIZE = 200

#: A spool segment is closed and queued for sending at this size.
SEGMENT_BYTES = 1024 * 1024

#: Longest wait between retries of an unreachable target, in seconds.
MAX_BACKOFF_SECONDS = 60.0

#: How long a send may take before it counts as failed, in seconds.
SEND_TIMEOUT_SECONDS = 15.0

APP_NAME = "unifi-mcp"
_LOOPBACK = {"localhost", "127.0.0.1", "::1"}
_SCHEMES = {"syslog+tls", "syslog+tcp", "https", "http", "otlp+https", "otlp+http"}


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------


async def _wait_event(event: asyncio.Event, timeout: float) -> None:
    """Wait until ``event`` is set or ``timeout`` passes, staying cancellable.

    Before Python 3.12, cancelling a task inside
    ``asyncio.wait_for(event.wait(), timeout)`` just as the timeout fires can
    lose the cancellation, so ``SiemForwarder.stop()`` would wait forever.
    ``asyncio.wait`` never swallows it.
    """
    waiter = asyncio.ensure_future(event.wait())
    try:
        await asyncio.wait({waiter}, timeout=timeout)
    finally:
        waiter.cancel()


class Exporter(Protocol):
    """Sends a batch of stored audit records to one destination."""

    name: str

    async def send(self, records: Sequence[Mapping[str, Any]]) -> None:
        """Deliver ``records``; raise if they were not all accepted."""
        ...


def _severity(record: Mapping[str, Any]) -> tuple[int, str, int]:
    """(syslog severity, text, OTLP severity number) of one record."""
    if record.get("event_type") == "denied" or record.get("result") in ("error", "failed"):
        return 4, "WARN", 13
    return 5, "INFO", 9


def _timestamp(record: Mapping[str, Any]) -> datetime:
    stamp = record.get("timestamp")
    if isinstance(stamp, str):
        with contextlib.suppress(ValueError):
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return datetime.now(UTC)


def _body(record: Mapping[str, Any]) -> str:
    return json.dumps(record, separators=(",", ":"), sort_keys=True)


class SyslogExporter:
    """RFC 5424 over TCP, optionally TLS, with RFC 5425 octet-counted framing."""

    #: local0
    facility = 16

    def __init__(
        self, host: str, port: int, *, tls: bool, ca_file: str | None = None, hostname: str = ""
    ) -> None:
        """Send to ``host:port``; ``tls`` verifies the server (``ca_file`` or system roots)."""
        self.name = f"syslog{'+tls' if tls else '+tcp'}://{host}:{port}"
        self.host = host
        self.port = port
        self._ssl = ssl.create_default_context(cafile=ca_file) if tls else None
        self._hostname = hostname or socket.gethostname()

    def format(self, record: Mapping[str, Any]) -> bytes:
        """One framed RFC 5424 message carrying the record as its MSG."""
        severity, _, _ = _severity(record)
        pri = self.facility * 8 + severity
        stamp = _timestamp(record).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        msgid = str(record.get("event_type") or "audit")[:32]
        message = (
            f"<{pri}>1 {stamp} {self._hostname[:255]} {APP_NAME} {os.getpid()} {msgid} - "
            f"{_body(record)}"
        ).encode()
        return f"{len(message)} ".encode() + message

    async def send(self, records: Sequence[Mapping[str, Any]]) -> None:
        """Open a connection, write every message, and close it."""
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port, ssl=self._ssl), SEND_TIMEOUT_SECONDS
        )
        try:
            writer.write(b"".join(self.format(record) for record in records))
            await asyncio.wait_for(writer.drain(), SEND_TIMEOUT_SECONDS)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


class WebhookExporter:
    """HMAC-signed JSON POSTs."""

    def __init__(self, url: str, secret: str, *, ca_file: str | None = None) -> None:
        """POST to ``url``, signed with ``secret``."""
        self.name = url.split("?", 1)[0]  # shown in logs; the query may hold a token
        self.key = url  # spool identity: targets differing only in the query stay apart
        self.url = url
        self._secret = secret.encode()
        # Always verify: the system trust store, or only ``ca_file`` when set (as syslog).
        self._verify = ssl.create_default_context(cafile=ca_file)

    def sign(self, timestamp: str, body: bytes) -> str:
        """``sha256=<hex HMAC>`` over ``"<timestamp>.<body>"``."""
        digest = hmac.new(self._secret, timestamp.encode() + b"." + body, hashlib.sha256)
        return f"sha256={digest.hexdigest()}"

    async def send(self, records: Sequence[Mapping[str, Any]]) -> None:
        """POST the batch; any non-2xx answer is a failure."""
        body = json.dumps(list(records), separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-UniFi-MCP-Timestamp": timestamp,
            "X-UniFi-MCP-Signature": self.sign(timestamp, body),
        }
        async with httpx.AsyncClient(timeout=SEND_TIMEOUT_SECONDS, verify=self._verify) as client:
            response = await client.post(self.url, content=body, headers=headers)
        response.raise_for_status()


class OtlpExporter:
    """OTLP logs over HTTP/JSON (``POST {endpoint}/v1/logs``)."""

    def __init__(
        self, endpoint: str, *, headers: Mapping[str, str] | None = None, ca_file: str | None = None
    ) -> None:
        """Send to ``endpoint`` (``https://collector:4318``) with extra ``headers``."""
        self.url = endpoint.rstrip("/") + "/v1/logs"
        self.name = f"otlp+{endpoint}"
        self._headers = {"Content-Type": "application/json", **(headers or {})}
        self._verify = ssl.create_default_context(cafile=ca_file)

    @staticmethod
    def _attribute(key: str, value: Any) -> dict[str, Any]:
        if isinstance(value, bool):
            return {"key": key, "value": {"boolValue": value}}
        if isinstance(value, int):
            return {"key": key, "value": {"intValue": str(value)}}
        return {"key": key, "value": {"stringValue": str(value)}}

    def payload(self, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """The ``ExportLogsServiceRequest`` for ``records``."""
        log_records = []
        for record in records:
            _, text, number = _severity(record)
            attributes = [
                self._attribute(f"unifi_mcp.{key}", record[key])
                for key in (
                    "event_id",
                    "event_type",
                    "operation",
                    "result",
                    "tier",
                    "controller",
                    "chain_id",
                    "seq",
                )
                if record.get(key) is not None
            ]
            log_records.append(
                {
                    "timeUnixNano": str(int(_timestamp(record).timestamp() * 1e9)),
                    "severityNumber": number,
                    "severityText": text,
                    "body": {"stringValue": _body(record)},
                    "attributes": attributes,
                }
            )
        return {
            "resourceLogs": [
                {
                    "resource": {
                        "attributes": [
                            self._attribute("service.name", APP_NAME),
                            self._attribute("host.name", socket.gethostname()),
                        ]
                    },
                    "scopeLogs": [
                        {"scope": {"name": "unifi_mcp.audit"}, "logRecords": log_records}
                    ],
                }
            ]
        }

    async def send(self, records: Sequence[Mapping[str, Any]]) -> None:
        """POST the batch; any non-2xx answer is a failure."""
        async with httpx.AsyncClient(timeout=SEND_TIMEOUT_SECONDS, verify=self._verify) as client:
            response = await client.post(
                self.url, json=self.payload(records), headers=self._headers
            )
        response.raise_for_status()


def _headers(raw: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for part in (raw or "").split(","):
        key, sep, value = part.partition("=")
        if sep and key.strip():
            headers[key.strip()] = value.strip()
    return headers


def build_exporters(settings: Settings) -> list[Exporter]:
    """Exporters for ``UNIFI_AUDIT_SIEM_TARGETS``.

    Raises:
        ConfigurationError: For an unknown scheme, a webhook without a secret,
            or plain HTTP to a host that is not loopback
    """
    exporters: list[Exporter] = []
    ca_file = getattr(settings, "audit_siem_ca_file", None)
    for target in (t.strip() for t in (settings.audit_siem_targets or "").split(",")):
        if not target:
            continue
        parts = urlsplit(target)
        scheme, host = parts.scheme.lower(), parts.hostname or ""
        if scheme in _SCHEMES and not host:
            raise ConfigurationError(f"SIEM target {scheme}:// needs a host")
        if scheme in ("syslog+tls", "syslog+tcp"):
            if scheme == "syslog+tcp" and host not in _LOOPBACK:
                logger.warning("SIEM target %s sends audit metadata without TLS", host)
            exporters.append(
                SyslogExporter(
                    host,
                    parts.port or (6514 if scheme == "syslog+tls" else 514),
                    tls=scheme == "syslog+tls",
                    ca_file=ca_file,
                )
            )
        elif scheme in ("https", "http"):
            if scheme == "http" and host not in _LOOPBACK:
                raise ConfigurationError(
                    "A SIEM webhook must use https:// (http:// only to a loopback host)"
                )
            secret = settings.audit_siem_webhook_secret
            if not secret:
                raise ConfigurationError(
                    "A SIEM webhook target needs UNIFI_AUDIT_SIEM_WEBHOOK_SECRET to sign deliveries"
                )
            exporters.append(WebhookExporter(target, secret, ca_file=ca_file))
        elif scheme in ("otlp+https", "otlp+http"):
            if scheme == "otlp+http" and host not in _LOOPBACK:
                logger.warning(
                    "SIEM target %s sends audit metadata without TLS", target.split("@")[-1]
                )
            exporters.append(
                OtlpExporter(
                    target.split("+", 1)[1],
                    headers=_headers(settings.audit_siem_otlp_headers),
                    ca_file=ca_file,
                )
            )
        else:
            raise ConfigurationError(
                f"Unknown SIEM target scheme '{scheme}': use syslog+tls://, https:// or "
                "otlp+https://"
            )
    return exporters


# ---------------------------------------------------------------------------
# Spool and forwarding
# ---------------------------------------------------------------------------


def _spool_key(exporter: Exporter) -> str:
    """What identifies a target's spool: its full URL where the name is redacted."""
    return str(getattr(exporter, "key", exporter.name))


def _spool_name(key: str) -> str:
    """A directory name for one target (its URL never appears in the path)."""
    return base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()[:12]).decode()


@dataclass
class _Target:
    exporter: Exporter
    directory: Path
    max_bytes: int
    lock: threading.Lock = field(default_factory=threading.Lock)
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    counter: int = 0
    dropped: int = 0
    delivered: int = 0
    # Heads this target has spooled; cleared when the cap drops a segment,
    # which may have held an anchor, so every head is re-sent.
    anchored: dict[str, tuple[int, str]] = field(default_factory=dict)

    @property
    def active(self) -> Path:
        return self.directory / "active.jsonl"

    def append(self, line: str) -> None:
        with self.lock:
            with open(self.active, "a", encoding="utf-8", opener=_private) as f:
                f.write(line + "\n")
            if self.active.stat().st_size >= SEGMENT_BYTES:
                self._seal()
            self._enforce_cap()

    def _seal(self) -> None:
        """Close the active segment (call with the lock held)."""
        if self.active.exists() and self.active.stat().st_size:
            self.counter += 1
            name = f"{time.time_ns():020d}-{self.counter:06d}.jsonl"
            self.active.rename(self.directory / name)

    def seal(self) -> None:
        with self.lock:
            self._seal()

    def segments(self) -> list[Path]:
        return sorted(p for p in self.directory.glob("*.jsonl") if p.name != "active.jsonl")

    def _enforce_cap(self) -> None:
        """Drop the oldest sealed segments over the cap (call with the lock held)."""
        segments = self.segments()
        total = sum(p.stat().st_size for p in segments)
        if self.active.exists():
            total += self.active.stat().st_size
        while total > self.max_bytes and segments:
            oldest = segments.pop(0)
            size = oldest.stat().st_size
            lost = sum(1 for _ in oldest.open(encoding="utf-8"))
            oldest.unlink()
            total -= size
            self.dropped += lost
            self.anchored.clear()
            logger.error(
                "SIEM spool for %s over its %d MB cap: dropped %d undelivered audit record(s)",
                self.exporter.name,
                self.max_bytes // (1024 * 1024),
                lost,
            )


def _private(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)


class SiemForwarder:
    """Spools stored audit records per target and delivers them in the background."""

    def __init__(
        self,
        exporters: Sequence[Exporter],
        buffer_dir: Path,
        *,
        max_bytes: int = 100 * 1024 * 1024,
        anchor_seconds: float = 300.0,
        flush_seconds: float = 2.0,
    ) -> None:
        """Create a forwarder; :meth:`start` begins delivery.

        Args:
            exporters: Where records go
            buffer_dir: Spool root (one subdirectory per target, mode 0700)
            max_bytes: Spool cap per target
            anchor_seconds: How often chain heads are sent
            flush_seconds: Longest a record waits in the active segment
        """
        self.anchor_seconds = anchor_seconds
        self.flush_seconds = flush_seconds
        self._targets: list[_Target] = []
        # mkdir's mode applies to the last component only: create the root
        # private too, since spooled records name operations and principals.
        buffer_dir.mkdir(parents=True, exist_ok=True)
        buffer_dir.chmod(0o700)
        keys = [_spool_key(exporter) for exporter in exporters]
        if len(set(keys)) != len(keys):
            raise ConfigurationError("UNIFI_AUDIT_SIEM_TARGETS lists the same target twice")
        for exporter in exporters:
            directory = buffer_dir / _spool_name(_spool_key(exporter))
            directory.mkdir(exist_ok=True, mode=0o700)
            directory.chmod(0o700)
            self._targets.append(_Target(exporter, directory, max_bytes))
        self._heads: dict[str, tuple[int, str]] = {}
        self._heads_lock = threading.Lock()
        self._tasks: list[asyncio.Task[None]] = []

    @classmethod
    def from_settings(cls, settings: Settings) -> SiemForwarder | None:
        """A forwarder for ``UNIFI_AUDIT_SIEM_TARGETS``, or None when unset.

        Raises:
            ConfigurationError: For an invalid target (see :func:`build_exporters`),
                or when ``UNIFI_AUDIT_CHAIN_KEY`` is unset
        """
        exporters = build_exporters(settings)
        if not exporters:
            return None
        # Without the key the chain is plain SHA-256, which anyone holding the
        # records can recompute after editing them, so the copy the SIEM keeps
        # (and the anchors it is sent) would prove nothing.
        if resolve_chain_key() is None:
            raise ConfigurationError(
                f"UNIFI_AUDIT_SIEM_TARGETS needs {CHAIN_KEY_ENV}: an unkeyed audit chain "
                "can be recomputed after tampering, so exported records could not be trusted"
            )
        buffer_dir = settings.audit_siem_buffer_dir
        if buffer_dir:
            root = Path(buffer_dir)
        else:
            audit_file = Path(settings.audit_log_file or "audit.log")
            root = audit_file.parent / "siem-buffer"
        return cls(
            exporters,
            root,
            max_bytes=settings.audit_siem_buffer_max_mb * 1024 * 1024,
            anchor_seconds=float(settings.audit_siem_anchor_seconds),
        )

    @property
    def targets(self) -> list[str]:
        """Names of the configured targets."""
        return [target.exporter.name for target in self._targets]

    def stats(self) -> dict[str, dict[str, int]]:
        """Per target: records delivered, dropped over the cap, and segments waiting."""
        return {
            t.exporter.name: {
                "delivered": t.delivered,
                "dropped": t.dropped,
                "pending_segments": len(t.segments()) + int(t.active.exists()),
            }
            for t in self._targets
        }

    def forward(self, record: Mapping[str, Any]) -> None:
        """Spool one stored record for every target. Never raises."""
        try:
            line = _body(record)
            chain_id, seq, digest = record.get("chain_id"), record.get("seq"), record.get("hash")
            if isinstance(chain_id, str) and isinstance(seq, int) and isinstance(digest, str):
                with self._heads_lock:
                    self._heads[chain_id] = (seq, digest)
            for target in self._targets:
                target.append(line)
        except Exception as e:  # never fail the tool call that produced the record
            logger.error("Could not spool an audit record for the SIEM: %s", e)
            return
        self._notify()

    def _notify(self) -> None:
        """Wake every delivery loop (from the loop thread or any other)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # no loop here: the delivery loops' flush timer picks it up
        for target in self._targets:
            loop.call_soon_threadsafe(target.wake.set)

    def anchors(self, target: _Target | None = None) -> list[dict[str, Any]]:
        """One ``anchor`` event per chain whose head ``target`` has not spooled yet.

        Without a target, one per chain head known.
        """
        now = datetime.now(UTC).isoformat()
        with self._heads_lock:
            heads = dict(self._heads)
        return [
            {
                "event_id": uuid.uuid4().hex,
                "event_type": "anchor",
                "timestamp": now,
                "chain_id": chain_id,
                "seq": seq,
                "hash": digest,
            }
            for chain_id, (seq, digest) in sorted(heads.items())
            if target is None or target.anchored.get(chain_id) != (seq, digest)
        ]

    def _anchor(self) -> None:
        """Spool each target's missing anchors; one that fails is retried next time."""
        for target in self._targets:
            for event in self.anchors(target):
                try:
                    target.append(_body(event))
                except Exception as e:
                    logger.error(
                        "Could not spool a chain anchor for %s: %s", target.exporter.name, e
                    )
                    continue
                with target.lock:
                    target.anchored[event["chain_id"]] = (event["seq"], event["hash"])
        self._notify()

    async def start(self) -> None:
        """Start delivering (one task per target) and anchoring."""
        self._tasks = [asyncio.create_task(self._deliver(t)) for t in self._targets]
        self._tasks.append(asyncio.create_task(self._anchor_loop()))

    async def stop(self, *, flush_seconds: float = 5.0) -> None:
        """Anchor, try to deliver what is spooled for up to ``flush_seconds``, then stop.

        Whatever is still undelivered stays on disk for the next start.
        """
        self._anchor()
        try:
            await asyncio.wait_for(self.flush(), flush_seconds)
        except Exception as e:  # unreachable or slow: the spool waits on disk
            logger.warning(
                "SIEM export stopped with records still spooled (%s: %s); they are sent "
                "after the next start",
                type(e).__name__,
                e,
            )
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []

    async def flush(self) -> None:
        """Deliver everything spooled now (raising on the first failure)."""
        for target in self._targets:
            target.seal()
            for segment in target.segments():
                await self._send_segment(target, segment)

    async def _anchor_loop(self) -> None:
        while True:
            await asyncio.sleep(self.anchor_seconds)
            self._anchor()

    async def _deliver(self, target: _Target) -> None:
        backoff = 1.0
        while True:
            await _wait_event(target.wake, self.flush_seconds)
            target.wake.clear()
            target.seal()
            try:
                for segment in target.segments():
                    await self._send_segment(target, segment)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(
                    "SIEM target %s unreachable (%s: %s); retrying in %.0fs",
                    target.exporter.name,
                    type(e).__name__,
                    e,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                target.wake.set()
                continue
            backoff = 1.0

    async def _send_segment(self, target: _Target, segment: Path) -> None:
        if not segment.exists():  # dropped over the cap meanwhile
            return
        records = [
            json.loads(line) for line in segment.read_text(encoding="utf-8").splitlines() if line
        ]
        for start in range(0, len(records), BATCH_SIZE):
            await target.exporter.send(records[start : start + BATCH_SIZE])
        with target.lock:
            segment.unlink(missing_ok=True)
        target.delivered += len(records)


def load_anchors(path: Path) -> dict[str, tuple[int, str]]:
    """The latest anchor per chain from exported records (JSON lines or one JSON array).

    Records other than ``anchor`` events are ignored, so a raw SIEM export
    can be passed as is.
    """
    text = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(text)
        items = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    heads: dict[str, tuple[int, str]] = {}
    for item in items:
        if not isinstance(item, dict) or item.get("event_type") != "anchor":
            continue
        chain_id, seq, digest = item.get("chain_id"), item.get("seq"), item.get("hash")
        if isinstance(chain_id, str) and isinstance(seq, int) and isinstance(digest, str):
            if chain_id not in heads or seq >= heads[chain_id][0]:
                heads[chain_id] = (seq, digest)
    return heads
