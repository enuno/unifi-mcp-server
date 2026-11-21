"""Unit tests for controller event/alarm/neighbor tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.events import (
    list_alarms,
    list_client_connection_events,
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


# =============================================================================
# list_client_connection_events Tests (coverage item 23)
# =============================================================================


def _log_row(key, mac="00:11:22:33:44:55", type_override=None, **over):
    """One v2 system-log row shaped like the live controller's."""
    connected = key.startswith("CLIENT_CONNECTED")
    row = {
        "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
        "timestamp": 1760000000000,
        "type": "CLIENT_CONNECTION",
        "category": "CLIENT_DEVICES",
        "key": key,
        "event": "CLIENT_CONNECTED_WIRELESS" if connected else "CLIENT_DISCONNECTED_WIRELESS",
        "severity": "LOW",
        "status": "NEW",
        "target": "CLIENT",
        "message_raw": "Client connected",
        "title_raw": "Client Connected",
        "parameters": {
            "CLIENT": {
                "id": mac,
                "name": "Phone",
                "hostname": "phone",
                "ip": "10.2.2.10",
            },
            "DEVICE": {
                "id": "8c:30:66:9c:9b:46",
                "name": "AP-Hallway",
                "model": "UX7",
                "version": "5.2.15",
            },
            "WLAN": {"name": "Home"},
            "NETWORK": {"name": "LAN"},
            "CHANNEL": {"name": "36"},
            "SIGNAL_STRENGTH": {"name": "-52 dBm"},
            "AUTH_METHOD": {"name": "WPA2"},
            "DATA_UP": {"name": "190957"},
            "DATA_DOWN": {"name": "621203"},
            "DURATION": {"name": "0"},
        },
    }
    if type_override:
        row["type"] = type_override
    row.update(over)
    return row


