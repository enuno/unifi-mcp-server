"""Tests for the UniFi Carrier Fabric tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import carrier

_PLAN = "plan-1"
_SUBSCRIBER = "sub-1"
_HOST = "host-1"


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
    return patch("src.tools.carrier.SiteManagerClient", return_value=cm)


# ── service plans ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_carrier_service_plans(settings):
    response = {"data": [{"id": _PLAN, "name": "Fiber 1G"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.list_carrier_service_plans(settings)

    assert result["count"] == 1
    assert result["data"][0]["name"] == "Fiber 1G"
    client.get.assert_called_once_with("carrier/service-plans")


@pytest.mark.asyncio
async def test_list_carrier_service_plans_requires_cloud(settings):
    settings.site_manager_enabled = False
    with pytest.raises(ValueError, match="UNIFI_SITE_MANAGER_ENABLED"):
        await carrier.list_carrier_service_plans(settings)


@pytest.mark.asyncio
async def test_get_carrier_service_plan(settings):
    client, cm = _make_client({"data": {"id": _PLAN, "name": "Fiber 1G"}})
    with _patch_client(cm):
        result = await carrier.get_carrier_service_plan(_PLAN, settings)

    assert result["id"] == _PLAN
    client.get.assert_called_once_with(f"carrier/service-plans/{_PLAN}")


@pytest.mark.asyncio
async def test_get_carrier_service_plan_rejects_empty_id(settings):
    with pytest.raises(Exception, match="plan_id"):
        await carrier.get_carrier_service_plan("   ", settings)


# ── subscribers: reads ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_carrier_subscribers_minimal_params(settings):
    response = {"data": [{"id": _SUBSCRIBER, "subscriberNumber": "SN-1"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.list_carrier_subscribers(settings)

    assert result["count"] == 1
    client.get.assert_called_once_with("carrier/subscribers", params={"limit": 100, "offset": 0})


@pytest.mark.asyncio
async def test_list_carrier_subscribers_with_optional_filters(settings):
    response = {"data": [{"id": _SUBSCRIBER, "subscriberNumber": "SN-1"}]}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.list_carrier_subscribers(
            settings, limit=50, offset=10, plan_id=_PLAN, suspended=True
        )

    assert result["limit"] == 50
    assert result["offset"] == 10
    client.get.assert_called_once_with(
        "carrier/subscribers",
        params={"limit": 50, "offset": 10, "planId": _PLAN, "suspended": True},
    )


@pytest.mark.asyncio
async def test_list_carrier_subscribers_rejects_bad_limit(settings):
    with pytest.raises(Exception, match="limit|Limit"):
        await carrier.list_carrier_subscribers(settings, limit=0)


@pytest.mark.asyncio
async def test_get_carrier_subscriber(settings):
    client, cm = _make_client({"data": {"id": _SUBSCRIBER, "subscriberNumber": "SN-1"}})
    with _patch_client(cm):
        result = await carrier.get_carrier_subscriber(_SUBSCRIBER, settings)

    assert result["id"] == _SUBSCRIBER
    client.get.assert_called_once_with(f"carrier/subscribers/{_SUBSCRIBER}")


@pytest.mark.asyncio
async def test_get_carrier_subscriber_rejects_empty_id(settings):
    with pytest.raises(Exception, match="subscriber_id"):
        await carrier.get_carrier_subscriber("", settings)


# ── subscribers: writes ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_carrier_subscriber_success(settings):
    response = {"data": {"id": _SUBSCRIBER, "subscriberNumber": "SN-1", "name": "Acme"}}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.create_carrier_subscriber(
            settings,
            "SN-1",
            name="Acme",
            email="ops@example.com",
            service_address="1 Main St",
            plan_id=_PLAN,
            host_id=_HOST,
            metadata={"tier": "gold"},
            confirm=True,
        )

    assert result["name"] == "Acme"
    client.post.assert_called_once_with(
        "carrier/subscribers",
        json_data={
            "subscriberNumber": "SN-1",
            "name": "Acme",
            "email": "ops@example.com",
            "serviceAddress": "1 Main St",
            "planId": _PLAN,
            "hostId": _HOST,
            "metadata": {"tier": "gold"},
        },
    )


@pytest.mark.asyncio
async def test_create_carrier_subscriber_requires_confirmation(settings):
    with pytest.raises(Exception, match="confirmation"):
        await carrier.create_carrier_subscriber(settings, "SN-1")


@pytest.mark.asyncio
async def test_create_carrier_subscriber_rejects_empty_number(settings):
    with pytest.raises(Exception, match="subscriber_number"):
        await carrier.create_carrier_subscriber(settings, "   ", confirm=True)


@pytest.mark.asyncio
async def test_create_carrier_subscriber_rejects_long_number(settings):
    with pytest.raises(Exception, match="32"):
        await carrier.create_carrier_subscriber(settings, "x" * 33, confirm=True)


@pytest.mark.asyncio
async def test_create_carrier_subscriber_dry_run(settings):
    client, cm = _make_client({"data": {}})
    with _patch_client(cm):
        result = await carrier.create_carrier_subscriber(
            settings, "SN-1", name="Acme", dry_run=True
        )

    assert result["dry_run"] is True
    assert result["payload"] == {"subscriberNumber": "SN-1", "name": "Acme"}
    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_update_carrier_subscriber_success(settings):
    response = {"data": {"id": _SUBSCRIBER, "name": "New Name", "email": "new@example.com"}}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.update_carrier_subscriber(
            _SUBSCRIBER, settings, name="New Name", email="new@example.com", confirm=True
        )

    assert result["name"] == "New Name"
    client.patch.assert_called_once_with(
        f"carrier/subscribers/{_SUBSCRIBER}",
        json_data={"name": "New Name", "email": "new@example.com"},
    )


@pytest.mark.asyncio
async def test_update_carrier_subscriber_rejects_no_updates(settings):
    with pytest.raises(Exception, match="No updates"):
        await carrier.update_carrier_subscriber(_SUBSCRIBER, settings, confirm=True)


@pytest.mark.asyncio
async def test_update_carrier_subscriber_rejects_empty_id(settings):
    with pytest.raises(Exception, match="subscriber_id"):
        await carrier.update_carrier_subscriber("  ", settings, name="X", confirm=True)


@pytest.mark.asyncio
async def test_update_carrier_subscriber_dry_run(settings):
    client, cm = _make_client({"data": {}})
    with _patch_client(cm):
        result = await carrier.update_carrier_subscriber(
            _SUBSCRIBER, settings, notes="n", dry_run=True
        )

    assert result["payload"] == {"notes": "n"}
    client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_attach_carrier_subscriber_host_success(settings):
    response = {"data": {"id": _SUBSCRIBER, "hostId": _HOST}}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.attach_carrier_subscriber_host(
            _SUBSCRIBER, settings, _HOST, confirm=True
        )

    assert result["hostId"] == _HOST
    client.put.assert_called_once_with(
        f"carrier/subscribers/{_SUBSCRIBER}/host", json_data={"hostId": _HOST}
    )


@pytest.mark.asyncio
async def test_attach_carrier_subscriber_host_rejects_empty_host(settings):
    with pytest.raises(Exception, match="host_id"):
        await carrier.attach_carrier_subscriber_host(_SUBSCRIBER, settings, " ", confirm=True)


@pytest.mark.asyncio
async def test_attach_carrier_subscriber_host_dry_run(settings):
    client, cm = _make_client({"data": {}})
    with _patch_client(cm):
        result = await carrier.attach_carrier_subscriber_host(
            _SUBSCRIBER, settings, _HOST, dry_run=True
        )

    assert result["dry_run"] is True
    client.put.assert_not_called()


@pytest.mark.asyncio
async def test_detach_carrier_subscriber_host_success(settings):
    response = {"data": {"id": _SUBSCRIBER, "hostId": None}}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.detach_carrier_subscriber_host(_SUBSCRIBER, settings, confirm=True)

    assert result["id"] == _SUBSCRIBER
    client.delete.assert_called_once_with(f"carrier/subscribers/{_SUBSCRIBER}/host")


@pytest.mark.asyncio
async def test_detach_carrier_subscriber_host_dry_run(settings):
    client, cm = _make_client({"data": {}})
    with _patch_client(cm):
        result = await carrier.detach_carrier_subscriber_host(_SUBSCRIBER, settings, dry_run=True)

    assert result["dry_run"] is True
    client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_assign_carrier_subscriber_plan_success(settings):
    response = {"data": {"id": _SUBSCRIBER, "planId": _PLAN}}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.assign_carrier_subscriber_plan(
            _SUBSCRIBER, settings, _PLAN, confirm=True
        )

    assert result["planId"] == _PLAN
    client.put.assert_called_once_with(
        f"carrier/subscribers/{_SUBSCRIBER}/plan", json_data={"planId": _PLAN}
    )


@pytest.mark.asyncio
async def test_assign_carrier_subscriber_plan_rejects_empty_plan(settings):
    with pytest.raises(Exception, match="plan_id"):
        await carrier.assign_carrier_subscriber_plan(_SUBSCRIBER, settings, "", confirm=True)


@pytest.mark.asyncio
async def test_resume_carrier_subscriber_success(settings):
    response = {"data": {"id": _SUBSCRIBER, "suspended": False}}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.resume_carrier_subscriber(_SUBSCRIBER, settings, confirm=True)

    assert result["suspended"] is False
    client.post.assert_called_once_with(f"carrier/subscribers/{_SUBSCRIBER}/resume")


@pytest.mark.asyncio
async def test_resume_carrier_subscriber_dry_run(settings):
    client, cm = _make_client({"data": {}})
    with _patch_client(cm):
        result = await carrier.resume_carrier_subscriber(_SUBSCRIBER, settings, dry_run=True)

    assert result["dry_run"] is True
    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_suspend_carrier_subscriber_with_reason(settings):
    response = {"data": {"id": _SUBSCRIBER, "suspended": True}}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.suspend_carrier_subscriber(
            _SUBSCRIBER, settings, reason="non-payment", confirm=True
        )

    assert result["suspended"] is True
    client.post.assert_called_once_with(
        f"carrier/subscribers/{_SUBSCRIBER}/suspend", json_data={"reason": "non-payment"}
    )


@pytest.mark.asyncio
async def test_suspend_carrier_subscriber_without_reason(settings):
    response = {"data": {"id": _SUBSCRIBER, "suspended": True}}
    client, cm = _make_client(response)
    with _patch_client(cm):
        result = await carrier.suspend_carrier_subscriber(_SUBSCRIBER, settings, confirm=True)

    assert result["suspended"] is True
    client.post.assert_called_once_with(f"carrier/subscribers/{_SUBSCRIBER}/suspend")


@pytest.mark.asyncio
async def test_suspend_carrier_subscriber_dry_run(settings):
    client, cm = _make_client({"data": {}})
    with _patch_client(cm):
        result = await carrier.suspend_carrier_subscriber(
            _SUBSCRIBER, settings, reason="r", dry_run=True
        )

    assert result["dry_run"] is True
    assert result["payload"] == {"reason": "r"}
    client.post.assert_not_called()
