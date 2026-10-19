"""Configuration management for UniFi MCP Server using Pydantic Settings."""

import difflib
import logging
import re
from enum import Enum
from typing import Any, Literal

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


logger = logging.getLogger(__name__)

#: Roles an MCP_AUTH_TOKEN entry may carry as a ``<role>:`` prefix.
AUTH_TOKEN_ROLES = ("viewer", "operator", "admin", "fleet-admin")


_ROLE_SHAPED_PREFIX = re.compile(r"[A-Za-z][A-Za-z_-]*")


def _check_unknown_role_prefix(prefix: str) -> None:
    """Refuse a near-miss role prefix; warn about any other word-like one.

    An entry whose prefix is not one of :data:`AUTH_TOKEN_ROLES` is a whole
    bare token, which is ``fleet-admin``. A mistyped role (``Viewer:``,
    ``veiwer:``, ``fleet_admin:``) would therefore hand out full admin while
    the operator meant to restrict it, so those stop the server. Messages
    never repeat the prefix, which is part of the secret in that case.

    Raises:
        ValueError: If the prefix differs from a role only in case, ``_`` for
            ``-``, or a small misspelling
    """
    normalized = prefix.lower().replace("_", "-")
    if normalized in AUTH_TOKEN_ROLES or difflib.get_close_matches(
        normalized, AUTH_TOKEN_ROLES, n=1, cutoff=0.8
    ):
        raise ValueError(
            "an MCP_AUTH_TOKEN entry starts with what looks like a misspelled role; "
            f"roles are written exactly as {', '.join(AUTH_TOKEN_ROLES)}"
        )
    logger.warning(
        "An MCP_AUTH_TOKEN entry contains ':' after a word that is not a role, so the "
        "whole entry is one fleet-admin token. Roles are written as <role>:<token> "
        "with one of: %s",
        ", ".join(AUTH_TOKEN_ROLES),
    )


