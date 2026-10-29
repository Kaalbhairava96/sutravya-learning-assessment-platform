"""Add email OTP registration, passwordless sessions and rate-limit storage.

Revision ID: 0004_registration_accounts
Revises: 0003_secure_verify
"""

from alembic import context, op
import sqlalchemy as sa


revision = "0004_registration_accounts"
down_revision = "0003_secure_verify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Offline mode only renders a SQL script and has no result set to inspect.
    # The unique index still enforces this invariant when that script is applied.
    if not context.is_offline_mode():
        duplicate_email = op.get_bind().execute(
            sa.text(
                "SELECT lower(email) FROM candidates "
                "WHERE email_verified_at IS NOT NULL "
                "GROUP BY lower(email) HAVING count(*) > 1 LIMIT 1"
            )
        ).first()
        if duplicate_email is not None:
            raise RuntimeError(
                "Cannot add verified-email uniqueness: existing verified email duplicates must be resolved first."
            )

    op.add_column("candidates", sa.Column("pending_stream", sa.String(length=32), nullable=True))
    op.create_index(
        "uq_candidates_verified_email",
        "candidates",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("email_verified_at IS NOT NULL"),
        sqlite_where=sa.text("email_verified_at IS NOT NULL"),
    )

    op.add_column("registrations", sa.Column("registration_id", sa.String(length=32), nullable=True))
    op.add_column("registrations", sa.Column("stream", sa.String(length=32), nullable=True))
    op.create_unique_constraint("uq_registrations_public_id", "registrations", ["registration_id"])

    op.drop_constraint("ck_verification_challenges_purpose", "verification_challenges", type_="check")
    op.create_check_constraint(
        "ck_verification_challenges_purpose",
        "verification_challenges",
        "purpose IN ('contact_verification', 'registration_verification', 'login')",
    )

    op.create_table(
        "candidate_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"],
            name="fk_candidate_sessions_candidate_id_candidates", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_candidate_sessions"),
        sa.UniqueConstraint("token_digest", name="uq_candidate_sessions_token_digest"),
    )
    op.create_index("ix_candidate_sessions_candidate_expiry", "candidate_sessions", ["candidate_id", "expires_at"])

    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("subject_digest", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("request_count >= 0", name="ck_rate_limit_buckets_nonnegative_count"),
        sa.PrimaryKeyConstraint("id", name="pk_rate_limit_buckets"),
        sa.UniqueConstraint("scope", "subject_digest", name="uq_rate_limit_buckets_scope_subject"),
    )
    op.create_index("ix_rate_limit_buckets_window", "rate_limit_buckets", ["window_started_at"])


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "Cannot render this downgrade offline: live database checks are required to protect registration, "
            "pending-registration, session, OTP, and rate-limit data."
        )

    bind = op.get_bind()
    registration_rows = bind.execute(
        sa.text(
            "SELECT 1 FROM registrations "
            "WHERE registration_id IS NOT NULL OR stream IS NOT NULL LIMIT 1"
        )
    ).first()
    if registration_rows is not None:
        raise RuntimeError("Cannot downgrade registration accounts while completed registration identifiers or streams exist.")

    pending_streams = bind.execute(
        sa.text("SELECT 1 FROM candidates WHERE pending_stream IS NOT NULL LIMIT 1")
    ).first()
    if pending_streams is not None:
        raise RuntimeError("Cannot downgrade registration accounts while pending candidate registrations exist.")

    sessions = bind.execute(sa.text("SELECT 1 FROM candidate_sessions LIMIT 1")).first()
    if sessions is not None:
        raise RuntimeError("Cannot downgrade registration accounts while candidate sessions exist.")

    rate_limits = bind.execute(sa.text("SELECT 1 FROM rate_limit_buckets LIMIT 1")).first()
    if rate_limits is not None:
        raise RuntimeError("Cannot downgrade registration accounts while rate-limit records exist.")

    purpose_rows = bind.execute(
        sa.text(
            "SELECT 1 FROM verification_challenges "
            "WHERE purpose IN ('registration_verification', 'login') LIMIT 1"
        )
    ).first()
    if purpose_rows is not None:
        raise RuntimeError(
            "Cannot downgrade registration accounts while registration/login OTP challenges exist."
        )

    op.drop_index("ix_rate_limit_buckets_window", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
    op.drop_index("ix_candidate_sessions_candidate_expiry", table_name="candidate_sessions")
    op.drop_table("candidate_sessions")
    op.drop_constraint("uq_registrations_public_id", "registrations", type_="unique")
    op.drop_column("registrations", "stream")
    op.drop_column("registrations", "registration_id")
    op.drop_index("uq_candidates_verified_email", table_name="candidates")
    op.drop_column("candidates", "pending_stream")
    op.drop_constraint("ck_verification_challenges_purpose", "verification_challenges", type_="check")
    op.create_check_constraint(
        "ck_verification_challenges_purpose",
        "verification_challenges",
        "purpose = 'contact_verification'",
    )
