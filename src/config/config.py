"""Configuration management for UniFi MCP Server using Pydantic Settings."""

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIType(str, Enum):
    """API connection type enumeration."""

    CLOUD = "cloud"
    LOCAL = "local"


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
        default=APIType.CLOUD,
        description="API connection type: 'cloud' or 'local'",
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
        if self.api_type == APIType.CLOUD:
            return self.cloud_api_url
        else:
            protocol = "https" if self.local_verify_ssl else "http"
            return f"{protocol}://{self.local_host}:{self.local_port}"

    @property
    def verify_ssl(self) -> bool:
        """Get SSL verification setting based on API type.

        Returns:
            Whether to verify SSL certificates
        """
        if self.api_type == APIType.CLOUD:
            return True
        return self.local_verify_ssl

    def get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests.

        Returns:
            Dictionary of HTTP headers
        """
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
