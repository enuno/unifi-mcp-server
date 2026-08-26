"""Unit tests for diagnostics tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.diagnostics import (
    get_historical_stats,
    get_network_references,
    get_spectrum_scan,
    get_speed_test_history,
    get_speed_test_status,
    list_spectrum_interference,
    run_speed_test,
    start_spectrum_scan,
)
from src.utils.exceptions import ValidationError


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "cloud-ea"
    settings.base_url = "https://api.ui.com"
    settings.api_key = "test-key"
    return settings


def create_mock_client(get_responses=None):
    """Create a mock UniFiClient with configurable GET responses."""
    mock_client = AsyncMock()
    if get_responses:
        mock_client.get = AsyncMock(side_effect=get_responses)
    else:
        mock_client.get = AsyncMock(return_value={"data": []})
    mock_client.post = AsyncMock(return_value={})
    mock_client.authenticate = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestGetNetworkReferences:
    @pytest.mark.asyncio
    async def test_get_network_references_success(self, mock_settings):
        """Test successful retrieval of network references."""
        response = {
            "data": {
                "referenceResources": [
                    {
                        "id": "ref-1",
                        "name": "Main WiFi",
                        "type": "wifi",
                        "resource_type": "broadcast",
                    },
                    {
                        "id": "ref-2",
                        "name": "Port Profile 1",
                        "type": "port_profile",
                        "resource_type": "switching",
                    },
                ]
            }
        }

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_network_references("site-1", "net-123", mock_settings)

            assert isinstance(result, dict)
            assert "references" in result
            assert len(result["references"]) == 2
            assert result["references"][0]["name"] == "Main WiFi"
            assert result["references"][1]["type"] == "port_profile"
            assert result["network_id"] == "net-123"

    @pytest.mark.asyncio
    async def test_get_network_references_empty(self, mock_settings):
        """Test network references with empty response."""
        response = {"data": {"referenceResources": []}}

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_network_references("site-1", "net-123", mock_settings)

            assert result["references"] == []
            assert result["network_id"] == "net-123"

    @pytest.mark.asyncio
    async def test_get_network_references_invalid_site_id(self, mock_settings):
        """Test validation error for empty site_id."""
        with pytest.raises(ValidationError):
            await get_network_references("", "net-123", mock_settings)


class TestRunSpeedTest:
    @pytest.mark.asyncio
    async def test_run_speed_test_success(self, mock_settings):
        """Test successful speed test initiation."""
        response = {"data": {"status": "started", "test_id": "st-123"}}

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client()
            mock_client_class.return_value.post = AsyncMock(return_value=response)

            result = await run_speed_test("site-1", mock_settings, confirm=True)

            assert isinstance(result, dict)
            assert result["status"] == "started"
            assert result["test_id"] == "st-123"
            assert result["site_id"] == "site-1"

    @pytest.mark.asyncio
    async def test_run_speed_test_invalid_site_id(self, mock_settings):
        """Test validation error for empty site_id."""
        with pytest.raises(ValidationError):
            await run_speed_test("", mock_settings)


class TestGetSpeedTestStatus:
    """Status lives on the gateway's stat/device record.

    The record carries a ``speedtest-status`` object with the last result,
    the outcome string on ``uplink.speedtest_status``, and a
    ``speedtest-pending-interfaces`` list that is non-empty while a test
    runs. The ``cmd/devmgr/speedtest-status`` resource the old code GETed
    does not exist on any controller.
    """

    @staticmethod
    def _gateway(pending=None, **status_overrides):
        status = {
            "latency": 12,
            "rundate": 1735689600,
            "runtime": 14,
            "server": {"cc": "US", "city": "Anytown", "provider": "Example ISP"},
            "status_download": 2,
            "status_ping": 2,
            "status_summary": 2,
            "status_upload": 2,
            "xput_download": 850.5,
            "xput_upload": 420.2,
        }
        status.update(status_overrides)
        return {
            "mac": "00:00:5e:00:53:01",
            "type": "udm",
            "name": "Gateway",
            "speedtest-status": status,
            "speedtest-pending-interfaces": pending or [],
            "uplink": {"speedtest_status": "Success", "speedtest_ping": 12},
        }

    @staticmethod
    def _ap():
        return {"mac": "00:00:5e:00:53:41", "type": "uap", "name": "Test AP"}

    @pytest.mark.asyncio
    async def test_get_speed_test_status_success(self, mock_settings):
        """The gateway record's last result maps into the tool shape."""
        response = {"data": [self._ap(), self._gateway()]}

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_speed_test_status("site-1", mock_settings)

            assert result["status"] == "Success"
            assert result["download_speed_mbps"] == 850.5
            assert result["upload_speed_mbps"] == 420.2
            assert result["ping_ms"] == 12
            assert result["timestamp"].startswith("2025-01-01")
            assert result["server_name"] == "Example ISP"

    @pytest.mark.asyncio
    async def test_get_speed_test_status_running(self, mock_settings):
        """A non-empty pending-interfaces list means a test is in flight."""
        response = {"data": [self._gateway(pending=["eth4"])]}

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_speed_test_status("site-1", mock_settings)

            assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_speed_test_status_never_run(self, mock_settings):
        """A gateway with no recorded test reports that honestly."""
        gateway = self._gateway()
        del gateway["speedtest-status"]
        response = {"data": [gateway]}

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_speed_test_status("site-1", mock_settings)

            assert result["status"] == "no_result"
            assert "run_speed_test" in result["message"]

    @pytest.mark.asyncio
    async def test_get_speed_test_status_no_gateway(self, mock_settings):
        """A site with no gateway device raises instead of guessing."""
        from src.utils.exceptions import APIError

        response = {"data": [self._ap()]}

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            with pytest.raises(APIError, match="gateway"):
                await get_speed_test_status("site-1", mock_settings)

    @pytest.mark.asyncio
    async def test_get_speed_test_status_finds_ugw_gateway(self, mock_settings):
        """A USG reports ``type="ugw"`` -- the spelling the rest of the code uses.

        ``sites.py`` counts gateways as ``("ugw", "udm", "uxg")``; ``"usg"`` is a
        model-string token (``helpers.py``), never a device ``type``. A gateway
        that has not run a speed test carries no ``speedtest-status`` key, so
        the type check is the only thing that can find it.
        """
        gateway = self._gateway()
        gateway["type"] = "ugw"
        del gateway["speedtest-status"]
        response = {"data": [self._ap(), gateway]}

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_speed_test_status("site-1", mock_settings)

        assert result["status"] == "no_result"

    @pytest.mark.asyncio
    async def test_get_speed_test_status_invalid_site_id(self, mock_settings):
        """Test validation error for empty site_id."""
        with pytest.raises(ValidationError):
            await get_speed_test_status("", mock_settings)


