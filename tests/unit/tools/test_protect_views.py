"""Unit tests for UniFi Protect view and viewer tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.exceptions import ValidationError

protect_views = pytest.importorskip("src.tools.protect_views")


def _tool(*names: str):
    for name in names:
        tool = getattr(protect_views, name, None)
        if tool is not None:
            return tool
    pytest.fail(f"None of the expected tool names exist on {protect_views.__name__}: {names}")


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


@pytest.mark.asyncio
async def test_list_protect_viewers_success(mock_settings, mock_client):
    response = {
        "count": 1,
        "totalCount": 1,
        "data": [
            {
                "id": "viewer-1",
                "name": "Lobby Viewer",
                "liveview": "liveview-1",
            }
        ],
    }
    mock_client.get = AsyncMock(return_value=response)
    list_protect_viewers = _tool("list_protect_viewers", "get_protect_viewers")

    with patch(f"{protect_views.__name__}.ProtectClient", return_value=mock_client):
        result = await list_protect_viewers(mock_settings)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/viewers")
    assert result["count"] == 1
    assert result["data"][0]["id"] == "viewer-1"
    assert result["data"][0]["liveview"] == "liveview-1"


@pytest.mark.asyncio
async def test_get_protect_viewer_success(mock_settings, mock_client):
    response = {"id": "viewer-1", "name": "Lobby Viewer", "liveview": "liveview-1"}
    mock_client.get = AsyncMock(return_value=response)
    get_protect_viewer = _tool("get_protect_viewer")

    with patch(f"{protect_views.__name__}.ProtectClient", return_value=mock_client):
        result = await get_protect_viewer("viewer-1", mock_settings)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/viewers/viewer-1")
    assert result["id"] == "viewer-1"
    assert result["name"] == "Lobby Viewer"


@pytest.mark.asyncio
async def test_list_protect_live_views_success(mock_settings, mock_client):
    response = {
        "offset": 0,
        "limit": 10,
        "count": 2,
        "totalCount": 2,
        "data": [
            {
                "id": "liveview-1",
                "name": "Default View",
                "isDefault": True,
                "isGlobal": True,
                "owner": "admin",
                "layout": 1,
                "slots": [],
            },
            {
                "id": "liveview-2",
                "name": "Warehouse View",
                "isDefault": False,
                "isGlobal": False,
                "owner": "admin",
                "layout": 2,
                "slots": [],
            },
        ],
    }
    mock_client.get = AsyncMock(return_value=response)
    list_protect_live_views = _tool("list_protect_live_views", "get_protect_live_views")

    with patch(f"{protect_views.__name__}.ProtectClient", return_value=mock_client):
        result = await list_protect_live_views(mock_settings, limit=10, offset=0)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/liveviews")
    assert result["count"] == 2
    assert result["totalCount"] == 2
    assert result["data"][0]["id"] == "liveview-1"
    assert result["data"][1]["name"] == "Warehouse View"


@pytest.mark.asyncio
async def test_get_protect_live_view_success(mock_settings, mock_client):
    response = {
        "id": "liveview-1",
        "name": "Default View",
        "isDefault": True,
        "isGlobal": True,
        "owner": "admin",
        "layout": 1,
        "slots": [],
    }
    mock_client.get = AsyncMock(return_value=response)
    get_protect_live_view = _tool("get_protect_live_view")

    with patch(f"{protect_views.__name__}.ProtectClient", return_value=mock_client):
        result = await get_protect_live_view("liveview-1", mock_settings)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/liveviews/liveview-1")
    assert result["id"] == "liveview-1"
    assert result["name"] == "Default View"


@pytest.mark.asyncio
async def test_get_protect_live_view_empty_id_raises(mock_settings):
    get_protect_live_view = _tool("get_protect_live_view")

    with pytest.raises(ValidationError, match="live_view_id"):
        await get_protect_live_view("", mock_settings)


def _patch(client):
    return patch(f"{protect_views.__name__}.ProtectClient", return_value=client)


@pytest.mark.parametrize(
    ("response", "expected"),
    [([{"id": 1}, "x"], [{"id": 1}]), ({"data": "x"}, []), (None, [])],
)
def test_extract_collection_shapes(response, expected):
    assert protect_views._extract_collection(response) == expected


@pytest.mark.parametrize(
    ("response", "expected"),
    [({"data": [1]}, {"data": [1]}), ("x", {})],
)
def test_extract_item_shapes(response, expected):
    assert protect_views._extract_item(response) == expected


@pytest.mark.asyncio
async def test_get_protect_meta_info(mock_settings, mock_client):
    mock_client.get = AsyncMock(return_value={"applicationVersion": "6.0.0"})
    with _patch(mock_client):
        result = await protect_views.get_protect_meta_info(mock_settings)

    mock_client.authenticate.assert_awaited_once()
    mock_client.get.assert_awaited_once_with("/integration/v1/meta/info")
    assert result["applicationVersion"] == "6.0.0"


@pytest.mark.asyncio
async def test_update_protect_viewer_requires_confirm(mock_settings, mock_client):
    with _patch(mock_client), pytest.raises(ValidationError, match="confirm"):
        await protect_views.update_protect_viewer("viewer-1", mock_settings, name="Lobby")
    mock_client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_update_protect_viewer_dry_run(mock_settings, mock_client):
    with _patch(mock_client):
        result = await protect_views.update_protect_viewer(
            " viewer-1 ", mock_settings, name="Lobby", liveview="lv-1", dry_run=True
        )

    assert result == {
        "dry_run": True,
        "operation": "update_protect_viewer",
        "viewer_id": "viewer-1",
        "payload": {"name": "Lobby", "liveview": "lv-1"},
    }
    mock_client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_update_protect_viewer_applies(mock_settings, mock_client):
    mock_client.patch = AsyncMock(return_value={"data": {"id": "viewer-1", "name": "Lobby"}})
    with _patch(mock_client):
        result = await protect_views.update_protect_viewer(
            "viewer-1", mock_settings, name="Lobby", confirm=True
        )

    mock_client.patch.assert_awaited_once_with(
        "/integration/v1/viewers/viewer-1", json_data={"name": "Lobby"}
    )
    assert result["name"] == "Lobby"


@pytest.mark.asyncio
async def test_create_protect_live_view_requires_confirm(mock_settings, mock_client):
    with _patch(mock_client), pytest.raises(ValidationError, match="confirm"):
        await protect_views.create_protect_live_view({"name": "Wall"}, mock_settings)
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_protect_live_view_dry_run(mock_settings, mock_client):
    with _patch(mock_client):
        result = await protect_views.create_protect_live_view(
            {"name": "Wall"}, mock_settings, dry_run="true"
        )

    assert result == {"dry_run": True, "operation": "create_protect_live_view"}
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_protect_live_view_posts(mock_settings, mock_client):
    mock_client.post = AsyncMock(return_value={"id": "lv-9", "name": "Wall"})
    with _patch(mock_client):
        result = await protect_views.create_protect_live_view(
            {"name": "Wall", "layout": 4}, mock_settings, confirm=True
        )

    mock_client.post.assert_awaited_once_with(
        "/integration/v1/liveviews", json_data={"name": "Wall", "layout": 4}
    )
    assert result["id"] == "lv-9"


@pytest.mark.asyncio
async def test_update_protect_live_view_dry_run_maps_all_fields(mock_settings, mock_client):
    with _patch(mock_client):
        result = await protect_views.update_protect_live_view(
            "lv-1",
            mock_settings,
            name="Wall",
            model_key="liveview",
            is_default=True,
            is_global=False,
            owner="user-1",
            layout=4,
            slots=[{"cameras": ["cam-1"]}],
            dry_run=True,
        )

    assert result["live_view_id"] == "lv-1"
    assert result["payload"] == {
        "name": "Wall",
        "modelKey": "liveview",
        "isDefault": True,
        "isGlobal": False,
        "owner": "user-1",
        "layout": 4,
        "slots": [{"cameras": ["cam-1"]}],
    }
    mock_client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_update_protect_live_view_applies(mock_settings, mock_client):
    mock_client.patch = AsyncMock(return_value={"id": "lv-1", "name": "Wall"})
    with _patch(mock_client):
        result = await protect_views.update_protect_live_view(
            "lv-1", mock_settings, name="Wall", confirm=True
        )

    mock_client.patch.assert_awaited_once_with(
        "/integration/v1/liveviews/lv-1", json_data={"name": "Wall"}
    )
    assert result["name"] == "Wall"


@pytest.mark.asyncio
async def test_update_protect_live_view_rejects_blank_id(mock_settings):
    with pytest.raises(ValidationError, match="live_view_id is required"):
        await protect_views.update_protect_live_view(" ", mock_settings, name="x", confirm=True)
