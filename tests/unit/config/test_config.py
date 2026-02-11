"""Unit tests for src/config/config.py Settings class."""

import pytest

from src.config.config import APIType, Settings


class TestAPITypeEnum:
    """Tests for APIType enumeration."""

    def test_cloud_v1_value(self):
        assert APIType.CLOUD_V1.value == "cloud-v1"

    def test_cloud_ea_value(self):
        assert APIType.CLOUD_EA.value == "cloud-ea"

    def test_local_value(self):
        assert APIType.LOCAL.value == "local"

    def test_cloud_alias_equals_cloud_ea(self):
        assert APIType.CLOUD.value == APIType.CLOUD_EA.value


class TestSettingsValidateApiType:
    """Tests for Settings.validate_api_type validator."""

    def test_validate_api_type_from_string(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()
        assert settings.api_type == APIType.CLOUD_EA

    def test_validate_api_type_uppercase(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "CLOUD-V1")
        settings = Settings()
        assert settings.api_type == APIType.CLOUD_V1

    def test_validate_api_type_local(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "LOCAL")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        settings = Settings()
        assert settings.api_type == APIType.LOCAL

    def test_validate_api_type_already_enum(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()
        assert isinstance(settings.api_type, APIType)


class TestSettingsValidatePort:
    """Tests for Settings.validate_port validator."""

    def test_validate_port_valid(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", "8443")
        settings = Settings()
        assert settings.local_port == 8443

    def test_validate_port_min_boundary(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", "1")
        settings = Settings()
        assert settings.local_port == 1

    def test_validate_port_max_boundary(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", "65535")
        settings = Settings()
        assert settings.local_port == 65535

    def test_validate_port_zero_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", "0")
        with pytest.raises(ValueError) as exc_info:
            Settings()
        assert "Port must be between 1 and 65535" in str(exc_info.value)

    def test_validate_port_too_high_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", "65536")
        with pytest.raises(ValueError) as exc_info:
            Settings()
        assert "Port must be between 1 and 65535" in str(exc_info.value)


class TestSettingsLocalConfiguration:
    """Tests for Settings.validate_local_configuration validator."""

    def test_local_without_host_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        with pytest.raises(ValueError) as exc_info:
            Settings()
        assert "local_host is required" in str(exc_info.value)

    def test_local_with_host_succeeds(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        settings = Settings()
        assert settings.local_host == "192.168.2.1"

    def test_cloud_without_host_succeeds(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        settings = Settings()
        assert settings.local_host is None


class TestSettingsBaseUrl:
    """Tests for Settings.base_url property."""

    def test_base_url_cloud_ea(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()
        assert settings.base_url == "https://api.ui.com"

    def test_base_url_cloud_v1(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-v1")
        settings = Settings()
        assert settings.base_url == "https://api.ui.com"

    def test_base_url_local(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", "443")
        settings = Settings()
        assert settings.base_url == "https://192.168.2.1:443"

    def test_base_url_local_custom_port(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
        monkeypatch.setenv("UNIFI_LOCAL_PORT", "8443")
        settings = Settings()
        assert settings.base_url == "https://10.0.0.1:8443"


class TestSettingsVerifySsl:
    """Tests for Settings.verify_ssl property."""

    def test_verify_ssl_cloud_always_true(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()
        assert settings.verify_ssl is True

    def test_verify_ssl_local_default_true(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        monkeypatch.delenv("UNIFI_LOCAL_VERIFY_SSL", raising=False)
        monkeypatch.setenv("UNIFI_LOCAL_VERIFY_SSL", "true")
        settings = Settings()
        assert settings.verify_ssl is True

    def test_verify_ssl_local_disabled(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        monkeypatch.setenv("UNIFI_LOCAL_VERIFY_SSL", "false")
        settings = Settings()
        assert settings.verify_ssl is False


class TestSettingsGetIntegrationPath:
    """Tests for Settings.get_integration_path method."""

    def test_get_integration_path_cloud_v1(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-v1")
        settings = Settings()
        result = settings.get_integration_path("/sites/abc/firewall/zones")
        assert result == "/v1/sites/abc/firewall/zones"

    def test_get_integration_path_cloud_ea(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()
        result = settings.get_integration_path("/sites/abc/firewall/zones")
        assert result == "/integration/v1/sites/abc/firewall/zones"

    def test_get_integration_path_local(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        settings = Settings()
        result = settings.get_integration_path("/sites/abc/firewall/zones")
        assert result == "/proxy/network/integration/v1/sites/abc/firewall/zones"

    def test_get_integration_path_strips_leading_slash(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-v1")
        settings = Settings()
        result = settings.get_integration_path("sites/abc/devices")
        assert result == "/v1/sites/abc/devices"


class TestSettingsGetSiteApiPath:
    """Tests for Settings.get_site_api_path method."""

    def test_get_site_api_path_cloud_v1(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-v1")
        settings = Settings()
        result = settings.get_site_api_path("default", "devices")
        assert result == "/v1/devices"

    def test_get_site_api_path_cloud_ea(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()
        result = settings.get_site_api_path("default", "devices")
        assert result == "/ea/sites/default/devices"

    def test_get_site_api_path_local(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        settings = Settings()
        result = settings.get_site_api_path("default", "devices")
        assert result == "/proxy/network/api/s/default/devices"

    def test_get_site_api_path_strips_leading_slash(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        settings = Settings()
        result = settings.get_site_api_path("default", "/sta")
        assert result == "/proxy/network/api/s/default/sta"


class TestSettingsGetHeaders:
    """Tests for Settings.get_headers method."""

    def test_get_headers_includes_api_key(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "my-secret-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()
        headers = settings.get_headers()
        assert headers["X-API-KEY"] == "my-secret-key"

    def test_get_headers_content_type(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()
        headers = settings.get_headers()
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_accept(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        settings = Settings()
        headers = settings.get_headers()
        assert headers["Accept"] == "application/json"


class TestSettingsDefaults:
    """Tests for Settings default values."""

    def test_default_log_level(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        settings = Settings()
        assert settings.log_level == "INFO"

    def test_default_cache_ttl(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        settings = Settings()
        assert settings.cache_ttl == 300

    def test_default_rate_limit(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        settings = Settings()
        assert settings.rate_limit_requests == 100

    def test_default_site(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        settings = Settings()
        assert settings.default_site == "default"

    def test_api_type_accepts_valid_values(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        monkeypatch.delenv("UNIFI_LOCAL_HOST", raising=False)
        settings = Settings()
        assert settings.api_type == APIType.CLOUD_EA

    def test_default_cloud_api_url(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        settings = Settings()
        assert settings.cloud_api_url == "https://api.ui.com"

    def test_default_audit_log_enabled(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        settings = Settings()
        assert settings.audit_log_enabled is True
