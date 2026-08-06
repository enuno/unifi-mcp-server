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
            mock_client._site_uuid_to_name = {"default": "default"}

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
            mock_client._site_uuid_to_name = {"my-custom-site": "my-custom-site"}
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

    @pytest.mark.asyncio
    async def test_list_firewall_policies_with_app_matching_target_fails(
        self, local_settings: Settings
    ) -> None:
        """Test that list_firewall_policies succeeds with matching_target='APP'.

        Bug #72 (FIXED): The MatchingTarget enum now includes the 'APP' value that
        real UniFi controllers return. This test verifies the fix works correctly.
        """
        from src.models.firewall_policy import MatchingTarget
        from src.tools.firewall_policies import list_firewall_policies

        # API response with matching_target='APP' that previously caused validation error
        policy_with_app_target = [
            {
                "_id": "682a0e42220317278bb0b2cb",
                "name": "Block APP Traffic",
                "enabled": True,
                "action": "BLOCK",
                "predefined": False,
                "index": 10000,
                "protocol": "all",
                "ip_version": "BOTH",
                "connection_state_type": "ALL",
                "source": {
                    "zone_id": "682a0e42220317278bb0b2c5",
                    "matching_target": "APP",  # Bug #72 FIXED: APP now in MatchingTarget enum
                },
                "destination": {
                    "zone_id": "682a0e42220317278bb0b2c5",
                    "matching_target": "ANY",
                },
            },
        ]

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client._site_uuid_to_name = {"default": "default"}
            mock_client.get.return_value = policy_with_app_target

            # This should now succeed because APP is in the enum
            result = await list_firewall_policies("default", local_settings)

            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["name"] == "Block APP Traffic"
            assert result[0]["source"]["matching_target"] == MatchingTarget.APP.value


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
    def sample_existing_policy(self) -> dict:
        """Existing policy as returned by GET before update."""
        return {
            "_id": "682a0e42220317278bb0b2cb",
            "name": "Original Name",
            "enabled": True,
            "action": "ALLOW",
            "predefined": False,
            "index": 10000,
            "protocol": "all",
            "ip_version": "BOTH",
            "logging": False,
            "connection_state_type": "ALL",
            "schedule": {"mode": "ALWAYS"},
            "source": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "ANY",
            },
            "destination": {
                "zone_id": "682a0e42220317278bb0b2c5",
                "matching_target": "ANY",
            },
        }

    @pytest.fixture
    def sample_updated_policy(self, sample_existing_policy: dict) -> dict:
        """Sample updated policy response from UniFi controller."""
        updated = sample_existing_policy.copy()
        updated["name"] = "Updated Policy Name"
        return updated

    @pytest.mark.asyncio
    async def test_update_firewall_policy_success_with_confirm(
        self,
        local_settings: Settings,
        sample_existing_policy: dict,
        sample_updated_policy: dict,
    ) -> None:
        """Test successful update of a firewall policy with confirm=True."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            # The new GET-merge-PUT flow fetches the existing policy first.
            mock_client.get.return_value = sample_existing_policy
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
            mock_client.get.assert_called_once()
            mock_client.put.assert_called_once()
            # The PUT body should be the full merged object, not just the
            # overrides, because the v2 endpoint requires all required
            # fields on every update.
            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["name"] == "Updated Policy Name"
            assert put_body["source"]["zone_id"] == "682a0e42220317278bb0b2c5"
            # _id and predefined must be stripped before PUT.
            assert "_id" not in put_body
            assert "predefined" not in put_body

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
    async def test_update_firewall_policy_dry_run_mode(
        self, local_settings: Settings, sample_existing_policy: dict
    ) -> None:
        """Test dry_run mode returns preview without making changes."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_existing_policy

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
            assert "merged_payload" in result
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
    async def test_update_firewall_policy_name_override_merges_with_existing(
        self,
        local_settings: Settings,
        sample_existing_policy: dict,
        sample_updated_policy: dict,
    ) -> None:
        """A name override must be merged into the existing object and the
        full object PUT back (partial PUT is rejected by the v2 endpoint)."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_existing_policy
            mock_client.put.return_value = sample_updated_policy

            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                name="Updated Policy Name",
                site_id="default",
                confirm=True,
                settings=local_settings,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            # Override applied
            assert put_body["name"] == "Updated Policy Name"
            # Existing fields preserved (merged)
            assert put_body["action"] == "ALLOW"
            assert put_body["enabled"] is True
            assert put_body["schedule"] == {"mode": "ALWAYS"}
            assert put_body["source"]["zone_id"] == "682a0e42220317278bb0b2c5"
            # Required-field-strip contract
            assert "_id" not in put_body
            assert "predefined" not in put_body

    @pytest.mark.asyncio
    async def test_update_firewall_policy_enabled_toggle(
        self,
        local_settings: Settings,
        sample_existing_policy: dict,
    ) -> None:
        """Toggling enabled=False flows through without touching other fields."""
        from src.tools.firewall_policies import update_firewall_policy

        disabled_policy = sample_existing_policy.copy()
        disabled_policy["enabled"] = False

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_existing_policy
            mock_client.put.return_value = disabled_policy

            result = await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                enabled=False,
                site_id="default",
                confirm=True,
                settings=local_settings,
            )

            assert result["enabled"] is False
            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["enabled"] is False
            # Other existing fields untouched
            assert put_body["name"] == "Original Name"
            assert put_body["action"] == "ALLOW"

    @pytest.mark.asyncio
    async def test_update_firewall_policy_logging_toggle(
        self,
        local_settings: Settings,
        sample_existing_policy: dict,
    ) -> None:
        """Enabling ``logging`` forces CPU inspection so the matched flows
        show up in the v2 traffic-flows endpoint."""
        from src.tools.firewall_policies import update_firewall_policy

        logging_on = sample_existing_policy.copy()
        logging_on["logging"] = True

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_existing_policy
            mock_client.put.return_value = logging_on

            result = await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                logging=True,
                site_id="default",
                confirm=True,
                settings=local_settings,
            )

            assert result["logging"] is True
            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["logging"] is True
            # Existing required fields still present
            assert put_body["action"] == "ALLOW"
            assert put_body["source"]["zone_id"] == "682a0e42220317278bb0b2c5"

    @pytest.mark.asyncio
    async def test_update_firewall_policy_rejects_predefined(
        self, local_settings: Settings, sample_existing_policy: dict
    ) -> None:
        """Predefined system policies must not be updatable."""
        from src.tools.firewall_policies import update_firewall_policy

        system_policy = {**sample_existing_policy, "predefined": True}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = system_policy

            with pytest.raises(ValueError, match="predefined"):
                await update_firewall_policy(
                    policy_id="682a0e42220317278bb0b2cb",
                    name="Hacked",
                    site_id="default",
                    confirm=True,
                    settings=local_settings,
                )

    @pytest.mark.asyncio
    async def test_update_firewall_policy_invalid_ip_version_raises(
        self, local_settings: Settings
    ) -> None:
        from src.tools.firewall_policies import update_firewall_policy

        with pytest.raises(ValueError, match="Invalid ip_version"):
            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                ip_version="IPV5",
                site_id="default",
                confirm=True,
                settings=local_settings,
            )

    @pytest.mark.asyncio
    async def test_update_firewall_policy_with_site_uuid_bug_73(
        self,
        local_settings: Settings,
        sample_existing_policy: dict,
        sample_updated_policy: dict,
    ) -> None:
        """Test that update_firewall_policy succeeds with site UUIDs using normalization.

        Bug #73 (FIXED): update_firewall_policy() now uses _site_uuid_to_name mapping
        to normalize UUIDs to short-names like "default" before building the endpoint.
        """
        from src.tools.firewall_policies import update_firewall_policy

        site_uuid = "62d2c5fdbf6b8c7ef80c0f2a"  # Example site UUID

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client._site_uuid_to_name = {site_uuid: "default"}
            mock_client.get.return_value = sample_existing_policy
            mock_client.put.return_value = sample_updated_policy

            result = await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                name="Updated Policy Name",
                site_id=site_uuid,
                confirm=True,
                settings=local_settings,
            )

            assert result["name"] == "Updated Policy Name"

            # Verify the endpoint was built with the normalized short-name "default"
            called_endpoint = mock_client.put.call_args[0][0]
            assert "default" in called_endpoint
            assert site_uuid not in called_endpoint


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
        """Test creation with specific zone IDs resolved via the v2 zone index."""
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        # Prime the zone cache so tests don't need to mock /firewall/zone.
        _zone_cache["default"] = {
            "zone-iot": "zone-iot",
            "zone-lan": "zone-lan",
        }

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = sample_created_policy

            try:
                await create_firewall_policy(
                    name="Block IOT to LAN",
                    action="BLOCK",
                    site_id="default",
                    settings=local_settings,
                    source_zone_id="zone-iot",
                    destination_zone_id="zone-lan",
                    confirm=True,
                )
            finally:
                _zone_cache.pop("default", None)

            call_args = mock_client.post.call_args
            request_body = call_args[1]["json_data"]
            assert request_body["source"]["zone_id"] == "zone-iot"
            assert request_body["destination"]["zone_id"] == "zone-lan"
            # Required v2 API fields are always included.
            assert request_body["schedule"] == {"mode": "ALWAYS"}
            assert request_body["ip_version"] == "BOTH"

    @pytest.mark.asyncio
    async def test_create_firewall_policy_resolves_zone_by_name(
        self, local_settings: Settings, sample_created_policy: dict
    ) -> None:
        """Zone names ('Internal') and external UUIDs should resolve to the
        internal ObjectId via the v2 zone index."""
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        # Simulated zone index: zone name + external UUID → internal _id
        _zone_cache["default"] = {
            "internal": "690d6e64e9671173fd71c586",
            "1daa9f24-eeaf-4bec-a714-e5eb65ea7ba2": "690d6e64e9671173fd71c586",
            "690d6e64e9671173fd71c586": "690d6e64e9671173fd71c586",
            "dmz": "690d6e64e9671173fd71c58b",
            "690d6e64e9671173fd71c58b": "690d6e64e9671173fd71c58b",
        }

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = sample_created_policy

            try:
                await create_firewall_policy(
                    name="Internal to DMZ",
                    action="ALLOW",
                    site_id="default",
                    settings=local_settings,
                    source_zone_id="Internal",  # by name (case-insensitive)
                    destination_zone_id="1daa9f24-eeaf-4bec-a714-e5eb65ea7ba2",  # noqa: E501 — external UUID
                    confirm=True,
                )
            finally:
                _zone_cache.pop("default", None)

            request_body = mock_client.post.call_args[1]["json_data"]
            assert request_body["source"]["zone_id"] == "690d6e64e9671173fd71c586"
            assert request_body["destination"]["zone_id"] == "690d6e64e9671173fd71c586"

    @pytest.mark.asyncio
    async def test_create_firewall_policy_unknown_zone_raises(
        self, local_settings: Settings
    ) -> None:
        """Unresolvable zone identifiers raise ValueError with a helpful hint."""
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        _zone_cache["default"] = {"known": "abc123"}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            # Make refresh return an empty list too, so no new mappings appear.
            mock_client.get.return_value = {"data": []}

            try:
                with pytest.raises(ValueError, match="Could not resolve firewall zone"):
                    await create_firewall_policy(
                        name="Bad zone",
                        action="ALLOW",
                        site_id="default",
                        settings=local_settings,
                        source_zone_id="nonexistent",
                        confirm=True,
                    )
            finally:
                _zone_cache.pop("default", None)

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


class TestListFirewallZonesV2:
    """Tests for the v2 firewall zone listing helper."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.mark.asyncio
    async def test_list_firewall_zones_v2_returns_id_mapping(
        self, local_settings: Settings
    ) -> None:
        """Each returned entry exposes both internal and external IDs plus
        zone name and zone_key so callers can look up zones by any
        identifier."""
        from src.tools.firewall_policies import list_firewall_zones_v2

        raw_zones = [
            {
                "_id": "690d6e64e9671173fd71c586",
                "external_id": "1daa9f24-eeaf-4bec-a714-e5eb65ea7ba2",
                "name": "Internal",
                "zone_key": "internal",
                "default_zone": True,
                "network_ids": ["net-1", "net-2"],
            },
            {
                "_id": "6918c2f7dec8680b5fc97ffb",
                "external_id": "4d1c7bb4-1714-4b55-933d-f37ee9fccdda",
                "name": "Semi-Trusted",
                "zone_key": None,
                "default_zone": False,
                "network_ids": [],
            },
        ]

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = raw_zones

            result = await list_firewall_zones_v2("default", local_settings)

            assert len(result) == 2
            assert result[0] == {
                "internal_id": "690d6e64e9671173fd71c586",
                "external_id": "1daa9f24-eeaf-4bec-a714-e5eb65ea7ba2",
                "name": "Internal",
                "zone_key": "internal",
                "default_zone": True,
                "network_ids": ["net-1", "net-2"],
            }
            assert result[1]["internal_id"] == "6918c2f7dec8680b5fc97ffb"
            assert result[1]["external_id"] == "4d1c7bb4-1714-4b55-933d-f37ee9fccdda"

            called_endpoint = mock_client.get.call_args[0][0]
            assert called_endpoint.endswith("/firewall/zone")

    @pytest.mark.asyncio
    async def test_list_firewall_zones_v2_handles_none_data(self, local_settings: Settings) -> None:
        """UniFiClient can return ``{"data": None}`` for empty responses;
        the tool must not raise ``TypeError: 'NoneType' is not iterable``."""
        from src.tools.firewall_policies import list_firewall_zones_v2

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = {"data": None}

            result = await list_firewall_zones_v2("default", local_settings)
            assert result == []


