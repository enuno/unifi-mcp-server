"""Server-issued API tokens (docs/FLEET_SCALING_PLAN.md §3.6, Phase 2b).

Tokens are 32 random bytes with a ``umcp_`` prefix, shown once at creation;
only their SHA-256 hash is stored (enough for high-entropy tokens, so no slow
password hash is needed). Each carries a role and optional module and
controller-label filters, which :class:`FleetTokenVerifier` passes to the
tool wrapper as access-token claims.

Revocation reaches a server within :data:`CACHE_SECONDS`: verified tokens are
cached that long, so a revoked token is refused at the next lookup.
"""

import hashlib
import hmac
import secrets
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastmcp.server.auth import AccessToken, TokenVerifier
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from ..access import ROLES
from ..utils.exceptions import ResourceNotFoundError, ValidationError
from ..utils.logger import get_logger
from .db.models import ApiToken

logger = get_logger(__name__)

TOKEN_PREFIX = "umcp_"  # nosec B105 - format marker, not a password

#: Lifetime of a new token unless another is given (0 means never expires).
DEFAULT_EXPIRY_DAYS = 90

#: How long a verified token is trusted without asking the database again.
CACHE_SECONDS = 30.0


def generate_token() -> str:
    """Return a new bearer token."""
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the stored form of a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TokenInfo:
    """A token's metadata; never its value or hash."""

    id: str
    name: str
    role: str
    allow_modules: list[str] | None
    deny_modules: list[str]
    controller_labels: dict[str, str]
    created_by: str
    created_at: str | None
    expires_at: str | None
    revoked_at: str | None
    last_used_at: str | None

    @classmethod
    def of(cls, row: ApiToken) -> "TokenInfo":
        """Build from a database row."""

        def iso(value: datetime | None) -> str | None:
            return value.isoformat() if value is not None else None

        return cls(
            id=str(row.id),
            name=row.name,
            role=row.role,
            allow_modules=list(row.allow_modules) if row.allow_modules is not None else None,
            deny_modules=list(row.deny_modules),
            controller_labels=dict(row.controller_labels),
            created_by=row.created_by,
            created_at=iso(row.created_at),
            expires_at=iso(row.expires_at),
            revoked_at=iso(row.revoked_at),
            last_used_at=iso(row.last_used_at),
        )


def _check_role(role: str) -> None:
    if role not in ROLES:
        raise ValidationError(f"role must be one of: {', '.join(ROLES)}")


