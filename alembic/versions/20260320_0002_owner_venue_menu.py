"""owner venue areas tables and menu

Revision ID: 20260320_0002
Revises: 20260320_0001
Create Date: 2026-03-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260320_0002"
down_revision: Union[str, None] = "20260320_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "venue_areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outlet_id", "name", name="uq_venue_areas_outlet_name"),
    )
    op.create_index("ix_venue_areas_outlet_id", "venue_areas", ["outlet_id"])

    op.create_table(
        "venue_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column(
            "resource_kind",
            sa.Enum("dine_table", "time_based", name="resource_kind", native_enum=False),
            nullable=False,
        ),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["area_id"], ["venue_areas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outlet_id", "label", name="uq_venue_tables_outlet_label"),
    )
    op.create_index("ix_venue_tables_outlet_id", "venue_tables", ["outlet_id"])
    op.create_index("ix_venue_tables_area_id", "venue_tables", ["area_id"])

    op.create_table(
        "menu_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outlet_id", "name", name="uq_menu_categories_outlet_name"),
    )
    op.create_index("ix_menu_categories_outlet_id", "menu_categories", ["outlet_id"])

    op.create_table(
        "menu_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("short_code", sa.String(length=32), nullable=True),
        sa.Column("is_veg", sa.Boolean(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["menu_categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_menu_items_outlet_id", "menu_items", ["outlet_id"])
    op.create_index("ix_menu_items_category_id", "menu_items", ["category_id"])


def downgrade() -> None:
    op.drop_table("menu_items")
    op.drop_table("menu_categories")
    op.drop_table("venue_tables")
    op.drop_table("venue_areas")