class TestGetSpeedTestHistory:
    """History comes from the stat/report/archive.speedtest report.

    Fixtures mirror the live archive shape: xput_* in Mbps, latency in ms,
    time in epoch milliseconds. The previous rest/speedtest resource does
    not exist (api.err.InvalidObject on every call).
    """

    @staticmethod
    def _archive_entry(ts=1786007141000, down=935.0, up=918.0, latency=12):
        return {
            "_id": "st-1",
            "oid": "site-oid",
            "o": "speedtest",
            "time": ts,
            "xput_download": down,
            "xput_upload": up,
            "latency": latency,
        }

    @pytest.mark.asyncio
    async def test_get_speed_test_history_success(self, mock_settings):
        """The archive shape parses into the module's result shape."""
        response = {
            "data": [
                self._archive_entry(),
                {**self._archive_entry(), "_id": "st-2", "time": 1786093541000},
            ]
        }

        mock_client = create_mock_client()
        mock_client.post = AsyncMock(return_value=response)

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            result = await get_speed_test_history("site-1", mock_settings)

            called_url = mock_client.post.call_args[0][0]
            assert called_url == "/ea/sites/site-1/stat/report/archive.speedtest"
            body = mock_client.post.call_args[1]["json_data"]
            assert body["attrs"] == ["time", "xput_download", "xput_upload", "latency"]
            assert body["end"] > body["start"]

            assert len(result) == 2
            assert result[0]["download_speed_mbps"] == 935.0
            assert result[0]["upload_speed_mbps"] == 918.0
            assert result[0]["ping_ms"] == 12
            assert result[0]["timestamp"].startswith("2026-")

    @pytest.mark.asyncio
    async def test_get_speed_test_history_window(self, mock_settings):
        """The hours parameter sets the report window."""
        mock_client = create_mock_client()
        mock_client.post = AsyncMock(return_value={"data": []})

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            await get_speed_test_history("site-1", mock_settings, hours=24)

            body = mock_client.post.call_args[1]["json_data"]
            assert body["end"] - body["start"] == 24 * 3600 * 1000

    @pytest.mark.asyncio
    async def test_get_speed_test_history_empty(self, mock_settings):
        """Test speed test history with empty response."""
        mock_client = create_mock_client()
        mock_client.post = AsyncMock(return_value={"data": []})

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            result = await get_speed_test_history("site-1", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_get_speed_test_history_invalid_site_id(self, mock_settings):
        """Test validation error for empty site_id."""
        with pytest.raises(ValidationError):
            await get_speed_test_history("", mock_settings)

    @pytest.mark.asyncio
    async def test_get_speed_test_history_sorted_oldest_first(self, mock_settings):
        """The docstring promises oldest first regardless of report order."""
        newer = {**self._archive_entry(), "_id": "st-2", "time": 1786093541000}
        older = self._archive_entry()
        mock_client = create_mock_client()
        mock_client.post = AsyncMock(return_value={"data": [newer, older]})

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            result = await get_speed_test_history("site-1", mock_settings)

        assert [r["id"] for r in result] == ["st-1", "st-2"]

    @pytest.mark.asyncio
    async def test_get_speed_test_history_rejects_bad_hours(self, mock_settings):
        """Zero, negative and non-numeric windows fail fast."""
        for bad in (0, -24, "not-a-number"):
            with pytest.raises(ValidationError):
                await get_speed_test_history("site-1", mock_settings, hours=bad)


class TestGetSpectrumScan:
    """Spectrum data is per AP: stat/spectrum-scan/{mac}.

    Fixtures mirror the live shape on Network 10.5.67: per-AP entries with
    a scans[] list per radio, each carrying a spectrum_table. The old
    site-wide stat/spectrumscan path does not exist (404 on every call).
    """

    @staticmethod
    def _ap_device(mac="00:00:5e:00:53:41"):
        return {"mac": mac, "type": "uap", "name": "Test AP"}

    @staticmethod
    def _scan_entry(mac="00:00:5e:00:53:41", table=None):
        return {
            "mac": mac,
            "spectrum_scanning": False,
            "scans": [
                {"name": "wifi0", "radio": "ng", "spectrum_table": table or []},
                {"name": "wifi1", "radio": "na", "spectrum_table": []},
            ],
        }

    @pytest.mark.asyncio
    async def test_get_spectrum_scan_enumerates_aps(self, mock_settings):
        """Without ap_mac, each AP on the site is queried on its own route."""
        devices = {"data": [self._ap_device(), {"mac": "00:00:5e:00:53:99", "type": "usw"}]}
        scan = {"data": [self._scan_entry()]}

        mock_client = create_mock_client([devices, scan])

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            result = await get_spectrum_scan("site-1", mock_settings)

            urls = [c[0][0] for c in mock_client.get.call_args_list]
            assert urls == [
                "/ea/sites/site-1/devices",
                "/ea/sites/site-1/stat/spectrum-scan/00:00:5e:00:53:41",
            ]
            assert len(result["aps"]) == 1
            assert result["aps"][0]["mac"] == "00:00:5e:00:53:41"
            assert result["aps"][0]["scans"][0]["radio"] == "ng"

    @pytest.mark.asyncio
    async def test_get_spectrum_scan_explicit_ap(self, mock_settings):
        """An explicit ap_mac skips device enumeration."""
        scan = {"data": [self._scan_entry()]}
        mock_client = create_mock_client([scan])

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            result = await get_spectrum_scan("site-1", mock_settings, ap_mac="00:00:5e:00:53:41")

            urls = [c[0][0] for c in mock_client.get.call_args_list]
            assert urls == ["/ea/sites/site-1/stat/spectrum-scan/00:00:5e:00:53:41"]
            assert len(result["aps"]) == 1

    @pytest.mark.asyncio
    async def test_get_spectrum_scan_no_aps(self, mock_settings):
        """A site with no APs reports an empty result, not an error."""
        mock_client = create_mock_client([{"data": []}])

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            result = await get_spectrum_scan("site-1", mock_settings)

            assert result["aps"] == []

    @pytest.mark.asyncio
    async def test_get_spectrum_scan_invalid_site_id(self, mock_settings):
        with pytest.raises(ValidationError):
            await get_spectrum_scan("", mock_settings)

    @pytest.mark.asyncio
    async def test_get_spectrum_scan_rejects_malformed_mac(self, mock_settings):
        """A malformed ap_mac fails fast instead of entering the path."""
        with pytest.raises(ValidationError):
            await get_spectrum_scan("site-1", mock_settings, ap_mac="not-a-mac")


class TestListSpectrumInterference:
    @pytest.mark.asyncio
    async def test_list_spectrum_interference_flattens_tables(self, mock_settings):
        """spectrum_table rows come back annotated with AP and radio."""
        devices = {"data": [TestGetSpectrumScan._ap_device()]}
        scan = {
            "data": [
                TestGetSpectrumScan._scan_entry(
                    table=[{"channel": 6, "utilization": 41, "interference": "none"}]
                )
            ]
        }
        mock_client = create_mock_client([devices, scan])

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            result = await list_spectrum_interference("site-1", mock_settings)

            assert len(result) == 1
            assert result[0]["ap_mac"] == "00:00:5e:00:53:41"
            assert result[0]["radio"] == "ng"
            assert result[0]["channel"] == 6
            assert result[0]["utilization"] == 41

    @pytest.mark.asyncio
    async def test_annotations_win_over_row_keys(self, mock_settings):
        """A row carrying its own ap_mac/radio keys cannot mask the annotations."""
        devices = {"data": [TestGetSpectrumScan._ap_device()]}
        scan = {
            "data": [
                TestGetSpectrumScan._scan_entry(
                    table=[{"channel": 11, "ap_mac": "00:00:5e:00:53:99", "radio": "bogus"}]
                )
            ]
        }
        mock_client = create_mock_client([devices, scan])

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            result = await list_spectrum_interference("site-1", mock_settings)

            assert result[0]["ap_mac"] == "00:00:5e:00:53:41"
            assert result[0]["radio"] == "ng"
            assert result[0]["channel"] == 11

    @pytest.mark.asyncio
    async def test_list_spectrum_interference_no_scans_run(self, mock_settings):
        """APs that never ran an RF scan yield an empty list."""
        devices = {"data": [TestGetSpectrumScan._ap_device()]}
        scan = {"data": [TestGetSpectrumScan._scan_entry()]}
        mock_client = create_mock_client([devices, scan])

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            result = await list_spectrum_interference("site-1", mock_settings)

            assert result == []


class TestSpeedTestStatusGuards:
    @pytest.mark.asyncio
    async def test_speed_test_status_skips_non_dict_devices(self, mock_settings):
        """Junk entries in the device list are skipped while finding the gateway."""
        gateway = {
            "mac": "00:00:5e:00:53:01",
            "type": "udm",
            "speedtest-status": {"xput_download": 900.0, "xput_upload": 500.0, "latency": 9},
            "speedtest-pending-interfaces": [],
            "uplink": {"speedtest_status": "Success"},
        }
        client = create_mock_client([{"data": ["junk", 42, None, gateway]}])

        with patch("src.tools.diagnostics.UniFiClient", return_value=client):
            result = await get_speed_test_status("site-1", mock_settings)

        assert result["download_speed_mbps"] == 900.0
        assert result["status"] == "Success"


class TestSpectrumEdgeCoverage:
    """Close the codecov gaps reported on merged PR #128."""

    @pytest.mark.asyncio
    async def test_non_list_device_payload_yields_no_targets(self, mock_settings):
        """A malformed device list produces an empty scan, not an error."""
        client = create_mock_client([{"data": "garbage"}])

        with patch("src.tools.diagnostics.UniFiClient", return_value=client):
            result = await get_spectrum_scan("site-1", mock_settings)

        assert result == {"site_id": "site-1", "aps": []}
        client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_dict_radio_scan_entries_are_skipped(self, mock_settings):
        """Junk in the scans list is skipped rather than raising."""
        entry = {
            "mac": "00:00:5e:00:53:41",
            "scans": [
                "junk",
                {"radio": "ng", "name": "wifi0", "spectrum_table": [{"channel": 6}]},
            ],
        }
        client = create_mock_client(
            [
                {"data": [{"mac": "00:00:5e:00:53:41", "type": "uap"}]},
                {"data": [entry]},
            ]
        )

        with patch("src.tools.diagnostics.UniFiClient", return_value=client):
            result = await list_spectrum_interference("site-1", mock_settings)

        assert len(result) == 1
        assert result[0]["channel"] == 6
        assert result[0]["radio"] == "ng"


class TestGetHistoricalStats:
    @pytest.mark.asyncio
    async def test_posts_window_attrs_and_sorts_by_time(self, mock_settings):
        """The report body carries attrs + epoch-ms window; samples sort oldest first."""
        samples = [
            {"time": 2000, "cu_total": 30},
            {"time": 1000, "cu_total": 25},
        ]
        client = create_mock_client()
        client.post = AsyncMock(return_value={"data": samples})

        with patch("src.tools.diagnostics.UniFiClient", return_value=client):
            result = await get_historical_stats(
                "default", mock_settings, subject="ap", interval="hourly", hours=48
            )

        url = client.post.call_args[0][0]
        assert url == "/ea/sites/default/stat/report/hourly.ap"
        body = client.post.call_args[1]["json_data"]
        assert body["attrs"][0] == "time"
        # Archive airtime attrs are band-prefixed; bare cu_total is dead there.
        assert "ng-cu_total" in body["attrs"]
        assert "cu_total" not in body["attrs"]
        assert body["end"] - body["start"] == 48 * 3600 * 1000
        assert "macs" not in body
        assert [s["time"] for s in result] == [1000, 2000]

    @pytest.mark.asyncio
    async def test_mac_filter_and_custom_attrs_get_time_added(self, mock_settings):
        """A single MAC becomes a list; custom attrs always gain "time"."""
        client = create_mock_client()
        client.post = AsyncMock(return_value={"data": []})

        with patch("src.tools.diagnostics.UniFiClient", return_value=client):
            await get_historical_stats(
                "default",
                mock_settings,
                subject="user",
                interval="5minutes",
                macs="00:00:5e:00:53:07",
                attrs=["signal"],
            )

        body = client.post.call_args[1]["json_data"]
        assert body["macs"] == ["00:00:5e:00:53:07"]
        assert body["attrs"] == ["time", "signal"]

    @pytest.mark.asyncio
    async def test_rejects_bad_interval_subject_and_window(self, mock_settings):
        with pytest.raises(ValidationError, match="interval"):
            await get_historical_stats("default", mock_settings, interval="weekly")
        with pytest.raises(ValidationError, match="subject"):
            await get_historical_stats("default", mock_settings, subject="switch")
        with pytest.raises(ValidationError, match="hours"):
            await get_historical_stats("default", mock_settings, hours=0)


class TestStartSpectrumScan:
    @pytest.mark.asyncio
    async def test_posts_devmgr_spectrum_scan(self, mock_settings):
        client = create_mock_client()

        with patch("src.tools.diagnostics.UniFiClient", return_value=client):
            result = await start_spectrum_scan(
                "default", mock_settings, ap_mac="00:00:5e:00:53:41", confirm=True
            )

        url = client.post.call_args[0][0]
        assert url == "/ea/sites/default/cmd/devmgr"
        body = client.post.call_args[1]["json_data"]
        assert body == {"cmd": "spectrum-scan", "mac": "00:00:5e:00:53:41"}
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_dry_run_warns_and_does_not_post(self, mock_settings):
        client = create_mock_client()

        with patch("src.tools.diagnostics.UniFiClient", return_value=client):
            result = await start_spectrum_scan(
                "default", mock_settings, ap_mac="00:00:5e:00:53:41", confirm=True, dry_run=True
            )

        assert result["dry_run"] is True
        assert result["would_scan"] == "00:00:5e:00:53:41"
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_requires_confirm(self, mock_settings):
        with pytest.raises(ValidationError):
            await start_spectrum_scan("default", mock_settings, ap_mac="00:00:5e:00:53:41")


class TestReviewFollowUps:
    @pytest.mark.asyncio
    async def test_gw_defaults_omit_the_unarchived_latency(self, mock_settings):
        """Gateway latency is not archived; the defaults must not ask for it."""
        client = create_mock_client()
        client.post = AsyncMock(return_value={"data": []})

        with patch("src.tools.diagnostics.UniFiClient", return_value=client):
            await get_historical_stats("default", mock_settings, subject="gw")

        body = client.post.call_args[1]["json_data"]
        assert "latency" not in body["attrs"]

    @pytest.mark.asyncio
    async def test_scan_string_false_dry_run_still_posts(self, mock_settings):
        """The JSON-RPC string "false" must not downgrade a scan to a preview."""
        client = create_mock_client()

        with patch("src.tools.diagnostics.UniFiClient", return_value=client):
            result = await start_spectrum_scan(
                "default",
                mock_settings,
                ap_mac="00:00:5e:00:53:41",
                confirm=True,
                dry_run="false",
            )

        client.post.assert_called_once()
        assert result["success"] is True
