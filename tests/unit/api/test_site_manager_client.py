"""Unit tests for SiteManagerClient rate limiting."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.site_manager_client import SiteManagerClient


class MockSettings:
    """Minimal settings object for SiteManagerClient tests."""

    log_level = "INFO"
    request_timeout = 5.0
    rate_limit_requests = 10
    rate_limit_period = 60
    resolved_site_manager_api_key = "site-manager-key"

    def get_headers(self, api_key: str | None = None) -> dict[str, str]:
        return {"X-API-KEY": api_key or "default"}


@pytest.fixture
def mock_settings() -> MockSettings:
    return MockSettings()


@patch("src.api.site_manager_client.httpx.AsyncClient")
@patch("src.api.site_manager_client.RateLimiter")
def test_site_manager_client_initializes_rate_limiter(
    mock_rate_limiter: MagicMock,
    mock_http_client: MagicMock,
    mock_settings: MockSettings,
) -> None:
    mock_http_client.return_value = MagicMock()

    SiteManagerClient(cast(Any, mock_settings))

    mock_rate_limiter.assert_called_once_with(
        mock_settings.rate_limit_requests,
        mock_settings.rate_limit_period,
    )


def _build_mock_http_client() -> AsyncMock:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"data": []})

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)
    mock_http_client.post = AsyncMock(return_value=mock_response)
    mock_http_client.aclose = AsyncMock()
    return mock_http_client


@pytest.mark.anyio
@patch("src.api.site_manager_client.httpx.AsyncClient")
@patch("src.api.site_manager_client.RateLimiter")
async def test_get_awaits_rate_limiter(
    mock_rate_limiter: MagicMock,
    mock_http_client_cls: MagicMock,
    mock_settings: MockSettings,
) -> None:
    rate_limiter = AsyncMock()
    mock_rate_limiter.return_value = rate_limiter
    mock_http_client = _build_mock_http_client()
    mock_http_client_cls.return_value = mock_http_client

    client = SiteManagerClient(cast(Any, mock_settings))
    client._authenticated = True

    await client.get("sites")

    rate_limiter.acquire.assert_awaited()
    mock_http_client.get.assert_awaited_once_with("sites", params=None)


@pytest.mark.anyio
@patch("src.api.site_manager_client.httpx.AsyncClient")
@patch("src.api.site_manager_client.RateLimiter")
async def test_post_awaits_rate_limiter(
    mock_rate_limiter: MagicMock,
    mock_http_client_cls: MagicMock,
    mock_settings: MockSettings,
) -> None:
    rate_limiter = AsyncMock()
    mock_rate_limiter.return_value = rate_limiter
    mock_http_client = _build_mock_http_client()
    mock_http_client_cls.return_value = mock_http_client

    client = SiteManagerClient(cast(Any, mock_settings))
    client._authenticated = True

    await client.post("query", data={"foo": "bar"})

    rate_limiter.acquire.assert_awaited()
    mock_http_client.post.assert_awaited_once()


@pytest.mark.anyio
@patch("src.api.site_manager_client.httpx.AsyncClient")
@patch("src.api.site_manager_client.RateLimiter")
async def test_authenticate_awaits_rate_limiter(
    mock_rate_limiter: MagicMock,
    mock_http_client_cls: MagicMock,
    mock_settings: MockSettings,
) -> None:
    rate_limiter = AsyncMock()
    mock_rate_limiter.return_value = rate_limiter
    mock_http_client = _build_mock_http_client()
    mock_http_client_cls.return_value = mock_http_client

    client = SiteManagerClient(cast(Any, mock_settings))

    await client.authenticate()

    rate_limiter.acquire.assert_awaited()
    mock_http_client.get.assert_awaited_with("sites")


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["list_sites", "list_hosts"])
@patch("src.api.site_manager_client.httpx.AsyncClient")
@patch("src.api.site_manager_client.RateLimiter")
async def test_list_limit_maps_to_page_size(
    mock_rate_limiter: MagicMock,
    mock_http_client_cls: MagicMock,
    mock_settings: MockSettings,
    method: str,
) -> None:
    """The Site Manager API paginates with pageSize/nextToken, not limit/offset."""
    mock_rate_limiter.return_value = AsyncMock()
    mock_http_client = _build_mock_http_client()
    mock_http_client_cls.return_value = mock_http_client

    client = SiteManagerClient(cast(Any, mock_settings))
    client._authenticated = True

    await getattr(client, method)(limit=2)

    mock_http_client.get.assert_awaited_once_with(
        method.removeprefix("list_"), params={"pageSize": 2}
    )


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["list_sites", "list_hosts"])
@patch("src.api.site_manager_client.httpx.AsyncClient")
@patch("src.api.site_manager_client.RateLimiter")
async def test_list_offset_is_not_sent(
    mock_rate_limiter: MagicMock,
    mock_http_client_cls: MagicMock,
    mock_settings: MockSettings,
    method: str,
) -> None:
    """offset is accepted for schema compatibility but the API has no such parameter."""
    mock_rate_limiter.return_value = AsyncMock()
    mock_http_client = _build_mock_http_client()
    mock_http_client_cls.return_value = mock_http_client

    client = SiteManagerClient(cast(Any, mock_settings))
    client._authenticated = True

    await getattr(client, method)(offset=5)

    mock_http_client.get.assert_awaited_once_with(method.removeprefix("list_"), params=None)
