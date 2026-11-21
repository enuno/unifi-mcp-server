"""Async HTTP client for UniFi Protect API."""

from __future__ import annotations

import asyncio
import json
import ssl
import time
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from ..config import APIType, Settings
from ..utils.exceptions import APIError, AuthenticationError
from ..utils.logger import get_logger
from .pool import active_pool
from .tls import httpx_verify, tls_event_hooks


class ProtectClient:
    """Async HTTP client for UniFi Protect API."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the Protect client with the given settings."""
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)
        self._authenticated = False
        # Inside a pooled tool call, reuse the controller's long-lived HTTP
        # client (see src/api/pool.py) instead of opening a new one.
        self._pool = active_pool.get()
        self._connection = self._pool.acquire(settings) if self._pool is not None else None
        self._pooled = self._connection is not None
        if self._connection is not None:
            self.client = self._connection.client
            return
        self.client = httpx.AsyncClient(
            headers=settings.get_headers(),
            timeout=settings.request_timeout,
            verify=httpx_verify(settings.verify_ssl),
            event_hooks=tls_event_hooks(settings.tls_server_name),
            follow_redirects=False,
        )

    async def __aenter__(self) -> ProtectClient:
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the async context manager and close the HTTP client."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client (or hand a pooled connection back to the pool).

        Idempotent: a pooled client is shared, so it is never closed here, even
        on a second call after the connection was released.
        """
        if self._pooled:
            if self._connection is not None and self._pool is not None:
                self._pool.release(self._connection)
                self._connection = None
            return
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

    def _build_websocket_url(self, endpoint: str, params: dict[str, str]) -> str:
        """Build a WebSocket URL on the configured direct-console origin."""
        http_url = self._build_url(endpoint)
        parts = urlsplit(http_url)
        scheme = {"http": "ws", "https": "wss"}.get(parts.scheme)
        if scheme is None:
            raise APIError("Protect WebSocket base URL must use http or https")
        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(params), ""))

    def _websocket_ssl_context(self) -> ssl.SSLContext:
        """Build the TLS context used for direct-console WebSocket upgrades."""
        verify = httpx_verify(self.settings.verify_ssl)
        if isinstance(verify, ssl.SSLContext):
            return verify
        if verify:
            return ssl.create_default_context()
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    async def sample_model_updates(
        self,
        model_keys: Sequence[str],
        *,
        duration_seconds: float,
        max_messages: int,
    ) -> dict[str, Any]:
        """Collect a bounded sample from the Protect model-updates WebSocket.

        The Cloud Connector proxies ordinary HTTP requests but doesn't support
        WebSocket upgrades. This method therefore requires direct local-console
        access and never falls back to a plain HTTP GET.

        Args:
            model_keys: Protect model keys to include in the subscription.
            duration_seconds: Overall connection and sampling deadline in seconds.
            max_messages: Maximum number of update frames to collect.

        Returns:
            Messages and metadata describing why the bounded sample stopped.

        Raises:
            APIError: If configuration, upgrade, framing, or connection closure fails.
        """
        if self.settings.api_type != APIType.LOCAL:
            raise APIError(
                "Protect WebSocket subscriptions require direct local console access; "
                "the UniFi Cloud Connector does not support WebSocket upgrades"
            )
        if duration_seconds <= 0:
            raise APIError("duration_seconds must be greater than zero")
        if max_messages <= 0:
            raise APIError("max_messages must be greater than zero")

        url = self._build_websocket_url(
            self.settings.get_protect_integration_path("subscribe/updates"),
            {"modelKeys": ",".join(model_keys)},
        )
        connect_kwargs: dict[str, Any] = {
            "additional_headers": self.settings.get_headers(),
            "open_timeout": min(float(self.settings.request_timeout), duration_seconds),
            "close_timeout": min(1.0, duration_seconds),
            "max_size": 1_048_576,
            "proxy": None,
        }
        if url.startswith("wss://"):
            connect_kwargs["ssl"] = self._websocket_ssl_context()
            if self.settings.tls_server_name:
                connect_kwargs["server_hostname"] = self.settings.tls_server_name

        started = time.monotonic()
        messages: list[dict[str, Any]] = []
        stop_reason = "peer_closed"
        connected = False
        try:
            async with asyncio.timeout(duration_seconds):
                async with connect(url, **connect_kwargs) as websocket:
                    connected = True
                    while len(messages) < max_messages:
                        try:
                            raw_message = await websocket.recv()
                        except ConnectionClosedOK:
                            stop_reason = "peer_closed"
                            break
                        except ConnectionClosedError as exc:
                            raise APIError(
                                "Protect model-updates WebSocket closed unexpectedly "
                                f"(code {exc.code})"
                            ) from exc
                        if isinstance(raw_message, bytes):
                            raise APIError(
                                "Protect model-updates WebSocket returned an unexpected binary frame"
                            )
                        try:
                            message = json.loads(raw_message)
                        except json.JSONDecodeError as exc:
                            raise APIError(
                                "Protect model-updates WebSocket returned malformed JSON"
                            ) from exc
                        if not isinstance(message, dict):
                            raise APIError(
                                "Protect model-updates WebSocket messages must be a JSON object"
                            )
                        messages.append(message)
                    else:
                        stop_reason = "max_messages"
        except TimeoutError as exc:
            if not connected:
                raise APIError("Protect WebSocket upgrade timed out") from exc
            stop_reason = "deadline"
        except APIError:
            raise
        except Exception as exc:
            raise APIError(f"Protect WebSocket subscription failed: {exc}") from exc

        return {
            "messages": messages,
            "count": len(messages),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "stop_reason": stop_reason,
        }

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

            # Successful write endpoints may return 204 No Content (and some
            # versions return an empty 200 response). Treat both as an empty
            # object instead of attempting to decode absent JSON.
            if not response.content:
                return {}

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
