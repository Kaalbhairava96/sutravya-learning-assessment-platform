"""Remove payment data and convert pending applications to free registrations.

Revision ID: 0015_free_registration
Revises: 0014_hackathon_registrations
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_free_registration"
down_revision = "0014_hackathon_registrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure every existing, email-verified application has its official ID before
    # payment-only fields are removed. Existing IDs are retained unchanged.
    op.execute(sa.text("""
        UPDATE registrations
        SET registration_id =
            'SUT-' ||
            to_char(created_at AT TIME ZONE 'Asia/Kolkata', 'YYYY/MM/DD') ||
            '-' ||
            lpad(nextval('registration_id_serial_seq')::text, 11, '0')
        WHERE registration_id IS NULL
    """))

    # An email-verified application is now a fully confirmed free registration.
    op.execute(sa.text("""
        UPDATE registrations
        SET status = 'active'
        WHERE status = 'payment_pending' OR status IS NULL
    """))

    # Strip historical fee/payment metadata from saved JSON details, including
    # unverified candidate applications that may complete OTP after this deploy.
    op.execute(sa.text("""
        UPDATE registrations
        SET details = (
            CAST(details AS jsonb)
            - 'registration_fee_paise'
            - 'currency'
            - 'payment_status'
        )::json
        WHERE details IS NOT NULL
    """))
    op.execute(sa.text("""
        UPDATE candidates
        SET pending_registration_details = (
            CAST(pending_registration_details AS jsonb)
            - 'registration_fee_paise'
            - 'currency'
            - 'payment_status'
        )::json
        WHERE pending_registration_details IS NOT NULL
    """))

    op.drop_constraint("ck_registrations_payment_status", "registrations", type_="check")
    op.drop_constraint("uq_registrations_payment_order_id", "registrations", type_="unique")
    op.drop_constraint("uq_registrations_payment_reference", "registrations", type_="unique")
    for column in (
        "payment_paid_at",
        "payment_currency",
        "payment_amount_paise",
        "payment_reference",
        "payment_order_id",
        "payment_provider",
        "payment_status",
    ):
        op.drop_column("registrations", column)


def downgrade() -> None:
    raise RuntimeError(
        "The free-registration migration removes payment data and converts pending applications. "
        "It cannot be safely downgraded without restoring the retired payment workflow and its data."
    )
