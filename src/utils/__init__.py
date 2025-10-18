"""Utility modules for UniFi MCP Server."""

from .audit import AuditLogger, get_audit_logger, log_audit
from .exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    ConfirmationRequiredError,
    NetworkError,
    RateLimitError,
    ResourceNotFoundError,
    UniFiMCPException,
    ValidationError,
)
from .helpers import (
    build_uri,
    format_bytes,
    format_percentage,
    format_uptime,
    get_iso_timestamp,
    get_timestamp,
    merge_dicts,
    parse_device_type,
    sanitize_dict,
)
from .logger import get_logger, log_api_request, log_audit_event
from .validators import (
    validate_confirmation,
    validate_device_id,
    validate_ip_address,
    validate_limit_offset,
    validate_mac_address,
    validate_port,
    validate_site_id,
)

__all__ = [
    # Exceptions
    "UniFiMCPException",
    "ConfigurationError",
    "AuthenticationError",
    "APIError",
    "RateLimitError",
    "ResourceNotFoundError",
    "ValidationError",
    "NetworkError",
    "ConfirmationRequiredError",
    # Audit
    "AuditLogger",
    "get_audit_logger",
    "log_audit",
    # Logger
    "get_logger",
    "log_api_request",
    "log_audit_event",
    # Validators
    "validate_mac_address",
    "validate_ip_address",
    "validate_port",
    "validate_site_id",
    "validate_device_id",
    "validate_confirmation",
    "validate_limit_offset",
    # Helpers
    "get_timestamp",
    "get_iso_timestamp",
    "format_uptime",
    "format_bytes",
    "format_percentage",
    "sanitize_dict",
    "merge_dicts",
    "parse_device_type",
    "build_uri",
]
