"""variation/addon food_type and variation is_available

Revision ID: 20260320_0020
"""

from alembic import op
import sqlalchemy as sa

revision = "20260320_0020"
down_revision = "20260320_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "menu_item_variations",
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "menu_item_variations",
        sa.Column("food_type", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "menu_item_addons",
        sa.Column("food_type", sa.String(length=16), nullable=True),
    )
    op.alter_column("menu_item_variations", "is_available", server_default=None)


def downgrade() -> None:
    op.drop_column("menu_item_addons", "food_type")
    op.drop_column("menu_item_variations", "food_type")
    op.drop_column("menu_item_variations", "is_available")
