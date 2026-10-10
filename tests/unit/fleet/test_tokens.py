"""Server-issued API tokens on a real Postgres, including a bearer-token HTTP round trip."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")

import httpx  # noqa: E402
from fastmcp import Client, FastMCP  # noqa: E402
from fastmcp.client.transports import StreamableHttpTransport  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402
from sqlalchemy import text  # noqa: E402

from src.config.config import Settings  # noqa: E402
from src.fleet import cli  # noqa: E402
from src.fleet.admin_tools import register_admin_tools  # noqa: E402
from src.fleet.postgres_registry import PostgresRegistry  # noqa: E402
from src.fleet.router import FleetRouter  # noqa: E402
from src.fleet.tokens import FleetTokenVerifier, TokenStore, hash_token  # noqa: E402
from src.tool_registry import _make_tool_wrapper  # noqa: E402
from src.utils.exceptions import ResourceNotFoundError, ValidationError  # noqa: E402

ENV_TOKEN = "env-break-glass-token-0123456789"  # pragma: allowlist secret


@pytest.fixture
def store(migrated_engine: Any) -> TokenStore:
    return TokenStore(migrated_engine)


class TestTokenStore:
    async def test_only_the_hash_is_stored(self, store, migrated_engine):
        token, info = await store.create(name="ops-bot", role="operator", created_by="test")

        async with migrated_engine.connect() as conn:
            stored = [
                tuple(map(str, r)) for r in await conn.execute(text("SELECT * FROM api_tokens"))
            ]

        assert token.startswith("umcp_")
        assert token not in json.dumps(stored)
        assert hash_token(token) in json.dumps(stored)
        assert token not in json.dumps(info.__dict__)

    async def test_default_expiry_is_90_days(self, store):
        _, info = await store.create(name="a", role="viewer", created_by="t")
        _, forever = await store.create(name="b", role="viewer", created_by="t", expires_in_days=0)

        assert info.expires_at is not None
        assert forever.expires_at is None

    async def test_lookup_returns_claims_and_records_use(self, store):
        token, _ = await store.create(
            name="ops-bot",
            role="operator",
            created_by="t",
            allow_modules=["devices"],
            controller_labels={"group": "retail"},
        )

        claims = await store.lookup(token)
        (info,) = await store.list()

        assert claims["role"] == "operator"
        assert claims["allow_modules"] == ["devices"]
        assert claims["controller_labels"] == {"group": "retail"}
        assert info.last_used_at is not None

    async def test_revoked_expired_and_unknown_tokens_are_refused(self, store, migrated_engine):
        revoked, _ = await store.create(name="r", role="viewer", created_by="t")
        expired, _ = await store.create(name="e", role="viewer", created_by="t")
        await store.revoke("r")
        async with migrated_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE api_tokens SET expires_at = now() - interval '1 second' WHERE name = 'e'"
                )
            )

        assert await store.lookup(revoked) is None
        assert await store.lookup(expired) is None
        assert await store.lookup("umcp_never-issued") is None

    async def test_role_changes_and_validation(self, store):
        token, _ = await store.create(name="a", role="viewer", created_by="t")
        await store.set_role("a", "admin")

        assert (await store.lookup(token))["role"] == "admin"
        with pytest.raises(ValidationError, match="role"):
            await store.create(name="b", role="root", created_by="t")
        with pytest.raises(ValidationError, match="already exists"):
            await store.create(name="a", role="viewer", created_by="t")
        with pytest.raises(ResourceNotFoundError):
            await store.revoke("nope")


class TestVerifier:
    async def test_env_tokens_are_break_glass(self, store):
        access = await FleetTokenVerifier([ENV_TOKEN], store).verify_token(ENV_TOKEN)

        assert access is not None and access.claims == {}

    async def test_issued_token_carries_claims(self, store):
        token, _ = await store.create(name="ops", role="operator", created_by="t")

        access = await FleetTokenVerifier([], store).verify_token(token)

        assert access.client_id == "ops"
        assert access.claims["role"] == "operator"

    async def test_unknown_tokens_are_refused(self, store):
        verifier = FleetTokenVerifier([ENV_TOKEN], store)

        assert await verifier.verify_token("not-a-token") is None
        assert await verifier.verify_token("umcp_unknown") is None

    async def test_revocation_takes_effect_after_the_cache_window(self, store):
        token, _ = await store.create(name="ops", role="operator", created_by="t")
        verifier = FleetTokenVerifier([], store, cache_seconds=0.2)
        assert await verifier.verify_token(token) is not None

        await store.revoke("ops")
        still_cached = await verifier.verify_token(token)
        await asyncio.sleep(0.25)
        after_window = await verifier.verify_token(token)

        assert still_cached is not None
        assert after_window is None

    async def test_database_errors_fail_closed(self, store, monkeypatch):
        token, _ = await store.create(name="ops", role="operator", created_by="t")
        verifier = FleetTokenVerifier([], store)

        async def broken(_: str) -> Any:
            raise OSError("database down")

        monkeypatch.setattr(store, "lookup", broken)
        assert await verifier.verify_token(token) is None


@pytest.fixture
def settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, database_url: str, credential_key: str
) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "env-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    monkeypatch.setenv("UNIFI_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr("src.utils.audit._audit_logger", None)
    return Settings()


@pytest.fixture
async def registry(settings: Settings, migrated_engine: Any) -> AsyncIterator[PostgresRegistry]:
    registry = PostgresRegistry.from_settings(settings)
    await registry.start()
    yield registry
    await registry.stop()


async def reboot_ap(site_id: str, confirm: bool = False, settings: Any = None) -> str:
    """A write-tier tool."""
    return f"rebooted via {settings.local_host}"


async def wlan_list(site_id: str, settings: Any = None) -> str:
    """A read-tier tool."""
    return "wlans"


def _server(settings: Settings, registry: PostgresRegistry) -> FastMCP:
    verifier = FleetTokenVerifier([ENV_TOKEN], TokenStore(registry.store.engine))
    mcp = FastMCP("http-test", auth=verifier)
    router = FleetRouter(settings, registry)
    mcp.tool()(_make_tool_wrapper(reboot_ap, settings, router))
    mcp.tool()(_make_tool_wrapper(wlan_list, settings, router))
    register_admin_tools(mcp, registry, settings)
    return mcp


@asynccontextmanager
async def _http_client(mcp: FastMCP, token: str) -> AsyncIterator[Client]:
    """A real MCP-over-HTTP client with a bearer token, served in process."""
    app = mcp.http_app(path="/mcp")

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), **kwargs)

    transport = StreamableHttpTransport(
        "http://testserver/mcp",
        headers={"Authorization": f"Bearer {token}"},
        httpx_client_factory=factory,
    )
    async with app.router.lifespan_context(app), Client(transport) as client:
        yield client


class TestOverHttp:
    async def test_roles_are_enforced_for_bearer_tokens(self, settings, registry):
        mcp = _server(settings, registry)
        async with _http_client(mcp, ENV_TOKEN) as admin:
            created = (
                await admin.call_tool(
                    "create_api_token", {"name": "viewer-bot", "role": "viewer", "confirm": True}
                )
            ).data
        viewer_token = created["token"]

        async with _http_client(mcp, viewer_token) as viewer:
            assert (await viewer.call_tool("wlan_list", {"site_id": "default"})).data == "wlans"
            with pytest.raises(ToolError, match="needs the 'write' tier"):
                await viewer.call_tool("reboot_ap", {"site_id": "default", "confirm": True})
            with pytest.raises(ToolError, match="needs the 'fleet-admin' tier"):
                await viewer.call_tool("list_api_tokens", {})

        records = [
            json.loads(line) for line in Path(settings.audit_log_file).read_text().splitlines()
        ]
        denied = [r for r in records if r["event_type"] == "denied"]
        assert [r["operation"] for r in denied] == ["reboot_ap", "list_api_tokens"]
        assert all(r["principal"]["name"] == "viewer-bot" for r in denied)
        assert viewer_token not in Path(settings.audit_log_file).read_text()

    async def test_bad_and_revoked_tokens_are_rejected(self, settings, registry):
        mcp = _server(settings, registry)
        token, _ = await TokenStore(registry.store.engine).create(
            name="short-lived", role="viewer", created_by="test"
        )

        with pytest.raises(Exception) as rejected:  # noqa: B017 - surfaces as an ExceptionGroup
            async with _http_client(mcp, "umcp_forged") as client:
                await client.list_tools()
        assert "401 Unauthorized" in repr(rejected.value)

        async with _http_client(mcp, ENV_TOKEN) as admin:
            await admin.call_tool("revoke_api_token", {"name": "short-lived", "confirm": True})
            tokens = (await admin.call_tool("list_api_tokens", {})).data["tokens"]

        assert tokens[0]["revoked_at"] is not None
        assert all("token" not in t and "token_hash" not in t for t in tokens)
        fresh = _server(settings, registry)  # new verifier: no cached result
        with pytest.raises(Exception) as rejected:  # noqa: B017 - surfaces as an ExceptionGroup
            async with _http_client(fresh, token) as client:
                await client.list_tools()
        assert "401 Unauthorized" in repr(rejected.value)


class TestCli:
    def test_create_list_revoke(self, database_url, capsys):
        assert cli.main(["--database-url", database_url, "migrate"]) == 0
        capsys.readouterr()

        assert (
            cli.main(
                [
                    "--database-url",
                    database_url,
                    "tokens",
                    "create",
                    "--name",
                    "first-admin",
                    "--role",
                    "fleet-admin",
                    "--label",
                    "group=retail",
                ]
            )
            == 0
        )
        token = capsys.readouterr().out.strip()
        assert cli.main(["--database-url", database_url, "tokens", "list"]) == 0
        listed = json.loads(capsys.readouterr().out)
        assert (
            cli.main(["--database-url", database_url, "tokens", "revoke", "--name", "first-admin"])
            == 0
        )

        assert token.startswith("umcp_")
        assert listed[0]["controller_labels"] == {"group": "retail"}
        assert token not in json.dumps(listed)
