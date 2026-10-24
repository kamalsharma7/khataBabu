"""VAT / item-scoped tax: menu items linked to a tax profile."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0034"
down_revision = "20260320_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outlet_tax_profiles",
        sa.Column("scope", sa.String(16), nullable=False, server_default="venue"),
    )
    op.create_table(
        "outlet_tax_profile_items",
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("menu_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["outlet_tax_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("profile_id", "menu_item_id"),
    )
    op.create_index("ix_outlet_tax_profile_items_item", "outlet_tax_profile_items", ["menu_item_id"])


def downgrade() -> None:
    op.drop_index("ix_outlet_tax_profile_items_item", table_name="outlet_tax_profile_items")
    op.drop_table("outlet_tax_profile_items")
    op.drop_column("outlet_tax_profiles", "scope")
