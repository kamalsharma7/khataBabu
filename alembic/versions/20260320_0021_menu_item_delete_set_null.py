"""Allow menu item delete while preserving order line history (SET NULL FK)."""

from alembic import op

revision = "20260320_0021"
down_revision = "20260320_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "pos_order_lines_menu_item_id_fkey",
        "pos_order_lines",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "pos_order_lines_menu_item_id_fkey",
        "pos_order_lines",
        "menu_items",
        ["menu_item_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "pos_order_lines_menu_item_id_fkey",
        "pos_order_lines",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "pos_order_lines_menu_item_id_fkey",
        "pos_order_lines",
        "menu_items",
        ["menu_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
