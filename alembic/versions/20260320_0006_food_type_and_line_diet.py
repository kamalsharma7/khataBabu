"""food_type on menu and order lines

Revision ID: 20260320_0006
Revises: 20260320_0005
Create Date: 2026-03-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260320_0006"
down_revision: Union[str, None] = "20260320_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "menu_items",
        sa.Column(
            "food_type",
            sa.Enum("veg", "non_veg", "egg", name="food_type", native_enum=False),
            nullable=False,
            server_default="veg",
        ),
    )
    op.execute(
        "UPDATE menu_items SET food_type = CASE WHEN is_veg THEN 'veg' ELSE 'non_veg' END",
    )
    op.add_column(
        "pos_order_lines",
        sa.Column(
            "food_type",
            sa.Enum("veg", "non_veg", "egg", name="food_type_line", native_enum=False),
            nullable=False,
            server_default="veg",
        ),
    )


def downgrade() -> None:
    op.drop_column("pos_order_lines", "food_type")
    op.drop_column("menu_items", "food_type")
