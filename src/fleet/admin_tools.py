"""MCP tools that manage the Postgres controller registry (Phase 2a).

Registered only when DATABASE_URL is set, never in read-only mode. They are
``fleet-admin`` tier, need ``confirm=True``, honour ``dry_run``, and go through
the tool wrapper like every other tool, so each call is audited as an
``admin`` event (API keys redacted). After a change the registry snapshot is
reloaded so the change is routable immediately on this server.
"""

from typing import Any

from fastmcp import FastMCP
from pydantic import ValidationError as PydanticValidationError

from ..config import APIType, Settings
from ..tool_registry import TOOL_TIERS, _make_tool_wrapper
from ..utils.exceptions import ValidationError
from ..utils.validators import coerce_bool, validate_confirmation
from .postgres_registry import PostgresRegistry
from .registry import ControllerProfile


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
    for tool in build_admin_tools(registry):
        mcp.tool()(
            _make_tool_wrapper(tool, settings, routed=False, tier="fleet-admin", event_type="admin")
        )
        TOOL_TIERS[tool.__name__] = "fleet-admin"
        names.append(tool.__name__)
    return names
