"""UniFi API client with authentication, rate limiting, and error handling."""

import asyncio
import json
import time
from typing import Any
from uuid import UUID

import httpx
from pydantic import ValidationError as PydanticValidationError

from ..config import APIType, Settings
from ..models.site import SiteReference
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
        match = re.match(r"^/ea/sites/([^/]+)/(.+)$", endpoint)
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
        match = re.match(r"^/ea/sites/([^/]+)$", endpoint)
        if match:
            site_id = match.group(1)
            # Translate UUID to site name if we have the mapping
            site_name = self._site_uuid_to_name.get(site_id, site_id)
            if site_id != site_name:
                self.logger.debug(f"Translated site ID: {site_id} -> {site_name}")
            return f"/proxy/network/api/s/{site_name}/self"

        # Pattern: /proxy/network/v2/api/site/{site_id}/{rest}
        # The v2 API keys off the site short name and rejects UUIDs with
        # {"errorCode":404,"message":"Site does not exist"}. Callers normally
        # hold the UUID that list_sites returns, so translate centrally here
        # rather than relying on every call site to remember. The lookup is
        # idempotent -- a short name maps to itself -- so callers that already
        # normalize are unaffected.
        match = re.match(r"^(/proxy/network/v2/api/site/)([^/]+)(/.*)?$", endpoint)
        if match:
            prefix, site_id, rest = match.groups()
            site_name = self._site_uuid_to_name.get(site_id, site_id)
            if site_id != site_name:
                self.logger.debug(f"Translated v2 site ID: {site_id} -> {site_name}")
            return f"{prefix}{site_name}{rest or ''}"

        # If no pattern matches, check if it's already a local endpoint
        if endpoint.startswith("/proxy/network/"):
            return endpoint

        # Integration API endpoints need /proxy/network prefix on local gateway
        if endpoint.startswith("/integration/"):
            return f"/proxy/network{endpoint}"

        # V1 API endpoints need /proxy/network prefix on local gateway
        if endpoint.startswith("/v1/"):
            return f"/proxy/network{endpoint}"

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
            elif isinstance(response, dict):
                # Dict response - check for success indicators
                self._authenticated = (
                    response.get("meta", {}).get("rc") == "ok"
                    or response.get("data") is not None
                    or response.get("count") is not None
                )
            else:
                self._authenticated = False

            # Build site UUID -> name mapping for local API.
            # /ea/sites arrives either as a bare list or wrapped as {"data": [...]},
            # depending on how _request normalizes the payload. Accept both, or the
            # map silently stays empty and every UUID -> site name lookup no-ops.
            if self.settings.api_type == APIType.LOCAL:
                sites = self._extract_site_list(response)
                if sites is not None:
                    self._build_site_uuid_map(sites)

            self.logger.info(
                f"Successfully authenticated with UniFi API (response type: {type(response).__name__})"
            )
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate with UniFi API: {e}") from e

    @staticmethod
    def _extract_site_list(response: Any) -> list[Any] | None:
        """Pull the site list out of an /ea/sites response envelope.

        Envelope handling only: the entries themselves are validated as
        :class:`SiteReference` in :meth:`_build_site_uuid_map`.

        Args:
            response: Raw response, either a bare list or ``{"data": [...]}``

        Returns:
            The list of site entries, or None if the response carries none
        """
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            data = response.get("data")
            if isinstance(data, list):
                return data
        return None

    def _build_site_uuid_map(self, sites: list[Any]) -> None:
        """Build a mapping of site UUIDs to internal reference names.

        This is required for local API, which uses site names (e.g., 'default')
        instead of UUIDs in endpoint paths. Entries are validated through
        :class:`SiteReference`; one malformed entry is skipped rather than
        failing authentication for every other site.

        Args:
            sites: List of site objects from /ea/sites endpoint
        """
        self._site_uuid_to_name.clear()
        for site in sites:
            try:
                reference = SiteReference.model_validate(site)
            except PydanticValidationError as exc:
                self.logger.warning(f"Skipping unparsable site entry: {exc}")
                continue
            if reference.internal_reference:
                self._site_uuid_to_name[reference.id] = reference.internal_reference

        self.logger.info(f"Built site UUID mapping: {len(self._site_uuid_to_name)} sites")

    def _retry_or_give_up(self, started_at: float, wait: float, reason: str) -> float:
        """Decide whether another retry fits inside the wall-clock budget.

        Retries used to be bounded only by attempt count, so one logical
        request could legitimately burn ``(max_retries + 1) x request_timeout``
        plus backoff — ~127s at the defaults — and a tool that authenticates
        first stacks two of those, which is how issue #97's four-minute hangs
        happen. The budget bounds elapsed time, not attempts.

        Args:
            started_at: ``time.monotonic()`` captured on the first attempt
            wait: Seconds the caller intends to sleep before retrying
            reason: What went wrong, for the giving-up message

        Returns:
            ``wait``, when the retry (including its sleep) fits the budget

        Raises:
            NetworkError: When the budget is already spent
        """
        budget = self.settings.retry_total_timeout
        elapsed = time.monotonic() - started_at
        if elapsed + wait >= budget:
            raise NetworkError(
                f"Giving up after {elapsed:.0f}s of retries ({reason}); "
                f"retry budget is {budget}s (UNIFI_RETRY_TOTAL_TIMEOUT)"
            )
        return wait

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        retry_count: int = 0,
        started_at: float | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with retries and error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON request body
            retry_count: Current retry attempt number
            started_at: Monotonic timestamp of the first attempt, threaded
                through retries so the total-elapsed budget survives recursion

        Returns:
            Response data as dictionary

        Raises:
            APIError: If API returns an error
            RateLimitError: If rate limit is exceeded
            NetworkError: If network communication fails
        """
        if started_at is None:
            started_at = time.monotonic()

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
            full_url = (
                f"{self.settings.base_url}{translated_endpoint}"
                if translated_endpoint.startswith("/")
                else translated_endpoint
            )

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
                    self._retry_or_give_up(started_at, retry_after, "rate limited")
                    self.logger.warning(f"Rate limited, retrying after {retry_after}s")
                    await asyncio.sleep(retry_after)
                    return await self._request(
                        method, endpoint, params, json_data, retry_count + 1, started_at
                    )

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
                        api_type = (
                            self.settings.api_type.value
                            if hasattr(self.settings.api_type, "value")
                            else str(self.settings.api_type)
                        )
                        self.logger.debug(
                            f"Normalized {api_type} API response: extracted {len(data) if isinstance(data, list) else 'N/A'} items"
                        )
                        # Return a normalized dict with data key for consistency across APIs
                        # Always return a dict[str, Any]
                        return {"data": data}
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
                self._retry_or_give_up(started_at, backoff, "request timeouts")
                self.logger.warning(f"Request timeout, retrying in {backoff}s")
                await asyncio.sleep(backoff)
                return await self._request(
                    method, endpoint, params, json_data, retry_count + 1, started_at
                )

            raise NetworkError(f"Request timeout: {e}") from e

        except httpx.NetworkError as e:
            # Retry on network error
            if retry_count < self.settings.max_retries:
                backoff = self.settings.retry_backoff_factor**retry_count
                self._retry_or_give_up(started_at, backoff, "network errors")
                self.logger.warning(f"Network error, retrying in {backoff}s")
                await asyncio.sleep(backoff)
                return await self._request(
                    method, endpoint, params, json_data, retry_count + 1, started_at
                )

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
        # Handle both list (when API returns {"data": [...]}) and dict responses
        if isinstance(response, list):
            sites = response
        else:
            sites = response.get("data", response.get("sites", []))

        for site in sites:
            if not isinstance(site, dict):
                self.logger.warning(
                    f"Skipping non-dict site entry in resolve: {type(site).__name__}"
                )
                continue
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
                site_id_str = str(site_id)
                self._site_id_cache[site_identifier] = site_id_str
                return site_id_str

        raise ResourceNotFoundError("site", site_identifier)

    # Backup and Restore Operations

    async def trigger_backup(
        self,
        site_id: str,
        backup_type: str = "network",
        days: int = -1,
    ) -> dict[str, Any]:
        """Trigger a backup operation on the UniFi controller.

        Args:
            site_id: Site identifier
            backup_type: Type of backup ("network" for network-only, "system" for full)
            days: Number of days to retain backup (-1 for indefinite)

        Returns:
            Backup operation response including download URL

        Note:
            For local API, use: /proxy/network/api/s/{site}/cmd/backup
            Response contains a URL in data.url for downloading the backup file
        """
        site_id = await self.resolve_site_id(site_id)

        # For local API, translate to local endpoint format
        if self.settings.api_type == APIType.LOCAL:
            # Use site name (e.g., "default") not UUID for local API
            site_name = self._site_uuid_to_name.get(site_id, site_id)
            endpoint = f"/proxy/network/api/s/{site_name}/cmd/backup"
        else:
            # Cloud API
            endpoint = f"/ea/sites/{site_id}/cmd/backup"

        payload = {
            "cmd": "backup",
            "days": str(days),
        }

        return await self.post(endpoint, json_data=payload)

    async def list_backups(self, site_id: str) -> list[dict[str, Any]]:
        """List all available backups for a site.

        Args:
            site_id: Site identifier

        Returns:
            List of backup metadata dictionaries

        Note:
            For local API: POST /proxy/network/api/s/{site}/cmd/backup
            with body {"cmd": "list-backups"}
        """
        site_id = await self.resolve_site_id(site_id)

        # Backups are listed with the backup command, scoped to a site. The
        # previous site-less GET /api/backup/list-backups had no site context,
        # so the controller rejected it with api.err.NoSiteContext -- carried
        # on an HTTP 401, which this client then reported as an
        # authentication failure. Verified live on Network 10.5.67.
        if self.settings.api_type == APIType.LOCAL:
            site_name = self._site_uuid_to_name.get(site_id, site_id)
            endpoint = f"/proxy/network/api/s/{site_name}/cmd/backup"
        else:
            # Cloud API
            endpoint = f"/ea/sites/{site_id}/cmd/backup"

        response = await self.post(endpoint, json_data={"cmd": "list-backups"})

        # Handle different response formats
        if isinstance(response, list):
            return response
        data = (
            response.get("data", response.get("backups", [])) if isinstance(response, dict) else []
        )
        if isinstance(data, list):
            return data
        return []

    async def download_backup(
        self,
        site_id: str,
        backup_filename: str,
    ) -> bytes:
        """Download a backup file.

        Args:
            site_id: Site identifier
            backup_filename: Backup filename to download

        Returns:
            Backup file content as bytes

        Note:
            This method downloads the actual backup file content.
            For local API: /proxy/network/data/backup/{filename}
        """
        site_id = await self.resolve_site_id(site_id)

        # For local API
        if self.settings.api_type == APIType.LOCAL:
            endpoint = f"/proxy/network/data/backup/{backup_filename}"
        else:
            # Cloud API
            endpoint = f"/ea/sites/{site_id}/backups/{backup_filename}/download"

        # Use direct HTTP client for binary download
        full_url = f"{self.settings.base_url}{endpoint}"

        response = await self.client.get(full_url)
        response.raise_for_status()

        return response.content

    async def delete_backup(
        self,
        site_id: str,
        backup_filename: str,
    ) -> dict[str, Any]:
        """Delete a specific backup file.

        Args:
            site_id: Site identifier
            backup_filename: Backup filename to delete

        Returns:
            Deletion confirmation response

        Note:
            For local API: DELETE /proxy/network/api/backup/delete-backup/{filename}
        """
        site_id = await self.resolve_site_id(site_id)

        # For local API
        if self.settings.api_type == APIType.LOCAL:
            endpoint = f"/proxy/network/api/backup/delete-backup/{backup_filename}"
        else:
            # Cloud API
            endpoint = f"/ea/sites/{site_id}/backups/{backup_filename}"

        return await self.delete(endpoint)

    async def restore_backup(
        self,
        site_id: str,
        backup_filename: str,
    ) -> dict[str, Any]:
        """Restore the controller from a backup file.

        Args:
            site_id: Site identifier
            backup_filename: Backup filename to restore from

        Returns:
            Restore operation response

        Warning:
            This is a destructive operation that will restore the controller
            to the state captured in the backup. Use with extreme caution.

        Note:
            For local API: POST /proxy/network/api/backup/restore
            Controller may restart during restore process
        """
        site_id = await self.resolve_site_id(site_id)

        # For local API
        if self.settings.api_type == APIType.LOCAL:
            endpoint = "/proxy/network/api/backup/restore"
            payload = {"filename": backup_filename}
        else:
            # Cloud API
            endpoint = f"/ea/sites/{site_id}/backups/{backup_filename}/restore"
            payload = {"backup_id": backup_filename}

        return await self.post(endpoint, json_data=payload)

    async def get_backup_status(
        self,
        site_id: str,
        operation_id: str,
    ) -> dict[str, Any]:
        """Get the status of an ongoing backup operation.

        Args:
            site_id: Site identifier
            operation_id: Backup operation ID

        Returns:
            Operation status including progress and any errors
        """
        site_id = await self.resolve_site_id(site_id)

        # For local API
        if self.settings.api_type == APIType.LOCAL:
            site_name = self._site_uuid_to_name.get(site_id, site_id)
            endpoint = f"/proxy/network/api/s/{site_name}/stat/backup/{operation_id}"
        else:
            # Cloud API
            endpoint = f"/ea/sites/{site_id}/operations/{operation_id}"

        return await self.get(endpoint)

    async def get_restore_status(
        self,
        operation_id: str,
    ) -> dict[str, Any]:
        """Get the status of an ongoing restore operation.

        Args:
            operation_id: Restore operation ID

        Returns:
            Operation status including progress, step, and any errors
        """
        # UniFi does not expose a dedicated restore-status endpoint; return a
        # response that honestly reflects this limitation rather than
        # falsely claiming the restore is complete.
        return {
            "status": "not_supported",
            "message": "Restore status tracking is not available via the UniFi API.",
            "operation_id": operation_id,
        }

    async def configure_backup_schedule(
        self,
        site_id: str,
        backup_type: str = "network",
        frequency: str = "daily",
        time_of_day: str = "02:00",
        enabled: bool = True,
        retention_days: int = 30,
        max_backups: int = 10,
        day_of_week: str | int | None = None,
        day_of_month: int | None = None,
        cloud_backup_enabled: bool = False,
    ) -> dict[str, Any]:
        """Configure the automated backup schedule for a site.

        Args:
            site_id: Site identifier
            backup_type: Type of backup ("network" or "system")
            frequency: Schedule frequency ("daily", "weekly", "monthly")
            time_of_day: Time to run backup in HH:MM format
            enabled: Whether the schedule is active
            retention_days: Number of days to keep backups
            max_backups: Maximum number of backups to retain
            day_of_week: Day of week for weekly schedules; a day name
                ("monday") or the tool layer's integer form (0=Monday
                through 6=Sunday)
            day_of_month: Day of month for monthly schedules (1-28)
            cloud_backup_enabled: Whether to also push backups to cloud storage

        Returns:
            Schedule configuration response

        Note:
            For local API: PUT
            /proxy/network/api/s/{site}/set/setting/auto_backup/{settings_id}
        """
        # Translate the weekday into a cron day NAME before any network
        # round-trip. The tool layer documents integers as
        # 0=Monday..6=Sunday, which is not cron's numbering (cron counts
        # 0=Sunday) -- and Monday's 0 is falsy, so a bare f-string default
        # would silently turn Monday into the fallback. Names sidestep both
        # traps.
        cron_day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        if day_of_week is None:
            cron_dow = "sun"
        elif isinstance(day_of_week, int):
            if not 0 <= day_of_week <= 6:
                raise APIError(
                    f"day_of_week must be 0 (Monday) through 6 (Sunday), got {day_of_week}"
                )
            cron_dow = cron_day_names[day_of_week]
        else:
            cron_dow = str(day_of_week).strip().lower()[:3]
            if cron_dow not in cron_day_names:
                raise APIError(f"day_of_week must be a weekday name, got {day_of_week!r}")

        site_id = await self.resolve_site_id(site_id)

        # The schedule lives in the auto_backup settings section; the
        # rest/backup/schedule resource this method previously PUT to does
        # not exist on any controller (api.err.InvalidObject). UniFi OS
        # consoles do not carry the section at all -- their scheduled
        # backups are managed at the console level -- so absence is reported
        # as such rather than written into.
        current = await self.get_backup_schedule(site_id)
        settings_id = current.get("_id")
        if not settings_id:
            raise APIError(
                "This controller has no auto_backup settings section, so the "
                "backup schedule cannot be configured through the Network "
                "API. UniFi OS consoles manage scheduled backups at the "
                "console level (existing backups are still visible via "
                "list_backups)."
            )

        hour, _, minute = time_of_day.partition(":")
        cron_map = {
            "daily": f"{minute or 0} {hour or 0} * * *",
            "weekly": f"{minute or 0} {hour or 0} * * {cron_dow}",
            "monthly": f"{minute or 0} {hour or 0} {day_of_month or 1} * *",
        }
        payload: dict[str, Any] = {
            "auto_backup_enabled": enabled,
            "auto_backup_cron_expr": cron_map.get(frequency, cron_map["daily"]),
            "auto_backup_max_files": max_backups,
            "auto_backup_days": retention_days,
        }

        site_name = self._site_uuid_to_name.get(site_id, site_id)
        if self.settings.api_type == APIType.LOCAL:
            endpoint = f"/proxy/network/api/s/{site_name}/set/setting/auto_backup/{settings_id}"
        else:
            endpoint = f"/ea/sites/{site_id}/set/setting/auto_backup/{settings_id}"

        return await self.put(endpoint, json_data=payload)

    async def get_backup_schedule(
        self,
        site_id: str,
    ) -> dict[str, Any]:
        """Retrieve the current backup schedule configuration for a site.

        Args:
            site_id: Site identifier

        Returns:
            Backup schedule configuration, or empty dict if none is configured

        Note:
            For local API: GET
            /proxy/network/api/s/{site}/get/setting/auto_backup
        """
        site_id = await self.resolve_site_id(site_id)

        # The schedule is the auto_backup settings section. Absence (or the
        # api.err.Invalid a UniFi OS console answers with) means scheduled
        # backups are managed at the console level, not through this API --
        # report that as an empty dict and let callers decide how loud to be.
        if self.settings.api_type == APIType.LOCAL:
            site_name = self._site_uuid_to_name.get(site_id, site_id)
            endpoint = f"/proxy/network/api/s/{site_name}/get/setting/auto_backup"
        else:
            endpoint = f"/ea/sites/{site_id}/get/setting/auto_backup"

        try:
            response = await self.get(endpoint)
        except APIError as exc:
            # Only the controller's "no such setting" answers mean absence;
            # anything else (500s, validation failures) is a real error the
            # caller must see, not a console-level-backups condition.
            message = str(exc)
            if any(
                marker in message
                for marker in ("api.err.Invalid", "api.err.NotFound", "api.err.NoSuchObject")
            ):
                return {}
            raise

        items = response if isinstance(response, list) else response.get("data", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("key") == "auto_backup":
                    return item
            return items[0] if items and isinstance(items[0], dict) else {}
        return items if isinstance(items, dict) else {}
