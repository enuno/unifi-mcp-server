"""Unit tests for voucher management tools."""

from datetime import datetime
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


@pytest.fixture
def sample_voucher():
    """Create a sample voucher for testing."""
    return {
        "_id": "voucher1",
        "site_id": "default",
        "code": "ABCD-1234-EFGH",
        "status": "unused",
        "used": 0,
        "quota": 1,
        "duration": 3600,
        "create_time": datetime.now().isoformat(),
    }


# =============================================================================
# list_vouchers Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_vouchers_success(mock_settings, sample_voucher):
    """Test successful voucher listing."""
    mock_response = {
        "data": [sample_voucher, {**sample_voucher, "_id": "voucher2", "code": "WXYZ-5678"}]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        result = await list_vouchers("default", mock_settings)

    assert len(result) == 2
    assert result[0]["code"] == "ABCD-1234-EFGH"


@pytest.mark.asyncio
async def test_list_vouchers_with_filter(mock_settings, sample_voucher):
    """Test voucher listing with filter expression."""
    mock_response = {"data": [sample_voucher]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        await list_vouchers("default", mock_settings, filter_expr="status==unused")

    call_args = mock_client.get.call_args
    params = call_args[1]["params"]
    assert params["filter"] == "status==unused"


@pytest.mark.asyncio
async def test_list_vouchers_pagination(mock_settings, sample_voucher):
    """Test voucher listing with pagination."""
    mock_response = {"data": [sample_voucher]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        await list_vouchers("default", mock_settings, limit=10, offset=5)

    call_args = mock_client.get.call_args
    params = call_args[1]["params"]
    assert params["limit"] == 10
    assert params["offset"] == 5


@pytest.mark.asyncio
async def test_list_vouchers_empty(mock_settings):
    """Test voucher listing with empty response."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        result = await list_vouchers("default", mock_settings)

    assert result == []


@pytest.mark.asyncio
async def test_list_vouchers_authenticates_if_needed(mock_settings, sample_voucher):
    """Test that list_vouchers authenticates if not already authenticated."""
    mock_response = {"data": [sample_voucher]}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = False
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        await list_vouchers("default", mock_settings)

    mock_client.authenticate.assert_called_once()


# =============================================================================
# get_voucher Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_voucher_success(mock_settings, sample_voucher):
    """Test successful voucher retrieval."""
    mock_response = {"data": sample_voucher}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        result = await get_voucher("default", "voucher1", mock_settings)

    assert result["code"] == "ABCD-1234-EFGH"
    mock_client.get.assert_called_once_with("/integration/v1/sites/default/vouchers/voucher1")


@pytest.mark.asyncio
async def test_get_voucher_authenticates_if_needed(mock_settings, sample_voucher):
    """Test that get_voucher authenticates if not already authenticated."""
    mock_response = {"data": sample_voucher}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = False
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        await get_voucher("default", "voucher1", mock_settings)

    mock_client.authenticate.assert_called_once()


# =============================================================================
# create_vouchers Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_vouchers_success(mock_settings):
    """Test successful voucher creation."""
    mock_response = {
        "data": [
            {
                "_id": "new1",
                "code": "NEW1-CODE",
                "status": "unused",
                "duration": 3600,
                "site_id": "default",
                "quota": 1,
                "used": 0,
                "create_time": datetime.now().isoformat(),
            },
            {
                "_id": "new2",
                "code": "NEW2-CODE",
                "status": "unused",
                "duration": 3600,
                "site_id": "default",
                "quota": 1,
                "used": 0,
                "create_time": datetime.now().isoformat(),
            },
        ]
    }

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        with patch.object(vouchers_module, "audit_action", new=AsyncMock()):
            result = await create_vouchers("default", 2, 3600, mock_settings, confirm=True)

    assert result["success"] is True
    assert result["count"] == 2
    assert len(result["vouchers"]) == 2


@pytest.mark.asyncio
async def test_create_vouchers_with_limits(mock_settings):
    """Test voucher creation with bandwidth limits."""
    mock_response = {"data": []}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        with patch.object(vouchers_module, "audit_action", new=AsyncMock()):
            await create_vouchers(
                "default",
                5,
                7200,
                mock_settings,
                upload_limit_kbps=1000,
                download_limit_kbps=5000,
                upload_quota_mb=500,
                download_quota_mb=1000,
                note="Test vouchers",
                confirm=True,
            )

    call_args = mock_client.post.call_args
    payload = call_args[1]["json_data"]
    assert payload["uploadLimit"] == 1000
    assert payload["downloadLimit"] == 5000
    assert payload["uploadQuota"] == 500
    assert payload["downloadQuota"] == 1000
    assert payload["note"] == "Test vouchers"


@pytest.mark.asyncio
async def test_create_vouchers_dry_run(mock_settings):
    """Test voucher creation dry run."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        result = await create_vouchers(
            "default", 3, 3600, mock_settings, confirm=True, dry_run=True
        )

    assert result["dry_run"] is True
    assert result["payload"]["count"] == 3
    assert result["payload"]["duration"] == 3600


@pytest.mark.asyncio
async def test_create_vouchers_no_confirm(mock_settings):
    """Test voucher creation fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await create_vouchers("default", 1, 3600, mock_settings, confirm=False)

    assert "requires confirmation" in str(excinfo.value).lower()


# =============================================================================
# delete_voucher Tests
# =============================================================================


@pytest.mark.asyncio
async def test_delete_voucher_success(mock_settings):
    """Test successful voucher deletion."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.delete = AsyncMock(return_value={})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        with patch.object(vouchers_module, "audit_action", new=AsyncMock()):
            result = await delete_voucher("default", "voucher1", mock_settings, confirm=True)

    assert result["success"] is True
    mock_client.delete.assert_called_once_with("/integration/v1/sites/default/vouchers/voucher1")


@pytest.mark.asyncio
async def test_delete_voucher_dry_run(mock_settings):
    """Test voucher deletion dry run."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        result = await delete_voucher(
            "default", "voucher1", mock_settings, confirm=True, dry_run=True
        )

    assert result["dry_run"] is True
    assert result["voucher_id"] == "voucher1"


@pytest.mark.asyncio
async def test_delete_voucher_no_confirm(mock_settings):
    """Test voucher deletion fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await delete_voucher("default", "voucher1", mock_settings, confirm=False)

    assert "requires confirmation" in str(excinfo.value).lower()


# =============================================================================
# bulk_delete_vouchers Tests
# =============================================================================


@pytest.mark.asyncio
async def test_bulk_delete_vouchers_success(mock_settings):
    """Test successful bulk voucher deletion."""
    mock_response = {"data": {"count": 5}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.delete = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        with patch.object(vouchers_module, "audit_action", new=AsyncMock()):
            result = await bulk_delete_vouchers(
                "default", "status==expired", mock_settings, confirm=True
            )

    assert result["success"] is True
    assert result["deleted_count"] == 5


@pytest.mark.asyncio
async def test_bulk_delete_vouchers_dry_run(mock_settings):
    """Test bulk voucher deletion dry run."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = True
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        result = await bulk_delete_vouchers(
            "default", "status==unused", mock_settings, confirm=True, dry_run=True
        )

    assert result["dry_run"] is True
    assert result["filter"] == "status==unused"


@pytest.mark.asyncio
async def test_bulk_delete_vouchers_no_confirm(mock_settings):
    """Test bulk voucher deletion fails without confirmation."""
    with pytest.raises(ValidationError) as excinfo:
        await bulk_delete_vouchers("default", "status==expired", mock_settings, confirm=False)

    assert "requires confirmation" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_bulk_delete_vouchers_authenticates_if_needed(mock_settings):
    """Test that bulk_delete authenticates if not already authenticated."""
    mock_response = {"data": {"count": 0}}

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = False
    mock_client.delete = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(vouchers_module, "UniFiClient", return_value=mock_client):
        with patch.object(vouchers_module, "audit_action", new=AsyncMock()):
            await bulk_delete_vouchers("default", "status==old", mock_settings, confirm=True)

    mock_client.authenticate.assert_called_once()
