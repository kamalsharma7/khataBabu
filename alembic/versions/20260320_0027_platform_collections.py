"""Platform subscription collections from venues."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0027"
down_revision = "20260320_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_inr", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("next_payment_date", sa.Date(), nullable=False),
        sa.Column("tenure_months", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["recorded_by_admin_id"],
            ["platform_admins.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("tenure_months >= 1", name="ck_platform_collections_tenure_months"),
        sa.CheckConstraint("amount_inr > 0", name="ck_platform_collections_amount_positive"),
    )
    op.create_index("ix_platform_collections_business_id", "platform_collections", ["business_id"])
    op.create_index("ix_platform_collections_payment_date", "platform_collections", ["payment_date"])
    op.create_index(
        "ix_platform_collections_next_payment_date",
        "platform_collections",
        ["next_payment_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_platform_collections_next_payment_date", table_name="platform_collections")
    op.drop_index("ix_platform_collections_payment_date", table_name="platform_collections")
    op.drop_index("ix_platform_collections_business_id", table_name="platform_collections")
    op.drop_table("platform_collections")
