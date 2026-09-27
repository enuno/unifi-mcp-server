"""Unit tests for UniFi Protect user tools (Protect v7 surface)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.protect_users import (
    get_protect_ulp_user,
    get_protect_user,
    list_protect_ulp_users,
    list_protect_users,
)
from src.utils.exceptions import ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.get_protect_integration_path = MagicMock(
        side_effect=lambda endpoint: f"/integration/v1/{endpoint.lstrip('/')}"
    )
    return settings


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.authenticate = AsyncMock()
    client.get = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# --- Users ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_protect_users_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(
        return_value={"count": 2, "totalCount": 2, "data": [
            {"id": "user-1", "name": "Admin"},
            {"id": "user-2", "name": "Viewer"},
        ]}
    )
    with patch("src.tools.protect_users.ProtectClient", return_value=mock_client):
        result = await list_protect_users(mock_settings, limit=10, offset=0)
    mock_client.get.assert_awaited_once_with(
        "/integration/v1/users", params={"limit": 10, "offset": 0}
    )
    assert result["count"] == 2
    assert result["data"][0]["id"] == "user-1"


@pytest.mark.asyncio
async def test_get_protect_user_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"id": "user-1", "name": "Admin"})
    with patch("src.tools.protect_users.ProtectClient", return_value=mock_client):
        result = await get_protect_user("user-1", mock_settings)
    mock_client.get.assert_awaited_once_with("/integration/v1/users/user-1")
    assert result["id"] == "user-1"


# --- ULP users --------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_protect_ulp_users_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(
        return_value={"count": 2, "totalCount": 2, "data": [
            {"id": "ulp-1", "name": "Identity One"},
            {"id": "ulp-2", "name": "Identity Two"},
        ]}
    )
    with patch("src.tools.protect_users.ProtectClient", return_value=mock_client):
        result = await list_protect_ulp_users(mock_settings, limit=10, offset=0)
    mock_client.get.assert_awaited_once_with(
        "/integration/v1/ulp-users", params={"limit": 10, "offset": 0}
    )
    assert result["count"] == 2
    assert result["data"][0]["id"] == "ulp-1"


@pytest.mark.asyncio
async def test_get_protect_ulp_user_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"id": "ulp-1", "name": "Identity One"})
    with patch("src.tools.protect_users.ProtectClient", return_value=mock_client):
        result = await get_protect_ulp_user("ulp-1", mock_settings)
    mock_client.get.assert_awaited_once_with("/integration/v1/ulp-users/ulp-1")
    assert result["id"] == "ulp-1"


# --- Input validation -------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_user_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await get_protect_user("   ", mock_settings)


@pytest.mark.asyncio
async def test_empty_ulp_user_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await get_protect_ulp_user("   ", mock_settings)
