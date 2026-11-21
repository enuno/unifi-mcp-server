"""Tests for NetFlow export configuration tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import APIType
from src.tools.netflow import get_netflow_export_config, update_netflow_export_config
from src.utils.exceptions import ResourceNotFoundError, ValidationError


@pytest.fixture
def settings():
    value = MagicMock()
    value.api_type = APIType.LOCAL
    value.log_level = "INFO"
    value.get_site_api_path.side_effect = (
        lambda site, endpoint: f"/proxy/network/api/s/{site}/{endpoint}"
    )
    return value


def _client(client_class, *, get_responses=None, post_response=None):
    client = AsyncMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock(side_effect=get_responses or [])
    client.post = AsyncMock(return_value=post_response or {})
    client.put = AsyncMock(return_value={})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client_class.return_value = client
    return client


async def test_get_netflow_export_config_reads_observed_legacy_path(settings):
    record = {"_id": "setting-1", "key": "netflow", "enabled": False, "version": 10}
    with patch("src.tools.netflow.UniFiClient") as client_class:
        client = _client(client_class, get_responses=[{"data": [record]}])
        result = await get_netflow_export_config("default", settings)

    client.get.assert_awaited_once_with("/proxy/network/api/s/default/get/setting/netflow")
    assert result == record


async def test_get_netflow_export_config_requires_one_record(settings):
    with patch("src.tools.netflow.UniFiClient") as client_class:
        _client(client_class, get_responses=[{"data": []}])
        with pytest.raises(ResourceNotFoundError, match="netflow"):
            await get_netflow_export_config("default", settings)


async def test_update_netflow_export_config_requires_confirmation(settings):
    with patch("src.tools.netflow.UniFiClient") as client_class:
        with pytest.raises(ValidationError, match="requires confirmation"):
            await update_netflow_export_config("default", settings, enabled=True)
    client_class.assert_not_called()


async def test_update_netflow_export_config_dry_run_makes_no_request(settings):
    with patch("src.tools.netflow.UniFiClient") as client_class:
        result = await update_netflow_export_config(
            "default", settings, enabled=True, server="collector.example", dry_run=True
        )

    client_class.assert_not_called()
    assert result == {
        "dry_run": True,
        "operation": "update_netflow_export_config",
        "site_id": "default",
        "changes": {"enabled": True, "server": "collector.example"},
    }


async def test_update_netflow_export_config_preserves_record_and_reads_back(settings):
    before = {
        "_id": "setting-1",
        "site_id": "site-1",
        "key": "netflow",
        "enabled": False,
        "network_ids": ["network-1"],
        "server": "old.example",
        "port": 2055,
        "version": 10,
        "auto_engine_id_enabled": True,
        "export_frequency": 5,
        "refresh_rate": 20,
        "sampling_mode": "hash",
        "sampling_rate": 512,
    }
    after = {**before, "enabled": True, "server": "collector.example"}
    with patch("src.tools.netflow.UniFiClient") as client_class:
        client = _client(
            client_class,
            get_responses=[{"data": [before]}, {"data": [after]}],
            post_response={"data": [after]},
        )
        result = await update_netflow_export_config(
            "default",
            settings,
            enabled=True,
            server="collector.example",
            confirm=True,
        )

    client.put.assert_not_awaited()
    client.post.assert_awaited_once_with(
        "/proxy/network/api/s/default/set/setting/netflow",
        json_data=after,
    )
    assert result == {
        "site_id": "default",
        "changed_fields": ["enabled", "server"],
        "before": before,
        "after": after,
        "verified": True,
    }


@pytest.mark.parametrize(
    ("updates", "error"),
    [
        ({}, "No NetFlow updates"),
        ({"version": 8}, "version"),
        ({"port": 1023}, "port"),
        ({"sampling_mode": "periodic"}, "sampling_mode"),
        ({"sampling_rate": 1}, "sampling_rate"),
        ({"export_frequency": 61}, "export_frequency"),
        ({"refresh_rate": 0}, "refresh_rate"),
        ({"engine_id": 0}, "engine_id"),
    ],
)
async def test_update_netflow_export_config_validates_fields(settings, updates, error):
    with pytest.raises(ValidationError, match=error):
        await update_netflow_export_config("default", settings, confirm=True, **updates)


async def test_update_netflow_export_config_requires_enabled_dependencies(settings):
    before = {
        "_id": "setting-1",
        "key": "netflow",
        "enabled": False,
        "version": 10,
        "auto_engine_id_enabled": True,
        "sampling_mode": "hash",
    }
    with patch("src.tools.netflow.UniFiClient") as client_class:
        _client(client_class, get_responses=[{"data": [before]}])
        with pytest.raises(ValidationError, match="server"):
            await update_netflow_export_config("default", settings, enabled=True, confirm=True)


async def test_netflow_rejects_cloud_mode(settings):
    """No Cloud Connector route is documented, so cloud mode must fail loudly."""
    settings.api_type = APIType.CLOUD_V1
    with pytest.raises(ValidationError, match="direct local-console access"):
        await get_netflow_export_config("default", settings)
    with pytest.raises(ValidationError, match="direct local-console access"):
        await update_netflow_export_config("default", settings, enabled=False, confirm=True)


async def test_netflow_read_rejects_a_non_list_envelope(settings):
    """A controller answer whose data is not a list yields no records."""
    with patch("src.tools.netflow.UniFiClient") as client_class:
        _client(client_class, get_responses=[{"data": {"key": "netflow"}}])
        with pytest.raises(ResourceNotFoundError, match="netflow"):
            await get_netflow_export_config("default", settings)


async def test_netflow_update_raises_when_record_missing_before_write(settings):
    with patch("src.tools.netflow.UniFiClient") as client_class:
        client = _client(client_class, get_responses=[{"data": []}])
        with pytest.raises(ResourceNotFoundError, match="netflow"):
            await update_netflow_export_config("default", settings, enabled=False, confirm=True)
    client.post.assert_not_awaited()


async def test_netflow_update_raises_when_record_missing_after_write(settings):
    before = {"_id": "s1", "key": "netflow", "enabled": False, "version": 10}
    with patch("src.tools.netflow.UniFiClient") as client_class:
        _client(
            client_class,
            get_responses=[{"data": [before]}, {"data": []}],
            post_response={"data": [before]},
        )
        with pytest.raises(ResourceNotFoundError, match="netflow"):
            await update_netflow_export_config(
                "default", settings, export_frequency=6, confirm=True
            )


async def test_netflow_enabled_requires_at_least_one_network(settings):
    before = {
        "_id": "s1",
        "key": "netflow",
        "enabled": False,
        "server": "collector.example",
        "network_ids": [],
        "version": 10,
    }
    with patch("src.tools.netflow.UniFiClient") as client_class:
        _client(client_class, get_responses=[{"data": [before]}])
        with pytest.raises(ValidationError, match="network_ids"):
            await update_netflow_export_config("default", settings, enabled=True, confirm=True)


async def test_netflow_v5_engine_id_is_capped_at_127(settings):
    before = {
        "_id": "s1",
        "key": "netflow",
        "enabled": False,
        "version": 10,
        "network_ids": ["n1"],
        "server": "collector.example",
    }
    with patch("src.tools.netflow.UniFiClient") as client_class:
        _client(client_class, get_responses=[{"data": [before]}])
        with pytest.raises(ValidationError, match="1 and 127"):
            await update_netflow_export_config(
                "default", settings, version=5, engine_id=128, confirm=True
            )
