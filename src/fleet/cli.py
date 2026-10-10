"""Operator commands for the Postgres controller registry.

Usage::

    DATABASE_URL=postgresql://... python -m src.fleet.cli migrate
    DATABASE_URL=postgresql://... python -m src.fleet.cli status
    python -m src.fleet.cli import --name hq --make-default

``migrate`` and ``status`` need only DATABASE_URL. ``import`` registers the
controller configured by the UNIFI_* variables and needs
UNIFI_FLEET_CREDENTIAL_KEY to encrypt its API key. The server refuses to start
until ``migrate`` has brought the schema to the version it needs.

Exit codes: 0 success, 1 failure (e.g. schema behind for ``status``), 2 usage.
"""

import argparse
import asyncio
import os
import sys

from ..utils.exceptions import UniFiMCPException


async def _migrate(url: str, revision: str) -> int:
    from .db.schema import current_revision, make_engine, upgrade

    engine = make_engine(url)
    try:
        await upgrade(engine, revision)
        print(f"Fleet registry schema is at {await current_revision(engine)}")
    finally:
        await engine.dispose()
    return 0


async def _status(url: str) -> int:
    from .db.schema import current_revision, head_revision, make_engine

    engine = make_engine(url)
    try:
        current, head = await current_revision(engine), head_revision()
    finally:
        await engine.dispose()
    if current == head:
        print(f"Fleet registry schema is up to date ({head})")
        return 0
    print(f"Fleet registry schema is at {current or 'no version'}; this server needs {head}")
    return 1


async def _import(url: str, name: str, make_default: bool) -> int:
    from ..config import Settings
    from .credentials import CredentialCipher
    from .db.schema import ensure_current, make_engine
    from .db.store import FleetStore

    settings = Settings()
    engine = make_engine(url)
    try:
        await ensure_current(engine)
        store = FleetStore(engine, CredentialCipher.from_env())
        await store.add_controller(
            name=name,
            api_type=settings.api_type,
            api_key=settings.api_key,
            make_default=make_default,
            local_host=settings.local_host,
            local_port=settings.local_port,
            local_verify_ssl=settings.local_verify_ssl,
            cloud_api_url=settings.cloud_api_url,
            default_site=settings.default_site,
        )
    finally:
        await engine.dispose()
    print(f"Registered the UNIFI_* controller as '{name}'")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the fleet registry CLI.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``)

    Returns:
        Process exit code
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.fleet.cli", description="Manage the fleet controller registry."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres URL (default: the DATABASE_URL environment variable)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("migrate", help="Upgrade the schema")
    migrate.add_argument("--revision", default="head", help="Target revision (default: head)")
    commands.add_parser("status", help="Show whether the schema is up to date")
    imp = commands.add_parser("import", help="Register the UNIFI_* controller")
    imp.add_argument("--name", default="default", help="Controller name (default: default)")
    imp.add_argument("--make-default", action="store_true", help="Make it the default controller")
    args = parser.parse_args(argv)

    if not args.database_url:
        print("error: set DATABASE_URL or pass --database-url", file=sys.stderr)
        return 2
    try:
        if args.command == "migrate":
            return asyncio.run(_migrate(args.database_url, args.revision))
        if args.command == "status":
            return asyncio.run(_status(args.database_url))
        return asyncio.run(_import(args.database_url, args.name, args.make_default))
    except UniFiMCPException as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
