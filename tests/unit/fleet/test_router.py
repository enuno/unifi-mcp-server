"""Unit tests for controller resolution (Phase 1 of docs/FLEET_SCALING_PLAN.md)."""

import asyncio
import contextvars
import random
from typing import Any

import pytest

from src.config.config import APIType, Settings
from src.fleet import ControllerProfile, EnvRegistry
from src.fleet.router import SESSION_KEY, FleetRouter, current_controller
from src.utils.exceptions import ResourceNotFoundError, ValidationError


class StaticRegistry:
    """In-memory registry with a fixed set of controllers."""

    def __init__(self, *profiles: ControllerProfile, default: str | None = None) -> None:
        self._profiles = {p.name: p for p in profiles}
        self._default = default

    async def list_controllers(self) -> list[ControllerProfile]:
        return list(self._profiles.values())

    async def get_controller(self, name: str) -> ControllerProfile:
        try:
            return self._profiles[name]
        except KeyError:
            raise ResourceNotFoundError("controller", name) from None

    async def default_controller(self) -> str | None:
        return self._default


class FakeContext:
    """Stands in for one MCP session's FastMCP Context."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {}

    async def get_state(self, key: str) -> Any:
        return self.state.get(key)

    async def set_state(self, key: str, value: Any) -> None:
        self.state[key] = value


_active_ctx: contextvars.ContextVar[FakeContext | None] = contextvars.ContextVar(
    "test_active_ctx", default=None
)


def _fake_get_context() -> FakeContext:
    ctx = _active_ctx.get()
    if ctx is None:
        raise RuntimeError("No active context found.")
    return ctx


@pytest.fixture(autouse=True)
def _patch_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.fleet.router.get_context", _fake_get_context)


@pytest.fixture
def base(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "base-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    return Settings()


def _profile(name: str, host: str) -> ControllerProfile:
    return ControllerProfile(
        name=name,
        api_type=APIType.LOCAL,
        api_key=f"{name}-key",  # pragma: allowlist secret
        local_host=host,
    )


@pytest.fixture
def two_controllers() -> StaticRegistry:
    return StaticRegistry(_profile("hq", "10.0.0.1"), _profile("branch", "10.0.1.1"), default="hq")


class TestZeroConfig:
    async def test_env_registry_hands_out_the_base_settings_object(self, base: Settings):
        router = FleetRouter(base, EnvRegistry(base))

        resolution = await router.resolve(None, mutating=True)

        assert resolution.name == "default"
        assert resolution.source == "default"
        assert resolution.settings is base

    async def test_explicit_default_is_accepted(self, base: Settings):
        resolution = await FleetRouter(base, EnvRegistry(base)).resolve("default", mutating=True)

        assert resolution.settings is base
        assert resolution.source == "explicit"

    async def test_unknown_controller_is_rejected(self, base: Settings):
        with pytest.raises(ResourceNotFoundError, match="controller 'nope' not found"):
            await FleetRouter(base, EnvRegistry(base)).resolve("nope", mutating=False)


class TestResolutionOrder:
    async def test_explicit_wins_over_session_and_default(self, base, two_controllers):
        router = FleetRouter(base, two_controllers)
        _active_ctx.set(FakeContext())
        await router.select("hq")

        resolution = await router.resolve("branch", mutating=True)

        assert (resolution.name, resolution.source) == ("branch", "explicit")
        assert resolution.settings.local_host == "10.0.1.1"
        assert resolution.settings.api_key == "branch-key"  # pragma: allowlist secret

    async def test_session_selection_wins_over_default(self, base, two_controllers):
        router = FleetRouter(base, two_controllers)
        _active_ctx.set(FakeContext())
        await router.select("branch")

        resolution = await router.resolve(None, mutating=False)

        assert (resolution.name, resolution.source) == ("branch", "session")

    async def test_default_used_for_reads(self, base, two_controllers):
        resolution = await FleetRouter(base, two_controllers).resolve(None, mutating=False)

        assert (resolution.name, resolution.source) == ("hq", "default")

    async def test_no_target_at_all_is_an_error(self, base):
        router = FleetRouter(base, StaticRegistry(_profile("a", "10.0.0.1")))

        with pytest.raises(ValidationError, match="No controller"):
            await router.resolve(None, mutating=False)

    async def test_select_unknown_controller_is_rejected(self, base, two_controllers):
        _active_ctx.set(FakeContext())

        with pytest.raises(ResourceNotFoundError):
            await FleetRouter(base, two_controllers).select("nope")

    async def test_select_without_session_is_an_error(self, base, two_controllers):
        _active_ctx.set(None)

        with pytest.raises(ValidationError, match="session"):
            await FleetRouter(base, two_controllers).select("hq")

    async def test_session_controller_removed_from_registry(self, base, two_controllers):
        ctx = FakeContext()
        ctx.state[SESSION_KEY] = "retired"
        _active_ctx.set(ctx)

        with pytest.raises(ResourceNotFoundError, match="retired"):
            await FleetRouter(base, two_controllers).resolve(None, mutating=False)


class TestWriteTargetRule:
    async def test_write_on_registry_default_is_refused_with_several_controllers(
        self, base, two_controllers
    ):
        with pytest.raises(ValidationError, match="controller"):
            await FleetRouter(base, two_controllers).resolve(None, mutating=True)

    async def test_write_allowed_with_explicit_target(self, base, two_controllers):
        resolution = await FleetRouter(base, two_controllers).resolve("hq", mutating=True)

        assert resolution.name == "hq"

    async def test_write_allowed_with_session_selection(self, base, two_controllers):
        router = FleetRouter(base, two_controllers)
        _active_ctx.set(FakeContext())
        await router.select("branch")

        assert (await router.resolve(None, mutating=True)).name == "branch"

    async def test_write_on_default_allowed_with_single_controller(self, base):
        router = FleetRouter(base, StaticRegistry(_profile("only", "10.0.0.1"), default="only"))

        assert (await router.resolve(None, mutating=True)).name == "only"


class TestSettingsDerivation:
    async def test_derived_settings_are_reused(self, base, two_controllers):
        router = FleetRouter(base, two_controllers)

        first = await router.resolve("branch", mutating=False)
        second = await router.resolve("branch", mutating=False)

        assert first.settings is second.settings

    async def test_safety_flags_come_from_base(self, monkeypatch, two_controllers):
        monkeypatch.setenv("UNIFI_API_KEY", "base-key")  # pragma: allowlist secret
        monkeypatch.setenv("UNIFI_DRY_RUN", "true")
        base = Settings()

        resolution = await FleetRouter(base, two_controllers).resolve("branch", mutating=False)

        assert resolution.settings.dry_run is True


class TestSessionIsolation:
    async def test_interleaved_sessions_never_see_each_others_controller(
        self, base, two_controllers
    ):
        # Two MCP sessions select different controllers, then interleave
        # 1,000 calls; every call must resolve to its own session's choice.
        router = FleetRouter(base, two_controllers)
        mismatches: list[tuple[str, str]] = []

        async def session(choice: str) -> None:
            _active_ctx.set(FakeContext())
            await router.select(choice)
            for _ in range(500):
                await asyncio.sleep(random.random() / 1000)
                resolution = await router.resolve(None, mutating=True)
                if resolution.name != choice:
                    mismatches.append((choice, resolution.name))

        await asyncio.gather(session("hq"), session("branch"))

        assert mismatches == []

    async def test_current_controller_is_unset_outside_calls(self):
        assert current_controller.get() is None
