"""Area time billing defaults and order time sessions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260320_0010"
down_revision = "20260320_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "venue_areas",
        sa.Column("billing_mode", sa.String(length=16), nullable=False, server_default="dine_in"),
    )
    op.add_column("venue_areas", sa.Column("operating_start", sa.Time(), nullable=True))
    op.add_column("venue_areas", sa.Column("operating_end", sa.Time(), nullable=True))
    op.add_column("venue_areas", sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True))

    op.add_column(
        "pos_orders",
        sa.Column("time_session_start", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pos_orders",
        sa.Column("time_session_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("pos_orders", sa.Column("time_billed_minutes", sa.Integer(), nullable=True))
    op.add_column(
        "pos_orders",
        sa.Column("hourly_rate_snapshot", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column("pos_orders", sa.Column("time_charge", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("pos_orders", "time_charge")
    op.drop_column("pos_orders", "hourly_rate_snapshot")
    op.drop_column("pos_orders", "time_billed_minutes")
    op.drop_column("pos_orders", "time_session_end")
    op.drop_column("pos_orders", "time_session_start")
    op.drop_column("venue_areas", "hourly_rate")
    op.drop_column("venue_areas", "operating_end")
    op.drop_column("venue_areas", "operating_start")
    op.drop_column("venue_areas", "billing_mode")
