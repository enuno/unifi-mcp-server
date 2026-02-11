"""Unit tests for DPI (Deep Packet Inspection) tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.dpi as dpi_module
import src.tools.dpi_tools as dpi_tools_module
from src.tools.dpi import get_client_dpi, get_dpi_statistics, list_top_applications
from src.tools.dpi_tools import list_countries, list_dpi_applications, list_dpi_categories


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "local"
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-key"
    settings.local_host = "192.168.2.1"
    settings.local_port = 443
    settings.local_verify_ssl = False
    return settings


# =============================================================================
# get_dpi_statistics Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_dpi_statistics_success(mock_settings):
    """Test successful DPI statistics retrieval."""
    mock_response = {
        "data": [
            {"app": "YouTube", "cat": "Streaming", "tx_bytes": 1000000, "rx_bytes": 5000000},
            {"app": "Netflix", "cat": "Streaming", "tx_bytes": 500000, "rx_bytes": 3000000},
            {"app": "Chrome", "cat": "Web", "tx_bytes": 200000, "rx_bytes": 800000},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await get_dpi_statistics("default", mock_settings)

    assert result["site_id"] == "default"
    assert result["time_range"] == "24h"
    assert len(result["applications"]) == 3
    assert result["total_applications"] == 3
    assert result["applications"][0]["application"] == "YouTube"


@pytest.mark.asyncio
async def test_get_dpi_statistics_time_ranges(mock_settings):
    """Test DPI statistics with different time ranges."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        for time_range in ["1h", "6h", "12h", "24h", "7d", "30d"]:
            result = await get_dpi_statistics("default", mock_settings, time_range=time_range)
            assert result["time_range"] == time_range


@pytest.mark.asyncio
async def test_get_dpi_statistics_invalid_time_range(mock_settings):
    """Test DPI statistics with invalid time range."""
    with pytest.raises(ValueError) as excinfo:
        await get_dpi_statistics("default", mock_settings, time_range="invalid")

    assert "Invalid time range" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_dpi_statistics_empty(mock_settings):
    """Test DPI statistics with empty response."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await get_dpi_statistics("default", mock_settings)

    assert result["applications"] == []
    assert result["categories"] == []
    assert result["total_applications"] == 0


@pytest.mark.asyncio
async def test_get_dpi_statistics_category_aggregation(mock_settings):
    """Test that DPI statistics aggregates by category."""
    mock_response = {
        "data": [
            {"app": "YouTube", "cat": "Streaming", "tx_bytes": 1000, "rx_bytes": 2000},
            {"app": "Netflix", "cat": "Streaming", "tx_bytes": 500, "rx_bytes": 1500},
            {"app": "Chrome", "cat": "Web", "tx_bytes": 100, "rx_bytes": 200},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await get_dpi_statistics("default", mock_settings)

    assert result["total_categories"] == 2
    streaming_cat = next(c for c in result["categories"] if c["category"] == "Streaming")
    assert streaming_cat["total_bytes"] == 5000
    assert streaming_cat["application_count"] == 2


# =============================================================================
# list_top_applications Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_top_applications_success(mock_settings):
    """Test successful top applications listing."""
    mock_response = {
        "data": [
            {"app": f"App{i}", "cat": "Cat", "tx_bytes": i * 1000, "rx_bytes": i * 2000}
            for i in range(20, 0, -1)
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await list_top_applications("default", mock_settings)

    assert len(result) == 10
    assert result[0]["total_bytes"] > result[9]["total_bytes"]


@pytest.mark.asyncio
async def test_list_top_applications_with_limit(mock_settings):
    """Test top applications with custom limit."""
    mock_response = {
        "data": [
            {"app": f"App{i}", "cat": "Cat", "tx_bytes": i * 1000, "rx_bytes": i * 2000}
            for i in range(10, 0, -1)
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await list_top_applications("default", mock_settings, limit=5)

    assert len(result) == 5


@pytest.mark.asyncio
async def test_list_top_applications_empty(mock_settings):
    """Test top applications with no data."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await list_top_applications("default", mock_settings)

    assert result == []


