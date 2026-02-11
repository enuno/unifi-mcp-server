"""Unit tests for Settings.get_v2_api_path() method.

Tests the v2 API path generation for local gateway access.
The v2 API is only available on local gateways, not cloud.
"""

import pytest

from src.config.config import Settings


class TestGetV2ApiPath:
    """Tests for Settings.get_v2_api_path() method."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for local API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return Settings()

    @pytest.fixture
    def cloud_ea_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for cloud EA API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        return Settings()

    @pytest.fixture
    def cloud_v1_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for cloud V1 API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-v1")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        return Settings()

    def test_local_api_returns_correct_path(self, local_settings: Settings) -> None:
        """Test that local API type returns the correct v2 path."""
        result = local_settings.get_v2_api_path("default")

        assert result == "/proxy/network/v2/api/site/default"

    def test_local_api_with_custom_site_id(self, local_settings: Settings) -> None:
        """Test path generation with custom site_id."""
        result = local_settings.get_v2_api_path("my-custom-site")

        assert result == "/proxy/network/v2/api/site/my-custom-site"

    def test_local_api_with_uuid_site_id(self, local_settings: Settings) -> None:
        """Test path generation with UUID-style site_id."""
        site_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = local_settings.get_v2_api_path(site_id)

        assert result == f"/proxy/network/v2/api/site/{site_id}"

    def test_cloud_ea_raises_not_implemented_error(self, cloud_ea_settings: Settings) -> None:
        """Test that cloud-ea API type raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            cloud_ea_settings.get_v2_api_path("default")

        assert "v2 API" in str(exc_info.value)
        assert "local" in str(exc_info.value).lower()

    def test_cloud_v1_raises_not_implemented_error(self, cloud_v1_settings: Settings) -> None:
        """Test that cloud-v1 API type raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            cloud_v1_settings.get_v2_api_path("default")

        assert "v2 API" in str(exc_info.value)
        assert "local" in str(exc_info.value).lower()

    def test_empty_site_id(self, local_settings: Settings) -> None:
        """Test path generation with empty site_id still works (no validation)."""
        result = local_settings.get_v2_api_path("")

        assert result == "/proxy/network/v2/api/site/"

    def test_site_id_with_special_characters(self, local_settings: Settings) -> None:
        """Test path generation with site_id containing special chars."""
        result = local_settings.get_v2_api_path("site-with-dashes")

        assert result == "/proxy/network/v2/api/site/site-with-dashes"


class TestGetV2ApiPathIntegration:
    """Integration-style tests for get_v2_api_path with base_url."""

    @pytest.fixture
    def local_settings(self, monkeypatch: pytest.MonkeyPatch) -> Settings:
        """Create settings for local API access."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", "443")
        return Settings()

    def test_full_url_construction_for_local(self, local_settings: Settings) -> None:
        """Test that v2 path works correctly with base_url for local API."""
        base_url = local_settings.base_url
        v2_path = local_settings.get_v2_api_path("default")
        full_url = f"{base_url}{v2_path}"

        assert full_url == "https://192.168.2.1:443/proxy/network/v2/api/site/default"

    def test_v2_path_format_matches_expected_pattern(self, local_settings: Settings) -> None:
        """Verify v2 API path follows the documented pattern."""
        path = local_settings.get_v2_api_path("default")

        assert path.startswith("/proxy/network/v2/api/site/")
        parts = path.split("/")
        assert parts[-1] == "default"
