"""Unit tests for src/config/config.py Settings class."""

import certifi
import pytest

from src.config.config import APIType, Settings, TransportMode


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


class TestSettingsTransportConfiguration:
    """Tests for MCP server transport configuration."""

    def test_default_transport_is_stdio(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        settings = Settings()
        assert settings.server_transport == TransportMode.STDIO

    def test_default_host(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        settings = Settings()
        # Defaults to loopback; exposing on all interfaces is an explicit
        # opt-in that also requires MCP_AUTH_TOKEN.
        assert settings.server_host == "127.0.0.1"

    def test_default_port(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        settings = Settings()
        assert settings.server_port == 3000

    def test_transport_sse(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("MCP_SERVER_TRANSPORT", "sse")
        settings = Settings()
        assert settings.server_transport == TransportMode.SSE

    def test_transport_http(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("MCP_SERVER_TRANSPORT", "http")
        settings = Settings()
        assert settings.server_transport == TransportMode.HTTP

    def test_transport_streamable_http(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("MCP_SERVER_TRANSPORT", "streamable_http")
        settings = Settings()
        assert settings.server_transport == TransportMode.STREAMABLE_HTTP

    def test_transport_uppercase(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("MCP_SERVER_TRANSPORT", "SSE")
        settings = Settings()
        assert settings.server_transport == TransportMode.SSE

    def test_custom_port(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("MCP_SERVER_PORT", "8080")
        settings = Settings()
        assert settings.server_port == 8080

    def test_custom_host(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("MCP_SERVER_HOST", "127.0.0.1")
        settings = Settings()
        assert settings.server_host == "127.0.0.1"

    def test_server_port_min_boundary(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("MCP_SERVER_PORT", "1")
        settings = Settings()
        assert settings.server_port == 1

    def test_server_port_max_boundary(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("MCP_SERVER_PORT", "65535")
        settings = Settings()
        assert settings.server_port == 65535

    def test_server_port_zero_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("MCP_SERVER_PORT", "0")
        with pytest.raises(ValueError) as exc_info:
            Settings()
        assert "Server port must be between 1 and 65535" in str(exc_info.value)

    def test_server_port_too_high_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("MCP_SERVER_PORT", "65536")
        with pytest.raises(ValueError) as exc_info:
            Settings()
        assert "Server port must be between 1 and 65535" in str(exc_info.value)


class TestSettingsRedis:
    """Redis settings: the documented REDIS_* names must reach Settings."""

    @pytest.fixture(autouse=True)
    def _clean_redis_env(self, monkeypatch: pytest.MonkeyPatch):
        for name in ("REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_PASSWORD"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")

    def test_defaults(self):
        settings = Settings()
        assert settings.redis_url is None
        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379
        assert settings.redis_db == 0
        assert settings.redis_password is None

    def test_reads_documented_env_names(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REDIS_HOST", "redis.internal")
        monkeypatch.setenv("REDIS_PORT", "6380")
        monkeypatch.setenv("REDIS_DB", "2")
        monkeypatch.setenv("REDIS_PASSWORD", "s3cret")
        settings = Settings()
        assert settings.redis_host == "redis.internal"
        assert settings.redis_port == 6380
        assert settings.redis_db == 2
        assert settings.redis_password == "s3cret"  # pragma: allowlist secret

    def test_reads_redis_url(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REDIS_URL", "redis://:pw@cache:6379/1")
        assert Settings().redis_url == "redis://:pw@cache:6379/1"

    def test_blank_values_mean_unset(self, monkeypatch: pytest.MonkeyPatch):
        # docker-compose forwards ``${REDIS_PASSWORD:-}`` as an empty string
        monkeypatch.setenv("REDIS_PASSWORD", "")
        monkeypatch.setenv("REDIS_URL", "  ")
        settings = Settings()
        assert settings.redis_password is None
        assert settings.redis_url is None

    def test_secrets_not_in_repr(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REDIS_PASSWORD", "s3cret")
        monkeypatch.setenv("REDIS_URL", "redis://:urlsecret@cache:6379/0")
        text = repr(Settings())
        assert "s3cret" not in text
        assert "urlsecret" not in text


class TestSettingsWebhookSecret:
    """WEBHOOK_SECRET is documented in README, API.md and docker-compose.yml."""

    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")

    def test_default_unset(self):
        assert Settings().webhook_secret is None

    def test_reads_documented_env_name(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("WEBHOOK_SECRET", "hook-secret")  # pragma: allowlist secret
        assert Settings().webhook_secret == "hook-secret"  # pragma: allowlist secret

    def test_blank_means_unset(self, monkeypatch: pytest.MonkeyPatch):
        # docker-compose forwards ``${WEBHOOK_SECRET:-}`` as an empty string
        monkeypatch.setenv("WEBHOOK_SECRET", " ")
        assert Settings().webhook_secret is None

    def test_not_in_repr(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("WEBHOOK_SECRET", "hook-secret")  # pragma: allowlist secret
        assert "hook-secret" not in repr(Settings())


class TestSettingsStatelessHttp:
    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("MCP_STATELESS_HTTP", raising=False)
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")

    def test_default_off(self):
        assert Settings().mcp_stateless_http is False

    def test_reads_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("MCP_STATELESS_HTTP", "true")
        assert Settings().mcp_stateless_http is True


class TestDocumentedSettings:
    """Every setting is documented, and the docs name no setting that does not exist."""

    #: Read with os.environ outside Settings (key material and CLI-only URLs).
    OUTSIDE_SETTINGS = {
        "DEBUG",
        "MIGRATION_DATABASE_URL",
        "UNIFI_AUDIT_CHAIN_KEY",
        "UNIFI_AUDIT_LOG_KEY",
        "UNIFI_AUDIT_ENCRYPTION_KEY",
        "UNIFI_FLEET_CREDENTIAL_KEY",
        "UNIFI_PROFILE",
    }
    #: Third-party variables the docs mention (agnost.ai monitoring, MCP Toolbox).
    THIRD_PARTY = {
        "AGNOST_ENABLED",
        "AGNOST_ORG_ID",
        "AGNOST_ENDPOINT",
        "AGNOST_DISABLE_INPUT",
        "AGNOST_DISABLE_OUTPUT",
        "TOOLBOX_PORT",
        "TOOLBOX_SERVICE_NAME",
        "TOOLBOX_TELEMETRY_OTLP",
        "TOOLBOX_VERSION",
    }
    #: In Settings but deliberately left out of .env.example.
    NOT_IN_ENV_EXAMPLE = {"UNIFI_CACHE_TTL"}

    @staticmethod
    def _aliases() -> set[str]:
        return {str(field.validation_alias) for field in Settings.model_fields.values()}

    @staticmethod
    def _read(name: str) -> str:
        from pathlib import Path

        return (Path(__file__).parents[3] / name).read_text(encoding="utf-8")

    def _api_rows(self) -> set[str]:
        """Variable names in API.md's environment-variable table."""
        import re

        text = self._read("API.md")
        start = text.index("### Environment Variables")
        end = text.index("\n### ", start + 1)
        names: set[str] = set()
        for cell in re.findall(r"^\| ([^|]+) \|", text[start:end], re.M):
            names.update(re.findall(r"`([A-Z][A-Z0-9_]+)`", cell))
        return names - {"Variable"}

    def _env_assignments(self) -> set[str]:
        """Names assigned (or shown commented out) in .env.example."""
        import re

        return set(re.findall(r"^#? ?([A-Z][A-Z0-9_]+)=", self._read(".env.example"), re.M))

    def test_every_setting_is_in_api_md(self) -> None:
        assert sorted(self._aliases() - self._api_rows()) == []

    def test_every_setting_is_in_env_example(self) -> None:
        missing = self._aliases() - self.NOT_IN_ENV_EXAMPLE - self._env_assignments()
        assert sorted(missing) == []

    def test_api_md_names_no_unknown_setting(self) -> None:
        unknown = self._api_rows() - self._aliases() - self.OUTSIDE_SETTINGS - self.THIRD_PARTY
        assert sorted(unknown) == []

    def test_env_example_names_no_unknown_setting(self) -> None:
        unknown = (
            self._env_assignments() - self._aliases() - self.OUTSIDE_SETTINGS - self.THIRD_PARTY
        )
        assert sorted(unknown) == []


class TestLocalTLSSettings:
    """UNIFI_LOCAL_VERIFY_SSL, UNIFI_LOCAL_CA_FILE and the startup warning."""

    @pytest.fixture
    def local_env(self, monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "local")
        monkeypatch.setenv("UNIFI_LOCAL_HOST", "192.168.2.1")
        return monkeypatch

    def test_verification_is_on_by_default(self, local_env):
        settings = Settings()
        assert settings.local_verify_ssl is True
        assert settings.verify_ssl is True
        assert settings.tls_warnings() == []

    def test_ca_file_becomes_the_verify_value(self, local_env):
        local_env.setenv("UNIFI_LOCAL_CA_FILE", certifi.where())
        assert Settings().verify_ssl == certifi.where()

    def test_blank_ca_file_is_unset(self, local_env):
        local_env.setenv("UNIFI_LOCAL_CA_FILE", "")
        settings = Settings()
        assert settings.local_ca_file is None
        assert settings.verify_ssl is True

    def test_missing_ca_file_fails_at_startup(self, local_env, tmp_path):
        local_env.setenv("UNIFI_LOCAL_CA_FILE", str(tmp_path / "missing.pem"))
        with pytest.raises(ValueError, match="UNIFI_LOCAL_CA_FILE"):
            Settings()

    def test_ca_file_without_a_certificate_fails_at_startup(self, local_env, tmp_path):
        bogus = tmp_path / "bogus.pem"
        bogus.write_text("not a certificate\n")
        local_env.setenv("UNIFI_LOCAL_CA_FILE", str(bogus))
        with pytest.raises(ValueError, match="UNIFI_LOCAL_CA_FILE"):
            Settings()

    def test_verification_off_warns(self, local_env):
        local_env.setenv("UNIFI_LOCAL_VERIFY_SSL", "false")
        settings = Settings()
        assert settings.verify_ssl is False
        warnings = settings.tls_warnings()
        assert len(warnings) == 1
        assert "verification is OFF" in warnings[0]
        assert "https://192.168.2.1:443" in warnings[0]

    def test_verification_off_ignores_the_ca_file_and_says_so(self, local_env):
        local_env.setenv("UNIFI_LOCAL_VERIFY_SSL", "false")
        local_env.setenv("UNIFI_LOCAL_CA_FILE", certifi.where())
        settings = Settings()
        assert settings.verify_ssl is False
        assert any("ignored" in w for w in settings.tls_warnings())

    def test_cloud_always_verifies_and_never_warns(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("UNIFI_API_KEY", "test-key")
        monkeypatch.setenv("UNIFI_API_TYPE", "cloud-ea")
        monkeypatch.setenv("UNIFI_LOCAL_VERIFY_SSL", "false")
        settings = Settings()
        assert settings.verify_ssl is True
        assert settings.tls_warnings() == []
