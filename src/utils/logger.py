"""Structured logging configuration for UniFi MCP Server."""

import logging
import sys
from typing import Any

# Configure logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the module)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Set log level from parameter or environment variable
    log_level = level or "INFO"
    logger.setLevel(getattr(logging, log_level.upper()))

    # Avoid duplicate handlers
    if not logger.handlers:
        # Console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)

        # Formatter
        formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger


def log_api_request(
    logger: logging.Logger,
    method: str,
    url: str,
    status_code: int | None = None,
    duration_ms: float | None = None,
    **kwargs: Any,
) -> None:
    """Log API request details in structured format.

    Args:
        logger: Logger instance
        method: HTTP method
        url: Request URL
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        **kwargs: Additional context to log
    """
    context = {
        "method": method,
        "url": url,
        "status_code": status_code,
        "duration_ms": duration_ms,
        **kwargs,
    }

    # Remove None values
    context = {k: v for k, v in context.items() if v is not None}

    if status_code and status_code >= 400:
        logger.error(f"API request failed: {context}")
    else:
        logger.info(f"API request: {context}")


def log_audit_event(
    logger: logging.Logger,
    operation: str,
    resource_type: str,
    resource_id: str,
    success: bool,
    **kwargs: Any,
) -> None:
    """Log audit event for mutating operations.

    Args:
        logger: Logger instance
        operation: Operation performed (create, update, delete, etc.)
        resource_type: Type of resource affected
        resource_id: ID of the resource
        success: Whether operation succeeded
        **kwargs: Additional context to log
    """
    context = {
        "operation": operation,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "success": success,
        **kwargs,
    }

    level = logging.INFO if success else logging.ERROR
    logger.log(level, f"Audit event: {context}")
