"""POS order customer and pay-later fields."""

from alembic import op
import sqlalchemy as sa

revision = "20260320_0007"
down_revision = "20260320_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_orders", sa.Column("customer_name", sa.String(length=128), nullable=True))
    op.add_column("pos_orders", sa.Column("customer_mobile", sa.String(length=20), nullable=True))
    op.add_column(
        "pos_orders",
        sa.Column("pay_later", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("pos_orders", "pay_later")
    op.drop_column("pos_orders", "customer_mobile")
    op.drop_column("pos_orders", "customer_name")
