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
#
# Site DPI counters come from POST stat/sitedpi with {"type": "by_app"} /
# {"type": "by_cat"}: data[0] carries the rows under the type key, app/cat
# as numeric catalog ids. Verified live on Network 10.5.67 (route answers;
# counters empty there because traffic identification runs via flows).
# =============================================================================


def _sitedpi_client(by_app=None, by_cat=None):
    async def post(url, json_data=None):
        kind = (json_data or {}).get("type")
        rows = {"by_app": by_app or [], "by_cat": by_cat or []}[kind]
        return {"data": [{kind: rows}]}

    client = MagicMock()
    client.authenticate = AsyncMock()
    client.post = AsyncMock(side_effect=post)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_get_dpi_statistics_success(mock_settings):
    """Rows are totalled and sorted by traffic."""
    client = _sitedpi_client(
        by_app=[
            {"app": 94, "cat": 4, "tx_bytes": 1000000, "rx_bytes": 5000000},
            {"app": 133, "cat": 13, "tx_bytes": 200000, "rx_bytes": 800000},
        ],
        by_cat=[{"cat": 4, "tx_bytes": 1000000, "rx_bytes": 5000000}],
    )

    with patch.object(dpi_module, "UniFiClient", return_value=client):
        result = await get_dpi_statistics("site-1", mock_settings)

    posted = [c[1]["json_data"]["type"] for c in client.post.call_args_list]
    assert posted == ["by_app", "by_cat"]
    urls = {c[0][0] for c in client.post.call_args_list}
    assert urls == {"/ea/sites/site-1/stat/sitedpi"}

    assert result["total_applications"] == 2
    assert result["applications"][0]["app"] == 94
    assert result["applications"][0]["total_bytes"] == 6000000
    assert result["categories"][0]["total_bytes"] == 6000000
    assert "note" not in result


@pytest.mark.asyncio
async def test_get_dpi_statistics_empty_notes_flow_engine(mock_settings):
    """A flow-based controller reports empty counters plus a pointer."""
    client = _sitedpi_client()

    with patch.object(dpi_module, "UniFiClient", return_value=client):
        result = await get_dpi_statistics("site-1", mock_settings)

    assert result["applications"] == []
    assert result["categories"] == []
    assert "traffic-flow" in result["note"]


@pytest.mark.asyncio
async def test_get_dpi_statistics_empty_object_row(mock_settings):
    """The live empty shape is data: [{}] — no type key at all."""

    async def post(url, json_data=None):
        return {"data": [{}]}

    client = MagicMock()
    client.authenticate = AsyncMock()
    client.post = AsyncMock(side_effect=post)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch.object(dpi_module, "UniFiClient", return_value=client):
        result = await get_dpi_statistics("site-1", mock_settings)

    assert result["total_applications"] == 0


# =============================================================================
# list_top_applications Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_top_applications_success(mock_settings):
    client = _sitedpi_client(
        by_app=[
            {"app": 94, "cat": 4, "tx_bytes": 0, "rx_bytes": 500},
            {"app": 7, "cat": 13, "tx_bytes": 0, "rx_bytes": 9000},
        ]
    )

    with patch.object(dpi_module, "UniFiClient", return_value=client):
        result = await list_top_applications("site-1", mock_settings)

    assert [r["app"] for r in result] == [7, 94]


@pytest.mark.asyncio
async def test_list_top_applications_with_limit(mock_settings):
    client = _sitedpi_client(
        by_app=[{"app": i, "tx_bytes": 0, "rx_bytes": i * 100} for i in range(1, 6)]
    )

    with patch.object(dpi_module, "UniFiClient", return_value=client):
        result = await list_top_applications("site-1", mock_settings, limit=2)

    assert len(result) == 2
    assert result[0]["app"] == 5


@pytest.mark.asyncio
async def test_list_top_applications_empty(mock_settings):
    client = _sitedpi_client()

    with patch.object(dpi_module, "UniFiClient", return_value=client):
        result = await list_top_applications("site-1", mock_settings)

    assert result == []


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


