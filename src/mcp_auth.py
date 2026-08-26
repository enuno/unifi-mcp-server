"""Authentication boundary for network MCP transports."""

from __future__ import annotations

import secrets

from fastmcp.server.auth import AccessToken, TokenVerifier
from starlette.exceptions import HTTPException
from starlette.requests import Request

from .config import Settings, TransportMode


class ConfiguredBearerTokenVerifier(TokenVerifier):
    """Verify one operator-configured bearer token in constant time."""

    def __init__(self, token: str) -> None:
        """Initialize the verifier without exposing the token in metadata."""
        super().__init__()
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an authenticated principal only for the configured token."""
        if not secrets.compare_digest(token.encode(), self._token.encode()):
            return None
        return AccessToken(
            token=token,
            client_id="configured-mcp-client",
            scopes=[],
            claims={"authentication": "configured-bearer-token"},
        )


def require_authenticated_request(request: Request) -> None:
    """Reject custom HTTP routes unless FastMCP authenticated the request."""
    try:
        authenticated = request.user.is_authenticated
    except AssertionError:
        authenticated = False
    if not authenticated:
        raise HTTPException(status_code=401, detail="Authentication required")


def build_mcp_auth(settings: Settings) -> TokenVerifier | None:
    """Build network authentication while preserving token-free stdio."""
    if settings.server_transport == TransportMode.STDIO:
        return None
    if settings.mcp_auth_token is None:  # Defensive; Settings already fails closed.
        raise ValueError("MCP_AUTH_TOKEN is required for network transports")
    return ConfiguredBearerTokenVerifier(settings.mcp_auth_token.get_secret_value())
