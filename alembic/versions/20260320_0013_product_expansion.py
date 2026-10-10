"""Customer fields, GST, staff, sales employees, inventory, bill save."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0013"
down_revision = "20260320_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_orders", sa.Column("customer_locality", sa.String(length=255), nullable=True))
    op.add_column("pos_orders", sa.Column("customer_relation", sa.String(length=32), nullable=True))
    op.add_column(
        "pos_orders",
        sa.Column("bill_saved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "menu_items",
        sa.Column("gst_applicable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "menu_items",
        sa.Column("cgst_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "menu_items",
        sa.Column("sgst_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )

    op.add_column("menu_item_variations", sa.Column("weight_grams", sa.Integer(), nullable=True))
    op.add_column("menu_item_addons", sa.Column("weight_grams", sa.Integer(), nullable=True))

    op.add_column(
        "pos_bills",
        sa.Column("cgst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "pos_bills",
        sa.Column("sgst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "pos_bills",
        sa.Column("tip_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )

    op.create_table(
        "platform_sales_employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_code", sa.String(length=32), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("mobile", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("employee_code", name="uq_platform_sales_employees_code"),
        sa.UniqueConstraint("mobile", name="uq_platform_sales_employees_mobile"),
    )

    op.add_column(
        "businesses",
        sa.Column("assigned_sales_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_businesses_sales_employee",
        "businesses",
        "platform_sales_employees",
        ["assigned_sales_employee_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "owner_password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["business_owners.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_owner_password_reset_tokens_owner",
        "owner_password_reset_tokens",
        ["owner_id"],
    )

    op.create_table(
        "inventory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default="pcs"),
        sa.Column("current_stock", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Numeric(12, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("outlet_id", "name", name="uq_inventory_items_outlet_name"),
    )

    op.create_table(
        "menu_item_inventory_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("menu_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty_per_serve", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("menu_item_id", "inventory_item_id", name="uq_menu_item_inventory"),
    )

    op.create_table(
        "inventory_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delta", sa.Numeric(12, 3), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("order_line_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_line_id"], ["pos_order_lines.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_inventory_tx_outlet_created", "inventory_transactions", ["outlet_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_inventory_tx_outlet_created", table_name="inventory_transactions")
    op.drop_table("inventory_transactions")
    op.drop_table("menu_item_inventory_links")
    op.drop_table("inventory_items")
    op.drop_index("ix_owner_password_reset_tokens_owner", table_name="owner_password_reset_tokens")
    op.drop_table("owner_password_reset_tokens")
    op.drop_constraint("fk_businesses_sales_employee", "businesses", type_="foreignkey")
    op.drop_column("businesses", "assigned_sales_employee_id")
    op.drop_table("platform_sales_employees")
    op.drop_column("pos_bills", "tip_amount")
    op.drop_column("pos_bills", "sgst_amount")
    op.drop_column("pos_bills", "cgst_amount")
    op.drop_column("menu_item_addons", "weight_grams")
    op.drop_column("menu_item_variations", "weight_grams")
    op.drop_column("menu_items", "sgst_percent")
    op.drop_column("menu_items", "cgst_percent")
    op.drop_column("menu_items", "gst_applicable")
    op.drop_column("pos_orders", "bill_saved_at")
    op.drop_column("pos_orders", "customer_relation")
    op.drop_column("pos_orders", "customer_locality")
