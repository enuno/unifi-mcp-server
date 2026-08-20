"""Unit tests for channel-planning MCP tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.channel_planning import list_ap_neighbors_v2, list_site_internal_ap_neighbors_v2
from src.utils.exceptions import ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "local"
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-key"  # pragma: allowlist secret
    return settings


def _client(get_return=None):
    client = MagicMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value=get_return if get_return is not None else {"data": []})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestListApNeighborsV2:
    @pytest.mark.asyncio
    async def test_uses_v2_endpoint_default_window_and_filters(self, mock_settings):
        rows = [
            {"mac": "00:00:5e:00:53:60", "channel": 1, "signal": -67, "lastSeen": 1000},
            {"mac": "00:00:5e:00:53:61", "channel": 11, "signal": -82, "lastSeen": 2000},
            {"mac": "00:00:5e:00:53:62", "channel": 6, "signal": -90, "lastSeen": 3000},
            {"mac": "not-a-mac", "channel": 6, "signal": -40},
            {"mac": "00:00:5e:00:53:63", "signal": -40},
        ]
        client = _client(get_return={"data": rows})

        with (
            patch("src.tools.channel_planning.UniFiClient", return_value=client),
            patch("src.tools.channel_planning.time.time", return_value=1_000_000.0),
        ):
            result = await list_ap_neighbors_v2(
                "default",
                "00:00:5e:00:53:41",
                mock_settings,
                min_rssi=-85,
                internal_ap_macs=["00:00:5e:00:53:60", "00:00:5e:00:53:61"],
            )

        assert (
            client.get.call_args[0][0]
            == "/proxy/network/v2/api/site/default/ap/00:00:5e:00:53:41/neighbors"
        )
        assert client.get.call_args[1]["params"] == {
            "start": 1_000_000_000 - 24 * 3600 * 1000,
            "end": 1_000_000_000,
        }
        assert [n["mac"] for n in result] == ["00:00:5e:00:53:60", "00:00:5e:00:53:61"]
        assert result[0]["ap_mac"] == "00:00:5e:00:53:41"
        assert result[0]["last_seen"] == 1000

    @pytest.mark.asyncio
    async def test_validates_window_and_rssi_range(self, mock_settings):
        with pytest.raises(ValidationError, match="end_ms must be greater"):
            await list_ap_neighbors_v2(
                "default",
                "00:00:5e:00:53:41",
                mock_settings,
                start_ms=2000,
                end_ms=2000,
            )

        with pytest.raises(ValidationError, match="min_rssi"):
            await list_ap_neighbors_v2(
                "default",
                "00:00:5e:00:53:41",
                mock_settings,
                min_rssi=-10,
            )

    @pytest.mark.asyncio
    async def test_rejects_invalid_ap_mac(self, mock_settings):
        with pytest.raises(ValidationError, match="Invalid MAC"):
            await list_ap_neighbors_v2("default", "invalid", mock_settings)


class TestListSiteInternalApNeighborsV2:
    @pytest.mark.asyncio
    async def test_builds_internal_graph_for_all_managed_aps(self, mock_settings):
        devices = {
            "data": [
                {"type": "uap", "mac": "00:00:5e:00:53:41"},
                {"type": "uap", "mac": "00:00:5e:00:53:42"},
                {"type": "usw", "mac": "00:00:5e:00:53:50"},
            ]
        }
        n1 = {
            "data": [
                {"mac": "00:00:5e:00:53:42", "channel": 1, "signal": -63, "lastSeen": 1000},
                {"mac": "00:00:5e:00:53:99", "channel": 6, "signal": -50, "lastSeen": 1000},
            ]
        }
        n2 = {
            "data": [
                {"mac": "00:00:5e:00:53:41", "channel": 11, "signal": -68, "lastSeen": 2000},
                {"mac": "00:00:5e:00:53:42", "channel": 11, "signal": -40, "lastSeen": 2000},
            ]
        }

        client = _client(get_return={"data": []})
        client.get = AsyncMock(side_effect=[devices, n1, n2])

        with patch("src.tools.channel_planning.UniFiClient", return_value=client):
            result = await list_site_internal_ap_neighbors_v2(
                "default",
                mock_settings,
                start_ms=100,
                end_ms=200,
                min_rssi=-85,
            )

        assert client.get.call_args_list[0][0][0] == "/ea/sites/default/devices"
        assert result["managed_ap_count"] == 2
        assert result["internal_neighbor_edge_count"] == 2
        assert all(
            edge["mac"] in {"00:00:5e:00:53:41", "00:00:5e:00:53:42"}
            for edge in result["internal_neighbor_edges"]
        )
        assert all(edge["mac"] != edge["ap_mac"] for edge in result["internal_neighbor_edges"])

    @pytest.mark.asyncio
    async def test_continues_when_one_ap_neighbor_call_fails(self, mock_settings):
        devices = {
            "data": [
                {"type": "uap", "mac": "00:00:5e:00:53:41"},
                {"type": "uap", "mac": "00:00:5e:00:53:42"},
            ]
        }
        n1 = {"data": [{"mac": "00:00:5e:00:53:42", "channel": 1, "signal": -63}]}

        client = _client(get_return={"data": []})
        client.get = AsyncMock(side_effect=[devices, n1, ValidationError("boom")])

        with patch("src.tools.channel_planning.UniFiClient", return_value=client):
            result = await list_site_internal_ap_neighbors_v2("default", mock_settings)

        assert result["internal_neighbor_edge_count"] == 1
        assert len(result["skipped_aps"]) == 1
