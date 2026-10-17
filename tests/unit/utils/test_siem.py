"""Audit export to a SIEM (src/utils/siem.py, docs/FLEET_SCALING_PLAN.md Phase 5).

Exporters run against real local listeners (TCP, TLS) or an HTTP mock
transport; the forwarder runs against a recording exporter that can be made
to fail, which is also the SIEM-outage drill.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import hmac
import json
import ssl
import stat
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest

from src.config.config import Settings
from src.utils import siem
from src.utils.audit import AuditLogger
from src.utils.audit_verify import main as verify_cli
from src.utils.exceptions import ConfigurationError
from src.utils.siem import (
    OtlpExporter,
    SiemForwarder,
    SyslogExporter,
    WebhookExporter,
    build_exporters,
    load_anchors,
)

SECRET = "siem-webhook-secret"  # pragma: allowlist secret
RECORD = {
    "v": 2,
    "event_id": "e-1",
    "timestamp": "2026-10-11T12:00:00.123+00:00",
    "event_type": "tool_call",
    "operation": "update_network",
    "result": "success",
    "chain_id": "c" * 32,
    "seq": 3,
    "hash": "h" * 64,
    "parameters": "fernet:v1:ciphertext",
    "parameters_encrypted": True,
}


@pytest.fixture(autouse=True)
def _no_env_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("UNIFI_AUDIT_CHAIN_KEY", "UNIFI_AUDIT_LOG_KEY"):
        monkeypatch.delenv(name, raising=False)


def _settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: str) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "k")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Settings()


class Recorder:
    """An exporter that records batches and fails while ``down``."""

    def __init__(self, name: str = "recorder") -> None:
        self.name = name
        self.batches: list[list[dict[str, Any]]] = []
        self.down = False

    @property
    def records(self) -> list[dict[str, Any]]:
        return [r for batch in self.batches for r in batch]

    async def send(self, records: Sequence[Any]) -> None:
        if self.down:
            raise ConnectionError("SIEM unreachable")
        self.batches.append([dict(r) for r in records])


async def _until(predicate: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached")
        await asyncio.sleep(0.02)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestBuildExporters:
    def test_unset(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        assert build_exporters(_settings(monkeypatch, tmp_path)) == []
        assert SiemForwarder.from_settings(_settings(monkeypatch, tmp_path)) is None

    def test_every_scheme(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        settings = _settings(
            monkeypatch,
            tmp_path,
            UNIFI_AUDIT_SIEM_TARGETS=(
                "syslog+tls://siem.example:6514, syslog+tcp://127.0.0.1,"
                "https://hooks.example/audit,otlp+https://otel.example:4318"
            ),
            UNIFI_AUDIT_SIEM_WEBHOOK_SECRET=SECRET,
            UNIFI_AUDIT_SIEM_OTLP_HEADERS="x-api-key=abc, x-tenant = t1,junk",
        )
        syslog_tls, syslog_tcp, webhook, otlp = build_exporters(settings)

        assert isinstance(syslog_tls, SyslogExporter) and syslog_tls.port == 6514
        assert syslog_tls._ssl is not None
        assert isinstance(syslog_tcp, SyslogExporter) and syslog_tcp.port == 514
        assert syslog_tcp._ssl is None
        assert isinstance(webhook, WebhookExporter)
        assert isinstance(otlp, OtlpExporter)
        assert otlp.url == "https://otel.example:4318/v1/logs"
        assert otlp._headers["x-api-key"] == "abc"
        assert otlp._headers["x-tenant"] == "t1"

    @pytest.mark.parametrize(
        ("targets", "message"),
        [
            ("ftp://siem.example", "Unknown SIEM target scheme"),
            ("https://hooks.example/audit", "UNIFI_AUDIT_SIEM_WEBHOOK_SECRET"),
            ("http://hooks.example/audit", "must use https"),
            ("syslog+tls://", "needs a host"),
            ("https:///ingest", "needs a host"),
            ("otlp+https:///v1/logs", "needs a host"),
        ],
    )
    def test_invalid(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, targets: str, message: str
    ) -> None:
        settings = _settings(monkeypatch, tmp_path, UNIFI_AUDIT_SIEM_TARGETS=targets)
        with pytest.raises(ConfigurationError, match=message):
            build_exporters(settings)

    def test_plain_http_to_loopback_is_allowed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: Any
    ) -> None:
        settings = _settings(
            monkeypatch,
            tmp_path,
            UNIFI_AUDIT_SIEM_TARGETS="http://127.0.0.1:9000/hook,otlp+http://otel.internal:4318",
            UNIFI_AUDIT_SIEM_WEBHOOK_SECRET=SECRET,
        )
        assert len(build_exporters(settings)) == 2
        assert "without TLS" in caplog.text

    def test_plain_syslog_off_loopback_is_warned_about(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: Any
    ) -> None:
        settings = _settings(
            monkeypatch, tmp_path, UNIFI_AUDIT_SIEM_TARGETS="syslog+tcp://127.0.0.1:514"
        )
        build_exporters(settings)
        assert "without TLS" not in caplog.text
        settings = _settings(
            monkeypatch, tmp_path, UNIFI_AUDIT_SIEM_TARGETS="syslog+tcp://siem.internal:514"
        )
        build_exporters(settings)
        assert "siem.internal sends audit metadata without TLS" in caplog.text

    def test_blank_values_are_unset(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        blank = dict.fromkeys(
            (
                "UNIFI_AUDIT_SIEM_TARGETS",
                "UNIFI_AUDIT_SIEM_WEBHOOK_SECRET",
                "UNIFI_AUDIT_SIEM_OTLP_HEADERS",
                "UNIFI_AUDIT_SIEM_CA_FILE",
                "UNIFI_AUDIT_SIEM_BUFFER_DIR",
            ),
            "  ",
        )
        settings = _settings(monkeypatch, tmp_path, **blank)
        assert settings.audit_siem_targets is None
        assert settings.audit_siem_webhook_secret is None
        assert settings.audit_siem_otlp_headers is None
        assert settings.audit_siem_ca_file is None
        assert settings.audit_siem_buffer_dir is None

    def test_default_buffer_is_next_to_the_audit_log(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        settings = _settings(
            monkeypatch, tmp_path, UNIFI_AUDIT_SIEM_TARGETS="syslog+tcp://127.0.0.1:1"
        )
        monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", "chain-key")  # pragma: allowlist secret
        forwarder = SiemForwarder.from_settings(settings)
        assert forwarder is not None
        assert (tmp_path / "siem-buffer").is_dir()
        assert stat.S_IMODE((tmp_path / "siem-buffer").stat().st_mode) == 0o700

    def test_targets_need_the_chain_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # An unkeyed chain can be recomputed after editing the records, so the
        # SIEM copy and its anchors would prove nothing (AC-531).
        settings = _settings(
            monkeypatch, tmp_path, UNIFI_AUDIT_SIEM_TARGETS="syslog+tcp://127.0.0.1:1"
        )
        with pytest.raises(ConfigurationError, match="UNIFI_AUDIT_CHAIN_KEY"):
            SiemForwarder.from_settings(settings)
        assert not (tmp_path / "siem-buffer").exists()

    def test_blank_chain_key_counts_as_unset(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        settings = _settings(
            monkeypatch,
            tmp_path,
            UNIFI_AUDIT_SIEM_TARGETS="syslog+tcp://127.0.0.1:1",
            UNIFI_AUDIT_CHAIN_KEY="  ",
        )
        with pytest.raises(ConfigurationError, match="UNIFI_AUDIT_CHAIN_KEY"):
            SiemForwarder.from_settings(settings)


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------


def _self_signed(directory: Path) -> tuple[Path, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=1))
        .not_valid_after(now + dt.timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "siem.crt", directory / "siem.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


def _parse_octet_counted(data: bytes) -> list[bytes]:
    messages = []
    while data:
        length, _, rest = data.partition(b" ")
        size = int(length)
        messages.append(rest[:size])
        data = rest[size:]
    return messages


class TestSyslog:
    def test_message_format(self) -> None:
        exporter = SyslogExporter("siem", 514, tls=False, hostname="mcp-1")
        frame = exporter.format(RECORD)
        (message,) = _parse_octet_counted(frame)
        header, _, body = message.partition(b" - ")

        assert header.startswith(b"<133>1 2026-10-11T12:00:00.123Z mcp-1 unifi-mcp ")
        assert header.endswith(b" tool_call")
        assert json.loads(body) == RECORD

    def test_denials_are_warnings(self) -> None:
        exporter = SyslogExporter("siem", 514, tls=False)
        frame = exporter.format({**RECORD, "event_type": "denied", "result": "denied"})
        assert _parse_octet_counted(frame)[0].startswith(b"<132>1 ")

    @pytest.mark.parametrize("tls", [False, True])
    async def test_delivers_over_tcp_and_tls(self, tmp_path: Path, tls: bool) -> None:
        received = bytearray()
        done = asyncio.Event()

        async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            received.extend(await reader.read())
            writer.close()
            done.set()

        context = None
        ca_file = None
        if tls:
            cert, key = _self_signed(tmp_path)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            ca_file = str(cert)
        server = await asyncio.start_server(handle, "localhost", 0, ssl=context)
        port = server.sockets[0].getsockname()[1]
        exporter = SyslogExporter("localhost", port, tls=tls, ca_file=ca_file)
        try:
            await exporter.send([RECORD, {**RECORD, "event_id": "e-2"}])
            await asyncio.wait_for(done.wait(), 5)
        finally:
            server.close()
            await server.wait_closed()

        messages = _parse_octet_counted(bytes(received))
        assert [json.loads(m.partition(b" - ")[2])["event_id"] for m in messages] == ["e-1", "e-2"]

    async def test_untrusted_certificate_is_refused(self, tmp_path: Path) -> None:
        cert, key = _self_signed(tmp_path)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        server = await asyncio.start_server(lambda r, w: None, "localhost", 0, ssl=context)
        port = server.sockets[0].getsockname()[1]
        try:
            with pytest.raises(ssl.SSLError):
                await SyslogExporter("localhost", port, tls=True).send([RECORD])
        finally:
            server.close()
            await server.wait_closed()


def _mock_httpx(monkeypatch: pytest.MonkeyPatch, handler: Any) -> list[httpx.Request]:
    seen: list[httpx.Request] = []
    real = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        kwargs.pop("verify", None)
        return real(*args, transport=httpx.MockTransport(recording), **kwargs)

    monkeypatch.setattr(siem.httpx, "AsyncClient", factory)
    return seen


class TestWebhook:
    async def test_signed_delivery(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = _mock_httpx(monkeypatch, lambda request: httpx.Response(202))
        await WebhookExporter("https://hooks.example/audit", SECRET).send([RECORD])

        (request,) = seen
        body = request.content
        timestamp = request.headers["X-UniFi-MCP-Timestamp"]
        expected = hmac.new(SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
        assert request.headers["X-UniFi-MCP-Signature"] == f"sha256={expected.hexdigest()}"
        assert abs(int(timestamp) - time.time()) < 60
        assert json.loads(body) == [RECORD]

    async def test_error_status_is_a_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_httpx(monkeypatch, lambda request: httpx.Response(503))
        with pytest.raises(httpx.HTTPStatusError):
            await WebhookExporter("https://hooks.example/audit", SECRET).send([RECORD])

    def test_name_hides_the_query_string(self) -> None:
        assert WebhookExporter("https://h.example/a?token=x", SECRET).name == "https://h.example/a"


class TestOtlp:
    def test_payload(self) -> None:
        payload = OtlpExporter("https://otel.example:4318").payload(
            [RECORD, {**RECORD, "event_type": "denied", "result": "denied"}]
        )
        (resource,) = payload["resourceLogs"]
        logs = resource["scopeLogs"][0]["logRecords"]
        first = logs[0]

        assert {"key": "service.name", "value": {"stringValue": "unifi-mcp"}} in resource[
            "resource"
        ]["attributes"]
        assert first["timeUnixNano"] == str(
            int(dt.datetime(2026, 10, 11, 12, 0, 0, 123000, dt.timezone.utc).timestamp() * 1e9)
        )
        assert (first["severityNumber"], first["severityText"]) == (9, "INFO")
        assert (logs[1]["severityNumber"], logs[1]["severityText"]) == (13, "WARN")
        assert json.loads(first["body"]["stringValue"]) == RECORD
        attributes = {a["key"]: a["value"] for a in first["attributes"]}
        assert attributes["unifi_mcp.seq"] == {"intValue": "3"}
        assert attributes["unifi_mcp.operation"] == {"stringValue": "update_network"}

    async def test_delivery_with_headers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = _mock_httpx(monkeypatch, lambda request: httpx.Response(200, json={}))
        await OtlpExporter("https://otel.example:4318/", headers={"x-api-key": "abc"}).send(
            [RECORD]
        )
        (request,) = seen
        assert str(request.url) == "https://otel.example:4318/v1/logs"
        assert request.headers["x-api-key"] == "abc"

    async def test_error_status_is_a_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _mock_httpx(monkeypatch, lambda request: httpx.Response(400))
        with pytest.raises(httpx.HTTPStatusError):
            await OtlpExporter("https://otel.example:4318").send([RECORD])


# ---------------------------------------------------------------------------
# Forwarder
# ---------------------------------------------------------------------------


def _record(n: int, chain: str = "c" * 32) -> dict[str, Any]:
    return {**RECORD, "event_id": f"e-{n}", "seq": n, "hash": f"{n:064x}", "chain_id": chain}


class TestWaitEvent:
    async def test_a_cancel_arriving_with_the_event_is_not_lost(self) -> None:
        # stop() sets the wake event and cancels the delivery task in one
        # tick; asyncio.wait_for dropped that cancellation before 3.12.
        from src.utils.siem import _wait_event

        event = asyncio.Event()

        async def loop() -> None:
            while True:
                await _wait_event(event, 30)
                event.clear()

        task = asyncio.create_task(loop())
        await asyncio.sleep(0.01)
        event.set()
        task.cancel()
        done, _pending = await asyncio.wait({task}, timeout=2)
        assert done, "the waiter ignored its cancellation"
        task.cancel()

    async def test_returns_when_the_event_is_set(self) -> None:
        from src.utils.siem import _wait_event

        event = asyncio.Event()
        asyncio.get_running_loop().call_later(0.01, event.set)
        started = time.monotonic()
        await _wait_event(event, 5)
        assert time.monotonic() - started < 1


class TestForwarder:
    async def test_delivers_in_the_background(self, tmp_path: Path) -> None:
        recorder = Recorder()
        forwarder = SiemForwarder([recorder], tmp_path, flush_seconds=0.05)
        await forwarder.start()
        try:
            for n in range(3):
                forwarder.forward(_record(n))
            await _until(lambda: len(recorder.records) == 3)
        finally:
            await forwarder.stop()

        calls = [r["event_id"] for r in recorder.records if r["event_type"] == "tool_call"]
        assert calls == ["e-0", "e-1", "e-2"]
        assert forwarder.stats()[recorder.name]["delivered"] >= 3

    async def test_spool_files_are_private(self, tmp_path: Path) -> None:
        recorder = Recorder()
        recorder.down = True
        forwarder = SiemForwarder([recorder], tmp_path / "spool")
        forwarder.forward(_record(0))
        (directory,) = list((tmp_path / "spool").iterdir())
        (spool,) = list(directory.iterdir())

        assert stat.S_IMODE((tmp_path / "spool").stat().st_mode) == 0o700
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        assert stat.S_IMODE(spool.stat().st_mode) == 0o600
        assert "recorder" not in str(directory)  # target names never in paths

    async def test_anchors_report_each_moved_head_once(self, tmp_path: Path) -> None:
        recorder = Recorder()
        forwarder = SiemForwarder([recorder], tmp_path)
        forwarder.forward(_record(4))
        forwarder.forward(_record(9, chain="d" * 32))

        anchors = forwarder.anchors()
        assert [(a["chain_id"][0], a["seq"]) for a in anchors] == [("c", 4), ("d", 9)]
        assert all(a["event_type"] == "anchor" for a in anchors)
        forwarder._anchor()
        forwarder._anchor()  # unchanged heads are not re-sent
        forwarder.forward(_record(5))
        forwarder._anchor()
        await forwarder.flush()
        sent = [
            (r["chain_id"][0], r["seq"]) for r in recorder.records if r["event_type"] == "anchor"
        ]
        assert sent == [("c", 4), ("d", 9), ("c", 5)]

    async def test_an_anchor_that_could_not_be_spooled_is_retried(
        self, tmp_path: Path, monkeypatch: Any, caplog: Any
    ) -> None:
        first, second = Recorder("one"), Recorder("two")
        forwarder = SiemForwarder([first, second], tmp_path)
        forwarder.forward(_record(4))
        broken = forwarder._targets[0]
        real_append = broken.append

        def fail(line: str) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(broken, "append", fail)
        forwarder._anchor()
        assert "Could not spool a chain anchor for one" in caplog.text
        monkeypatch.setattr(broken, "append", real_append)
        forwarder._anchor()  # only the target that missed it gets it again
        await forwarder.flush()

        def anchors(recorder: Recorder) -> list[int]:
            return [r["seq"] for r in recorder.records if r["event_type"] == "anchor"]

        assert anchors(first) == [4]
        assert anchors(second) == [4]

    def test_an_anchor_dropped_over_the_cap_is_re_sent(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr(siem, "SEGMENT_BYTES", 1)  # one record per segment
        recorder = Recorder()
        size = len(json.dumps(_record(0), separators=(",", ":"), sort_keys=True)) + 1
        forwarder = SiemForwarder([recorder], tmp_path, max_bytes=size * 2)
        forwarder.forward(_record(0))
        forwarder._anchor()
        for n in range(1, 4):  # pushes the anchor out of the spool
            forwarder.forward({**_record(n), "chain_id": "d" * 32})
        forwarder._anchor()
        asyncio.run(forwarder.flush())

        anchors = [r for r in recorder.records if r["event_type"] == "anchor"]
        assert ("c" * 32, 0) in [(a["chain_id"], a["seq"]) for a in anchors]

    def test_targets_differing_in_the_query_get_their_own_spool(self, tmp_path: Path) -> None:
        first = WebhookExporter("https://siem.example/hook?tenant=a", SECRET)
        second = WebhookExporter("https://siem.example/hook?tenant=b", SECRET)
        assert first.name == second.name  # the query is kept out of logs
        forwarder = SiemForwarder([first, second], tmp_path / "spool")
        forwarder.forward(_record(0))
        assert len(list((tmp_path / "spool").iterdir())) == 2

    def test_the_same_target_twice_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="same target twice"):
            SiemForwarder([Recorder("one"), Recorder("one")], tmp_path)

    async def test_stop_sends_the_anchors_and_flushes(self, tmp_path: Path) -> None:
        recorder = Recorder()
        forwarder = SiemForwarder([recorder], tmp_path, flush_seconds=60)
        await forwarder.start()
        forwarder.forward(_record(0))
        await forwarder.stop()

        assert [r["event_type"] for r in recorder.records] == ["tool_call", "anchor"]
        assert recorder.records[1]["hash"] == _record(0)["hash"]

    async def test_periodic_anchors(self, tmp_path: Path) -> None:
        recorder = Recorder()
        forwarder = SiemForwarder([recorder], tmp_path, anchor_seconds=0.05, flush_seconds=0.05)
        await forwarder.start()
        try:
            forwarder.forward(_record(0))
            await _until(lambda: any(r["event_type"] == "anchor" for r in recorder.records))
        finally:
            await forwarder.stop()

    async def test_every_target_gets_every_record(self, tmp_path: Path) -> None:
        first, second = Recorder("one"), Recorder("two")
        forwarder = SiemForwarder([first, second], tmp_path, flush_seconds=0.05)
        await forwarder.start()
        try:
            forwarder.forward(_record(0))
            await _until(lambda: first.records and second.records)
        finally:
            await forwarder.stop()

    async def test_large_spools_go_in_batches(self, tmp_path: Path, monkeypatch: Any) -> None:
        monkeypatch.setattr(siem, "BATCH_SIZE", 3)
        recorder = Recorder()
        forwarder = SiemForwarder([recorder], tmp_path)
        for n in range(7):
            forwarder.forward(_record(n))
        await forwarder.flush()
        assert [len(b) for b in recorder.batches] == [3, 3, 1]

    def test_forward_never_raises(self, tmp_path: Path, caplog: Any) -> None:
        forwarder = SiemForwarder([Recorder()], tmp_path)
        forwarder.forward({"unserializable": object()})  # type: ignore[dict-item]
        assert "Could not spool" in caplog.text


class TestSiemOutageDrill:
    """A SIEM outage never blocks or fails a tool call, and loses nothing it can keep."""

    async def test_outage_spools_then_delivers_everything_in_order(self, tmp_path: Path) -> None:
        recorder = Recorder()
        recorder.down = True
        forwarder = SiemForwarder([recorder], tmp_path, flush_seconds=0.02)
        await forwarder.start()
        try:
            started = time.perf_counter()
            for n in range(50):
                forwarder.forward(_record(n))  # what the audit path calls per record
            per_record = (time.perf_counter() - started) / 50
            await asyncio.sleep(0.2)  # delivery attempts fail meanwhile
            assert recorder.records == []

            recorder.down = False
            await _until(lambda: len({r["event_id"] for r in recorder.records}) == 50, 30)
        finally:
            await forwarder.stop()

        assert per_record < 0.01  # a local file append, not a network round trip
        ids = [r["event_id"] for r in recorder.records if r["event_type"] == "tool_call"]
        assert ids == [f"e-{n}" for n in range(50)]

    async def test_spool_survives_a_restart(self, tmp_path: Path) -> None:
        recorder = Recorder()
        recorder.down = True
        before = SiemForwarder([recorder], tmp_path)
        for n in range(3):
            before.forward(_record(n))

        recorder.down = False
        after = SiemForwarder([recorder], tmp_path)
        await after.flush()

        assert [r["event_id"] for r in recorder.records] == ["e-0", "e-1", "e-2"]

    def test_cap_drops_the_oldest_and_counts_the_loss(
        self, tmp_path: Path, monkeypatch: Any, caplog: Any
    ) -> None:
        monkeypatch.setattr(siem, "SEGMENT_BYTES", 1)  # one record per segment
        recorder = Recorder()
        size = len(json.dumps(_record(0), separators=(",", ":"), sort_keys=True)) + 1
        forwarder = SiemForwarder([recorder], tmp_path, max_bytes=size * 3)
        for n in range(6):
            forwarder.forward(_record(n))

        assert forwarder.stats()[recorder.name]["dropped"] == 3
        assert "dropped" in caplog.text
        asyncio.run(forwarder.flush())
        assert [r["event_id"] for r in recorder.records] == ["e-3", "e-4", "e-5"]

    async def test_stop_while_down_keeps_the_spool(self, tmp_path: Path) -> None:
        recorder = Recorder()
        recorder.down = True
        forwarder = SiemForwarder([recorder], tmp_path, flush_seconds=0.02)
        await forwarder.start()
        forwarder.forward(_record(0))
        await forwarder.stop(flush_seconds=0.1)

        recorder.down = False
        await SiemForwarder([recorder], tmp_path).flush()
        assert {r["event_type"] for r in recorder.records} == {"tool_call", "anchor"}


# ---------------------------------------------------------------------------
# Audit logger integration and anchors
# ---------------------------------------------------------------------------


class TestAuditLoggerHook:
    def test_file_records_are_forwarded_sealed(self, tmp_path: Path, monkeypatch: Any) -> None:
        from cryptography.fernet import Fernet

        monkeypatch.setenv("UNIFI_AUDIT_LOG_KEY", Fernet.generate_key().decode())
        logger = AuditLogger(tmp_path / "audit.log")
        recorder = Recorder()
        logger.forwarder = SiemForwarder([recorder], tmp_path / "spool")

        logger.log_operation("update_network", {"psk": "x", "vlan": 7}, "success")
        asyncio.run(logger.forwarder.flush())

        (exported,) = recorder.records
        (stored,) = [json.loads(line) for line in (tmp_path / "audit.log").read_text().splitlines()]
        assert exported == stored  # exactly the stored, sealed form
        assert exported["parameters_encrypted"] is True
        assert "vlan" not in json.dumps(exported)

    def test_unstored_records_are_not_forwarded(self, tmp_path: Path, monkeypatch: Any) -> None:
        logger = AuditLogger(tmp_path / "missing-dir-is-a-file" / "audit.log")
        recorder = Recorder()
        logger.forwarder = SiemForwarder([recorder], tmp_path / "spool")
        monkeypatch.setattr("builtins.open", _failing_open)

        logger.log_operation("update_network", {}, "success")
        monkeypatch.undo()
        asyncio.run(logger.forwarder.flush())
        assert recorder.records == []

    async def test_sink_records_are_forwarded_only_once_stored(self, tmp_path: Path) -> None:
        class Sink:
            def __init__(self) -> None:
                self.ok = True

            async def append(self, record: dict[str, Any], *, key: Any, strict: bool) -> bool:
                record.update(chain_id="s" * 32, seq=0, hash="0" * 64)
                return self.ok

        logger = AuditLogger(tmp_path / "audit.log")
        sink = Sink()
        logger.sink = sink
        recorder = Recorder()
        logger.forwarder = SiemForwarder([recorder], tmp_path / "spool")

        await logger.alog_event("admin", "token_created", "success")
        sink.ok = False
        await logger.alog_event("admin", "token_revoked", "success")
        logger.log_event("system", "server_start", "success")  # via _schedule
        await asyncio.gather(*logger._pending)
        await logger.forwarder.flush()

        assert [r["operation"] for r in recorder.records] == ["token_created"]
        sink.ok = True
        logger.log_event("system", "server_start", "success")
        await asyncio.gather(*logger._pending)
        await logger.forwarder.flush()
        assert [r["operation"] for r in recorder.records] == ["token_created", "server_start"]


def _failing_open(*args: Any, **kwargs: Any) -> Any:
    raise OSError("disk full")


class TestAnchorsVerifyTruncation:
    def test_exported_anchors_catch_a_truncated_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = tmp_path / "audit.log"
        logger = AuditLogger(log)
        recorder = Recorder()
        logger.forwarder = SiemForwarder([recorder], tmp_path / "spool")
        for n in range(4):
            logger.log_operation(f"op_{n}", {}, "success")
        asyncio.run(logger.forwarder.stop())  # sends the anchor
        export = tmp_path / "siem-export.jsonl"
        export.write_text("".join(json.dumps(r) + "\n" for r in recorder.records))

        assert verify_cli([str(log), "--anchors", str(export)]) == 0
        log.write_text("".join(log.read_text().splitlines(keepends=True)[:2]))
        assert verify_cli([str(log)]) == 0  # the file alone cannot tell
        assert verify_cli([str(log), "--anchors", str(export)]) == 1
        assert "missing from the end" in capsys.readouterr().out

    def test_load_anchors_takes_the_latest_per_chain(self, tmp_path: Path) -> None:
        path = tmp_path / "anchors.json"
        path.write_text(
            json.dumps(
                [
                    {"event_type": "anchor", "chain_id": "a", "seq": 3, "hash": "x"},
                    {"event_type": "anchor", "chain_id": "a", "seq": 7, "hash": "y"},
                    {"event_type": "anchor", "chain_id": "a", "seq": 5, "hash": "z"},
                    {"event_type": "tool_call", "chain_id": "b", "seq": 9, "hash": "w"},
                    {"event_type": "anchor", "chain_id": "c", "seq": "bad", "hash": "w"},
                ]
            )
        )
        assert load_anchors(path) == {"a": (7, "y")}

    def test_load_anchors_from_json_lines_with_junk(self, tmp_path: Path) -> None:
        path = tmp_path / "anchors.jsonl"
        path.write_text(
            '{"event_type": "anchor", "chain_id": "a", "seq": 1, "hash": "x"}\nnot json\n\n'
        )
        assert load_anchors(path) == {"a": (1, "x")}

    def test_cli_missing_anchors_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = tmp_path / "audit.log"
        AuditLogger(log).log_operation("op", {}, "success")
        assert verify_cli([str(log), "--anchors", str(tmp_path / "nope")]) == 2
        assert "anchors file not found" in capsys.readouterr().err

    def test_cli_anchors_file_without_anchors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = tmp_path / "audit.log"
        AuditLogger(log).log_operation("op", {}, "success")
        export = tmp_path / "export.jsonl"
        export.write_text('{"event_type": "tool_call"}\n', encoding="utf-8")
        assert verify_cli([str(log), "--anchors", str(export)]) == 2
        assert "no anchor events" in capsys.readouterr().err


class TestServerWiring:
    async def test_unset_starts_nothing(self, monkeypatch: Any, tmp_path: Path) -> None:
        settings = _settings(monkeypatch, tmp_path)
        from src.main import start_siem_forwarder

        assert await start_siem_forwarder(settings) is None

    async def test_invalid_target_stops_startup(self, monkeypatch: Any, tmp_path: Path) -> None:
        settings = _settings(monkeypatch, tmp_path, UNIFI_AUDIT_SIEM_TARGETS="ftp://x")
        from src.main import start_siem_forwarder

        with pytest.raises(ConfigurationError):
            await start_siem_forwarder(settings)

    async def test_target_without_chain_key_stops_startup(
        self, monkeypatch: Any, tmp_path: Path
    ) -> None:
        settings = _settings(
            monkeypatch, tmp_path, UNIFI_AUDIT_SIEM_TARGETS="syslog+tcp://127.0.0.1:1"
        )
        from src.main import start_siem_forwarder

        with pytest.raises(ConfigurationError, match="UNIFI_AUDIT_CHAIN_KEY"):
            await start_siem_forwarder(settings)

    async def test_configured_target_is_attached_to_the_audit_logger(
        self, monkeypatch: Any, tmp_path: Path
    ) -> None:
        settings = _settings(
            monkeypatch,
            tmp_path,
            UNIFI_AUDIT_SIEM_TARGETS="syslog+tcp://127.0.0.1:1",
            UNIFI_AUDIT_CHAIN_KEY="chain-key",  # pragma: allowlist secret
        )
        from src.main import start_siem_forwarder
        from src.utils.audit import get_audit_logger

        monkeypatch.setattr("src.utils.audit._audit_logger", None)
        forwarder = await start_siem_forwarder(settings)
        try:
            assert forwarder is not None
            assert get_audit_logger(settings.audit_log_file).forwarder is forwarder
        finally:
            await forwarder.stop(flush_seconds=0.1)
            get_audit_logger(settings.audit_log_file).forwarder = None
