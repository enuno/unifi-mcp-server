"""Credential encryption, the registry store and PostgresRegistry, on a real Postgres."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")

from cryptography.fernet import Fernet  # noqa: E402
from sqlalchemy import text  # noqa: E402

from src.config.config import APIType, Settings  # noqa: E402
from src.fleet.credentials import CredentialCipher  # noqa: E402
from src.fleet.db.schema import FleetSchemaError  # noqa: E402
from src.fleet.db.store import FleetStore  # noqa: E402
from src.fleet.postgres_registry import PostgresRegistry  # noqa: E402
from src.fleet.router import FleetRouter  # noqa: E402
from src.utils.exceptions import (  # noqa: E402
    ConfigurationError,
    ResourceNotFoundError,
    ValidationError,
)

HQ_KEY = "hq-api-key-0123456789"  # pragma: allowlist secret
CLOUD_KEY = "cloud-api-key-9876543210"  # pragma: allowlist secret


@pytest.fixture
def cipher(credential_key: str) -> CredentialCipher:
    return CredentialCipher.from_env()


@pytest.fixture
def store(migrated_engine: Any, cipher: CredentialCipher) -> FleetStore:
    return FleetStore(migrated_engine, cipher)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, database_url: str) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "env-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr("src.utils.audit._audit_logger", None)
    return Settings()


async def _all_stored_text(engine: Any) -> str:
    async with engine.connect() as conn:
        rows = []
        for table in ("credentials", "cloud_accounts", "controllers"):
            rows += [
                json.dumps([str(v) for v in r])
                for r in await conn.execute(text(f"SELECT * FROM {table}"))  # noqa: S608
            ]
    return "\n".join(rows)


class TestCredentialCipher:
    def test_missing_key_is_a_configuration_error(self, monkeypatch):
        monkeypatch.delenv("UNIFI_FLEET_CREDENTIAL_KEY", raising=False)

        with pytest.raises(ConfigurationError, match="UNIFI_FLEET_CREDENTIAL_KEY"):
            CredentialCipher.from_env()

    def test_round_trip(self, cipher):
        token = cipher.encrypt(HQ_KEY)

        assert HQ_KEY not in token
        assert cipher.decrypt(token) == HQ_KEY

    def test_passphrase_keys_differ_from_audit_keys(self, monkeypatch):
        # One passphrase used for both purposes must not give the same key.
        from src.utils.audit_encryption import decrypt_field, resolve_audit_cipher

        monkeypatch.setenv("UNIFI_FLEET_CREDENTIAL_KEY", "shared passphrase")
        token = CredentialCipher.from_env().encrypt(HQ_KEY)

        audit_cipher = resolve_audit_cipher({"UNIFI_AUDIT_LOG_KEY": "shared passphrase"})
        with pytest.raises(Exception):  # noqa: B017 - any decryption failure
            decrypt_field(audit_cipher, token)

    def test_rotate_moves_to_the_newest_key(self, monkeypatch):
        old = Fernet.generate_key().decode()
        new = Fernet.generate_key().decode()
        monkeypatch.setenv("UNIFI_FLEET_CREDENTIAL_KEY", old)
        token = CredentialCipher.from_env().encrypt(HQ_KEY)

        monkeypatch.setenv("UNIFI_FLEET_CREDENTIAL_KEY", f"{new},{old}")
        rotated = CredentialCipher.from_env().rotate(token)

        monkeypatch.setenv("UNIFI_FLEET_CREDENTIAL_KEY", new)
        assert CredentialCipher.from_env().decrypt(rotated) == HQ_KEY


class TestStore:
    async def test_local_controller_round_trip(self, store):
        await store.add_controller(
            name="hq",
            api_type=APIType.LOCAL,
            api_key=HQ_KEY,
            local_host="10.0.0.1",
            labels={"site_group": "retail"},
            make_default=True,
        )

        (profile,), default = await store.load()

        assert profile.name == "hq"
        assert profile.api_key == HQ_KEY
        assert profile.local_host == "10.0.0.1"
        assert profile.labels == {"site_group": "retail"}
        assert default == "hq"

    async def test_api_keys_are_never_stored_in_plaintext(self, store, migrated_engine):
        await store.add_cloud_account(name="acct", api_type=APIType.CLOUD_EA, api_key=CLOUD_KEY)
        await store.add_controller(
            name="hq", api_type=APIType.LOCAL, api_key=HQ_KEY, local_host="10.0.0.1"
        )

        stored = await _all_stored_text(migrated_engine)

        assert HQ_KEY not in stored
        assert CLOUD_KEY not in stored

    async def test_cloud_controller_uses_its_accounts_key_and_url(self, store):
        await store.add_cloud_account(
            name="acct",
            api_type=APIType.CLOUD_EA,
            api_key=CLOUD_KEY,
            cloud_api_url="https://api.example",
        )
        await store.add_controller(
            name="console-1", api_type=APIType.CLOUD_EA, cloud_account="acct"
        )

        (profile,), _ = await store.load()

        assert profile.api_key == CLOUD_KEY
        assert profile.cloud_api_url == "https://api.example"

    async def test_needs_exactly_one_credential_source(self, store):
        with pytest.raises(ValidationError, match="exactly one"):
            await store.add_controller(name="x", api_type=APIType.CLOUD_EA)
        with pytest.raises(ValidationError, match="exactly one"):
            await store.add_controller(
                name="x", api_type=APIType.CLOUD_EA, api_key=HQ_KEY, cloud_account="acct"
            )

    async def test_unknown_cloud_account(self, store):
        with pytest.raises(ResourceNotFoundError, match="cloud account 'nope'"):
            await store.add_controller(name="x", api_type=APIType.CLOUD_EA, cloud_account="nope")

    async def test_duplicate_name_error_does_not_echo_the_key(self, store):
        await store.add_controller(
            name="hq", api_type=APIType.LOCAL, api_key=HQ_KEY, local_host="h"
        )

        with pytest.raises(ValidationError) as err:
            await store.add_controller(
                name="hq", api_type=APIType.LOCAL, api_key=HQ_KEY, local_host="h"
            )

        assert "already exists" in str(err.value)
        assert HQ_KEY not in str(err.value)

    async def test_make_default_moves_the_default(self, store):
        await store.add_controller(
            name="hq", api_type=APIType.LOCAL, api_key=HQ_KEY, local_host="h", make_default=True
        )
        await store.add_controller(
            name="branch", api_type=APIType.LOCAL, api_key=HQ_KEY, local_host="b", make_default=True
        )

        _, default = await store.load()
        assert default == "branch"

        await store.update_controller("hq", changes={}, make_default=True)
        _, default = await store.load()
        assert default == "hq"

    async def test_update_and_disable(self, store):
        await store.add_controller(
            name="hq", api_type=APIType.LOCAL, api_key=HQ_KEY, local_host="h"
        )

        await store.update_controller(
            "hq", changes={"local_port": 8443}, api_key="new-key"  # pragma: allowlist secret
        )
        (profile,), _ = await store.load()
        assert (profile.local_port, profile.api_key) == (8443, "new-key")

        await store.update_controller("hq", changes={"enabled": False})
        assert (await store.load())[0] == []

    async def test_update_rejects_unknown_fields_and_names(self, store):
        with pytest.raises(ValidationError, match="Cannot change: name"):
            await store.update_controller("hq", changes={"name": "x"})
        with pytest.raises(ResourceNotFoundError):
            await store.update_controller("nope", changes={})

    async def test_disabled_account_hides_its_controllers(self, store, migrated_engine):
        await store.add_cloud_account(name="acct", api_type=APIType.CLOUD_EA, api_key=CLOUD_KEY)
        await store.add_controller(name="c1", api_type=APIType.CLOUD_EA, cloud_account="acct")
        async with migrated_engine.begin() as conn:
            await conn.execute(text("UPDATE cloud_accounts SET enabled = false"))

        assert (await store.load())[0] == []

    async def test_undecryptable_controller_is_skipped(self, store, migrated_engine, monkeypatch):
        await store.add_controller(
            name="hq", api_type=APIType.LOCAL, api_key=HQ_KEY, local_host="h"
        )
        monkeypatch.setenv("UNIFI_FLEET_CREDENTIAL_KEY", Fernet.generate_key().decode())
        other = FleetStore(migrated_engine, CredentialCipher.from_env())

        assert (await other.load())[0] == []

    async def test_rotation_lets_the_old_key_be_retired(
        self, migrated_engine, monkeypatch, credential_key
    ):
        await FleetStore(migrated_engine, CredentialCipher.from_env()).add_controller(
            name="hq", api_type=APIType.LOCAL, api_key=HQ_KEY, local_host="h"
        )
        new = Fernet.generate_key().decode()
        monkeypatch.setenv("UNIFI_FLEET_CREDENTIAL_KEY", f"{new},{credential_key}")

        rotated = await FleetStore(
            migrated_engine, CredentialCipher.from_env()
        ).rotate_credentials()

        monkeypatch.setenv("UNIFI_FLEET_CREDENTIAL_KEY", new)
        (profile,), _ = await FleetStore(migrated_engine, CredentialCipher.from_env()).load()
        assert rotated == 1
        assert profile.api_key == HQ_KEY

    async def test_seed_only_when_empty(self, store, settings):
        assert await store.seed_from_settings(settings) is True
        assert await store.seed_from_settings(settings) is False

        (profile,), default = await store.load()
        assert (profile.name, default) == ("default", "default")
        assert profile.api_key == "env-key"  # pragma: allowlist secret

    async def test_concurrent_seeding_registers_one_controller(self, store, settings):
        results = await asyncio.gather(*(store.seed_from_settings(settings) for _ in range(5)))

        assert results.count(True) == 1
        assert await store.count_controllers() == 1


class TestPostgresRegistry:
    async def test_refuses_an_unmigrated_database(self, settings, credential_key):
        registry = PostgresRegistry.from_settings(settings)
        try:
            with pytest.raises(FleetSchemaError):
                await registry.start()
        finally:
            await registry.stop()

    async def test_needs_the_credential_key(self, settings, monkeypatch):
        monkeypatch.delenv("UNIFI_FLEET_CREDENTIAL_KEY", raising=False)

        with pytest.raises(ConfigurationError, match="UNIFI_FLEET_CREDENTIAL_KEY"):
            PostgresRegistry.from_settings(settings)

    async def test_first_start_seeds_and_audits(
        self, settings, migrated_engine, credential_key, tmp_path
    ):
        registry = PostgresRegistry.from_settings(settings)
        await registry.start()
        try:
            assert [c.name for c in await registry.list_controllers()] == ["default"]
            assert await registry.default_controller() == "default"
        finally:
            await registry.stop()

        records = [json.loads(line) for line in (tmp_path / "audit.log").read_text().splitlines()]
        assert [(r["event_type"], r["operation"]) for r in records] == [
            ("admin", "registry_seeded")
        ]

    async def test_seeded_default_routes_with_the_base_settings(
        self, settings, migrated_engine, credential_key
    ):
        registry = PostgresRegistry.from_settings(settings)
        await registry.start()
        try:
            resolution = await FleetRouter(settings, registry).resolve(None, mutating=True)
        finally:
            await registry.stop()

        assert resolution.name == "default"
        assert resolution.settings is settings

    async def test_outage_keeps_serving_the_last_snapshot(
        self, settings, migrated_engine, credential_key, monkeypatch
    ):
        registry = PostgresRegistry.from_settings(settings)
        await registry.start()
        try:

            async def down() -> Any:
                raise OSError("connection refused")

            monkeypatch.setattr(registry.store, "load", down)
            assert await registry.refresh() is False
            assert await registry.get_controller("default")
        finally:
            await registry.stop()

    async def test_unknown_and_unloaded(self, settings, credential_key):
        registry = PostgresRegistry.from_settings(settings)
        try:
            with pytest.raises(ConfigurationError, match="not been loaded"):
                await registry.list_controllers()
        finally:
            await registry.stop()
