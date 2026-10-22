"""Customer master (CRM) per outlet + link from POS orders."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0031"
down_revision = "20260320_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("locality", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("anniversary", sa.Date(), nullable=True),
        sa.Column("relation", sa.String(16), nullable=True),
        sa.Column("tags", sa.String(512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="pos"),
        sa.Column("marketing_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_spend_inr", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("first_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_owner_id"], ["business_owners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_outlet_id", "customers", ["outlet_id"])
    op.create_index("ix_customers_outlet_last_visit", "customers", ["outlet_id", "last_visit_at"])
    op.create_index(
        "uq_customers_outlet_phone",
        "customers",
        ["outlet_id", "phone"],
        unique=True,
        postgresql_where=sa.text("phone IS NOT NULL"),
    )

    op.add_column(
        "pos_orders",
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_pos_orders_customer_id",
        "pos_orders",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_pos_orders_customer_id", "pos_orders", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_pos_orders_customer_id", table_name="pos_orders")
    op.drop_constraint("fk_pos_orders_customer_id", "pos_orders", type_="foreignkey")
    op.drop_column("pos_orders", "customer_id")
    op.drop_index("uq_customers_outlet_phone", table_name="customers")
    op.drop_index("ix_customers_outlet_last_visit", table_name="customers")
    op.drop_index("ix_customers_outlet_id", table_name="customers")
    op.drop_table("customers")
