"""platform_sales_employees aadhaar and pan

Revision ID: 20260320_0019
"""

from alembic import op
import sqlalchemy as sa

revision = "20260320_0019"
down_revision = "20260320_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_sales_employees",
        sa.Column("aadhaar_number", sa.String(length=12), nullable=False, server_default="000000000000"),
    )
    op.add_column(
        "platform_sales_employees",
        sa.Column("pan_number", sa.String(length=10), nullable=False, server_default="AAAAA0000A"),
    )
    op.alter_column("platform_sales_employees", "aadhaar_number", server_default=None)
    op.alter_column("platform_sales_employees", "pan_number", server_default=None)


def downgrade() -> None:
    op.drop_column("platform_sales_employees", "pan_number")
    op.drop_column("platform_sales_employees", "aadhaar_number")
