"""Custom exception classes for UniFi MCP Server."""

from typing import Any, Optional


class UniFiMCPException(Exception):
    """Base exception for UniFi MCP Server."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        """Initialize exception with message and optional details.

        Args:
            message: Human-readable error message
            details: Additional context about the error
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(UniFiMCPException):
    """Raised when configuration is invalid or missing."""

    pass


class AuthenticationError(UniFiMCPException):
    """Raised when authentication fails."""

    pass


class APIError(UniFiMCPException):
    """Raised when UniFi API returns an error."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize API error.

        Args:
            message: Human-readable error message
            status_code: HTTP status code
            response_data: Raw API response data
        """
        super().__init__(message, {"status_code": status_code, "response": response_data})
        self.status_code = status_code
        self.response_data = response_data


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
    ) -> None:
        """Initialize rate limit error.

        Args:
            message: Human-readable error message
            retry_after: Seconds until rate limit resets
        """
        super().__init__(message, status_code=429, response_data={"retry_after": retry_after})
        self.retry_after = retry_after


class ResourceNotFoundError(APIError):
    """Raised when requested resource is not found."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        """Initialize resource not found error.

        Args:
            resource_type: Type of resource (site, device, client, etc.)
            resource_id: ID of the resource
        """
        message = f"{resource_type} '{resource_id}' not found"
        super().__init__(message, status_code=404)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ValidationError(UniFiMCPException):
    """Raised when input validation fails."""

    pass


class NetworkError(UniFiMCPException):
    """Raised when network communication fails."""

    pass


class ConfirmationRequiredError(UniFiMCPException):
    """Raised when mutating operation requires confirmation."""

    def __init__(self, operation: str) -> None:
        """Initialize confirmation required error.

        Args:
            operation: Name of the operation requiring confirmation
        """
        message = (
            f"Operation '{operation}' requires confirmation. "
            "Set confirm=true to proceed with this mutating operation."
        )
        super().__init__(message, {"operation": operation})
        self.operation = operation
