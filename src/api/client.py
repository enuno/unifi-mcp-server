"""UniFi API client with authentication, rate limiting, and error handling."""

import asyncio
import time
from typing import Any

import httpx

from ..config import Settings
from ..utils import (
    APIError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
    ResourceNotFoundError,
    get_logger,
    log_api_request,
)


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, requests_per_period: int, period_seconds: int) -> None:
        """Initialize rate limiter.

        Args:
            requests_per_period: Maximum requests allowed in the period
            period_seconds: Time period in seconds
        """
        self.requests_per_period = requests_per_period
        self.period_seconds = period_seconds
        self.tokens: float = float(requests_per_period)
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.time()
            time_passed = now - self.last_update
            self.tokens = min(
                self.requests_per_period,
                self.tokens + (time_passed * self.requests_per_period / self.period_seconds),
            )
            self.last_update = now

            if self.tokens < 1:
                sleep_time = (1 - self.tokens) * self.period_seconds / self.requests_per_period
                await asyncio.sleep(sleep_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class UniFiClient:
    """Async HTTP client for UniFi API with authentication and rate limiting."""

    def __init__(self, settings: Settings) -> None:
        """Initialize UniFi API client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            base_url=settings.base_url,
            headers=settings.get_headers(),
            timeout=settings.request_timeout,
            verify=settings.verify_ssl,
        )

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            settings.rate_limit_requests,
            settings.rate_limit_period,
        )

        self._authenticated = False

    async def __aenter__(self) -> "UniFiClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    @property
    def is_authenticated(self) -> bool:
        """Check if client is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        return self._authenticated

    async def authenticate(self) -> None:
        """Authenticate with the UniFi API.

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Test authentication with a simple API call
            response = await self._request("GET", "/ea/sites")
            self._authenticated = (
                response.get("meta", {}).get("rc") == "ok" or response.get("data") is not None
            )
            self.logger.info("Successfully authenticated with UniFi API")
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate with UniFi API: {e}") from e

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        """Make an HTTP request with retries and error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON request body
            retry_count: Current retry attempt number

        Returns:
            Response data as dictionary

        Raises:
            APIError: If API returns an error
            RateLimitError: If rate limit is exceeded
            NetworkError: If network communication fails
        """
        # Apply rate limiting
        await self.rate_limiter.acquire()

        start_time = time.time()

        try:
            response = await self.client.request(
                method=method,
                url=endpoint,
                params=params,
                json=json_data,
            )

            duration_ms = (time.time() - start_time) * 1000

            # Log request if enabled
            if self.settings.log_api_requests:
                log_api_request(
                    self.logger,
                    method=method,
                    url=endpoint,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))

                # Retry if we haven't exceeded max retries
                if retry_count < self.settings.max_retries:
                    self.logger.warning(f"Rate limited, retrying after {retry_after}s")
                    await asyncio.sleep(retry_after)
                    return await self._request(method, endpoint, params, json_data, retry_count + 1)

                raise RateLimitError(retry_after=retry_after)

            # Handle not found
            if response.status_code == 404:
                raise ResourceNotFoundError("resource", endpoint)

            # Handle authentication errors
            if response.status_code in (401, 403):
                raise AuthenticationError(f"Authentication failed: {response.text}")

            # Handle other errors
            if response.status_code >= 400:
                error_data = None
                try:
                    error_data = response.json()
                except Exception:
                    pass

                raise APIError(
                    message=f"API request failed: {response.text}",
                    status_code=response.status_code,
                    response_data=error_data,
                )

            # Parse response
            json_response: dict[str, Any] = response.json()
            return json_response

        except httpx.TimeoutException as e:
            # Retry on timeout
            if retry_count < self.settings.max_retries:
                backoff = self.settings.retry_backoff_factor**retry_count
                self.logger.warning(f"Request timeout, retrying in {backoff}s")
                await asyncio.sleep(backoff)
                return await self._request(method, endpoint, params, json_data, retry_count + 1)

            raise NetworkError(f"Request timeout: {e}") from e

        except httpx.NetworkError as e:
            # Retry on network error
            if retry_count < self.settings.max_retries:
                backoff = self.settings.retry_backoff_factor**retry_count
                self.logger.warning(f"Network error, retrying in {backoff}s")
                await asyncio.sleep(backoff)
                return await self._request(method, endpoint, params, json_data, retry_count + 1)

            raise NetworkError(f"Network communication failed: {e}") from e

        except (RateLimitError, AuthenticationError, APIError, ResourceNotFoundError):
            # Re-raise our custom exceptions
            raise

        except Exception as e:
            self.logger.error(f"Unexpected error during API request: {e}")
            raise APIError(f"Unexpected error: {e}") from e

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response data
        """
        return await self._request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        json_data: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a POST request.

        Args:
            endpoint: API endpoint path
            json_data: JSON request body
            params: Query parameters

        Returns:
            Response data
        """
        return await self._request("POST", endpoint, params=params, json_data=json_data)

    async def put(
        self,
        endpoint: str,
        json_data: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a PUT request.

        Args:
            endpoint: API endpoint path
            json_data: JSON request body
            params: Query parameters

        Returns:
            Response data
        """
        return await self._request("PUT", endpoint, params=params, json_data=json_data)

    async def delete(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a DELETE request.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response data
        """
        return await self._request("DELETE", endpoint, params=params)
