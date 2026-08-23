"""Utility modules for UniFi MCP Server."""

from .audit import AuditLogger, audit_action, get_audit_logger, log_audit
from .exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    ConfirmationRequiredError,
    DuplicateResourceError,
    NetworkError,
    RateLimitError,
    ResourceNotFoundError,
    UniFiMCPException,
    ValidationError,
)
from .helpers import (
    build_uri,
    first_response_item,
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
from .sanitize import (
    sanitize_credentials,
    sanitize_for_logging,
    sanitize_list,
    sanitize_log_message,
    sanitize_sensitive_data,
)
from .sanitize import sanitize_dict as sanitize_sensitive_dict
from .validators import (
    coerce_bool,
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
    "DuplicateResourceError",
    # Audit
    "AuditLogger",
    "get_audit_logger",
    "log_audit",
    "audit_action",
    # Logger
    "get_logger",
    "log_api_request",
    "log_audit_event",
    # Sanitization
    "sanitize_sensitive_dict",
    "sanitize_for_logging",
    "sanitize_list",
    "sanitize_log_message",
    "sanitize_sensitive_data",
    # Validators
    "coerce_bool",
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
    "sanitize_credentials",
    "sanitize_dict",
    "merge_dicts",
    "parse_device_type",
    "build_uri",
    "first_response_item",
]
