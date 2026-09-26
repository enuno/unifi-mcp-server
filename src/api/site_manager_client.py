"""Site Manager API client for multi-site management."""

from typing import Any

import httpx

from ..config import Settings
from ..utils import APIError, AuthenticationError, NetworkError, ResourceNotFoundError, get_logger
from .client import RateLimiter

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

        # Initialize HTTP client with Site Manager-specific API key
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers=settings.get_headers(settings.resolved_site_manager_api_key),
            timeout=settings.request_timeout,
            verify=True,  # Always verify SSL for Site Manager API
        )

        self.rate_limiter = RateLimiter(
            settings.rate_limit_requests,
            settings.rate_limit_period,
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
            await self.rate_limiter.acquire()
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
            await self.rate_limiter.acquire()
            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()

            return response.json()  # type: ignore[no-any-return]

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

    async def post(self, endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a POST request to Site Manager API.

        Args:
            endpoint: API endpoint path (without /v1/ prefix)
            data: Request body as dictionary

        Returns:
            Response data as dictionary

        Raises:
            APIError: If API returns an error
            AuthenticationError: If authentication fails
        """
        if not self._authenticated:
            await self.authenticate()

        try:
            await self.rate_limiter.acquire()
            response = await self.client.post(endpoint, json=data or {})
            response.raise_for_status()

            return response.json()  # type: ignore[no-any-return]

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
        # The Site Manager API paginates with pageSize/nextToken; it ignores
        # limit and has no offset parameter, so offset is accepted but unused.
        params = {"pageSize": limit} if limit is not None else None
        return await self.get("sites", params=params)

    async def get_site_health(self, site_id: str | None = None) -> dict[str, Any]:
        """Get health metrics for a site or all sites.

        The Site Manager API embeds statistics directly in the /v1/sites response;
        there is no separate /sites/health endpoint.

        Args:
            site_id: Optional site identifier. If None, returns all sites.

        Returns:
            Single site dict if site_id given, otherwise {"data": [<sites>]}
        """
        response = await self.get("sites")
        sites_raw = response.get("data", [])
        sites: list[dict[str, Any]] = [site for site in sites_raw if isinstance(site, dict)]

        if site_id:
            for site in sites:
                if site.get("siteId") == site_id:
                    return site
            raise ResourceNotFoundError("site", site_id)

        return response

    # ISP Metrics endpoints
    async def get_isp_metrics(
        self,
        metric_type: str = "5m",
        duration: str | None = None,
        begin_timestamp: str | None = None,
        end_timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Get ISP metrics by interval type.

        Args:
            metric_type: Interval — "5m" (5-min, 24h retention) or "1h" (hourly, 30d retention)
            duration: Shorthand window ("24h", "7d", "30d"). Cannot combine with timestamps.
            begin_timestamp: RFC3339 start. Cannot combine with duration.
            end_timestamp: RFC3339 end. Cannot combine with duration.

        Returns:
            ISP metrics response with nested periods data
        """
        params = {
            k: v
            for k, v in {
                "duration": duration,
                "beginTimestamp": begin_timestamp,
                "endTimestamp": end_timestamp,
            }.items()
            if v is not None
        }
        return await self.get(f"isp-metrics/{metric_type}", params=params or None)

    async def query_isp_metrics(
        self,
        metric_type: str = "5m",
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query ISP metrics for specific sites via POST.

        Args:
            metric_type: Interval — "5m" or "1h"
            body: Request body. Must contain {"sites": [{"hostId": ..., "siteId": ...}]}

        Returns:
            ISP metrics query results
        """
        return await self.post(f"isp-metrics/{metric_type}/query", data=body)

    # SD-WAN endpoints
    async def list_sdwan_configs(self) -> dict[str, Any]:
        """List all SD-WAN configurations.

        Returns:
            Response with SD-WAN configurations list
        """
        return await self.get("sd-wan-configs")

    async def get_sdwan_config(self, config_id: str) -> dict[str, Any]:
        """Get SD-WAN configuration by ID.

        Args:
            config_id: Configuration identifier

        Returns:
            SD-WAN configuration data
        """
        return await self.get(f"sd-wan-configs/{config_id}")

    async def get_sdwan_config_status(self, config_id: str) -> dict[str, Any]:
        """Get SD-WAN configuration deployment status.

        Args:
            config_id: Configuration identifier

        Returns:
            SD-WAN configuration status data
        """
        return await self.get(f"sd-wan-configs/{config_id}/status")

    # Host Management endpoints
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
        # The Site Manager API paginates with pageSize/nextToken; it ignores
        # limit and has no offset parameter, so offset is accepted but unused.
        params = {"pageSize": limit} if limit is not None else None
        return await self.get("hosts", params=params)

    async def get_host(self, host_id: str) -> dict[str, Any]:
        """Get host details by ID.

        Args:
            host_id: Host identifier

        Returns:
            Host details
        """
        return await self.get(f"hosts/{host_id}")

    # Devices endpoint (cross-site device listing)
    async def list_devices(self) -> dict[str, Any]:
        """List all devices across all hosts from Site Manager API.

        Returns:
            Response with hosts and their devices
        """
        return await self.get("devices")
