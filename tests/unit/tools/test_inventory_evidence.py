"""Offline contract tests for bounded, minimized inventory evidence (EV-02/03)."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.inventory_evidence import collect_inventory_topology
from src.utils.exceptions import APIError, AuthenticationError, ValidationError


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("UNIFI_API_KEY", "fixture-value")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.0.2.1")
    return Settings(_env_file=None)


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.paths = []
        self.authenticate = AsyncMock()
        self.resolve_site_id = AsyncMock(return_value="123e4567-e89b-12d3-a456-426614174000")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def get(self, path):
        self.paths.append(path)
        value = self.responses[path.split("/")[-1].split("?")[0]]
        if isinstance(value, Exception):
            raise value
        if callable(value):
            return await value(path)
        return value


def client_patch(client):
    return patch("src.tools.inventory_evidence.UniFiClient", return_value=client)


@pytest.mark.asyncio
async def test_snapshot_is_scoped_minimized_and_observation_time_unknown(settings):
    device = {
        "id": "device-a",
        "name": "private-name",
        "macAddress": "aa:bb:cc:dd:ee:ff",
        "ipAddress": "10.0.0.1",
        "model": "USW",
        "state": "ONLINE",
        "password": "should-never-escape",  # pragma: allowlist secret
    }
    client_record = {
        "id": "client-a",
        "name": "private-client",
        "macAddress": "11:22:33:44:55:66",
        "uplinkDeviceId": "device-a",
        "secret": "should-never-escape",  # pragma: allowlist secret
    }
    fake = FakeClient({"devices": {"data": [device]}, "clients": {"data": [client_record]}})
    with client_patch(fake):
        result = await collect_inventory_topology("default", settings, max_records=20)
    assert result["schema_version"] == "1"
    assert result["scope"] == {
        "controller": "default",
        "site_id": fake.resolve_site_id.return_value,
    }
    assert result["sections"]["devices"]["status"] == "ok"
    assert result["sections"]["clients"]["status"] == "ok"
    assert result["freshness"] == "unknown"
    assert result["completeness"] == "complete"
    assert result["relationships"] == [
        {"source": "client:1", "target": "device:1", "kind": "uplink", "basis": "observed"}
    ]
    assert result["redaction"] == "allowlist; client names, addresses and raw payloads excluded"
    text = str(result)
    for sensitive in (
        "private-name",
        "private-client",
        "aa:bb",
        "10.0.0.1",
        "fixture-value",
        "should-never-escape",
    ):
        assert sensitive not in text
    assert all("123e4567-e89b-12d3-a456-426614174000" in p for p in fake.paths)
    assert all("offset=0&limit=20" in p for p in fake.paths)
    fake.resolve_site_id.assert_awaited_once_with("default")


@pytest.mark.asyncio
async def test_empty_success_is_not_failed(settings):
    fake = FakeClient({"devices": {"data": []}, "clients": {"data": []}})
    with client_patch(fake):
        result = await collect_inventory_topology("default", settings)
    assert result["completeness"] == "complete"
    assert result["sections"]["clients"]["status"] == "empty"
    assert result["sections"]["devices"]["status"] == "empty"


@pytest.mark.asyncio
async def test_device_identifier_that_is_a_mac_is_not_serialized(settings):
    mac = "aa:bb:cc:dd:ee:ff"
    fake = FakeClient(
        {
            "devices": {"data": [{"id": mac, "state": "ONLINE"}]},
            "clients": {"data": [{"id": "client-1", "uplinkDeviceId": mac}]},
        }
    )
    with client_patch(fake):
        result = await collect_inventory_topology("default", settings)
    assert mac not in str(result)
    assert result["data"]["devices"] == [{"id": "device:1", "state": "ONLINE"}]
    assert result["relationships"][0]["target"] == "device:1"


@pytest.mark.asyncio
async def test_device_list_without_id_retains_inventory_but_not_unproven_links(settings):
    fake = FakeClient(
        {
            "devices": {"data": [{"name": "private-ap", "state": "ONLINE"}]},
            "clients": {"data": [{"id": "client-1", "uplinkDeviceId": "unknown-id"}]},
        }
    )
    with client_patch(fake):
        result = await collect_inventory_topology("default", settings)
    assert result["data"]["devices"] == [{"id": "device:1", "state": "ONLINE"}]
    assert result["sections"]["devices"]["status"] == "partial"
    assert result["sections"]["devices"]["reason"] == "missing_identity"
    assert result["completeness"] == "partial"
    assert result["relationships"] == []
    assert "private-ap" not in str(result)


@pytest.mark.asyncio
async def test_legacy_device_id_alias_can_resolve_explicit_uplink(settings):
    fake = FakeClient(
        {
            "devices": {"data": [{"_id": "legacy-1", "state": "ONLINE"}]},
            "clients": {"data": [{"id": "client-1", "uplinkDeviceId": "legacy-1"}]},
        }
    )
    with client_patch(fake):
        result = await collect_inventory_topology("default", settings)
    assert result["sections"]["devices"]["status"] == "ok"
    assert result["relationships"] == [
        {"source": "client:1", "target": "device:1", "kind": "uplink", "basis": "observed"}
    ]


@pytest.mark.asyncio
async def test_ambiguous_normalized_ids_do_not_misattribute_links(settings):
    fake = FakeClient(
        {
            "devices": {
                "data": [
                    {"id": " device-a", "state": "ONLINE"},
                    {"id": "device-a", "state": "OFFLINE"},
                ]
            },
            "clients": {"data": [{"id": "client-1", "uplinkDeviceId": "device-a"}]},
        }
    )
    with client_patch(fake):
        result = await collect_inventory_topology("default", settings)
    assert result["sections"]["devices"]["status"] == "partial"
    assert result["data"]["devices"] == [{"id": "device:1", "state": "OFFLINE"}]
    assert result["relationships"] == [
        {"source": "client:1", "target": "device:1", "kind": "uplink", "basis": "observed"}
    ]


@pytest.mark.asyncio
async def test_page_cap_is_honest_about_truncation(settings):
    async def pages(path):
        offset = int(path.split("offset=")[1].split("&")[0])
        return {"data": [{"id": f"id-{offset+i}"} for i in range(2)]}

    fake = FakeClient({"devices": pages, "clients": {"data": []}})
    with client_patch(fake):
        result = await collect_inventory_topology("default", settings, max_records=2, max_pages=2)
    assert len(result["data"]["devices"]) == 4
    assert result["sections"]["devices"]["truncated"] is True
    assert result["completeness"] == "partial"
    assert len([p for p in fake.paths if "/devices?" in p]) == 2


@pytest.mark.asyncio
async def test_repeated_page_is_partial_not_complete(settings):
    fake = FakeClient(
        {"devices": {"data": [{"id": "same"}, {"id": "other"}]}, "clients": {"data": []}}
    )
    with client_patch(fake):
        result = await collect_inventory_topology("default", settings, max_records=2, max_pages=3)
    assert result["sections"]["devices"]["status"] == "partial"
    assert result["completeness"] == "partial"
    assert len([p for p in fake.paths if "/devices?" in p]) == 2


@pytest.mark.asyncio
async def test_failed_section_does_not_masquerade_as_empty(settings):
    fake = FakeClient({"devices": RuntimeError("password=do-not-leak"), "clients": {"data": []}})
    with client_patch(fake):
        result = await collect_inventory_topology("default", settings)
    assert result["sections"]["devices"]["status"] == "failed"
    assert result["sections"]["devices"]["reason"] == "collection_error"
    assert result["completeness"] == "partial"
    assert "do-not-leak" not in str(result)


@pytest.mark.asyncio
async def test_authentication_failure_is_fail_closed(settings):
    fake = FakeClient({"devices": AuthenticationError("not permitted"), "clients": {"data": []}})
    with client_patch(fake), pytest.raises(AuthenticationError):
        await collect_inventory_topology("default", settings)


@pytest.mark.asyncio
async def test_invalid_or_ambiguous_scope_rejected_before_client(settings):
    with patch("src.tools.inventory_evidence.UniFiClient") as ctor:
        with pytest.raises(ValidationError):
            await collect_inventory_topology("../other", settings)
        with pytest.raises(ValidationError):
            await collect_inventory_topology("default", settings, max_records=0)
        with pytest.raises(ValidationError):
            await collect_inventory_topology("default", settings, max_pages=0)
        with pytest.raises(ValidationError):
            await collect_inventory_topology("default", settings, timeout_seconds=0)
        ctor.assert_not_called()
    settings.mixed_mode = True
    with pytest.raises(ValidationError):
        await collect_inventory_topology("default", settings)
    settings.mixed_mode = False
    settings.database_url = "postgresql://placeholder.invalid/test"
    with patch("src.tools.inventory_evidence.UniFiClient") as ctor:
        with pytest.raises(ValidationError):
            await collect_inventory_topology("default", settings)
        ctor.assert_not_called()


@pytest.mark.asyncio
async def test_timeout_yields_partial_and_bounded_concurrency(settings):
    active = 0
    peak = 0

    async def slow(path):
        nonlocal active, peak
        active += 1
        peak = max(active, peak)
        try:
            await asyncio.sleep(2)
            return {"data": [{"id": "late"}]}
        finally:
            active -= 1

    fake = FakeClient({"devices": slow, "clients": slow})
    with client_patch(fake):
        result = await collect_inventory_topology("default", settings, timeout_seconds=1)
    assert peak <= 2
    assert active == 0
    assert result["completeness"] != "complete"
    assert result["sections"]["devices"]["status"] == "failed"
    assert result["sections"]["devices"]["reason"] == "timeout"


@pytest.mark.asyncio
async def test_slow_cancellation_fails_closed_instead_of_returning_late_evidence(settings):
    async def slow_cleanup(path):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await asyncio.sleep(0.2)
            raise

    fake = FakeClient({"devices": slow_cleanup, "clients": slow_cleanup})
    with client_patch(fake), pytest.raises(APIError, match="deadline"):
        await collect_inventory_topology("default", settings, timeout_seconds=1)


@pytest.mark.asyncio
async def test_authentication_is_inside_total_deadline(settings):
    fake = FakeClient({"devices": {"data": []}, "clients": {"data": []}})

    async def slow_auth():
        await asyncio.sleep(2)

    fake.authenticate = AsyncMock(side_effect=slow_auth)
    with client_patch(fake), pytest.raises(APIError, match="deadline"):
        await collect_inventory_topology("default", settings, timeout_seconds=1)
    fake.resolve_site_id.assert_not_awaited()
    assert fake.paths == []


@pytest.mark.asyncio
async def test_caller_cancellation_does_not_leave_section_reads_running(settings):
    active = 0
    started = asyncio.Event()

    async def slow(path):
        nonlocal active
        active += 1
        started.set()
        try:
            await asyncio.sleep(10)
            return {"data": []}
        finally:
            active -= 1

    fake = FakeClient({"devices": slow, "clients": slow})
    with client_patch(fake):
        task = asyncio.create_task(collect_inventory_topology("default", settings))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
    assert active == 0