def _parse_auth_token_entries(raw: str | None) -> dict[str, str]:
    """Split MCP_AUTH_TOKEN into a token-to-role mapping.

    Args:
        raw: Comma-separated entries, each ``<token>`` or ``<role>:<token>``

    Returns:
        Mapping of bearer token to role; a bare token is ``fleet-admin``

    Raises:
        ValueError: If an entry is ``<role>:`` with no token, or one token is
            listed with two different roles
    """
    roles: dict[str, str] = {}
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        prefix, sep, rest = entry.partition(":")
        if sep and prefix.strip() in AUTH_TOKEN_ROLES:
            role, token = prefix.strip(), rest.strip()
            if not token:
                raise ValueError(f"MCP_AUTH_TOKEN entry '{role}:' has no token")
        else:
            if sep and _ROLE_SHAPED_PREFIX.fullmatch(prefix.strip()):
                _check_unknown_role_prefix(prefix.strip())
            role, token = "fleet-admin", entry
        if roles.get(token, role) != role:
            # Never echo the token itself.
            raise ValueError("MCP_AUTH_TOKEN lists the same token with two different roles")
        roles[token] = role
    return roles


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

    retry_total_timeout: int = Field(
        default=60,
        description=(
            "Wall-clock budget in seconds for one request including all "
            "retries and backoff waits. Attempt-count limits alone let a "
            "single request burn (max_retries+1) x request_timeout; tools "
            "that authenticate first then stack two of those (issue #97)."
        ),
        validation_alias="UNIFI_RETRY_TOTAL_TIMEOUT",
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

    # Redis Configuration (cache). REDIS_URL, when set, takes precedence over
    # the individual host/port/db/password fields.
    redis_url: str | None = Field(
        default=None,
        description="Redis connection URL, e.g. redis://:password@host:6379/0",
        validation_alias="REDIS_URL",
        repr=False,
    )

    redis_host: str = Field(
        default="localhost",
        description="Redis host (ignored when REDIS_URL is set)",
        validation_alias="REDIS_HOST",
    )

    redis_port: int = Field(
        default=6379,
        description="Redis port (ignored when REDIS_URL is set)",
        validation_alias="REDIS_PORT",
    )

    redis_db: int = Field(
        default=0,
        description="Redis database number (ignored when REDIS_URL is set)",
        validation_alias="REDIS_DB",
    )

    redis_password: str | None = Field(
        default=None,
        description="Redis password (ignored when REDIS_URL is set)",
        validation_alias="REDIS_PASSWORD",
        repr=False,
    )

    webhook_secret: str | None = Field(
        default=None,
        description=(
            "HMAC-SHA256 key for verifying X-UniFi-Signature on incoming webhooks. "
            "Without it the webhook receiver refuses every request."
        ),
        validation_alias="WEBHOOK_SECRET",
        repr=False,
    )

    # Fleet registry (docs/FLEET_SCALING_PLAN.md Phase 2a). Setting DATABASE_URL
    # switches the controller registry from the single UNIFI_* controller to
    # Postgres; UNIFI_FLEET_CREDENTIAL_KEY must then be set as well.
    database_url: str | None = Field(
        default=None,
        description="Postgres URL for the controller registry, e.g. postgresql://user:pw@host/db",  # pragma: allowlist secret
        validation_alias="DATABASE_URL",
        repr=False,
    )

    fleet_registry_refresh_seconds: int = Field(
        default=30,
        ge=1,
        description="How often each server reloads the controller registry from Postgres",
        validation_alias="UNIFI_FLEET_REGISTRY_REFRESH_SECONDS",
    )

    fleet_max_open_clients: int = Field(
        default=256,
        ge=1,
        description=(
            "Most controller connections each server keeps open; the least recently "
            "used idle ones are closed beyond this"
        ),
        validation_alias="UNIFI_FLEET_MAX_OPEN_CLIENTS",
    )

    fleet_expected_replicas: int = Field(
        default=1,
        ge=1,
        description=(
            "How many processes (server replicas and workers) share each controller's rate "
            "limit. While Redis is unavailable each falls back to UNIFI_RATE_LIMIT_REQUESTS "
            "divided by this"
        ),
        validation_alias="UNIFI_FLEET_EXPECTED_REPLICAS",
    )

    # fleet_fanout: one read tool run on many controllers (FLEET_SCALING_PLAN.md §3.4).
    fleet_fanout_concurrency: int = Field(
        default=20,
        ge=1,
        description="Most controllers one fleet_fanout call reaches at once",
        validation_alias="UNIFI_FLEET_FANOUT_CONCURRENCY",
    )

    fleet_fanout_timeout_seconds: float = Field(
        default=15.0,
        gt=0,
        description="Default per-controller timeout of fleet_fanout",
        validation_alias="UNIFI_FLEET_FANOUT_TIMEOUT_SECONDS",
    )

    fleet_fanout_deadline_seconds: float = Field(
        default=60.0,
        gt=0,
        description=(
            "Default overall deadline of fleet_fanout; controllers not done by then "
            "are reported as timed out"
        ),
        validation_alias="UNIFI_FLEET_FANOUT_DEADLINE_SECONDS",
    )

    # Worker tier (python -m src.worker, docs/FLEET_SCALING_PLAN.md §3.5).
    fleet_worker_health_seconds: int = Field(
        default=60,
        ge=5,
        description="How often the worker health-checks each controller",
        validation_alias="UNIFI_FLEET_WORKER_HEALTH_SECONDS",
    )

    fleet_worker_sync_seconds: int = Field(
        default=900,
        ge=30,
        description="How often the worker refreshes each controller's sites and device inventory",
        validation_alias="UNIFI_FLEET_WORKER_SYNC_SECONDS",
    )

    fleet_worker_concurrency: int = Field(
        default=20,
        ge=1,
        description="Most controller jobs one worker runs at once",
        validation_alias="UNIFI_FLEET_WORKER_CONCURRENCY",
    )

    fleet_worker_lease_seconds: int = Field(
        default=30,
        ge=3,
        description=(
            "How long a worker's membership and controller leases last without renewal; "
            "a dead worker's controllers move to the others after this"
        ),
        validation_alias="UNIFI_FLEET_WORKER_LEASE_SECONDS",
    )

    fleet_worker_down_after: int = Field(
        default=3,
        ge=1,
        description=(
            "Consecutive failed health checks before a controller is marked down "
            "(earlier failures mark it degraded)"
        ),
        validation_alias="UNIFI_FLEET_WORKER_DOWN_AFTER",
    )

    stdio_role: Literal["viewer", "operator", "admin", "fleet-admin"] = Field(
        default="fleet-admin",
        description=(
            "Role of the local stdio caller. stdio is a single-user channel, so it "
            "defaults to full access; lower it to restrict what a local client may run."
        ),
        validation_alias="UNIFI_STDIO_ROLE",
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

    # Safety
    read_only: bool = Field(
        default=False,
        description=(
            "Register only non-mutating tools. When enabled, tools that can change "
            "controller state are never exposed to the MCP client."
        ),
        validation_alias="UNIFI_READ_ONLY",
    )

    dry_run: bool = Field(
        default=False,
        description=(
            "Global change-safe mode: every tool carrying a dry_run parameter "
            "executes as a preview (dry_run is forced on), and mutating tools "
            "without a dry_run gate are not registered. No write reaches the "
            "controller."
        ),
        validation_alias="UNIFI_DRY_RUN",
    )

    metrics_enabled: bool = Field(
        default=False,
        description=(
            "Record per-tool call counters and durations and expose them on a "
            "GET /metrics endpoint in Prometheus text exposition format. On "
            "network transports the endpoint requires the same bearer token "
            "as /mcp."
        ),
        validation_alias="UNIFI_METRICS_ENABLED",
    )

    # Audit Logging
    audit_log_enabled: bool = Field(
        default=True,
        description="Enable audit logging for mutating operations",
        validation_alias="UNIFI_AUDIT_LOG_ENABLED",
    )

    audit_log_file: str | None = Field(
        default=None,
        description=(
            "Path to the audit log file. Relative paths resolve against the "
            "process working directory, which is not predictable under stdio "
            "transport - prefer an absolute path."
        ),
        validation_alias="UNIFI_AUDIT_LOG_PATH",
    )

    audit_fail_closed: bool = Field(
        default=True,
        description=(
            "Refuse a mutating tool call when its audit record cannot be "
            "written, so no change reaches a controller unrecorded. Set to "
            "false only as a break-glass measure."
        ),
        validation_alias="UNIFI_AUDIT_FAIL_CLOSED",
    )

    # SIEM export (src/utils/siem.py, docs/FLEET_SCALING_PLAN.md §3.7).
    audit_siem_targets: str | None = Field(
        default=None,
        description=(
            "Comma-separated SIEM destinations for audit records: syslog+tls://host:6514, "
            "https://host/path (signed webhook) or otlp+https://collector:4318"
        ),
        validation_alias="UNIFI_AUDIT_SIEM_TARGETS",
        repr=False,
    )

    audit_siem_webhook_secret: str | None = Field(
        default=None,
        description="HMAC-SHA256 key signing webhook deliveries (required for https:// targets)",
        validation_alias="UNIFI_AUDIT_SIEM_WEBHOOK_SECRET",
        repr=False,
    )

    audit_siem_otlp_headers: str | None = Field(
        default=None,
        description="Extra headers for OTLP targets, as key=value,key=value (e.g. an API key)",
        validation_alias="UNIFI_AUDIT_SIEM_OTLP_HEADERS",
        repr=False,
    )

    audit_siem_ca_file: str | None = Field(
        default=None,
        description="CA bundle to verify SIEM targets with (system roots when unset)",
        validation_alias="UNIFI_AUDIT_SIEM_CA_FILE",
    )

    audit_siem_buffer_dir: str | None = Field(
        default=None,
        description=(
            "Where records wait for delivery (default: siem-buffer next to the audit log)"
        ),
        validation_alias="UNIFI_AUDIT_SIEM_BUFFER_DIR",
    )

    audit_siem_buffer_max_mb: int = Field(
        default=100,
        ge=1,
        description="Most undelivered data kept per target; the oldest is dropped beyond it",
        validation_alias="UNIFI_AUDIT_SIEM_BUFFER_MAX_MB",
    )

    audit_siem_anchor_seconds: int = Field(
        default=300,
        ge=10,
        description="How often each audit chain's head is sent to the SIEM as an anchor",
        validation_alias="UNIFI_AUDIT_SIEM_ANCHOR_SECONDS",
    )

    audit_log_rotate_mb: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Rotate the JSONL audit file at this size into <log>.<UTC time>Z files "
            "(read by the audit logger; unset never rotates)"
        ),
        validation_alias="UNIFI_AUDIT_LOG_ROTATE_MB",
    )

    # Audit retention (src/fleet/db/retention.py, docs/FLEET_SCALING_PLAN.md §3.7).
    audit_retention_days: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Archive and delete Postgres audit records older than this many days "
            "(python -m src.fleet.cli audit-retention); unset keeps them forever"
        ),
        validation_alias="UNIFI_AUDIT_RETENTION_DAYS",
    )

    audit_archive_dir: str | None = Field(
        default=None,
        description=(
            "Where retention writes its archives (default: audit-archive next to the audit log)"
        ),
        validation_alias="UNIFI_AUDIT_ARCHIVE_DIR",
    )

    # Backup download location
    backup_download_dir: str = Field(
        default=".",
        description=(
            "Directory that download_backup writes into. The caller supplies "
            "only the filename; any directory component is ignored and the "
            "file is confined to this directory."
        ),
        validation_alias="UNIFI_BACKUP_DOWNLOAD_DIR",
    )

    # Supermemory Configuration (optional operator notes/context store)
    supermemory_enabled: bool = Field(
        default=False,
        description="Enable Supermemory integration for persisting operator notes/context",
        validation_alias="SUPERMEMORY_ENABLED",
    )

    supermemory_api_key: str | None = Field(
        default=None,
        description="Supermemory API key (get one at https://console.supermemory.ai)",
        validation_alias="SUPERMEMORY_API_KEY",
    )

    # MCP Server Transport Configuration
    server_transport: TransportMode = Field(
        default=TransportMode.STDIO,
        description="MCP server transport mode: stdio (default), http, sse, or streamable_http",
        validation_alias="MCP_SERVER_TRANSPORT",
    )

    server_host: str = Field(
        default="127.0.0.1",
        description=(
            "Server bind address (used for http/sse/streamable_http transport). "
            "Defaults to loopback; set MCP_SERVER_HOST=0.0.0.0 to expose on all "
            "interfaces, which additionally requires MCP_AUTH_TOKEN."
        ),
        validation_alias="MCP_SERVER_HOST",
    )

    server_port: int = Field(
        default=3000,
        description="Server port (used for http/sse/streamable_http transport)",
        validation_alias="MCP_SERVER_PORT",
    )

    mcp_stateless_http: bool = Field(
        default=False,
        description=(
            "Serve Streamable HTTP without MCP sessions, so any replica can answer any "
            "request. No session survives between requests: select_controller is "
            "refused and every controller-bound call needs controller=<name> (or the "
            "registry default). The default, stateful mode needs sticky routing on "
            "mcp-session-id behind a load balancer."
        ),
        validation_alias="MCP_STATELESS_HTTP",
    )

    mcp_auth_token: str | None = Field(
        default=None,
        description=(
            "Bearer token(s) required to call the MCP server over a network "
            "transport (http/sse/streamable_http). Comma-separated to allow "
            "several. An entry may carry a role as <role>:<token> (viewer, "
            "operator, admin or fleet-admin); a bare token is fleet-admin. When "
            "unset, only the stdio transport may start. Ignored for stdio."
        ),
        validation_alias="MCP_AUTH_TOKEN",
    )

    @field_validator(
        "redis_url",
        "redis_password",
        "database_url",
        "webhook_secret",
        "audit_siem_targets",
        "audit_siem_webhook_secret",
        "audit_siem_otlp_headers",
        "audit_siem_ca_file",
        "audit_siem_buffer_dir",
        "audit_retention_days",
        "audit_archive_dir",
        "audit_log_rotate_mb",
        mode="before",
    )
    @classmethod
    def blank_secret_is_unset(cls, v: str | None) -> str | None:
        """Treat a blank value as unset.

        docker-compose forwards unset variables as empty strings
        (``${REDIS_PASSWORD:-}``), which must not become an empty password.
        """
        if isinstance(v, str) and not v.strip():
            return None
        return v

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

    @property
    def mcp_auth_tokens(self) -> list[str]:
        """Return the configured MCP bearer tokens as a list.

        Splits ``MCP_AUTH_TOKEN`` on commas and drops blanks so several
        tokens can be issued from one variable, and strips any ``<role>:``
        prefix (see :attr:`mcp_auth_token_roles`). Empty when unset.

        Returns:
            List of non-empty bearer tokens (possibly empty)
        """
        return list(self.mcp_auth_token_roles)

    @property
    def mcp_auth_token_roles(self) -> dict[str, str]:
        """Return each configured MCP bearer token with its role.

        An ``MCP_AUTH_TOKEN`` entry is either a bare token, which is a
        break-glass ``fleet-admin``, or ``<role>:<token>`` where the role is
        ``viewer``, ``operator``, ``admin`` or ``fleet-admin``. Only those
        four prefixes are read as roles, so any other token containing a
        colon is used whole.

        Returns:
            Mapping of bearer token to role, in configuration order

        Raises:
            ValueError: If an entry is ``<role>:`` with no token, or one token
                is listed with two different roles
        """
        return _parse_auth_token_entries(self.mcp_auth_token)

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

    def get_protect_integration_path(self, endpoint: str) -> str:
        """Get the correct UniFi Protect integration API endpoint path based on API type.

        For Cloud V1 API: Returns /v1/{endpoint}
        For Cloud EA API: Returns /integration/v1/{endpoint}
        For Local API: Returns /proxy/protect/integration/v1/{endpoint}

        Args:
            endpoint: The endpoint path (e.g., "cameras", "nvrs/nvr-1")

        Returns:
            Complete endpoint path with correct prefix

        Example:
            >>> settings.get_protect_integration_path("cameras")
            # Cloud V1: "/v1/cameras"
            # Cloud EA: "/integration/v1/cameras"
            # Local: "/proxy/protect/integration/v1/cameras"
        """
        # Remove leading slash if present for consistency
        endpoint = endpoint.lstrip("/")

        if self.api_type == APIType.CLOUD_V1:
            return f"/v1/{endpoint}"
        elif self.api_type == APIType.CLOUD_EA:
            return f"/integration/v1/{endpoint}"
        else:
            # Local gateways require /proxy/protect/ prefix for Protect API
            return f"/proxy/protect/integration/v1/{endpoint}"

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


class AuditMaintenanceSettings(BaseSettings):
    """What the audit retention job reads: same variables as :class:`Settings`.

    A database maintenance job needs no controller credentials, so this
    model leaves out ``UNIFI_API_KEY`` and everything else it does not use.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    read_only: bool = Field(default=False, validation_alias="UNIFI_READ_ONLY")
    audit_log_enabled: bool = Field(default=True, validation_alias="UNIFI_AUDIT_LOG_ENABLED")
    audit_log_file: str | None = Field(default=None, validation_alias="UNIFI_AUDIT_LOG_PATH")
    audit_retention_days: int | None = Field(
        default=None, ge=1, validation_alias="UNIFI_AUDIT_RETENTION_DAYS"
    )
    audit_archive_dir: str | None = Field(default=None, validation_alias="UNIFI_AUDIT_ARCHIVE_DIR")

    @field_validator("audit_log_file", "audit_retention_days", "audit_archive_dir", mode="before")
    @classmethod
    def blank_is_unset(cls, v: Any) -> Any:
        """Treat a blank value (as compose forwards an unset one) as unset."""
        if isinstance(v, str) and not v.strip():
            return None
        return v
