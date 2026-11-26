"""Persist one-time administrator password reset challenges.

Revision ID: 0016_admin_password_resets
Revises: 0015_free_registration
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016_admin_password_resets"
down_revision = "0015_free_registration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_password_resets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("otp_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_count >= 0", name="ck_admin_password_resets_attempt_nonnegative"),
        sa.CheckConstraint("length(otp_digest) = 64", name="ck_admin_password_resets_digest_length"),
        sa.CheckConstraint("expires_at > created_at", name="ck_admin_password_resets_expiry_after_creation"),
        sa.CheckConstraint("consumed_at IS NULL OR invalidated_at IS NULL", name="ck_admin_password_resets_single_terminal_state"),
        sa.ForeignKeyConstraint(
            ["admin_user_id"], ["admin_users.id"], ondelete="CASCADE",
            name="fk_admin_password_resets_admin_user_id_admin_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_password_resets"),
    )
    op.create_index(
        "ix_admin_password_resets_admin_created",
        "admin_password_resets", ["admin_user_id", "created_at"], unique=False,
    )
    op.create_index(
        "ix_admin_password_resets_expires_at",
        "admin_password_resets", ["expires_at"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admin_password_resets_expires_at", table_name="admin_password_resets")
    op.drop_index("ix_admin_password_resets_admin_created", table_name="admin_password_resets")
    op.drop_table("admin_password_resets")
