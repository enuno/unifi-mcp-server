"""Unit tests for DPI (Deep Packet Inspection) statistics tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.dpi import get_client_dpi, get_dpi_statistics, list_top_applications

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_dpi_data():
    """Sample DPI data for testing."""
    return [
        {"app": "443", "cat": "5", "tx_bytes": 1000000, "rx_bytes": 2000000},
        {"app": "80", "cat": "5", "tx_bytes": 500000, "rx_bytes": 1500000},
        {"app": "22", "cat": "8", "tx_bytes": 100000, "rx_bytes": 200000},
        {"app": "3389", "cat": "12", "tx_bytes": 800000, "rx_bytes": 400000},
        {"app": "53", "cat": "15", "tx_bytes": 50000, "rx_bytes": 50000},
    ]


@pytest.fixture
def sample_client_dpi_data():
    """Sample client-specific DPI data for testing."""
    return [
        {"app": "443", "cat": "5", "tx_bytes": 500000, "rx_bytes": 1000000},
        {"app": "80", "cat": "5", "tx_bytes": 200000, "rx_bytes": 300000},
        {"app": "22", "cat": "8", "tx_bytes": 10000, "rx_bytes": 15000},
    ]


# ============================================================================
# Test: get_dpi_statistics - Overall DPI Statistics
# ============================================================================


@pytest.mark.asyncio
async def test_get_dpi_statistics_success(
    settings: Settings, sample_dpi_data: list
) -> None:
    """Test getting DPI statistics successfully."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_dpi_data}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await get_dpi_statistics("site-123", settings, time_range="24h")

        assert result["site_id"] == "site-123"
        assert result["time_range"] == "24h"
        assert len(result["applications"]) == 5
        assert len(result["categories"]) == 4  # Unique categories: 5, 8, 12, 15
        assert result["total_applications"] == 5
        assert result["total_categories"] == 4

        # Verify applications are sorted by total_bytes (descending)
        apps = result["applications"]
        assert apps[0]["application"] == "443"  # 3000000 bytes total
        assert apps[1]["application"] == "80"  # 2000000 bytes total
        assert apps[2]["application"] == "3389"  # 1200000 bytes total

        # Verify aggregation correctness
        assert apps[0]["tx_bytes"] == 1000000
        assert apps[0]["rx_bytes"] == 2000000
        assert apps[0]["total_bytes"] == 3000000


@pytest.mark.asyncio
async def test_get_dpi_statistics_invalid_time_range(settings: Settings) -> None:
    """Test getting DPI statistics with invalid time range."""
    with pytest.raises(ValueError, match="Invalid time range"):
        await get_dpi_statistics("site-123", settings, time_range="invalid")


@pytest.mark.asyncio
async def test_get_dpi_statistics_empty_data(settings: Settings) -> None:
    """Test getting DPI statistics with no data."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": []}  # No DPI data
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await get_dpi_statistics("site-123", settings)

        assert result["total_applications"] == 0
        assert result["total_categories"] == 0
        assert len(result["applications"]) == 0
        assert len(result["categories"]) == 0


@pytest.mark.asyncio
async def test_get_dpi_statistics_aggregation(settings: Settings) -> None:
    """Test DPI statistics aggregation logic."""
    # Multiple entries for same app/category
    dpi_data_with_duplicates = [
        {"app": "443", "cat": "5", "tx_bytes": 500000, "rx_bytes": 1000000},
        {"app": "443", "cat": "5", "tx_bytes": 500000, "rx_bytes": 1000000},
        {"app": "80", "cat": "5", "tx_bytes": 200000, "rx_bytes": 300000},
    ]

    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": dpi_data_with_duplicates}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await get_dpi_statistics("site-123", settings)

        # Verify aggregation: two "443" entries should be combined
        apps = result["applications"]
        app_443 = next(a for a in apps if a["application"] == "443")
        assert app_443["tx_bytes"] == 1000000  # 500000 + 500000
        assert app_443["rx_bytes"] == 2000000  # 1000000 + 1000000
        assert app_443["total_bytes"] == 3000000

        # Verify category aggregation
        cats = result["categories"]
        cat_5 = next(c for c in cats if c["category"] == "5")
        assert cat_5["total_bytes"] == 3500000  # 3000000 + 500000
        assert cat_5["application_count"] == 3  # 3 app entries in category 5


@pytest.mark.asyncio
async def test_get_dpi_statistics_sorting(settings: Settings) -> None:
    """Test that results are sorted by total_bytes descending."""
    dpi_data = [
        {"app": "low", "cat": "1", "tx_bytes": 10000, "rx_bytes": 10000},
        {"app": "high", "cat": "1", "tx_bytes": 500000, "rx_bytes": 500000},
        {"app": "medium", "cat": "1", "tx_bytes": 100000, "rx_bytes": 100000},
    ]

    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": dpi_data}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await get_dpi_statistics("site-123", settings)

        apps = result["applications"]
        assert apps[0]["application"] == "high"  # 1000000 bytes
        assert apps[1]["application"] == "medium"  # 200000 bytes
        assert apps[2]["application"] == "low"  # 20000 bytes


# ============================================================================
# Test: list_top_applications - Top Applications Listing
# ============================================================================


@pytest.mark.asyncio
async def test_list_top_applications_default_limit(
    settings: Settings, sample_dpi_data: list
) -> None:
    """Test listing top applications with default limit."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_dpi_data}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_top_applications("site-123", settings)

        # Default limit is 10, but we only have 5 apps
        assert len(result) == 5
        # Should be sorted by total_bytes descending
        assert result[0]["application"] == "443"


