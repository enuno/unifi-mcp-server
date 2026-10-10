"""MCP tools that manage the Postgres controller registry (Phase 2a).

Registered only when DATABASE_URL is set, never in read-only mode. They are
``fleet-admin`` tier, need ``confirm=True``, honour ``dry_run``, and go through
the tool wrapper like every other tool, so each call is audited as an
``admin`` event (API keys redacted). After a change the registry snapshot is
reloaded so the change is routable immediately on this server.
"""

import json
from datetime import datetime
from typing import Any

from fastmcp import FastMCP
from pydantic import ValidationError as PydanticValidationError

from ..access import current_principal
from ..config import APIType, Settings
from ..tool_registry import TOOL_TIERS, _make_tool_wrapper
from ..utils.audit import get_audit_logger
from ..utils.audit_verify import ChainKeyMissingError
from ..utils.exceptions import ValidationError
from ..utils.validators import coerce_bool, validate_confirmation
from .db import audit_store
from .postgres_registry import PostgresRegistry
from .registry import ControllerProfile
from .tokens import DEFAULT_EXPIRY_DAYS, TokenStore


def _api_type(value: str) -> APIType:
    try:
        return APIType(value)
    except ValueError:
        raise ValidationError("api_type must be one of: local, cloud-v1, cloud-ea") from None


def _validate_profile(**fields: Any) -> None:
    """Check fields with ControllerProfile's rules, reporting field names only."""
    try:
        ControllerProfile(**fields)
    except PydanticValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'controller'}: {err['msg']}"
            for err in e.errors(include_input=False)
        )
        raise ValidationError(f"Invalid controller: {problems}") from None


def _optional_bool(value: bool | str | None) -> bool | None:
    return None if value is None else coerce_bool(value)


