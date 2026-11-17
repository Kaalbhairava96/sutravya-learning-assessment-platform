"""Add free Healthcare Innovation Hackathon registration and OTP purposes."""

from alembic import op
import sqlalchemy as sa

revision = "0014_hackathon_registrations"
down_revision = "0013_admin_browser_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hackathon_registrations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("registration_id", sa.String(length=32), nullable=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("mobile", sa.String(length=16), nullable=False),
        sa.Column("college_name", sa.String(length=240), nullable=False),
        sa.Column("year_of_study", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(length=600), nullable=False),
        sa.Column("pin_code", sa.String(length=6), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"],
            name="fk_hackathon_registrations_candidate_id_candidates", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_hackathon_registrations"),
        sa.UniqueConstraint("candidate_id", name="uq_hackathon_registrations_candidate_id"),
        sa.UniqueConstraint("registration_id", name="uq_hackathon_registrations_public_id"),
        sa.UniqueConstraint("email", name="uq_hackathon_registrations_email"),
        sa.CheckConstraint("year_of_study BETWEEN 1 AND 4", name="ck_hackathon_registrations_year"),
        sa.CheckConstraint("status IN ('pending', 'registered')", name="ck_hackathon_registrations_status"),
        sa.CheckConstraint("length(pin_code) = 6", name="ck_hackathon_registrations_pin_length"),
    )
    op.create_table(
        "hackathon_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"],
            name="fk_hackathon_sessions_candidate_id_candidates", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_hackathon_sessions"),
        sa.UniqueConstraint("token_digest", name="uq_hackathon_sessions_token_digest"),
    )
    op.create_index("ix_hackathon_sessions_candidate_expiry", "hackathon_sessions", ["candidate_id", "expires_at"])
    with op.batch_alter_table("verification_challenges") as batch:
        batch.drop_constraint("ck_verification_challenges_purpose", type_="check")
        batch.create_check_constraint(
            "ck_verification_challenges_purpose",
            "purpose IN ('contact_verification', 'registration_verification', 'login', "
            "'hackathon_registration_verification', 'hackathon_login')",
        )


def downgrade() -> None:
    with op.batch_alter_table("verification_challenges") as batch:
        batch.drop_constraint("ck_verification_challenges_purpose", type_="check")
        batch.create_check_constraint(
            "ck_verification_challenges_purpose",
            "purpose IN ('contact_verification', 'registration_verification', 'login')",
        )
    op.drop_index("ix_hackathon_sessions_candidate_expiry", table_name="hackathon_sessions")
    op.drop_table("hackathon_sessions")
    op.drop_table("hackathon_registrations")
