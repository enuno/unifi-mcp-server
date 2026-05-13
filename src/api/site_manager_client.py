"""Site Manager API client for multi-site management."""

from typing import Any, cast

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
            # Test authentication with sites endpoint (relative to base_url /v1/)
            response = await self.client.get("sites")
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
            # base_url already includes /v1/ - pass endpoint as relative path
            endpoint = endpoint.lstrip("/")

            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()

            return cast(dict[str, Any], response.json())

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

    async def _mutate(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a mutating (POST/PUT/PATCH/DELETE) request to Site Manager API.

        Args:
            method: HTTP method (post, put, patch, delete)
            endpoint: API endpoint path (without /v1/ prefix)
            json_data: Optional request body

        Returns:
            Response data as dictionary

        Raises:
            APIError: If API returns an error
            AuthenticationError: If authentication fails
        """
        if not self._authenticated:
            await self.authenticate()

        try:
            endpoint = endpoint.lstrip("/")
            http_method = getattr(self.client, method)
            if json_data is not None:
                response = await http_method(endpoint, json=json_data)
            else:
                response = await http_method(endpoint)
            response.raise_for_status()

            if response.content:
                return cast(dict[str, Any], response.json())
            return {}

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

    async def post(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a POST request to Site Manager API."""
        return await self._mutate("post", endpoint, json_data)

    async def put(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PUT request to Site Manager API."""
        return await self._mutate("put", endpoint, json_data)

    async def patch(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PATCH request to Site Manager API."""
        return await self._mutate("patch", endpoint, json_data)

    async def delete(self, endpoint: str) -> dict[str, Any]:
        """Make a DELETE request to Site Manager API."""
        return await self._mutate("delete", endpoint)

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
        params = {"limit": limit, "offset": offset}
        return await self.get("sites", params={k: v for k, v in params.items() if v is not None})

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

    # ISP Metrics endpoints (added 2026-02-16)
    async def get_isp_metrics(self, site_id: str) -> dict[str, Any]:
        """Get ISP metrics for a site.

        Args:
            site_id: Site identifier

        Returns:
            ISP metrics data
        """
        return await self.get(f"sites/{site_id}/isp/metrics")

    async def query_isp_metrics(
        self,
        site_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """Query ISP metrics with filters.

        Args:
            site_id: Optional site identifier (None for all sites)
            start_time: Optional start time (ISO format)
            end_time: Optional end time (ISO format)

        Returns:
            ISP metrics query results
        """
        params = {
            "site_id": site_id,
            "start_time": start_time,
            "end_time": end_time,
        }
        return await self.get(
            "isp/metrics", params={k: v for k, v in params.items() if v is not None}
        )

    # SD-WAN endpoints (added 2026-02-16)
    async def list_sdwan_configs(self) -> dict[str, Any]:
        """List all SD-WAN configurations.

        Returns:
            Response with SD-WAN configurations list
        """
        return await self.get("sdwan/configs")

    async def get_sdwan_config(self, config_id: str) -> dict[str, Any]:
        """Get SD-WAN configuration by ID.

        Args:
            config_id: Configuration identifier

        Returns:
            SD-WAN configuration data
        """
        return await self.get(f"sdwan/configs/{config_id}")

    async def get_sdwan_config_status(self, config_id: str) -> dict[str, Any]:
        """Get SD-WAN configuration deployment status.

        Args:
            config_id: Configuration identifier

        Returns:
            SD-WAN configuration status data
        """
        return await self.get(f"sdwan/configs/{config_id}/status")

    # Host Management endpoints (added 2026-02-16)
    async def list_hosts(
        self, limit: int | None = None, offset: int | None = None
    ) -> dict[str, Any]:
        """List all managed hosts/consoles.

        Args:
            limit: Maximum number of hosts to return
            offset: Number of hosts to skip

        Returns:
            Response with hosts list
        """
        params = {"limit": limit, "offset": offset}
        return await self.get("hosts", params={k: v for k, v in params.items() if v is not None})

    async def get_host(self, host_id: str) -> dict[str, Any]:
        """Get host details by ID.

        Args:
            host_id: Host identifier

        Returns:
            Host details
        """
        return await self.get(f"hosts/{host_id}")

    # Version Control endpoint (added 2026-02-16)
    async def get_version_control(self) -> dict[str, Any]:
        """Get API version control information.

        Returns:
            Version control data
        """
        return await self.get("version")
