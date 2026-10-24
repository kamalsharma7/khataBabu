"""Outlet tax profiles (GST / VAT / other) and bill tax snapshot fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0033"
down_revision = "20260320_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outlet_tax_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("scheme", sa.String(16), nullable=False, server_default="gst"),
        sa.Column("gst_slab", sa.String(16), nullable=True),
        sa.Column("rate_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("cgst_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("sgst_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("igst_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("title", sa.String(64), nullable=False, server_default="GST"),
        sa.Column("cgst_title", sa.String(64), nullable=True),
        sa.Column("sgst_title", sa.String(64), nullable=True),
        sa.Column("igst_title", sa.String(64), nullable=True),
        sa.Column("title_suffix", sa.String(32), nullable=True),
        sa.Column("method", sa.String(16), nullable=False, server_default="forward"),
        sa.Column("applies_dine_in", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("applies_takeaway", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("applies_delivery", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outlet_tax_profiles_outlet_id", "outlet_tax_profiles", ["outlet_id"])

    op.add_column("pos_bills", sa.Column("igst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("pos_bills", sa.Column("tax_method", sa.String(16), nullable=True))
    op.add_column("pos_bills", sa.Column("tax_label", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("pos_bills", "tax_label")
    op.drop_column("pos_bills", "tax_method")
    op.drop_column("pos_bills", "igst_amount")
    op.drop_index("ix_outlet_tax_profiles_outlet_id", table_name="outlet_tax_profiles")
    op.drop_table("outlet_tax_profiles")