class TestCreateFirewallPolicyConfirmCoercion:
    """Regression tests for the string-truthiness confirmation bypass."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.mark.asyncio
    async def test_string_false_confirm_does_not_bypass(self, local_settings: Settings) -> None:
        """confirm='False' (a truthy string) must not bypass the gate."""
        from src.tools.firewall_policies import create_firewall_policy

        with pytest.raises(ValueError, match="requires confirm=True"):
            await create_firewall_policy(
                name="Test",
                action="ALLOW",
                site_id="default",
                settings=local_settings,
                confirm="False",
            )

    @pytest.mark.asyncio
    async def test_string_true_confirm_is_accepted(self, local_settings: Settings) -> None:
        """confirm='true' (JSON-RPC stringified bool) must be coerced."""
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        _zone_cache["default"] = {"zone-a": "zone-a", "zone-b": "zone-b"}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = {
                "_id": "new",
                "name": "Test",
                "action": "ALLOW",
                "source": {"zone_id": "zone-a", "matching_target": "ANY"},
                "destination": {"zone_id": "zone-b", "matching_target": "ANY"},
            }

            try:
                result = await create_firewall_policy(
                    name="Test",
                    action="ALLOW",
                    site_id="default",
                    settings=local_settings,
                    source_zone_id="zone-a",
                    destination_zone_id="zone-b",
                    confirm="true",
                )
            finally:
                _zone_cache.pop("default", None)

            assert result["id"] == "new"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_ip_version_raises(self, local_settings: Settings) -> None:
        from src.tools.firewall_policies import create_firewall_policy

        with pytest.raises(ValueError, match="Invalid ip_version"):
            await create_firewall_policy(
                name="Test",
                action="ALLOW",
                site_id="default",
                settings=local_settings,
                ip_version="IPV5",
                confirm=True,
            )


class TestCreateFirewallPolicyPortMatching:
    """Verify port / port_group_id / port_matching_type plumbing."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def created_policy(self) -> dict:
        return {
            "_id": "new-policy",
            "name": "test",
            "action": "ALLOW",
            "enabled": True,
            "predefined": False,
            "ip_version": "BOTH",
            "protocol": "all",
            "schedule": {"mode": "ALWAYS"},
            "source": {"zone_id": "z1", "matching_target": "ANY"},
            "destination": {"zone_id": "z2", "matching_target": "ANY"},
        }

    @pytest.mark.asyncio
    async def test_specific_destination_port_auto_sets_mode(
        self, local_settings: Settings, created_policy: dict
    ) -> None:
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        _zone_cache["default"] = {"z1": "z1", "z2": "z2"}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = created_policy

            try:
                await create_firewall_policy(
                    name="Allow DNS",
                    action="ALLOW",
                    site_id="default",
                    settings=local_settings,
                    source_zone_id="z1",
                    destination_zone_id="z2",
                    destination_port="53",
                    confirm=True,
                )
            finally:
                _zone_cache.pop("default", None)

            body = mock_client.post.call_args[1]["json_data"]
            assert body["destination"]["port_matching_type"] == "SPECIFIC"
            assert body["destination"]["port"] == "53"
            assert "port_group_id" not in body["destination"]
            # Source side stays ANY (default)
            assert body["source"]["port_matching_type"] == "ANY"
            assert "port" not in body["source"]

    @pytest.mark.asyncio
    async def test_destination_port_range(
        self, local_settings: Settings, created_policy: dict
    ) -> None:
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        _zone_cache["default"] = {"z1": "z1", "z2": "z2"}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = created_policy

            try:
                await create_firewall_policy(
                    name="Allow ranges",
                    action="ALLOW",
                    site_id="default",
                    settings=local_settings,
                    source_zone_id="z1",
                    destination_zone_id="z2",
                    destination_port="9000-9010",
                    confirm=True,
                )
            finally:
                _zone_cache.pop("default", None)

            body = mock_client.post.call_args[1]["json_data"]
            assert body["destination"]["port"] == "9000-9010"
            assert body["destination"]["port_matching_type"] == "SPECIFIC"

    @pytest.mark.asyncio
    async def test_port_group_id_auto_sets_object_mode(
        self, local_settings: Settings, created_policy: dict
    ) -> None:
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        _zone_cache["default"] = {"z1": "z1", "z2": "z2"}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = created_policy

            try:
                await create_firewall_policy(
                    name="Allow port group",
                    action="ALLOW",
                    site_id="default",
                    settings=local_settings,
                    source_zone_id="z1",
                    destination_zone_id="z2",
                    destination_port_group_id="pg-1",
                    confirm=True,
                )
            finally:
                _zone_cache.pop("default", None)

            body = mock_client.post.call_args[1]["json_data"]
            assert body["destination"]["port_matching_type"] == "OBJECT"
            assert body["destination"]["port_group_id"] == "pg-1"
            assert "port" not in body["destination"]

    @pytest.mark.asyncio
    async def test_port_and_port_group_id_conflict(
        self, local_settings: Settings, created_policy: dict
    ) -> None:
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        _zone_cache["default"] = {"z1": "z1", "z2": "z2"}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True

            try:
                with pytest.raises(ValueError, match="port.*port_group_id"):
                    await create_firewall_policy(
                        name="Conflict",
                        action="ALLOW",
                        site_id="default",
                        settings=local_settings,
                        source_zone_id="z1",
                        destination_zone_id="z2",
                        destination_port="53",
                        destination_port_group_id="pg-1",
                        confirm=True,
                    )
            finally:
                _zone_cache.pop("default", None)

    @pytest.mark.asyncio
    async def test_match_opposite_ports_passthrough(
        self, local_settings: Settings, created_policy: dict
    ) -> None:
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        _zone_cache["default"] = {"z1": "z1", "z2": "z2"}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = created_policy

            try:
                await create_firewall_policy(
                    name="NOT 53",
                    action="BLOCK",
                    site_id="default",
                    settings=local_settings,
                    source_zone_id="z1",
                    destination_zone_id="z2",
                    destination_port="53",
                    destination_match_opposite_ports=True,
                    confirm=True,
                )
            finally:
                _zone_cache.pop("default", None)

            body = mock_client.post.call_args[1]["json_data"]
            assert body["destination"]["match_opposite_ports"] is True

    @pytest.mark.asyncio
    async def test_specific_without_port_raises(self, local_settings: Settings) -> None:
        """port_matching_type='SPECIFIC' without a port value must error."""
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        _zone_cache["default"] = {"z1": "z1", "z2": "z2"}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True

            try:
                with pytest.raises(ValueError, match="SPECIFIC.*requires.*port"):
                    await create_firewall_policy(
                        name="Bad",
                        action="ALLOW",
                        site_id="default",
                        settings=local_settings,
                        source_zone_id="z1",
                        destination_zone_id="z2",
                        destination_port_matching_type="SPECIFIC",
                        confirm=True,
                    )
            finally:
                _zone_cache.pop("default", None)

    @pytest.mark.asyncio
    async def test_object_without_port_group_id_raises(self, local_settings: Settings) -> None:
        """port_matching_type='OBJECT' without a port_group_id must error."""
        from src.tools.firewall_policies import _zone_cache, create_firewall_policy

        _zone_cache["default"] = {"z1": "z1", "z2": "z2"}

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True

            try:
                with pytest.raises(ValueError, match="OBJECT.*requires.*port_group_id"):
                    await create_firewall_policy(
                        name="Bad",
                        action="ALLOW",
                        site_id="default",
                        settings=local_settings,
                        source_zone_id="z1",
                        destination_zone_id="z2",
                        destination_port_matching_type="OBJECT",
                        confirm=True,
                    )
            finally:
                _zone_cache.pop("default", None)