def build_admin_tools(registry: PostgresRegistry) -> list[Any]:
    """Return the registry management tools bound to ``registry``."""

    async def register_controller(
        name: str,
        api_type: str,
        local_host: str | None = None,
        local_port: int | None = None,
        local_verify_ssl: bool | str | None = None,
        cloud_api_url: str | None = None,
        default_site: str | None = None,
        api_key: str | None = None,
        cloud_account: str | None = None,
        labels: dict[str, str] | None = None,
        make_default: bool | str = False,
        confirm: bool | str = False,
        dry_run: bool | str = False,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Register a UniFi controller in the fleet registry.

        Give the controller its own ``api_key``, or name a ``cloud_account``
        registered with register_cloud_account to share that account's key.

        Args:
            name: Routing name (lowercase letters, digits, '-' or '_')
            api_type: ``local``, ``cloud-ea`` or ``cloud-v1``
            local_host: Gateway host (required for ``local``)
            local_port: Gateway port (default 443)
            local_verify_ssl: Verify the gateway's TLS certificate
            cloud_api_url: Cloud API base URL override
            default_site: Site used when a tool call names none
            api_key: The controller's own API key (stored encrypted)
            cloud_account: Use this cloud account's key instead of api_key
            labels: Free-form labels, e.g. {"region": "west"}
            make_default: Make this the default controller
            confirm: Must be true to register
            dry_run: Validate and preview without registering
            settings: Injected by the server

        Returns:
            The registered controller, or the preview
        """
        kind = _api_type(api_type)
        verify = _optional_bool(local_verify_ssl)
        _validate_profile(
            name=name,
            api_type=kind,
            api_key=api_key or "placeholder",
            local_host=local_host,
            local_port=local_port,
            labels=labels or {},
        )
        if (api_key is None) == (cloud_account is None):
            raise ValidationError("Give exactly one of api_key and cloud_account")
        validate_confirmation(confirm, "register controller", dry_run)
        summary = {
            "name": name,
            "api_type": kind.value,
            "host": local_host if kind == APIType.LOCAL else cloud_api_url,
            "credential": f"cloud account {cloud_account}" if cloud_account else "own api_key",
            "default": coerce_bool(make_default),
        }
        if coerce_bool(dry_run):
            return {"dry_run": True, "would_register": summary}
        await registry.store.add_controller(
            name=name,
            api_type=kind,
            api_key=api_key,
            cloud_account=cloud_account,
            make_default=coerce_bool(make_default),
            local_host=local_host,
            local_port=local_port,
            local_verify_ssl=verify,
            cloud_api_url=cloud_api_url,
            default_site=default_site,
            labels=dict(labels or {}),
        )
        await registry.refresh()
        return {"registered": summary}

    async def update_controller(
        name: str,
        local_host: str | None = None,
        local_port: int | None = None,
        local_verify_ssl: bool | str | None = None,
        cloud_api_url: str | None = None,
        default_site: str | None = None,
        labels: dict[str, str] | None = None,
        enabled: bool | str | None = None,
        api_key: str | None = None,
        make_default: bool | str | None = None,
        confirm: bool | str = False,
        dry_run: bool | str = False,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Change a registered controller; only the fields you pass change.

        Set ``enabled=false`` to take a controller out of routing without
        deleting it.

        Args:
            name: The controller to change
            local_host: New gateway host
            local_port: New gateway port
            local_verify_ssl: Verify the gateway's TLS certificate
            cloud_api_url: New cloud API base URL
            default_site: New default site
            labels: Replacement labels
            enabled: Include in routing (true) or not (false)
            api_key: Replace its API key (stored encrypted)
            make_default: true makes it the default; false clears that
            confirm: Must be true to apply
            dry_run: Preview without applying
            settings: Injected by the server

        Returns:
            The applied changes (API key shown as changed, never its value)
        """
        changes = {
            key: value
            for key, value in {
                "local_host": local_host,
                "local_port": local_port,
                "local_verify_ssl": _optional_bool(local_verify_ssl),
                "cloud_api_url": cloud_api_url,
                "default_site": default_site,
                "labels": dict(labels) if labels is not None else None,
                "enabled": _optional_bool(enabled),
            }.items()
            if value is not None
        }
        default = _optional_bool(make_default)
        if not changes and api_key is None and default is None:
            raise ValidationError("Nothing to change")
        validate_confirmation(confirm, "update controller", dry_run)
        summary = {
            "name": name,
            "changes": changes,
            "api_key_replaced": api_key is not None,
            "default": default,
        }
        if coerce_bool(dry_run):
            return {"dry_run": True, "would_update": summary}
        await registry.store.update_controller(
            name, changes=changes, api_key=api_key, make_default=default
        )
        await registry.refresh()
        return {"updated": summary}

    async def register_cloud_account(
        name: str,
        api_key: str,
        api_type: str = "cloud-ea",
        cloud_api_url: str | None = None,
        labels: dict[str, str] | None = None,
        confirm: bool | str = False,
        dry_run: bool | str = False,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Register a UniFi cloud (Site Manager) API key that cloud controllers can share.

        Args:
            name: Account name (lowercase letters, digits, '-' or '_')
            api_key: The account's API key (stored encrypted)
            api_type: ``cloud-ea`` (default) or ``cloud-v1``
            cloud_api_url: Cloud API base URL override
            labels: Free-form labels
            confirm: Must be true to register
            dry_run: Validate and preview without registering
            settings: Injected by the server

        Returns:
            The registered account, or the preview
        """
        kind = _api_type(api_type)
        _validate_profile(name=name, api_type=kind, api_key=api_key, labels=labels or {})
        if kind == APIType.LOCAL:
            raise ValidationError("A cloud account needs api_type cloud-ea or cloud-v1")
        validate_confirmation(confirm, "register cloud account", dry_run)
        summary = {"name": name, "api_type": kind.value, "cloud_api_url": cloud_api_url}
        if coerce_bool(dry_run):
            return {"dry_run": True, "would_register": summary}
        await registry.store.add_cloud_account(
            name=name, api_type=kind, api_key=api_key, cloud_api_url=cloud_api_url, labels=labels
        )
        return {"registered": summary}

    async def rotate_fleet_credentials(
        confirm: bool | str = False,
        dry_run: bool | str = False,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Re-encrypt every stored API key under the newest UNIFI_FLEET_CREDENTIAL_KEY key.

        Put the new key first in UNIFI_FLEET_CREDENTIAL_KEY ("new,old"), run
        this, then drop the old key from the variable.

        Args:
            confirm: Must be true to rotate
            dry_run: Preview without rotating
            settings: Injected by the server

        Returns:
            How many credentials were re-encrypted
        """
        validate_confirmation(confirm, "rotate fleet credentials", dry_run)
        if coerce_bool(dry_run):
            return {"dry_run": True, "would_rotate": "every stored credential"}
        rotated = await registry.store.rotate_credentials()
        await registry.refresh()
        return {"rotated": rotated}

    return [
        register_controller,
        update_controller,
        register_cloud_account,
        rotate_fleet_credentials,
    ]


def build_token_tools(tokens: TokenStore) -> list[Any]:
    """Return the API token management tools bound to ``tokens``."""

    async def create_api_token(
        name: str,
        role: str,
        expires_in_days: int = DEFAULT_EXPIRY_DAYS,
        allow_modules: list[str] | None = None,
        deny_modules: list[str] | None = None,
        controller_labels: dict[str, str] | None = None,
        confirm: bool | str = False,
        dry_run: bool | str = False,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Issue a bearer token for a person or agent. The token is shown only in this result.

        Args:
            name: Token name (lowercase letters, digits, '-' or '_')
            role: ``viewer`` (reads), ``operator`` (+ writes), ``admin``
                (+ destructive tools) or ``fleet-admin`` (+ registry, token and
                audit tools)
            expires_in_days: Lifetime in days (default 90; 0 never expires)
            allow_modules: Only tool modules matching these patterns, e.g.
                ["devices", "protect_*"]
            deny_modules: Refuse tool modules matching these patterns
            controller_labels: Only controllers carrying all these labels
            confirm: Must be true to issue
            dry_run: Validate and preview without issuing
            settings: Injected by the server

        Returns:
            The token value (store it now: it cannot be shown again) and its metadata
        """
        _validate_profile(name=name, api_type=APIType.LOCAL, api_key="x", local_host="x")
        validate_confirmation(confirm, "create API token", dry_run)
        if coerce_bool(dry_run):
            return {"dry_run": True, "would_create": {"name": name, "role": role}}
        caller = current_principal.get()
        token, info = await tokens.create(
            name=name,
            role=role,
            created_by=caller.id if caller else "unknown",
            expires_in_days=expires_in_days,
            allow_modules=allow_modules,
            deny_modules=deny_modules or (),
            controller_labels=controller_labels,
        )
        return {
            "token": token,
            "warning": "Store this token now; it is not stored and cannot be shown again.",
            "metadata": info.__dict__,
        }

    async def list_api_tokens(settings: Settings | None = None) -> dict[str, Any]:
        """List issued API tokens: names, roles, filters and dates, never token values.

        Args:
            settings: Injected by the server

        Returns:
            Token metadata, newest first
        """
        return {"tokens": [info.__dict__ for info in await tokens.list()]}

    async def revoke_api_token(
        name: str,
        confirm: bool | str = False,
        dry_run: bool | str = False,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Revoke an API token; every server refuses it within 30 seconds.

        Args:
            name: The token to revoke
            confirm: Must be true to revoke
            dry_run: Preview without revoking
            settings: Injected by the server

        Returns:
            The revoked token's metadata
        """
        validate_confirmation(confirm, "revoke API token", dry_run)
        if coerce_bool(dry_run):
            return {"dry_run": True, "would_revoke": name}
        return {"revoked": (await tokens.revoke(name)).__dict__}

    async def update_api_token_role(
        name: str,
        role: str,
        confirm: bool | str = False,
        dry_run: bool | str = False,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Change an API token's role; takes effect on every server within 30 seconds.

        Args:
            name: The token to change
            role: viewer, operator, admin or fleet-admin
            confirm: Must be true to change
            dry_run: Preview without changing
            settings: Injected by the server

        Returns:
            The token's updated metadata
        """
        validate_confirmation(confirm, "update API token role", dry_run)
        if coerce_bool(dry_run):
            return {"dry_run": True, "would_update": {"name": name, "role": role}}
        return {"updated": (await tokens.set_role(name, role)).__dict__}

    return [create_api_token, list_api_tokens, revoke_api_token, update_api_token_role]


def _when(value: str | None, field: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{field} must be an ISO 8601 timestamp") from None


def build_audit_tools(registry: PostgresRegistry, config: Settings) -> list[Any]:
    """Return the audit store query tools."""
    engine = registry.store.engine

    async def search_audit_log(
        since: str | None = None,
        until: str | None = None,
        event_type: str | None = None,
        operation: str | None = None,
        principal: str | None = None,
        controller: str | None = None,
        result: str | None = None,
        limit: int = 100,
        cursor: int | None = None,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Search the audit trail, newest first. Each search is itself audited.

        Args:
            since: Only records at or after this ISO 8601 time
            until: Only records before this ISO 8601 time
            event_type: ``tool_call``, ``denied``, ``admin`` or ``system``
            operation: Tool or event name
            principal: Principal id, e.g. ``token:<id>``, ``env:<fingerprint>``, ``local``
            controller: Controller name
            result: e.g. ``attempt``, ``success``, ``error``, ``dry_run``, ``denied``
            limit: Most records to return (max 1000)
            cursor: ``next_cursor`` from the previous page
            settings: Injected by the server

        Returns:
            Matching records (payloads decrypted when the audit key is
            configured) and the cursor for the next page
        """
        rows, next_cursor = await audit_store.search(
            engine,
            limit=limit,
            before_id=cursor,
            since=_when(since, "since"),
            until=_when(until, "until"),
            event_type=event_type,
            operation=operation,
            principal_id=principal,
            controller=controller,
            result=result,
        )
        audit = get_audit_logger(config.audit_log_file)
        records = [audit._decrypt_entry(json.loads(text)) for _, text in rows]
        return {"records": records, "next_cursor": next_cursor}

    async def verify_audit_chain(settings: Settings | None = None) -> dict[str, Any]:
        """Check the audit trail's hash chains for edited, missing or reordered records.

        Args:
            settings: Injected by the server

        Returns:
            Whether every chain is intact, what was checked, the first problems
            found, and each chain's head (record these somewhere off the server)
        """
        try:
            report = await audit_store.verify(
                engine, get_audit_logger(config.audit_log_file).chain_key
            )
        except ChainKeyMissingError as e:
            raise ValidationError(str(e)) from None
        return {
            "ok": report.ok,
            "records": report.records,
            "chains": report.chains,
            "problems": report.problems[:50],
            "chain_heads": await audit_store.chain_heads(engine),
        }

    async def export_audit_log(
        since: str | None = None,
        until: str | None = None,
        limit: int = 1000,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """Export stored audit records as JSON lines, oldest first, for archiving.

        Records are exported as stored (payloads stay encrypted) so they can be
        verified with ``python -m src.utils.audit_verify``.

        Args:
            since: Only records at or after this ISO 8601 time
            until: Only records before this ISO 8601 time
            limit: Most records (max 1000); export in time windows for more
            settings: Injected by the server

        Returns:
            The records as JSON lines, how many, and the chain heads
        """
        rows, _ = await audit_store.search(
            engine, limit=limit, since=_when(since, "since"), until=_when(until, "until")
        )
        lines = [text for _, text in reversed(rows)]
        return {
            "jsonl": "\n".join(lines) + ("\n" if lines else ""),
            "count": len(lines),
            "chain_heads": await audit_store.chain_heads(engine),
        }

    return [search_audit_log, verify_audit_chain, export_audit_log]


def register_admin_tools(mcp: FastMCP, registry: PostgresRegistry, settings: Settings) -> list[str]:
    """Register the registry management tools, unless the server is read-only.

    Args:
        mcp: The FastMCP server instance
        registry: The Postgres registry the tools change
        settings: Process-wide settings

    Returns:
        The registered tool names
    """
    if settings.read_only:
        return []
    names = []
    tools = build_admin_tools(registry) + build_token_tools(TokenStore(registry.store.engine))
    audit_tools = build_audit_tools(registry, settings)
    for tool in tools + audit_tools:
        mcp.tool()(
            _make_tool_wrapper(
                tool,
                settings,
                routed=False,
                tier="fleet-admin",
                event_type="admin",
                always_audit=tool in audit_tools,
            )
        )
        TOOL_TIERS[tool.__name__] = "fleet-admin"
        names.append(tool.__name__)
    return names
