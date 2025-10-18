"""Input validation functions for UniFi MCP Server."""

import re
from typing import Any, Optional

from .exceptions import ValidationError


def validate_mac_address(mac: str) -> str:
    """Validate and normalize MAC address.

    Args:
        mac: MAC address string

    Returns:
        Normalized MAC address (lowercase, colon-separated)

    Raises:
        ValidationError: If MAC address is invalid
    """
    # Remove common separators
    cleaned = re.sub(r"[:\-\.]", "", mac.lower())

    # Check if valid hex and correct length
    if not re.match(r"^[0-9a-f]{12}$", cleaned):
        raise ValidationError(f"Invalid MAC address format: {mac}")

    # Format as colon-separated
    return ":".join([cleaned[i : i + 2] for i in range(0, 12, 2)])


def validate_ip_address(ip: str) -> str:
    """Validate IPv4 address.

    Args:
        ip: IP address string

    Returns:
        Validated IP address

    Raises:
        ValidationError: If IP address is invalid
    """
    parts = ip.split(".")
    if len(parts) != 4:
        raise ValidationError(f"Invalid IP address format: {ip}")

    try:
        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                raise ValidationError(f"Invalid IP address octet: {part}")
    except ValueError as e:
        raise ValidationError(f"Invalid IP address format: {ip}") from e

    return ip


def validate_port(port: int) -> int:
    """Validate port number.

    Args:
        port: Port number

    Returns:
        Validated port number

    Raises:
        ValidationError: If port is invalid
    """
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise ValidationError(f"Invalid port number: {port}")

    return port


def validate_site_id(site_id: str) -> str:
    """Validate site ID format.

    Args:
        site_id: Site identifier

    Returns:
        Validated site ID

    Raises:
        ValidationError: If site ID is invalid
    """
    if not site_id or not isinstance(site_id, str):
        raise ValidationError("Site ID cannot be empty")

    # Site IDs should be alphanumeric with hyphens/underscores
    if not re.match(r"^[a-zA-Z0-9_\-]+$", site_id):
        raise ValidationError(f"Invalid site ID format: {site_id}")

    return site_id


def validate_device_id(device_id: str) -> str:
    """Validate device ID format.

    Args:
        device_id: Device identifier

    Returns:
        Validated device ID

    Raises:
        ValidationError: If device ID is invalid
    """
    if not device_id or not isinstance(device_id, str):
        raise ValidationError("Device ID cannot be empty")

    # Device IDs are typically 24-character hex strings (MongoDB ObjectId)
    if not re.match(r"^[a-f0-9]{24}$", device_id.lower()):
        raise ValidationError(f"Invalid device ID format: {device_id}")

    return device_id.lower()


def validate_confirmation(confirm: Optional[bool], operation: str) -> None:
    """Validate that confirmation is provided for mutating operations.

    Args:
        confirm: Confirmation flag
        operation: Operation name

    Raises:
        ValidationError: If confirmation is not provided
    """
    if not confirm:
        raise ValidationError(
            f"Operation '{operation}' requires confirmation. Set confirm=true to proceed."
        )


def validate_limit_offset(limit: Optional[int] = None, offset: Optional[int] = None) -> tuple[int, int]:
    """Validate and normalize pagination parameters.

    Args:
        limit: Maximum number of items to return
        offset: Number of items to skip

    Returns:
        Tuple of (limit, offset) with defaults applied

    Raises:
        ValidationError: If parameters are invalid
    """
    # Set defaults
    final_limit = limit if limit is not None else 100
    final_offset = offset if offset is not None else 0

    # Validate
    if final_limit < 1 or final_limit > 1000:
        raise ValidationError(f"Limit must be between 1 and 1000: {final_limit}")

    if final_offset < 0:
        raise ValidationError(f"Offset must be non-negative: {final_offset}")

    return final_limit, final_offset
