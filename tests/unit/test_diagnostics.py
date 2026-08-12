"""Unit tests for diagnostics tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.diagnostics import (
    get_network_references,
    get_spectrum_scan,
    get_speed_test_history,
    get_speed_test_status,
    list_spectrum_interference,
    run_speed_test,
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

            result = await run_speed_test("site-1", mock_settings)

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
    @pytest.mark.asyncio
    async def test_get_speed_test_status_success(self, mock_settings):
        """Test successful retrieval of speed test status."""
        response = {
            "data": {
                "status": "completed",
                "download_speed_mbps": 850.5,
                "upload_speed_mbps": 420.2,
                "ping_ms": 12.3,
                "jitter_ms": 2.1,
                "timestamp": "2025-01-15T10:30:00Z",
            }
        }

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_speed_test_status("site-1", mock_settings)

            assert isinstance(result, dict)
            assert result["status"] == "completed"
            assert result["download_speed_mbps"] == 850.5
            assert result["upload_speed_mbps"] == 420.2
            assert result["ping_ms"] == 12.3

    @pytest.mark.asyncio
    async def test_get_speed_test_status_running(self, mock_settings):
        """Test speed test status when still running."""
        response = {"data": {"status": "running"}}

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_speed_test_status("site-1", mock_settings)

            assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_speed_test_status_invalid_site_id(self, mock_settings):
        """Test validation error for empty site_id."""
        with pytest.raises(ValidationError):
            await get_speed_test_status("", mock_settings)


class TestGetSpeedTestHistory:
    @pytest.mark.asyncio
    async def test_get_speed_test_history_success(self, mock_settings):
        """Test successful retrieval of speed test history."""
        response = {
            "data": [
                {
                    "id": "st-1",
                    "status": "completed",
                    "download_speed_mbps": 850.5,
                    "upload_speed_mbps": 420.2,
                    "ping_ms": 12.3,
                    "timestamp": "2025-01-15T10:30:00Z",
                },
                {
                    "id": "st-2",
                    "status": "completed",
                    "download_speed_mbps": 900.1,
                    "upload_speed_mbps": 450.5,
                    "ping_ms": 10.5,
                    "timestamp": "2025-01-14T10:30:00Z",
                },
            ]
        }

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_speed_test_history("site-1", mock_settings)

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["id"] == "st-1"
            assert result[0]["download_speed_mbps"] == 850.5
            assert result[1]["id"] == "st-2"

    @pytest.mark.asyncio
    async def test_get_speed_test_history_empty(self, mock_settings):
        """Test speed test history with empty response."""
        response = {"data": []}

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_speed_test_history("site-1", mock_settings)

            assert result == []

    @pytest.mark.asyncio
    async def test_get_speed_test_history_list_response(self, mock_settings):
        """Test speed test history with direct list response."""
        response = [
            {
                "id": "st-1",
                "status": "completed",
                "download_speed_mbps": 500.0,
                "upload_speed_mbps": 200.0,
                "timestamp": "2025-01-15T10:30:00Z",
            }
        ]

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = create_mock_client([response])

            result = await get_speed_test_history("site-1", mock_settings)

            assert len(result) == 1
            assert result[0]["id"] == "st-1"

    @pytest.mark.asyncio
    async def test_get_speed_test_history_invalid_site_id(self, mock_settings):
        """Test validation error for empty site_id."""
        with pytest.raises(ValidationError):
            await get_speed_test_history("", mock_settings)


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
    async def test_list_spectrum_interference_no_scans_run(self, mock_settings):
        """APs that never ran an RF scan yield an empty list."""
        devices = {"data": [TestGetSpectrumScan._ap_device()]}
        scan = {"data": [TestGetSpectrumScan._scan_entry()]}
        mock_client = create_mock_client([devices, scan])

        with patch("src.tools.diagnostics.UniFiClient") as mock_client_class:
            mock_client_class.return_value = mock_client

            result = await list_spectrum_interference("site-1", mock_settings)

            assert result == []
