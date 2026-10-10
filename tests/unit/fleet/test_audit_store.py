"""The Postgres audit store (plan §3.7, Phase 2b), on a real Postgres."""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")

from cryptography.fernet import Fernet  # noqa: E402
from fastmcp import Client, FastMCP  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

from src.config.config import Settings  # noqa: E402
from src.fleet.admin_tools import register_admin_tools  # noqa: E402
from src.fleet.db import audit_store  # noqa: E402
from src.fleet.db.audit_store import PostgresAuditSink  # noqa: E402
from src.fleet.db.schema import make_engine  # noqa: E402
from src.fleet.postgres_registry import PostgresRegistry  # noqa: E402
from src.fleet.router import FleetRouter  # noqa: E402
from src.tool_registry import _make_tool_wrapper  # noqa: E402
from src.utils.audit import AuditLogger, AuditUnavailableError, get_audit_logger  # noqa: E402
from src.utils.audit_verify import verify_records  # noqa: E402

CHAIN_KEY = "audit-chain-key"  # pragma: allowlist secret


@pytest.fixture
def settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, database_url: str, credential_key: str
) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "env-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UNIFI_AUDIT_CHAIN_KEY", CHAIN_KEY)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.delenv("UNIFI_AUDIT_LOG_KEY", raising=False)
    monkeypatch.setattr("src.utils.audit._audit_logger", None)
    return Settings()


@pytest.fixture
async def registry(settings: Settings, migrated_engine: Any) -> AsyncIterator[PostgresRegistry]:
    audit_store.install(settings, migrated_engine)
    registry = PostgresRegistry.from_settings(settings)
    await registry.start()
    yield registry
    await registry.stop()


