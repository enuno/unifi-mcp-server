"""Input validation functions for UniFi MCP Server."""

import ipaddress
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
    """Validate an IPv4 address in dotted-quad form.

    Parsed with :mod:`ipaddress`, which accepts only four ASCII decimal octets
    of 0-255 without leading zeros. Whitespace, signs, ``_`` digit separators,
    non-ASCII digits and octal-looking octets such as ``010`` are rejected
    rather than passed on to the controller.

    Args:
        ip: IP address string

    Returns:
        The address in canonical dotted-quad form

    Raises:
        ValidationError: If IP address is invalid
    """
    # ipaddress also accepts integers (3232235786 -> 192.168.1.10), so insist on str.
    if not isinstance(ip, str):
        raise ValidationError(f"Invalid IP address format: {ip!r}")
    try:
        return str(ipaddress.IPv4Address(ip))
    except ValueError as e:
        raise ValidationError(f"Invalid IP address format: {ip!r}") from e


def validate_ip_or_cidr(value: str) -> str:
    """Validate an IPv4 address or an IPv4 network in CIDR form.

    A value without ``/`` is validated as an address. A value with ``/`` must
    have a valid address and a prefix length of 0-32 (or a netmask); host bits
    are cleared, so ``192.168.1.10/24`` becomes ``192.168.1.0/24``.

    Args:
        value: Address (``192.168.1.10``) or network (``192.168.1.0/24``)

    Returns:
        The address or network in canonical form

    Raises:
        ValidationError: If the value is not a valid address or network
    """
    if not isinstance(value, str):
        raise ValidationError(f"Invalid IP address or CIDR: {value!r}")
    if "/" not in value:
        try:
            return validate_ip_address(value)
        except ValidationError as e:
            raise ValidationError(f"Invalid IP address or CIDR: {value!r}") from e
    try:
        return str(ipaddress.IPv4Network(value, strict=False))
    except ValueError as e:
        raise ValidationError(f"Invalid IP address or CIDR: {value!r}") from e


def validate_port(port: int) -> int:
    """Validate port number.

    Args:
        port: Port number

    Returns:
        Validated port number

    Raises:
        ValidationError: If port is invalid
    """
    # bool is a subclass of int; without this check True passes as port 1.
    if isinstance(port, bool) or not isinstance(port, int) or port < 1 or port > 65535:
        raise ValidationError(f"Invalid port number: {port!r}")

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
_UUID_RE = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")


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


_BACKUP_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")


def validate_backup_filename(backup_filename: str) -> str:
    """Validate a controller backup filename before it is used in a path.

    The filename is interpolated into a controller request path
    (``/proxy/network/data/backup/{filename}``). Without validation, path
    separators and ``..`` segments let a caller retarget the authenticated
    GET at any controller route, and the bytes returned can then be written
    to disk. Allow only a single, plain path component.

    Args:
        backup_filename: Backup filename supplied by the caller

    Returns:
        The validated filename, unchanged

    Raises:
        ValidationError: If the filename is empty, contains a path separator
            or ``..`` segment, or has characters outside ``[A-Za-z0-9._-]``
    """
    if not backup_filename or not isinstance(backup_filename, str):
        raise ValidationError("Backup filename cannot be empty")

    if "/" in backup_filename or "\\" in backup_filename or backup_filename in (".", ".."):
        raise ValidationError(f"Invalid backup filename: {backup_filename!r}")

    if not _BACKUP_FILENAME_RE.match(backup_filename):
        raise ValidationError(
            f"Invalid backup filename: {backup_filename!r} "
            "(allowed: letters, digits, '.', '_', '-'; no path separators)"
        )

    return backup_filename
