"""Tests for the Matter and Thread inventory tools."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import APIType, Settings
from src.models.matter import MatterNode, ThreadNetwork
from src.tools.matter import list_matter_nodes, list_matter_thread_clients, list_thread_networks
from src.utils.exceptions import APIError, ResourceNotFoundError, ValidationError


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.0.2.10")
    return Settings()


def _client(get: AsyncMock) -> MagicMock:
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.is_authenticated = True
    client.authenticate = AsyncMock()
    client._site_uuid_to_name = {}
    client.get = get
    return client


def _patch(get: AsyncMock) -> Any:
    return patch("src.tools.matter.UniFiClient", return_value=_client(get))


def _awaited_path(get: AsyncMock) -> str:
    """Return the endpoint the mocked client was asked for."""
    assert get.await_args is not None
    return str(get.await_args[0][0])


# --------------------------------------------------------------------------- #
# Thread networks                                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_list_thread_networks_shapes_the_record(settings: Settings) -> None:
    get = AsyncMock(
        return_value=[
            {
                "networkName": "Home Thread",
                "extendedPanId": "DEAD0000BEEF0000",
                "channel": 15,
                "controller": "Home Assistant",
                "threadVersion": "1.3.0",
                "deviceCount": 1,
                "fabrics": [{"fabricId": "1"}, {"fabricId": "2"}],
                "borderRouters": [
                    {
                        "name": "Border Router",
                        "vendorName": "Ubiquiti",
                        "routingRole": "leader",
                        "online": True,
                    }
                ],
            }
        ]
    )
    with _patch(get):
        result = await list_thread_networks("default", settings)

    assert result["supported"] is True
    assert result["count"] == 1
    network = result["thread_networks"][0]
    assert network["network_name"] == "Home Thread"
    assert network["extended_pan_id"] == "DEAD0000BEEF0000"
    assert network["channel"] == 15
    assert network["fabric_count"] == 2
    assert network["border_routers"][0]["routing_role"] == "leader"
    assert _awaited_path(get).endswith("/v2/api/site/default/thread-networks")


@pytest.mark.asyncio
async def test_thread_network_never_surfaces_border_router_internals() -> None:
    """A border router's identification internals must not reach the result."""
    network = ThreadNetwork.from_api(
        {
            "networkName": "Home Thread",
            "fabrics": [{"fabricId": "1"}],
            "borderRouters": [
                {
                    "name": "Border Router",
                    "fingerprint": "must-not-appear",
                    "host": "198.51.100.7",
                    "domainName": "thread.internal",
                    "stateBitmap": 7,
                    "sequenceNumber": 12,
                    "backboneRouterPort": 61631,
                }
            ],
        }
    )
    dumped = network.model_dump()
    router = dumped["border_routers"][0]
    for leaked in (
        "fingerprint",
        "host",
        "domain_name",
        "domainName",
        "state_bitmap",
        "sequence_number",
        "backbone_router_port",
    ):
        assert leaked not in router
    # Fabric identifiers are reduced to a count, never passed through.
    assert dumped["fabric_count"] == 1
    assert "fabrics" not in dumped


@pytest.mark.asyncio
async def test_list_thread_networks_reports_unsupported_on_404(settings: Settings) -> None:
    """A pre-Network-11 controller 404s; that is 'unsupported', not an error."""
    get = AsyncMock(side_effect=ResourceNotFoundError("resource", "/thread-networks"))
    with _patch(get):
        result = await list_thread_networks("default", settings)

    assert result == {"supported": False, "count": 0, "thread_networks": []}


@pytest.mark.asyncio
async def test_list_thread_networks_propagates_a_real_failure(settings: Settings) -> None:
    """A 500/401/429 must not be reported as an unsupported controller."""
    get = AsyncMock(side_effect=APIError("controller unavailable"))
    with _patch(get), pytest.raises(APIError):
        await list_thread_networks("default", settings)


@pytest.mark.asyncio
async def test_list_thread_networks_handles_an_empty_site(settings: Settings) -> None:
    get = AsyncMock(return_value=[])
    with _patch(get):
        result = await list_thread_networks("default", settings)
    assert result == {"supported": True, "count": 0, "thread_networks": []}


@pytest.mark.asyncio
async def test_list_thread_networks_tolerates_an_unexpected_shape(settings: Settings) -> None:
    """A scalar or unkeyed body yields no records rather than raising."""
    get = AsyncMock(return_value="not a collection")
    with _patch(get):
        result = await list_thread_networks("default", settings)
    assert result == {"supported": True, "count": 0, "thread_networks": []}