# =============================================================================
# get_client_dpi Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_client_dpi_success(mock_settings):
    """Test successful client DPI statistics retrieval."""
    mock_response = {
        "data": [
            {"app": "YouTube", "cat": "Streaming", "tx_bytes": 100000, "rx_bytes": 500000},
            {"app": "Chrome", "cat": "Web", "tx_bytes": 50000, "rx_bytes": 100000},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await get_client_dpi("default", "aa:bb:cc:dd:ee:ff", mock_settings)

    assert result["client_mac"] == "aa:bb:cc:dd:ee:ff"
    assert result["total_tx_bytes"] == 150000
    assert result["total_rx_bytes"] == 600000
    assert len(result["applications"]) == 2


@pytest.mark.asyncio
async def test_get_client_dpi_pagination(mock_settings):
    """Test client DPI with pagination."""
    mock_response = {
        "data": [
            {"app": f"App{i}", "cat": "Cat", "tx_bytes": i * 100, "rx_bytes": i * 200}
            for i in range(10, 0, -1)
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await get_client_dpi(
            "default", "aa:bb:cc:dd:ee:ff", mock_settings, limit=3, offset=2
        )

    assert len(result["applications"]) == 3
    assert result["total_applications"] == 10


@pytest.mark.asyncio
async def test_get_client_dpi_with_time_range(mock_settings):
    """Test client DPI with specific time range."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await get_client_dpi(
            "default", "aa:bb:cc:dd:ee:ff", mock_settings, time_range="7d"
        )

    assert result["time_range"] == "7d"


@pytest.mark.asyncio
async def test_get_client_dpi_invalid_time_range(mock_settings):
    """Test client DPI with invalid time range."""
    with pytest.raises(ValueError) as excinfo:
        await get_client_dpi("default", "aa:bb:cc:dd:ee:ff", mock_settings, time_range="invalid")

    assert "Invalid time range" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_client_dpi_percentage_calculation(mock_settings):
    """Test that client DPI calculates percentages correctly."""
    mock_response = {
        "data": [
            {"app": "YouTube", "cat": "Streaming", "tx_bytes": 500, "rx_bytes": 500},
            {"app": "Chrome", "cat": "Web", "tx_bytes": 250, "rx_bytes": 250},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await get_client_dpi("default", "aa:bb:cc:dd:ee:ff", mock_settings)

    youtube_app = next(a for a in result["applications"] if a["application"] == "YouTube")
    assert youtube_app["percentage"] == pytest.approx(66.67, rel=0.1)


@pytest.mark.asyncio
async def test_get_client_dpi_empty(mock_settings):
    """Test client DPI with no data."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_module, "UniFiClient", return_value=mock_client):
        result = await get_client_dpi("default", "aa:bb:cc:dd:ee:ff", mock_settings)

    assert result["applications"] == []
    assert result["total_bytes"] == 0


# =============================================================================
# list_dpi_categories Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_dpi_categories_success(mock_settings):
    """Test successful DPI categories listing."""
    mock_response = {
        "data": [
            {"_id": "cat1", "name": "Streaming"},
            {"_id": "cat2", "name": "Social Media"},
            {"_id": "cat3", "name": "Gaming"},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        result = await list_dpi_categories(mock_settings)

    assert len(result) == 3
    assert result[0]["name"] == "Streaming"


@pytest.mark.asyncio
async def test_list_dpi_categories_empty(mock_settings):
    """Test DPI categories with empty response."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        result = await list_dpi_categories(mock_settings)

    assert result == []


@pytest.mark.asyncio
async def test_list_dpi_categories_authenticates_if_needed(mock_settings):
    """Test that DPI categories authenticates if not already authenticated."""
    mock_response = {"data": [{"_id": "cat1", "name": "Test"}]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = False
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        await list_dpi_categories(mock_settings)

    mock_client.authenticate.assert_called_once()


# =============================================================================
# list_dpi_applications Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_dpi_applications_success(mock_settings):
    """Test successful DPI applications listing."""
    mock_response = {
        "data": [
            {"_id": "app1", "name": "YouTube", "category_id": "cat1"},
            {"_id": "app2", "name": "Netflix", "category_id": "cat1"},
            {"_id": "app3", "name": "Facebook", "category_id": "cat2"},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        result = await list_dpi_applications(mock_settings)

    assert len(result) == 3
    assert result[0]["name"] == "YouTube"


@pytest.mark.asyncio
async def test_list_dpi_applications_with_params(mock_settings):
    """Test DPI applications with limit, offset, and filter."""
    mock_response = {
        "data": [
            {"_id": "app1", "name": "YouTube", "category_id": "cat1"},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        await list_dpi_applications(mock_settings, limit=10, offset=5, filter_expr="name==YouTube")

    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    params = call_args[1]["params"]
    assert params["limit"] == 10
    assert params["offset"] == 5
    assert params["filter"] == "name==YouTube"


@pytest.mark.asyncio
async def test_list_dpi_applications_empty(mock_settings):
    """Test DPI applications with empty response."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        result = await list_dpi_applications(mock_settings)

    assert result == []


# =============================================================================
# list_countries Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_countries_success(mock_settings):
    """Test successful countries listing."""
    mock_response = {
        "data": [
            {"code": "US", "name": "United States"},
            {"code": "GB", "name": "United Kingdom"},
            {"code": "DE", "name": "Germany"},
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        result = await list_countries(mock_settings)

    assert len(result) == 3
    assert result[0]["code"] == "US"


@pytest.mark.asyncio
async def test_list_countries_empty(mock_settings):
    """Test countries with empty response."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        result = await list_countries(mock_settings)

    assert result == []
