"""Unit tests for the clients, devices and networks MCP resources."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.resources.clients import ClientsResource
from src.resources.devices import DevicesResource
from src.resources.networks import NetworksResource
from src.utils.exceptions import ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    return settings


def create_mock_client(response):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client.authenticate = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _client(mac, is_wired):
    return {"mac": mac, "is_wired": is_wired}


def _device(device_id, device_type, model):
    return {
        "_id": device_id,
        "type": device_type,
        "model": model,
        "mac": f"aa:bb:cc:00:00:{device_id[-2:]}",
        "state": 1,
    }


def _network(network_id, vlan=None):
    network = {"_id": network_id, "name": f"net {network_id}", "purpose": "corporate"}
    if vlan is not None:
        network["vlan"] = vlan
    return network


class TestClientsResource:
    @pytest.mark.asyncio
    async def test_list_all_clients_uses_alluser(self, mock_settings):
        client = create_mock_client({"data": [_client("aa:00", True), _client("aa:01", False)]})
        with patch("src.resources.clients.UniFiClient", return_value=client):
            result = await ClientsResource(mock_settings).list_clients("default")

        client.authenticate.assert_awaited_once()
        client.get.assert_awaited_once_with("/ea/sites/default/stat/alluser")
        assert [c.mac for c in result] == ["aa:00", "aa:01"]

    @pytest.mark.asyncio
    async def test_active_only_uses_sta_and_paginates(self, mock_settings):
        data = [_client(f"aa:{i:02d}", True) for i in range(5)]
        client = create_mock_client({"data": data})
        with patch("src.resources.clients.UniFiClient", return_value=client):
            result = await ClientsResource(mock_settings).list_clients(
                "default", limit=2, offset=1, active_only=True
            )

        client.get.assert_awaited_once_with("/ea/sites/default/sta")
        assert [c.mac for c in result] == ["aa:01", "aa:02"]

    @pytest.mark.asyncio
    async def test_rejects_invalid_site(self, mock_settings):
        with pytest.raises(ValidationError):
            await ClientsResource(mock_settings).list_clients("../etc")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("is_wired", "expected"),
        [(True, ["aa:00", "aa:02"]), (False, ["aa:01"]), (None, ["aa:00", "aa:01", "aa:02"])],
    )
    async def test_filter_by_connection(self, mock_settings, is_wired, expected):
        data = [_client("aa:00", True), _client("aa:01", False), _client("aa:02", True)]
        client = create_mock_client({"data": data})
        with patch("src.resources.clients.UniFiClient", return_value=client):
            result = await ClientsResource(mock_settings).filter_by_connection(
                "default", is_wired=is_wired
            )

        client.get.assert_awaited_once_with("/ea/sites/default/sta")
        assert [c.mac for c in result] == expected

    def test_get_uri(self, mock_settings):
        resource = ClientsResource(mock_settings)
        assert resource.get_uri("default") == "sites://default/clients"
        assert resource.get_uri("default", "aa:00") == "sites://default/clients/aa:00"


class TestDevicesResource:
    @pytest.mark.asyncio
    async def test_list_devices_paginates(self, mock_settings):
        data = [_device(f"dev-{i:02d}", "uap", "U6-Pro") for i in range(4)]
        client = create_mock_client({"data": data})
        with patch("src.resources.devices.UniFiClient", return_value=client):
            result = await DevicesResource(mock_settings).list_devices("default", limit=2, offset=2)

        client.authenticate.assert_awaited_once()
        client.get.assert_awaited_once_with("/ea/sites/default/devices")
        assert [d.id for d in result] == ["dev-02", "dev-03"]

    @pytest.mark.asyncio
    async def test_list_devices_empty(self, mock_settings):
        client = create_mock_client({})
        with patch("src.resources.devices.UniFiClient", return_value=client):
            assert await DevicesResource(mock_settings).list_devices("default") == []

    @pytest.mark.asyncio
    async def test_filter_by_type_matches_type_or_model(self, mock_settings):
        data = [
            _device("dev-01", "uap", "U6-Pro"),
            _device("dev-02", "usw", "USW-24"),
            _device("dev-03", "ugw", "UAP-in-name"),
        ]
        client = create_mock_client({"data": data})
        with patch("src.resources.devices.UniFiClient", return_value=client):
            result = await DevicesResource(mock_settings).filter_by_type("default", "UAP")

        assert [d.id for d in result] == ["dev-01", "dev-03"]

    def test_get_uri(self, mock_settings):
        resource = DevicesResource(mock_settings)
        assert resource.get_uri("default") == "sites://default/devices"
        assert resource.get_uri("default", "dev-1") == "sites://default/devices/dev-1"


class TestNetworksResource:
    @pytest.mark.asyncio
    async def test_list_networks_paginates(self, mock_settings):
        data = [_network(f"n{i}") for i in range(3)]
        client = create_mock_client({"data": data})
        with patch("src.resources.networks.UniFiClient", return_value=client):
            result = await NetworksResource(mock_settings).list_networks("default", limit=2)

        client.authenticate.assert_awaited_once()
        client.get.assert_awaited_once_with("/ea/sites/default/rest/networkconf")
        assert [n.id for n in result] == ["n0", "n1"]

    @pytest.mark.asyncio
    async def test_list_vlans_filters_untagged(self, mock_settings):
        data = [_network("n0"), _network("n1", vlan=10), _network("n2", vlan=20)]
        client = create_mock_client({"data": data})
        with patch("src.resources.networks.UniFiClient", return_value=client):
            result = await NetworksResource(mock_settings).list_vlans("default", offset=1)

        assert [n.vlan_id for n in result] == [20]

    def test_get_uri(self, mock_settings):
        resource = NetworksResource(mock_settings)
        assert resource.get_uri("default") == "sites://default/networks"
        assert resource.get_uri("default", "n1") == "sites://default/networks/n1"
