"""Nested menu variations (type → size) and topping groups."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0035"
down_revision = "20260320_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "menu_item_variations",
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_menu_item_variations_parent",
        "menu_item_variations",
        "menu_item_variations",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_menu_item_variations_parent_id", "menu_item_variations", ["parent_id"])

    op.create_table(
        "menu_addon_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("menu_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("min_select", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_select", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_menu_addon_groups_menu_item_id", "menu_addon_groups", ["menu_item_id"])

    op.add_column(
        "menu_item_addons",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_menu_item_addons_group",
        "menu_item_addons",
        "menu_addon_groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_menu_item_addons_group", "menu_item_addons", type_="foreignkey")
    op.drop_column("menu_item_addons", "group_id")
    op.drop_index("ix_menu_addon_groups_menu_item_id", table_name="menu_addon_groups")
    op.drop_table("menu_addon_groups")
    op.drop_index("ix_menu_item_variations_parent_id", table_name="menu_item_variations")
    op.drop_constraint("fk_menu_item_variations_parent", "menu_item_variations", type_="foreignkey")
    op.drop_column("menu_item_variations", "parent_id")
