"""Controller registry: the named UniFi controllers this server can reach.

Phase 0 of ``docs/FLEET_SCALING_PLAN.md``. A :class:`ControllerProfile` holds
the connection details for one controller; :meth:`ControllerProfile.apply_to`
derives that controller's :class:`Settings` from the process-wide base
settings. A :class:`ControllerRegistry` looks profiles up by name.

:class:`EnvRegistry` is the zero-config registry: one controller named
``default``, built from today's ``UNIFI_*`` environment variables, so a
deployment without a database behaves exactly as before.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..config import APIType, Settings
from ..utils.exceptions import ResourceNotFoundError

#: Name of the single controller the environment registry exposes.
DEFAULT_CONTROLLER_NAME = "default"

#: The only Settings fields a profile may override. Safety switches
#: (read_only, dry_run, audit logging, auth) stay process-wide so one
#: controller's entry can never relax them.
_CONNECTION_FIELDS = (
    "api_type",
    "api_key",
    "cloud_api_url",
    "local_host",
    "local_port",
    "local_verify_ssl",
    "default_site",
)


class ControllerProfile(BaseModel):
    """Connection details for one named controller.

    Optional fields left as ``None`` inherit the base settings' value.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,62}$",
        description="Routing handle: lowercase letters, digits, '-' or '_'",
    )
    api_type: APIType
    api_key: str = Field(..., repr=False)
    cloud_api_url: str | None = None
    local_host: str | None = None
    local_port: int | None = Field(default=None, ge=1, le=65535)
    local_verify_ssl: bool | None = None
    default_site: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_local_host(self) -> "ControllerProfile":
        """A local controller needs a host, as the base Settings require."""
        if self.api_type == APIType.LOCAL and not self.local_host:
            raise ValueError("local_host is required when api_type is 'local'")
        return self

    def apply_to(self, base: Settings) -> Settings:
        """Return a copy of ``base`` pointed at this controller.

        Args:
            base: The process-wide settings

        Returns:
            New settings with this profile's connection fields applied;
            ``base`` is not modified.
        """
        update = {
            field: value
            for field in _CONNECTION_FIELDS
            if (value := getattr(self, field)) is not None
        }
        return base.model_copy(update=update)


@runtime_checkable
class ControllerRegistry(Protocol):
    """Looks up controller profiles by name."""

    async def list_controllers(self) -> list[ControllerProfile]:
        """Return every registered controller."""
        ...

    async def get_controller(self, name: str) -> ControllerProfile:
        """Return the named controller.

        Raises:
            ResourceNotFoundError: If no controller has that name
        """
        ...

    async def default_controller(self) -> str | None:
        """Return the name of the default controller, if one is set."""
        ...


class EnvRegistry:
    """Registry holding the single controller configured by environment."""

    def __init__(self, settings: Settings) -> None:
        """Build the ``default`` profile from ``settings``.

        Args:
            settings: The process-wide settings
        """
        self._profile = ControllerProfile(
            name=DEFAULT_CONTROLLER_NAME,
            **{field: getattr(settings, field) for field in _CONNECTION_FIELDS},
        )

    async def list_controllers(self) -> list[ControllerProfile]:
        """Return the single environment-configured controller."""
        return [self._profile]

    async def get_controller(self, name: str) -> ControllerProfile:
        """Return the controller if ``name`` is ``default``.

        Raises:
            ResourceNotFoundError: For any other name
        """
        if name != DEFAULT_CONTROLLER_NAME:
            raise ResourceNotFoundError("controller", name)
        return self._profile

    async def default_controller(self) -> str | None:
        """Return ``default``."""
        return DEFAULT_CONTROLLER_NAME
