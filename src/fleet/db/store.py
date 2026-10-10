"""Reads and writes of the controller registry tables."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ...config import APIType, Settings
from ...utils.audit_encryption import AuditEncryptionError
from ...utils.exceptions import ResourceNotFoundError, ValidationError
from ...utils.logger import get_logger
from ..credentials import CredentialCipher
from ..registry import DEFAULT_CONTROLLER_NAME, ControllerProfile
from .models import CloudAccount, Controller, Credential

logger = get_logger(__name__)

#: Controller fields ``update_controller`` may change directly.
UPDATABLE_FIELDS = frozenset(
    {
        "local_host",
        "local_port",
        "local_verify_ssl",
        "cloud_api_url",
        "default_site",
        "labels",
        "enabled",
    }
)


class FleetStore:
    """The registry's tables, with API keys encrypted at rest."""

    def __init__(self, engine: AsyncEngine, cipher: CredentialCipher) -> None:
        """Create a store.

        Args:
            engine: Async engine for DATABASE_URL
            cipher: Encrypts API keys before they reach the database
        """
        self.engine = engine
        self._cipher = cipher
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    def _credential(self, api_key: str) -> Credential:
        return Credential(
            ciphertext=self._cipher.encrypt(api_key), key_fingerprint=self._cipher.fingerprint
        )

    async def load(self) -> tuple[list[ControllerProfile], str | None]:
        """Return every usable controller and the default controller's name.

        Disabled controllers, and controllers of disabled cloud accounts, are
        left out. A controller whose key cannot be decrypted is left out with
        a warning rather than failing the whole registry.
        """
        async with self._sessions() as session:
            rows = (
                (await session.execute(select(Controller).order_by(Controller.name)))
                .unique()
                .scalars()
                .all()
            )
        profiles: list[ControllerProfile] = []
        default: str | None = None
        for row in rows:
            account = row.cloud_account
            if not row.enabled or (account is not None and not account.enabled):
                continue
            credential = row.credential or (account.credential if account else None)
            if credential is None:  # pragma: no cover - prevented by a check constraint
                continue
            try:
                api_key = self._cipher.decrypt(credential.ciphertext)
            except AuditEncryptionError:
                logger.warning(
                    "Controller %s skipped: its API key cannot be decrypted with "
                    "UNIFI_FLEET_CREDENTIAL_KEY",
                    row.name,
                )
                continue
            profiles.append(
                ControllerProfile(
                    name=row.name,
                    api_type=APIType(row.api_type),
                    api_key=api_key,
                    cloud_api_url=row.cloud_api_url or (account.cloud_api_url if account else None),
                    local_host=row.local_host,
                    local_port=row.local_port,
                    local_verify_ssl=row.local_verify_ssl,
                    default_site=row.default_site,
                    labels=dict(row.labels),
                )
            )
            if row.is_default:
                default = row.name
        return profiles, default

    async def count_controllers(self) -> int:
        """Return how many controllers are registered, enabled or not."""
        async with self._sessions() as session:
            return int(await session.scalar(select(func.count()).select_from(Controller)) or 0)

    async def add_controller(
        self,
        *,
        name: str,
        api_type: APIType,
        api_key: str | None = None,
        cloud_account: str | None = None,
        make_default: bool = False,
        **fields: Any,
    ) -> None:
        """Register a controller.

        Exactly one of ``api_key`` (its own key) and ``cloud_account`` (use
        that account's key) must be given.

        Raises:
            ValidationError: For a duplicate name or an invalid combination
            ResourceNotFoundError: If ``cloud_account`` does not exist
        """
        if (api_key is None) == (cloud_account is None):
            raise ValidationError("Give exactly one of api_key and cloud_account")
        async with self._sessions.begin() as session:
            controller = Controller(name=name, api_type=api_type.value, **fields)
            if cloud_account is not None:
                controller.cloud_account_id = await self._cloud_account_id(session, cloud_account)
            else:
                assert api_key is not None  # noqa: S101 - checked above
                controller.credential = self._credential(api_key)
            if make_default:
                await session.execute(update(Controller).values(is_default=False))
                controller.is_default = True
            session.add(controller)
            await self._flush(session, f"controller '{name}' already exists")

    async def update_controller(
        self,
        name: str,
        *,
        changes: Mapping[str, Any],
        api_key: str | None = None,
        make_default: bool | None = None,
    ) -> None:
        """Change a controller.

        Args:
            name: The controller
            changes: Fields from :data:`UPDATABLE_FIELDS`
            api_key: Replace the controller's own API key
            make_default: True makes it the default; False clears its default flag

        Raises:
            ResourceNotFoundError: If no controller has that name
            ValidationError: For fields that cannot be changed
        """
        unknown = set(changes) - UPDATABLE_FIELDS
        if unknown:
            raise ValidationError(f"Cannot change: {', '.join(sorted(unknown))}")
        async with self._sessions.begin() as session:
            controller = await session.scalar(select(Controller).where(Controller.name == name))
            if controller is None:
                raise ResourceNotFoundError("controller", name)
            for field, value in changes.items():
                setattr(controller, field, value)
            if api_key is not None:
                controller.credential = self._credential(api_key)
                controller.cloud_account_id = None
            if make_default:
                await session.execute(
                    update(Controller)
                    .where(Controller.id != controller.id)
                    .values(is_default=False)
                )
                controller.is_default = True
            elif make_default is False:
                controller.is_default = False
            await self._flush(session, f"controller '{name}' could not be updated")

    async def add_cloud_account(
        self,
        *,
        name: str,
        api_type: APIType,
        api_key: str,
        cloud_api_url: str | None = None,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        """Register a cloud account whose key cloud controllers can share.

        Raises:
            ValidationError: For a duplicate name or a non-cloud API type
        """
        if api_type == APIType.LOCAL:
            raise ValidationError("A cloud account needs api_type cloud-v1 or cloud-ea")
        async with self._sessions.begin() as session:
            session.add(
                CloudAccount(
                    name=name,
                    api_type=api_type.value,
                    cloud_api_url=cloud_api_url,
                    labels=dict(labels or {}),
                    credential=self._credential(api_key),
                )
            )
            await self._flush(session, f"cloud account '{name}' already exists")

    async def rotate_credentials(self) -> int:
        """Re-encrypt every stored API key under the current key.

        Returns:
            How many credentials were re-encrypted
        """
        async with self._sessions.begin() as session:
            credentials = (await session.execute(select(Credential))).scalars().all()
            for credential in credentials:
                credential.ciphertext = self._cipher.rotate(credential.ciphertext)
                credential.key_fingerprint = self._cipher.fingerprint
                credential.rotated_at = func.now()
            return len(credentials)

    async def seed_from_settings(self, settings: Settings) -> bool:
        """Register the UNIFI_* controller as ``default`` if the registry is empty.

        Returns:
            True if this call seeded the registry; False if it already had
            controllers (including when another server seeded it concurrently)
        """
        if await self.count_controllers():
            return False
        try:
            await self.add_controller(
                name=DEFAULT_CONTROLLER_NAME,
                api_type=settings.api_type,
                api_key=settings.api_key,
                make_default=True,
                local_host=settings.local_host,
                local_port=settings.local_port,
                local_verify_ssl=settings.local_verify_ssl,
                cloud_api_url=settings.cloud_api_url,
                default_site=settings.default_site,
            )
        except ValidationError:
            return False  # another server seeded it first
        return True

    @staticmethod
    async def _cloud_account_id(session: AsyncSession, name: str) -> Any:
        account_id = await session.scalar(select(CloudAccount.id).where(CloudAccount.name == name))
        if account_id is None:
            raise ResourceNotFoundError("cloud account", name)
        return account_id

    @staticmethod
    async def _flush(session: AsyncSession, conflict_message: str) -> None:
        try:
            await session.flush()
        except IntegrityError as e:
            raise ValidationError(f"{conflict_message} ({_constraint(e)})") from e


def _constraint(error: IntegrityError) -> str:
    """Name the violated constraint without echoing row data (which may hold keys)."""
    name = getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)
    return f"constraint {name}" if name else "constraint violated"
