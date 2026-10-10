"""Engine creation and schema migrations for the fleet registry."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from ...utils.exceptions import ConfigurationError
from .models import Base

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

#: Alembic's bookkeeping table, named so it cannot collide with another
#: application's migrations in a shared database.
VERSION_TABLE = "unifi_mcp_alembic_version"

MIGRATE_COMMAND = "python -m src.fleet.cli migrate"


class FleetSchemaError(ConfigurationError):
    """Raised when the database schema is not at the version this code needs."""


def async_url(url: str) -> str:
    """Return ``url`` with the asyncpg driver, accepting plain postgres URLs."""
    for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix) :]
    raise ConfigurationError("DATABASE_URL must be a postgresql:// URL")


def make_engine(url: str) -> AsyncEngine:
    """Create the registry's async engine (connections open lazily)."""
    return create_async_engine(async_url(url), pool_pre_ping=True)


def _config(connection: Connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["connection"] = connection
    config.attributes["target_metadata"] = Base.metadata
    return config


def head_revision() -> str:
    """Return the newest migration revision this code ships."""
    head = ScriptDirectory.from_config(_config(None)).get_current_head()  # type: ignore[arg-type]
    assert head is not None  # noqa: S101 - the migrations directory always has a head
    return head


async def current_revision(engine: AsyncEngine) -> str | None:
    """Return the database's migration revision, or None if never migrated."""

    def _read(connection: Connection) -> str | None:
        context = MigrationContext.configure(connection, opts={"version_table": VERSION_TABLE})
        return context.get_current_revision()

    async with engine.connect() as connection:
        return await connection.run_sync(_read)


async def upgrade(engine: AsyncEngine, revision: str = "head") -> None:
    """Apply migrations up to ``revision``."""
    async with engine.begin() as connection:
        await connection.run_sync(lambda c: command.upgrade(_config(c), revision))


async def downgrade(engine: AsyncEngine, revision: str) -> None:
    """Revert migrations down to ``revision`` (``base`` removes everything)."""
    async with engine.begin() as connection:
        await connection.run_sync(lambda c: command.downgrade(_config(c), revision))


async def ensure_current(engine: AsyncEngine) -> None:
    """Refuse to run against a schema that is not at this code's head revision.

    Raises:
        FleetSchemaError: Naming the current and required revisions and the
            command to run
    """
    current, head = await current_revision(engine), head_revision()
    if current != head:
        raise FleetSchemaError(
            f"The fleet registry schema is at {current or 'no version'} but this server "
            f"needs {head}: run `{MIGRATE_COMMAND}` against DATABASE_URL first"
        )