class TestUpdateFirewallPolicyPortMatching:
    """Verify update_firewall_policy port-merge behaviour."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def existing_policy(self) -> dict:
        return {
            "_id": "p1",
            "name": "Allow Identity Sync",
            "action": "ALLOW",
            "enabled": True,
            "predefined": False,
            "ip_version": "BOTH",
            "protocol": "all",
            "logging": False,
            "schedule": {"mode": "ALWAYS"},
            "source": {
                "zone_id": "z-internal",
                "matching_target": "ANY",
                "port_matching_type": "ANY",
            },
            "destination": {
                "zone_id": "z-gateway",
                "matching_target": "ANY",
                "port_matching_type": "OBJECT",
                "port_group_id": "pg-old",
            },
        }

    @pytest.mark.asyncio
    async def test_switch_object_to_specific_clears_port_group_id(
        self, local_settings: Settings, existing_policy: dict
    ) -> None:
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = existing_policy
            mock_client.put.return_value = existing_policy

            await update_firewall_policy(
                policy_id="p1",
                site_id="default",
                settings=local_settings,
                destination_port="9543",
                confirm=True,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["destination"]["port_matching_type"] == "SPECIFIC"
            assert put_body["destination"]["port"] == "9543"
            # Old port_group_id must be removed since we switched modes
            assert "port_group_id" not in put_body["destination"]
            # Existing zone_id and matching_target preserved
            assert put_body["destination"]["zone_id"] == "z-gateway"
            assert put_body["destination"]["matching_target"] == "ANY"

    @pytest.mark.asyncio
    async def test_switch_to_any_clears_both_port_fields(
        self, local_settings: Settings, existing_policy: dict
    ) -> None:
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = existing_policy
            mock_client.put.return_value = existing_policy

            await update_firewall_policy(
                policy_id="p1",
                site_id="default",
                settings=local_settings,
                destination_port_matching_type="ANY",
                confirm=True,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["destination"]["port_matching_type"] == "ANY"
            assert "port" not in put_body["destination"]
            assert "port_group_id" not in put_body["destination"]

    @pytest.mark.asyncio
    async def test_change_only_port_group_id(
        self, local_settings: Settings, existing_policy: dict
    ) -> None:
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = existing_policy
            mock_client.put.return_value = existing_policy

            await update_firewall_policy(
                policy_id="p1",
                site_id="default",
                settings=local_settings,
                destination_port_group_id="pg-new",
                confirm=True,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["destination"]["port_group_id"] == "pg-new"
            assert put_body["destination"]["port_matching_type"] == "OBJECT"
            assert "port" not in put_body["destination"]

    @pytest.mark.asyncio
    async def test_unrelated_field_does_not_touch_ports(
        self, local_settings: Settings, existing_policy: dict
    ) -> None:
        """A name-only update must leave existing port settings alone."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = existing_policy
            mock_client.put.return_value = existing_policy

            await update_firewall_policy(
                policy_id="p1",
                site_id="default",
                settings=local_settings,
                name="renamed",
                confirm=True,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["destination"]["port_matching_type"] == "OBJECT"
            assert put_body["destination"]["port_group_id"] == "pg-old"

    @pytest.mark.asyncio
    async def test_port_and_port_group_id_conflict_on_update(
        self, local_settings: Settings, existing_policy: dict
    ) -> None:
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = existing_policy

            with pytest.raises(ValueError, match="port.*port_group_id"):
                await update_firewall_policy(
                    policy_id="p1",
                    site_id="default",
                    settings=local_settings,
                    destination_port="53",
                    destination_port_group_id="pg-1",
                    confirm=True,
                )


class TestUpdateFirewallPolicyNewFields:
    """Tests for the 6 new parameters added to update_firewall_policy."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for local API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def sample_existing_policy(self) -> dict:
        """Existing policy as returned by GET before update."""
        return {
            "_id": "682a0e42220317278bb0b2cb",
            "name": "Test Policy",
            "enabled": True,
            "action": "ALLOW",
            "predefined": False,
            "index": 10000,
            "protocol": "all",
            "ip_version": "BOTH",
            "connection_state_type": "ALL",
            "connection_states": [],
            "schedule": {"mode": "ALWAYS"},
            "source": {"zone_id": "zone-src", "matching_target": "ANY"},
            "destination": {"zone_id": "zone-dst", "matching_target": "ANY"},
        }

    @pytest.fixture
    def sample_updated_policy(self, sample_existing_policy: dict) -> dict:
        """Sample updated policy response."""
        return dict(sample_existing_policy)

    @pytest.mark.asyncio
    async def test_update_icmp_typename(
        self, local_settings: Settings, sample_existing_policy: dict, sample_updated_policy: dict
    ) -> None:
        """icmp_typename flows into the PUT body."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_existing_policy
            mock_client.put.return_value = sample_updated_policy

            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                settings=local_settings,
                icmp_typename="echo",
                confirm=True,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["icmp_typename"] == "echo"

    @pytest.mark.asyncio
    async def test_update_icmp_v6_typename(
        self, local_settings: Settings, sample_existing_policy: dict, sample_updated_policy: dict
    ) -> None:
        """icmp_v6_typename flows into the PUT body."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_existing_policy
            mock_client.put.return_value = sample_updated_policy

            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                settings=local_settings,
                icmp_v6_typename="echo-request",
                confirm=True,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["icmp_v6_typename"] == "echo-request"

    @pytest.mark.asyncio
    async def test_update_match_ip_sec(
        self, local_settings: Settings, sample_existing_policy: dict, sample_updated_policy: dict
    ) -> None:
        """match_ip_sec=True flows into the PUT body."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_existing_policy
            mock_client.put.return_value = sample_updated_policy

            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                settings=local_settings,
                match_ip_sec=True,
                confirm=True,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["match_ip_sec"] is True

    @pytest.mark.asyncio
    async def test_update_match_opposite_protocol(
        self, local_settings: Settings, sample_existing_policy: dict, sample_updated_policy: dict
    ) -> None:
        """match_opposite_protocol=True flows into the PUT body."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_existing_policy
            mock_client.put.return_value = sample_updated_policy

            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                settings=local_settings,
                match_opposite_protocol=True,
                confirm=True,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["match_opposite_protocol"] is True

    @pytest.mark.asyncio
    async def test_update_connection_state_type_all(
        self, local_settings: Settings, sample_existing_policy: dict, sample_updated_policy: dict
    ) -> None:
        """connection_state_type='ALL' is uppercased and placed in PUT body."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_existing_policy
            mock_client.put.return_value = sample_updated_policy

            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                settings=local_settings,
                connection_state_type="all",
                confirm=True,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["connection_state_type"] == "ALL"
            assert put_body["connection_states"] == []

    @pytest.mark.asyncio
    async def test_update_connection_state_type_custom(
        self, local_settings: Settings, sample_existing_policy: dict, sample_updated_policy: dict
    ) -> None:
        """connection_state_type=CUSTOM with states flows into PUT body."""
        from src.tools.firewall_policies import update_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.get.return_value = sample_existing_policy
            mock_client.put.return_value = sample_updated_policy

            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                settings=local_settings,
                connection_state_type="CUSTOM",
                connection_states=["NEW", "ESTABLISHED"],
                confirm=True,
            )

            put_body = mock_client.put.call_args[1]["json_data"]
            assert put_body["connection_state_type"] == "CUSTOM"
            assert put_body["connection_states"] == ["NEW", "ESTABLISHED"]

    @pytest.mark.asyncio
    async def test_update_connection_state_type_custom_without_states_raises(
        self, local_settings: Settings
    ) -> None:
        """CUSTOM type without connection_states raises ValueError."""
        from src.tools.firewall_policies import update_firewall_policy

        with pytest.raises(ValueError, match="connection_states must be non-empty"):
            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                settings=local_settings,
                connection_state_type="CUSTOM",
                confirm=True,
            )

    @pytest.mark.asyncio
    async def test_update_connection_states_without_type_raises(
        self, local_settings: Settings
    ) -> None:
        """Providing connection_states without connection_state_type raises ValueError."""
        from src.tools.firewall_policies import update_firewall_policy

        with pytest.raises(ValueError, match="connection_state_type='CUSTOM' is required"):
            await update_firewall_policy(
                policy_id="682a0e42220317278bb0b2cb",
                site_id="default",
                settings=local_settings,
                connection_states=["NEW"],
                confirm=True,
            )


