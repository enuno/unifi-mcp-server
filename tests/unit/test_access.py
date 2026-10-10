"""Caller identity (src/access.py)."""

from typing import Any

import pytest
from fastmcp.server.auth import AccessToken

from src.access import (
    LOCAL_PRINCIPAL,
    Principal,
    current_principal,
    request_principal,
    token_fingerprint,
)
from src.tool_registry import _make_tool_wrapper

TOKEN = "s3cret-bearer-token-value"  # pragma: allowlist secret


def _access_token() -> AccessToken:
    return AccessToken(token=TOKEN, client_id="mcp-client", scopes=[])


def test_no_request_is_the_local_principal():
    assert request_principal() == LOCAL_PRINCIPAL
    assert LOCAL_PRINCIPAL.role == "fleet-admin"


def test_env_token_is_break_glass_fleet_admin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.access.get_access_token", _access_token)

    principal = request_principal()

    assert principal.id == f"env:{token_fingerprint(TOKEN)}"
    assert principal.name == "mcp-client"
    assert principal.role == "fleet-admin"
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


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        ("viewer", {"read"}),
        ("operator", {"read", "write"}),
        ("admin", {"read", "write", "destructive"}),
        ("fleet-admin", {"read", "write", "destructive", "fleet-admin"}),
    ],
)
def test_role_tier_matrix(role, allowed):
    principal = Principal(id="t", name="t", role=role)

    for tier in ("read", "write", "destructive", "fleet-admin"):
        assert principal.can_use(tier) is (tier in allowed), (role, tier)


def test_module_filters():
    only_devices = Principal(id="t", name="t", role="admin", allow_modules=("devices", "protect_*"))
    no_firewall = Principal(id="t", name="t", role="admin", deny_modules=("firewall*",))

    assert only_devices.allows_module("devices")
    assert only_devices.allows_module("protect_cameras")
    assert not only_devices.allows_module("firewall")
    assert no_firewall.allows_module("devices")
    assert not no_firewall.allows_module("firewall_policies")


def test_deny_wins_over_allow():
    principal = Principal(
        id="t", name="t", role="admin", allow_modules=("*",), deny_modules=("backups",)
    )

    assert not principal.allows_module("backups")


def test_controller_label_selector():
    retail = Principal(id="t", name="t", role="admin", controller_labels={"group": "retail"})

    assert retail.allows_controller({"group": "retail", "region": "west"})
    assert not retail.allows_controller({"group": "office"})
    assert not retail.allows_controller({})
    assert Principal(id="t", name="t", role="admin").allows_controller({})


def test_issued_token_claims_become_the_principal(monkeypatch: pytest.MonkeyPatch):
    claims = {
        "token_id": "abc",
        "name": "ops-bot",
        "role": "operator",
        "allow_modules": ["devices"],
        "deny_modules": [],
        "controller_labels": {"group": "retail"},
    }
    monkeypatch.setattr(
        "src.access.get_access_token",
        lambda: AccessToken(token="umcp_x", client_id="ops-bot", scopes=[], claims=claims),
    )

    principal = request_principal()

    assert principal == Principal(
        id="token:abc",
        name="ops-bot",
        role="operator",
        allow_modules=("devices",),
        controller_labels={"group": "retail"},
    )
    assert principal.break_glass is False


def test_local_role_can_be_lowered():
    assert request_principal("viewer").role == "viewer"
    assert request_principal("viewer").break_glass is True
