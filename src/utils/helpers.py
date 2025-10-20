"""Helper utility functions for UniFi MCP Server."""

import time
from datetime import datetime, timezone
from typing import Any


def get_timestamp() -> int:
    """Get current Unix timestamp in seconds.

    Returns:
        Current timestamp
    """
    return int(time.time())


def get_iso_timestamp() -> str:
    """Get current ISO 8601 formatted timestamp.

    Returns:
        ISO formatted timestamp string
    """
    return datetime.now(timezone.utc).isoformat()


def format_uptime(uptime_seconds: int) -> str:
    """Format uptime seconds into human-readable string.

    Args:
        uptime_seconds: Uptime in seconds

    Returns:
        Formatted uptime string (e.g., "2d 4h 30m")
    """
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
        parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
    elif hours > 0:
        parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
    else:
        parts.append(f"{minutes}m")

    return " ".join(parts)


def format_bytes(bytes_value: int, precision: int = 2) -> str:
    """Format bytes into human-readable string.

    Args:
        bytes_value: Number of bytes
        precision: Decimal precision

    Returns:
        Formatted bytes string (e.g., "1.23 GB")
    """
    bytes_float = float(bytes_value)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if bytes_float < 1024.0:
            return f"{bytes_float:.{precision}f} {unit}"
        bytes_float /= 1024.0
    return f"{bytes_float:.{precision}f} PB"


def format_percentage(value: float, precision: int = 1) -> str:
    """Format value as percentage string.

    Args:
        value: Decimal value (0.0 to 1.0 or 0 to 100)
        precision: Decimal precision

    Returns:
        Formatted percentage string (e.g., "45.3%")
    """
    # Handle both 0-1 and 0-100 ranges
    pct = value if value > 1 else value * 100
    return f"{pct:.{precision}f}%"


def sanitize_dict(data: dict[str, Any], exclude_keys: list[str] | None = None) -> dict[str, Any]:
    """Remove sensitive keys from dictionary.

    Args:
        data: Dictionary to sanitize
        exclude_keys: List of keys to remove (default: common sensitive keys)

    Returns:
        Sanitized dictionary copy
    """
    if exclude_keys is None:
        exclude_keys = ["password", "api_key", "secret", "token", "x_api_key", "x-api-key"]

    return {k: v for k, v in data.items() if k.lower() not in [e.lower() for e in exclude_keys]}


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two dictionaries, with override taking precedence.

    Args:
        base: Base dictionary
        override: Override dictionary

    Returns:
        Merged dictionary
    """
    result = base.copy()
    result.update(override)
    return result


def parse_device_type(model: str) -> str:
    """Parse device type from model string.

    Args:
        model: Device model string

    Returns:
        Device type (ap, switch, gateway, etc.)
    """
    model_lower = model.lower()

    if "uap" in model_lower or "u6" in model_lower or "u7" in model_lower:
        return "ap"
    elif "usw" in model_lower or "switch" in model_lower:
        return "switch"
    elif "usg" in model_lower or "udm" in model_lower or "uxg" in model_lower:
        return "gateway"
    elif "unvr" in model_lower or "nvr" in model_lower:
        return "nvr"
    else:
        return "unknown"


def build_uri(scheme: str, *parts: str, query: dict[str, Any] | None = None) -> str:
    """Build a URI with optional query parameters.

    Args:
        scheme: URI scheme (e.g., "sites")
        *parts: URI path parts
        query: Optional query parameters

    Returns:
        Complete URI string
    """
    path = "/".join(str(p) for p in parts if p)
    uri = f"{scheme}://{path}" if path else f"{scheme}://"

    if query:
        query_str = "&".join(f"{k}={v}" for k, v in query.items() if v is not None)
        if query_str:
            uri += f"?{query_str}"

    return uri
