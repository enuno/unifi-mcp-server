"""audit log

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10 09:00:33.626741
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Refuses changes to audit_log for every role, including the table owner.
APPEND_ONLY_FUNCTION = """
CREATE FUNCTION unifi_mcp_audit_log_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: % is not allowed', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;
"""


def upgrade() -> None:
    """Create the audit tables and make audit_log append-only."""
    op.create_table(
        "audit_chain_heads",
        sa.Column("chain_id", sa.String(length=32), nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("chain_id", name=op.f("pk_audit_chain_heads")),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=32), nullable=False),
        sa.Column(
            "ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("operation", sa.String(length=128), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=True),
        sa.Column("controller", sa.String(length=63), nullable=True),
        sa.Column("principal_id", sa.String(length=255), nullable=True),
        sa.Column("call_id", sa.String(length=32), nullable=True),
        sa.Column("chain_id", sa.String(length=32), nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("record", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
        sa.UniqueConstraint("chain_id", "seq", name="uq_audit_log_chain_seq"),
        sa.UniqueConstraint("event_id", name=op.f("uq_audit_log_event_id")),
    )
    op.create_index("ix_audit_log_controller", "audit_log", ["controller"], unique=False)
    op.create_index("ix_audit_log_operation", "audit_log", ["operation"], unique=False)
    op.create_index("ix_audit_log_principal_id", "audit_log", ["principal_id"], unique=False)
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"], unique=False)
    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER audit_log_no_update_delete BEFORE UPDATE OR DELETE ON audit_log "
        "FOR EACH ROW EXECUTE FUNCTION unifi_mcp_audit_log_append_only()"
    )
    op.execute(
        "CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log "
        "FOR EACH STATEMENT EXECUTE FUNCTION unifi_mcp_audit_log_append_only()"
    )


def downgrade() -> None:
    """Drop the audit tables (and with them the append-only triggers)."""
    op.drop_index("ix_audit_log_ts", table_name="audit_log")
    op.drop_index("ix_audit_log_principal_id", table_name="audit_log")
    op.drop_index("ix_audit_log_operation", table_name="audit_log")
    op.drop_index("ix_audit_log_controller", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("audit_chain_heads")
    op.execute("DROP FUNCTION unifi_mcp_audit_log_append_only()")
