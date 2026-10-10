"""worker snapshots: sites, device inventory, controller health

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-10 23:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the controller health columns and the sites and device_inventory tables."""
    op.add_column("controllers", sa.Column("health", sa.String(length=16), nullable=True))
    op.add_column("controllers", sa.Column("health_detail", sa.String(length=255), nullable=True))
    op.add_column(
        "controllers",
        sa.Column("health_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "controllers", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "controllers",
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_controllers_health"), "controllers", "health IN ('ok', 'degraded', 'down')"
    )
    op.create_table(
        "sites",
        sa.Column("controller_id", sa.Uuid(), nullable=False),
        sa.Column("site_uuid", sa.String(length=64), nullable=False),
        sa.Column("short_name", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["controller_id"],
            ["controllers.id"],
            name=op.f("fk_sites_controller_id_controllers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("controller_id", "site_uuid", name=op.f("pk_sites")),
    )
    op.create_table(
        "device_inventory",
        sa.Column("controller_id", sa.Uuid(), nullable=False),
        sa.Column("site_uuid", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("mac", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["controller_id", "site_uuid"],
            ["sites.controller_id", "sites.site_uuid"],
            name="fk_device_inventory_site",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "controller_id", "site_uuid", "device_id", name=op.f("pk_device_inventory")
        ),
    )
    op.create_index("ix_device_inventory_model", "device_inventory", ["model"], unique=False)
    op.create_index("ix_device_inventory_version", "device_inventory", ["version"], unique=False)


def downgrade() -> None:
    """Drop the snapshots and the controller health columns."""
    op.drop_index("ix_device_inventory_version", table_name="device_inventory")
    op.drop_index("ix_device_inventory_model", table_name="device_inventory")
    op.drop_table("device_inventory")
    op.drop_table("sites")
    op.drop_constraint(op.f("ck_controllers_health"), "controllers", type_="check")
    for column in ("capabilities", "last_seen_at", "health_checked_at", "health_detail", "health"):
        op.drop_column("controllers", column)
