"""Registry management tools and the fleet CLI, end to end on a real Postgres."""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")

from fastmcp import Client, FastMCP  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402

from src.config.config import Settings  # noqa: E402
from src.fleet import cli  # noqa: E402
from src.fleet.admin_tools import register_admin_tools  # noqa: E402
from src.fleet.postgres_registry import PostgresRegistry  # noqa: E402
from src.fleet.router import FleetRouter  # noqa: E402
from src.fleet.tools import register_fleet_tools  # noqa: E402
from src.tool_registry import TOOL_TIERS, _make_tool_wrapper  # noqa: E402

NEW_KEY = "branch-key-0123456789abcdef"  # pragma: allowlist secret


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


async def where(site_id: str, confirm: bool = False, settings: Any = None) -> dict:
    """A mutating tool reporting which controller host it reached."""
    return {"host": settings.local_host}


@pytest.fixture
def server(settings: Settings, registry: PostgresRegistry) -> FastMCP:
    mcp = FastMCP("admin-test")
    router = FleetRouter(settings, registry)
    mcp.tool()(_make_tool_wrapper(where, settings, router))
    register_fleet_tools(mcp, router)
    register_admin_tools(mcp, registry, settings)
    return mcp


def _audit(settings: Settings) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(settings.audit_log_file).read_text().splitlines()]


async def _names(client: Client) -> list[str]:
    listed = (await client.call_tool("list_controllers", {})).data
    return [c["name"] for c in listed["controllers"]]


BRANCH = {
    "name": "branch",
    "api_type": "local",
    "local_host": "10.0.1.1",
    "api_key": NEW_KEY,
    "confirm": True,
}


class TestRegisterController:
    async def test_needs_confirm(self, server):
        async with Client(server) as client:
            with pytest.raises(ToolError, match="confirm"):
                await client.call_tool("register_controller", {**BRANCH, "confirm": False})

    async def test_dry_run_changes_nothing(self, server):
        async with Client(server) as client:
            preview = await client.call_tool("register_controller", {**BRANCH, "dry_run": True})
            names = await _names(client)

        assert preview.data["dry_run"] is True
        assert NEW_KEY not in json.dumps(preview.data)
        assert names == ["default"]

    async def test_registered_controller_is_routable_at_once(self, server):
        async with Client(server) as client:
            result = await client.call_tool("register_controller", BRANCH)
            names = await _names(client)
            reached = await client.call_tool(
                "where", {"site_id": "default", "confirm": True, "controller": "branch"}
            )

        assert NEW_KEY not in json.dumps(result.data)
        assert names == ["branch", "default"]
        assert reached.data["host"] == "10.0.1.1"

    async def test_cloud_controller_via_account(self, server):
        async with Client(server) as client:
            await client.call_tool(
                "register_cloud_account",
                {"name": "acct", "api_key": NEW_KEY, "confirm": True},
            )
            await client.call_tool(
                "register_controller",
                {
                    "name": "console",
                    "api_type": "cloud-ea",
                    "cloud_account": "acct",
                    "confirm": True,
                },
            )
            names = await _names(client)

        assert "console" in names

    @pytest.mark.parametrize(
        ("change", "message"),
        [
            ({"name": "Bad Name"}, "name"),
            ({"api_type": "lan"}, "api_type"),
            ({"local_host": None}, "local_host"),
            ({"cloud_account": "acct"}, "exactly one"),
        ],
    )
    async def test_invalid_input_never_echoes_the_key(self, server, change, message):
        async with Client(server) as client:
            with pytest.raises(ToolError, match=message) as err:
                await client.call_tool("register_controller", {**BRANCH, **change})

        assert NEW_KEY not in str(err.value)

    async def test_duplicate_name(self, server):
        async with Client(server) as client:
            await client.call_tool("register_controller", BRANCH)
            with pytest.raises(ToolError, match="already exists"):
                await client.call_tool("register_controller", BRANCH)


class TestUpdateAndRotate:
    async def test_disable_takes_a_controller_out_of_routing(self, server):
        async with Client(server) as client:
            await client.call_tool("register_controller", BRANCH)
            await client.call_tool(
                "update_controller", {"name": "branch", "enabled": False, "confirm": True}
            )
            names = await _names(client)
            with pytest.raises(ToolError, match="not found"):
                await client.call_tool(
                    "where", {"site_id": "default", "confirm": True, "controller": "branch"}
                )

        assert names == ["default"]

    async def test_make_default(self, server):
        async with Client(server) as client:
            await client.call_tool("register_controller", BRANCH)
            await client.call_tool(
                "update_controller", {"name": "branch", "make_default": True, "confirm": True}
            )
            active = (await client.call_tool("get_active_controller", {})).data

        assert active == {"name": "branch", "source": "default"}

    async def test_nothing_to_change(self, server):
        async with Client(server) as client:
            with pytest.raises(ToolError, match="Nothing to change"):
                await client.call_tool("update_controller", {"name": "default", "confirm": True})

    async def test_rotate(self, server):
        async with Client(server) as client:
            await client.call_tool("register_controller", BRANCH)
            rotated = (await client.call_tool("rotate_fleet_credentials", {"confirm": True})).data

        assert rotated == {"rotated": 2}


class TestAdminAuditAndRegistration:
    async def test_admin_calls_are_audited_with_keys_redacted(self, server, settings):
        async with Client(server) as client:
            await client.call_tool("register_controller", BRANCH)

        records = _audit(settings)
        admin = [r for r in records if r["operation"] == "register_controller"]
        assert [r["result"] for r in admin] == ["attempt", "success"]
        assert all(r["event_type"] == "admin" and r["tier"] == "fleet-admin" for r in admin)
        assert all("controller" not in r for r in admin)
        assert NEW_KEY not in Path(settings.audit_log_file).read_text()

    async def test_admin_tools_have_no_controller_argument(self, server):
        async with Client(server) as client:
            tools = {t.name: t for t in await client.list_tools()}

        for name in ("register_controller", "update_controller", "rotate_fleet_credentials"):
            assert "controller" not in tools[name].inputSchema["properties"]
            assert TOOL_TIERS[name] == "fleet-admin"

    async def test_read_only_server_has_no_admin_tools(self, registry, monkeypatch):
        monkeypatch.setenv("UNIFI_READ_ONLY", "true")
        mcp = FastMCP("read-only")

        assert register_admin_tools(mcp, registry, Settings()) == []


class TestCli:
    def test_migrate_status_and_import(self, database_url, settings, capsys):
        assert cli.main(["--database-url", database_url, "status"]) == 1
        assert cli.main(["--database-url", database_url, "migrate"]) == 0
        assert cli.main(["--database-url", database_url, "status"]) == 0
        assert cli.main(["--database-url", database_url, "import", "--name", "hq"]) == 0
        assert cli.main(["--database-url", database_url, "import", "--name", "hq"]) == 1

        out = capsys.readouterr()
        assert "up to date" in out.out
        assert "already exists" in out.err

    def test_import_needs_a_migrated_schema(self, database_url, settings, capsys):
        assert cli.main(["--database-url", database_url, "import"]) == 1
        assert "migrate" in capsys.readouterr().err

    def test_needs_a_database_url(self, monkeypatch, capsys):
        monkeypatch.delenv("DATABASE_URL", raising=False)

        assert cli.main(["status"]) == 2