class TestCreateFirewallPolicyNewFields:
    """Tests for the 6 new parameters added to create_firewall_policy."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for local API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def sample_created_policy(self) -> dict:
        """Sample created policy API response."""
        return {
            "_id": "new-policy-id",
            "name": "Test Policy",
            "enabled": True,
            "action": "ALLOW",
            "predefined": False,
            "protocol": "all",
            "ip_version": "BOTH",
            "connection_state_type": "ALL",
            "source": {"zone_id": "zone-src", "matching_target": "ANY"},
            "destination": {"zone_id": "zone-dst", "matching_target": "ANY"},
        }

    @pytest.mark.asyncio
    async def test_create_with_icmp_typename(
        self, local_settings: Settings, sample_created_policy: dict
    ) -> None:
        """icmp_typename flows into the POST body."""
        from src.tools.firewall_policies import create_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = sample_created_policy

            await create_firewall_policy(
                name="Test Policy",
                action="ALLOW",
                site_id="default",
                settings=local_settings,
                icmp_typename="echo",
                confirm=True,
            )

            post_body = mock_client.post.call_args[1]["json_data"]
            assert post_body["icmp_typename"] == "echo"

    @pytest.mark.asyncio
    async def test_create_with_connection_state_type_custom(
        self, local_settings: Settings, sample_created_policy: dict
    ) -> None:
        """connection_state_type=CUSTOM with states flows into the POST body."""
        from src.tools.firewall_policies import create_firewall_policy

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.post.return_value = sample_created_policy

            await create_firewall_policy(
                name="Test Policy",
                action="ALLOW",
                site_id="default",
                settings=local_settings,
                connection_state_type="CUSTOM",
                connection_states=["NEW", "ESTABLISHED"],
                confirm=True,
            )

            post_body = mock_client.post.call_args[1]["json_data"]
            assert post_body["connection_state_type"] == "CUSTOM"
            assert post_body["connection_states"] == ["NEW", "ESTABLISHED"]

    @pytest.mark.asyncio
    async def test_create_connection_state_type_custom_without_states_raises(
        self, local_settings: Settings
    ) -> None:
        """CUSTOM type without connection_states raises ValueError."""
        from src.tools.firewall_policies import create_firewall_policy

        with pytest.raises(ValueError, match="connection_states must be non-empty"):
            await create_firewall_policy(
                name="Test Policy",
                action="ALLOW",
                site_id="default",
                settings=local_settings,
                connection_state_type="CUSTOM",
                confirm=True,
            )


class TestGetZonePolicyMatrix:
    """Tests for get_zone_policy_matrix function."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def cloud_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        return Settings()

    @pytest.fixture
    def sample_zones_response(self) -> dict:
        return {
            "totalCount": 3,
            "count": 3,
            "data": [
                {"id": "uuid-iot", "name": "IoT", "networkIds": ["net-1"]},
                {"id": "uuid-lan", "name": "LAN", "networkIds": ["net-2"]},
                {"id": "uuid-ext", "name": "External", "networkIds": []},
            ],
        }

    @pytest.fixture
    def sample_policies(self) -> list[dict]:
        return [
            {
                "_id": "policy-1",
                "name": "Block IoT to LAN",
                "action": "BLOCK",
                "enabled": True,
                "predefined": False,
                "source": {"zone_id": "oid-iot", "matching_target": "ANY"},
                "destination": {"zone_id": "oid-lan", "matching_target": "ANY"},
            },
            {
                "_id": "policy-2",
                "name": "Allow LAN to IoT",
                "action": "ALLOW",
                "enabled": True,
                "predefined": False,
                "source": {"zone_id": "oid-lan", "matching_target": "ANY"},
                "destination": {"zone_id": "oid-iot", "matching_target": "ANY"},
            },
            {
                "_id": "policy-3",
                "name": "Block IoT to LAN (predefined)",
                "action": "BLOCK",
                "enabled": True,
                "predefined": True,
                "source": {"zone_id": "oid-iot", "matching_target": "ANY"},
                "destination": {"zone_id": "oid-lan", "matching_target": "ANY"},
            },
        ]

    @pytest.mark.asyncio
    async def test_get_zone_policy_matrix_success(
        self,
        local_settings: Settings,
        sample_zones_response: dict,
        sample_policies: list[dict],
    ) -> None:
        """Test matrix returns zones, matrix, and summary."""
        from src.tools.firewall_policies import get_zone_policy_matrix

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.resolve_site_id = AsyncMock(return_value="resolved-site-id")
            mock_client.get.side_effect = [sample_zones_response, sample_policies]

            result = await get_zone_policy_matrix("default", local_settings)

            assert "matrix" in result
            assert "zones" in result
            assert "summary" in result
            # Both zones and policies endpoints must be fetched
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_zone_policy_matrix_fetches_both_endpoints(
        self,
        local_settings: Settings,
        sample_zones_response: dict,
        sample_policies: list[dict],
    ) -> None:
        """Zones and policies are fetched via asyncio.gather (both calls fire)."""
        from src.tools.firewall_policies import get_zone_policy_matrix

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.resolve_site_id = AsyncMock(return_value="resolved-site-id")
            mock_client.get.side_effect = [sample_zones_response, sample_policies]

            await get_zone_policy_matrix("default", local_settings)

            assert mock_client.get.call_count == 2
            call_urls = [str(c.args[0]) for c in mock_client.get.call_args_list]
            assert any("zones" in url for url in call_urls), "zones endpoint must be called"
            assert any(
                "firewall-policies" in url for url in call_urls
            ), "policies endpoint must be called"

    @pytest.mark.asyncio
    async def test_get_zone_policy_matrix_groups_by_zone_pair(
        self,
        local_settings: Settings,
        sample_zones_response: dict,
        sample_policies: list[dict],
    ) -> None:
        """Test policies are grouped by source/destination zone pair."""
        from src.tools.firewall_policies import get_zone_policy_matrix

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.resolve_site_id = AsyncMock(return_value="resolved-site-id")
            mock_client.get.side_effect = [sample_zones_response, sample_policies]

            result = await get_zone_policy_matrix("default", local_settings)

            matrix = result["matrix"]
            assert len(matrix) == 2
            iot_to_lan = next(
                (
                    p
                    for p in matrix
                    if p["source_zone_id"] == "oid-iot" and p["destination_zone_id"] == "oid-lan"
                ),
                None,
            )
            assert iot_to_lan is not None
            assert iot_to_lan["policy_count"] == 2

    @pytest.mark.asyncio
    async def test_get_zone_policy_matrix_summary_counts(
        self,
        local_settings: Settings,
        sample_zones_response: dict,
        sample_policies: list[dict],
    ) -> None:
        """Test summary counts are correct."""
        from src.tools.firewall_policies import get_zone_policy_matrix

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.resolve_site_id = AsyncMock(return_value="resolved-site-id")
            mock_client.get.side_effect = [sample_zones_response, sample_policies]

            result = await get_zone_policy_matrix("default", local_settings)

            summary = result["summary"]
            assert summary["total_policies"] == 3
            assert summary["zone_pairs_with_policies"] == 2
            assert summary["total_zones"] == 3

    @pytest.mark.asyncio
    async def test_get_zone_policy_matrix_policy_fields(
        self,
        local_settings: Settings,
        sample_zones_response: dict,
        sample_policies: list[dict],
    ) -> None:
        """Test that policy summaries include required fields."""
        from src.tools.firewall_policies import get_zone_policy_matrix

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.resolve_site_id = AsyncMock(return_value="resolved-site-id")
            mock_client.get.side_effect = [sample_zones_response, sample_policies]

            result = await get_zone_policy_matrix("default", local_settings)

            policy_summary = result["matrix"][0]["policies"][0]
            for field in ["id", "name", "action", "enabled", "predefined"]:
                assert field in policy_summary

    @pytest.mark.asyncio
    async def test_get_zone_policy_matrix_empty_policies(
        self,
        local_settings: Settings,
        sample_zones_response: dict,
    ) -> None:
        """Test empty policies returns empty matrix."""
        from src.tools.firewall_policies import get_zone_policy_matrix

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.resolve_site_id = AsyncMock(return_value="resolved-site-id")
            mock_client.get.side_effect = [sample_zones_response, []]

            result = await get_zone_policy_matrix("default", local_settings)

            assert result["matrix"] == []
            assert result["summary"]["total_policies"] == 0
            assert result["summary"]["zone_pairs_with_policies"] == 0

    @pytest.mark.asyncio
    async def test_get_zone_policy_matrix_zones_included(
        self,
        local_settings: Settings,
        sample_zones_response: dict,
        sample_policies: list[dict],
    ) -> None:
        """Test zones list is included with name and id."""
        from src.tools.firewall_policies import get_zone_policy_matrix

        with patch("src.tools.firewall_policies.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.is_authenticated = True
            mock_client.resolve_site_id = AsyncMock(return_value="resolved-site-id")
            mock_client.get.side_effect = [sample_zones_response, sample_policies]

            result = await get_zone_policy_matrix("default", local_settings)

            zones = result["zones"]
            assert len(zones) == 3
            assert zones[0]["name"] == "IoT"
            assert "id" in zones[0]

    @pytest.mark.asyncio
    async def test_get_zone_policy_matrix_cloud_api_raises(self, cloud_settings: Settings) -> None:
        """Test cloud API raises NotImplementedError."""
        from src.tools.firewall_policies import get_zone_policy_matrix

        with pytest.raises(NotImplementedError):
            await get_zone_policy_matrix("default", cloud_settings)
