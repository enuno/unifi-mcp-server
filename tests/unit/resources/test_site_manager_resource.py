"""Unit tests for src/resources/site_manager.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.resources.site_manager import SiteManagerResource

DISABLED = "Site Manager API is not enabled. Set UNIFI_SITE_MANAGER_ENABLED=true"


@pytest.fixture
def enabled_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.site_manager_enabled = True
    return settings


@pytest.fixture
def disabled_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.site_manager_enabled = False
    return settings


def _client(**methods):
    client = AsyncMock()
    for name, value in methods.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _patch(client):
    return patch("src.resources.site_manager.SiteManagerClient", return_value=client)


class TestDisabled:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method", ["get_all_sites", "get_health_metrics", "get_internet_health_status"]
    )
    async def test_returns_hint_without_calling_api(self, disabled_settings, method):
        with patch("src.resources.site_manager.SiteManagerClient") as client_class:
            result = await getattr(SiteManagerResource(disabled_settings), method)()

        assert result == DISABLED
        client_class.assert_not_called()


class TestEnabled:
    @pytest.mark.asyncio
    async def test_get_all_sites_from_data(self, enabled_settings):
        client = _client(list_sites={"data": [{"name": "HQ", "id": "s1"}, {}]})
        with _patch(client):
            result = await SiteManagerResource(enabled_settings).get_all_sites()

        assert result == "Site: HQ (s1)\nSite: Unknown (unknown)"

    @pytest.mark.asyncio
    async def test_get_all_sites_from_sites_key(self, enabled_settings):
        client = _client(list_sites={"sites": [{"name": "Branch", "id": "s2"}]})
        with _patch(client):
            result = await SiteManagerResource(enabled_settings).get_all_sites()

        assert result == "Site: Branch (s2)"

    @pytest.mark.asyncio
    async def test_get_health_metrics(self, enabled_settings):
        client = _client(get_site_health={"data": {"healthy": 3}})
        with _patch(client):
            result = await SiteManagerResource(enabled_settings).get_health_metrics()

        assert result == "Health Status: {'healthy': 3}"

    @pytest.mark.asyncio
    async def test_get_internet_health_without_envelope(self, enabled_settings):
        client = _client(get_internet_health={"status": "ok"})
        with _patch(client):
            result = await SiteManagerResource(enabled_settings).get_internet_health_status()

        assert result == "Internet Health: {'status': 'ok'}"
