"""Link sales team salary expenditures to sales employees."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0026"
down_revision = "20260320_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_expenditures",
        sa.Column("sales_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_platform_expenditures_sales_employee_id",
        "platform_expenditures",
        "platform_sales_employees",
        ["sales_employee_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_platform_expenditures_sales_employee_id",
        "platform_expenditures",
        ["sales_employee_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_platform_expenditures_sales_employee_id", table_name="platform_expenditures")
    op.drop_constraint(
        "fk_platform_expenditures_sales_employee_id",
        "platform_expenditures",
        type_="foreignkey",
    )
    op.drop_column("platform_expenditures", "sales_employee_id")
