"""Unit tests for UniFi API client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.api.client import RateLimiter, UniFiClient
from src.config import APIType
from src.utils.exceptions import (
    APIError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
    ResourceNotFoundError,
)


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = APIType.CLOUD_EA
    settings.base_url = "https://api.ui.com"
    settings.api_key = "test-api-key"
    settings.request_timeout = 30.0
    settings.verify_ssl = True
    settings.rate_limit_requests = 100
    settings.rate_limit_period = 60
    settings.max_retries = 3
    settings.retry_backoff_factor = 2
    settings.log_api_requests = True
    settings.default_site = "default"
    settings.get_headers = MagicMock(return_value={"X-API-Key": "test-api-key"})
    return settings


@pytest.fixture
def mock_settings_local():
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.api_type = APIType.LOCAL
    settings.base_url = "https://192.168.2.1"
    settings.api_key = "test-api-key"
    settings.request_timeout = 30.0
    settings.verify_ssl = False
    settings.rate_limit_requests = 100
    settings.rate_limit_period = 60
    settings.max_retries = 3
    settings.retry_backoff_factor = 2
    settings.log_api_requests = True
    settings.default_site = "default"
    settings.get_headers = MagicMock(return_value={"X-API-Key": "test-api-key"})
    return settings


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        limiter = RateLimiter(requests_per_period=10, period_seconds=60)

        for _ in range(5):
            await limiter.acquire()

        assert limiter.tokens >= 4

    @pytest.mark.asyncio
    async def test_acquire_depletes_tokens(self):
        limiter = RateLimiter(requests_per_period=5, period_seconds=60)
        initial_tokens = limiter.tokens

        await limiter.acquire()
        assert limiter.tokens < initial_tokens

        await limiter.acquire()
        assert limiter.tokens < initial_tokens - 1

    @pytest.mark.asyncio
    async def test_acquire_waits_when_exhausted(self):
        limiter = RateLimiter(requests_per_period=100, period_seconds=1)
        limiter.tokens = 0.0

        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        duration = asyncio.get_event_loop().time() - start

        assert duration >= 0.001


class TestUniFiClientInit:
    @pytest.mark.asyncio
    async def test_client_init(self, mock_settings):
        client = UniFiClient(mock_settings)

        assert client.settings == mock_settings
        assert client._authenticated is False
        assert client._site_id_cache == {}
        await client.close()

    @pytest.mark.asyncio
    async def test_client_context_manager(self, mock_settings):
        async with UniFiClient(mock_settings) as client:
            assert client is not None
            assert isinstance(client, UniFiClient)

    @pytest.mark.asyncio
    async def test_is_authenticated_property(self, mock_settings):
        client = UniFiClient(mock_settings)

        assert client.is_authenticated is False
        client._authenticated = True
        assert client.is_authenticated is True

        await client.close()


class TestUniFiClientEndpointTranslation:
    @pytest.mark.asyncio
    async def test_translate_cloud_ea_unchanged(self, mock_settings):
        client = UniFiClient(mock_settings)

        result = client._translate_endpoint("/ea/sites")
        assert result == "/ea/sites"

        result = client._translate_endpoint("/ea/sites/default/devices")
        assert result == "/ea/sites/default/devices"

        await client.close()

    @pytest.mark.asyncio
    async def test_translate_cloud_v1_unchanged(self, mock_settings):
        mock_settings.api_type = APIType.CLOUD_V1
        client = UniFiClient(mock_settings)

        result = client._translate_endpoint("/v1/hosts")
        assert result == "/v1/hosts"

        await client.close()

    @pytest.mark.asyncio
    async def test_translate_local_sites(self, mock_settings_local):
        client = UniFiClient(mock_settings_local)

        result = client._translate_endpoint("/ea/sites")
        assert result == "/proxy/network/integration/v1/sites"

        await client.close()

    @pytest.mark.asyncio
    async def test_translate_local_devices(self, mock_settings_local):
        client = UniFiClient(mock_settings_local)

        result = client._translate_endpoint("/ea/sites/default/devices")
        assert result == "/proxy/network/api/s/default/stat/device"

        await client.close()

    @pytest.mark.asyncio
    async def test_translate_local_with_uuid_mapping(self, mock_settings_local):
        client = UniFiClient(mock_settings_local)
        client._site_uuid_to_name = {"abc-123-uuid": "default"}

        result = client._translate_endpoint("/ea/sites/abc-123-uuid/devices")
        assert result == "/proxy/network/api/s/default/stat/device"

        await client.close()

    @pytest.mark.asyncio
    async def test_translate_local_site_detail(self, mock_settings_local):
        client = UniFiClient(mock_settings_local)

        result = client._translate_endpoint("/ea/sites/default")
        assert result == "/proxy/network/api/s/default/self"

        await client.close()


class TestUniFiClientAuthentication:
    @pytest.mark.asyncio
    async def test_authenticate_success_list_response(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '[{"id": "site1"}]'
        mock_response.json = MagicMock(return_value=[{"id": "site1"}])

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            await client.authenticate()

        assert client._authenticated is True
        await client.close()

    @pytest.mark.asyncio
    async def test_authenticate_success_dict_response(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": [{"id": "site1"}]}'
        mock_response.json = MagicMock(return_value={"data": [{"id": "site1"}]})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            await client.authenticate()

        assert client._authenticated is True
        await client.close()

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, mock_settings):
        client = UniFiClient(mock_settings)

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("Connection refused")

            with pytest.raises(AuthenticationError, match="Failed to authenticate"):
                await client.authenticate()

        await client.close()

    @pytest.mark.asyncio
    async def test_build_site_uuid_map(self, mock_settings_local):
        client = UniFiClient(mock_settings_local)

        sites = [
            {"id": "uuid-1", "internalReference": "default"},
            {"id": "uuid-2", "internalReference": "office"},
        ]

        client._build_site_uuid_map(sites)

        assert client._site_uuid_to_name["uuid-1"] == "default"
        assert client._site_uuid_to_name["uuid-2"] == "office"
        await client.close()


class TestUniFiClientHttpMethods:
    @pytest.mark.asyncio
    async def test_get_success(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": [{"id": "device1"}]}'
        mock_response.json = MagicMock(return_value={"data": [{"id": "device1"}]})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await client.get("/ea/sites/default/devices")

        assert result == [{"id": "device1"}]
        await client.close()

    @pytest.mark.asyncio
    async def test_post_success(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": {"id": "new-resource"}}'
        mock_response.json = MagicMock(return_value={"data": {"id": "new-resource"}})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await client.post("/ea/sites/default/networks", {"name": "test"})

        assert result == {"data": {"id": "new-resource"}}
        await client.close()

    @pytest.mark.asyncio
    async def test_put_success(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": {"id": "updated"}}'
        mock_response.json = MagicMock(return_value={"data": {"id": "updated"}})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await client.put("/ea/sites/default/networks/123", {"name": "updated"})

        assert result == {"data": {"id": "updated"}}
        await client.close()

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "{}"
        mock_response.json = MagicMock(return_value={})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await client.delete("/ea/sites/default/networks/123")

        assert result == {}
        await client.close()


class TestUniFiClientErrorHandling:
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, mock_settings):
        mock_settings.max_retries = 0
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(RateLimitError):
                await client.get("/ea/sites")

        await client.close()

    @pytest.mark.asyncio
    async def test_not_found_error(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(ResourceNotFoundError):
                await client.get("/ea/sites/nonexistent")

        await client.close()

    @pytest.mark.asyncio
    async def test_authentication_error_401(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(AuthenticationError, match="Authentication failed"):
                await client.get("/ea/sites")

        await client.close()

    @pytest.mark.asyncio
    async def test_authentication_error_403(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(AuthenticationError, match="Authentication failed"):
                await client.get("/ea/sites")

        await client.close()

    @pytest.mark.asyncio
    async def test_api_error(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json = MagicMock(return_value={"error": "Server error"})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(APIError, match="API request failed"):
                await client.get("/ea/sites")

        await client.close()

    @pytest.mark.asyncio
    async def test_timeout_retry(self, mock_settings):
        mock_settings.max_retries = 2
        mock_settings.retry_backoff_factor = 0.01
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": []}'
        mock_response.json = MagicMock(return_value={"data": []})

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("timeout")
            return mock_response

        with patch.object(client.client, "request", side_effect=side_effect):
            result = await client.get("/ea/sites")

        assert result == []
        assert call_count == 2
        await client.close()

    @pytest.mark.asyncio
    async def test_timeout_max_retries_exceeded(self, mock_settings):
        mock_settings.max_retries = 1
        mock_settings.retry_backoff_factor = 0.01
        client = UniFiClient(mock_settings)

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.TimeoutException("timeout")

            with pytest.raises(NetworkError, match="timeout"):
                await client.get("/ea/sites")

        await client.close()

    @pytest.mark.asyncio
    async def test_network_error_retry(self, mock_settings):
        mock_settings.max_retries = 2
        mock_settings.retry_backoff_factor = 0.01
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": []}'
        mock_response.json = MagicMock(return_value={"data": []})

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.NetworkError("connection reset")
            return mock_response

        with patch.object(client.client, "request", side_effect=side_effect):
            result = await client.get("/ea/sites")

        assert result == []
        assert call_count == 2
        await client.close()


class TestUniFiClientResponseParsing:
    @pytest.mark.asyncio
    async def test_parse_empty_response(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.json = MagicMock(return_value={})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await client.get("/ea/sites/default/some-endpoint")

        assert result == {}
        await client.close()

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self, mock_settings):
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "not json"
        mock_response.json = MagicMock(side_effect=ValueError("Invalid JSON"))

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await client.get("/ea/sites")

        assert result == {}
        await client.close()

    @pytest.mark.asyncio
    async def test_https_force_correction(self, mock_settings):
        mock_settings.base_url = "http://api.ui.com"
        client = UniFiClient(mock_settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": []}'
        mock_response.json = MagicMock(return_value={"data": []})

        with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            await client.get("/ea/sites")

            call_args = mock_request.call_args
            assert call_args[1]["url"].startswith("https://")

        await client.close()


class TestUniFiClientBackupMethods:
    """Tests for backup-related client methods."""

    @pytest.mark.asyncio
    async def test_get_restore_status_returns_not_supported(self, mock_settings):
        """get_restore_status returns a not_supported status (endpoint not in UniFi API)."""
        client = UniFiClient(mock_settings)
        result = await client.get_restore_status(operation_id="op-123")
        assert result["status"] == "not_supported"
        assert result["operation_id"] == "op-123"
        assert "message" in result
        await client.close()

    @pytest.mark.asyncio
    async def test_configure_backup_schedule_local(self, mock_settings_local):
        """configure_backup_schedule calls PUT on the local endpoint."""
        client = UniFiClient(mock_settings_local)
        client._site_uuid_to_name = {"default": "default"}

        with patch.object(client, "resolve_site_id", new=AsyncMock(return_value="default")):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"data": {"schedule_id": "sched-1"}}'
            mock_response.json = MagicMock(return_value={"data": {"schedule_id": "sched-1"}})

            with patch.object(client.client, "request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                await client.configure_backup_schedule(
                    site_id="default",
                    backup_type="network",
                    frequency="daily",
                    time_of_day="02:00",
                    enabled=True,
                    retention_days=30,
                    max_backups=10,
                )

        assert mock_req.called
        call_kwargs = mock_req.call_args
        assert "/proxy/network/api/s/default/rest/backup/schedule" in call_kwargs[1]["url"]
        await client.close()

    @pytest.mark.asyncio
    async def test_configure_backup_schedule_cloud(self, mock_settings):
        """configure_backup_schedule calls PUT on the cloud endpoint."""
        client = UniFiClient(mock_settings)

        with patch.object(client, "resolve_site_id", new=AsyncMock(return_value="site-uuid")):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"data": {"schedule_id": "sched-2"}}'
            mock_response.json = MagicMock(return_value={"data": {"schedule_id": "sched-2"}})

            with patch.object(client.client, "request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                await client.configure_backup_schedule(
                    site_id="site-uuid",
                    backup_type="network",
                    frequency="weekly",
                    time_of_day="03:00",
                    enabled=True,
                    retention_days=14,
                    max_backups=5,
                    day_of_week="monday",
                )

        assert mock_req.called
        call_kwargs = mock_req.call_args
        assert "/ea/sites/site-uuid/backup/schedule" in call_kwargs[1]["url"]
        await client.close()

    @pytest.mark.asyncio
    async def test_get_backup_schedule_local_returns_dict(self, mock_settings_local):
        """get_backup_schedule returns a dict for a configured schedule."""
        client = UniFiClient(mock_settings_local)
        client._site_uuid_to_name = {"default": "default"}

        with patch.object(client, "resolve_site_id", new=AsyncMock(return_value="default")):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"data": {"schedule_id": "sched-1", "enabled": true}}'
            mock_response.json = MagicMock(
                return_value={"data": {"schedule_id": "sched-1", "enabled": True}}
            )

            with patch.object(client.client, "request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                result = await client.get_backup_schedule(site_id="default")

        assert isinstance(result, dict)
        await client.close()

    @pytest.mark.asyncio
    async def test_get_backup_schedule_empty_list_returns_empty_dict(self, mock_settings):
        """get_backup_schedule returns empty dict when API returns empty list."""
        client = UniFiClient(mock_settings)

        with patch.object(client, "resolve_site_id", new=AsyncMock(return_value="site-uuid")):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "[]"
            mock_response.json = MagicMock(return_value=[])

            with patch.object(client.client, "request", new_callable=AsyncMock) as mock_req:
                mock_req.return_value = mock_response
                result = await client.get_backup_schedule(site_id="site-uuid")

        assert result == {}
        await client.close()


class TestUniFiClientHelpers:
    def test_looks_like_uuid_valid(self):
        assert UniFiClient._looks_like_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_looks_like_uuid_invalid(self):
        assert UniFiClient._looks_like_uuid("default") is False
        assert UniFiClient._looks_like_uuid("not-a-uuid") is False

    def test_looks_like_uuid_none(self):
        assert UniFiClient._looks_like_uuid(None) is False

    def test_looks_like_uuid_empty(self):
        assert UniFiClient._looks_like_uuid("") is False
