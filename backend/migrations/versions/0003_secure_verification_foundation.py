"""Add candidate contact verification metadata and OTP challenge persistence.

Revision ID: 0003_secure_verify
Revises: 0002_core_application_schema
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_secure_verify"
down_revision = "0002_core_application_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidates", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_candidates_email_verification_requires_email",
        "candidates",
        "email_verified_at IS NULL OR email IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_candidates_phone_verification_requires_phone",
        "candidates",
        "phone_verified_at IS NULL OR phone IS NOT NULL",
    )
    op.create_index(
        "uq_candidates_verified_contact_pair",
        "candidates",
        [sa.text("lower(email)"), "phone"],
        unique=True,
        postgresql_where=sa.text("email_verified_at IS NOT NULL AND phone_verified_at IS NOT NULL"),
    )

    op.create_table(
        "verification_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("destination_digest", sa.String(length=64), nullable=False),
        sa.Column("otp_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("channel IN ('mobile', 'email')", name="ck_verification_challenges_channel"),
        sa.CheckConstraint("purpose = 'contact_verification'", name="ck_verification_challenges_purpose"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_verification_challenges_attempt_count_nonnegative"),
        sa.CheckConstraint("length(destination_digest) = 64", name="ck_verification_challenges_destination_digest_length"),
        sa.CheckConstraint("length(otp_digest) = 64", name="ck_verification_challenges_digest_length"),
        sa.CheckConstraint("expires_at > created_at", name="ck_verification_challenges_expiry_after_creation"),
        sa.CheckConstraint(
            "consumed_at IS NULL OR invalidated_at IS NULL",
            name="ck_verification_challenges_single_terminal_state",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name="fk_verification_challenges_candidate_id_candidates",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_verification_challenges"),
    )
    op.create_index(
        "ix_verification_challenges_candidate_channel_purpose_created",
        "verification_challenges",
        ["candidate_id", "channel", "purpose", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_verification_challenges_expires_at",
        "verification_challenges",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_verification_challenges_expires_at", table_name="verification_challenges")
    op.drop_index(
        "ix_verification_challenges_candidate_channel_purpose_created",
        table_name="verification_challenges",
    )
    op.drop_table("verification_challenges")
    op.drop_index("uq_candidates_verified_contact_pair", table_name="candidates")
    op.drop_constraint("ck_candidates_phone_verification_requires_phone", "candidates", type_="check")
    op.drop_constraint("ck_candidates_email_verification_requires_email", "candidates", type_="check")
    op.drop_column("candidates", "phone_verified_at")
    op.drop_column("candidates", "email_verified_at")
