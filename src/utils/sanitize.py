"""Data sanitization utilities for logging and audit trails.

Provides functions to sanitize sensitive data before logging to prevent
exposure of private information such as MAC addresses, IP addresses,
client identifiers, and network configuration details.
"""

import re
from typing import Any

# Sensitive field patterns
SENSITIVE_FIELDS = {
    # Network identifiers
    "mac",
    "mac_address",
    "client_mac",
    "device_mac",
    "bssid",
    "oui",
    # IP and network info
    "ip",
    "ip_address",
    "fixed_ip",
    "network_id",
    "subnet",
    "gateway",
    "dns",
    "dhcp_start",
    "dhcp_stop",
    # Device identifiers
    "device_id",
    "client_id",
    "user_id",
    "site_id",
    "serial",
    "serial_number",
    # Authentication
    "password",
    "passphrase",
    "psk",
    "key",
    "secret",
    "token",
    "api_key",
    # Personal information
    "email",
    "hostname",
    "name",
    "username",
    "user",
    # Location
    "latitude",
    "longitude",
    "location",
}

# Credential-bearing field patterns.
#
# A strict subset of SENSITIVE_FIELDS: these carry secrets rather than
# identifiers. Audit records need the identifiers to stay readable (an audit
# trail that cannot say which site or resource was touched has lost its
# purpose), but must never carry the secrets.
CREDENTIAL_FIELDS = {
    "password",
    "passphrase",
    "psk",
    "key",
    "secret",
    "token",
    "api_key",
}

# Partial redaction patterns (show last N characters)
PARTIAL_REDACT_FIELDS = {
    "mac",
    "mac_address",
    "client_mac",
    "device_mac",
    "ip",
    "ip_address",
}


def _redact_value(key: str, value: Any, partial: bool = True) -> str:
    """Redact a sensitive value.

    Args:
        key: Field name
        value: Value to redact
        partial: If True, show last few characters for debugging

    Returns:
        Redacted string representation
    """
    if value is None:
        return "None"

    str_value = str(value)

    # For MAC addresses and IPs, show last segment for debugging. Partial
    # reveal is only ever appropriate for network identifiers, never for
    # credentials: a trailing fragment of a passphrase or shared secret both
    # shrinks the search space and confirms guesses, and audit records are
    # persisted.
    is_partial_field = key.lower() in PARTIAL_REDACT_FIELDS
    if partial and is_partial_field:
        # MAC address: show last octet (XX:XX:XX:XX:XX:AB)
        if ":" in str_value and len(str_value) == 17:
            return f"**:**:**:**:**:{str_value[-2:]}"
        # IP address: show last octet (XXX.XXX.XXX.123)
        if "." in str_value and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", str_value):
            return f"***.***.***.{str_value.split('.')[-1]}"

    # Full redaction
    if len(str_value) <= 4 or not is_partial_field:
        return "***"
    return f"***{str_value[-2:]}" if partial else "***"


def sanitize_dict(data: dict[str, Any], partial: bool = True) -> dict[str, Any]:
    """Sanitize sensitive fields in a dictionary.

    Args:
        data: Dictionary potentially containing sensitive data
        partial: If True, partially redact some fields for debugging

    Returns:
        Dictionary with sensitive fields redacted
    """
    if not isinstance(data, dict):
        return data

    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()

        # Check if this key is sensitive
        is_sensitive = any(pattern in key_lower for pattern in SENSITIVE_FIELDS)

        if is_sensitive:
            # Redact the value
            sanitized[key] = _redact_value(key_lower, value, partial)
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries
            sanitized[key] = sanitize_dict(value, partial)
        elif isinstance(value, list):
            # Sanitize lists
            sanitized[key] = [
                sanitize_dict(item, partial) if isinstance(item, dict) else item for item in value
            ]
        else:
            # Keep non-sensitive values as-is
            sanitized[key] = value

    return sanitized


def sanitize_list(data: list[Any], partial: bool = True) -> list[Any]:
    """Sanitize sensitive fields in a list of dictionaries.

    Args:
        data: List of dictionaries potentially containing sensitive data
        partial: If True, partially redact some fields for debugging

    Returns:
        List with sensitive fields redacted
    """
    if not isinstance(data, list):
        return data

    return [sanitize_dict(item, partial) if isinstance(item, dict) else item for item in data]


def sanitize_log_message(message: str, context: dict[str, Any] | None = None) -> str:
    """Sanitize a log message and optional context.

    Args:
        message: Log message to sanitize
        context: Optional context dictionary to include

    Returns:
        Sanitized log message with context
    """
    # Sanitize common patterns in the message itself
    sanitized_msg = message

    # Redact MAC addresses (XX:XX:XX:XX:XX:XX)
    sanitized_msg = re.sub(
        r"\b([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})\b",
        lambda m: f"**:**:**:**:**:{m.group(2)}",
        sanitized_msg,
    )

    # Redact IP addresses (XXX.XXX.XXX.XXX)
    _zero_ip = "0.0.0.0"  # nosec B104 — string comparison, not a bind address
    sanitized_msg = re.sub(
        r"\b(\d{1,3}\.){3}(\d{1,3})\b",
        lambda m: f"***.***.***.{m.group(2)}" if m.group(0) != _zero_ip else m.group(0),
        sanitized_msg,
    )

    # Add sanitized context if provided
    if context:
        sanitized_context = sanitize_dict(context)
        sanitized_msg = f"{sanitized_msg} | Context: {sanitized_context}"

    return sanitized_msg


