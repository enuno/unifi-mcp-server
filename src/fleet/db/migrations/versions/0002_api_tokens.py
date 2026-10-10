"""api tokens

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10 08:53:35.592961
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the api_tokens table."""
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=63), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("allow_modules", postgresql.ARRAY(sa.String(length=63)), nullable=True),
        sa.Column(
            "deny_modules",
            postgresql.ARRAY(sa.String(length=63)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "controller_labels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "name ~ '^[a-z0-9][a-z0-9_-]{0,62}$'", name=op.f("ck_api_tokens_name_format")
        ),
        sa.CheckConstraint(
            "role IN ('viewer', 'operator', 'admin', 'fleet-admin')",
            name=op.f("ck_api_tokens_role"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_tokens")),
        sa.UniqueConstraint("name", name=op.f("uq_api_tokens_name")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_api_tokens_token_hash")),
    )


def downgrade() -> None:
    """Drop the api_tokens table."""
    op.drop_table("api_tokens")
