"""audit retention: archive checkpoints, and deletes for the retention job only

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Alembic reads these module attributes; listing them marks them as used.
__all__ = ["branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade"]

#: Still refuses every change, except a DELETE from audit_log made by the
#: table's owner inside a transaction that set ``unifi_mcp.audit_retention``
#: (``python -m src.fleet.cli audit-retention`` does, after archiving the rows).
#: A least-privilege runtime role holds no DELETE grant either.
RETENTION_FUNCTION = """
CREATE OR REPLACE FUNCTION unifi_mcp_audit_log_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND TG_TABLE_NAME = 'audit_log'
       AND current_setting('unifi_mcp.audit_retention', true) = 'on'
       AND pg_has_role(current_user,
                       (SELECT relowner FROM pg_class WHERE oid = TG_RELID), 'USAGE') THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION '% is append-only: % is not allowed', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;
"""

#: The function as revision 0003 created it.
ORIGINAL_FUNCTION = """
CREATE OR REPLACE FUNCTION unifi_mcp_audit_log_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: % is not allowed', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;
"""


def upgrade() -> None:
    """Create audit_archives (append-only) and let only retention delete from audit_log."""
    op.create_table(
        "audit_archives",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("chain_id", sa.String(length=32), nullable=False),
        sa.Column("first_seq", sa.BigInteger(), nullable=False),
        sa.Column("last_seq", sa.BigInteger(), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("last_hash", sa.String(length=64), nullable=False),
        sa.Column("records", sa.Integer(), nullable=False),
        sa.Column("archive", sa.String(length=255), nullable=False),
        sa.Column("archive_sha256", sa.String(length=64), nullable=False),
        sa.Column("cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_archives")),
        sa.UniqueConstraint("chain_id", "first_seq", name="uq_audit_archives_chain_first_seq"),
    )
    op.execute(RETENTION_FUNCTION)
    op.execute(
        "CREATE TRIGGER audit_archives_no_update_delete BEFORE UPDATE OR DELETE "
        "ON audit_archives FOR EACH ROW EXECUTE FUNCTION unifi_mcp_audit_log_append_only()"
    )
    op.execute(
        "CREATE TRIGGER audit_archives_no_truncate BEFORE TRUNCATE ON audit_archives "
        "FOR EACH STATEMENT EXECUTE FUNCTION unifi_mcp_audit_log_append_only()"
    )


def downgrade() -> None:
    """Drop audit_archives and make audit_log fully append-only again.

    Refused once retention has run: the checkpoints are the only link between
    each remaining chain and its archived records, so dropping them would
    leave every such chain unverifiable.
    """
    archived = op.get_bind().execute(sa.text("SELECT count(*) FROM audit_archives")).scalar()
    if archived:
        raise RuntimeError(
            f"audit_archives holds {archived} checkpoint(s) from audit retention; "
            "downgrading below 0005 would make the remaining audit chains unverifiable"
        )
    op.drop_table("audit_archives")
    op.execute(ORIGINAL_FUNCTION)
