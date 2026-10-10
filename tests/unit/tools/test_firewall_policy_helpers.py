"""Match-target helpers, zone resolution, update target overrides and delete
paths in src/tools/firewall_policies.py.

The client mock sets ``_site_uuid_to_name`` to a real dict: on a bare
``AsyncMock`` its ``.get`` returns an un-awaited coroutine, which then ends up
in the endpoint path.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.config.config import Settings
from src.tools import firewall_policies as fp
from src.utils.exceptions import ResourceNotFoundError

POLICY_ID = "682a0e42220317278bb0b2cb"
ZONE_INTERNAL = "682a0e42220317278bb0b2c5"  # pragma: allowlist secret
ZONE_EXTERNAL = "682a0e42220317278bb0b2c6"  # pragma: allowlist secret
V2 = "/proxy/network/v2/api/site/default"


@pytest.fixture
def local_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")  # pragma: allowlist secret
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
    return Settings()


@pytest.fixture(autouse=True)
def _clear_zone_cache():
    fp._zone_cache.clear()
    yield
    fp._zone_cache.clear()


def _policy(**overrides: Any) -> dict[str, Any]:
    return {
        "_id": POLICY_ID,
        "name": "Block IOT to Internal",
        "enabled": True,
        "action": "BLOCK",
        "predefined": False,
        "index": 10000,
        "protocol": "all",
        "ip_version": "BOTH",
        "source": {
            "zone_id": ZONE_INTERNAL,
            "matching_target": "ANY",
            "port": "80",
            "port_matching_type": "SPECIFIC",
        },
        "destination": {"zone_id": ZONE_EXTERNAL, "matching_target": "ANY"},
        **overrides,
    }


ZONES = [
    {"_id": ZONE_INTERNAL, "name": "Internal", "zone_key": "internal", "external_id": "uuid-int"},
    {"_id": ZONE_EXTERNAL, "name": "External"},
    {"name": "no id"},
]


def _client(get: Any = None) -> AsyncMock:
    client = AsyncMock()
    client.is_authenticated = True
    client._site_uuid_to_name = {}
    if callable(get):
        client.get.side_effect = get
    else:
        client.get.return_value = get
    return client


def _patch(client: AsyncMock):
    patcher = patch("src.tools.firewall_policies.UniFiClient")
    mock_cls = patcher.start()
    mock_cls.return_value.__aenter__.return_value = client
    return patcher


def _router(policy: Any):
    async def get(endpoint: str) -> Any:
        if endpoint.endswith("/firewall/zone"):
            return ZONES
        return policy

    return get


class TestBuildMatchTarget:
    @staticmethod
    def _build(**kwargs: Any) -> dict[str, Any]:
        base = {
            "zone_id": None,
            "matching_target": "ANY",
            "port": None,
            "port_group_id": None,
            "port_matching_type": None,
            "match_opposite_ports": None,
        }
        return fp._build_match_target(**{**base, **kwargs})

    def test_invalid_port_matching_type(self) -> None:
        with pytest.raises(ValueError, match="Invalid port_matching_type"):
            self._build(port_matching_type="range")

    def test_explicit_specific_requires_port(self) -> None:
        with pytest.raises(ValueError, match="requires a 'port'"):
            self._build(port_matching_type="specific")

    def test_explicit_object_requires_group(self) -> None:
        with pytest.raises(ValueError, match="requires a 'port_group_id'"):
            self._build(port_matching_type="OBJECT")

    @pytest.mark.parametrize(
        ("kwargs", "target"),
        [
            ({"ips": ["10.0.0.1"]}, "IP"),
            ({"network_ids": ["n1"]}, "NETWORK"),
            ({"client_macs": ["aa:bb:cc:dd:ee:ff"]}, "CLIENT"),
        ],
    )
    def test_infers_matching_target(self, kwargs: dict, target: str) -> None:
        result = self._build(**kwargs)
        assert result["matching_target"] == target
        assert result["matching_target_type"] == "SPECIFIC"

    def test_object_mode_with_all_options(self) -> None:
        result = self._build(
            zone_id="z1",
            port_group_id="pg1",
            match_opposite_ports=True,
            match_opposite_ips=False,
        )
        assert result == {
            "matching_target": "ANY",
            "port_matching_type": "OBJECT",
            "zone_id": "z1",
            "port_group_id": "pg1",
            "match_opposite_ports": True,
            "match_opposite_ips": False,
        }


class TestPortOverrides:
    @staticmethod
    def _collect(**kwargs: Any) -> dict[str, Any] | None:
        base = {
            "port": None,
            "port_group_id": None,
            "port_matching_type": None,
            "match_opposite_ports": None,
        }
        return fp._collect_port_overrides(**{**base, **kwargs})

    def test_nothing_requested(self) -> None:
        assert self._collect() is None

    def test_port_and_group_conflict(self) -> None:
        with pytest.raises(ValueError, match="Cannot specify both"):
            self._collect(port="80", port_group_id="pg1")

    def test_invalid_type(self) -> None:
        with pytest.raises(ValueError, match="Invalid port_matching_type"):
            self._collect(port_matching_type="nope")

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            ({"port_group_id": "pg1"}, {"port_matching_type": "OBJECT", "port_group_id": "pg1"}),
            ({"port": "53"}, {"port_matching_type": "SPECIFIC", "port": "53"}),
            ({"match_opposite_ports": True}, {"match_opposite_ports": True}),
            ({"port_matching_type": "any"}, {"port_matching_type": "ANY"}),
        ],
    )
    def test_collects(self, kwargs: dict, expected: dict) -> None:
        assert self._collect(**kwargs) == expected

    @pytest.mark.parametrize(
        ("mode", "expected_keys"),
        [
            ("ANY", {"port_matching_type", "zone_id"}),
            ("SPECIFIC", {"port_matching_type", "zone_id", "port"}),
            ("OBJECT", {"port_matching_type", "zone_id", "port_group_id"}),
        ],
    )
    def test_merge_clears_stale_fields(self, mode: str, expected_keys: set) -> None:
        existing = {"zone_id": "z", "port": "80", "port_group_id": "pg1"}
        merged = fp._merge_port_overrides(existing, {"port_matching_type": mode})
        assert set(merged) == expected_keys


class TestZoneResolution:
    @pytest.mark.parametrize(
        ("response", "expected"),
        [
            ([{"_id": "a"}, "x"], [{"_id": "a"}]),
            ({"data": None}, []),
            ({"data": [{"_id": "b"}, 3]}, [{"_id": "b"}]),
            ({"data": {"_id": "c"}}, []),
            ("x", []),
        ],
    )
    def test_extract_zone_list(self, response: Any, expected: list) -> None:
        assert fp._extract_zone_list(response) == expected

    @pytest.mark.asyncio
    async def test_index_maps_every_identifier(self, local_settings: Settings) -> None:
        client = _client(ZONES)

        index = await fp._load_zone_index(client, local_settings, "default")

        client.get.assert_awaited_once_with(f"{V2}/firewall/zone")
        assert index == {
            ZONE_INTERNAL: ZONE_INTERNAL,
            "uuid-int": ZONE_INTERNAL,
            "internal": ZONE_INTERNAL,
            ZONE_EXTERNAL: ZONE_EXTERNAL,
            "external": ZONE_EXTERNAL,
        }
        assert fp._zone_cache["default"] is index

    @pytest.mark.asyncio
    @pytest.mark.parametrize("identifier", ["Internal", "internal", "uuid-int", ZONE_INTERNAL])
    async def test_resolves_names_and_ids(self, local_settings: Settings, identifier: str) -> None:
        client = _client(ZONES)
        assert await fp._resolve_zone_id(client, local_settings, "default", identifier) == (
            ZONE_INTERNAL
        )

    @pytest.mark.asyncio
    async def test_refreshes_stale_cache_once(self, local_settings: Settings) -> None:
        fp._zone_cache["default"] = {"old": "old-id"}
        client = _client(ZONES)

        assert await fp._resolve_zone_id(client, local_settings, "default", "External") == (
            ZONE_EXTERNAL
        )
        client.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refresh_matches_exact_identifier(self, local_settings: Settings) -> None:
        fp._zone_cache["default"] = {"old": "old-id"}
        client = _client(ZONES)

        assert await fp._resolve_zone_id(client, local_settings, "default", "uuid-int") == (
            ZONE_INTERNAL
        )

    @pytest.mark.asyncio
    async def test_unknown_zone(self, local_settings: Settings) -> None:
        client = _client(ZONES)
        with pytest.raises(ValueError, match="Could not resolve firewall zone 'Guest'"):
            await fp._resolve_zone_id(client, local_settings, "default", "Guest")
        assert client.get.await_count == 2

    @pytest.mark.asyncio
    async def test_blank_identifier(self, local_settings: Settings) -> None:
        with pytest.raises(ValueError, match="required"):
            await fp._resolve_zone_id(_client(), local_settings, "default", "")


class TestUpdateTargetOverrides:
    @pytest.mark.asyncio
    async def test_source_and_destination_overrides_dry_run(self, local_settings: Settings) -> None:
        client = _client(_router(_policy()))
        patcher = _patch(client)
        try:
            result = await fp.update_firewall_policy(
                policy_id=POLICY_ID,
                site_id="default",
                settings=local_settings,
                source_zone_id="External",
                source_ips=["10.0.0.0/24"],
                source_match_opposite_ips=True,
                source_port_matching_type="ANY",
                destination_zone_id="internal",
                destination_network_ids=["net-1"],
                destination_client_macs=["aa:bb:cc:dd:ee:ff"],
                destination_match_opposite_ips=False,
                destination_port_group_id="pg-1",
                dry_run=True,
            )
        finally:
            patcher.stop()

        merged = result["merged_payload"]
        assert result["status"] == "dry_run"
        assert "_id" not in merged and "predefined" not in merged
        assert merged["source"] == {
            "zone_id": ZONE_EXTERNAL,
            "matching_target": "IP",
            "matching_target_type": "SPECIFIC",
            "ips": ["10.0.0.0/24"],
            "match_opposite_ips": True,
            "port_matching_type": "ANY",
        }
        dst = merged["destination"]
        assert dst["zone_id"] == ZONE_INTERNAL
        assert dst["matching_target"] == "CLIENT"  # last list given wins
        assert dst["network_ids"] == ["net-1"]
        assert dst["client_macs"] == ["aa:bb:cc:dd:ee:ff"]
        assert dst["match_opposite_ips"] is False
        assert dst["port_matching_type"] == "OBJECT"
        assert dst["port_group_id"] == "pg-1"
        client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_source_network_and_client_lists(self, local_settings: Settings) -> None:
        client = _client(_router({"data": _policy()}))
        patcher = _patch(client)
        try:
            result = await fp.update_firewall_policy(
                policy_id=POLICY_ID,
                site_id="default",
                settings=local_settings,
                source_network_ids=["net-2"],
                source_client_macs=["aa:bb:cc:dd:ee:01"],
                destination_ips=["192.0.2.1"],
                dry_run=True,
            )
        finally:
            patcher.stop()

        src = result["merged_payload"]["source"]
        assert src["network_ids"] == ["net-2"]
        assert src["client_macs"] == ["aa:bb:cc:dd:ee:01"]
        assert result["merged_payload"]["destination"]["ips"] == ["192.0.2.1"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("current", [None, [], "x"])
    async def test_missing_policy(self, local_settings: Settings, current: Any) -> None:
        client = _client(current)
        patcher = _patch(client)
        try:
            with pytest.raises(ResourceNotFoundError):
                await fp.update_firewall_policy(
                    policy_id=POLICY_ID,
                    site_id="default",
                    settings=local_settings,
                    name="x",
                    confirm=True,
                )
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["get", "put"])
    async def test_not_found_is_rewrapped(self, local_settings: Settings, method: str) -> None:
        client = _client(_policy())
        getattr(client, method).side_effect = ResourceNotFoundError("resource", "x")
        patcher = _patch(client)
        try:
            with pytest.raises(ResourceNotFoundError, match=POLICY_ID):
                await fp.update_firewall_policy(
                    policy_id=POLICY_ID,
                    site_id="default",
                    settings=local_settings,
                    name="x",
                    confirm=True,
                )
        finally:
            patcher.stop()


class TestDeleteFirewallPolicy:
    @pytest.mark.asyncio
    async def test_requires_confirm(self, local_settings: Settings) -> None:
        with pytest.raises(ValueError, match="confirm=True"):
            await fp.delete_firewall_policy(POLICY_ID, "default", local_settings)

    @pytest.mark.asyncio
    async def test_rejects_cloud(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")  # pragma: allowlist secret
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        with pytest.raises(NotImplementedError):
            await fp.delete_firewall_policy(POLICY_ID, "default", Settings(), confirm=True)

    @pytest.mark.asyncio
    async def test_dry_run_previews(self, local_settings: Settings) -> None:
        client = _client({"data": _policy()})
        client.is_authenticated = False
        patcher = _patch(client)
        try:
            result = await fp.delete_firewall_policy(
                POLICY_ID, "default", local_settings, dry_run=True
            )
        finally:
            patcher.stop()

        client.authenticate.assert_awaited_once()
        client.get.assert_awaited_once_with(f"{V2}/firewall-policies/{POLICY_ID}")
        assert result["action"] == "would_delete"
        assert result["policy"]["name"] == "Block IOT to Internal"
        client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes_and_audits(self, local_settings: Settings) -> None:
        client = _client(_policy())
        patcher = _patch(client)
        try:
            with patch("src.tools.firewall_policies.log_audit") as audit:
                result = await fp.delete_firewall_policy(
                    POLICY_ID, "default", local_settings, confirm=True
                )
        finally:
            patcher.stop()

        client.delete.assert_awaited_once_with(f"{V2}/firewall-policies/{POLICY_ID}")
        assert result == {"status": "success", "policy_id": POLICY_ID, "action": "deleted"}
        assert audit.call_args.kwargs["operation"] == "delete_firewall_policy"

    @pytest.mark.asyncio
    async def test_predefined_rule_refused(self, local_settings: Settings) -> None:
        client = _client(_policy(predefined=True))
        patcher = _patch(client)
        try:
            with pytest.raises(ValueError, match="Cannot delete predefined"):
                await fp.delete_firewall_policy(POLICY_ID, "default", local_settings, confirm=True)
        finally:
            patcher.stop()
        client.delete.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("response", [{"data": None}, None])
    async def test_missing_policy(self, local_settings: Settings, response: Any) -> None:
        client = _client(response)
        patcher = _patch(client)
        try:
            with pytest.raises(ResourceNotFoundError):
                await fp.delete_firewall_policy(POLICY_ID, "default", local_settings, confirm=True)
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_get_not_found_is_rewrapped(self, local_settings: Settings) -> None:
        client = _client()
        client.get.side_effect = ResourceNotFoundError("resource", "x")
        patcher = _patch(client)
        try:
            with pytest.raises(ResourceNotFoundError, match=POLICY_ID):
                await fp.delete_firewall_policy(POLICY_ID, "default", local_settings, confirm=True)
        finally:
            patcher.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", [fp.update_firewall_policy, fp.delete_firewall_policy])
async def test_settings_is_required(tool) -> None:
    with pytest.raises(ValueError, match="settings is required"):
        await tool(POLICY_ID, "default", None, confirm=True)
