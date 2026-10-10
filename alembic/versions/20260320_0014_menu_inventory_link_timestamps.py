"""Add updated_at to menu_item_inventory_links (TimestampMixin parity)."""

from alembic import op
import sqlalchemy as sa

revision = "20260320_0014"
down_revision = "20260320_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "menu_item_inventory_links",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("menu_item_inventory_links", "updated_at")
