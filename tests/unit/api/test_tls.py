"""Settings.verify_ssl to httpx verify= (src/api/tls.py)."""

import ssl

import certifi
import httpx
import pytest

from src.api.client import UniFiClient
from src.api.tls import httpx_verify
from src.config.config import Settings


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
