"""Caller identity (src/access.py)."""

from typing import Any

import pytest
from fastmcp.server.auth import AccessToken

from src.access import LOCAL_PRINCIPAL, current_principal, request_principal, token_fingerprint
from src.tool_registry import _make_tool_wrapper

TOKEN = "s3cret-bearer-token-value"  # pragma: allowlist secret


def _access_token() -> AccessToken:
    return AccessToken(token=TOKEN, client_id="mcp-client", scopes=[])


def test_no_request_is_the_local_principal():
    assert request_principal() == LOCAL_PRINCIPAL
    assert LOCAL_PRINCIPAL.role == "admin"


def test_env_token_is_break_glass_admin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.access.get_access_token", _access_token)

    principal = request_principal()

    assert principal.id == f"env:{token_fingerprint(TOKEN)}"
    assert principal.name == "mcp-client"
    assert principal.role == "admin"
    assert principal.break_glass is True


def test_principal_never_contains_the_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.access.get_access_token", _access_token)

    principal = request_principal()

    assert TOKEN not in repr(principal)
    assert len(token_fingerprint(TOKEN)) == 12


def test_distinct_tokens_get_distinct_ids():
    assert token_fingerprint("token-a") != token_fingerprint("token-b")


async def test_wrapper_binds_principal_for_the_call_only(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.access.get_access_token", _access_token)
    seen: list[Any] = []

    async def spy(site_id: str, settings: Any = None) -> None:
        seen.append(current_principal.get())

    settings = type("S", (), {"dry_run": False, "metrics_enabled": False})()
    await _make_tool_wrapper(spy, settings)("default")

    assert seen[0].break_glass is True
    assert current_principal.get() is None
