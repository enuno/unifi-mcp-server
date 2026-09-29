"""Tests for the UniFi Mobility tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import mobility

_WORKSPACE = "11111111-2222-3333-4444-555555555555"
_DEVICE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


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
    return patch("src.tools.mobility.SiteManagerClient", return_value=cm)


# ── reads ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_mobility_workspaces(settings):
    response = {"data": [{"id": _WORKSPACE, "name": "HQ"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await mobility.list_mobility_workspaces(settings)

    assert result["count"] == 1
    assert result["data"][0]["name"] == "HQ"
    client.get.assert_called_once_with("mobility/workspaces")


@pytest.mark.asyncio
async def test_list_mobility_workspaces_requires_cloud(settings):
    settings.site_manager_enabled = False
    with pytest.raises(ValueError, match="UNIFI_SITE_MANAGER_ENABLED"):
        await mobility.list_mobility_workspaces(settings)


@pytest.mark.asyncio
async def test_list_mobility_workspace_admins(settings):
    response = {"data": [{"id": "admin-1", "email": "ops@example.com"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await mobility.list_mobility_workspace_admins(_WORKSPACE, settings)

    assert result["workspace_id"] == _WORKSPACE
    assert result["count"] == 1
    client.get.assert_called_once_with(f"mobility/workspaces/{_WORKSPACE}/admins")


@pytest.mark.asyncio
async def test_list_mobility_workspace_admins_rejects_empty_id(settings):
    with pytest.raises(Exception, match="workspace_id"):
        await mobility.list_mobility_workspace_admins("   ", settings)


@pytest.mark.asyncio
async def test_list_mobility_devices(settings):
    response = {"data": [{"id": _DEVICE, "name": "Gateway 1"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await mobility.list_mobility_devices(_WORKSPACE, settings, limit=50, offset=10)

    assert result["limit"] == 50
    assert result["offset"] == 10
    assert result["count"] == 1
    client.get.assert_called_once_with(
        f"mobility/workspaces/{_WORKSPACE}/devices",
        params={"limit": 50, "offset": 10},
    )


@pytest.mark.asyncio
async def test_list_mobility_devices_rejects_bad_limit(settings):
    with pytest.raises(Exception, match="limit"):
        await mobility.list_mobility_devices(_WORKSPACE, settings, limit=500)


@pytest.mark.asyncio
async def test_get_mobility_device(settings):
    client, cm = _make_client({"data": {"id": _DEVICE, "name": "Gateway 1"}})
    with _patch_client(cm):
        result = await mobility.get_mobility_device(_WORKSPACE, _DEVICE, settings)

    assert result["id"] == _DEVICE
    client.get.assert_called_once_with(f"mobility/workspaces/{_WORKSPACE}/devices/{_DEVICE}")


@pytest.mark.asyncio
async def test_list_mobility_device_clients(settings):
    response = {"data": [{"id": "client-1", "mac": "aa:bb:cc:dd:ee:ff"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await mobility.list_mobility_device_clients(_WORKSPACE, _DEVICE, settings)

    assert result["count"] == 1
    client.get.assert_called_once_with(
        f"mobility/workspaces/{_WORKSPACE}/devices/{_DEVICE}/clients",
        params={"limit": 100, "offset": 0},
    )


# ── writes ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_mobility_device_dry_run(settings):
    client, cm = _make_client({"data": {}})
    with _patch_client(cm):
        result = await mobility.update_mobility_device(
            _WORKSPACE, _DEVICE, settings, name="New Name", dry_run=True
        )

    assert result["dry_run"] is True
    assert result["payload"] == {"name": "New Name"}
    client.put.assert_not_called()


@pytest.mark.asyncio
async def test_update_mobility_device_requires_confirmation(settings):
    with pytest.raises(Exception, match="confirmation"):
        await mobility.update_mobility_device(_WORKSPACE, _DEVICE, settings, name="New Name")


@pytest.mark.asyncio
async def test_update_mobility_device_name_too_long(settings):
    with pytest.raises(Exception, match="32"):
        await mobility.update_mobility_device(
            _WORKSPACE, _DEVICE, settings, name="x" * 33, confirm=True
        )


@pytest.mark.asyncio
async def test_update_mobility_device_success(settings):
    client, cm = _make_client({"data": {"id": _DEVICE, "name": "New Name"}})
    with _patch_client(cm):
        result = await mobility.update_mobility_device(
            _WORKSPACE, _DEVICE, settings, name="New Name", confirm=True
        )

    assert result["name"] == "New Name"
    client.put.assert_called_once_with(
        f"mobility/workspaces/{_WORKSPACE}/devices/{_DEVICE}", json_data={"name": "New Name"}
    )


@pytest.mark.asyncio
async def test_update_mobility_device_network_success(settings):
    client, cm = _make_client({"data": {"dhcp_mode": "dhcp"}})
    with _patch_client(cm):
        result = await mobility.update_mobility_device_network(
            _WORKSPACE,
            _DEVICE,
            settings,
            dhcp_mode="dhcp",
            dhcp_range_start="192.168.1.100",
            dhcp_range_stop="192.168.1.200",
            dhcp_lease_time=3600,
            confirm=True,
        )

    assert result["dhcp_mode"] == "dhcp"
    call = client.put.call_args
    assert call.kwargs["json_data"] == {
        "dhcp_mode": "dhcp",
        "dhcp_range_start": "192.168.1.100",
        "dhcp_range_stop": "192.168.1.200",
        "dhcp_lease_time": 3600,
    }
    assert call.args[0].endswith("/network")


@pytest.mark.asyncio
async def test_update_mobility_device_network_rejects_bad_mode(settings):
    with pytest.raises(Exception, match="dhcp_mode"):
        await mobility.update_mobility_device_network(
            _WORKSPACE, _DEVICE, settings, dhcp_mode="relay", confirm=True
        )


@pytest.mark.asyncio
async def test_update_mobility_device_network_rejects_negative_lease(settings):
    with pytest.raises(Exception, match="lease"):
        await mobility.update_mobility_device_network(
            _WORKSPACE, _DEVICE, settings, dhcp_lease_time=-5, confirm=True
        )


@pytest.mark.asyncio
async def test_update_mobility_device_network_rejects_empty_update(settings):
    with pytest.raises(Exception, match="No updates"):
        await mobility.update_mobility_device_network(_WORKSPACE, _DEVICE, settings, confirm=True)


@pytest.mark.asyncio
async def test_update_mobility_device_network_dry_run(settings):
    client, cm = _make_client({"data": {}})
    with _patch_client(cm):
        result = await mobility.update_mobility_device_network(
            _WORKSPACE, _DEVICE, settings, host_address="192.168.1.1/24", dry_run=True
        )

    assert result["payload"] == {"host_address": "192.168.1.1/24"}
    client.put.assert_not_called()


@pytest.mark.asyncio
async def test_update_mobility_device_wireless_success(settings):
    client, cm = _make_client({"data": {"ssid": "HQ WiFi"}})
    with _patch_client(cm):
        result = await mobility.update_mobility_device_wireless(
            _WORKSPACE, _DEVICE, settings, ssid="HQ WiFi", password="s3cret", confirm=True
        )

    assert result["ssid"] == "HQ WiFi"
    client.put.assert_called_once_with(
        f"mobility/workspaces/{_WORKSPACE}/devices/{_DEVICE}/wireless",
        json_data={"ssid": "HQ WiFi", "password": "s3cret"},
    )


@pytest.mark.asyncio
async def test_update_mobility_device_wireless_requires_password(settings):
    with pytest.raises(Exception, match="password"):
        await mobility.update_mobility_device_wireless(
            _WORKSPACE, _DEVICE, settings, ssid="HQ WiFi", password="", confirm=True
        )


@pytest.mark.asyncio
async def test_update_mobility_device_wireless_dry_run(settings):
    client, cm = _make_client({"data": {}})
    with _patch_client(cm):
        result = await mobility.update_mobility_device_wireless(
            _WORKSPACE, _DEVICE, settings, ssid="HQ WiFi", password="s3cret", dry_run=True
        )

    assert result["payload"]["ssid"] == "HQ WiFi"
    client.put.assert_not_called()
