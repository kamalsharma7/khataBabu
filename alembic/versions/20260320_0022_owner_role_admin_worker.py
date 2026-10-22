"""Expand business_owners.role for admin and worker staff logins."""

from alembic import op
import sqlalchemy as sa

revision = "20260320_0022"
down_revision = "20260320_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Original migration used Enum("owner") → VARCHAR(5); "worker" is 6 chars.
    op.alter_column(
        "business_owners",
        "role",
        existing_type=sa.Enum("owner", name="owner_role", native_enum=False),
        type_=sa.Enum(
            "owner",
            "admin",
            "worker",
            name="owner_role",
            native_enum=False,
            length=16,
        ),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "business_owners",
        "role",
        existing_type=sa.Enum(
            "owner",
            "admin",
            "worker",
            name="owner_role",
            native_enum=False,
            length=16,
        ),
        type_=sa.Enum("owner", name="owner_role", native_enum=False),
        existing_nullable=False,
    )
