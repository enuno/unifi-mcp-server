"""Site Manager API client for multi-site management."""

from typing import Any, cast

import httpx

from ..config import Settings
from ..utils import APIError, AuthenticationError, NetworkError, ResourceNotFoundError, get_logger

logger = get_logger(__name__)

#: A decoded JSON reply: most Site Manager endpoints answer with an object, but
#: endpoints reached through the Cloud Connector proxy can answer with an array.
JSONBody = dict[str, Any] | list[Any]


def _object(value: Any) -> dict[str, Any]:
    """Use an empty object for absent version-specific response sections."""
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    """Accept a reported number, excluding booleans and missing values."""
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


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

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> JSONBody:
        """Make a GET request to Site Manager API.

        Args:
            endpoint: API endpoint path (without /v1/ prefix)
            params: Query parameters

        Returns:
            The decoded JSON reply: an object, or an array for endpoints that
            answer with one (many Cloud Connector proxy paths do)

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

            return cast(JSONBody, response.json())

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
    ) -> JSONBody:
        """Make a mutating (POST/PUT/PATCH/DELETE) request to Site Manager API.

        Args:
            method: HTTP method (post, put, patch, delete)
            endpoint: API endpoint path (without /v1/ prefix)
            json_data: Optional request body

        Returns:
            The decoded JSON reply: an object, or an array for endpoints that
            answer with one (many Cloud Connector proxy paths do)

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
                return cast(JSONBody, response.json())
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

    async def post(self, endpoint: str, json_data: dict[str, Any] | None = None) -> JSONBody:
        """Make a POST request to Site Manager API."""
        return await self._mutate("post", endpoint, json_data)

    async def put(self, endpoint: str, json_data: dict[str, Any] | None = None) -> JSONBody:
        """Make a PUT request to Site Manager API."""
        return await self._mutate("put", endpoint, json_data)

    async def patch(self, endpoint: str, json_data: dict[str, Any] | None = None) -> JSONBody:
        """Make a PATCH request to Site Manager API."""
        return await self._mutate("patch", endpoint, json_data)

    async def delete(self, endpoint: str) -> JSONBody:
        """Make a DELETE request to Site Manager API."""
        return await self._mutate("delete", endpoint)

    async def _get_object(self, endpoint: str, params: dict[str, Any] | None = None) -> JSONBody:
        """GET an endpoint documented to answer with a JSON object.

        Some deployments answer these endpoints (``hosts``, ``vantage-points``
        and others) with a bare array instead. The tools in
        ``src/tools/site_manager.py`` handle both shapes, so the reply is
        passed through as is and typed as such, rather than rejected.
        """
        return await self.get(endpoint, params=params)

    async def list_sites(self, limit: int | None = None, offset: int | None = None) -> JSONBody:
        """List all sites from Site Manager API.

        Args:
            limit: Maximum number of sites to return
            offset: Number of sites to skip

        Returns:
            Response with sites list
        """
        params = {"limit": limit, "offset": offset}
        return await self._get_object(
            "sites", params={k: v for k, v in params.items() if v is not None}
        )

    async def get_site_health(self, site_id: str | None = None) -> JSONBody:
        """Summarize the documented sites response, including all pages.

        Site Manager has no ``/sites/health`` endpoint. Its ``statistics``
        shape varies by Network version, so absent values stay unknown.
        """
        sites: list[dict[str, Any]] = []
        next_token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            response = await self._get_object(
                "sites", params={"nextToken": next_token} if next_token else None
            )
            if not isinstance(response, dict) or not isinstance(response.get("data"), list):
                raise APIError("Unexpected Site Manager sites response")
            sites.extend(response["data"])
            next_token = response.get("nextToken")
            if next_token is None or next_token == "":
                break
            if not isinstance(next_token, str) or next_token in seen_tokens:
                raise APIError("Invalid Site Manager sites pagination token")
            seen_tokens.add(next_token)

        summaries = [self._site_summary(site) for site in sites]
        if site_id is None:
            return summaries
        for summary in summaries:
            if summary["site_id"] == site_id:
                return summary
        raise ResourceNotFoundError("site", site_id)

    @staticmethod
    def _site_summary(site: Any) -> dict[str, Any]:
        if not isinstance(site, dict) or not isinstance(site.get("siteId"), str):
            raise APIError("Unexpected Site Manager site entry")
        meta = _object(site.get("meta"))
        legacy_site = _object(site.get("site"))
        statistics = _object(site.get("statistics"))
        counts = _object(statistics.get("counts"))
        percentages = _object(statistics.get("percentages"))

        def count(name: str) -> int | None:
            value = counts.get(name)
            return value if type(value) is int and value >= 0 else None

        total = count("totalDevice")
        offline = count("offlineDevice")
        gateway_total = count("gatewayDevice")
        gateway_offline = count("offlineGatewayDevice")
        wifi_clients = count("wifiClient")
        wired_clients = count("wiredClient")
        issues = statistics.get("internetIssues")
        status = "unknown"
        reason = None
        if (
            gateway_total is not None
            and gateway_total > 0
            and gateway_offline is not None
            and gateway_offline >= gateway_total
        ):
            status = "down"
            reason = "all_gateways_offline"
        elif (offline is not None and offline > 0) or (
            gateway_offline is not None and gateway_offline > 0
        ):
            status = "degraded"
            reason = "offline_devices"
        elif total is not None and total > 0 and offline == 0 and gateway_offline == 0:
            status = "healthy"
            reason = "no_offline_devices"

        issue_types: list[str] | None = None
        if isinstance(issues, list):
            names: set[str] = set()
            for issue in issues:
                if isinstance(issue, str):
                    names.add(issue)
                elif isinstance(issue, dict):
                    names.update(key for key, value in issue.items() if value is True)
                    if isinstance(issue.get("type"), str):
                        names.add(issue["type"])
            issue_types = sorted(names)

        return {
            "site_id": site["siteId"],
            "site_name": meta.get("name") or legacy_site.get("name") or site["siteId"],
            "status": status,
            "status_source": "device_counts" if status != "unknown" else None,
            "status_reason": reason,
            "reported_internet_issue_count": len(issues) if isinstance(issues, list) else None,
            "reported_internet_issue_types": issue_types,
            "devices_total": total,
            "devices_online": (
                max(total - offline, 0) if total is not None and offline is not None else None
            ),
            "clients_active": (
                wifi_clients + wired_clients
                if wifi_clients is not None and wired_clients is not None
                else None
            ),
            "uptime_percentage": _number(percentages.get("wanUptime")),
            "last_updated": None,
        }

    async def get_internet_health(self, site_id: str | None = None) -> JSONBody:
        """Read the latest documented 5-minute ISP metric for each site.

        This is a reported metric interval, not a requested connection test.
        Zero upload/download values are treated as unavailable because the
        API can report zero while the connection is in use.
        """
        response = await self._get_object("isp-metrics/5m", params={"duration": "24h"})
        if not isinstance(response, dict) or not isinstance(response.get("data"), list):
            raise APIError("Unexpected Site Manager ISP metrics response")

        metrics: list[dict[str, Any]] = []
        for item in response["data"]:
            if not isinstance(item, dict) or not isinstance(item.get("siteId"), str):
                raise APIError("Unexpected Site Manager ISP metrics entry")
            periods = item.get("periods")
            periods = periods if isinstance(periods, list) else []
            reported = [
                period
                for period in periods
                if isinstance(period, dict) and isinstance(period.get("metricTime"), str)
            ]
            latest = max(reported, key=lambda period: period["metricTime"]) if reported else {}
            data = _object(latest.get("data"))
            wan = _object(data.get("wan"))

            download = _number(wan.get("download_kbps"))
            upload = _number(wan.get("upload_kbps"))
            metrics.append(
                {
                    "site_id": item["siteId"],
                    "latency_ms": _number(wan.get("avgLatency")),
                    "packet_loss_percent": _number(wan.get("packetLoss")),
                    "jitter_ms": None,
                    "bandwidth_up_mbps": (
                        upload / 1000 if upload is not None and upload > 0 else None
                    ),
                    "bandwidth_down_mbps": (
                        download / 1000 if download is not None and download > 0 else None
                    ),
                    "uptime_percentage": _number(wan.get("uptime")),
                    "status": "unknown",
                    "last_reported": latest.get("metricTime"),
                    "last_tested": None,
                }
            )

        if site_id is None:
            return metrics
        for metric in metrics:
            if metric["site_id"] == site_id:
                return metric
        return {
            "site_id": site_id,
            "latency_ms": None,
            "packet_loss_percent": None,
            "jitter_ms": None,
            "bandwidth_up_mbps": None,
            "bandwidth_down_mbps": None,
            "uptime_percentage": None,
            "status": "unknown",
            "last_reported": None,
            "last_tested": None,
        }

    async def list_vantage_points(self) -> JSONBody:
        """List all Vantage Points.

        Returns:
            Response with Vantage Points list
        """
        return await self._get_object("vantage-points")

    # ISP Metrics endpoints (added 2026-02-16)
    async def get_isp_metrics(self, site_id: str) -> JSONBody:
        """Get ISP metrics for a site.

        Args:
            site_id: Site identifier

        Returns:
            ISP metrics data
        """
        return await self._get_object(f"sites/{site_id}/isp/metrics")

    async def query_isp_metrics(
        self,
        site_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> JSONBody:
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
        return await self._get_object(
            "isp/metrics", params={k: v for k, v in params.items() if v is not None}
        )

    # SD-WAN endpoints (added 2026-02-16)
    async def list_sdwan_configs(self) -> JSONBody:
        """List all SD-WAN configurations.

        Returns:
            Response with SD-WAN configurations list
        """
        return await self._get_object("sd-wan-configs")

    async def get_sdwan_config(self, config_id: str) -> JSONBody:
        """Get SD-WAN configuration by ID.

        Args:
            config_id: Configuration identifier

        Returns:
            SD-WAN configuration data
        """
        return await self._get_object(f"sd-wan-configs/{config_id}")

    async def get_sdwan_config_status(self, config_id: str) -> JSONBody:
        """Get SD-WAN configuration deployment status.

        Args:
            config_id: Configuration identifier

        Returns:
            SD-WAN configuration status data
        """
        return await self._get_object(f"sd-wan-configs/{config_id}/status")

    # Host Management endpoints (added 2026-02-16)
    async def list_hosts(self, limit: int | None = None, offset: int | None = None) -> JSONBody:
        """List all managed hosts/consoles.

        Args:
            limit: Maximum number of hosts to return
            offset: Number of hosts to skip

        Returns:
            Response with hosts list
        """
        params = {"limit": limit, "offset": offset}
        return await self._get_object(
            "hosts", params={k: v for k, v in params.items() if v is not None}
        )

    async def get_host(self, host_id: str) -> JSONBody:
        """Get host details by ID.

        Args:
            host_id: Host identifier

        Returns:
            Host details
        """
        return await self._get_object(f"hosts/{host_id}")

    # Version Control endpoint (added 2026-02-16)
    async def get_version_control(self) -> JSONBody:
        """Get API version control information.

        Returns:
            Version control data
        """
        return await self._get_object("version")
