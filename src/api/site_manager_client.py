"""Site Manager API client for multi-site management."""

from typing import Any

import httpx

from ..config import Settings
from ..utils import APIError, AuthenticationError, NetworkError, ResourceNotFoundError, get_logger

logger = get_logger(__name__)


class SiteManagerClient:
    """Client for UniFi Site Manager API (api.ui.com/v1/)."""

    def __init__(self, settings: Settings) -> None:
        """Initialize Site Manager API client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)

        # Site Manager API base URL
        base_url = "https://api.ui.com/v1/"

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers=settings.get_headers(),
            timeout=settings.request_timeout,
            verify=True,  # Always verify SSL for Site Manager API
        )

        self._authenticated = False

    async def __aenter__(self) -> "SiteManagerClient":
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
        """Authenticate with the Site Manager API.

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Test authentication with sites endpoint
            response = await self.client.get("/v1/sites")
            if response.status_code == 200:
                self._authenticated = True
                self.logger.info("Successfully authenticated with Site Manager API")
            else:
                raise AuthenticationError(f"Authentication failed: {response.status_code}")
        except Exception as e:
            self.logger.error(f"Site Manager authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate with Site Manager API: {e}") from e

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request to Site Manager API.

        Args:
            endpoint: API endpoint path (without /v1/ prefix)
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            APIError: If API returns an error
            AuthenticationError: If authentication fails
        """
        if not self._authenticated:
            await self.authenticate()

        try:
            # Ensure endpoint starts with /v1/
            if not endpoint.startswith("/v1/"):
                endpoint = f"/v1/{endpoint.lstrip('/')}"

            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Site Manager API authentication failed") from e
            elif e.response.status_code == 404:
                raise ResourceNotFoundError("resource", endpoint) from e
            else:
                raise APIError(
                    message=f"Site Manager API error: {e.response.text}",
                    status_code=e.response.status_code,
                ) from e
        except httpx.NetworkError as e:
            raise NetworkError(f"Network communication failed: {e}") from e
        except Exception as e:
            self.logger.error(f"Unexpected error in Site Manager API request: {e}")
            raise APIError(f"Unexpected error: {e}") from e

    async def list_sites(
        self, limit: int | None = None, offset: int | None = None
    ) -> dict[str, Any]:
        """List all sites from Site Manager API.

        Args:
            limit: Maximum number of sites to return
            offset: Number of sites to skip

        Returns:
            Response with sites list
        """
        params = {}
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset

        return await self.get("sites", params=params)

    async def get_site_health(self, site_id: str | None = None) -> dict[str, Any]:
        """Get health metrics for a site or all sites.

        Args:
            site_id: Optional site identifier. If None, returns health for all sites.

        Returns:
            Health metrics
        """
        endpoint = "sites/health"
        if site_id:
            endpoint = f"sites/{site_id}/health"

        return await self.get(endpoint)

    async def get_internet_health(self, site_id: str | None = None) -> dict[str, Any]:
        """Get internet health metrics.

        Args:
            site_id: Optional site identifier. If None, returns aggregate internet health.

        Returns:
            Internet health metrics
        """
        endpoint = "internet/health"
        if site_id:
            endpoint = f"sites/{site_id}/internet/health"

        return await self.get(endpoint)

    async def list_vantage_points(self) -> dict[str, Any]:
        """List all Vantage Points.

        Returns:
            Response with Vantage Points list
        """
        return await self.get("vantage-points")
