"""POS orders, KOT, billing

Revision ID: 20260320_0005
Revises: 20260320_0004
Create Date: 2026-03-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260320_0005"
down_revision: Union[str, None] = "20260320_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outlet_counters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("counter_date", sa.Date(), nullable=False),
        sa.Column("counter_kind", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "outlet_id",
            "counter_date",
            "counter_kind",
            name="uq_outlet_counters_outlet_date_kind",
        ),
    )
    op.create_index("ix_outlet_counters_outlet_id", "outlet_counters", ["outlet_id"])

    op.create_table(
        "pos_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "order_type",
            sa.Enum("dine_in", "takeaway", "delivery", name="order_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("order_number", sa.Integer(), nullable=False),
        sa.Column("venue_table_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "settled", "cancelled", name="order_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("guest_count", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("opened_by_owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opened_by_owner_id"], ["business_owners.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["venue_table_id"], ["venue_tables.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_orders_outlet_id", "pos_orders", ["outlet_id"])
    op.create_index("ix_pos_orders_venue_table_id", "pos_orders", ["venue_table_id"])

    op.create_table(
        "pos_order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("menu_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("menu_item_variation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("variation_name", sa.String(length=128), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("addons_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending_kot",
                "in_kot",
                "served",
                "cancelled",
                name="order_line_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["menu_item_variation_id"], ["menu_item_variations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["pos_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_order_lines_order_id", "pos_order_lines", ["order_id"])

    op.create_table(
        "pos_order_line_addons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("menu_item_addon_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_addon_id"], ["menu_item_addons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_line_id"], ["pos_order_lines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_order_line_addons_order_line_id", "pos_order_line_addons", ["order_line_id"])

    op.create_table(
        "pos_kots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kot_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "cancelled", name="kot_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["pos_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_kots_outlet_id", "pos_kots", ["outlet_id"])
    op.create_index("ix_pos_kots_order_id", "pos_kots", ["order_id"])

    op.create_table(
        "pos_kot_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["kot_id"], ["pos_kots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_line_id"], ["pos_order_lines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_kot_lines_kot_id", "pos_kot_lines", ["kot_id"])
    op.create_index("ix_pos_kot_lines_order_line_id", "pos_kot_lines", ["order_line_id"])

    op.create_table(
        "pos_bills",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_number", sa.Integer(), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("round_off", sa.Numeric(12, 2), nullable=False),
        sa.Column("grand_total", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "settled", "void", name="bill_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["pos_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_bills_outlet_id", "pos_bills", ["outlet_id"])
    op.create_index("ix_pos_bills_order_id", "pos_bills", ["order_id"])

    op.create_table(
        "pos_bill_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "method",
            sa.Enum(
                "cash",
                "upi",
                "card",
                "wallet",
                "bank",
                "due",
                "complimentary",
                "other",
                name="payment_method",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["pos_bills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_bill_payments_bill_id", "pos_bill_payments", ["bill_id"])


def downgrade() -> None:
    op.drop_table("pos_bill_payments")
    op.drop_table("pos_bills")
    op.drop_table("pos_kot_lines")
    op.drop_table("pos_kots")
    op.drop_table("pos_order_line_addons")
    op.drop_table("pos_order_lines")
    op.drop_table("pos_orders")
    op.drop_table("outlet_counters")
