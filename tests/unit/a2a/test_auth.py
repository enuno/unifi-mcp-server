"""Unit tests for src/a2a/auth.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.a2a.auth import AuthContext, AuthManager, CloudAuthProvider, LocalAuthProvider
from src.config import APIType


class TestAuthContext:
    """Tests for AuthContext."""

    def test_defaults_to_no_permissions_and_no_expiry(self) -> None:
        context = AuthContext(mode="local", credentials={})

        assert context.permissions == set()
        assert context.expiry is None

    def test_a_context_without_an_expiry_never_expires(self) -> None:
        assert AuthContext(mode="local", credentials={}).is_expired() is False

    def test_a_past_expiry_is_expired(self) -> None:
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=1)

        assert AuthContext(mode="local", credentials={}, expiry=past).is_expired() is True

    def test_a_future_expiry_is_not_expired(self) -> None:
        future = datetime.now(tz=timezone.utc) + timedelta(hours=1)

        assert AuthContext(mode="local", credentials={}, expiry=future).is_expired() is False


class TestLocalAuthProvider:
    """Tests for LocalAuthProvider."""

    def test_authenticate_reports_local_mode(self) -> None:
        context = LocalAuthProvider().authenticate({"api_key": "k"})

        assert context.mode == APIType.LOCAL.value
        assert context.credentials == {"api_key": "k"}

    def test_explicit_permissions_are_normalized_and_win(self) -> None:
        context = LocalAuthProvider().authenticate({"api_key": "k", "permissions": ["READ", None]})

        assert context.permissions == {"read"}

    @pytest.mark.parametrize("credential", ["api_key", "token", "username"])
    def test_any_credential_grants_full_local_permissions(self, credential: str) -> None:
        context = LocalAuthProvider().authenticate({credential: "value"})

        assert context.permissions == {"read", "write", "destructive"}

    def test_anonymous_access_is_read_only(self) -> None:
        assert LocalAuthProvider().authenticate({}).permissions == {"read"}

    def test_expiry_uses_the_default_ttl(self) -> None:
        before = datetime.now(tz=timezone.utc)

        context = LocalAuthProvider(default_ttl_seconds=60).authenticate({})

        assert context.expiry is not None
        assert timedelta(seconds=55) <= context.expiry - before <= timedelta(seconds=65)

    def test_expires_in_overrides_the_default_ttl(self) -> None:
        before = datetime.now(tz=timezone.utc)

        context = LocalAuthProvider(default_ttl_seconds=3600).authenticate({"expires_in": 30})

        assert context.expiry is not None
        assert context.expiry - before <= timedelta(seconds=35)

    def test_a_non_positive_ttl_is_clamped_to_one_second(self) -> None:
        before = datetime.now(tz=timezone.utc)

        context = LocalAuthProvider().authenticate({"expires_in": -100})

        assert context.expiry is not None
        assert timedelta(0) < context.expiry - before <= timedelta(seconds=5)

    def test_refresh_extends_the_expiry_and_keeps_the_payload(self) -> None:
        provider = LocalAuthProvider()
        original = provider.authenticate({"api_key": "k", "expires_in": 1})

        refreshed = provider.refresh(original)

        assert refreshed.credentials == original.credentials
        assert refreshed.permissions == original.permissions
        assert refreshed.mode == original.mode
        assert refreshed.expiry is not None


class TestCloudAuthProvider:
    """Tests for CloudAuthProvider."""

    def test_defaults_to_the_cloud_ea_mode(self) -> None:
        assert CloudAuthProvider().authenticate({}).mode == APIType.CLOUD_EA.value

    def test_an_explicit_mode_is_lowercased(self) -> None:
        assert CloudAuthProvider().authenticate({"mode": "CLOUD-V1"}).mode == "cloud-v1"

    @pytest.mark.parametrize("scope", ["read", "viewer", "view"])
    def test_read_scopes_grant_read(self, scope: str) -> None:
        assert CloudAuthProvider().authenticate({"scopes": [scope]}).permissions == {"read"}

    @pytest.mark.parametrize("scope", ["write", "editor", "manage"])
    def test_write_scopes_grant_write(self, scope: str) -> None:
        assert CloudAuthProvider().authenticate({"scopes": [scope]}).permissions == {"write"}

    def test_destructive_scope_grants_write_and_destructive(self) -> None:
        permissions = CloudAuthProvider().authenticate({"scopes": ["destructive"]}).permissions

        assert permissions == {"write", "destructive"}

    @pytest.mark.parametrize("scope", ["admin", "owner"])
    def test_admin_scopes_grant_everything(self, scope: str) -> None:
        permissions = CloudAuthProvider().authenticate({"scopes": [scope]}).permissions

        assert permissions == {"write", "destructive", "admin"}

    def test_permissions_key_is_accepted_instead_of_scopes(self) -> None:
        assert CloudAuthProvider().authenticate({"permissions": ["write"]}).permissions == {"write"}

    def test_none_scopes_are_ignored(self) -> None:
        assert CloudAuthProvider().authenticate({"scopes": ["read", None]}).permissions == {"read"}

    def test_unknown_scopes_fall_back_to_read_only(self) -> None:
        assert CloudAuthProvider().authenticate({"scopes": ["bogus"]}).permissions == {"read"}

    def test_missing_scopes_fall_back_to_read_only(self) -> None:
        assert CloudAuthProvider().authenticate({}).permissions == {"read"}

    def test_expires_in_overrides_the_default_ttl(self) -> None:
        before = datetime.now(tz=timezone.utc)

        context = CloudAuthProvider(default_ttl_seconds=1800).authenticate({"expires_in": 30})

        assert context.expiry is not None
        assert context.expiry - before <= timedelta(seconds=35)

    def test_refresh_returns_a_context_with_a_new_expiry(self) -> None:
        provider = CloudAuthProvider()
        original = provider.authenticate({"scopes": ["admin"], "expires_in": 1})

        refreshed = provider.refresh(original)

        assert refreshed.permissions == original.permissions
        assert refreshed.expiry is not None


class TestAuthManagerNormalizeMode:
    """Tests for AuthManager._normalize_mode."""

    def test_accepts_an_api_type_enum(self) -> None:
        assert AuthManager._normalize_mode(APIType.LOCAL) == "local"

    def test_trims_and_lowercases_strings(self) -> None:
        assert AuthManager._normalize_mode("  LOCAL  ") == "local"

    def test_the_generic_cloud_mode_maps_to_cloud_ea(self) -> None:
        assert AuthManager._normalize_mode(APIType.CLOUD.value) == APIType.CLOUD_EA.value


class TestAuthManagerAuthenticate:
    """Tests for AuthManager.authenticate."""

    def test_local_mode_uses_the_local_provider(self) -> None:
        context = AuthManager().authenticate(APIType.LOCAL, {"api_key": "k"})

        assert context.mode == APIType.LOCAL.value
        assert context.permissions == {"read", "write", "destructive"}

    @pytest.mark.parametrize("mode", [APIType.CLOUD_EA, APIType.CLOUD_V1])
    def test_cloud_modes_use_the_cloud_provider(self, mode: APIType) -> None:
        context = AuthManager().authenticate(mode, {"scopes": ["admin"]})

        assert context.mode == mode.value
        assert "admin" in context.permissions

    def test_unsupported_modes_raise(self) -> None:
        with pytest.raises(ValueError, match="Unsupported auth mode: carrier-pigeon"):
            AuthManager().authenticate("carrier-pigeon", {})


class TestAuthManagerRefresh:
    """Tests for AuthManager.refresh."""

    def test_local_contexts_are_refreshed_locally(self) -> None:
        manager = AuthManager()
        context = manager.authenticate(APIType.LOCAL, {"api_key": "k"})

        assert manager.refresh(context).mode == APIType.LOCAL.value

    def test_cloud_contexts_are_refreshed_in_the_cloud(self) -> None:
        manager = AuthManager()
        context = manager.authenticate(APIType.CLOUD_EA, {"scopes": ["write"]})

        assert manager.refresh(context).permissions == {"write"}


class TestRequiredPermission:
    """Tests for AuthManager._required_permission."""

    @pytest.mark.parametrize(
        "tool_name",
        ["delete_site", "remove_client", "reset_device", "revoke_key", "purge_logs", "wipe_site"],
    )
    def test_destructive_prefixes(self, tool_name: str) -> None:
        assert AuthManager._required_permission(tool_name) == "destructive"

    @pytest.mark.parametrize(
        "tool_name",
        ["create_wlan", "add_client", "update_site", "set_flag", "reboot_device", "adopt_device"],
    )
    def test_write_prefixes(self, tool_name: str) -> None:
        assert AuthManager._required_permission(tool_name) == "write"

    @pytest.mark.parametrize("tool_name", ["list_sites", "get_device", "  LIST_SITES  "])
    def test_everything_else_is_read(self, tool_name: str) -> None:
        assert AuthManager._required_permission(tool_name) == "read"


class TestValidatePermissions:
    """Tests for AuthManager.validate_permissions."""

    @pytest.fixture
    def manager(self) -> AuthManager:
        return AuthManager()

    def make_context(self, *permissions: str) -> AuthContext:
        """Build a context granting exactly the given permissions."""
        return AuthContext(mode="local", credentials={}, permissions=set(permissions))

    def test_admin_may_do_anything(self, manager: AuthManager) -> None:
        context = self.make_context("admin")

        assert manager.validate_permissions(context, "delete_site") is True

    @pytest.mark.parametrize("permission", ["read", "write", "destructive"])
    def test_read_tools_accept_any_permission(self, manager: AuthManager, permission: str) -> None:
        assert manager.validate_permissions(self.make_context(permission), "list_sites") is True

    def test_read_tools_reject_an_empty_context(self, manager: AuthManager) -> None:
        assert manager.validate_permissions(self.make_context(), "list_sites") is False

    def test_write_tools_reject_read_only(self, manager: AuthManager) -> None:
        assert manager.validate_permissions(self.make_context("read"), "create_wlan") is False

    @pytest.mark.parametrize("permission", ["write", "destructive"])
    def test_write_tools_accept_write_or_destructive(
        self, manager: AuthManager, permission: str
    ) -> None:
        assert manager.validate_permissions(self.make_context(permission), "create_wlan") is True

    def test_destructive_tools_require_the_destructive_permission(
        self, manager: AuthManager
    ) -> None:
        assert manager.validate_permissions(self.make_context("write"), "delete_site") is False
        assert manager.validate_permissions(self.make_context("destructive"), "delete_site") is True

    def test_permissions_are_compared_case_insensitively(self, manager: AuthManager) -> None:
        assert manager.validate_permissions(self.make_context("DESTRUCTIVE"), "delete_site") is True
