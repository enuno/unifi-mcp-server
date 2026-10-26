"""Checks that the A2A layer and the server's RBAC agree.

The A2A authorization layer restates the server's role table in its own
vocabulary, because it cannot import ``src.access`` (that module reads the
request context). The restatement is a copy, and a copy can drift. These
tests make the drift visible.
"""

from __future__ import annotations

import pytest

from src.a2a.auth import _ROLE_TIERS, AuthManager, _tiers_for_role
from src.access import ROLE_TIERS, ROLES


class TestRoleTablesAgree:
    def test_the_same_roles_exist_in_both_tables(self) -> None:
        assert set(_ROLE_TIERS) == set(ROLES)

    @pytest.mark.parametrize("role", ROLES)
    def test_the_same_tiers_are_granted(self, role: str) -> None:
        """Each role grants the same risk tiers in both tables.

        The A2A table uses ``admin`` where the server's table uses
        ``fleet-admin`` for the top role, so the two are compared on the
        risk tiers they share.
        """
        server_tiers = ROLE_TIERS[role]
        a2a_tiers = _ROLE_TIERS[role]

        shared = {"read", "write", "destructive"}
        assert {t for t in server_tiers if t in shared} == {t for t in a2a_tiers if t in shared}

    def test_a_tool_the_server_does_not_know_is_not_assumed_readable(self) -> None:
        """An unknown name must not fall through to the read tier.

        A name the server does not know cannot be inspected, so it cannot
        be shown to be harmless.
        """
        auth = AuthManager()

        assert auth.required_permission("delete_thing") == "destructive"
        assert auth.required_permission("list_things") == "read"

    def test_only_the_top_role_is_granted_the_admin_permission(self) -> None:
        granted = [role for role, tiers in _ROLE_TIERS.items() if "admin" in tiers]

        assert granted == ["fleet-admin"]

    def test_the_fleet_admin_role_is_the_only_one_with_the_admin_permission(
        self,
    ) -> None:
        assert "fleet-admin" not in ROLE_TIERS["admin"]


class TestTierParityWithTheRegistry:
    """The A2A layer and the MCP path must agree on every tool's tier.

    A tool's tier decides what role may call it. If the A2A layer
    classified a tool differently from the path an MCP client takes, the
    same tool would be reachable by a weaker role over one interface than
    the other. The two must therefore resolve the same tier for every
    registered tool.
    """

    def test_every_registered_tool_has_the_same_tier_in_both_paths(self) -> None:
        """No registered tool may be reachable over A2A by a weaker role.

        The registry is read in a subprocess: importing the server
        in-process would reuse whatever ``src.main`` another test module
        already cached under a different environment.
        """
        import os
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        script = (
            "import json\n"
            "import src.main as main\n"
            "from src.a2a.auth import AuthManager\n"
            "from src.a2a.capabilities import iter_registered_tools\n"
            "from src.tool_registry import TOOL_TIERS, tool_tier\n"
            "auth = AuthManager()\n"
            "auth.register_tools({t.name: t for t in iter_registered_tools(main.mcp)})\n"
            "out = []\n"
            "for tool in iter_registered_tools(main.mcp):\n"
            "    fn = getattr(tool, 'fn', None)\n"
            "    mcp = TOOL_TIERS.get(tool.name) or tool_tier(fn)\n"
            "    a2a = auth.required_permission(tool.name)\n"
            "    if mcp != a2a:\n"
            "        out.append(f'{tool.name}: MCP={mcp} A2A={a2a}')\n"
            "print(json.dumps(out))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(root),
            env={
                **{k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
                "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
                "UNIFI_API_TYPE": "local",
                "UNIFI_LOCAL_HOST": "192.0.2.1",
                "AGNOST_ENABLED": "false",
            },
            capture_output=True,
            text=True,
            check=True,
        )
        import json

        mismatches = json.loads(result.stdout)

        assert not mismatches, "\n".join(mismatches)


class TestCallerPermissions:
    def test_an_anonymous_caller_gets_read_only(self) -> None:
        assert _tiers_for_role(None) == frozenset({"read"})

    def test_an_unknown_role_gets_read_only(self) -> None:
        """An unrecognised role must never widen access."""
        assert _tiers_for_role("superuser") == frozenset({"read"})

    def test_a_viewer_gets_read_only(self) -> None:
        assert _tiers_for_role("viewer") == frozenset({"read"})

    def test_an_operator_gets_read_and_write(self) -> None:
        assert _tiers_for_role("operator") == frozenset({"read", "write"})

    def test_an_admin_gets_destructive(self) -> None:
        assert "destructive" in _tiers_for_role("admin")

    def test_a_fleet_admin_gets_everything(self) -> None:
        assert _tiers_for_role("fleet-admin") >= {"read", "write", "destructive", "admin"}


class TestPayloadCannotWidenAccess:
    def _credentials(self, payload: dict, role: str | None) -> dict:
        return AuthManager().credentials_for_caller(payload, role)

    def test_a_payload_permission_list_is_ignored(self) -> None:
        credentials = self._credentials(
            {"auth": {"permissions": ["destructive", "admin"]}}, "viewer"
        )

        assert credentials["permissions"] == ["read"]

    def test_scopes_narrow_the_role(self) -> None:
        credentials = self._credentials({"scopes": ["read"]}, "admin")

        assert credentials["permissions"] == ["read"]

    def test_scopes_cannot_widen_the_role(self) -> None:
        """A scope the role does not hold narrows the grant to nothing.

        The result is an intersection, so a viewer asking for
        ``destructive`` ends up with no permission at all, never with
        ``destructive``.
        """
        credentials = self._credentials({"scopes": ["destructive", "admin"]}, "viewer")

        assert credentials["permissions"] == []
        assert "destructive" not in credentials["permissions"]
        assert "admin" not in credentials["permissions"]

    def test_no_scopes_keeps_the_role(self) -> None:
        credentials = self._credentials({}, "operator")

        assert credentials["permissions"] == ["read", "write"]

    def test_the_agent_id_is_recorded(self) -> None:
        credentials = self._credentials({"agent_id": "agent-7"}, "viewer")

        assert credentials["agent_id"] == "agent-7"
