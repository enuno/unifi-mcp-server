"""Unit tests for the fleet controller registry (Phase 0 of FLEET_SCALING_PLAN)."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.config.config import APIType, Settings
from src.fleet import DEFAULT_CONTROLLER_NAME, ControllerProfile, ControllerRegistry, EnvRegistry
from src.utils.exceptions import ResourceNotFoundError


@pytest.fixture
def local_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "base-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    monkeypatch.setenv("UNIFI_LOCAL_VERIFY_SSL", "false")
    monkeypatch.setenv("UNIFI_READ_ONLY", "true")
    return Settings()


def _profile(**overrides: object) -> ControllerProfile:
    fields: dict[str, object] = {
        "name": "branch-1",
        "api_type": APIType.LOCAL,
        "api_key": "branch-key",  # pragma: allowlist secret
        "local_host": "10.0.0.1",
    }
    fields.update(overrides)
    return ControllerProfile(**fields)


class TestControllerProfile:
    def test_apply_to_overrides_connection_fields(self, local_settings: Settings):
        derived = _profile(local_port=8443, default_site="hq").apply_to(local_settings)

        assert derived.api_key == "branch-key"  # pragma: allowlist secret
        assert derived.local_host == "10.0.0.1"
        assert derived.local_port == 8443
        assert derived.default_site == "hq"

    def test_apply_to_keeps_unset_fields_from_base(self, local_settings: Settings):
        derived = _profile().apply_to(local_settings)

        assert derived.local_port == local_settings.local_port
        assert derived.local_verify_ssl is False

    def test_apply_to_never_changes_safety_flags(self, local_settings: Settings):
        derived = _profile().apply_to(local_settings)

        assert derived.read_only is True
        assert derived.dry_run == local_settings.dry_run
        assert derived.audit_log_enabled == local_settings.audit_log_enabled

    def test_apply_to_does_not_mutate_base(self, local_settings: Settings):
        _profile().apply_to(local_settings)

        assert local_settings.api_key == "base-key"  # pragma: allowlist secret
        assert local_settings.local_host == "192.168.2.1"

    def test_safety_flags_are_not_profile_fields(self):
        with pytest.raises(PydanticValidationError):
            _profile(read_only=False)

    def test_local_profile_requires_host(self):
        with pytest.raises(PydanticValidationError, match="local_host"):
            _profile(local_host=None)

    @pytest.mark.parametrize("name", ["", "Branch", "has space", "-leading", "x" * 64])
    def test_rejects_invalid_names(self, name: str):
        with pytest.raises(PydanticValidationError):
            _profile(name=name)

    def test_api_key_not_in_repr(self):
        assert "branch-key" not in repr(_profile())


class TestEnvRegistry:
    def test_satisfies_protocol(self, local_settings: Settings):
        assert isinstance(EnvRegistry(local_settings), ControllerRegistry)

    @pytest.mark.asyncio
    async def test_exposes_single_default_controller(self, local_settings: Settings):
        registry = EnvRegistry(local_settings)

        controllers = await registry.list_controllers()

        assert [c.name for c in controllers] == [DEFAULT_CONTROLLER_NAME]
        assert await registry.default_controller() == DEFAULT_CONTROLLER_NAME

    @pytest.mark.asyncio
    async def test_default_profile_reproduces_env_settings(self, local_settings: Settings):
        # The zero-config guarantee: routing through the env registry must
        # yield exactly the settings the server uses today.
        profile = await EnvRegistry(local_settings).get_controller(DEFAULT_CONTROLLER_NAME)

        assert profile.apply_to(local_settings) == local_settings

    @pytest.mark.asyncio
    async def test_cloud_settings_round_trip(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "cloud-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()

        profile = await EnvRegistry(settings).get_controller(DEFAULT_CONTROLLER_NAME)

        assert profile.api_type == APIType.CLOUD_EA
        assert profile.apply_to(settings) == settings

    @pytest.mark.asyncio
    async def test_unknown_controller_raises(self, local_settings: Settings):
        with pytest.raises(ResourceNotFoundError, match="controller 'nope' not found"):
            await EnvRegistry(local_settings).get_controller("nope")
