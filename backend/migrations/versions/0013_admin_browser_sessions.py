"""Add revocable administrator browser sessions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_admin_browser_sessions"
down_revision = "0012_mbbs_ug_pg_subject_blocks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["admin_user_id"], ["admin_users.id"],
            name="fk_admin_sessions_admin_user_id_admin_users", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_sessions"),
        sa.UniqueConstraint("token_digest", name="uq_admin_sessions_token_digest"),
    )
    op.create_index("ix_admin_sessions_admin_expiry", "admin_sessions", ["admin_user_id", "expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_sessions_admin_expiry", table_name="admin_sessions")
    op.drop_table("admin_sessions")
