"""Unit tests for Traffic Matching List tools."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import Settings
from src.tools.traffic_matching_lists import (
    create_traffic_matching_list,
    delete_traffic_matching_list,
    get_traffic_matching_list,
    list_traffic_matching_lists,
    update_traffic_matching_list,
)
from src.utils import ResourceNotFoundError, ValidationError


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
    return Settings(_env_file=None)


class TestListTrafficMatchingLists:
    """Test suite for list_traffic_matching_lists function."""

    @pytest.mark.asyncio
    async def test_list_success(self, mock_settings: Settings) -> None:
        """Test listing traffic matching lists."""
        mock_data = {
            "data": [
                {
                    "_id": "list1",
                    "type": "PORTS",
                    "name": "Web Ports",
                    "items": ["80", "443"],
                },
                {
                    "_id": "list2",
                    "type": "IPV4_ADDRESSES",
                    "name": "Internal IPs",
                    "items": ["192.168.1.0/24"],
                },
            ]
        }

        with patch("src.tools.traffic_matching_lists.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_traffic_matching_lists("site-123", mock_settings)

            assert len(result) == 2
            assert result[0]["name"] == "Web Ports"
            assert result[0]["type"] == "PORTS"
            assert result[1]["name"] == "Internal IPs"
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_empty(self, mock_settings: Settings) -> None:
        """Test listing when no traffic matching lists exist."""
        mock_data = {"data": []}

        with patch("src.tools.traffic_matching_lists.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_traffic_matching_lists("site-123", mock_settings)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_pagination(self, mock_settings: Settings) -> None:
        """Test listing with pagination."""
        mock_data = {
            "data": [
                {"_id": f"list{i}", "type": "PORTS", "name": f"List {i}", "items": ["80"]}
                for i in range(10)
            ]
        }

        with patch("src.tools.traffic_matching_lists.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await list_traffic_matching_lists("site-123", mock_settings, limit=5, offset=2)

            assert len(result) == 5
            assert result[0]["name"] == "List 2"


class TestGetTrafficMatchingList:
    """Test suite for get_traffic_matching_list function."""

    @pytest.mark.asyncio
    async def test_get_success(self, mock_settings: Settings) -> None:
        """Test getting a specific traffic matching list."""
        mock_data = {
            "data": {
                "_id": "list1",
                "type": "PORTS",
                "name": "Web Ports",
                "items": ["80", "443", "8080"],
            }
        }

        with patch("src.tools.traffic_matching_lists.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await get_traffic_matching_list("site-123", "list1", mock_settings)

            assert result["id"] == "list1"
            assert result["name"] == "Web Ports"
            assert result["type"] == "PORTS"
            assert len(result["items"]) == 3

    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_settings: Settings) -> None:
        """Test getting a non-existent traffic matching list."""
        mock_data = {"data": None}

        with patch("src.tools.traffic_matching_lists.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_data
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            with pytest.raises(ResourceNotFoundError):
                await get_traffic_matching_list("site-123", "nonexistent", mock_settings)


class TestCreateTrafficMatchingList:
    """Test suite for create_traffic_matching_list function."""

    @pytest.mark.asyncio
    async def test_create_success(self, mock_settings: Settings) -> None:
        """Test creating a traffic matching list."""
        mock_response = {
            "data": {
                "_id": "new-list",
                "type": "PORTS",
                "name": "My Ports",
                "items": ["8000", "8080"],
            }
        }

        with patch("src.tools.traffic_matching_lists.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await create_traffic_matching_list(
                site_id="site-123",
                list_type="PORTS",
                name="My Ports",
                items=["8000", "8080"],
                settings=mock_settings,
                confirm=True,
            )

            assert result["_id"] == "new-list"
            assert result["name"] == "My Ports"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_invalid_type(self, mock_settings: Settings) -> None:
        """Test creating with invalid list type."""
        with pytest.raises(ValidationError) as exc_info:
            await create_traffic_matching_list(
                site_id="site-123",
                list_type="INVALID_TYPE",
                name="My List",
                items=["80"],
                settings=mock_settings,
                confirm=True,
            )

        assert "Invalid list type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_empty_items(self, mock_settings: Settings) -> None:
        """Test creating with empty items list."""
        with pytest.raises(ValidationError) as exc_info:
            await create_traffic_matching_list(
                site_id="site-123",
                list_type="PORTS",
                name="My List",
                items=[],
                settings=mock_settings,
                confirm=True,
            )

        assert "Items list cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_no_confirmation(self, mock_settings: Settings) -> None:
        """Test creating without confirmation."""
        with pytest.raises(ValidationError):
            await create_traffic_matching_list(
                site_id="site-123",
                list_type="PORTS",
                name="My List",
                items=["80"],
                settings=mock_settings,
                confirm=False,
            )

    @pytest.mark.asyncio
    async def test_create_dry_run(self, mock_settings: Settings) -> None:
        """Test creating in dry-run mode."""
        result = await create_traffic_matching_list(
            site_id="site-123",
            list_type="PORTS",
            name="My List",
            items=["80", "443"],
            settings=mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert "would_create" in result
        assert result["would_create"]["name"] == "My List"


class TestUpdateTrafficMatchingList:
    """Test suite for update_traffic_matching_list function."""

    @pytest.mark.asyncio
    async def test_update_success(self, mock_settings: Settings) -> None:
        """Test updating a traffic matching list."""
        mock_existing = {
            "data": {
                "_id": "list1",
                "type": "PORTS",
                "name": "Old Name",
                "items": ["80"],
            }
        }
        mock_updated = {
            "data": {
                "_id": "list1",
                "type": "PORTS",
                "name": "New Name",
                "items": ["80", "443"],
            }
        }

        with patch("src.tools.traffic_matching_lists.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_existing
            mock_client.put.return_value = mock_updated
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await update_traffic_matching_list(
                site_id="site-123",
                list_id="list1",
                settings=mock_settings,
                name="New Name",
                items=["80", "443"],
                confirm=True,
            )

            assert result["_id"] == "list1"
            assert result["name"] == "New Name"
            assert len(result["items"]) == 2
            mock_client.get.assert_called_once()
            mock_client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_not_found(self, mock_settings: Settings) -> None:
        """Test updating a non-existent list."""
        mock_response = {"data": None}

        with patch("src.tools.traffic_matching_lists.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            with pytest.raises(ResourceNotFoundError):
                await update_traffic_matching_list(
                    site_id="site-123",
                    list_id="nonexistent",
                    settings=mock_settings,
                    name="New Name",
                    confirm=True,
                )

    @pytest.mark.asyncio
    async def test_update_invalid_type(self, mock_settings: Settings) -> None:
        """Test updating with invalid list type."""
        with pytest.raises(ValidationError) as exc_info:
            await update_traffic_matching_list(
                site_id="site-123",
                list_id="list1",
                settings=mock_settings,
                list_type="INVALID",
                confirm=True,
            )

        assert "Invalid list type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_empty_items(self, mock_settings: Settings) -> None:
        """Test updating with empty items list."""
        with pytest.raises(ValidationError) as exc_info:
            await update_traffic_matching_list(
                site_id="site-123",
                list_id="list1",
                settings=mock_settings,
                items=[],
                confirm=True,
            )

        assert "Items list cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_dry_run(self, mock_settings: Settings) -> None:
        """Test updating in dry-run mode."""
        result = await update_traffic_matching_list(
            site_id="site-123",
            list_id="list1",
            settings=mock_settings,
            name="New Name",
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert "would_update" in result

    @pytest.mark.asyncio
    async def test_update_no_confirmation(self, mock_settings: Settings) -> None:
        """Test updating without confirmation."""
        with pytest.raises(ValidationError):
            await update_traffic_matching_list(
                site_id="site-123",
                list_id="list1",
                settings=mock_settings,
                name="New Name",
                confirm=False,
            )


class TestDeleteTrafficMatchingList:
    """Test suite for delete_traffic_matching_list function."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_settings: Settings) -> None:
        """Test deleting a traffic matching list."""
        mock_existing = {
            "data": {
                "_id": "list1",
                "type": "PORTS",
                "name": "My List",
                "items": ["80"],
            }
        }

        with patch("src.tools.traffic_matching_lists.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_existing
            mock_client.delete.return_value = {"success": True}
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await delete_traffic_matching_list(
                site_id="site-123", list_id="list1", settings=mock_settings, confirm=True
            )

            assert result["success"] is True
            assert result["deleted_list_id"] == "list1"
            mock_client.get.assert_called_once()
            mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_settings: Settings) -> None:
        """Test deleting a non-existent list."""
        with patch("src.tools.traffic_matching_lists.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Not found")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            with pytest.raises(ResourceNotFoundError):
                await delete_traffic_matching_list(
                    site_id="site-123",
                    list_id="nonexistent",
                    settings=mock_settings,
                    confirm=True,
                )

    @pytest.mark.asyncio
    async def test_delete_dry_run(self, mock_settings: Settings) -> None:
        """Test deleting in dry-run mode."""
        result = await delete_traffic_matching_list(
            site_id="site-123",
            list_id="list1",
            settings=mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["would_delete"] == "list1"

    @pytest.mark.asyncio
    async def test_delete_no_confirmation(self, mock_settings: Settings) -> None:
        """Test deleting without confirmation."""
        with pytest.raises(ValidationError):
            await delete_traffic_matching_list(
                site_id="site-123", list_id="list1", settings=mock_settings, confirm=False
            )
