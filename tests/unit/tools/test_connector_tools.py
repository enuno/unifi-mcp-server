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
        """GET must proxy to connector/{console_id}/proxy/network/{path}."""
        response = {"data": [{"_id": "wlan1"}]}
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client(response)
            result = await connector_network_get(
                console_id="console-abc",
                path="api/s/default/rest/wlanconf",
                settings=mock_settings,
            )
        mock_cls.return_value.get.assert_called_once_with(
            "connector/console-abc/proxy/network/api/s/default/rest/wlanconf",
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
            "connector/console-abc/proxy/network/api/s/default/stat/device",
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
            "connector/c1/proxy/network/api/s/default/rest/wlanconf",
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
            "connector/c1/proxy/network/api/s/default/rest/wlanconf",
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
        assert "connector/c1/proxy/network" in result["would_post_to"]


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
            "connector/c1/proxy/network/api/s/default/rest/wlanconf/wlan-123"
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
        """GET must proxy to connector/{console_id}/proxy/protect/{path}."""
        response = {"data": [{"id": "cam-1"}]}
        with patch("src.tools.connector.SiteManagerClient") as mock_cls:
            mock_cls.return_value = make_mock_client(response)
            result = await connector_protect_get(
                console_id="console-xyz",
                path="v1/cameras",
                settings=mock_settings,
            )
        mock_cls.return_value.get.assert_called_once_with(
            "connector/console-xyz/proxy/protect/v1/cameras",
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
            "connector/c1/proxy/protect/v1/cameras/cam-1/snapshot",
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
            "connector/c1/proxy/protect/v1/cameras/cam-1"
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