@pytest.mark.asyncio
async def test_list_top_applications_custom_limit(
    settings: Settings, sample_dpi_data: list
) -> None:
    """Test listing top applications with custom limit."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_dpi_data}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_top_applications("site-123", settings, limit=3)

        assert len(result) == 3
        # Should return top 3 by bandwidth
        assert result[0]["application"] == "443"
        assert result[1]["application"] == "80"
        assert result[2]["application"] == "3389"


@pytest.mark.asyncio
async def test_list_top_applications_limit_exceeds(
    settings: Settings, sample_dpi_data: list
) -> None:
    """Test listing top applications when limit exceeds available apps."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_dpi_data}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_top_applications("site-123", settings, limit=100)

        # Should return all 5 apps even though limit is 100
        assert len(result) == 5


@pytest.mark.asyncio
async def test_list_top_applications_limit_one(
    settings: Settings, sample_dpi_data: list
) -> None:
    """Test listing top single application."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_dpi_data}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await list_top_applications("site-123", settings, limit=1)

        assert len(result) == 1
        assert result[0]["application"] == "443"  # Top bandwidth consumer


# ============================================================================
# Test: get_client_dpi - Per-Client DPI Statistics
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_dpi_success(
    settings: Settings, sample_client_dpi_data: list
) -> None:
    """Test getting client DPI statistics successfully."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_client_dpi_data}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await get_client_dpi(
            "site-123", "00:11:22:33:44:55", settings, time_range="24h"
        )

        assert result["site_id"] == "site-123"
        assert result["client_mac"] == "00:11:22:33:44:55"
        assert result["time_range"] == "24h"
        assert result["total_applications"] == 3
        assert len(result["applications"]) == 3

        # Verify total bytes calculation
        assert result["total_tx_bytes"] == 710000  # 500000 + 200000 + 10000
        assert result["total_rx_bytes"] == 1315000  # 1000000 + 300000 + 15000
        assert result["total_bytes"] == 2025000

        # Verify applications are sorted by total_bytes
        apps = result["applications"]
        assert apps[0]["application"] == "443"  # 1500000 bytes


@pytest.mark.asyncio
async def test_get_client_dpi_pagination(
    settings: Settings, sample_client_dpi_data: list
) -> None:
    """Test getting client DPI with pagination."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_client_dpi_data}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        # Test limit
        result = await get_client_dpi(
            "site-123", "00:11:22:33:44:55", settings, limit=2
        )
        assert len(result["applications"]) == 2

        # Test offset
        result = await get_client_dpi(
            "site-123", "00:11:22:33:44:55", settings, offset=1, limit=2
        )
        assert len(result["applications"]) == 2
        assert result["applications"][0]["application"] == "80"  # Second app after offset


@pytest.mark.asyncio
async def test_get_client_dpi_percentage_calculation(
    settings: Settings, sample_client_dpi_data: list
) -> None:
    """Test client DPI percentage calculation accuracy."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_client_dpi_data}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await get_client_dpi(
            "site-123", "00:11:22:33:44:55", settings
        )

        total_bytes = result["total_bytes"]
        apps = result["applications"]

        # Verify percentage calculation
        for app in apps:
            expected_percentage = (app["total_bytes"] / total_bytes) * 100
            assert abs(app["percentage"] - expected_percentage) < 0.01

        # Verify percentages sum to approximately 100%
        total_percentage = sum(app["percentage"] for app in apps)
        assert abs(total_percentage - 100.0) < 0.1


@pytest.mark.asyncio
async def test_get_client_dpi_zero_bytes_division(settings: Settings) -> None:
    """Test client DPI with zero total bytes (division by zero handling)."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": []}  # No data = zero bytes
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        result = await get_client_dpi(
            "site-123", "00:11:22:33:44:55", settings
        )

        assert result["total_bytes"] == 0
        assert len(result["applications"]) == 0


@pytest.mark.asyncio
async def test_get_client_dpi_mac_normalization(settings: Settings) -> None:
    """Test client DPI with different MAC address formats."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": []}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        # Test with different MAC formats - all should be normalized
        result = await get_client_dpi(
            "site-123", "AA:BB:CC:DD:EE:FF", settings  # Uppercase
        )
        assert result["client_mac"] == "aa:bb:cc:dd:ee:ff"  # Normalized to lowercase


@pytest.mark.asyncio
async def test_get_client_dpi_invalid_time_range(settings: Settings) -> None:
    """Test client DPI with invalid time range."""
    with pytest.raises(ValueError, match="Invalid time range"):
        await get_client_dpi(
            "site-123", "00:11:22:33:44:55", settings, time_range="invalid"
        )


@pytest.mark.asyncio
async def test_get_client_dpi_pagination_boundary(
    settings: Settings, sample_client_dpi_data: list
) -> None:
    """Test client DPI pagination edge cases."""
    with patch("src.tools.dpi.UniFiClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.authenticate.return_value = None
        mock_client.get.return_value = {"data": sample_client_dpi_data}
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client

        # Offset beyond available apps
        result = await get_client_dpi(
            "site-123", "00:11:22:33:44:55", settings, offset=10
        )
        assert len(result["applications"]) == 0  # No apps after offset 10

        # Very high limit should return all available apps
        result = await get_client_dpi(
            "site-123", "00:11:22:33:44:55", settings, limit=1000
        )
        assert len(result["applications"]) == 3  # All 3 apps available
