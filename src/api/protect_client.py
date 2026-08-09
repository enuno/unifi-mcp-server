"""Async HTTP client for UniFi Protect API."""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import Settings
from ..utils.exceptions import APIError, AuthenticationError
from ..utils.logger import get_logger


class ProtectClient:
    """Async HTTP client for UniFi Protect API."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the Protect client with the given settings."""
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)
        self.client = httpx.AsyncClient(
            headers=settings.get_headers(),
            timeout=settings.request_timeout,
            verify=settings.verify_ssl,
            follow_redirects=False,
        )
        self._authenticated = False

    async def __aenter__(self) -> ProtectClient:
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the async context manager and close the HTTP client."""
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    @property
    def is_authenticated(self) -> bool:
        """Return whether the client has authenticated successfully."""
        return self._authenticated

    def _build_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        if endpoint.startswith(("v1/", "integration/", "proxy/")):
            path = f"/{endpoint}"
        else:
            path = self.settings.get_protect_integration_path(endpoint)
        return f"{self.settings.base_url}{path}"

    async def authenticate(self) -> None:
        """Validate access to the Protect API."""
        try:
            response = await self.get(self.settings.get_protect_integration_path("cameras"))
            if isinstance(response, list):
                self._authenticated = True
            elif isinstance(response, dict):
                self._authenticated = (
                    response.get("meta", {}).get("rc") == "ok"
                    or response.get("data") is not None
                    or response.get("count") is not None
                )
            else:
                self._authenticated = False
            self.logger.info(
                f"Successfully authenticated with Protect API (response type: {type(response).__name__})"
            )
        except Exception as exc:
            self.logger.error(f"Authentication failed: {exc}")
            raise AuthenticationError(f"Failed to authenticate with Protect API: {exc}") from exc

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        start_time = time.time()
        url = self._build_url(endpoint)
        try:
            response = await self.client.request(method, url, params=params, json=json_data)
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.debug(f"Protect {method} {url} completed in {duration_ms}ms")

            if response.status_code >= 400:
                raise APIError(
                    f"Protect API request failed ({response.status_code}): {response.text}"
                )

            try:
                return response.json()
            except Exception as exc:
                raise APIError(f"Failed to decode Protect API response: {exc}") from exc
        except APIError:
            raise
        except Exception as exc:
            raise APIError(f"Unexpected Protect API error: {exc}") from exc

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Perform a GET request against the Protect API."""
        return await self._request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Perform a POST request against the Protect API."""
        return await self._request("POST", endpoint, params=params, json_data=json_data)

    async def put(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Perform a PUT request against the Protect API."""
        return await self._request("PUT", endpoint, params=params, json_data=json_data)

    async def patch(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Perform a PATCH request against the Protect API."""
        return await self._request("PATCH", endpoint, params=params, json_data=json_data)

    async def delete(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Perform a DELETE request against the Protect API."""
        return await self._request("DELETE", endpoint, params=params)
