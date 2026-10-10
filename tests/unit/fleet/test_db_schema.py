"""Migrations and constraints of the registry schema, on a real Postgres."""

from typing import Any

import pytest

pytest.importorskip("sqlalchemy")

from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from sqlalchemy import inspect as sa_inspect  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from src.fleet.db.models import Base  # noqa: E402
from src.fleet.db.schema import (  # noqa: E402
    VERSION_TABLE,
    FleetSchemaError,
    current_revision,
    downgrade,
    ensure_current,
    head_revision,
    upgrade,
)

TABLES = {"credentials", "cloud_accounts", "controllers"}


async def _tables(engine: Any) -> set[str]:
    async with engine.connect() as conn:
        return set(await conn.run_sync(lambda c: sa_inspect(c).get_table_names()))


async def test_fresh_database_fails_the_startup_check(engine):
    with pytest.raises(FleetSchemaError, match="python -m src.fleet.cli migrate"):
        await ensure_current(engine)


async def test_upgrade_reaches_head(migrated_engine):
    assert await current_revision(migrated_engine) == head_revision()
    assert TABLES <= await _tables(migrated_engine)
    await ensure_current(migrated_engine)


async def test_downgrade_and_upgrade_again(migrated_engine):
    await downgrade(migrated_engine, "base")
    assert not (TABLES & await _tables(migrated_engine))
    assert await current_revision(migrated_engine) is None

    await upgrade(migrated_engine)
    assert await current_revision(migrated_engine) == head_revision()


async def test_models_and_migrations_agree(migrated_engine):
    def diff(connection: Any) -> list[Any]:
        context = MigrationContext.configure(connection, opts={"version_table": VERSION_TABLE})
        return compare_metadata(context, Base.metadata)

    async with migrated_engine.connect() as conn:
        differences = await conn.run_sync(diff)

    assert differences == []


class TestConstraints:
    async def _credential(self, conn: Any) -> Any:
        return await conn.scalar(
            text(
                "INSERT INTO credentials (id, ciphertext, key_fingerprint) "
                "VALUES (gen_random_uuid(), 'x', 'f') RETURNING id"
            )
        )

    async def _insert_controller(self, migrated_engine: Any, **values: Any) -> None:
        row = {
            "name": "hq",
            "api_type": "local",
            "local_host": "10.0.0.1",
            "is_default": False,
            **values,
        }
        async with migrated_engine.begin() as conn:
            row.setdefault("credential_id", await self._credential(conn))
            await conn.execute(
                text(
                    "INSERT INTO controllers (id, name, api_type, local_host, credential_id, "
                    "is_default) VALUES (gen_random_uuid(), :name, :api_type, :local_host, "
                    ":credential_id, :is_default)"
                ),
                row,
            )

    async def test_valid_row_is_accepted(self, migrated_engine):
        await self._insert_controller(migrated_engine)

    @pytest.mark.parametrize(
        "values",
        [
            {"name": "Bad Name"},
            {"api_type": "lan"},
            {"local_host": None},
            {"credential_id": None},
        ],
        ids=["name-format", "api-type", "local-needs-host", "needs-credential"],
    )
    async def test_invalid_rows_are_rejected(self, migrated_engine, values):
        with pytest.raises(IntegrityError):
            await self._insert_controller(migrated_engine, **values)

    async def test_only_one_default(self, migrated_engine):
        await self._insert_controller(migrated_engine, name="hq", is_default=True)

        with pytest.raises(IntegrityError):
            await self._insert_controller(migrated_engine, name="branch", is_default=True)

    async def test_duplicate_names_are_rejected(self, migrated_engine):
        await self._insert_controller(migrated_engine)

        with pytest.raises(IntegrityError):
            await self._insert_controller(migrated_engine)
