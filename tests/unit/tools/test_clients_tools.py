"""Unit tests for src/tools/clients.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.clients import (
    get_client_details,
    get_client_statistics,
    list_active_clients,
    search_clients,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "cloud-ea"
    settings.base_url = "https://api.ui.com"
    settings.api_key = "test-key"
    return settings


def create_mock_client(get_responses=None):
    mock_client = AsyncMock()
    if get_responses:
        mock_client.get = AsyncMock(side_effect=get_responses)
    else:
        mock_client.get = AsyncMock(return_value={"data": []})
    mock_client.authenticate = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def make_client(
    mac="00:11:22:33:44:55",
    ip="192.168.2.100",
    hostname="test-client",
    name=None,
    is_wired=False,
):
    return {
        "mac": mac,
        "ip": ip,
        "hostname": hostname,
        "name": name or hostname,
        "is_wired": is_wired,
        "tx_bytes": 1000000,
        "rx_bytes": 2000000,
        "tx_packets": 1000,
        "rx_packets": 2000,
        "tx_rate": 100000,
        "rx_rate": 200000,
        "signal": -65,
        "rssi": 35,
        "noise": -95,
        "uptime": 3600,
    }


def make_wired_client(mac="00:00:5e:00:53:02", tx_bytes=5000000, rx_bytes=9000000):
    """A wired client as the sta route reports it: counters under wired- keys."""
    return {
        "mac": mac,
        "ip": "192.168.2.50",
        "hostname": "wired-server",
        "is_wired": True,
        "wired-tx_bytes": tx_bytes,
        "wired-rx_bytes": rx_bytes,
        "wired-tx_packets": 4000,
        "wired-rx_packets": 8000,
        "uptime": 7200,
    }


class TestWiredClientCounters:
    """Wired clients report counters ONLY under the wired- keys.

    Regression: every wired client reported null/zero traffic because the
    tools and the Client model read the plain tx_bytes/rx_bytes keys, which
    the sta route omits for wired clients. Observed live: a hypervisor
    moving gigabytes reported tx_bytes 0.
    """

    @pytest.mark.asyncio
    async def test_get_client_statistics_reads_wired_keys(self, mock_settings):
        mac = "00:00:5e:00:53:02"
        response = {"data": [make_wired_client(mac=mac)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_client_statistics("site-1", mac, mock_settings)

            assert result["tx_bytes"] == 5000000
            assert result["rx_bytes"] == 9000000
            assert result["tx_packets"] == 4000
            assert result["is_wired"] is True

    @pytest.mark.asyncio
    async def test_list_active_clients_reads_wired_keys(self, mock_settings):
        response = {"data": [make_wired_client()]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings)

            assert result[0]["tx_bytes"] == 5000000
            assert result[0]["rx_bytes"] == 9000000

    @pytest.mark.asyncio
    async def test_wireless_counters_unaffected(self, mock_settings):
        """A wireless client's plain keys keep winning."""
        response = {"data": [make_client()]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings)

            assert result[0]["tx_bytes"] == 1000000
            assert result[0]["rx_bytes"] == 2000000

    @pytest.mark.asyncio
    async def test_wireless_zero_is_not_replaced_by_stray_wired_keys(self, mock_settings):
        """A wireless client's legitimate zero counter must stay zero.

        The wired- fallback is gated on is_wired, so even a record that
        somehow carries wired- keys cannot overwrite a wireless zero.
        """
        mac = "00:00:5e:00:53:07"
        record = {
            **make_client(mac=mac),
            "tx_bytes": 0,
            "rx_bytes": 0,
            "wired-tx_bytes": 123456,
            "wired-rx_bytes": 654321,
        }
        response = {"data": [record]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            stats = await get_client_statistics("site-1", mac, mock_settings)
            assert stats["tx_bytes"] == 0
            assert stats["rx_bytes"] == 0

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            listed = await list_active_clients("site-1", mock_settings)
            assert listed[0]["tx_bytes"] == 0
            assert listed[0]["rx_bytes"] == 0


class TestGetClientDetails:
    @pytest.mark.asyncio
    async def test_get_client_details_found_in_active(self, mock_settings):
        mac = "00:11:22:33:44:55"
        active_response = {"data": [make_client(mac=mac)]}
        alluser_response = {"data": []}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await get_client_details("site-1", mac, mock_settings)

            assert result["mac"] == mac

    @pytest.mark.asyncio
    async def test_get_client_details_found_in_alluser(self, mock_settings):
        mac = "aa:bb:cc:dd:ee:ff"
        active_response = {"data": []}
        alluser_response = {"data": [make_client(mac=mac)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await get_client_details("site-1", mac, mock_settings)

            assert result["mac"] == mac

    @pytest.mark.asyncio
    async def test_get_client_details_list_response(self, mock_settings):
        mac = "00:11:22:33:44:55"
        active_response = [make_client(mac=mac)]

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response])

            result = await get_client_details("site-1", mac, mock_settings)

            assert result["mac"] == mac

    @pytest.mark.asyncio
    async def test_get_client_details_not_found(self, mock_settings):
        active_response = {"data": [make_client(mac="00:00:00:00:00:00")]}
        alluser_response = {"data": []}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            with pytest.raises(ResourceNotFoundError):
                await get_client_details("site-1", "ff:ff:ff:ff:ff:ff", mock_settings)

    @pytest.mark.asyncio
    async def test_get_client_details_invalid_site_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await get_client_details("", "00:11:22:33:44:55", mock_settings)

    @pytest.mark.asyncio
    async def test_get_client_details_invalid_mac(self, mock_settings):
        with pytest.raises(ValidationError):
            await get_client_details("site-1", "invalid-mac", mock_settings)

    @pytest.mark.asyncio
    async def test_get_client_details_mac_normalization(self, mock_settings):
        mac = "00:11:22:33:44:55"
        active_response = {"data": [make_client(mac=mac)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response])

            result = await get_client_details("site-1", "00-11-22-33-44-55", mock_settings)

            assert result["mac"] == mac


class TestGetClientStatistics:
    @pytest.mark.asyncio
    async def test_get_client_statistics_success(self, mock_settings):
        mac = "00:11:22:33:44:55"
        response = {"data": [make_client(mac=mac)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_client_statistics("site-1", mac, mock_settings)

            assert result["mac"] == mac
            assert result["tx_bytes"] == 1000000
            assert result["rx_bytes"] == 2000000
            assert result["tx_packets"] == 1000
            assert result["rx_packets"] == 2000
            assert result["signal"] == -65
            assert result["is_wired"] is False

    @pytest.mark.asyncio
    async def test_get_client_statistics_list_response(self, mock_settings):
        mac = "aa:bb:cc:dd:ee:ff"
        response = [make_client(mac=mac)]

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_client_statistics("site-1", mac, mock_settings)

            assert result["mac"] == mac

    @pytest.mark.asyncio
    async def test_get_client_statistics_not_found(self, mock_settings):
        response = {"data": [make_client(mac="00:00:00:00:00:00")]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            with pytest.raises(ResourceNotFoundError):
                await get_client_statistics("site-1", "ff:ff:ff:ff:ff:ff", mock_settings)

    @pytest.mark.asyncio
    async def test_get_client_statistics_minimal_data(self, mock_settings):
        mac = "00:11:22:33:44:55"
        minimal_client = {"mac": mac}
        response = {"data": [minimal_client]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_client_statistics("site-1", mac, mock_settings)

            assert result["mac"] == mac
            assert result["tx_bytes"] == 0
            assert result["rx_bytes"] == 0
            assert result["uptime"] == 0
            assert result["is_wired"] is False


class TestListActiveClients:
    @pytest.mark.asyncio
    async def test_list_active_clients_success(self, mock_settings):
        response = {
            "data": [
                make_client(mac="00:11:22:33:44:55"),
                make_client(mac="aa:bb:cc:dd:ee:ff"),
            ]
        }

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings)

            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_active_clients_list_response(self, mock_settings):
        response = [make_client(mac="00:11:22:33:44:55")]

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_active_clients_with_limit(self, mock_settings):
        response = {"data": [make_client(mac=f"00:00:00:00:00:{i:02x}") for i in range(10)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings, limit=5)

            assert len(result) == 5

    @pytest.mark.asyncio
    async def test_list_active_clients_with_offset(self, mock_settings):
        response = {"data": [make_client(mac=f"00:00:00:00:00:{i:02x}") for i in range(10)]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings, offset=5, limit=3)

            assert len(result) == 3
            assert result[0]["mac"] == "00:00:00:00:00:05"

    @pytest.mark.asyncio
    async def test_list_active_clients_empty(self, mock_settings):
        response = {"data": []}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await list_active_clients("site-1", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_active_clients_invalid_site_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await list_active_clients("", mock_settings)


class TestSearchClients:
    @pytest.mark.asyncio
    async def test_search_clients_by_mac(self, mock_settings):
        active_response = {"data": []}
        alluser_response = {
            "data": [
                make_client(mac="00:11:22:33:44:55"),
                make_client(mac="aa:bb:cc:dd:ee:ff"),
            ]
        }

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await search_clients("site-1", "00:11", mock_settings)

            assert len(result) == 1
            assert result[0]["mac"] == "00:11:22:33:44:55"

    @pytest.mark.asyncio
    async def test_search_clients_by_ip(self, mock_settings):
        # Active clients have current IP addresses
        active_response = {
            "data": [
                make_client(mac="00:11:22:33:44:55", ip="192.168.2.100"),
                make_client(mac="aa:bb:cc:dd:ee:ff", ip="192.168.2.200"),
            ]
        }
        # Historical clients may not have current IPs
        alluser_response = {"data": []}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await search_clients("site-1", "192.168.2", mock_settings)

            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_clients_by_hostname(self, mock_settings):
        active_response = {"data": []}
        alluser_response = {
            "data": [
                make_client(mac="00:11:22:33:44:55", hostname="office-laptop"),
                make_client(mac="aa:bb:cc:dd:ee:ff", hostname="home-phone"),
            ]
        }

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await search_clients("site-1", "office", mock_settings)

            assert len(result) == 1
            assert result[0]["hostname"] == "office-laptop"

    @pytest.mark.asyncio
    async def test_search_clients_by_name(self, mock_settings):
        active_response = {"data": []}
        alluser_response = {"data": [make_client(name="John's iPhone")]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await search_clients("site-1", "john", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_clients_case_insensitive(self, mock_settings):
        active_response = {"data": []}
        alluser_response = {"data": [make_client(hostname="Office-PC")]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await search_clients("site-1", "OFFICE", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_clients_with_pagination(self, mock_settings):
        active_response = {"data": []}
        alluser_response = {
            "data": [
                make_client(mac=f"00:00:00:00:00:{i:02x}", hostname=f"client-{i}")
                for i in range(10)
            ]
        }

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await search_clients("site-1", "client", mock_settings, limit=3, offset=2)

            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_search_clients_no_match(self, mock_settings):
        active_response = {"data": []}
        alluser_response = {"data": [make_client(hostname="office-pc")]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await search_clients("site-1", "nonexistent", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_search_clients_list_response(self, mock_settings):
        active_response = [make_client(hostname="test-client")]
        alluser_response = []

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await search_clients("site-1", "test", mock_settings)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_clients_ip_with_none_value(self, mock_settings):
        """Test that None IP values don't cause crashes."""
        active_response = {
            "data": [
                make_client(mac="00:11:22:33:44:55", ip="192.168.2.100"),
            ]
        }
        # Historical client with None IP
        alluser_response = {
            "data": [{"mac": "aa:bb:cc:dd:ee:ff", "hostname": "old-client", "ip": None}]
        }

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            # Should not crash when searching by IP
            result = await search_clients("site-1", "192.168.2", mock_settings)

            assert len(result) == 1
            assert result[0]["mac"] == "00:11:22:33:44:55"

    @pytest.mark.asyncio
    async def test_search_clients_deduplication_active_priority(self, mock_settings):
        """Test that active client data takes priority over historical data."""
        mac = "00:11:22:33:44:55"
        # Historical data with old IP
        alluser_response = {
            "data": [make_client(mac=mac, ip="192.168.2.50", hostname="old-hostname")]
        }
        # Active data with current IP (should override historical)
        active_response = {
            "data": [make_client(mac=mac, ip="192.168.2.100", hostname="current-hostname")]
        }

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await search_clients("site-1", "192.168.2.100", mock_settings)

            assert len(result) == 1
            assert result[0]["mac"] == mac
            assert result[0]["ip"] == "192.168.2.100"
            assert result[0]["hostname"] == "current-hostname"

    @pytest.mark.asyncio
    async def test_search_clients_historical_only_by_mac(self, mock_settings):
        """Test searching historical clients by MAC when not active."""
        mac = "aa:bb:cc:dd:ee:ff"
        active_response = {"data": []}
        alluser_response = {"data": [make_client(mac=mac, ip=None, hostname="offline-device")]}

        with patch("src.tools.clients.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([active_response, alluser_response])

            result = await search_clients("site-1", mac, mock_settings)

            assert len(result) == 1
            assert result[0]["mac"] == mac


class TestClientRfHealth:
    @pytest.mark.asyncio
    async def test_computes_retry_pct_and_sorts_worst_first(self, mock_settings):
        from src.tools.clients import list_client_rf_health

        sta = [
            {
                "mac": "00:00:5e:00:53:01",
                "name": "quiet",
                "radio": "na",
                "tx_packets": 900,
                "tx_retries": 100,
                "signal": -55,
            },
            {
                "mac": "00:00:5e:00:53:02",
                "name": "struggler",
                "radio": "ng",
                "tx_packets": 600,
                "tx_retries": 400,
                "signal": -78,
            },
            {
                "mac": "00:00:5e:00:53:03",
                "name": "wired-box",
                "is_wired": True,
                "tx_packets": 5,
                "tx_retries": 0,
            },
        ]
        client = MagicMock()
        client.authenticate = AsyncMock()
        client.get = AsyncMock(return_value={"data": sta})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.clients.UniFiClient", return_value=client):
            result = await list_client_rf_health("default", mock_settings)

        assert [r["name"] for r in result] == ["struggler", "quiet"]
        assert result[0]["tx_retry_pct"] == 40.0
        assert result[1]["tx_retry_pct"] == 10.0

    @pytest.mark.asyncio
    async def test_min_retry_pct_floor(self, mock_settings):
        from src.tools.clients import list_client_rf_health

        sta = [
            {"mac": "00:00:5e:00:53:01", "radio": "na", "tx_packets": 990, "tx_retries": 10},
            {"mac": "00:00:5e:00:53:02", "radio": "ng", "tx_packets": 800, "tx_retries": 200},
        ]
        client = MagicMock()
        client.authenticate = AsyncMock()
        client.get = AsyncMock(return_value={"data": sta})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.clients.UniFiClient", return_value=client):
            result = await list_client_rf_health("default", mock_settings, min_retry_pct=5)

        assert len(result) == 1
        assert result[0]["tx_retry_pct"] == 20.0

    @pytest.mark.asyncio
    async def test_zero_packets_yields_null_pct(self, mock_settings):
        from src.tools.clients import list_client_rf_health

        sta = [{"mac": "00:00:5e:00:53:01", "radio": "na", "tx_packets": 0, "tx_retries": 0}]
        client = MagicMock()
        client.authenticate = AsyncMock()
        client.get = AsyncMock(return_value={"data": sta})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.clients.UniFiClient", return_value=client):
            result = await list_client_rf_health("default", mock_settings)

        assert result[0]["tx_retry_pct"] is None
