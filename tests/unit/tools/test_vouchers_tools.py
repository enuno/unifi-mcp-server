"""Unit tests for voucher management tools.

Fixtures mirror the documented Integration v1 voucher shape
(``/v1/sites/{siteId}/hotspot/vouchers``): camelCase keys, integer ``code``,
and no ``site_id``/``status``/``duration``/``create_time`` — the legacy shape
the previous tests fed through this endpoint came from nowhere real.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.vouchers as vouchers_module
from src.tools.vouchers import (
    bulk_delete_vouchers,
    create_vouchers,
    delete_voucher,
    get_voucher,
    list_vouchers,
)
from src.utils.exceptions import ValidationError

VOUCHER_ID = "3c2a8f52-9c11-4b5e-9c2f-6d1a2b3c4d5e"


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
    settings.get_integration_path = MagicMock(
        side_effect=lambda e: f"/integration/v1/{e.lstrip('/')}"
    )
    return settings


@pytest.fixture
def sample_voucher():
    """A voucher exactly as the documented endpoint returns it."""
    return {
        "id": VOUCHER_ID,
        "createdAt": "2026-08-01T10:00:00Z",
        "name": "Guest access",
        "code": 4861320975,
        "authorizedGuestLimit": 1,
        "authorizedGuestCount": 0,
        "expiresAt": "2026-08-02T10:00:00Z",
        "expired": False,
        "timeLimitMinutes": 1440,
    }


def _make_client(response):
    client = MagicMock()
    client.is_authenticated = True
    client.authenticate = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    client.delete = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# =============================================================================
# list_vouchers
# =============================================================================


@pytest.mark.asyncio
async def test_list_vouchers_success(mock_settings, sample_voucher):
    """The documented payload parses and the hotspot path is called."""
    second = {**sample_voucher, "id": "0b1c2d3e-1111-2222-3333-444455556666", "code": 111222333}
    client = _make_client({"data": [sample_voucher, second]})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        result = await list_vouchers("default", mock_settings)

    called_url = client.get.call_args[0][0]
    assert called_url == "/integration/v1/sites/default/hotspot/vouchers"
    assert len(result) == 2
    assert result[0]["id"] == VOUCHER_ID
    assert result[0]["code"] == 4861320975
    assert result[0]["time_limit_minutes"] == 1440


@pytest.mark.asyncio
async def test_list_vouchers_builds_path_per_api_mode(mock_settings, sample_voucher):
    """Endpoints come from get_integration_path so every API mode works.

    Cloud V1 serves the Integration surface under /v1/..., not
    /integration/v1/..., so a hardcoded prefix would break that mode.
    """
    mock_settings.get_integration_path = MagicMock(side_effect=lambda e: f"/v1/{e.lstrip('/')}")
    client = _make_client({"data": [sample_voucher]})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        await list_vouchers("default", mock_settings)

    assert client.get.call_args[0][0] == "/v1/sites/default/hotspot/vouchers"


@pytest.mark.asyncio
async def test_list_vouchers_authenticates_when_needed(mock_settings, sample_voucher):
    """An unauthenticated client must authenticate before the call."""
    client = _make_client({"data": [sample_voucher]})
    client.is_authenticated = False

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        await list_vouchers("default", mock_settings)

    client.authenticate.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_vouchers_rejects_out_of_bounds_limits(mock_settings):
    """The documented parameter bounds fail fast instead of deferring to a 400."""
    cases = [
        {"time_limit_minutes": 1_000_001},
        {"time_limit_minutes": 60, "authorized_guest_limit": 0},
        {"time_limit_minutes": 60, "data_usage_limit_mb": 0},
        {"time_limit_minutes": 60, "rx_rate_limit_kbps": 1},
        {"time_limit_minutes": 60, "tx_rate_limit_kbps": 100_001},
    ]
    for kwargs in cases:
        with pytest.raises(ValidationError):
            await create_vouchers(
                site_id="default",
                name="Guest access",
                settings=mock_settings,
                confirm=True,
                **kwargs,
            )


@pytest.mark.asyncio
async def test_list_vouchers_params(mock_settings, sample_voucher):
    """Pagination and filter are passed through as query parameters."""
    client = _make_client({"data": [sample_voucher]})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        await list_vouchers(
            "default", mock_settings, limit=50, offset=10, filter_expr="expired.eq(false)"
        )

    params = client.get.call_args[1]["params"]
    assert params == {"limit": 50, "offset": 10, "filter": "expired.eq(false)"}


@pytest.mark.asyncio
async def test_list_vouchers_empty(mock_settings):
    client = _make_client({"data": []})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        result = await list_vouchers("default", mock_settings)

    assert result == []


# =============================================================================
# get_voucher
# =============================================================================


@pytest.mark.asyncio
async def test_get_voucher_success(mock_settings, sample_voucher):
    client = _make_client(sample_voucher)

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        result = await get_voucher("default", VOUCHER_ID, mock_settings)

    called_url = client.get.call_args[0][0]
    assert called_url == f"/integration/v1/sites/default/hotspot/vouchers/{VOUCHER_ID}"
    assert result["id"] == VOUCHER_ID
    assert result["name"] == "Guest access"


@pytest.mark.asyncio
async def test_get_voucher_unused_has_no_activated_at(mock_settings, sample_voucher):
    """activatedAt is absent until first use; the absent key stays absent."""
    client = _make_client(sample_voucher)

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        result = await get_voucher("default", VOUCHER_ID, mock_settings)

    assert "activated_at" not in result


# =============================================================================
# create_vouchers
# =============================================================================


@pytest.mark.asyncio
async def test_create_vouchers_sends_documented_body(mock_settings, sample_voucher):
    client = _make_client({"data": [sample_voucher]})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        result = await create_vouchers(
            site_id="default",
            name="Guest access",
            time_limit_minutes=1440,
            settings=mock_settings,
            count=5,
            authorized_guest_limit=2,
            data_usage_limit_mb=1024,
            rx_rate_limit_kbps=10000,
            tx_rate_limit_kbps=5000,
            confirm=True,
        )

    called_url = client.post.call_args[0][0]
    assert called_url == "/integration/v1/sites/default/hotspot/vouchers"
    payload = client.post.call_args[1]["json_data"]
    assert payload == {
        "count": 5,
        "name": "Guest access",
        "timeLimitMinutes": 1440,
        "authorizedGuestLimit": 2,
        "dataUsageLimitMBytes": 1024,
        "rxRateLimitKbps": 10000,
        "txRateLimitKbps": 5000,
    }
    assert result["success"] is True
    assert result["vouchers"][0]["code"] == 4861320975


@pytest.mark.asyncio
async def test_create_vouchers_parses_wrapped_201(mock_settings, sample_voucher):
    """Generation nests the batch under a ``vouchers`` key.

    Observed live on Network 10.5.67: the 201 body is
    ``{"vouchers": [...]}``, not a bare list or a ``data`` envelope. Note the
    live controller also returned ``code`` as a *string* — the docs say
    integer — which is why the model types it ``int | str``.
    """
    created = {**sample_voucher, "code": "6014397834"}
    client = _make_client({"vouchers": [created]})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        result = await create_vouchers(
            site_id="default",
            name="Guest access",
            time_limit_minutes=60,
            settings=mock_settings,
            confirm=True,
        )

    assert len(result["vouchers"]) == 1
    assert result["vouchers"][0]["id"] == VOUCHER_ID
    assert result["vouchers"][0]["code"] == "6014397834"


@pytest.mark.asyncio
async def test_create_vouchers_minimal_body(mock_settings, sample_voucher):
    """Optional limits stay out of the body when not requested."""
    client = _make_client({"data": [sample_voucher]})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        await create_vouchers(
            site_id="default",
            name="Guest access",
            time_limit_minutes=60,
            settings=mock_settings,
            confirm=True,
        )

    payload = client.post.call_args[1]["json_data"]
    assert payload == {"count": 1, "name": "Guest access", "timeLimitMinutes": 60}


@pytest.mark.asyncio
async def test_create_vouchers_dry_run(mock_settings):
    client = _make_client({})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        result = await create_vouchers(
            site_id="default",
            name="Guest access",
            time_limit_minutes=60,
            settings=mock_settings,
            confirm=True,
            dry_run=True,
        )

    assert result["dry_run"] is True
    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_vouchers_requires_name(mock_settings):
    with pytest.raises(ValidationError, match="name"):
        await create_vouchers(
            site_id="default",
            name="",
            time_limit_minutes=60,
            settings=mock_settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_vouchers_rejects_bad_count(mock_settings):
    with pytest.raises(ValidationError, match="count"):
        await create_vouchers(
            site_id="default",
            name="Guest access",
            time_limit_minutes=60,
            settings=mock_settings,
            count=0,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_vouchers_rejects_bad_time_limit(mock_settings):
    with pytest.raises(ValidationError, match="time_limit_minutes"):
        await create_vouchers(
            site_id="default",
            name="Guest access",
            time_limit_minutes=0,
            settings=mock_settings,
            confirm=True,
        )


@pytest.mark.asyncio
async def test_create_vouchers_requires_confirmation(mock_settings):
    with pytest.raises(ValidationError):
        await create_vouchers(
            site_id="default",
            name="Guest access",
            time_limit_minutes=60,
            settings=mock_settings,
            confirm=False,
        )


# =============================================================================
# delete_voucher / bulk_delete_vouchers
# =============================================================================


@pytest.mark.asyncio
async def test_delete_voucher_success(mock_settings):
    client = _make_client({})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        result = await delete_voucher("default", VOUCHER_ID, mock_settings, confirm=True)

    client.delete.assert_called_once_with(
        f"/integration/v1/sites/default/hotspot/vouchers/{VOUCHER_ID}"
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_delete_voucher_dry_run(mock_settings):
    client = _make_client({})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        result = await delete_voucher(
            "default", VOUCHER_ID, mock_settings, confirm=True, dry_run=True
        )

    assert result["dry_run"] is True
    client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_delete_vouchers_reports_documented_count(mock_settings):
    """The documented response is {"vouchersDeleted": N}."""
    client = _make_client({"vouchersDeleted": 5})

    with patch.object(vouchers_module, "UniFiClient", return_value=client):
        result = await bulk_delete_vouchers(
            "default", "expired.eq(true)", mock_settings, confirm=True
        )

    called_url = client.delete.call_args[0][0]
    assert called_url == "/integration/v1/sites/default/hotspot/vouchers"
    assert client.delete.call_args[1]["params"] == {"filter": "expired.eq(true)"}
    assert result["deleted_count"] == 5


@pytest.mark.asyncio
async def test_bulk_delete_vouchers_requires_filter(mock_settings):
    with pytest.raises(ValidationError, match="filter"):
        await bulk_delete_vouchers("default", "", mock_settings, confirm=True)


class TestVoucherItemsUnwrap:
    """Close the codecov gaps reported on merged PR #122."""

    def test_bare_list_filters_non_dict_items(self):
        from src.tools.vouchers import _voucher_items

        assert _voucher_items(["junk", {"id": "v1"}, 7]) == [{"id": "v1"}]

    def test_scalar_reply_yields_empty_list(self):
        from src.tools.vouchers import _voucher_items

        assert _voucher_items("ok") == []
        assert _voucher_items(None) == []