def _log_client(pages):
    """Mocked UniFiClient returning a fixed page per call."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.post = AsyncMock(side_effect=pages)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


@pytest.mark.asyncio
async def test_client_connection_events_filters_to_client_connection(mock_settings):
    rows = [
        _log_row("CLIENT_CONNECTED_WIRELESS_2"),
        _log_row("CLIENT_DISCONNECTED_WIRELESS_2"),
        {"id": "z", "type": "ADMIN_ACCESS", "category": "AUDIT", "key": "ADMIN_ACCESS"},
    ]
    mock_client = _log_client([{"data": rows}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(site_id="default", settings=mock_settings)

    assert result["count"] == 2
    assert all(e["type"] == "CLIENT_CONNECTION" for e in result["events"])
    assert {e["event"] for e in result["events"]} == {"connected", "disconnected"}


@pytest.mark.asyncio
async def test_client_connection_events_normalizes_the_row(mock_settings):
    mock_client = _log_client([{"data": [_log_row("CLIENT_CONNECTED_WIRELESS_2")]}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(site_id="default", settings=mock_settings)
    ev = result["events"][0]
    assert ev["event"] == "connected"
    assert ev["client_mac"] == "00:11:22:33:44:55"
    assert ev["client_name"] == "Phone"
    assert ev["client_ip"] == "10.2.2.10"
    assert ev["device_model"] == "UX7"
    assert ev["wlan"] == "Home"
    assert ev["channel"] == "36"
    assert ev["auth_method"] == "WPA2"


@pytest.mark.asyncio
async def test_client_connection_events_filters_by_direction(mock_settings):
    rows = [
        _log_row("CLIENT_CONNECTED_WIRELESS_2"),
        _log_row("CLIENT_DISCONNECTED_WIRELESS_2"),
    ]
    mock_client = _log_client([{"data": rows}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(
            site_id="default", settings=mock_settings, event_type="connected"
        )
    assert result["count"] == 1
    assert result["events"][0]["event"] == "connected"


@pytest.mark.asyncio
async def test_client_connection_events_filters_by_client_mac(mock_settings):
    rows = [
        _log_row("CLIENT_CONNECTED_WIRELESS_2", mac="00:11:22:33:44:55"),
        _log_row("CLIENT_CONNECTED_WIRELESS_2", mac="00:11:22:33:44:66"),
    ]
    mock_client = _log_client([{"data": rows}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(
            site_id="default",
            settings=mock_settings,
            client_mac="00:11:22:33:44:66",
        )
    assert result["count"] == 1
    assert result["events"][0]["client_mac"] == "00:11:22:33:44:66"


@pytest.mark.asyncio
async def test_client_connection_events_does_not_send_a_server_side_filter(mock_settings):
    """The console ignores its own filter object, so we must not send one."""
    mock_client = _log_client([{"data": [_log_row("CLIENT_CONNECTED_WIRELESS_2")]}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        await list_client_connection_events(
            site_id="default", settings=mock_settings, event_type="connected"
        )
    body = mock_client.post.call_args[1]["json_data"]
    assert "filter" not in body
    assert body["pageNumber"] == 0
    assert body["pageSize"] == 500


@pytest.mark.asyncio
async def test_client_connection_events_pages_until_enough(mock_settings):
    page1 = [_log_row("CLIENT_CONNECTED_WIRELESS_2") for _ in range(50)]
    page2 = [_log_row("CLIENT_CONNECTED_WIRELESS_2") for _ in range(50)]
    mock_client = _log_client([{"data": page1}, {"data": page2}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(
            site_id="default", settings=mock_settings, page_size=50, limit=75
        )
    assert result["count"] == 75
    assert result["pages_fetched"] == 2
    assert result["scanned_rows"] == 100
    assert result["truncated"] is True
    assert mock_client.post.call_count == 2
    assert mock_client.post.call_args_list[1][1]["json_data"]["pageNumber"] == 1


@pytest.mark.asyncio
async def test_client_connection_events_stops_on_a_short_page(mock_settings):
    mock_client = _log_client([{"data": [_log_row("CLIENT_CONNECTED_WIRELESS_2")]}, {"data": []}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(
            site_id="default", settings=mock_settings, page_size=100, limit=10
        )
    assert result["count"] == 1
    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_client_connection_events_rejects_bad_arguments(mock_settings):
    with pytest.raises(ValueError, match="event_type must be one of"):
        await list_client_connection_events(
            site_id="default", settings=mock_settings, event_type="sideways"
        )
    with pytest.raises(ValueError, match="hours must be between"):
        await list_client_connection_events(site_id="default", settings=mock_settings, hours=0)
    with pytest.raises(ValueError, match="limit must be between"):
        await list_client_connection_events(site_id="default", settings=mock_settings, limit=0)
    with pytest.raises(ValueError, match="page_size must be between"):
        await list_client_connection_events(site_id="default", settings=mock_settings, page_size=0)


@pytest.mark.asyncio
async def test_client_connection_events_returns_a_note(mock_settings):
    """The note records the two console behaviours a caller needs to know."""
    mock_client = _log_client([{"data": []}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(site_id="default", settings=mock_settings)
    assert "stat/alarm" in result["note"]
    assert "ignores its own filter" in result["note"]


@pytest.mark.asyncio
async def test_client_connection_events_skips_a_non_dict_row(mock_settings):
    """A malformed row is skipped, not crashed on."""
    mock_client = _log_client([{"data": ["not-a-dict", _log_row("CLIENT_CONNECTED_WIRELESS_2")]}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(site_id="default", settings=mock_settings)
    assert result["count"] == 1
    assert result["scanned_rows"] == 2


@pytest.mark.asyncio
async def test_client_connection_events_direction_falls_back_to_the_event_name(mock_settings):
    """A key with neither prefix falls back to the event name."""
    row = _log_row("CLIENT_ROAMED_WIRELESS_2")
    row["event"] = "CLIENT_DISCONNECTED_WIRELESS"
    mock_client = _log_client([{"data": [row]}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(site_id="default", settings=mock_settings)
    assert result["count"] == 1
    assert result["events"][0]["event"] == "disconnected"


@pytest.mark.asyncio
async def test_client_connection_events_marks_a_page_budget_exhaustion_as_truncated(
    mock_settings,
):
    """Twenty full non-matching pages means the window may hold more."""
    full = [_log_row("ADMIN_ACCESS", type_override="ADMIN_ACCESS") for _ in range(50)]
    mock_client = _log_client([{"data": full} for _ in range(20)])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(
            site_id="default", settings=mock_settings, page_size=50, limit=100
        )
    assert result["count"] == 0
    assert result["pages_fetched"] == 20
    assert result["truncated"] is True


@pytest.mark.asyncio
async def test_client_connection_events_is_not_truncated_when_the_window_ends(mock_settings):
    """Exactly `limit` events on a short final page means nothing was cut off."""
    rows = [_log_row("CLIENT_CONNECTED_WIRELESS_2") for _ in range(3)]
    mock_client = _log_client([{"data": rows}])
    with patch("src.tools.events.UniFiClient", return_value=mock_client):
        result = await list_client_connection_events(
            site_id="default", settings=mock_settings, page_size=50, limit=3
        )
    assert result["count"] == 3
    assert result["truncated"] is False
