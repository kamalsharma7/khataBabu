"""P0: business settings, day close, audit, refunds, invoice fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0017"
down_revision = "20260320_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_pos_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("invoice_prefix", sa.String(16), nullable=False, server_default="INV"),
        sa.Column("registered_address", sa.String(512), nullable=True),
        sa.Column("trading_name", sa.String(255), nullable=True),
        sa.Column(
            "worker_max_discount_percent",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="10",
        ),
        sa.Column(
            "max_discount_percent",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="50",
        ),
        sa.Column("manager_pin_hash", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("business_id", name="uq_business_pos_settings_business"),
    )
    op.create_index("ix_business_pos_settings_business_id", "business_pos_settings", ["business_id"])

    op.create_table(
        "tenant_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "outlet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outlets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_owners.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_username", sa.String(64), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("summary", sa.String(512), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_audit_logs_business_id", "tenant_audit_logs", ["business_id"])
    op.create_index("ix_tenant_audit_logs_outlet_id", "tenant_audit_logs", ["outlet_id"])
    op.create_index("ix_tenant_audit_logs_created_at", "tenant_audit_logs", ["created_at"])

    op.create_table(
        "outlet_business_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "outlet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outlets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("opening_cash", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("expected_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_closing_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_variance", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_sales_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(1024), nullable=True),
        sa.Column(
            "opened_by_owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_owners.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "closed_by_owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_owners.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("outlet_id", "business_date", name="uq_outlet_business_days_outlet_date"),
    )

    op.create_table(
        "outlet_cash_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_day_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outlet_business_days.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(512), nullable=False),
        sa.Column(
            "created_by_owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_owners.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column("pos_bills", sa.Column("invoice_number", sa.Integer(), nullable=True))
    op.add_column("pos_bills", sa.Column("invoice_code", sa.String(32), nullable=True))
    op.add_column(
        "pos_bills",
        sa.Column("refunded_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )

    op.create_table(
        "pos_bill_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_bills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "outlet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outlets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(512), nullable=False),
        sa.Column(
            "created_by_owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_owners.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "approved_by_owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("business_owners.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_bill_refunds_bill_id", "pos_bill_refunds", ["bill_id"])


def downgrade() -> None:
    op.drop_table("pos_bill_refunds")
    op.drop_column("pos_bills", "refunded_total")
    op.drop_column("pos_bills", "invoice_code")
    op.drop_column("pos_bills", "invoice_number")
    op.drop_table("outlet_cash_movements")
    op.drop_table("outlet_business_days")
    op.drop_table("tenant_audit_logs")
    op.drop_table("business_pos_settings")
