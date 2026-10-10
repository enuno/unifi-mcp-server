"""fleet registry: credentials, cloud accounts, controllers

Revision ID: 0001
Revises:
Create Date: 2026-10-09 22:59:25.197551
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the credentials, cloud_accounts and controllers tables."""
    op.create_table(
        "credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("key_fingerprint", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credentials")),
    )
    op.create_table(
        "cloud_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=63), nullable=False),
        sa.Column("api_type", sa.String(length=16), nullable=False),
        sa.Column("cloud_api_url", sa.String(length=255), nullable=True),
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column(
            "labels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "api_type IN ('cloud-v1', 'cloud-ea')", name=op.f("ck_cloud_accounts_api_type")
        ),
        sa.CheckConstraint(
            "name ~ '^[a-z0-9][a-z0-9_-]{0,62}$'", name=op.f("ck_cloud_accounts_name_format")
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["credentials.id"],
            name=op.f("fk_cloud_accounts_credential_id_credentials"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cloud_accounts")),
        sa.UniqueConstraint("name", name=op.f("uq_cloud_accounts_name")),
    )
    op.create_table(
        "controllers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=63), nullable=False),
        sa.Column("api_type", sa.String(length=16), nullable=False),
        sa.Column("local_host", sa.String(length=255), nullable=True),
        sa.Column("local_port", sa.Integer(), nullable=True),
        sa.Column("local_verify_ssl", sa.Boolean(), nullable=True),
        sa.Column("cloud_api_url", sa.String(length=255), nullable=True),
        sa.Column("default_site", sa.String(length=255), nullable=True),
        sa.Column("credential_id", sa.Uuid(), nullable=True),
        sa.Column("cloud_account_id", sa.Uuid(), nullable=True),
        sa.Column(
            "labels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "api_type <> 'local' OR local_host IS NOT NULL",
            name=op.f("ck_controllers_local_has_host"),
        ),
        sa.CheckConstraint(
            "api_type IN ('local', 'cloud-v1', 'cloud-ea')", name=op.f("ck_controllers_api_type")
        ),
        sa.CheckConstraint(
            "name ~ '^[a-z0-9][a-z0-9_-]{0,62}$'", name=op.f("ck_controllers_name_format")
        ),
        sa.CheckConstraint(
            "credential_id IS NOT NULL OR cloud_account_id IS NOT NULL",
            name=op.f("ck_controllers_has_credential"),
        ),
        sa.ForeignKeyConstraint(
            ["cloud_account_id"],
            ["cloud_accounts.id"],
            name=op.f("fk_controllers_cloud_account_id_cloud_accounts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["credentials.id"],
            name=op.f("fk_controllers_credential_id_credentials"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_controllers")),
        sa.UniqueConstraint("name", name=op.f("uq_controllers_name")),
    )
    op.create_index(
        "uq_controllers_single_default",
        "controllers",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    """Drop the registry tables."""
    op.drop_index(
        "uq_controllers_single_default",
        table_name="controllers",
        postgresql_where=sa.text("is_default"),
    )
    op.drop_table("controllers")
    op.drop_table("cloud_accounts")
    op.drop_table("credentials")
