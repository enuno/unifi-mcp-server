"""Test API client handling of empty JSON responses."""
import pytest
from httpx import Response
from unittest.mock import AsyncMock, Mock
from src.api.client import UniFiClient
from src.config import Settings


@pytest.mark.asyncio
async def test_empty_response_body_returns_empty_dict(settings: Settings):
    """Test that empty HTTP 200 response returns {} instead of raising JSONDecodeError."""
    import json
    client = UniFiClient(settings)

    # Mock httpx client to return empty response
    mock_response = Mock(spec=Response)
    mock_response.status_code = 200
    mock_response.text = ""  # Empty response body
    mock_response.headers = {}

    # Make .json() raise JSONDecodeError like real httpx.Response
    def raise_json_error():
        raise json.JSONDecodeError("Expecting value", "", 0)

    mock_response.json = raise_json_error

    # Mock the httpx client
    client.client = AsyncMock()
    client.client.request = AsyncMock(return_value=mock_response)

    # The _request method should raise APIError (current buggy behavior)
    # After fix, it should return {}
    try:
        result = await client._request("GET", "/ea/sites")
        # If we get here, fix is already applied
        assert result == {}
    except Exception as e:
        # This is the current buggy behavior - should be fixed
        assert "Expecting value" in str(e)
        pytest.fail(f"Bug still exists: {e}")


@pytest.mark.asyncio
async def test_whitespace_only_response_returns_empty_dict(settings: Settings):
    """Test that whitespace-only response returns {} instead of raising JSONDecodeError."""
    client = UniFiClient(settings)

    mock_response = Mock(spec=Response)
    mock_response.status_code = 200
    mock_response.text = "   \n\t  "  # Whitespace only
    mock_response.headers = {}

    client.client = AsyncMock()
    client.client.request = AsyncMock(return_value=mock_response)

    result = await client._request("GET", "/ea/sites")
    assert result == {}


@pytest.mark.asyncio
async def test_valid_json_response_still_works(settings: Settings):
    """Test that valid JSON responses still work correctly."""
    client = UniFiClient(settings)

    mock_response = Mock(spec=Response)
    mock_response.status_code = 200
    mock_response.text = '{"data": [{"id": "123"}]}'
    mock_response.headers = {}
    mock_response.json.return_value = {"data": [{"id": "123"}]}

    client.client = AsyncMock()
    client.client.request = AsyncMock(return_value=mock_response)

    result = await client._request("GET", "/ea/sites")
    assert result == {"data": [{"id": "123"}]}
