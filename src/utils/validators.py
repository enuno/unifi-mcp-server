"""Input validation functions for UniFi MCP Server."""

import logging
import re

from .exceptions import ValidationError

logger = logging.getLogger(__name__)


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


_OBJECT_ID_RE = re.compile(r"^[a-f0-9]{24}$")
_UUID_RE = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
)


def validate_device_id(device_id: str) -> str:
    """Validate device ID format.

    Accepts two ID spaces:

    * 24-character hex MongoDB ObjectIds (the legacy internal stats API)
    * RFC-style UUIDs (the UniFi integration API — what
      ``get_network_topology`` and the v1 ``/devices`` endpoint return)

    Args:
        device_id: Device identifier (UUID or legacy ObjectId)

    Returns:
        Validated, lowercased device ID

    Raises:
        ValidationError: If device ID matches neither format
    """
    if not device_id or not isinstance(device_id, str):
        raise ValidationError("Device ID cannot be empty")

    lowered = device_id.lower()
    if not (_OBJECT_ID_RE.match(lowered) or _UUID_RE.match(lowered)):
        raise ValidationError(
            f"Invalid device ID format: {device_id} (expected 24-hex ObjectId or UUID)"
        )

    return lowered


def coerce_bool(value: bool | str | None) -> bool:
    """Coerce a value to bool, handling MCP JSON-RPC string serialization.

    MCP clients may send boolean parameters as strings ("true"/"false")
    rather than native booleans due to JSON-RPC serialization differences.

    Args:
        value: Value to coerce (bool, str, None, or other)

    Returns:
        Boolean value
    """
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


def validate_confirmation(
    confirm: bool | str | None, operation: str, dry_run: bool | str = False
) -> None:
    """Validate that confirmation is provided for mutating operations.

    Skips validation when dry_run is True, allowing users to preview
    operations without needing to set confirm=True.

    Args:
        confirm: Confirmation flag (bool or string from MCP serialization)
        operation: Operation name
        dry_run: If True, skip confirmation check (preview mode)

    Raises:
        ValidationError: If confirmation is not provided and not in dry-run mode
    """
    if coerce_bool(dry_run):
        return
    if not coerce_bool(confirm):
        raise ValidationError(
            f"Operation '{operation}' requires confirmation. Set confirm=true to proceed."
        )


def validate_limit_offset(limit: int | None = None, offset: int | None = None) -> tuple[int, int]:
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