class TokenStore:
    """The ``api_tokens`` table."""

    def __init__(self, engine: AsyncEngine) -> None:
        """Create a store on the registry's engine."""
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def create(
        self,
        *,
        name: str,
        role: str,
        created_by: str,
        expires_in_days: int = DEFAULT_EXPIRY_DAYS,
        allow_modules: Iterable[str] | None = None,
        deny_modules: Iterable[str] = (),
        controller_labels: Mapping[str, str] | None = None,
    ) -> tuple[str, TokenInfo]:
        """Issue a token.

        Args:
            name: Unique token name
            role: viewer, operator, admin or fleet-admin
            created_by: Principal id of the issuer
            expires_in_days: Lifetime; 0 for a token that never expires
            allow_modules: Only tool modules matching these patterns
            deny_modules: Refuse tool modules matching these patterns
            controller_labels: Labels a controller must carry to be reachable

        Returns:
            The token (shown only now) and its metadata

        Raises:
            ValidationError: For a bad role, negative lifetime, or duplicate name
        """
        _check_role(role)
        if expires_in_days < 0:
            raise ValidationError("expires_in_days must be 0 (never) or more")
        token = generate_token()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            if expires_in_days
            else None
        )
        row = ApiToken(
            name=name,
            token_hash=hash_token(token),
            role=role,
            allow_modules=list(allow_modules) if allow_modules is not None else None,
            deny_modules=list(deny_modules),
            controller_labels=dict(controller_labels or {}),
            created_by=created_by,
            expires_at=expires_at,
        )
        try:
            async with self._sessions.begin() as session:
                session.add(row)
                await session.flush()
                await session.refresh(row)
        except IntegrityError as e:
            raise ValidationError(f"token '{name}' already exists or is invalid") from e
        return token, TokenInfo.of(row)

    async def list(self) -> list[TokenInfo]:
        """Return every token's metadata, newest first."""
        async with self._sessions() as session:
            rows = (
                (await session.execute(select(ApiToken).order_by(ApiToken.created_at.desc())))
                .scalars()
                .all()
            )
        return [TokenInfo.of(row) for row in rows]

    async def _get(self, session: Any, name: str) -> ApiToken:
        row: ApiToken | None = await session.scalar(select(ApiToken).where(ApiToken.name == name))
        if row is None:
            raise ResourceNotFoundError("token", name)
        return row

    async def revoke(self, name: str) -> TokenInfo:
        """Revoke a token; revoking twice keeps the first revocation time."""
        async with self._sessions.begin() as session:
            row = await self._get(session, name)
            if row.revoked_at is None:
                row.revoked_at = datetime.now(timezone.utc)
            return TokenInfo.of(row)

    async def set_role(self, name: str, role: str) -> TokenInfo:
        """Change a token's role."""
        _check_role(role)
        async with self._sessions.begin() as session:
            row = await self._get(session, name)
            row.role = role
            return TokenInfo.of(row)

    async def lookup(self, token: str) -> dict[str, Any] | None:
        """Return the claims of an active token, recording its use.

        Returns:
            Claims for the tool wrapper, or None if the token is unknown,
            revoked or expired
        """
        now = datetime.now(timezone.utc)
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(ApiToken).where(ApiToken.token_hash == hash_token(token))
            )
            if row is None or row.revoked_at is not None:
                return None
            if row.expires_at is not None and row.expires_at <= now:
                return None
            await session.execute(
                update(ApiToken).where(ApiToken.id == row.id).values(last_used_at=now)
            )
            return {
                "token_id": str(row.id),
                "name": row.name,
                "role": row.role,
                "allow_modules": list(row.allow_modules) if row.allow_modules is not None else None,
                "deny_modules": list(row.deny_modules),
                "controller_labels": dict(row.controller_labels),
                "expires_at": row.expires_at.timestamp() if row.expires_at else None,
            }


class FleetTokenVerifier(TokenVerifier):
    """Accepts MCP_AUTH_TOKEN tokens and active server-issued tokens."""

    def __init__(
        self,
        env_tokens: Iterable[str],
        store: TokenStore,
        cache_seconds: float = CACHE_SECONDS,
    ) -> None:
        """Create the verifier.

        Args:
            env_tokens: Break-glass tokens from MCP_AUTH_TOKEN
            store: Where issued tokens are looked up
            cache_seconds: How long a lookup result is reused
        """
        super().__init__()
        self._env_tokens = [t.encode("utf-8") for t in env_tokens]
        self._store = store
        self._cache_seconds = cache_seconds
        self._cache: dict[str, tuple[float, dict[str, Any] | None]] = {}

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an access token with claims, or None to refuse the request."""
        candidate = token.encode("utf-8")
        if any(hmac.compare_digest(candidate, env) for env in self._env_tokens):
            return AccessToken(token=token, client_id="mcp-client", scopes=[])
        if not token.startswith(TOKEN_PREFIX):
            return None

        key = hash_token(token)
        cached = self._cache.get(key)
        if cached is not None and cached[0] > time.monotonic():
            claims = cached[1]
        else:
            try:
                claims = await self._store.lookup(token)
            except Exception as e:
                # Fail closed and do not cache: the next request asks again.
                logger.warning("API token lookup failed; refusing the request: %s", e)
                return None
            self._cache[key] = (time.monotonic() + self._cache_seconds, claims)

        if claims is None:
            return None
        expires_at = claims.get("expires_at")
        if expires_at is not None and expires_at <= time.time():
            return None
        return AccessToken(
            token=token,
            client_id=str(claims["name"]),
            scopes=[],
            expires_at=int(expires_at) if expires_at is not None else None,
            claims=claims,
        )
