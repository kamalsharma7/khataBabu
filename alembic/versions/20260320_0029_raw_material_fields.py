"""Raw-material fields on inventory items (category, cost, notes)."""

from alembic import op
import sqlalchemy as sa

revision = "20260320_0029"
down_revision = "20260320_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_items",
        sa.Column("category", sa.String(64), nullable=False, server_default="grocery"),
    )
    op.add_column(
        "inventory_items",
        sa.Column("cost_per_unit", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("notes", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_items", "notes")
    op.drop_column("inventory_items", "cost_per_unit")
    op.drop_column("inventory_items", "category")
