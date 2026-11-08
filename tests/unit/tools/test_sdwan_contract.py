"""Regression witnesses from Site Manager v1.0.0 OpenAPI, retrieved 2026-11-08."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.api.site_manager_client import SiteManagerClient
from src.config import Settings
from src.tools.site_manager import get_sdwan_config, get_sdwan_config_status, list_sdwan_configs
from src.utils.exceptions import (
    APIError,
    AuthenticationError,
    ResourceNotFoundError,
    ValidationError,
)


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud-v1")
    monkeypatch.setenv("UNIFI_SITE_MANAGER_ENABLED", "true")
    return Settings()


@pytest.mark.asyncio
async def test_sdwan_reads_use_official_complete_urls(settings):
    seen = []

    def handler(request, **_kwargs):
        seen.append(request)
        return httpx.Response(200, request=request, json={"data": []})

    client = SiteManagerClient(settings)
    client._authenticated = True
    with patch.object(client.client, "send", side_effect=handler):
        async with client:
            await client.list_sdwan_configs()
            await client.get_sdwan_config("config-1")
            await client.get_sdwan_config_status("config-1")
    assert [(r.method, str(r.url)) for r in seen] == [
        ("GET", "https://api.ui.com/v1/sd-wan-configs"),
        ("GET", "https://api.ui.com/v1/sd-wan-configs/config-1"),
        ("GET", "https://api.ui.com/v1/sd-wan-configs/config-1/status"),
    ]
    assert all(r.headers["X-API-KEY"] == "test-key" for r in seen)


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", ["../hosts", "a/b", "..", "", "x?token=1"])
async def test_sdwan_invalid_identifier_never_reaches_network(settings, identifier):
    with patch("src.tools.site_manager.SiteManagerClient") as factory:
        with pytest.raises(ValidationError):
            await get_sdwan_config(settings, identifier)
        with pytest.raises(ValidationError):
            await get_sdwan_config_status(settings, identifier)
        factory.assert_not_called()


@pytest.mark.asyncio
async def test_sdwan_list_preserves_official_summary(settings):
    response = {"data": [{"id": "config-1", "name": "Test", "type": "sdwan-hbsp"}]}
    with patch("src.tools.site_manager.SiteManagerClient") as factory:
        client = factory.return_value.__aenter__.return_value
        client.list_sdwan_configs = AsyncMock(return_value=response)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        assert await list_sdwan_configs(settings) == response["data"]


@pytest.mark.asyncio
async def test_sdwan_detail_and_status_preserve_spec_fields(settings):
    detail = {
        "id": "config-1",
        "name": "Test",
        "type": "sdwan-hbsp",
        "variant": "single",
        "settings": {"spokeToHubRouting": "geo"},
        "hubs": [{"siteId": "hub", "routes": []}],
        "spokes": [
            {
                "siteId": "spoke",
                "routes": ["172.16.1.0/24"],
                "primaryWan": "WAN",
                "hubsPriority": None,
            }
        ],
    }
    status = {
        "id": "config-1",
        "fingerprint": "abc",
        "generateStatus": "OK",
        "errors": [],
        "warnings": [],
        "hubs": [{"siteId": "hub", "applyStatus": "ok"}],
        "spokes": [{"siteId": "spoke", "connections": [{"tunnels": [{"status": "connected"}]}]}],
    }
    with patch("src.tools.site_manager.SiteManagerClient") as factory:
        client = factory.return_value.__aenter__.return_value
        client.get_sdwan_config = AsyncMock(return_value={"data": detail})
        client.get_sdwan_config_status = AsyncMock(return_value={"data": status})
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        assert await get_sdwan_config(settings, "config-1") == detail
        assert await get_sdwan_config_status(settings, "config-1") == status


@pytest.mark.asyncio
async def test_sdwan_unsupported_list_is_not_empty_success(settings):
    with patch("src.tools.site_manager.SiteManagerClient") as factory:
        client = factory.return_value.__aenter__.return_value
        client.list_sdwan_configs = AsyncMock(
            side_effect=ResourceNotFoundError("resource", "sd-wan-configs")
        )
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(ResourceNotFoundError):
            await list_sdwan_configs(settings)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_data", [None, {}, "not-a-list", [None], [{}], [{"id": "x"}], [{"foo": "bar"}]]
)
async def test_sdwan_invalid_list_envelope_is_not_empty_success(settings, bad_data):
    with patch("src.tools.site_manager.SiteManagerClient") as factory:
        client = factory.return_value.__aenter__.return_value
        client.list_sdwan_configs = AsyncMock(return_value={"data": bad_data})
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises((APIError, ValueError)):
            await list_sdwan_configs(settings)


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", [get_sdwan_config, get_sdwan_config_status])
async def test_sdwan_empty_detail_or_status_is_not_success(settings, tool):
    with patch("src.tools.site_manager.SiteManagerClient") as factory:
        client = factory.return_value.__aenter__.return_value
        client.get_sdwan_config = AsyncMock(return_value={"data": {}})
        client.get_sdwan_config_status = AsyncMock(return_value={"data": {}})
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(APIError):
            await tool(settings, "config-1")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool,payload",
    [
        (get_sdwan_config, {"id": "x", "name": "Test", "type": "sdwan-hbsp", "hubs": "not a list"}),
        (get_sdwan_config, {"id": "x", "name": "Test", "type": "sdwan-hbsp", "spokes": [None]}),
        (get_sdwan_config_status, {"id": "", "generateStatus": "invalid"}),
        (get_sdwan_config_status, {"id": "", "hubs": [{"applyStatus": "OK"}]}),
        (get_sdwan_config_status, {"id": "", "spokes": [None]}),
        (get_sdwan_config_status, {"id": "", "generateStatus": None}),
        (get_sdwan_config_status, {"id": "", "hubs": "not a list"}),
    ],
)
async def test_sdwan_invalid_nested_or_state_is_not_success(settings, tool, payload):
    with patch("src.tools.site_manager.SiteManagerClient") as factory:
        client = factory.return_value.__aenter__.return_value
        client.get_sdwan_config = AsyncMock(return_value={"data": payload})
        client.get_sdwan_config_status = AsyncMock(return_value={"data": payload})
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises((APIError, ValueError)):
            await tool(settings, "config-1")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 404, 429])
async def test_sdwan_http_failures_are_not_empty_success(settings, status):
    client = SiteManagerClient(settings)
    client._authenticated = True

    def handler(request, **_kwargs):
        return httpx.Response(status, request=request, json={"message": "unavailable"})

    with patch.object(client.client, "send", side_effect=handler):
        async with client:
            with pytest.raises((APIError, AuthenticationError, ResourceNotFoundError)):
                await client.list_sdwan_configs()
