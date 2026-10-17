"""Unit tests for Cloud Connector proxy tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.connector import (
    connector_network_delete,
    connector_network_get,
    connector_network_patch,
    connector_network_post,
    connector_network_put,
    connector_protect_delete,
    connector_protect_get,
    connector_protect_patch,
    connector_protect_post,
    connector_protect_put,
)
from src.utils.exceptions import ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.site_manager_enabled = True
    settings.request_timeout = 30
    settings.api_key = "test-key"
    settings.get_headers.return_value = {"X-API-KEY": "test-key"}
    return settings


@pytest.fixture
def mock_settings_disabled():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.site_manager_enabled = False
    return settings


def make_mock_client(response: dict | None = None):
    client = AsyncMock()
    client.get = AsyncMock(return_value=response or {"data": []})
    client.post = AsyncMock(return_value=response or {"data": {}})
    client.put = AsyncMock(return_value=response or {"data": {}})
    client.patch = AsyncMock(return_value=response or {"data": {}})
    client.delete = AsyncMock(return_value=response or {})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# =============================================================================
# connector_network_get
# =============================================================================


class TestConnectorNetworkGet:
    @pytest.mark.asyncio
    async def test_success_builds_correct_endpoint(self, mock_settings):
        """GET must proxy to connector/consoles/{console_id}/proxy/network/{path}."""
        response = {"data": [{"_id": "wlan1"}]}
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client(response)
            result = await connector_network_get(
                console_id="console-abc",
                path="api/s/default/rest/wlanconf",
                settings=mock_settings,
            )
        mock_cls.return_value.get.assert_called_once_with(
            "connector/consoles/console-abc/proxy/network/api/s/default/rest/wlanconf",
            params=None,
        )
        assert result == response

    @pytest.mark.asyncio
    async def test_strips_leading_slash_from_path(self, mock_settings):
        """Leading slash in path must be stripped before building endpoint."""
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client({})
            await connector_network_get(
                console_id="console-abc",
                path="/api/s/default/stat/device",
                settings=mock_settings,
            )
        mock_cls.return_value.get.assert_called_once_with(
            "connector/consoles/console-abc/proxy/network/api/s/default/stat/device",
            params=None,
        )

    @pytest.mark.asyncio
    async def test_passes_params(self, mock_settings):
        """Query params must be forwarded to the underlying GET call."""
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client({})
            await connector_network_get(
                console_id="c1",
                path="api/s/default/rest/wlanconf",
                settings=mock_settings,
                params={"_limit": "10"},
            )
        mock_cls.return_value.get.assert_called_once_with(
            "connector/consoles/c1/proxy/network/api/s/default/rest/wlanconf",
            params={"_limit": "10"},
        )

    @pytest.mark.asyncio
    async def test_empty_console_id_raises(self, mock_settings):
        with pytest.raises(ValidationError, match="console_id"):
            await connector_network_get(
                console_id="", path="api/s/default/stat/device", settings=mock_settings
            )

    @pytest.mark.asyncio
    async def test_empty_path_raises(self, mock_settings):
        with pytest.raises(ValidationError, match="path"):
            await connector_network_get(console_id="c1", path="", settings=mock_settings)

    @pytest.mark.asyncio
    async def test_site_manager_disabled_raises(self, mock_settings_disabled):
        with pytest.raises(ValueError, match="Site Manager"):
            await connector_network_get(
                console_id="c1",
                path="api/s/default/stat/device",
                settings=mock_settings_disabled,
            )


# =============================================================================
# connector_network_post / put / patch / delete (mutating — need confirm)
# =============================================================================


class TestConnectorNetworkPost:
    @pytest.mark.asyncio
    async def test_success(self, mock_settings):
        response = {"data": {"_id": "new-wlan"}}
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client(response)
            result = await connector_network_post(
                console_id="c1",
                path="api/s/default/rest/wlanconf",
                settings=mock_settings,
                body={"name": "Test", "security": "wpapsk"},
                confirm=True,
            )
        mock_cls.return_value.post.assert_called_once_with(
            "connector/consoles/c1/proxy/network/api/s/default/rest/wlanconf",
            json_data={"name": "Test", "security": "wpapsk"},
        )
        assert result == response

    @pytest.mark.asyncio
    async def test_requires_confirm(self, mock_settings):
        with pytest.raises(ValidationError):
            await connector_network_post(
                console_id="c1",
                path="api/s/default/rest/wlanconf",
                settings=mock_settings,
                body={},
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_dry_run_skips_api_call(self, mock_settings):
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client({})
            result = await connector_network_post(
                console_id="c1",
                path="api/s/default/rest/wlanconf",
                settings=mock_settings,
                body={"name": "Test"},
                confirm=True,
                dry_run=True,
            )
        mock_cls.return_value.post.assert_not_called()
        assert result["dry_run"] is True
        assert "connector/consoles/c1/proxy/network" in result["would_post_to"]


class TestConnectorNetworkPut:
    @pytest.mark.asyncio
    async def test_success(self, mock_settings):
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client({"data": {}})
            await connector_network_put(
                console_id="c1",
                path="api/s/default/rest/wlanconf/wlan-123",
                settings=mock_settings,
                body={"name": "Updated"},
                confirm=True,
            )
        mock_cls.return_value.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_requires_confirm(self, mock_settings):
        with pytest.raises(ValidationError):
            await connector_network_put(
                console_id="c1",
                path="api/s/default/rest/wlanconf/wlan-123",
                settings=mock_settings,
                body={},
                confirm=False,
            )


class TestConnectorNetworkPatch:
    @pytest.mark.asyncio
    async def test_success(self, mock_settings):
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client({"data": {}})
            await connector_network_patch(
                console_id="c1",
                path="api/s/default/rest/wlanconf/wlan-123",
                settings=mock_settings,
                body={"enabled": False},
                confirm=True,
            )
        mock_cls.return_value.patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_requires_confirm(self, mock_settings):
        with pytest.raises(ValidationError):
            await connector_network_patch(
                console_id="c1",
                path="api/s/default/rest/wlanconf/wlan-123",
                settings=mock_settings,
                body={},
                confirm=False,
            )


class TestConnectorNetworkDelete:
    @pytest.mark.asyncio
    async def test_success(self, mock_settings):
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client({})
            result = await connector_network_delete(
                console_id="c1",
                path="api/s/default/rest/wlanconf/wlan-123",
                settings=mock_settings,
                confirm=True,
            )
        mock_cls.return_value.delete.assert_called_once_with(
            "connector/consoles/c1/proxy/network/api/s/default/rest/wlanconf/wlan-123"
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_requires_confirm(self, mock_settings):
        with pytest.raises(ValidationError):
            await connector_network_delete(
                console_id="c1",
                path="api/s/default/rest/wlanconf/wlan-123",
                settings=mock_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_dry_run(self, mock_settings):
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client({})
            result = await connector_network_delete(
                console_id="c1",
                path="api/s/default/rest/wlanconf/wlan-123",
                settings=mock_settings,
                confirm=True,
                dry_run=True,
            )
        mock_cls.return_value.delete.assert_not_called()
        assert result["dry_run"] is True


# =============================================================================
# Protect proxy tools (same structure as network)
# =============================================================================


class TestConnectorProtectGet:
    @pytest.mark.asyncio
    async def test_success_builds_protect_endpoint(self, mock_settings):
        """GET must proxy to connector/consoles/{console_id}/proxy/protect/{path}."""
        response = {"data": [{"id": "cam-1"}]}
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client(response)
            result = await connector_protect_get(
                console_id="console-xyz",
                path="v1/cameras",
                settings=mock_settings,
            )
        mock_cls.return_value.get.assert_called_once_with(
            "connector/consoles/console-xyz/proxy/protect/v1/cameras",
            params=None,
        )
        assert result == response

    @pytest.mark.asyncio
    async def test_empty_console_id_raises(self, mock_settings):
        with pytest.raises(ValidationError, match="console_id"):
            await connector_protect_get(console_id="", path="v1/cameras", settings=mock_settings)

    @pytest.mark.asyncio
    async def test_site_manager_disabled_raises(self, mock_settings_disabled):
        with pytest.raises(ValueError, match="Site Manager"):
            await connector_protect_get(
                console_id="c1", path="v1/cameras", settings=mock_settings_disabled
            )


class TestConnectorProtectPost:
    @pytest.mark.asyncio
    async def test_success(self, mock_settings):
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client({"data": {}})
            await connector_protect_post(
                console_id="c1",
                path="v1/cameras/cam-1/snapshot",
                settings=mock_settings,
                body={},
                confirm=True,
            )
        mock_cls.return_value.post.assert_called_once_with(
            "connector/consoles/c1/proxy/protect/v1/cameras/cam-1/snapshot",
            json_data={},
        )

    @pytest.mark.asyncio
    async def test_requires_confirm(self, mock_settings):
        with pytest.raises(ValidationError):
            await connector_protect_post(
                console_id="c1",
                path="v1/cameras/cam-1/snapshot",
                settings=mock_settings,
                body={},
                confirm=False,
            )


class TestConnectorProtectPut:
    @pytest.mark.asyncio
    async def test_requires_confirm(self, mock_settings):
        with pytest.raises(ValidationError):
            await connector_protect_put(
                console_id="c1",
                path="v1/cameras/cam-1",
                settings=mock_settings,
                body={},
                confirm=False,
            )


class TestConnectorProtectPatch:
    @pytest.mark.asyncio
    async def test_requires_confirm(self, mock_settings):
        with pytest.raises(ValidationError):
            await connector_protect_patch(
                console_id="c1",
                path="v1/cameras/cam-1",
                settings=mock_settings,
                body={},
                confirm=False,
            )


class TestConnectorProtectDelete:
    @pytest.mark.asyncio
    async def test_success(self, mock_settings):
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client({})
            await connector_protect_delete(
                console_id="c1",
                path="v1/cameras/cam-1",
                settings=mock_settings,
                confirm=True,
            )
        mock_cls.return_value.delete.assert_called_once_with(
            "connector/consoles/c1/proxy/protect/v1/cameras/cam-1"
        )

    @pytest.mark.asyncio
    async def test_requires_confirm(self, mock_settings):
        with pytest.raises(ValidationError):
            await connector_protect_delete(
                console_id="c1",
                path="v1/cameras/cam-1",
                settings=mock_settings,
                confirm=False,
            )


# =============================================================================
# Write tools: shared behaviour across both applications
# =============================================================================

WRITE_TOOLS = [
    # (tool, app, client method, dry-run key, sends body)
    (connector_network_post, "network", "post", "would_post_to", True),
    (connector_network_put, "network", "put", "would_put_to", True),
    (connector_network_patch, "network", "patch", "would_patch_to", True),
    (connector_network_delete, "network", "delete", "would_delete", False),
    (connector_protect_post, "protect", "post", "would_post_to", True),
    (connector_protect_put, "protect", "put", "would_put_to", True),
    (connector_protect_patch, "protect", "patch", "would_patch_to", True),
    (connector_protect_delete, "protect", "delete", "would_delete", False),
]
WRITE_IDS = [t[0].__name__ for t in WRITE_TOOLS]


def _write_kwargs(sends_body: bool, **extra):
    kwargs = {"console_id": "c1", "path": "/v1/thing", **extra}
    if sends_body:
        kwargs["body"] = {"name": "x"}
    return kwargs


@pytest.mark.parametrize(
    ("tool", "app", "method", "dry_key", "sends_body"), WRITE_TOOLS, ids=WRITE_IDS
)
class TestConnectorWriteTools:
    @pytest.mark.asyncio
    async def test_site_manager_disabled_raises(
        self, mock_settings_disabled, tool, app, method, dry_key, sends_body
    ):
        with pytest.raises(ValueError, match="Site Manager API is not enabled"):
            await tool(settings=mock_settings_disabled, **_write_kwargs(sends_body, confirm=True))

    @pytest.mark.asyncio
    async def test_executes_against_app_proxy(
        self, mock_settings, tool, app, method, dry_key, sends_body
    ):
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client({"ok": True})
            result = await tool(settings=mock_settings, **_write_kwargs(sends_body, confirm=True))

        call = getattr(mock_cls.return_value, method)
        endpoint = f"connector/consoles/c1/proxy/{app}/v1/thing"
        if sends_body:
            call.assert_awaited_once_with(endpoint, json_data={"name": "x"})
        else:
            call.assert_awaited_once_with(endpoint)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_dry_run_previews_without_confirm(
        self, mock_settings, tool, app, method, dry_key, sends_body
    ):
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            result = await tool(settings=mock_settings, **_write_kwargs(sends_body, dry_run=True))

        mock_cls.assert_not_called()
        assert result["dry_run"] is True
        assert result[dry_key] == f"connector/consoles/c1/proxy/{app}/v1/thing"

    @pytest.mark.asyncio
    async def test_blank_path_rejected(self, mock_settings, tool, app, method, dry_key, sends_body):
        kwargs = _write_kwargs(sends_body, confirm=True)
        kwargs["path"] = "  "
        with pytest.raises(ValidationError, match="path must not be empty"):
            await tool(settings=mock_settings, **kwargs)


# =============================================================================
# Array replies through the MCP protocol (issue #222)
# =============================================================================


class TestArrayReplies:
    """A proxied endpoint answering with a JSON array must reach the caller.

    The tools used to be annotated ``-> dict[str, Any]``, so FastMCP built an
    object output schema and rejected ``[]`` with "structured_content must be
    a dict". Many ``proxy/network/v2/api/...`` endpoints answer with arrays.
    """

    @pytest.fixture
    def site_manager_settings(self, monkeypatch: pytest.MonkeyPatch):
        from src.config.config import Settings

        monkeypatch.setenv("UNIFI_API_KEY", "test-key")  # pragma: allowlist secret
        monkeypatch.setenv("UNIFI_SITE_MANAGER_ENABLED", "true")
        return Settings()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("reply", [[], [{"_id": "route1"}], {"data": []}])
    async def test_get_reply_shapes(self, site_manager_settings, reply):
        from fastmcp import Client, FastMCP

        import src.tools.connector as connector
        from src.tool_registry import register_module_tools

        mcp = FastMCP("test")
        register_module_tools(
            mcp, connector, site_manager_settings, include=["connector_network_get"]
        )
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client()
            mock_cls.return_value.get = AsyncMock(return_value=reply)
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "connector_network_get",
                    {"console_id": "c1", "path": "v2/api/site/default/trafficroutes"},
                )

        assert not result.is_error
        assert result.data == reply

    @pytest.mark.asyncio
    async def test_mutating_tools_accept_array_replies(self, mock_settings):
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client()
            mock_cls.return_value.post = AsyncMock(return_value=[{"_id": "r1"}])
            result = await connector_network_post(
                console_id="c1",
                path="v2/api/site/default/trafficroutes",
                settings=mock_settings,
                body={"enabled": True},
                confirm=True,
            )
        assert result == [{"_id": "r1"}]
