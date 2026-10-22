"""pos_orders.time_billing_excluded

Revision ID: 20260320_0018
"""

from alembic import op
import sqlalchemy as sa

revision = "20260320_0018"
down_revision = "20260320_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pos_orders",
        sa.Column("time_billing_excluded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("pos_orders", "time_billing_excluded", server_default=None)


def downgrade() -> None:
    op.drop_column("pos_orders", "time_billing_excluded")
