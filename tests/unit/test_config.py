"""Unit tests for configuration management."""

import pytest
from pydantic import ValidationError

from src.config import APIType, Settings


class TestSettings:
    """Test suite for Settings class."""

    def test_default_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default settings with minimal configuration."""
        # Clear ALL existing UNIFI env vars to ensure clean test environment
        import os
        for key in list(os.environ.keys()):
            if key.startswith("UNIFI_"):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")

        settings = Settings()

        assert settings.api_key == "test-api-key"
        assert settings.api_type == APIType.CLOUD
        assert settings.cloud_api_url == "https://api.ui.com"
        assert settings.default_site == "default"
        assert settings.rate_limit_requests == 100
        assert settings.log_level == "INFO"

    def test_cloud_api_configuration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cloud API configuration."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud")

        settings = Settings()

        assert settings.api_type == APIType.CLOUD
        assert settings.base_url == "https://api.ui.com"
        assert settings.verify_ssl is True

    def test_local_api_configuration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test local API configuration."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.1.1")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", "8443")

        settings = Settings()

        assert settings.api_type == APIType.LOCAL
        assert settings.local_host == "192.168.1.1"
        assert settings.local_port == 8443
        assert settings.base_url == "https://192.168.1.1:8443"

    def test_local_api_without_host_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that local API without host raises error."""
        # Clear ALL UNIFI env vars to ensure clean test environment
        import os
        for key in list(os.environ.keys()):
            if key.startswith("UNIFI_"):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        # Explicitly NOT setting UNIFI_LOCAL_HOST - that's what we're testing

        with pytest.raises(ValidationError, match="local_host is required"):
            Settings()

    def test_invalid_port_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid port raises error."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", "99999")

        with pytest.raises(ValidationError, match="Port must be between"):
            Settings()

    def test_get_headers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test headers generation."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-api-key")

        settings = Settings()
        headers = settings.get_headers()

        assert headers["X-API-Key"] == "test-api-key"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_ssl_verification_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test SSL verification configuration."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.1.1")
        monkeypatch.setenv("UNIFI_LOCAL_VERIFY_SSL", "false")

        settings = Settings()

        assert settings.verify_ssl is False
        # base_url still uses https:// even when verify_ssl=False
        # verify_ssl controls certificate verification, not the protocol
        assert settings.base_url.startswith("https://")

    def test_api_type_enum_conversion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test API type enum conversion."""
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "CLOUD")

        settings = Settings()

        assert settings.api_type == APIType.CLOUD
        assert isinstance(settings.api_type, APIType)
