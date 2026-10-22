"""Owner purchase invoices (vendor bills) with line items and stock-in."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0030"
down_revision = "20260320_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_name", sa.String(255), nullable=False),
        sa.Column("vendor_phone", sa.String(20), nullable=True),
        sa.Column("vendor_gstin", sa.String(20), nullable=True),
        sa.Column("invoice_number", sa.String(64), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("po_reference", sa.String(64), nullable=True),
        sa.Column("subtotal_inr", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_inr", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_inr", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("other_charges_inr", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_inr", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("paid_inr", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("payment_mode", sa.String(32), nullable=True),
        sa.Column("payment_status", sa.String(16), nullable=False, server_default="unpaid"),
        sa.Column("status", sa.String(16), nullable=False, server_default="saved"),
        sa.Column("stock_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_owner_id"], ["business_owners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_invoices_outlet_id", "purchase_invoices", ["outlet_id"])
    op.create_index("ix_purchase_invoices_invoice_date", "purchase_invoices", ["invoice_date"])
    op.create_index("ix_purchase_invoices_vendor_name", "purchase_invoices", ["vendor_name"])

    op.create_table(
        "purchase_invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("unit_price_inr", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("line_total_inr", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["invoice_id"], ["purchase_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_invoice_lines_invoice_id", "purchase_invoice_lines", ["invoice_id"])

    op.create_table(
        "purchase_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_inr", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_mode", sa.String(32), nullable=False, server_default="cash"),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["purchase_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_owner_id"], ["business_owners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_payments_invoice_id", "purchase_payments", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_payments_invoice_id", table_name="purchase_payments")
    op.drop_table("purchase_payments")
    op.drop_index("ix_purchase_invoice_lines_invoice_id", table_name="purchase_invoice_lines")
    op.drop_table("purchase_invoice_lines")
    op.drop_index("ix_purchase_invoices_vendor_name", table_name="purchase_invoices")
    op.drop_index("ix_purchase_invoices_invoice_date", table_name="purchase_invoices")
    op.drop_index("ix_purchase_invoices_outlet_id", table_name="purchase_invoices")
    op.drop_table("purchase_invoices")