@pytest.mark.asyncio
async def test_list_dpi_applications_accepts_sparse_integration_response(mock_settings):
    """Integration v1 returns only a numeric id and a name; that must not raise.

    See issue #108: ``/integration/v1/dpi/applications`` sends exactly
    ``{"id": 3, "name": "ICQ"}``, so requiring ``category_id`` and typing ``id``
    as a string made the tool unusable on the local API.
    """
    mock_response = {"data": [{"id": 3, "name": "ICQ"}, {"id": 7, "name": "Skype"}]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        result = await list_dpi_applications(mock_settings)

    # Absent fields are dropped rather than failing validation or padding the
    # record with five nulls. Nothing carries a concrete default either, so an
    # application the controller never described is not reported as enabled.
    assert result == [{"id": 3, "name": "ICQ"}, {"id": 7, "name": "Skype"}]


@pytest.mark.asyncio
async def test_list_dpi_applications_preserves_populated_fields(mock_settings):
    """Relaxing the model must not drop values when they are present."""
    mock_response = {
        "data": [
            {
                "_id": "app1",
                "name": "YouTube",
                "category_id": "cat1",
                "category_name": "Streaming",
                "enabled": False,
                "protocols": ["tcp", "udp"],
                "ports": [80, 443],
            }
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

    assert result[0]["id"] == "app1"
    assert result[0]["category_id"] == "cat1"
    assert result[0]["category_name"] == "Streaming"
    assert result[0]["protocols"] == ["tcp", "udp"]
    assert result[0]["ports"] == [80, 443]
    # enabled=False survives the exclude_none filter; it is a reported value,
    # not an absent one.
    assert result[0]["enabled"] is False


@pytest.mark.asyncio
async def test_list_dpi_applications_accepts_camel_case_category(mock_settings):
    """The integration API spells the category key ``categoryId``."""
    mock_response = {"data": [{"id": 3, "name": "ICQ", "categoryId": 1}]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        result = await list_dpi_applications(mock_settings)

    assert result[0]["category_id"] == 1


@pytest.mark.asyncio
async def test_list_dpi_categories_accepts_numeric_id(mock_settings):
    """``/integration/v1/dpi/categories`` numbers its categories from zero."""
    mock_response = {"data": [{"id": 0, "name": "Instant messengers"}]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(dpi_tools_module, "UniFiClient", return_value=mock_client):
        result = await list_dpi_categories(mock_settings)

    assert result == [{"id": 0, "name": "Instant messengers"}]


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


class TestUpdateDpiSettings:
    @pytest.mark.asyncio
    async def test_rmw_preserves_section_and_verifies(self, mock_settings):
        from src.tools.dpi import update_dpi_settings

        section = {"_id": "dpi-1", "enabled": False, "fingerprintingEnabled": False, "site_id": "s"}
        stored = {**section, "enabled": True, "fingerprintingEnabled": False}
        client = MagicMock()
        client.authenticate = AsyncMock()
        client.get = AsyncMock(side_effect=[{"data": [section]}, {"data": [stored]}])
        client.post = AsyncMock(return_value={"data": []})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.dpi.UniFiClient", return_value=client):
            result = await update_dpi_settings("default", mock_settings, enabled=True, confirm=True)

        url = client.post.call_args[0][0]
        assert url == "/ea/sites/default/set/setting/dpi/dpi-1"
        body = client.post.call_args[1]["json_data"]
        assert body["enabled"] is True
        assert body["fingerprintingEnabled"] is False  # existing value preserved
        assert body["site_id"] == "s"  # section keys carried through
        assert "_id" not in body
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_creates_the_section_when_the_site_has_none(self, mock_settings):
        """With no stored section the POST goes to the bare endpoint.

        A site that has never had DPI configured returns no section, so
        there is no `_id` to address. The id is appended only when one
        exists -- posting `.../setting/dpi/None` would 404 and the change
        would be silently lost.
        """
        from src.tools.dpi import update_dpi_settings

        stored = {"_id": "dpi-new", "enabled": True, "fingerprintingEnabled": True}
        client = MagicMock()
        client.authenticate = AsyncMock()
        client.get = AsyncMock(side_effect=[{"data": []}, {"data": [stored]}])
        client.post = AsyncMock(return_value={"data": []})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.dpi.UniFiClient", return_value=client):
            result = await update_dpi_settings("default", mock_settings, enabled=True, confirm=True)

        url = client.post.call_args[0][0]
        assert url == "/ea/sites/default/set/setting/dpi"
        body = client.post.call_args[1]["json_data"]
        assert body["enabled"] is True
        # Nothing to preserve, so the lockstep default applies.
        assert body["fingerprintingEnabled"] is True
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_absent_enabled_key_is_not_a_confirmed_disable(self, mock_settings):
        """A dropped key must not read as a confirmed False.

        Regression: the check coerced the echo with ``bool()``, and
        ``bool(None)`` is ``False`` -- so a disable request against a
        controller that omits ``enabled`` entirely reported success while
        the stored state was actually unknown. Absent is not false.
        """
        from src.tools.dpi import update_dpi_settings

        section = {"_id": "dpi-1", "enabled": True}
        echoed_without_key = {"_id": "dpi-1"}
        client = MagicMock()
        client.authenticate = AsyncMock()
        client.get = AsyncMock(side_effect=[{"data": [section]}, {"data": [echoed_without_key]}])
        client.post = AsyncMock(return_value={"data": []})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.dpi.UniFiClient", return_value=client):
            result = await update_dpi_settings(
                "default", mock_settings, enabled=False, confirm=True
            )

        assert result["success"] is False
        assert result["enabled"] is None
        assert "did not echo" in result["warning"]

    @pytest.mark.asyncio
    async def test_unstored_state_reports_unconfirmed(self, mock_settings):
        from src.tools.dpi import update_dpi_settings

        section = {"_id": "dpi-1", "enabled": False}
        client = MagicMock()
        client.authenticate = AsyncMock()
        client.get = AsyncMock(side_effect=[{"data": [section]}, {"data": [section]}])
        client.post = AsyncMock(return_value={"data": []})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.dpi.UniFiClient", return_value=client):
            result = await update_dpi_settings("default", mock_settings, enabled=True, confirm=True)

        assert result["success"] is False
        assert "warning" in result

    @pytest.mark.asyncio
    async def test_dry_run_and_confirm_gate(self, mock_settings):
        from src.tools.dpi import update_dpi_settings
        from src.utils.exceptions import ValidationError

        section = {"_id": "dpi-1", "enabled": False}
        client = MagicMock()
        client.authenticate = AsyncMock()
        client.get = AsyncMock(return_value={"data": [section]})
        client.post = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.dpi.UniFiClient", return_value=client):
            result = await update_dpi_settings(
                "default", mock_settings, enabled=True, confirm=True, dry_run=True
            )
        assert result["dry_run"] is True and result["current_enabled"] is False
        client.post.assert_not_called()

        with pytest.raises(ValidationError):
            await update_dpi_settings("default", mock_settings, enabled=True)
