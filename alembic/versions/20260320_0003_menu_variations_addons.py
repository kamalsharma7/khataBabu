"""menu item variations and addons

Revision ID: 20260320_0003
Revises: 20260320_0002
Create Date: 2026-03-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260320_0003"
down_revision: Union[str, None] = "20260320_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "menu_item_variations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("menu_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_menu_item_variations_menu_item_id", "menu_item_variations", ["menu_item_id"])

    op.create_table(
        "menu_item_addons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("menu_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_menu_item_addons_menu_item_id", "menu_item_addons", ["menu_item_id"])


def downgrade() -> None:
    op.drop_index("ix_menu_item_addons_menu_item_id", table_name="menu_item_addons")
    op.drop_table("menu_item_addons")
    op.drop_index("ix_menu_item_variations_menu_item_id", table_name="menu_item_variations")
    op.drop_table("menu_item_variations")