async def _rows(engine: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT record FROM audit_log ORDER BY id"))
        return [json.loads(r.record) for r in result]


async def change_vlan(site_id: str, confirm: bool = False, settings: Any = None) -> str:
    """A write-tier tool."""
    return "changed"


async def show_vlans(site_id: str, settings: Any = None) -> str:
    """A read-tier tool."""
    return "vlans"


class TestAppendOnly:
    @pytest.mark.parametrize(
        "statement",
        [
            "UPDATE audit_log SET result = 'success'",
            "DELETE FROM audit_log",
            "TRUNCATE audit_log",
        ],
    )
    async def test_changes_are_refused_even_for_the_owner(self, migrated_engine, statement):
        await PostgresAuditSink(migrated_engine).append(
            {"event_id": "e1", "event_type": "system", "operation": "x", "result": "success"},
            key=None,
            strict=True,
        )

        with pytest.raises(DBAPIError, match="append-only"):
            async with migrated_engine.begin() as conn:
                await conn.execute(text(statement))
        assert len(await _rows(migrated_engine)) == 1

    async def test_least_privilege_runtime_role(self, migrated_engine, database_url):
        async with migrated_engine.begin() as conn:
            for sql in (
                "CREATE ROLE audit_runtime LOGIN PASSWORD 'rt'",
                "GRANT SELECT, INSERT ON audit_log TO audit_runtime",
                "GRANT SELECT, INSERT, UPDATE ON audit_chain_heads TO audit_runtime",
                "GRANT USAGE ON SEQUENCE audit_log_id_seq TO audit_runtime",
            ):
                await conn.execute(text(sql))
        runtime = make_engine(database_url.replace("postgres:@", "audit_runtime:rt@", 1))
        try:
            sink = PostgresAuditSink(runtime)
            for n in range(2):
                await sink.append(
                    {"event_id": f"e{n}", "event_type": "system", "operation": "x", "result": "ok"},
                    key=None,
                    strict=True,
                )
            with pytest.raises(DBAPIError, match="permission denied|append-only"):
                async with runtime.begin() as conn:
                    await conn.execute(text("DELETE FROM audit_log"))
        finally:
            await runtime.dispose()

        assert verify_records(
            [(str(i), json.dumps(r)) for i, r in enumerate(await _rows(migrated_engine))], None
        ).ok


class TestChaining:
    async def test_tampering_is_detected_even_with_triggers_disabled(self, migrated_engine):
        sink = PostgresAuditSink(migrated_engine)
        for n in range(3):
            await sink.append(
                {"event_id": f"e{n}", "event_type": "system", "operation": "x", "result": "ok"},
                key=CHAIN_KEY.encode(),
                strict=True,
            )
        assert (await audit_store.verify(migrated_engine, CHAIN_KEY.encode())).ok

        # A database superuser can bypass the trigger; the chain still catches it.
        async with migrated_engine.begin() as conn:
            await conn.execute(text("SET LOCAL session_replication_role = replica"))
            await conn.execute(
                text(
                    "UPDATE audit_log SET record = replace(record, '\"ok\"', '\"failed\"') "
                    "WHERE seq = 1"
                )
            )

        report = await audit_store.verify(migrated_engine, CHAIN_KEY.encode())
        assert any("hash does not match" in p for p in report.problems)

    async def test_two_servers_keep_separate_chains(self, migrated_engine):
        first = PostgresAuditSink(migrated_engine, chain_id="a" * 32)
        second = PostgresAuditSink(migrated_engine, chain_id="b" * 32)
        for n in range(3):
            for sink in (first, second):
                await sink.append(
                    {
                        "event_id": f"{sink.chain_id[0]}{n}",
                        "event_type": "system",
                        "operation": "x",
                        "result": "ok",
                    },
                    key=None,
                    strict=True,
                )

        report = await audit_store.verify(migrated_engine, None)
        heads = await audit_store.chain_heads(migrated_engine)

        assert report.ok and report.chains == 2
        assert [h["seq"] for h in heads] == [2, 2]

    async def test_failed_insert_does_not_advance_the_chain(self, migrated_engine):
        sink = PostgresAuditSink(migrated_engine)
        record = {"event_id": "dup", "event_type": "system", "operation": "x", "result": "ok"}
        await sink.append(dict(record), key=None, strict=True)

        with pytest.raises(AuditUnavailableError):
            await sink.append(dict(record), key=None, strict=True)  # duplicate event_id
        await sink.append({**record, "event_id": "next"}, key=None, strict=True)

        assert [r["seq"] for r in await _rows(migrated_engine)] == [0, 1]


class TestThroughTheWrapper:
    async def test_writes_go_to_postgres_only(self, settings, registry, migrated_engine):
        router = FleetRouter(settings, registry)

        await _make_tool_wrapper(change_vlan, settings, router)("default", confirm=True)
        await _make_tool_wrapper(show_vlans, settings, router)("default")

        rows = await _rows(migrated_engine)
        assert [(r["operation"], r["result"]) for r in rows] == [
            ("registry_seeded", "success"),
            ("change_vlan", "attempt"),
            ("change_vlan", "success"),
        ]
        assert not Path(settings.audit_log_file).exists()

    async def test_unreachable_store_refuses_writes_but_not_reads(self, settings, registry):
        router = FleetRouter(settings, registry)
        audit = get_audit_logger(settings.audit_log_file)
        audit.sink = PostgresAuditSink(make_engine("postgresql://nobody@127.0.0.1:1/none"))
        calls: list[str] = []

        async def guarded(site_id: str, confirm: bool = False, settings: Any = None) -> None:
            calls.append(site_id)

        with pytest.raises(AuditUnavailableError):
            await _make_tool_wrapper(guarded, settings, router)("default", confirm=True)
        assert calls == []
        assert await _make_tool_wrapper(show_vlans, settings, router)("default") == "vlans"

    async def test_payloads_are_encrypted_in_postgres(
        self, settings, registry, migrated_engine, monkeypatch
    ):
        monkeypatch.setenv("UNIFI_AUDIT_LOG_KEY", Fernet.generate_key().decode())
        audit = AuditLogger(log_file=settings.audit_log_file)
        audit.sink = PostgresAuditSink(migrated_engine, chain_id="c" * 32)
        monkeypatch.setattr("src.utils.audit._audit_logger", audit)

        await _make_tool_wrapper(change_vlan, settings, FleetRouter(settings, registry))(
            "secret-site", confirm=True
        )

        async with migrated_engine.connect() as conn:
            stored = (
                await conn.execute(text("SELECT string_agg(record, '') FROM audit_log"))
            ).scalar()
        outcome = (await _rows(migrated_engine))[-1]
        assert outcome["parameters_encrypted"] is True
        assert '"secret-site"' not in json.dumps(outcome["parameters"])
        assert stored is not None


class TestAuditTools:
    @pytest.fixture
    def server(self, settings: Settings, registry: PostgresRegistry) -> FastMCP:
        mcp = FastMCP("audit-tools")
        mcp.tool()(_make_tool_wrapper(change_vlan, settings, FleetRouter(settings, registry)))
        register_admin_tools(mcp, registry, settings)
        return mcp

    async def test_search_verify_and_export(self, server, migrated_engine):
        async with Client(server) as client:
            for _ in range(3):
                await client.call_tool("change_vlan", {"site_id": "default", "confirm": True})
            page = (
                await client.call_tool(
                    "search_audit_log",
                    {"operation": "change_vlan", "result": "success", "limit": 2},
                )
            ).data
            rest = (
                await client.call_tool(
                    "search_audit_log",
                    {
                        "operation": "change_vlan",
                        "result": "success",
                        "cursor": page["next_cursor"],
                    },
                )
            ).data
            verified = (await client.call_tool("verify_audit_chain", {})).data
            exported = (await client.call_tool("export_audit_log", {})).data

        assert len(page["records"]) == 2 and page["next_cursor"] is not None
        assert len(rest["records"]) == 1 and rest["next_cursor"] is None
        assert verified["ok"] is True and verified["chain_heads"]
        lines = exported["jsonl"].splitlines()
        assert exported["count"] == len(lines)
        assert verify_records(
            [(str(i), line) for i, line in enumerate(lines)], CHAIN_KEY.encode()
        ).ok

    async def test_queries_are_themselves_audited(self, server, migrated_engine):
        async with Client(server) as client:
            await client.call_tool("search_audit_log", {})

        rows = await _rows(migrated_engine)
        searches = [r for r in rows if r["operation"] == "search_audit_log"]
        assert [r["result"] for r in searches] == ["attempt", "success"]
        assert all(r["event_type"] == "admin" for r in searches)

    async def test_bad_timestamps_are_rejected(self, server):
        from fastmcp.exceptions import ToolError

        async with Client(server) as client:
            with pytest.raises(ToolError, match="ISO 8601"):
                await client.call_tool("search_audit_log", {"since": "yesterday"})


async def test_documented_least_privilege_grants_run_the_server(
    settings, migrated_engine, database_url, monkeypatch
):
    """The grants in SECURITY.md must be exactly enough for everything the server does."""
    import re

    from src.config.config import APIType
    from src.fleet.tokens import FleetTokenVerifier, TokenStore

    security = (Path(__file__).parents[3] / "SECURITY.md").read_text()
    block = re.search(r"Least-privilege database role.*?```sql\n(.*?)```", security, re.S).group(1)
    statements = [s.strip() for s in block.replace("'...'", "'rt'").split(";") if s.strip()]
    async with migrated_engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))

    runtime_url = database_url.replace("postgres:@", "unifi_mcp_runtime:rt@", 1)
    monkeypatch.setenv("DATABASE_URL", runtime_url)
    runtime_settings = Settings()
    registry = PostgresRegistry.from_settings(runtime_settings)
    audit_store.install(runtime_settings, registry.store.engine)
    try:
        await registry.start()  # schema check, seed, load
        await registry.store.add_controller(
            name="branch", api_type=APIType.LOCAL, api_key="k", local_host="10.0.1.1"
        )
        await registry.store.update_controller("branch", changes={"enabled": False})
        await registry.store.rotate_credentials()
        tokens = TokenStore(registry.store.engine)
        token, _ = await tokens.create(name="bot", role="viewer", created_by="test")
        assert await FleetTokenVerifier([], tokens).verify_token(token) is not None
        await tokens.revoke("bot")
        router = FleetRouter(runtime_settings, registry)
        await _make_tool_wrapper(change_vlan, runtime_settings, router)("default", confirm=True)
        report = await audit_store.verify(registry.store.engine, CHAIN_KEY.encode())
    finally:
        await registry.stop()

    assert report.ok and report.records >= 3