def is_production() -> bool:
    """Check if running in production environment.

    Returns:
        True if production, False otherwise
    """
    import os

    return os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod")


def sanitize_for_logging(
    data: dict[str, Any] | list[Any] | str,
    force_sanitize: bool = False,
) -> dict[str, Any] | list[Any] | str:
    """Sanitize data for logging based on environment.

    In production, always sanitizes. In development, only sanitizes if forced.

    Args:
        data: Data to potentially sanitize
        force_sanitize: Force sanitization even in development

    Returns:
        Sanitized or original data based on environment
    """
    # Always sanitize in production or when forced
    if is_production() or force_sanitize:
        if isinstance(data, dict):
            return sanitize_dict(data)
        elif isinstance(data, list):
            return sanitize_list(data)
        elif isinstance(data, str):
            return sanitize_log_message(data)

    # In development, return original data for debugging
    return data


# Convenience function for backward compatibility
def sanitize_sensitive_data(
    data: dict[str, Any] | list[Any], partial: bool = True
) -> dict[str, Any] | list[Any]:
    """Sanitize sensitive data (legacy function name).

    Args:
        data: Data to sanitize
        partial: If True, partially redact some fields for debugging

    Returns:
        Sanitized data
    """
    if isinstance(data, dict):
        return sanitize_dict(data, partial)
    elif isinstance(data, list):
        return sanitize_list(data, partial)
    return data


def sanitize_credentials(data: dict[str, Any]) -> dict[str, Any]:
    """Redact only credential-bearing fields, leaving identifiers intact.

    Unlike :func:`sanitize_dict`, which also redacts identifiers such as
    ``site_id``, ``name`` and ``mac``, this keeps those readable. Use it where
    the record must stay diagnostically useful — audit trails above all — while
    still never persisting a secret. Redaction is always full: no trailing
    fragment of a credential is preserved.

    Args:
        data: Dictionary potentially containing credentials

    Returns:
        Dictionary with credential fields redacted
    """
    if not isinstance(data, dict):
        return data

    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()

        if any(pattern in key_lower for pattern in CREDENTIAL_FIELDS):
            sanitized[key] = "***" if value is not None else None
        elif isinstance(value, dict):
            sanitized[key] = sanitize_credentials(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_credentials(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


# A credential-named key followed by ``:`` or ``=`` and its value, in free
# text: JSON and Python reprs (``"x_passphrase": "..."``), query strings
# (``?apikey=...``) and headers (``X-API-KEY: ...``). The key matches the way
# :func:`sanitize_credentials` matches dict keys: by substring.
_CREDENTIAL_PAIR = re.compile(
    r"""(?P<lead>(?P<q>["']?)[\w.-]*(?:"""
    + "|".join(sorted(CREDENTIAL_FIELDS, key=len, reverse=True))
    + r""")[\w.-]*(?P=q)\s*[:=]\s*)"""
    r"""(?P<value>"[^"]*"|'[^']*'|[^\s,;&}\]"']+)""",
    re.IGNORECASE,
)

#: ``Authorization: Bearer <token>`` and similar schemes.
_AUTH_SCHEME = re.compile(r"\b(?P<scheme>Bearer|Basic|Token)\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)

#: Credentials in a URL: ``scheme://user:password@host``.  # pragma: allowlist secret
_URL_USERINFO = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@", re.IGNORECASE)


def sanitize_error_text(text: str) -> str:
    """Redact credentials quoted back in error text, leaving identifiers intact.

    Controller and HTTP errors echo what they were sent: a rejected WLAN
    payload with its passphrase, a request URL with an API key, a header.
    Audit records store that text, so it gets the same rule as
    :func:`sanitize_credentials` applies to parameters: secrets go, while
    identifiers such as the MAC in ``api.err.MacUsed`` stay readable.

    Args:
        text: Error message

    Returns:
        The message with credential values replaced by ``***``
    """
    if not isinstance(text, str):
        return text

    def pair(match: re.Match[str]) -> str:
        value = match.group("value")
        quote = value[0] if value[:1] in ("'", '"') else ""
        return f"{match.group('lead')}{quote}***{quote}"

    text = _URL_USERINFO.sub(lambda m: f"{m.group('scheme')}***@", text)
    text = _AUTH_SCHEME.sub(lambda m: f"{m.group('scheme')} ***", text)
    return _CREDENTIAL_PAIR.sub(pair, text)
