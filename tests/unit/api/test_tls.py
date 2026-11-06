"""Settings.verify_ssl to httpx verify= (src/api/tls.py)."""

import contextlib
import datetime
import socket
import ssl
import threading
from collections.abc import Iterator
from pathlib import Path

import certifi
import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from src.api import tls
from src.api.client import UniFiClient
from src.api.pool import ClientPool
from src.api.protect_client import ProtectClient
from src.api.tls import httpx_verify, tls_event_hooks
from src.config.config import Settings

CANARY = "canary-api-key"  # pragma: allowlist secret


class TestHttpxVerify:
    def test_bools_pass_through(self):
        assert httpx_verify(True) is True
        assert httpx_verify(False) is False

    def test_ca_file_becomes_a_verifying_context(self):
        context = httpx_verify(certifi.where())
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True

    def test_context_is_reused_per_path(self):
        assert httpx_verify(certifi.where()) is httpx_verify(certifi.where())


async def test_client_verifies_with_the_ca_file(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UNIFI_API_KEY", "key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
    monkeypatch.setenv("UNIFI_LOCAL_CA_FILE", certifi.where())
    captured: dict = {}
    real_client = httpx.AsyncClient

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", spy)
    client = UniFiClient(Settings())
    try:
        assert captured["verify"] is httpx_verify(certifi.where())
    finally:
        await client.client.aclose()


def _write_self_signed(directory: Path, *, unifi_os: bool) -> tuple[Path, Path]:
    """Write a self-signed certificate for ``unifi.local`` and its key; return both paths.

    ``unifi_os=True`` shapes it like the certificate UniFi OS generates for itself:
    Key Usage includes keyCertSign, and there is no Basic Constraints extension.
    Python 3.13's strict verification rejects that as "invalid CA certificate".
    Either way it names only ``unifi.local``: 127.0.0.1, where the test server
    listens, stands in for the console's LAN address, which UniFi's certificate
    does not name either.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "unifi.local")])
    now = datetime.datetime.now(datetime.UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("unifi.local")]), critical=False)
    )
    if unifi_os:
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=True,
                data_encipherment=True,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=False,
        ).add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]
            ),
            critical=False,
        )
    else:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        ).add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    cert = builder.sign(key, hashes.SHA256())
    stem = "unifi-os" if unifi_os else "other"
    cert_path, key_path = directory / f"{stem}.pem", directory / f"{stem}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class _Console:
    """An HTTPS server on 127.0.0.1 that records the bytes each client sent after the handshake."""

    def __init__(self, cert: Path, key: Path) -> None:
        self.cert = cert
        self._context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._context.load_cert_chain(cert, key)
        self._listener = socket.create_server(("127.0.0.1", 0))
        self._listener.settimeout(0.2)
        self.port = self._listener.getsockname()[1]
        self.received = b""
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                raw, _ = self._listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            raw.settimeout(5)
            try:
                conn = self._context.wrap_socket(raw, server_side=True)
            except OSError:  # the client refused the certificate
                raw.close()
                continue
            with conn, contextlib.suppress(OSError):
                data = b""
                while b"\r\n\r\n" not in data:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                self.received += data
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    b"Content-Length: 2\r\nConnection: close\r\n\r\n{}"
                )

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._listener.close()


@pytest.fixture
def unifi_os_console(tmp_path: Path) -> Iterator[_Console]:
    """A console presenting a UniFi OS-shaped certificate."""
    console = _Console(*_write_self_signed(tmp_path, unifi_os=True))
    yield console
    console.close()


@pytest.fixture
def impostor(tmp_path: Path) -> Iterator[_Console]:
    """A server presenting another self-signed certificate for the same name."""
    console = _Console(*_write_self_signed(tmp_path, unifi_os=False))
    yield console
    console.close()


@pytest.fixture
def python313_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``ssl.create_default_context`` strict, as it is from Python 3.13 on.

    CI runs Python 3.11 and 3.12, whose default contexts are not strict, so
    without this the tests below could not catch a strict CA-file context.
    """
    real = ssl.create_default_context

    def strict_default(*args, **kwargs):  # type: ignore[no-untyped-def]
        context = real(*args, **kwargs)
        context.verify_flags |= ssl.VERIFY_X509_STRICT
        return context

    monkeypatch.setattr(ssl, "create_default_context", strict_default)
    tls._context_for.cache_clear()
    yield
    tls._context_for.cache_clear()


async def _get(console: _Console, ca_file: Path, server_name: str | None) -> httpx.Response:
    async with httpx.AsyncClient(
        headers={"X-API-KEY": CANARY},
        verify=httpx_verify(str(ca_file)),
        event_hooks=tls_event_hooks(server_name),
    ) as client:
        return await client.get(f"https://127.0.0.1:{console.port}/proxy/network/api/self")


class TestUniFiOSCertificate:
    """UNIFI_LOCAL_CA_FILE set to the console's own certificate."""

    def test_strict_verification_rejects_it(self, unifi_os_console: _Console):
        # Why the CA-file context must not be strict: this is the error Python 3.13+ gives.
        context = ssl.create_default_context(cafile=str(unifi_os_console.cert))
        context.verify_flags |= ssl.VERIFY_X509_STRICT
        with socket.create_connection(("127.0.0.1", unifi_os_console.port)) as sock:
            with pytest.raises(ssl.SSLCertVerificationError, match="invalid CA certificate"):
                context.wrap_socket(sock, server_hostname="unifi.local")

    def test_ca_file_context_is_not_strict(self, python313_defaults):
        context = httpx_verify(certifi.where())
        assert isinstance(context, ssl.SSLContext)
        assert not context.verify_flags & ssl.VERIFY_X509_STRICT
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True

    async def test_it_is_trusted_by_its_name(self, unifi_os_console: _Console, python313_defaults):
        response = await _get(unifi_os_console, unifi_os_console.cert, "unifi.local")
        assert response.status_code == 200
        assert CANARY.encode() in unifi_os_console.received

    async def test_the_address_alone_does_not_match_it(self, unifi_os_console: _Console):
        with pytest.raises(httpx.ConnectError, match="IP address mismatch"):
            await _get(unifi_os_console, unifi_os_console.cert, None)
        assert unifi_os_console.received == b""

    async def test_another_name_does_not_match_it(self, unifi_os_console: _Console):
        with pytest.raises(httpx.ConnectError, match="mismatch"):
            await _get(unifi_os_console, unifi_os_console.cert, "other.local")
        assert unifi_os_console.received == b""

    async def test_another_certificate_never_gets_the_key(
        self, unifi_os_console: _Console, impostor: _Console, python313_defaults
    ):
        with pytest.raises(httpx.ConnectError, match="certificate verify failed"):
            await _get(impostor, unifi_os_console.cert, "unifi.local")
        assert impostor.received == b""


class TestServerNameWiring:
    """UNIFI_LOCAL_TLS_SERVER_NAME reaches every client built for the local controller."""

    @pytest.fixture
    def named(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        monkeypatch.setenv("UNIFI_API_KEY", "key")  # pragma: allowlist secret
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
        monkeypatch.setenv("UNIFI_LOCAL_TLS_SERVER_NAME", "unifi.local")
        return Settings()

    @staticmethod
    async def _server_name(client: httpx.AsyncClient) -> str | None:
        request = httpx.Request("GET", "https://10.0.0.1/")
        for hook in client.event_hooks["request"]:
            await hook(request)
        return request.extensions.get("sni_hostname")

    def test_no_name_adds_no_hooks(self):
        assert tls_event_hooks(None) == {}

    async def test_unifi_client(self, named: Settings):
        client = UniFiClient(named)
        try:
            assert await self._server_name(client.client) == "unifi.local"
        finally:
            await client.client.aclose()

    async def test_protect_client(self, named: Settings):
        client = ProtectClient(named)
        try:
            assert await self._server_name(client.client) == "unifi.local"
        finally:
            await client.client.aclose()

    async def test_pooled_connection(self, named: Settings):
        pool = ClientPool()
        connection = pool.acquire(named)
        try:
            assert await self._server_name(connection.client) == "unifi.local"
        finally:
            await connection.client.aclose()

    async def test_unifi_client_reaches_a_unifi_os_console(
        self, unifi_os_console: _Console, monkeypatch: pytest.MonkeyPatch, python313_defaults
    ):
        monkeypatch.setenv("UNIFI_API_KEY", CANARY)
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "127.0.0.1")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", str(unifi_os_console.port))
        monkeypatch.setenv("UNIFI_LOCAL_CA_FILE", str(unifi_os_console.cert))
        monkeypatch.setenv("UNIFI_LOCAL_TLS_SERVER_NAME", "unifi.local")
        client = UniFiClient(Settings())
        try:
            response = await client.client.get(
                f"https://127.0.0.1:{unifi_os_console.port}/proxy/network/api/self"
            )
        finally:
            await client.client.aclose()
        assert response.status_code == 200
        assert CANARY.encode() in unifi_os_console.received