@pytest.mark.asyncio
async def test_an_unauthenticated_client_is_authenticated_first(settings: Settings) -> None:
    """A fresh client logs in before the read, rather than sending it blind."""
    get = AsyncMock(return_value=[])
    client = _client(get)
    client.is_authenticated = False
    with patch("src.tools.matter.UniFiClient", return_value=client):
        await list_matter_nodes("default", settings)
    client.authenticate.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_thread_networks_ignores_malformed_entries(settings: Settings) -> None:
    get = AsyncMock(return_value=["not-a-dict", None, {"networkName": "Only Real One"}])
    with _patch(get):
        result = await list_thread_networks("default", settings)
    assert result["count"] == 1
    assert result["thread_networks"][0]["network_name"] == "Only Real One"


# --------------------------------------------------------------------------- #
# Matter nodes                                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_list_matter_nodes_shapes_the_record(settings: Settings) -> None:
    get = AsyncMock(
        return_value={
            "data": [
                {
                    "nodeId": 42,
                    "name": "Kitchen Plug",
                    "status": "COMMISSIONED",
                    "online": True,
                    "deviceTypeName": "On/Off Plug-in Unit",
                    "vendorName": "Acme",
                    "productName": "Smart Plug",
                    "softwareVersionString": "1.4.2",
                    "clientId": "client-abc",
                    "lastOnlineAt": 1764000000,
                }
            ]
        }
    )
    with _patch(get):
        result = await list_matter_nodes("default", settings)

    assert result["supported"] is True
    node = result["matter_nodes"][0]
    assert node["node_id"] == 42
    assert node["status"] == "COMMISSIONED"
    # client_id is republished under a name that says what it is for.
    assert node["thread_client_id"] == "client-abc"
    assert _awaited_path(get).endswith("/v2/api/site/default/matter/nodes")


@pytest.mark.asyncio
async def test_matter_node_never_surfaces_the_setup_code() -> None:
    """The Matter pairing code is a credential and must never be returned."""
    node = MatterNode.from_api(
        {
            "nodeId": 7,
            "name": "Sensor",
            "setupCode": "12345678901",
            "setup_code": "12345678901",
            "fingerprint": "must-not-appear",
        }
    )
    dumped = node.model_dump()
    assert "setup_code" not in dumped
    assert "setupCode" not in dumped
    assert "fingerprint" not in dumped
    assert "12345678901" not in str(dumped)


@pytest.mark.asyncio
async def test_list_matter_nodes_reports_unsupported_on_404(settings: Settings) -> None:
    get = AsyncMock(side_effect=ResourceNotFoundError("resource", "/matter/nodes"))
    with _patch(get):
        result = await list_matter_nodes("default", settings)
    assert result == {"supported": False, "count": 0, "matter_nodes": []}


@pytest.mark.asyncio
async def test_list_matter_nodes_keeps_an_unknown_state(settings: Settings) -> None:
    """A newer controller's unseen state passes through, it does not fail."""
    get = AsyncMock(return_value=[{"nodeId": 1, "status": "SOME_NEW_STATE"}])
    with _patch(get):
        result = await list_matter_nodes("default", settings)
    assert result["matter_nodes"][0]["status"] == "SOME_NEW_STATE"


# --------------------------------------------------------------------------- #
# Matter/Thread client inventory                                              #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_list_matter_thread_clients_filters_by_type(settings: Settings) -> None:
    get = AsyncMock(
        return_value={
            "data": [
                {"id": "a", "type": "WIRELESS"},
                {"id": "b", "type": "MATTER_THREAD", "client_id": "client-abc"},
                {"id": "c", "type": "WIRED"},
            ]
        }
    )
    with _patch(get):
        result = await list_matter_thread_clients("default", settings)

    assert result["count"] == 1
    assert result["clients"][0]["client_id"] == "client-abc"
    assert _awaited_path(get).endswith("/v2/api/site/default/clients/active")


@pytest.mark.asyncio
async def test_list_matter_thread_clients_empty_is_not_unsupported(settings: Settings) -> None:
    """clients/active predates Network 11, so no matches means no devices."""
    get = AsyncMock(return_value={"data": [{"id": "a", "type": "WIRELESS"}]})
    with _patch(get):
        result = await list_matter_thread_clients("default", settings)
    assert result == {"supported": True, "count": 0, "clients": []}


# --------------------------------------------------------------------------- #
# Guards                                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "tool",
    [list_thread_networks, list_matter_nodes, list_matter_thread_clients],
)
@pytest.mark.asyncio
async def test_cloud_mode_is_refused(
    tool: Any, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "api_type", APIType.CLOUD_V1)
    with pytest.raises(NotImplementedError, match="local"):
        await tool("default", settings)


@pytest.mark.parametrize(
    "tool",
    [list_thread_networks, list_matter_nodes, list_matter_thread_clients],
)
@pytest.mark.asyncio
async def test_a_malformed_site_is_refused(tool: Any, settings: Settings) -> None:
    get = AsyncMock()
    with _patch(get), pytest.raises(ValidationError):
        await tool("", settings)
    get.assert_not_awaited()
