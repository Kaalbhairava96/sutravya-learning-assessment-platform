"""Add four-category QualiNova applications and provider-neutral payment fields."""
from alembic import op
import sqlalchemy as sa

revision = "0011_qualinova_paid_registration"
down_revision = "0010_question_level_timing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("pending_registration_details", sa.JSON(), nullable=True))
    op.add_column("registrations", sa.Column("details", sa.JSON(), nullable=True))
    op.add_column("registrations", sa.Column("payment_status", sa.String(length=24), nullable=False, server_default="not_required"))
    op.add_column("registrations", sa.Column("payment_provider", sa.String(length=40), nullable=True))
    op.add_column("registrations", sa.Column("payment_order_id", sa.String(length=160), nullable=True))
    op.add_column("registrations", sa.Column("payment_reference", sa.String(length=160), nullable=True))
    op.add_column("registrations", sa.Column("payment_amount_paise", sa.Integer(), nullable=True))
    op.add_column("registrations", sa.Column("payment_currency", sa.String(length=3), nullable=False, server_default="INR"))
    op.add_column("registrations", sa.Column("payment_paid_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_registrations_payment_order_id", "registrations", ["payment_order_id"])
    op.create_unique_constraint("uq_registrations_payment_reference", "registrations", ["payment_reference"])
    op.create_check_constraint(
        "ck_registrations_payment_status", "registrations",
        "payment_status IN ('not_required', 'pending', 'created', 'paid', 'failed', 'cancelled', 'refunded')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_registrations_payment_status", "registrations", type_="check")
    op.drop_constraint("uq_registrations_payment_reference", "registrations", type_="unique")
    op.drop_constraint("uq_registrations_payment_order_id", "registrations", type_="unique")
    op.drop_column("registrations", "payment_paid_at")
    op.drop_column("registrations", "payment_currency")
    op.drop_column("registrations", "payment_amount_paise")
    op.drop_column("registrations", "payment_reference")
    op.drop_column("registrations", "payment_order_id")
    op.drop_column("registrations", "payment_provider")
    op.drop_column("registrations", "payment_status")
    op.drop_column("registrations", "details")
    op.drop_column("candidates", "pending_registration_details")
