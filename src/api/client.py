"""UniFi API client with authentication, rate limiting, and error handling."""

import asyncio
import json
import time
from typing import Any
from uuid import UUID

import httpx

from ..config import APIType, Settings
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
        # Note: We construct full URLs explicitly in _request() to ensure HTTPS is preserved
        # Using base_url can cause protocol downgrade issues with httpx
        self.client = httpx.AsyncClient(
            headers=settings.get_headers(),
            timeout=settings.request_timeout,
            verify=settings.verify_ssl,
            follow_redirects=False,  # Prevent HTTP redirects that might downgrade protocol
        )

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            settings.rate_limit_requests,
            settings.rate_limit_period,
        )

        self._authenticated = False
        self._site_id_cache: dict[str, str] = {}
        # Cache for site UUID -> internalReference mapping (needed for local API)
        self._site_uuid_to_name: dict[str, str] = {}

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

    def _translate_endpoint(self, endpoint: str) -> str:
        """Translate endpoints based on API type.
        
        This method handles endpoint translation for different API modes:
        - cloud-v1: Stable v1 API (no translation for /ea/ endpoints, maps to /v1/)
        - cloud-ea: Early Access API (no translation needed)
        - local: Gateway API (translates cloud format to local format)
        
        Args:
            endpoint: API endpoint (e.g., /ea/sites/{site_id}/devices or /v1/hosts)
        
        Returns:
            Translated endpoint appropriate for the configured API type
        
        Examples:
            Cloud EA: /ea/sites/default/devices -> /ea/sites/default/devices (unchanged)
            Cloud V1: /v1/hosts -> /v1/hosts (unchanged)
            Local: /ea/sites/default/devices -> /proxy/network/api/s/default/devices
            Local: /ea/sites -> /proxy/network/integration/v1/sites (special case)
        """
        if self.settings.api_type in (APIType.CLOUD_V1, APIType.CLOUD_EA):
            # Cloud APIs - no translation needed
            return endpoint
        
        # Local API - translate cloud format to local format
        import re
        
        # Special case: /ea/sites (without site_id) -> Integration API
        if endpoint == "/ea/sites":
            return "/proxy/network/integration/v1/sites"
        
        # Pattern: /ea/sites/{site_id}/{rest_of_path}
        # Transform to: /proxy/network/api/s/{site_name}/{local_path}
        # Note: Local API uses site names (e.g., 'default'), not UUIDs
        # AND different endpoint paths than cloud API
        match = re.match(r'^/ea/sites/([^/]+)/(.+)$', endpoint)
        if match:
            site_id, cloud_path = match.groups()
            # Translate UUID to site name if we have the mapping
            site_name = self._site_uuid_to_name.get(site_id, site_id)
            if site_id != site_name:
                self.logger.debug(f"Translated site ID: {site_id} -> {site_name}")
            
            # Map cloud API paths to local API paths
            # Cloud API uses different endpoint naming than local API
            path_mapping = {
                "devices": "stat/device",
                "sta": "stat/sta",  # clients
                "rest/networkconf": "rest/networkconf",  # VLANs/networks
            }
            
            local_path = path_mapping.get(cloud_path, cloud_path)
            if cloud_path != local_path:
                self.logger.debug(f"Translated path: {cloud_path} -> {local_path}")
            
            return f"/proxy/network/api/s/{site_name}/{local_path}"
        
        # Pattern: /ea/sites/{site_id} (no trailing path)
        match = re.match(r'^/ea/sites/([^/]+)$', endpoint)
        if match:
            site_id = match.group(1)
            # Translate UUID to site name if we have the mapping
            site_name = self._site_uuid_to_name.get(site_id, site_id)
            if site_id != site_name:
                self.logger.debug(f"Translated site ID: {site_id} -> {site_name}")
            return f"/proxy/network/api/s/{site_name}/self"
        
        # If no pattern matches, check if it's already a local endpoint
        if endpoint.startswith("/proxy/network/"):
            return endpoint
        
        # If not recognized, return as-is and log warning
        self.logger.warning(f"Endpoint does not match known patterns: {endpoint}")
        return endpoint

    async def authenticate(self) -> None:
        """Authenticate with the UniFi API.

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Test authentication with a simple API call
            # Use appropriate endpoint based on API type
            if self.settings.api_type == APIType.CLOUD_V1:
                test_endpoint = "/v1/hosts"  # V1 stable API
            else:
                test_endpoint = "/ea/sites"  # EA API or local (will be auto-translated)

            response = await self._request("GET", test_endpoint)
            
            # Handle both dict and list responses
            # Local API (after normalization) returns list directly
            # Cloud API returns dict with "meta", "data", etc.
            if isinstance(response, list):
                # List response means we got data successfully (local API)
                self._authenticated = True
                # Build site UUID -> name mapping for local API
                if self.settings.api_type == APIType.LOCAL:
                    self._build_site_uuid_map(response)
            elif isinstance(response, dict):
                # Dict response - check for success indicators
                self._authenticated = (
                    response.get("meta", {}).get("rc") == "ok"
                    or response.get("data") is not None
                    or response.get("count") is not None
                )
            else:
                self._authenticated = False
                
            self.logger.info(f"Successfully authenticated with UniFi API (response type: {type(response).__name__})")
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate with UniFi API: {e}") from e
    
    def _build_site_uuid_map(self, sites: list[dict[str, Any]]) -> None:
        """Build a mapping of site UUIDs to internal reference names.
        
        This is required for local API, which uses site names (e.g., 'default')
        instead of UUIDs in endpoint paths.
        
        Args:
            sites: List of site objects from /ea/sites endpoint
        """
        self._site_uuid_to_name.clear()
        for site in sites:
            site_id = site.get("id")
            internal_ref = site.get("internalReference")
            if site_id and internal_ref:
                self._site_uuid_to_name[site_id] = internal_ref
        
        self.logger.info(f"Built site UUID mapping: {len(self._site_uuid_to_name)} sites")

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
            # Automatically translate endpoint based on API type
            translated_endpoint = self._translate_endpoint(endpoint)
            
            # ENHANCED LOGGING - Use INFO level to ensure visibility
            if endpoint != translated_endpoint:
                self.logger.info(f"Endpoint translation: {endpoint} -> {translated_endpoint}")
            
            # Construct full URL explicitly to ensure HTTPS protocol is preserved
            # httpx's base_url joining can have issues with protocol handling
            full_url = f"{self.settings.base_url}{translated_endpoint}" if translated_endpoint.startswith("/") else translated_endpoint
            
            # CRITICAL: Ensure HTTPS scheme - force replace http:// with https://
            if full_url.startswith("http://"):
                full_url = full_url.replace("http://", "https://", 1)
                self.logger.warning(f"Force-corrected HTTP to HTTPS: {full_url}")
            
            # ENHANCED LOGGING - Show actual URL being requested
            self.logger.info(f"Making {method} request to: {full_url}")
            
            response = await self.client.request(
                method=method,
                url=full_url,
                params=params,
                json=json_data,
            )

            duration_ms = (time.time() - start_time) * 1000

            # Log request if enabled
            if self.settings.log_api_requests:
                log_api_request(
                    self.logger,
                    method=method,
                    url=translated_endpoint,  # Log the translated endpoint, not the original
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

            # Parse response - handle empty responses from local gateway
            try:
                if response.text and response.text.strip():
                    json_response: dict[str, Any] = response.json()
                    
                    # Normalize response format based on API type
                    # Cloud V1 API returns: {"data": [...], "httpStatusCode": 200, "traceId": "..."}
                    # Local API returns: {"data": [...], "count": N, "totalCount": N}
                    # Cloud EA API returns: {...} or [...] directly
                    if isinstance(json_response, dict) and "data" in json_response:
                        # Both cloud v1 and local API wrap data in a "data" field
                        data = json_response["data"]
                        api_type = self.settings.api_type.value if hasattr(self.settings.api_type, 'value') else str(self.settings.api_type)
                        self.logger.debug(f"Normalized {api_type} API response: extracted {len(data) if isinstance(data, list) else 'N/A'} items")
                        # Return the data directly for consistency across all APIs
                        # If data is a list, return it; if single object, return as-is
                        return data if isinstance(data, list) else {"data": data}
                else:
                    # Empty response body - treat as success with empty data
                    self.logger.debug(f"Empty response body for {endpoint}, returning empty dict")
                    json_response = {}
                return json_response
            except (ValueError, json.JSONDecodeError) as e:
                # Invalid JSON - log and return empty dict for successful status codes
                self.logger.warning(f"Invalid JSON in response for {endpoint}: {e}")
                return {}

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

    @staticmethod
    def _looks_like_uuid(value: str | None) -> bool:
        """Determine whether a string value appears to be a UUID."""
        if not value:
            return False

        try:
            UUID(value)
            return True
        except (ValueError, TypeError):
            return False

    async def resolve_site_id(self, site_identifier: str | None) -> str:
        """Resolve a user-provided site identifier to the controller's UUID format.

        Args:
            site_identifier: Friendly site identifier (e.g., "default" or UUID)

        Returns:
            Resolved UUID for the site (or the original identifier for cloud API)

        Raises:
            ResourceNotFoundError: If the site cannot be located
        """
        if not site_identifier:
            site_identifier = self.settings.default_site

        if self.settings.api_type == APIType.CLOUD or self._looks_like_uuid(site_identifier):
            return site_identifier

        cached = self._site_id_cache.get(site_identifier)
        if cached:
            return cached

        sites_endpoint = self.settings.get_integration_path("sites")
        response = await self.get(sites_endpoint)
        sites = response.get("data", response.get("sites", []))

        for site in sites:
            site_id = site.get("id") or site.get("_id")
            if not site_id:
                continue

            identifiers = {
                site_id,
                site.get("internalReference"),
                site.get("name"),
                site.get("shortName"),
            }

            if site_identifier in {value for value in identifiers if value}:
                self._site_id_cache[site_identifier] = site_id
                return site_id

        raise ResourceNotFoundError("site", site_identifier)
