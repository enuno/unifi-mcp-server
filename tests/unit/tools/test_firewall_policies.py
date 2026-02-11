"""Unit tests for list_firewall_policies tool.

TDD: Tests for src/tools/firewall_policies.py list_firewall_policies
Based on API discovery in docs/research/TRAFFIC_RULES_API_DISCOVERY.md

Endpoint: GET /proxy/network/v2/api/site/{site}/firewall-policies
Only available with local gateway API (api_type="local")
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.config.config import Settings


class TestListFirewallPolicies:
    """Tests for list_firewall_policies function."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for local API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def cloud_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for cloud API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        return Settings()

    @pytest.fixture
    def sample_policy_response(self) -> list[dict]:
        """Sample API response from UniFi controller."""
        return [
            {
                "_id": "682a0e42220317278bb0b2cb",
                "name": "Block IOT to Internal",
                "enabled": True,
                "action": "BLOCK",
                "predefined": False,
                "index": 10000,
                "protocol": "all",
                "ip_version": "BOTH",
                "connection_state_type": "CUSTOM",
                "connection_states": ["NEW"],
                "source": {
                    "zone_id": "682a0e42220317278bb0b2c5",
                    "matching_target": "NETWORK",
                    "network_ids": ["6643a914785061509e45c60f"],
                },
                "destination": {
                    "zone_id": "682a0e42220317278bb0b2c5",
                    "matching_target": "NETWORK",
                    "network_ids": ["6507f744e35fa70a9663d80e"],
                },
            },
            {
                "_id": "682a0e42220317278bb0b2c9",
                "name": "Allow All Traffic",
                "enabled": True,
                "action": "ALLOW",
                "predefined": True,
                "index": 2147483647,
                "protocol": "all",
                "ip_version": "BOTH",
                "connection_state_type": "ALL",
                "source": {
                    "zone_id": "682a0e42220317278bb0b2c5",
                    "matching_target": "ANY",
                },
                "destination": {
                    "zone_id": "682a0e42220317278bb0b2c5",
                    "matching_target": "ANY",
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_list_firewall_policies_success(
        self, local_settings: Settings, sample_policy_response: list[dict]
    ) -> None:
        """Test successful listing of firewall policies."""
        from src.tools.firewall_policies import list_firewall_policies

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_policy_response

            result = await list_firewall_policies("default", local_settings)

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["name"] == "Block IOT to Internal"
            assert result[1]["name"] == "Allow All Traffic"
            assert result[0]["id"] == "682a0e42220317278bb0b2cb"
            assert result[0]["action"] == "BLOCK"

    @pytest.mark.asyncio
    async def test_list_firewall_policies_empty_response(self, local_settings: Settings) -> None:
        """Test listing when no firewall policies exist."""
        from src.tools.firewall_policies import list_firewall_policies

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = []

            result = await list_firewall_policies("default", local_settings)

            assert isinstance(result, list)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_firewall_policies_cloud_api_raises_error(
        self, cloud_settings: Settings
    ) -> None:
        """Test that cloud API raises NotImplementedError."""
        from src.tools.firewall_policies import list_firewall_policies

        with pytest.raises(NotImplementedError) as exc_info:
            await list_firewall_policies("default", cloud_settings)

        assert "local" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_list_firewall_policies_api_error(self, local_settings: Settings) -> None:
        """Test error handling when API returns an error."""
        from src.tools.firewall_policies import list_firewall_policies
        from src.utils.exceptions import APIError

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.side_effect = APIError("Connection failed")

            with pytest.raises(APIError):
                await list_firewall_policies("default", local_settings)

    @pytest.mark.asyncio
    async def test_list_firewall_policies_correct_endpoint(
        self, local_settings: Settings, sample_policy_response: list[dict]
    ) -> None:
        """Test that the correct v2 API endpoint is called."""
        from src.tools.firewall_policies import list_firewall_policies

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_policy_response

            await list_firewall_policies("default", local_settings)

            mock_client.get.assert_called_once()
            called_endpoint = mock_client.get.call_args[0][0]
            assert "v2" in called_endpoint
            assert "firewall-policies" in called_endpoint
            assert "default" in called_endpoint

    @pytest.mark.asyncio
    async def test_list_firewall_policies_custom_site_id(
        self, local_settings: Settings, sample_policy_response: list[dict]
    ) -> None:
        """Test listing policies for a custom site ID."""
        from src.tools.firewall_policies import list_firewall_policies

        custom_site_id = "my-custom-site"

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_policy_response

            result = await list_firewall_policies(custom_site_id, local_settings)

            assert isinstance(result, list)
            called_endpoint = mock_client.get.call_args[0][0]
            assert custom_site_id in called_endpoint

    @pytest.mark.asyncio
    async def test_list_firewall_policies_returns_model_dicts(
        self, local_settings: Settings, sample_policy_response: list[dict]
    ) -> None:
        """Test that response is validated through FirewallPolicy model."""
        from src.tools.firewall_policies import list_firewall_policies

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_policy_response

            result = await list_firewall_policies("default", local_settings)

            assert "id" in result[0]

    @pytest.mark.asyncio
    async def test_list_firewall_policies_authenticates_if_needed(
        self, local_settings: Settings, sample_policy_response: list[dict]
    ) -> None:
        """Test that client authenticates if not already authenticated."""
        from src.tools.firewall_policies import list_firewall_policies

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = False
            mock_client.get.return_value = sample_policy_response

            await list_firewall_policies("default", local_settings)

            mock_client.authenticate.assert_called_once()


class TestGetFirewallPolicy:
    """Tests for get_firewall_policy function."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for local API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def cloud_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for cloud API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        return Settings()

    @pytest.fixture
    def sample_policy(self) -> dict:
        """Sample single policy API response from UniFi controller."""
        return {
            "_id": "682a0e42220317278bb0b2cb",
            "name": "Block IOT to Internal",
            "enabled": True,
            "action": "BLOCK",
            "predefined": False,
            "index": 10000,
            "protocol": "all",
            "ip_version": "BOTH",
            "connection_state_type": "CUSTOM",
            "connection_states": ["NEW"],
            "source": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "NETWORK",
                "network_ids": ["6643a914785061509e45c60f"],
            },
            "destination": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "NETWORK",
                "network_ids": ["6507f744e35fa70a9663d80e"],
            },
        }

    @pytest.mark.asyncio
    async def test_get_firewall_policy_success(
        self, local_settings: Settings, sample_policy: dict
    ) -> None:
        """Test successful retrieval of a firewall policy."""
        from src.tools.firewall_policies import get_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_policy

            result = await get_firewall_policy(
                "682a0e42220317278bb0b2cb", "default", local_settings
            )

            assert isinstance(result, dict)
            assert result["name"] == "Block IOT to Internal"
            assert result["id"] == "682a0e42220317278bb0b2cb"
            assert result["action"] == "BLOCK"
            assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_firewall_policy_not_found(self, local_settings: Settings) -> None:
        """Test that ResourceNotFoundError is raised when policy not found."""
        from src.tools.firewall_policies import get_firewall_policy
        from src.utils.exceptions import ResourceNotFoundError

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.side_effect = ResourceNotFoundError("firewall_policy", "nonexistent-id")

            with pytest.raises(ResourceNotFoundError) as exc_info:
                await get_firewall_policy("nonexistent-id", "default", local_settings)

            assert "firewall_policy" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_firewall_policy_cloud_api_raises_error(
        self, cloud_settings: Settings
    ) -> None:
        """Test that cloud API raises NotImplementedError."""
        from src.tools.firewall_policies import get_firewall_policy

        with pytest.raises(NotImplementedError) as exc_info:
            await get_firewall_policy("682a0e42220317278bb0b2cb", "default", cloud_settings)

        assert "local" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_firewall_policy_correct_endpoint(
        self, local_settings: Settings, sample_policy: dict
    ) -> None:
        """Test that the correct v2 API endpoint with policy_id is called."""
        from src.tools.firewall_policies import get_firewall_policy

        policy_id = "682a0e42220317278bb0b2cb"

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_policy

            await get_firewall_policy(policy_id, "default", local_settings)

            mock_client.get.assert_called_once()
            called_endpoint = mock_client.get.call_args[0][0]
            assert "v2" in called_endpoint
            assert "firewall-policies" in called_endpoint
            assert policy_id in called_endpoint
            assert "default" in called_endpoint

    @pytest.mark.asyncio
    async def test_get_firewall_policy_wrapped_response(
        self, local_settings: Settings, sample_policy: dict
    ) -> None:
        """Test handling of wrapped API response with 'data' key."""
        from src.tools.firewall_policies import get_firewall_policy

        wrapped_response = {"data": sample_policy}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = wrapped_response

            result = await get_firewall_policy(
                "682a0e42220317278bb0b2cb", "default", local_settings
            )

            assert result["name"] == "Block IOT to Internal"
            assert result["id"] == "682a0e42220317278bb0b2cb"

    @pytest.mark.asyncio
    async def test_get_firewall_policy_empty_response_raises_error(
        self, local_settings: Settings
    ) -> None:
        """Test that empty response raises ResourceNotFoundError."""
        from src.tools.firewall_policies import get_firewall_policy
        from src.utils.exceptions import ResourceNotFoundError

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = {}

            with pytest.raises(ResourceNotFoundError):
                await get_firewall_policy("682a0e42220317278bb0b2cb", "default", local_settings)

    @pytest.mark.asyncio
    async def test_get_firewall_policy_api_error(self, local_settings: Settings) -> None:
        """Test error handling when API returns an error."""
        from src.tools.firewall_policies import get_firewall_policy
        from src.utils.exceptions import APIError

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.side_effect = APIError("Connection failed")

            with pytest.raises(APIError):
                await get_firewall_policy("682a0e42220317278bb0b2cb", "default", local_settings)

    @pytest.mark.asyncio
    async def test_get_firewall_policy_authenticates_if_needed(
        self, local_settings: Settings, sample_policy: dict
    ) -> None:
        """Test that client authenticates if not already authenticated."""
        from src.tools.firewall_policies import get_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = False
            mock_client.get.return_value = sample_policy

            await get_firewall_policy("682a0e42220317278bb0b2cb", "default", local_settings)

            mock_client.authenticate.assert_called_once()


class TestUpdateFirewallPolicy:
    """Tests for update_firewall_policy function."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for local API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def cloud_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for cloud API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        return Settings()

    @pytest.fixture
    def sample_updated_policy(self) -> dict:
        """Sample updated policy response from UniFi controller."""
        return {
            "_id": "682a0e42220317278bb0b2cb",
            "name": "Updated Policy Name",
            "enabled": True,
            "action": "ALLOW",
            "predefined": False,
            "index": 10000,
            "protocol": "all",
            "ip_version": "BOTH",
            "connection_state_type": "ALL",
            "source": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "ANY",
            },
            "destination": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "ANY",
            },
        }

    @pytest.mark.asyncio
    async def test_update_firewall_policy_success_with_confirm(
        self, local_settings: Settings, sample_updated_policy: dict
    ) -> None:
        """Test successful update of a firewall policy with confirm=True."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.put.return_value = sample_updated_policy

            result = await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                name="Updated Policy Name",
                action="ALLOW",
                site_id="default",
                confirm=True,
                settings=local_settings,
            )

            assert isinstance(result, dict)
            assert result["name"] == "Updated Policy Name"
            assert result["action"] == "ALLOW"
            mock_client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_firewall_policy_rejected_without_confirm(
        self, local_settings: Settings
    ) -> None:
        """Test that update is rejected without confirm=True."""
        from src.tools.firewall_policies import update_firewall_policy

        with pytest.raises(ValueError) as exc_info:
            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                name="Updated Policy Name",
                site_id="default",
                confirm=False,
                settings=local_settings,
            )

        assert "confirm=True" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_firewall_policy_dry_run_mode(self, local_settings: Settings) -> None:
        """Test dry_run mode returns preview without making changes."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                name="Updated Policy Name",
                site_id="default",
                dry_run=True,
                settings=local_settings,
            )

            assert result["status"] == "dry_run"
            assert result["policy_id"] == "682a0e42220317278bb0b2cb"
            assert "changes" in result
            assert result["changes"]["name"] == "Updated Policy Name"
            mock_client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_firewall_policy_not_found(self, local_settings: Settings) -> None:
        """Test 404 when policy not found."""
        from src.tools.firewall_policies import update_firewall_policy
        from src.utils.exceptions import ResourceNotFoundError

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.put.side_effect = ResourceNotFoundError("firewall_policy", "nonexistent-id")

            with pytest.raises(ResourceNotFoundError) as exc_info:
                await update_firewall_policy(
                    policy_id="nonexistent-id",
                    name="Updated Name",
                    site_id="default",
                    confirm=True,
                    settings=local_settings,
                )

            assert "firewall_policy" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_firewall_policy_cloud_api_raises_error(
        self, cloud_settings: Settings
    ) -> None:
        """Test that cloud API raises NotImplementedError."""
        from src.tools.firewall_policies import update_firewall_policy

        with pytest.raises(NotImplementedError) as exc_info:
            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                name="Updated Name",
                site_id="default",
                confirm=True,
                settings=cloud_settings,
            )

        assert "local" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_update_firewall_policy_partial_update_name_only(
        self, local_settings: Settings, sample_updated_policy: dict
    ) -> None:
        """Test partial update with only name field."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.put.return_value = sample_updated_policy

            result = await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                name="Updated Policy Name",
                site_id="default",
                confirm=True,
                settings=local_settings,
            )

            assert result["name"] == "Updated Policy Name"
            call_args = mock_client.put.call_args
            request_body = call_args[1]["json_data"]
            assert "name" in request_body
            assert "action" not in request_body

    @pytest.mark.asyncio
    async def test_update_firewall_policy_partial_update_enabled_only(
        self, local_settings: Settings, sample_updated_policy: dict
    ) -> None:
        """Test partial update with only enabled field."""
        from src.tools.firewall_policies import update_firewall_policy

        disabled_policy = sample_updated_policy.copy()
        disabled_policy["enabled"] = False

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.put.return_value = disabled_policy

            result = await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                enabled=False,
                site_id="default",
                confirm=True,
                settings=local_settings,
            )

            assert result["enabled"] is False
            call_args = mock_client.put.call_args
            request_body = call_args[1]["json_data"]
            assert "enabled" in request_body
            assert request_body["enabled"] is False


class TestDeleteFirewallPolicy:
    """Tests for delete_firewall_policy function."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for local API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def cloud_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for cloud API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        return Settings()

    @pytest.fixture
    def sample_policy(self) -> dict:
        """Sample policy for testing delete operations."""
        return {
            "_id": "682a0e42220317278bb0b2cb",
            "name": "Block IOT to Internal",
            "enabled": True,
            "action": "BLOCK",
            "predefined": False,
            "index": 10000,
            "protocol": "all",
            "ip_version": "BOTH",
            "connection_state_type": "CUSTOM",
            "connection_states": ["NEW"],
            "source": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "NETWORK",
                "network_ids": ["6643a914785061509e45c60f"],
            },
            "destination": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "NETWORK",
                "network_ids": ["6507f744e35fa70a9663d80e"],
            },
        }

    @pytest.fixture
    def predefined_policy(self) -> dict:
        """Sample predefined system policy."""
        return {
            "_id": "682a0e42220317278bb0b2c9",
            "name": "Allow All Traffic",
            "enabled": True,
            "action": "ALLOW",
            "predefined": True,
            "index": 2147483647,
            "protocol": "all",
            "ip_version": "BOTH",
            "connection_state_type": "ALL",
            "source": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "ANY",
            },
            "destination": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "ANY",
            },
        }

    @pytest.mark.asyncio
    async def test_delete_firewall_policy_success_with_confirm(
        self, local_settings: Settings, sample_policy: dict
    ) -> None:
        """Test successful deletion of a firewall policy with confirm=True."""
        from src.tools.firewall_policies import delete_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_policy
            mock_client.delete.return_value = {}

            result = await delete_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                confirm=True,
                settings=local_settings,
            )

            assert result["status"] == "success"
            assert result["policy_id"] == "682a0e42220317278bb0b2cb"
            assert result["action"] == "deleted"
            mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_firewall_policy_rejected_without_confirm(
        self, local_settings: Settings
    ) -> None:
        """Test that delete is rejected without confirm=True."""
        from src.tools.firewall_policies import delete_firewall_policy

        with pytest.raises(ValueError) as exc_info:
            await delete_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                confirm=False,
                settings=local_settings,
            )

        assert "confirm=True" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_firewall_policy_dry_run_mode(
        self, local_settings: Settings, sample_policy: dict
    ) -> None:
        """Test dry_run mode returns what would be deleted without making changes."""
        from src.tools.firewall_policies import delete_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_policy

            result = await delete_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                dry_run=True,
                settings=local_settings,
            )

            assert result["status"] == "dry_run"
            assert result["policy_id"] == "682a0e42220317278bb0b2cb"
            assert result["action"] == "would_delete"
            assert "policy" in result
            assert result["policy"]["name"] == "Block IOT to Internal"
            mock_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_firewall_policy_not_found(self, local_settings: Settings) -> None:
        """Test 404 when policy not found."""
        from src.tools.firewall_policies import delete_firewall_policy
        from src.utils.exceptions import ResourceNotFoundError

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.side_effect = ResourceNotFoundError("firewall_policy", "nonexistent-id")

            with pytest.raises(ResourceNotFoundError) as exc_info:
                await delete_firewall_policy(
                    policy_id="nonexistent-id",
                    site_id="default",
                    confirm=True,
                    settings=local_settings,
                )

            assert "firewall_policy" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_firewall_policy_cloud_api_raises_error(
        self, cloud_settings: Settings
    ) -> None:
        """Test that cloud API raises NotImplementedError."""
        from src.tools.firewall_policies import delete_firewall_policy

        with pytest.raises(NotImplementedError) as exc_info:
            await delete_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                confirm=True,
                settings=cloud_settings,
            )

        assert "local" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_delete_firewall_policy_cannot_delete_predefined(
        self, local_settings: Settings, predefined_policy: dict
    ) -> None:
        """Test that predefined system rules cannot be deleted."""
        from src.tools.firewall_policies import delete_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = predefined_policy

            with pytest.raises(ValueError) as exc_info:
                await delete_firewall_policy(
                    policy_id="682a0e42220317278bb0b2c9",
                    site_id="default",
                    confirm=True,
                    settings=local_settings,
                )

            assert "predefined" in str(exc_info.value).lower()
            mock_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_firewall_policy_correct_endpoint(
        self, local_settings: Settings, sample_policy: dict
    ) -> None:
        """Test that the correct v2 API endpoint with policy_id is called."""
        from src.tools.firewall_policies import delete_firewall_policy

        policy_id = "682a0e42220317278bb0b2cb"

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_policy
            mock_client.delete.return_value = {}

            await delete_firewall_policy(
                policy_id=policy_id,
                site_id="default",
                confirm=True,
                settings=local_settings,
            )

            mock_client.delete.assert_called_once()
            called_endpoint = mock_client.delete.call_args[0][0]
            assert "v2" in called_endpoint
            assert "firewall-policies" in called_endpoint
            assert policy_id in called_endpoint
            assert "default" in called_endpoint

    @pytest.mark.asyncio
    async def test_delete_firewall_policy_authenticates_if_needed(
        self, local_settings: Settings, sample_policy: dict
    ) -> None:
        """Test that client authenticates if not already authenticated."""
        from src.tools.firewall_policies import delete_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = False
            mock_client.get.return_value = sample_policy
            mock_client.delete.return_value = {}

            await delete_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                confirm=True,
                settings=local_settings,
            )

            mock_client.authenticate.assert_called_once()


