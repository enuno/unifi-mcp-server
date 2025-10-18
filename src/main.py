"""Main entry point for UniFi MCP Server."""

from fastmcp import FastMCP

from .config import Settings
from .utils import get_logger

# Initialize settings
settings = Settings()
logger = get_logger(__name__, settings.log_level)

# Initialize FastMCP server
mcp = FastMCP(
    "UniFi MCP Server",
    version="0.1.0",
    description="Model Context Protocol server for UniFi Network API",
)


@mcp.tool()
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify server is running.

    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "version": "0.1.0",
        "api_type": settings.api_type.value,
    }


def main() -> None:
    """Main entry point for the MCP server."""
    logger.info("Starting UniFi MCP Server...")
    logger.info(f"API Type: {settings.api_type.value}")
    logger.info(f"Base URL: {settings.base_url}")
    logger.info("Server ready to handle requests")


if __name__ == "__main__":
    main()
