"""Configuration management for UniFi MCP Server using Pydantic Settings."""

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIType(str, Enum):
    """API connection type enumeration."""

    CLOUD_V1 = "cloud-v1"  # Official stable v1 API
    CLOUD_EA = "cloud-ea"  # Early Access API
    LOCAL = "local"  # Direct gateway access

    # Legacy alias for backward compatibility (defaults to EA)
    CLOUD = "cloud-ea"


class TransportMode(str, Enum):
    """MCP server transport mode enumeration."""

    STDIO = "stdio"  # Default: stdin/stdout for local subprocess
    HTTP = "http"  # HTTP server for network access
    SSE = "sse"  # Server-Sent Events for MCP gateways
    STREAMABLE_HTTP = "streamable_http"  # Modern HTTP transport


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Configuration
    api_key: str = Field(
        ...,
        description="UniFi API key (X-API-Key header)",
        validation_alias="UNIFI_API_KEY",
    )

    api_type: APIType = Field(
        default=APIType.CLOUD_EA,
        description="API connection type: 'cloud-v1' (stable), 'cloud-ea' (early access), or 'local' (gateway)",
        validation_alias="UNIFI_API_TYPE",
    )

    # Cloud API Configuration
    cloud_api_url: str = Field(
        default="https://api.ui.com",
        description="UniFi Cloud API base URL",
        validation_alias="UNIFI_CLOUD_API_URL",
    )

    # Local API Configuration
    local_host: str | None = Field(
        default=None,
        description="Local UniFi controller hostname/IP",
        validation_alias="UNIFI_LOCAL_HOST",
    )

    local_port: int = Field(
        default=443,
        description="Local UniFi controller port",
        validation_alias="UNIFI_LOCAL_PORT",
    )

    local_verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificates for local controller",
        validation_alias="UNIFI_LOCAL_VERIFY_SSL",
    )

    # Site Configuration
    default_site: str = Field(
        default="default",
        description="Default site ID to use",
        validation_alias="UNIFI_DEFAULT_SITE",
    )

    # Site Manager API Configuration
    site_manager_enabled: bool = Field(
        default=False,
        description="Enable Site Manager API (multi-site management)",
        validation_alias="UNIFI_SITE_MANAGER_ENABLED",
    )

    # Rate Limiting Configuration
    rate_limit_requests: int = Field(
        default=100,
        description="Maximum requests per minute (EA tier: 100, v1 tier: 10000)",
        validation_alias="UNIFI_RATE_LIMIT_REQUESTS",
    )

    rate_limit_period: int = Field(
        default=60,
        description="Rate limit period in seconds",
        validation_alias="UNIFI_RATE_LIMIT_PERIOD",
    )

    # Retry Configuration
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for failed requests",
        validation_alias="UNIFI_MAX_RETRIES",
    )

    retry_backoff_factor: float = Field(
        default=2.0,
        description="Exponential backoff factor for retries",
        validation_alias="UNIFI_RETRY_BACKOFF_FACTOR",
    )

    # Timeout Configuration
    request_timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
        validation_alias="UNIFI_REQUEST_TIMEOUT",
    )

    # Caching Configuration
    cache_enabled: bool = Field(
        default=True,
        description="Enable response caching",
        validation_alias="UNIFI_CACHE_ENABLED",
    )

    cache_ttl: int = Field(
        default=300,
        description="Cache TTL in seconds (default: 5 minutes)",
        validation_alias="UNIFI_CACHE_TTL",
    )

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
        validation_alias="LOG_LEVEL",
    )

    log_api_requests: bool = Field(
        default=True,
        description="Log all API requests",
        validation_alias="LOG_API_REQUESTS",
    )

    # Audit Logging
    audit_log_enabled: bool = Field(
        default=True,
        description="Enable audit logging for mutating operations",
        validation_alias="UNIFI_AUDIT_LOG_ENABLED",
    )

    # MCP Server Transport Configuration
    server_transport: TransportMode = Field(
        default=TransportMode.STDIO,
        description="MCP server transport mode: stdio (default), http, sse, or streamable_http",
        validation_alias="MCP_SERVER_TRANSPORT",
    )

    server_host: str = Field(
        default="0.0.0.0",  # nosec B104 — intentional; overridable via MCP_SERVER_HOST env var
        description="Server bind address (used for http/sse/streamable_http transport)",
        validation_alias="MCP_SERVER_HOST",
    )

    server_port: int = Field(
        default=3000,
        description="Server port (used for http/sse/streamable_http transport)",
        validation_alias="MCP_SERVER_PORT",
    )

    @field_validator("api_type", mode="before")
    @classmethod
    def validate_api_type(cls, v: str) -> APIType:
        """Validate and convert API type to enum.

        Args:
            v: API type string

        Returns:
            APIType enum value
        """
        if isinstance(v, APIType):
            return v
        return APIType(v.lower())

    @field_validator("local_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port number is in valid range.

        Args:
            v: Port number

        Returns:
            Validated port number

        Raises:
            ValueError: If port is invalid
        """
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    @field_validator("server_port")
    @classmethod
    def validate_server_port(cls, v: int) -> int:
        """Validate server port number is in valid range.

        Args:
            v: Server port number

        Returns:
            Validated server port number

        Raises:
            ValueError: If server port is invalid
        """
        if not 1 <= v <= 65535:
            raise ValueError(f"Server port must be between 1 and 65535, got {v}")
        return v

    @field_validator("server_transport", mode="before")
    @classmethod
    def validate_server_transport(cls, v: str) -> TransportMode:
        """Validate and convert transport mode to enum.

        Args:
            v: Transport mode string

        Returns:
            TransportMode enum value
        """
        if isinstance(v, TransportMode):
            return v
        return TransportMode(v.lower())

    @model_validator(mode="after")
    def validate_local_configuration(self) -> "Settings":
        """Validate that local API has required configuration.

        Returns:
            Validated settings instance

        Raises:
            ValueError: If local API is selected but host is not provided
        """
        if self.api_type == APIType.LOCAL and not self.local_host:
            raise ValueError("local_host is required when api_type is 'local'")
        return self

    @property
    def base_url(self) -> str:
        """Get the appropriate base URL based on API type.

        Returns:
            Base URL for API requests
        """
        if self.api_type in (APIType.CLOUD_V1, APIType.CLOUD_EA):
            return self.cloud_api_url
        else:
            # Always use HTTPS for local gateways (port 443)
            # SSL verification is controlled separately via verify_ssl property
            return f"https://{self.local_host}:{self.local_port}"

    @property
    def verify_ssl(self) -> bool:
        """Get SSL verification setting based on API type.

        Returns:
            Whether to verify SSL certificates
        """
        if self.api_type in (APIType.CLOUD_V1, APIType.CLOUD_EA):
            return True
        return self.local_verify_ssl

    def get_integration_path(self, endpoint: str) -> str:
        """Get the correct integration API endpoint path based on API type.

        For Cloud V1 API: Returns /v1/{endpoint}
        For Cloud EA API: Returns /integration/v1/{endpoint} (ZBF not supported on Cloud)
        For Local API: Returns /proxy/network/integration/v1/{endpoint}

        Args:
            endpoint: The endpoint path starting with /sites/... (e.g., "/sites/default/firewall/zones")

        Returns:
            Complete endpoint path with correct prefix

        Example:
            >>> settings.get_integration_path("/sites/abc/firewall/zones")
            # Cloud V1: "/v1/sites/abc/firewall/zones"
            # Cloud EA: "/integration/v1/sites/abc/firewall/zones"
            # Local: "/proxy/network/integration/v1/sites/abc/firewall/zones"
        """
        # Remove leading slash if present for consistency
        endpoint = endpoint.lstrip("/")

        if self.api_type == APIType.CLOUD_V1:
            return f"/v1/{endpoint}"
        elif self.api_type == APIType.CLOUD_EA:
            return f"/integration/v1/{endpoint}"
        else:
            # Local gateways require /proxy/network/ prefix
            return f"/proxy/network/integration/v1/{endpoint}"

    def get_site_api_path(self, site_id: str, endpoint: str) -> str:
        """Get the correct standard UniFi API endpoint path based on API type.

        For Cloud V1 API: Returns /v1/{endpoint} (site-less endpoints like /hosts)
        For Cloud EA API: Returns /ea/sites/{site_id}/{endpoint}
        For Local API: Returns /proxy/network/api/s/{site_id}/{endpoint}

        Args:
            site_id: The site ID (may be unused for Cloud V1 top-level endpoints)
            endpoint: The endpoint path (e.g., "devices", "sta", "rest/networkconf")

        Returns:
            Complete endpoint path with correct prefix

        Example:
            >>> settings.get_site_api_path("default", "devices")
            # Cloud V1: "/v1/hosts" (devices are under hosts endpoint)
            # Cloud EA: "/ea/sites/default/devices"
            # Local: "/proxy/network/api/s/default/devices"
        """
        # Remove leading slash if present for consistency
        endpoint = endpoint.lstrip("/")

        if self.api_type == APIType.CLOUD_V1:
            # V1 API uses top-level endpoints without site_id in path
            # Note: For v1, endpoints like "devices" are accessed via /v1/hosts
            return f"/v1/{endpoint}"
        elif self.api_type == APIType.CLOUD_EA:
            return f"/ea/sites/{site_id}/{endpoint}"
        else:
            # Local gateways use /proxy/network/api/s/ prefix
            return f"/proxy/network/api/s/{site_id}/{endpoint}"

    def get_v2_api_path(self, site_id: str) -> str:
        """Get the v2 API endpoint path for local gateway access.

        The v2 API is only available on local gateways and provides access to
        features like firewall policies that are not available via the cloud API.

        Args:
            site_id: The site identifier

        Returns:
            Complete endpoint path: /proxy/network/v2/api/site/{site_id}

        Raises:
            NotImplementedError: If api_type is not LOCAL (v2 API only works locally)

        Example:
            >>> settings.get_v2_api_path("default")
            # Local: "/proxy/network/v2/api/site/default"
        """
        if self.api_type != APIType.LOCAL:
            raise NotImplementedError(
                "v2 API is only available with local gateway access. "
                "Set UNIFI_API_TYPE=local and configure UNIFI_LOCAL_HOST."
            )
        return f"/proxy/network/v2/api/site/{site_id}"

    def get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests.

        Returns:
            Dictionary of HTTP headers
        """
        return {
            "X-API-KEY": self.api_key,  # UniFi API expects all caps
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
