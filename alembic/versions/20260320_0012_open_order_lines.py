"""Open / custom order lines without required menu item."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260320_0012"
down_revision = "20260320_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("pos_order_lines", "menu_item_id", existing_type=sa.UUID(), nullable=True)
    op.add_column(
        "pos_order_lines",
        sa.Column("is_open_item", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("pos_order_lines", "is_open_item")
    op.alter_column("pos_order_lines", "menu_item_id", existing_type=sa.UUID(), nullable=False)
