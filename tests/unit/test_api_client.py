"""Unit tests for UniFi API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.api import UniFiClient
from src.config import Settings
from src.utils import APIError, AuthenticationError, NetworkError, RateLimitError


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create mock settings for testing."""
    monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "cloud")
    return Settings()


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Create a mock httpx client."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.aclose = AsyncMock()
    return client


class TestUniFiClient:
    """Test suite for UniFiClient class."""

    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_settings: Settings) -> None:
        """Test client initialization."""
        async with UniFiClient(mock_settings) as client:
            assert client.settings == mock_settings
            assert not client.is_authenticated

    @pytest.mark.asyncio
    async def test_successful_authentication(self, mock_settings: Settings) -> None:
        """Test successful authentication."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"meta": {"rc": "ok"}, "data": []}

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            client = UniFiClient(mock_settings)
            await client.authenticate()

            assert client.is_authenticated

            await client.close()

    @pytest.mark.asyncio
    async def test_failed_authentication(self, mock_settings: Settings) -> None:
        """Test failed authentication."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            client = UniFiClient(mock_settings)

            with pytest.raises(AuthenticationError):
                await client.authenticate()

            await client.close()

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, mock_settings: Settings) -> None:
        """Test rate limit handling."""
        mock_settings.max_retries = 0  # Disable retries for this test

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            client = UniFiClient(mock_settings)

            with pytest.raises(RateLimitError) as exc_info:
                await client.get("/test")

            assert exc_info.value.retry_after == 60

            await client.close()

    @pytest.mark.asyncio
    async def test_successful_get_request(self, mock_settings: Settings) -> None:
        """Test successful GET request."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": ["item1", "item2"]}

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            client = UniFiClient(mock_settings)
            result = await client.get("/test", params={"limit": 10})

            assert result == {"data": ["item1", "item2"]}

            await client.close()

    @pytest.mark.asyncio
    async def test_successful_post_request(self, mock_settings: Settings) -> None:
        """Test successful POST request."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            client = UniFiClient(mock_settings)
            result = await client.post("/test", json_data={"key": "value"})

            assert result == {"success": True}

            await client.close()

    @pytest.mark.asyncio
    async def test_404_error(self, mock_settings: Settings) -> None:
        """Test 404 not found error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.text = "Not Found"

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            client = UniFiClient(mock_settings)

            with pytest.raises(APIError) as exc_info:
                await client.get("/test")

            assert exc_info.value.status_code == 404

            await client.close()

    @pytest.mark.asyncio
    async def test_network_error_with_retry(self, mock_settings: Settings) -> None:
        """Test network error with retry."""
        mock_settings.max_retries = 2

        with patch("httpx.AsyncClient") as mock_client_class:
            # First call raises network error, second succeeds
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "success"}

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(
                side_effect=[
                    httpx.NetworkError("Connection failed"),
                    mock_response,
                ]
            )
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            client = UniFiClient(mock_settings)
            result = await client.get("/test")

            assert result == {"data": "success"}
            # Should have been called twice (original + 1 retry)
            assert mock_instance.request.call_count == 2

            await client.close()

    @pytest.mark.asyncio
    async def test_timeout_error(self, mock_settings: Settings) -> None:
        """Test timeout error."""
        mock_settings.max_retries = 0

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            client = UniFiClient(mock_settings)

            with pytest.raises(NetworkError, match="timeout"):
                await client.get("/test")

            await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_settings: Settings) -> None:
        """Test async context manager."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_instance

            async with UniFiClient(mock_settings) as client:
                assert client is not None

            # Ensure close was called
            mock_instance.aclose.assert_called_once()


class TestRateLimiter:
    """Test suite for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self) -> None:
        """Test rate limiter allows requests within limit."""
        from src.api.client import RateLimiter

        limiter = RateLimiter(requests_per_period=100, period_seconds=60)

        # Should allow multiple requests quickly
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

        # No assertion needed - test passes if no exception is raised

    @pytest.mark.asyncio
    async def test_rate_limiter_replenishes_tokens(self) -> None:
        """Test rate limiter replenishes tokens over time."""
        import asyncio

        from src.api.client import RateLimiter

        limiter = RateLimiter(requests_per_period=2, period_seconds=1)

        # Use up tokens
        await limiter.acquire()
        await limiter.acquire()

        # Wait for token replenishment
        await asyncio.sleep(0.6)

        # Should be able to acquire again
        await limiter.acquire()
