"""Tests for the UniFi InnerSpace tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import innerspace

_CONSOLE = "11111111-2222-3333-4444-555555555555"
_PLAN = "plan-1"
_FILE = "floorplan.png"


@pytest.fixture
def settings() -> MagicMock:
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.site_manager_enabled = True
    return settings


def _make_client(response):
    """Build a mocked SiteManagerClient context manager; returns the client mock."""
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    client.put = AsyncMock(return_value=response)
    client.patch = AsyncMock(return_value=response)
    client.delete = AsyncMock(return_value=response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return client, cm


def _patch_client(cm):
    return patch("src.tools.innerspace.SiteManagerClient", return_value=cm)


def _endpoint(path: str) -> str:
    return f"connector/consoles/{_CONSOLE}/proxy/innerspace/integration/{path}"


# ── reads ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_innerspace_access_points(settings):
    response = {"data": [{"id": "ap-1", "name": "AP 1", "siteId": "site-1"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await innerspace.list_innerspace_access_points(_CONSOLE, settings)

    assert result["count"] == 1
    assert result["data"][0]["name"] == "AP 1"
    client.get.assert_called_once_with(_endpoint("v1/access_points"))


@pytest.mark.asyncio
async def test_list_innerspace_access_points_rejects_empty_console_id(settings):
    with pytest.raises(Exception, match="console_id"):
        await innerspace.list_innerspace_access_points("   ", settings)


@pytest.mark.asyncio
async def test_list_innerspace_access_points_requires_cloud(settings):
    settings.site_manager_enabled = False
    with pytest.raises(ValueError, match="UNIFI_SITE_MANAGER_ENABLED"):
        await innerspace.list_innerspace_access_points(_CONSOLE, settings)


@pytest.mark.asyncio
async def test_list_innerspace_floor_plans(settings):
    response = {"data": [{"id": "plan-1", "name": "Level 1"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await innerspace.list_innerspace_floor_plans(_CONSOLE, settings)

    assert result["count"] == 1
    assert result["data"][0]["name"] == "Level 1"
    client.get.assert_called_once_with(_endpoint("v1/floor_plans"))


@pytest.mark.asyncio
async def test_list_innerspace_floor_plans_rejects_empty_console_id(settings):
    with pytest.raises(Exception, match="console_id"):
        await innerspace.list_innerspace_floor_plans("", settings)


@pytest.mark.asyncio
async def test_list_innerspace_inventory(settings):
    response = {"data": [{"id": "inv-1", "name": "Unplaced AP"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await innerspace.list_innerspace_inventory(_CONSOLE, settings)

    assert result["count"] == 1
    assert result["data"][0]["name"] == "Unplaced AP"
    client.get.assert_called_once_with(_endpoint("v1/inventory"))


@pytest.mark.asyncio
async def test_get_innerspace_project(settings):
    client, cm = _make_client({"data": {"id": "proj-1", "name": "HQ Project"}})
    with _patch_client(cm):
        result = await innerspace.get_innerspace_project(_CONSOLE, settings)

    assert result["id"] == "proj-1"
    assert result["name"] == "HQ Project"
    client.get.assert_called_once_with(_endpoint("v1/project"))


@pytest.mark.asyncio
async def test_get_innerspace_project_rejects_empty_console_id(settings):
    with pytest.raises(Exception, match="console_id"):
        await innerspace.get_innerspace_project("  ", settings)


@pytest.mark.asyncio
async def test_list_innerspace_switches_no_site_id(settings):
    response = {"data": [{"id": "sw-1", "name": "Switch 1"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await innerspace.list_innerspace_switches(_CONSOLE, settings)

    assert result["count"] == 1
    assert result["site_id"] is None
    client.get.assert_called_once_with(_endpoint("v1/switches"), params=None)


@pytest.mark.asyncio
async def test_list_innerspace_switches_with_site_id(settings):
    response = {"data": [{"id": "sw-1", "name": "Switch 1", "siteId": "site-1"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await innerspace.list_innerspace_switches(_CONSOLE, settings, site_id="site-1")

    assert result["site_id"] == "site-1"
    client.get.assert_called_once_with(_endpoint("v1/switches"), params={"siteId": "site-1"})


@pytest.mark.asyncio
async def test_list_innerspace_switches_rejects_empty_console_id(settings):
    with pytest.raises(Exception, match="console_id"):
        await innerspace.list_innerspace_switches(" ", settings)


@pytest.mark.asyncio
async def test_download_innerspace_asset_dict_response(settings):
    client, cm = _make_client({"data": {"bytes": "..."}})
    with _patch_client(cm):
        result = await innerspace.download_innerspace_asset(_CONSOLE, _PLAN, _FILE, settings)

    assert result["plan_id"] == _PLAN
    assert result["filename"] == _FILE
    assert result["content"] == {"bytes": "..."}
    client.get.assert_called_once_with(_endpoint(f"v1/assets/{_PLAN}/{_FILE}"))


@pytest.mark.asyncio
async def test_download_innerspace_asset_raw_response(settings):
    client, cm = _make_client(b"\x89PNG\r\n\x1a\n")
    with _patch_client(cm):
        result = await innerspace.download_innerspace_asset(_CONSOLE, _PLAN, _FILE, settings)

    assert result["content"] == {"raw": b"\x89PNG\r\n\x1a\n"}
    client.get.assert_called_once_with(_endpoint(f"v1/assets/{_PLAN}/{_FILE}"))


@pytest.mark.asyncio
async def test_download_innerspace_asset_rejects_empty_plan_id(settings):
    with pytest.raises(Exception, match="plan_id"):
        await innerspace.download_innerspace_asset(_CONSOLE, "", _FILE, settings)


@pytest.mark.asyncio
async def test_download_innerspace_asset_rejects_empty_filename(settings):
    with pytest.raises(Exception, match="filename"):
        await innerspace.download_innerspace_asset(_CONSOLE, _PLAN, "  ", settings)


@pytest.mark.asyncio
async def test_download_innerspace_asset_rejects_empty_console_id(settings):
    with pytest.raises(Exception, match="console_id"):
        await innerspace.download_innerspace_asset(" ", _PLAN, _FILE, settings)
