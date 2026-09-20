"""table label unique per area (not per outlet)

Revision ID: 20260320_0004
Revises: 20260320_0003
Create Date: 2026-03-20

"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260320_0004"
down_revision: Union[str, None] = "20260320_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_venue_tables_outlet_label", "venue_tables", type_="unique")
    op.create_unique_constraint(
        "uq_venue_tables_area_label",
        "venue_tables",
        ["area_id", "label"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_venue_tables_area_label", "venue_tables", type_="unique")
    op.create_unique_constraint(
        "uq_venue_tables_outlet_label",
        "venue_tables",
        ["outlet_id", "label"],
    )
