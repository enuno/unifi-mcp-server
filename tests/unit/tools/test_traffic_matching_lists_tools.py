"""Tests for Traffic Matching Lists tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.tools.traffic_matching_lists as tml_module
from src.tools.traffic_matching_lists import (
    create_traffic_matching_list,
    delete_traffic_matching_list,
    get_traffic_matching_list,
    list_traffic_matching_lists,
    update_traffic_matching_list,
)
from src.utils.exceptions import ResourceNotFoundError, ValidationError


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = MagicMock()
    settings.api_type.value = "local"
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-key"
    settings.local_host = "192.168.2.1"
    settings.local_port = 443
    settings.local_verify_ssl = False
    settings.request_timeout = 30.0
    settings.site_manager_enabled = False
    settings.get_headers = MagicMock(return_value={"X-API-Key": "test-key"})
    return settings


@pytest.mark.asyncio
async def test_list_traffic_matching_lists_success(mock_settings):
    mock_response = {
        "data": [
            {
                "_id": "tml-1",
                "type": "PORTS",
                "name": "Web Ports",
                "items": ["80", "443", "8080"],
                "site_id": "default",
            },
            {
                "_id": "tml-2",
                "type": "IPV4_ADDRESSES",
                "name": "Blocked IPs",
                "items": ["10.0.0.1", "10.0.0.2"],
                "site_id": "default",
            },
        ]
    }

    with patch("src.tools.traffic_matching_lists.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await list_traffic_matching_lists("default", mock_settings)

        assert len(result) == 2
        assert result[0]["id"] == "tml-1"
        assert result[0]["type"] == "PORTS"
        assert result[0]["name"] == "Web Ports"
        assert result[1]["id"] == "tml-2"
        assert result[1]["type"] == "IPV4_ADDRESSES"


@pytest.mark.asyncio
async def test_list_traffic_matching_lists_pagination(mock_settings):
    mock_response = {
        "data": [
            {"_id": f"tml-{i}", "type": "PORTS", "name": f"List {i}", "items": ["80"]}
            for i in range(10)
        ]
    }

    with patch("src.tools.traffic_matching_lists.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await list_traffic_matching_lists("default", mock_settings, limit=5, offset=2)

        assert len(result) == 5
        assert result[0]["id"] == "tml-2"
        assert result[4]["id"] == "tml-6"


@pytest.mark.asyncio
async def test_list_traffic_matching_lists_empty(mock_settings):
    mock_response = {"data": []}

    with patch("src.tools.traffic_matching_lists.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await list_traffic_matching_lists("default", mock_settings)

        assert result == []


@pytest.mark.asyncio
async def test_get_traffic_matching_list_success(mock_settings):
    mock_response = {
        "data": {
            "_id": "tml-1",
            "type": "PORTS",
            "name": "Web Ports",
            "items": ["80", "443", "8080", "8443"],
            "site_id": "default",
        }
    }

    with patch("src.tools.traffic_matching_lists.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await get_traffic_matching_list("default", "tml-1", mock_settings)

        assert result["id"] == "tml-1"
        assert result["name"] == "Web Ports"
        assert len(result["items"]) == 4


@pytest.mark.asyncio
async def test_get_traffic_matching_list_direct_response(mock_settings):
    mock_response = {
        "_id": "tml-1",
        "type": "IPV6_ADDRESSES",
        "name": "IPv6 List",
        "items": ["2001:db8::1", "2001:db8::2"],
    }

    with patch("src.tools.traffic_matching_lists.UniFiClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await get_traffic_matching_list("default", "tml-1", mock_settings)

        assert result["id"] == "tml-1"
        assert result["type"] == "IPV6_ADDRESSES"


@pytest.mark.asyncio
async def test_get_traffic_matching_list_not_found(mock_settings):
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value={})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(tml_module, "UniFiClient", return_value=mock_client):
        with pytest.raises(ResourceNotFoundError):
            await get_traffic_matching_list("default", "tml-nonexistent", mock_settings)


@pytest.mark.asyncio
async def test_create_traffic_matching_list_success(mock_settings):
    mock_response = {
        "data": {
            "_id": "tml-new",
            "type": "PORTS",
            "name": "New Port List",
            "items": ["22", "80", "443"],
            "site_id": "default",
        }
    }

    with patch("src.tools.traffic_matching_lists.UniFiClient") as mock_client_class:
        with patch("src.tools.traffic_matching_lists.log_audit"):
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await create_traffic_matching_list(
                "default",
                "PORTS",
                "New Port List",
                ["22", "80", "443"],
                mock_settings,
                confirm=True,
            )

            assert result["_id"] == "tml-new"
            assert result["name"] == "New Port List"
            mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_create_traffic_matching_list_dry_run(mock_settings):
    with patch("src.tools.traffic_matching_lists.log_audit"):
        result = await create_traffic_matching_list(
            "default",
            "IPV4_ADDRESSES",
            "Test IPs",
            ["192.168.2.1", "192.168.1.2"],
            mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["would_create"]["name"] == "Test IPs"
        assert result["would_create"]["type"] == "IPV4_ADDRESSES"


@pytest.mark.asyncio
async def test_create_traffic_matching_list_no_confirm(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await create_traffic_matching_list(
            "default",
            "PORTS",
            "Test",
            ["80"],
            mock_settings,
            confirm=False,
        )
    assert "requires confirmation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_traffic_matching_list_invalid_type(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await create_traffic_matching_list(
            "default",
            "INVALID_TYPE",
            "Test",
            ["80"],
            mock_settings,
            confirm=True,
        )
    assert "Invalid list type" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_traffic_matching_list_empty_items(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await create_traffic_matching_list(
            "default",
            "PORTS",
            "Test",
            [],
            mock_settings,
            confirm=True,
        )
    assert "cannot be empty" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_traffic_matching_list_success(mock_settings):
    mock_get_response = {
        "data": {
            "_id": "tml-1",
            "type": "PORTS",
            "name": "Old Name",
            "items": ["80"],
        }
    }
    mock_put_response = {
        "data": {
            "_id": "tml-1",
            "type": "PORTS",
            "name": "New Name",
            "items": ["80", "443"],
        }
    }

    with patch("src.tools.traffic_matching_lists.UniFiClient") as mock_client_class:
        with patch("src.tools.traffic_matching_lists.log_audit"):
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_get_response)
            mock_client.put = AsyncMock(return_value=mock_put_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await update_traffic_matching_list(
                "default",
                "tml-1",
                mock_settings,
                name="New Name",
                items=["80", "443"],
                confirm=True,
            )

            assert result["name"] == "New Name"
            mock_client.put.assert_called_once()


@pytest.mark.asyncio
async def test_update_traffic_matching_list_dry_run(mock_settings):
    with patch("src.tools.traffic_matching_lists.log_audit"):
        result = await update_traffic_matching_list(
            "default",
            "tml-1",
            mock_settings,
            name="Updated Name",
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["would_update"]["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_traffic_matching_list_no_confirm(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await update_traffic_matching_list(
            "default",
            "tml-1",
            mock_settings,
            name="New Name",
            confirm=False,
        )
    assert "requires confirmation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_traffic_matching_list_invalid_type(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await update_traffic_matching_list(
            "default",
            "tml-1",
            mock_settings,
            list_type="INVALID",
            confirm=True,
        )
    assert "Invalid list type" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_traffic_matching_list_empty_items(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await update_traffic_matching_list(
            "default",
            "tml-1",
            mock_settings,
            items=[],
            confirm=True,
        )
    assert "cannot be empty" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_traffic_matching_list_not_found(mock_settings):
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(return_value={})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(tml_module, "UniFiClient", return_value=mock_client):
        with patch.object(tml_module, "log_audit"):
            with pytest.raises(ResourceNotFoundError):
                await update_traffic_matching_list(
                    "default",
                    "tml-nonexistent",
                    mock_settings,
                    name="New Name",
                    confirm=True,
                )


@pytest.mark.asyncio
async def test_delete_traffic_matching_list_success(mock_settings):
    mock_get_response = {
        "data": {
            "_id": "tml-1",
            "type": "PORTS",
            "name": "To Delete",
            "items": ["80"],
        }
    }
    mock_delete_response = {}

    with patch("src.tools.traffic_matching_lists.UniFiClient") as mock_client_class:
        with patch("src.tools.traffic_matching_lists.log_audit"):
            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_get_response)
            mock_client.delete = AsyncMock(return_value=mock_delete_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await delete_traffic_matching_list(
                "default",
                "tml-1",
                mock_settings,
                confirm=True,
            )

            assert result["success"] is True
            assert result["deleted_list_id"] == "tml-1"
            mock_client.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_traffic_matching_list_dry_run(mock_settings):
    with patch("src.tools.traffic_matching_lists.log_audit"):
        result = await delete_traffic_matching_list(
            "default",
            "tml-1",
            mock_settings,
            confirm=True,
            dry_run=True,
        )

        assert result["dry_run"] is True
        assert result["would_delete"] == "tml-1"


@pytest.mark.asyncio
async def test_delete_traffic_matching_list_no_confirm(mock_settings):
    with pytest.raises(ValidationError) as excinfo:
        await delete_traffic_matching_list(
            "default",
            "tml-1",
            mock_settings,
            confirm=False,
        )
    assert "requires confirmation" in str(excinfo.value)


@pytest.mark.asyncio
async def test_delete_traffic_matching_list_not_found(mock_settings):
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Not found"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(tml_module, "UniFiClient", return_value=mock_client):
        with patch.object(tml_module, "log_audit"):
            with pytest.raises(ResourceNotFoundError):
                await delete_traffic_matching_list(
                    "default",
                    "tml-nonexistent",
                    mock_settings,
                    confirm=True,
                )
