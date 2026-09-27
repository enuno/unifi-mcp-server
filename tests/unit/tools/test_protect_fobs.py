"""Unit tests for UniFi Protect key fob tools (Protect v7 surface, Phase 5a)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import protect_fobs
from src.tools.protect_fobs import (
    get_protect_fob,
    list_protect_fobs,
    update_protect_fob,
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
    client.post = AsyncMock()
    client.patch = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# --- Read paths -------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_protect_fobs_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(
        return_value={"count": 2, "totalCount": 2, "data": [
            {"id": "fob-1", "name": "Front Door Fob"},
            {"id": "fob-2", "name": "Back Door Fob"},
        ]}
    )
    with patch("src.tools.protect_fobs.ProtectClient", return_value=mock_client):
        result = await list_protect_fobs(mock_settings, limit=10, offset=0)
    mock_client.get.assert_awaited_once_with(
        "/integration/v1/fobs", params={"limit": 10, "offset": 0}
    )
    assert result["count"] == 2
    assert result["data"][0]["id"] == "fob-1"


@pytest.mark.asyncio
async def test_get_protect_fob_success(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"id": "fob-1", "name": "Front Door Fob"})
    with patch("src.tools.protect_fobs.ProtectClient", return_value=mock_client):
        result = await get_protect_fob("fob-1", mock_settings)
    mock_client.get.assert_awaited_once_with("/integration/v1/fobs/fob-1")
    assert result["id"] == "fob-1"


# --- Write gates ------------------------------------------------------------

WRITES = [
    ("update_protect_fob", {"fob_id": "fob-1", "name": "x"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[n for n, _ in WRITES])
async def test_write_refused_without_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_fobs.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_fobs, name)(settings=mock_settings, **kwargs)
        client_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "kwargs"), WRITES, ids=[f"{n}-strfalse" for n, _ in WRITES])
async def test_write_refused_with_string_false_confirm(mock_settings, mock_client, name, kwargs):
    with patch("src.tools.protect_fobs.ProtectClient") as client_cls:
        with pytest.raises(ValidationError):
            await getattr(protect_fobs, name)(
                settings=mock_settings, confirm="false", **kwargs
            )
        client_cls.assert_not_called()


# --- Write happy paths ------------------------------------------------------


@pytest.mark.asyncio
async def test_update_protect_fob_success(mock_settings, mock_client):
    mock_client.patch = AsyncMock(return_value={"id": "fob-1", "name": "New Name"})
    with patch("src.tools.protect_fobs.ProtectClient", return_value=mock_client):
        result = await update_protect_fob("fob-1", mock_settings, name="New Name", confirm=True)
    mock_client.patch.assert_awaited_once_with(
        "/integration/v1/fobs/fob-1", json_data={"name": "New Name"}
    )
    assert result["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_protect_fob_dry_run(mock_settings, mock_client):
    with patch("src.tools.protect_fobs.ProtectClient", return_value=mock_client):
        result = await update_protect_fob("fob-1", mock_settings, name="New Name", confirm=True, dry_run=True)
    assert result["dry_run"] is True
    assert result["payload"] == {"name": "New Name"}
    mock_client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_update_protect_fob_requires_a_field(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await update_protect_fob("fob-1", mock_settings, confirm=True)


# --- Input validation -------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_fob_id_rejected(mock_settings, mock_client):
    with pytest.raises(ValidationError):
        await get_protect_fob("   ", mock_settings)
