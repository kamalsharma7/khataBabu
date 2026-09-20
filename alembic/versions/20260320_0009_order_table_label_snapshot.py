"""Snapshot table label on orders for historical bills."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260320_0009"
down_revision = "20260320_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pos_orders",
        sa.Column("table_label_snapshot", sa.String(length=128), nullable=True),
    )
    op.execute(
        """
        UPDATE pos_orders o
        SET table_label_snapshot = vt.label
        FROM venue_tables vt
        WHERE o.venue_table_id = vt.id
          AND o.table_label_snapshot IS NULL
        """,
    )


def downgrade() -> None:
    op.drop_column("pos_orders", "table_label_snapshot")
