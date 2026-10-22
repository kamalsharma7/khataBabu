"""Daily par stock fields on inventory items."""

from alembic import op
import sqlalchemy as sa

revision = "20260320_0015"
down_revision = "20260320_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_items",
        sa.Column("tracks_daily", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "inventory_items",
        sa.Column("daily_par", sa.Numeric(12, 3), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("stock_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("today_opening", sa.Numeric(12, 3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_items", "today_opening")
    op.drop_column("inventory_items", "stock_date")
    op.drop_column("inventory_items", "daily_par")
    op.drop_column("inventory_items", "tracks_daily")
