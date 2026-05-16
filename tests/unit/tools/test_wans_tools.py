"""Unit tests for src/tools/wans.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.wans import list_wan_connections


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    return settings


def make_wan(wan_id="wan-1"):
    return {
        "_id": wan_id,
        "site_id": "default",
        "name": "WAN1",
        "wan_type": "dhcp",
        "interface": "eth0",
        "status": "online",
    }


def create_mock_client(return_value):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=return_value)
    mock_client.authenticate = AsyncMock()
    mock_client.is_authenticated = False
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestListWanConnections:
    async def test_returns_list_when_api_returns_list(self, mock_settings):
        wan = make_wan()
        mock_client = create_mock_client([wan])
        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await list_wan_connections("default", mock_settings)
        assert len(result) == 1
        assert result[0]["name"] == "WAN1"

    async def test_returns_list_when_api_returns_dict(self, mock_settings):
        wan = make_wan()
        mock_client = create_mock_client({"data": [wan]})
        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await list_wan_connections("default", mock_settings)
        assert len(result) == 1
        assert result[0]["wan_type"] == "dhcp"

    async def test_empty_response(self, mock_settings):
        mock_client = create_mock_client([])
        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            result = await list_wan_connections("default", mock_settings)
        assert result == []

    async def test_authenticates_when_not_authenticated(self, mock_settings):
        wan = make_wan()
        mock_client = create_mock_client([wan])
        mock_client.is_authenticated = False
        with patch("src.tools.wans.UniFiClient", return_value=mock_client):
            await list_wan_connections("default", mock_settings)
        mock_client.authenticate.assert_called_once()
