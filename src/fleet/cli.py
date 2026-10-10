"""Operator commands for the Postgres controller registry.

Usage::

    DATABASE_URL=postgresql://... python -m src.fleet.cli migrate
    DATABASE_URL=postgresql://... python -m src.fleet.cli status
    python -m src.fleet.cli import --name hq --make-default
    python -m src.fleet.cli tokens create --name ops-bot --role operator
    python -m src.fleet.cli tokens list
    python -m src.fleet.cli tokens revoke --name ops-bot

``migrate``, ``status`` and ``tokens`` need only DATABASE_URL; ``tokens create``
is how the first fleet-admin token is issued. ``migrate`` and ``status`` prefer
MIGRATION_DATABASE_URL when set, so the schema owner can differ from the
least-privilege role the server runs as (see SECURITY.md). ``import`` registers the
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


async def _tokens(url: str, args: argparse.Namespace) -> int:
    import json

    from .db.schema import ensure_current, make_engine
    from .tokens import TokenStore

    engine = make_engine(url)
    try:
        await ensure_current(engine)
        store = TokenStore(engine)
        if args.tokens_command == "create":
            labels = dict(item.split("=", 1) for item in args.label)
            token, info = await store.create(
                name=args.name,
                role=args.role,
                created_by="cli",
                expires_in_days=args.expires_in_days,
                allow_modules=args.allow_module or None,
                deny_modules=args.deny_module,
                controller_labels=labels,
            )
            print(token)
            print(
                f"Token '{info.name}' ({info.role}) created; store it now, it is not "
                "shown again.",
                file=sys.stderr,
            )
        elif args.tokens_command == "list":
            print(json.dumps([info.__dict__ for info in await store.list()], indent=2))
        else:
            info = await store.revoke(args.name)
            print(f"Token '{info.name}' revoked at {info.revoked_at}")
    finally:
        await engine.dispose()
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
        default=None,
        help=(
            "Postgres URL (default: DATABASE_URL; for migrate and status, "
            "MIGRATION_DATABASE_URL first)"
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("migrate", help="Upgrade the schema")
    migrate.add_argument("--revision", default="head", help="Target revision (default: head)")
    commands.add_parser("status", help="Show whether the schema is up to date")
    imp = commands.add_parser("import", help="Register the UNIFI_* controller")
    imp.add_argument("--name", default="default", help="Controller name (default: default)")
    imp.add_argument("--make-default", action="store_true", help="Make it the default controller")
    tokens = commands.add_parser("tokens", help="Issue, list and revoke API tokens")
    token_commands = tokens.add_subparsers(dest="tokens_command", required=True)
    create = token_commands.add_parser("create", help="Issue a token (printed once)")
    create.add_argument("--name", required=True)
    create.add_argument(
        "--role", required=True, choices=["viewer", "operator", "admin", "fleet-admin"]
    )
    create.add_argument("--expires-in-days", type=int, default=90, help="0 never expires")
    create.add_argument("--allow-module", action="append", default=[], metavar="PATTERN")
    create.add_argument("--deny-module", action="append", default=[], metavar="PATTERN")
    create.add_argument("--label", action="append", default=[], metavar="KEY=VALUE")
    token_commands.add_parser("list", help="List tokens (never their values)")
    revoke = token_commands.add_parser("revoke", help="Revoke a token")
    revoke.add_argument("--name", required=True)
    args = parser.parse_args(argv)

    if args.database_url is None:
        migration_url = os.environ.get("MIGRATION_DATABASE_URL")
        if args.command in ("migrate", "status") and migration_url:
            args.database_url = migration_url
        else:
            args.database_url = os.environ.get("DATABASE_URL")
    if not args.database_url:
        print("error: set DATABASE_URL or pass --database-url", file=sys.stderr)
        return 2
    try:
        if args.command == "migrate":
            return asyncio.run(_migrate(args.database_url, args.revision))
        if args.command == "status":
            return asyncio.run(_status(args.database_url))
        if args.command == "tokens":
            return asyncio.run(_tokens(args.database_url, args))
        return asyncio.run(_import(args.database_url, args.name, args.make_default))
    except UniFiMCPException as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
