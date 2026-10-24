"""Venue-wise staff permission grants (owner ticks per receptionist per outlet)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260320_0032"
down_revision = "20260320_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_permission_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(64), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_by_owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["business_owners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_owner_id"], ["business_owners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outlet_id", "owner_id", "permission", name="uq_staff_perm_outlet_owner_code"),
    )
    op.create_index("ix_staff_permission_grants_outlet_id", "staff_permission_grants", ["outlet_id"])
    op.create_index("ix_staff_permission_grants_owner_id", "staff_permission_grants", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_staff_permission_grants_owner_id", table_name="staff_permission_grants")
    op.drop_index("ix_staff_permission_grants_outlet_id", table_name="staff_permission_grants")
    op.drop_table("staff_permission_grants")
