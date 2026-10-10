"""Postgres tables of the controller registry (docs/FLEET_SCALING_PLAN.md §3.2).

Phase 2a creates only what it uses: ``credentials``, ``cloud_accounts`` and
``controllers``. Token, audit, site and inventory tables arrive with the
phases that read them. Schema changes go through Alembic migrations in
``src/fleet/db/migrations``; a test checks the two agree.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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
