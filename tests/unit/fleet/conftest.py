"""A real Postgres for the fleet registry tests, started with pgserver (no Docker).

One server per test session; every test that asks for ``database_url`` gets a
fresh, empty database on it.
"""

import itertools
import os
import tempfile
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

_counter = itertools.count()


@pytest.fixture(scope="session")
def postgres_server() -> Iterator[Any]:
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("asyncpg")
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tempfile.mkdtemp(prefix="unifi-mcp-pg-"), cleanup_mode="stop")
    yield server
    server.cleanup()


@pytest.fixture
def database_url(postgres_server: Any) -> str:
    name = f"fleet_test_{os.getpid()}_{next(_counter)}"
    postgres_server.psql(f"CREATE DATABASE {name};")
    return str(postgres_server.get_uri(database=name))


@pytest.fixture
def credential_key(monkeypatch: pytest.MonkeyPatch) -> str:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("UNIFI_FLEET_CREDENTIAL_KEY", key)
    return key


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[Any]:
    from src.fleet.db.schema import make_engine

    engine = make_engine(database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def migrated_engine(engine: Any) -> Any:
    from src.fleet.db.schema import upgrade

    await upgrade(engine)
    return engine