class TestCreateFirewallPolicy:
    """Tests for create_firewall_policy function."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for local API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def cloud_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for cloud API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        return Settings()

    @pytest.fixture
    def sample_created_policy(self) -> dict:
        """Sample created policy response from UniFi controller."""
        return {
            "_id": "new-policy-id-12345",
            "name": "Block IOT to LAN",
            "enabled": True,
            "action": "BLOCK",
            "predefined": False,
            "index": 10000,
            "protocol": "all",
            "ip_version": "BOTH",
            "connection_state_type": "ALL",
            "source": {
                "zone_id": "zone-internal",
                "matching_target": "ANY",
            },
            "destination": {
                "zone_id": "zone-external",
                "matching_target": "ANY",
            },
        }

    @pytest.mark.asyncio
    async def test_create_firewall_policy_success_with_confirm(
        self, local_settings: Settings, sample_created_policy: dict
    ) -> None:
        """Test successful creation of a firewall policy with confirm=True."""
        from src.tools.firewall_policies import create_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = sample_created_policy

            result = await create_firewall_policy(
                name="Block IOT to LAN",
                action="BLOCK",
                site_id="default",
                settings=local_settings,
                confirm=True,
            )

            assert isinstance(result, dict)
            assert result["name"] == "Block IOT to LAN"
            assert result["action"] == "BLOCK"
            assert result["id"] == "new-policy-id-12345"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_firewall_policy_rejected_without_confirm(
        self, local_settings: Settings
    ) -> None:
        """Test that create is rejected without confirm=True (safety check)."""
        from src.tools.firewall_policies import create_firewall_policy

        with pytest.raises(ValueError) as exc_info:
            await create_firewall_policy(
                name="Block IOT to LAN",
                action="BLOCK",
                site_id="default",
                settings=local_settings,
                confirm=False,
            )

        assert "confirm=True" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_firewall_policy_dry_run_mode(self, local_settings: Settings) -> None:
        """Test dry_run mode returns preview without making changes."""
        from src.tools.firewall_policies import create_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await create_firewall_policy(
                name="Block IOT to LAN",
                action="BLOCK",
                site_id="default",
                settings=local_settings,
                dry_run=True,
            )

            assert result["status"] == "dry_run"
            assert "policy" in result
            assert result["policy"]["name"] == "Block IOT to LAN"
            assert result["policy"]["action"] == "BLOCK"
            mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_firewall_policy_api_error(self, local_settings: Settings) -> None:
        """Test error handling when API returns an error."""
        from src.tools.firewall_policies import create_firewall_policy
        from src.utils.exceptions import APIError

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.side_effect = APIError("Connection failed")

            with pytest.raises(APIError):
                await create_firewall_policy(
                    name="Block IOT to LAN",
                    action="BLOCK",
                    site_id="default",
                    settings=local_settings,
                    confirm=True,
                )

    @pytest.mark.asyncio
    async def test_create_firewall_policy_cloud_api_raises_error(
        self, cloud_settings: Settings
    ) -> None:
        """Test that cloud API raises NotImplementedError."""
        from src.tools.firewall_policies import create_firewall_policy

        with pytest.raises(NotImplementedError) as exc_info:
            await create_firewall_policy(
                name="Block IOT to LAN",
                action="BLOCK",
                site_id="default",
                settings=cloud_settings,
                confirm=True,
            )

        assert "local" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_firewall_policy_correct_endpoint(
        self, local_settings: Settings, sample_created_policy: dict
    ) -> None:
        """Test that the correct v2 API endpoint is called."""
        from src.tools.firewall_policies import create_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = sample_created_policy

            await create_firewall_policy(
                name="Block IOT to LAN",
                action="BLOCK",
                site_id="default",
                settings=local_settings,
                confirm=True,
            )

            mock_client.post.assert_called_once()
            called_endpoint = mock_client.post.call_args[0][0]
            assert "v2" in called_endpoint
            assert "firewall-policies" in called_endpoint
            assert "default" in called_endpoint

    @pytest.mark.asyncio
    async def test_create_firewall_policy_with_zones(
        self, local_settings: Settings, sample_created_policy: dict
    ) -> None:
        """Test creation with specific zone IDs."""
        from src.tools.firewall_policies import create_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = sample_created_policy

            await create_firewall_policy(
                name="Block IOT to LAN",
                action="BLOCK",
                site_id="default",
                settings=local_settings,
                source_zone_id="zone-iot",
                destination_zone_id="zone-lan",
                confirm=True,
            )

            call_args = mock_client.post.call_args
            request_body = call_args[1]["json_data"]
            assert request_body["source"]["zone_id"] == "zone-iot"
            assert request_body["destination"]["zone_id"] == "zone-lan"

    @pytest.mark.asyncio
    async def test_create_firewall_policy_invalid_action(self, local_settings: Settings) -> None:
        """Test that invalid action raises ValueError."""
        from src.tools.firewall_policies import create_firewall_policy

        with pytest.raises(ValueError) as exc_info:
            await create_firewall_policy(
                name="Test Policy",
                action="INVALID",
                site_id="default",
                settings=local_settings,
                confirm=True,
            )

        assert "Invalid action" in str(exc_info.value)
        assert "ALLOW" in str(exc_info.value)
        assert "BLOCK" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_firewall_policy_allow_action(self, local_settings: Settings) -> None:
        """Test creation with ALLOW action."""
        from src.tools.firewall_policies import create_firewall_policy

        allow_policy = {
            "_id": "allow-policy-id",
            "name": "Allow LAN to WAN",
            "enabled": True,
            "action": "ALLOW",
            "predefined": False,
            "index": 10000,
            "protocol": "all",
            "ip_version": "BOTH",
            "connection_state_type": "ALL",
            "source": {"zone_id": "zone-lan", "matching_target": "ANY"},
            "destination": {"zone_id": "zone-wan", "matching_target": "ANY"},
        }

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = allow_policy

            result = await create_firewall_policy(
                name="Allow LAN to WAN",
                action="ALLOW",
                site_id="default",
                settings=local_settings,
                confirm=True,
            )

            assert result["action"] == "ALLOW"
            call_args = mock_client.post.call_args
            request_body = call_args[1]["json_data"]
            assert request_body["action"] == "ALLOW"

    @pytest.mark.asyncio
    async def test_create_firewall_policy_authenticates_if_needed(
        self, local_settings: Settings, sample_created_policy: dict
    ) -> None:
        """Test that client authenticates if not already authenticated."""
        from src.tools.firewall_policies import create_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = False
            mock_client.post.return_value = sample_created_policy

            await create_firewall_policy(
                name="Block IOT to LAN",
                action="BLOCK",
                site_id="default",
                settings=local_settings,
                confirm=True,
            )

            mock_client.authenticate.assert_called_once()
