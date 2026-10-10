"""Postgres tables of the controller registry (docs/FLEET_SCALING_PLAN.md §3.2).

Phase 2a created ``credentials``, ``cloud_accounts`` and ``controllers``;
Phase 2b adds ``api_tokens``, ``audit_log`` and ``audit_chain_heads``. Site and
inventory tables arrive with the phases that read them. Schema changes go through Alembic migrations in
``src/fleet/db/migrations``; a test checks the two agree.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

#: Deterministic constraint names, so migrations can refer to them.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

#: Same rule as ControllerProfile.name: the routing handle callers type.
NAME_PATTERN = "^[a-z0-9][a-z0-9_-]{0,62}$"


class Base(DeclarativeBase):
    """Declarative base with the naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class _Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Credential(Base):
    """An API key, encrypted with UNIFI_FLEET_CREDENTIAL_KEY."""

    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CloudAccount(_Timestamps, Base):
    """A Site Manager / cloud API key shared by the consoles behind it."""

    __tablename__ = "cloud_accounts"
    __table_args__ = (
        CheckConstraint("api_type IN ('cloud-v1', 'cloud-ea')", name="api_type"),
        CheckConstraint(f"name ~ '{NAME_PATTERN}'", name="name_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    api_type: Mapped[str] = mapped_column(String(16), nullable=False)
    cloud_api_url: Mapped[str | None] = mapped_column(String(255))
    credential_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("credentials.id", ondelete="RESTRICT"), nullable=False
    )
    labels: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    credential: Mapped[Credential] = relationship(lazy="joined")


class Controller(_Timestamps, Base):
    """One UniFi controller tools can be routed to."""

    __tablename__ = "controllers"
    __table_args__ = (
        CheckConstraint("api_type IN ('local', 'cloud-v1', 'cloud-ea')", name="api_type"),
        CheckConstraint(f"name ~ '{NAME_PATTERN}'", name="name_format"),
        CheckConstraint("api_type <> 'local' OR local_host IS NOT NULL", name="local_has_host"),
        CheckConstraint(
            "credential_id IS NOT NULL OR cloud_account_id IS NOT NULL", name="has_credential"
        ),
        # At most one default controller.
        Index(
            "uq_controllers_single_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    api_type: Mapped[str] = mapped_column(String(16), nullable=False)
    local_host: Mapped[str | None] = mapped_column(String(255))
    local_port: Mapped[int | None] = mapped_column(Integer)
    local_verify_ssl: Mapped[bool | None] = mapped_column(Boolean)
    cloud_api_url: Mapped[str | None] = mapped_column(String(255))
    default_site: Mapped[str | None] = mapped_column(String(255))
    credential_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("credentials.id", ondelete="RESTRICT")
    )
    cloud_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="RESTRICT")
    )
    labels: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    credential: Mapped[Credential | None] = relationship(lazy="joined")
    cloud_account: Mapped[CloudAccount | None] = relationship(lazy="joined")


class ApiToken(Base):
    """A bearer token issued by the server; only its SHA-256 hash is stored."""

    __tablename__ = "api_tokens"
    __table_args__ = (
        CheckConstraint("role IN ('viewer', 'operator', 'admin', 'fleet-admin')", name="role"),
        CheckConstraint(f"name ~ '{NAME_PATTERN}'", name="name_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    allow_modules: Mapped[list[str] | None] = mapped_column(ARRAY(String(63)))
    deny_modules: Mapped[list[str]] = mapped_column(
        ARRAY(String(63)), nullable=False, server_default=text("'{}'")
    )
    controller_labels: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLogEntry(Base):
    """One audit record, append-only (a trigger refuses UPDATE, DELETE, TRUNCATE).

    ``record`` is the record exactly as hashed (payload fields encrypted when
    an audit key is set); the other columns copy fields out of it for queries.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        UniqueConstraint("chain_id", "seq", name="uq_audit_log_chain_seq"),
        Index("ix_audit_log_ts", "ts"),
        Index("ix_audit_log_operation", "operation"),
        Index("ix_audit_log_principal_id", "principal_id"),
        Index("ix_audit_log_controller", "controller"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    tier: Mapped[str | None] = mapped_column(String(16))
    controller: Mapped[str | None] = mapped_column(String(63))
    principal_id: Mapped[str | None] = mapped_column(String(255))
    call_id: Mapped[str | None] = mapped_column(String(32))
    chain_id: Mapped[str] = mapped_column(String(32), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record: Mapped[str] = mapped_column(Text, nullable=False)


class AuditChainHead(Base):
    """Latest position of each server's audit chain, for verification and anchoring."""

    __tablename__ = "audit_chain_heads"

    chain_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
