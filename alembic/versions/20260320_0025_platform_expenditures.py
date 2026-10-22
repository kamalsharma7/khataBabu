"""Platform business expenditure ledger."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0025"
down_revision = "20260320_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_expenditures",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "sales_team_salary",
                "ca_expenses",
                "it_cost",
                "marketing_cost",
                "travel_cost",
                "other",
                name="platform_expenditure_category",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("amount_inr", sa.Numeric(14, 2), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("spent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["recorded_by_admin_id"],
            ["platform_admins.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_expenditures_category", "platform_expenditures", ["category"])
    op.create_index("ix_platform_expenditures_spent_at", "platform_expenditures", ["spent_at"])


def downgrade() -> None:
    op.drop_index("ix_platform_expenditures_spent_at", table_name="platform_expenditures")
    op.drop_index("ix_platform_expenditures_category", table_name="platform_expenditures")
    op.drop_table("platform_expenditures")
