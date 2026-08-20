"""Unit tests for controller event/alarm/neighbor tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.events import (
    list_alarms,
    list_events,
    list_neighboring_aps,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "local"
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-key"  # pragma: allowlist secret
    return settings


def _client(get_return=None, post_return=None):
    client = MagicMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value=get_return if get_return is not None else {"data": []})
    client.post = AsyncMock(return_value=post_return if post_return is not None else {"data": []})
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


EVENTS = [
    {
        "_id": "507f191e810c19729de860ea",  # pragma: allowlist secret
        "key": "EVT_WU_Disconnected",
        "user": "00:00:5e:00:53:07",
        "ap": "00:00:5e:00:53:41",
        "time": 1735689600000,
        "msg": "User disconnected",
    },
    {
        "_id": "ev-2",
        "key": "EVT_AP_RestartedUnknown",
        "ap": "00:00:5e:00:53:41",
        "time": 1735689500000,
        "msg": "AP restarted",
    },
]


class TestListEvents:
    @pytest.mark.asyncio
    async def test_posts_window_and_returns_events(self, mock_settings):
        client = _client(post_return={"data": EVENTS})

        with patch("src.tools.events.UniFiClient", return_value=client):
            result = await list_events("default", mock_settings, hours=48, limit=100)

        url = client.post.call_args[0][0]
        assert url == "/ea/sites/default/stat/event"
        body = client.post.call_args[1]["json_data"]
        assert body == {"_limit": 100, "within": 48, "_sort": "-time"}
        assert len(result) == 2
        assert result[0]["key"] == "EVT_WU_Disconnected"

    @pytest.mark.asyncio
    async def test_event_type_filter_matches_key_substring(self, mock_settings):
        client = _client(post_return={"data": EVENTS})

        with patch("src.tools.events.UniFiClient", return_value=client):
            result = await list_events("default", mock_settings, event_type="restart")

        assert len(result) == 1
        assert result[0]["key"] == "EVT_AP_RestartedUnknown"

    @pytest.mark.asyncio
    async def test_rejects_bad_window_and_limit(self, mock_settings):
        with pytest.raises(ValidationError, match="hours"):
            await list_events("default", mock_settings, hours=0)
        with pytest.raises(ValidationError, match="limit"):
            await list_events("default", mock_settings, limit=0)


class TestListAlarms:
    @pytest.mark.asyncio
    async def test_unarchived_by_default(self, mock_settings):
        alarm = {"_id": "al-1", "key": "EVT_AP_Lost_Contact", "archived": False}
        client = _client(get_return={"data": [alarm]})

        with patch("src.tools.events.UniFiClient", return_value=client):
            result = await list_alarms("default", mock_settings)

        assert client.get.call_args[0][0] == "/ea/sites/default/stat/alarm?archived=false"
        assert result == [alarm]

    @pytest.mark.asyncio
    async def test_include_archived_drops_filter(self, mock_settings):
        client = _client(get_return={"data": []})

        with patch("src.tools.events.UniFiClient", return_value=client):
            await list_alarms("default", mock_settings, include_archived=True)

        assert client.get.call_args[0][0] == "/ea/sites/default/stat/alarm"


class TestListNeighboringAps:
    @pytest.mark.asyncio
    async def test_sorted_strongest_first_with_floor(self, mock_settings):
        neighbors = [
            {"bssid": "00:00:5e:00:53:60", "essid": "Neighbor-A", "channel": 6, "signal": -88},
            {"bssid": "00:00:5e:00:53:61", "essid": "Neighbor-B", "channel": 1, "signal": -62},
            {"bssid": "00:00:5e:00:53:62", "essid": "Neighbor-C", "channel": 11, "signal": -71},
        ]
        client = _client(get_return={"data": neighbors})

        with patch("src.tools.events.UniFiClient", return_value=client):
            result = await list_neighboring_aps("default", mock_settings, min_rssi=-85)

        assert client.get.call_args[0][0] == "/ea/sites/default/stat/rogueap"
        assert [n["essid"] for n in result] == ["Neighbor-B", "Neighbor-C"]


class TestV2Fallbacks:
    @pytest.mark.asyncio
    async def test_events_fall_back_to_v2_system_log(self, mock_settings):
        """A retired classic route sends the v2 body with an epoch-ms window."""
        client = _client()
        client.post = AsyncMock(
            side_effect=[ResourceNotFoundError("route", "stat/event"), {"data": EVENTS}]
        )

        with patch("src.tools.events.UniFiClient", return_value=client):
            result = await list_events("default", mock_settings, hours=6, limit=50)

        assert client.post.call_count == 2
        url = client.post.call_args_list[1][0][0]
        assert url == "/proxy/network/v2/api/site/default/system-log/all"
        body = client.post.call_args_list[1][1]["json_data"]
        assert body["pageNumber"] == 0
        assert body["pageSize"] == 50
        assert body["timestampTo"] - body["timestampFrom"] == 6 * 3600 * 1000
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_alarms_fall_back_to_the_v2_critical_tab(self, mock_settings):
        """A retired alarm route reads the v2 critical tab over a 7-day window."""
        alarm = {"id": "al-1", "key": "EVT_AP_Lost_Contact"}
        client = _client()
        client.get = AsyncMock(side_effect=ResourceNotFoundError("route", "stat/alarm"))
        client.post = AsyncMock(return_value={"data": [alarm]})

        with patch("src.tools.events.UniFiClient", return_value=client):
            result = await list_alarms("default", mock_settings)

        url = client.post.call_args[0][0]
        assert url == "/proxy/network/v2/api/site/default/system-log/critical"
        body = client.post.call_args[1]["json_data"]
        assert body["timestampTo"] - body["timestampFrom"] == 7 * 24 * 3600 * 1000
        assert result == [alarm]
